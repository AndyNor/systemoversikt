# -*- coding: utf-8 -*-
"""
Management command: systembruk_opprett_fra_ad_tilgangsgrupper

Formål
-------
Oppdage hvilke virksomheter som «synes» i medlemskapet til systemets valgte
AD-tilgangsgrupper (slik gruppedata er synket inn i Kartoteket), og sikre at det
finnes en SystemBruk-rad for hver slik virksomhet for det aktuelle systemet.

Dette kjører uten LDAP: alt bygger på ADgroup.member (JSON med DN-er), lokale
ADgroup-rader og User med Profile — samme forutsetninger som
adgruppe_transitive_users_db_only() i views.py.

Dataflyt (per system)
---------------------
1. Ta alle tilgangsgrupper knyttet til systemet (M2M tilgangsgrupper_ad).
2. Utvid transitivt til unike User via adgruppe_transitive_users_db_only():
   nestede grupper følges så lenge undergruppen finnes som ADgroup i databasen.
3. Samle unike Profile.virksomhet (representasjonsfeltet «Virksomhet / Etat:
   Representerer») for disse brukerne. Brukere uten profil eller uten satt
   virksomhet bidrar ikke til listen.
4. For hver virksomhet: SystemBruk.objects.get_or_create(system, brukergruppe).
   Modellen har unique_together (system, brukergruppe). Finnes raden fra før,
   settes ibruk til True dersom den var False (ingen ny rad opprettes).

Systemutvalg
------------
- livslop_status er ikke 6 eller 7 (under avvikling / avviklet), i tråd med
  filtrering brukt andre steder for «systembruk»-lister.
- Minst én tilgangsgruppe er knyttet (filter på M2M).

  (System.ibruk brukes ikke her — feltet er upålitelig / misvisende for dette formålet.)

Begrensninger / tolkning
------------------------
- Medlemmer som ikke kan mappes til User (CN/DN-matching) eller som er
  datamaskiner/grupper uten ADgroup-rad i DB, telles ikke.
- antall_brukere og andre felt på SystemBruk settes ikke automatisk; ved nye rader
  settes kommentar + ibruk=True. Eksisterende rader får ibruk=True hvis de var deaktivert.
- Gjentatte kjøringer: ingen duplikatrader; allerede aktive systembruk endres ikke.

Drift
------
Følger samme mønster som øvrige management commands: IntegrasjonKonfigurasjon
(kodeord), ApplicationLog, runtime/helsestatus på integrasjonen, push_pushover
ved uventet feil.
"""
import json
import os
import time
import traceback

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from systemoversikt.models import ApplicationLog, IntegrasjonKonfigurasjon, System, SystemBruk
from systemoversikt.views import adgruppe_transitive_users_db_only, push_pushover


