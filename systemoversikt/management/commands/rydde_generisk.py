# -*- coding: utf-8 -*-
# sette systemforvalter og rette "ibruk" på systemer

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from systemoversikt.views import push_pushover
from django.conf import settings
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
import os

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "lokal_rydde_systemer"
		LOG_EVENT_TYPE = 'Rydde generisk'
		KILDE = "Lokal"
		PROTOKOLL = "N/A"
		BESKRIVELSE = 'Sette systemforvalter og rette "ibruk" på systemer'
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

		print(f"------------\nStarter {SCRIPT_NAVN}")

		try:

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

			teller_uten_eier = 0
			teller_rettet = 0
			for system in System.objects.all():

				if system.er_ibruk():
					if system.ibruk == False:
						system.ibruk = True
						system.save()
						print(f"Rettet ibruk på {system} til sann.")
				else:
					if system.ibruk == True:
						system.ibruk = False
						system.save()
						print(f"Rettet ibruk på {system} til usann.")

				# fikse manglende tilgjengelighetsvurdering
				if system.tilgjengelighetsvurdering == None:
					system.tilgjengelighetsvurdering = 6
					system.save()
					print(f"Endret tilgjengelighetsvurdering til ukjent for {system}.")


				# fikse manglende systemforvalter ved å sette systemeier dersom det eksisterer
				if system.systemforvalter:
					continue

				if system.systemeier:
					system.systemforvalter = system.systemeier
					system.save()
					teller_rettet += 1

				print(f"{system} har hverken forvalter eller eier")
				teller_uten_eier += 1



			logg_entry_message = f"Rettet {teller_rettet} systemer uten forvalter organisasjon satt. Fant også {teller_uten_eier} systemer uten eier."
			print(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_entry_message
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
