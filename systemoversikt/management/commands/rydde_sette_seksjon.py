# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
import collections
import os

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "lokal_systemforvalter_seksjon"
		LOG_EVENT_TYPE = 'Sette seksjon på system'
		KILDE = "Lokal"
		PROTOKOLL = "N/A"
		BESKRIVELSE = "Sette seksjon på system"
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
		int_config.save()

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")

		try:

			antall_satt = 0
			for s in System.objects.all():
				if s.systemforvalter_avdeling_referanse != None:
					continue # vi overskriver ikke

				aktuelle_seksjoner = []
				for ansvarlig in s.systemforvalter_kontaktpersoner_referanse.all():
					try:
						org_enhet = ansvarlig.brukernavn.profile.org_unit
						if org_enhet != None:
							aktuelle_seksjoner.append(org_enhet)
					except:
						pass

				if len(aktuelle_seksjoner) == 0:
					continue

				if len(aktuelle_seksjoner) == 1:
					s.systemforvalter_avdeling_referanse = aktuelle_seksjoner[0]
					print(f"Setter seksjon direkte for {s} til {aktuelle_seksjoner[0]}")
					s.save()
					antall_satt += 1
					continue

				# det var flere enn 1 seksjon, vi velger den mest frekvente
				mest_frekvente_seksjon = collections.Counter(aktuelle_seksjoner).most_common(1)[0][0]
				s.systemforvalter_avdeling_referanse = mest_frekvente_seksjon
				print(f"Setter mest frekvente seksjon for {s} til {mest_frekvente_seksjon}")
				s.save()
				antall_satt += 1

			#logg dersom vellykket
			logg_message = f"Ferdig med å sette seksjon på {antall_satt} systemer som mangler seksjon."
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message
			int_config.save()


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# Push error
			push_pushover(f"{SCRIPT_NAVN} feilet")