class Command(BaseCommand):
	def handle(self, **options):
		# Én IntegrasjonKonfigurasjon-rad per «jobbtype» — brukes i oversikter og sporbarhet.
		INTEGRASJON_KODEORD = "systembruk_synk_ad_tilgangsgrupper"
		LOG_EVENT_TYPE = "Systembruk fra AD-tilgangsgrupper"
		KILDE = "Kartoteket (ADgroup + User)"
		PROTOKOLL = "database"
		BESKRIVELSE = "Oppretter systembruk ut fra virksomheter funnet blant medlemmer i AD-tilgangsgrupper"
		FILNAVN = ""
		URL = ""
		FREKVENS = "Etter behov / nattlig"

		try:
			int_config = IntegrasjonKonfigurasjon.objects.get(kodeord=INTEGRASJON_KODEORD)
		except IntegrasjonKonfigurasjon.DoesNotExist:
			int_config = IntegrasjonKonfigurasjon.objects.create(
				kodeord=INTEGRASJON_KODEORD,
				kilde=KILDE,
				protokoll=PROTOKOLL,
				informasjon=BESKRIVELSE,
				sp_filnavn=FILNAVN,
				url=URL,
				frekvensangivelse=FREKVENS,
				log_event_type=LOG_EVENT_TYPE,
			)

		SCRIPT_NAVN = os.path.basename(__file__)
		int_config.script_navn = SCRIPT_NAVN
		int_config.sp_filnavn = json.dumps(FILNAVN)
		int_config.helsestatus = "Forbereder"
		int_config.save()

		timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
		runtime_t0 = time.time()

		try:
			# distinct() nødvendig pga. join mot M2M ved filter på tilgangsgrupper_ad.
			systemer = (
				System.objects.exclude(livslop_status__in=[6, 7])
				.filter(tilgangsgrupper_ad__isnull=False)
				.distinct()
				.prefetch_related("tilgangsgrupper_ad")
			)

			totalt_systemer = 0  # systemer som faktisk loopes (har minst én gruppe i praksis)
			totalt_opprettet = 0  # nye SystemBruk-rader
			totalt_eksisterte = 0  # get_or_create traff eksisterende (system, virksomhet)
			totalt_ibruk_aktivert = 0  # eksisterende rad hadde ibruk=False, satt til True
			totalt_ingen_brukere = 0  # AD-utvidelse ga ingen User i Kartoteket
			totalt_ingen_virksomhet = 0  # brukere fantes, men ingen hadde profile.virksomhet satt

			for system in systemer:
				totalt_systemer += 1
				grupper = list(system.tilgangsgrupper_ad.all())
				if not grupper:
					continue

				# Ingen nettverkskall: kun ADgroup.member + User/ADgroup i databasen.
				brukere = adgruppe_transitive_users_db_only(grupper)
				if not brukere:
					totalt_ingen_brukere += 1
					print(f"  {system.pk} {system}: ingen matchende brukere i databasen")
					continue

				# Én bulk-spørring: unike virksomheter blant utvidede brukere.
				# profile__virksomhet er «Representerer»-feltet (ikke innlogget_som).
				vir_ids = set(
					User.objects.filter(pk__in=[u.pk for u in brukere])
					.exclude(profile__virksomhet_id__isnull=True)
					.values_list("profile__virksomhet_id", flat=True)
				)
				if not vir_ids:
					totalt_ingen_virksomhet += 1
					print(f"  {system.pk} {system}: ingen brukere med satt virksomhet i profil")
					continue

				nye_for_system = 0
				ibruk_aktivert_for_system = 0
				for vid in vir_ids:
					_obj, opprettet = SystemBruk.objects.get_or_create(
						system=system,
						brukergruppe_id=vid,
						defaults={
							"ibruk": True,
							"kommentar": "Automatisk opprettet ut fra medlemmer i systemets AD-tilgangsgrupper.",
						},
					)
					if opprettet:
						totalt_opprettet += 1
						nye_for_system += 1
					else:
						totalt_eksisterte += 1
						if not _obj.ibruk:
							_obj.ibruk = True
							_obj.save()
							totalt_ibruk_aktivert += 1
							ibruk_aktivert_for_system += 1

				print(
					f"  {system.pk} {system}: {len(vir_ids)} virksomheter fra AD-medlemmer, "
					f"{nye_for_system} nye systembruk, {ibruk_aktivert_for_system} eksisterende satt i bruk"
				)

			logg_message = (
				f"Ferdig: {totalt_systemer} systemer med AD-grupper. "
				f"Opprettet {totalt_opprettet} nye systembruk, "
				f"{totalt_eksisterte} fantes allerede (herav {totalt_ibruk_aktivert} fikk ibruk=True). "
				f"Uten brukere i DB: {totalt_ingen_brukere}, uten virksomhet på profiler: {totalt_ingen_virksomhet}."
			)
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)

			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message
			runtime_t1 = time.time()
			int_config.runtime = int(runtime_t1 - runtime_t0)
			int_config.elementer = totalt_opprettet + totalt_ibruk_aktivert
			int_config.helsestatus = "Vellykket"
			int_config.save()

		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			int_config.helsestatus = f"Feilet\n{traceback.format_exc()}"
			int_config.save()
			push_pushover(f"{SCRIPT_NAVN} feilet")
