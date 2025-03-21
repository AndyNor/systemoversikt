# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.db import transaction
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
import os, time, sys, json, csv, requests

class Command(BaseCommand):
	def handle(self, **options):
		"""
		Her sjekker vi først klassen "ansvarlige" for alle felter og avhengig av relasjonstype identifiserer vi om det er aktive relasjoner til dem. Normalt benyttes mangetilmange-relasjoner mot ansvarlige, men det er noen få unntak med OneToOneFields.
		"""
		INTEGRASJON_KODEORD = "lokal_rydde_ansvarlig"
		LOG_EVENT_TYPE = 'Rydde ansvarlige'
		KILDE = "Lokal"
		PROTOKOLL = "N/A"
		BESKRIVELSE = "Fjerne ansvarlige uten tildelt ansvar"
		FILNAVN = ""
		URL = ""
		FREKVENS = "Hver natt"

		try:
			int_config = IntegrasjonKonfigurasjon.objects.get(kodeord=INTEGRASJON_KODEORD)
		except:
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

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")

		try:
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

			runtime_t0 = time.time()
			antall_slettet = 0

			@transaction.atomic
			def perform_atomic_update():
				alle_ansvarlige = Ansvarlig.objects.all()
				m2m_relations = []
				fk_relations = []

				for ansvarlig in alle_ansvarlige:
					if ansvarlig.brukernavn.profile.accountdisable == False: # aktiv bruker
						dagens_seksjon_cache = ansvarlig.cache_seksjon
						faktisk_seksjon = ansvarlig.brukernavn.profile.org_unit
						if dagens_seksjon_cache != faktisk_seksjon:
							ansvarlig.cache_seksjon = faktisk_seksjon
							ansvarlig.save()
							print(f"Endret seksjon (cache) for {ansvarlig} til {faktisk_seksjon}")

				print("Identifiserer aktuelle relasjonsfelt:\n")

				for f in Ansvarlig._meta.get_fields(include_hidden=False):
					if f.get_internal_type() in ["ManyToManyField"]:
						#print(f.__dict__)
						m2m_relations.append(f)

					if f.get_internal_type() in ["ForeignKey"]:
						#print(f.__dict__)
						fk_relations.append(f)

				print("m2m_relations")
				for m2m in m2m_relations:
					print("* %s.%s" % (m2m.related_model._meta, m2m.field.name))

				print("\nfk_relations")
				for fk in fk_relations:
					try:
						print("* %s.%s" % (fk.related_model._meta, fk.field.name))
					except:
						fk_relations.remove(fk)

				print("\nLeter etter brukere som kan deaktiveres")


				for ansvarlig in alle_ansvarlige:
					ansvar_teller = 0
					for m2m in m2m_relations:
						ansvarlig_for = getattr(ansvarlig, m2m.name).all()
						ansvar_teller += len(ansvarlig_for)

					for fk in fk_relations:
						model = fk.related_model
						fieldname = fk.field.name
						ansvarlig_for = model.objects.filter(**{ fieldname: ansvarlig.pk})
						ansvar_teller += len(ansvarlig_for)

					if ansvar_teller == 0:
						print(f"* {ansvarlig} slettes")
						ansvarlig.delete()
						message = ("%s (%s) er ikke registrert med ansvar. Slettet automatisk." % (ansvarlig, ansvarlig.brukernavn.username))
						UserChangeLog.objects.create(event_type='Ansvarlig slettet', message=message)
						nonlocal antall_slettet
						antall_slettet += 1


			perform_atomic_update()

			runtime_t1 = time.time()
			logg_total_runtime = runtime_t1 - runtime_t0
			logg_entry_message = f"Kjøretid: {round(logg_total_runtime, 1)} sekunder. Slettet {antall_slettet} ansvarlige uten ansvar."
			print(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_entry_message
			int_config.runtime = int(logg_total_runtime)
			int_config.helsestatus = "Vellykket"
			int_config.save()


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			import traceback
			int_config.helsestatus = f"Feilet\n{traceback.format_exc()}"
			int_config.save()
			push_pushover(f"{SCRIPT_NAVN} feilet") # Push error
