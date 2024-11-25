# -*- coding: utf-8 -*-

# scriptet krever hvitlisting av utgående IP-adresse hos HelseCERT!

from django.core.management.base import BaseCommand
from systemoversikt.models import *
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
import os

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "helsecert_blocklist"
		LOG_EVENT_TYPE = "Oppdatere blocklist"
		KILDE = "HelseCERT"
		PROTOKOLL = "REST"
		BESKRIVELSE = "URL blocklist"
		FILNAVN = "-"
		URL = "https://data.helsecert.no"
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

			username = os.environ['HELSECERT_BLOCKLIST_USERNAME']
			password = os.environ['HELSECERT_BLOCKLIST_PASSWORD']

			url = 'https://data.helsecert.no/blocklist/v2/'

			response = requests.get(url, auth=HTTPBasicAuth(username, password))

			if response.status_code == 200:
				print('Authentication successful')
				print('Response:', response.json())
			else:
				print('Authentication failed')
				print('Status Code:', response.status_code)
				print('Response:', response.text)


			runtime_t1 = time.time()
			logg_total_runtime = round(runtime_t1 - runtime_t0, 1)
			logg_entry_message = f"Kjøretid: {logg_total_runtime} sekunder"
			print(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_entry_message,
			)

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
			#push_pushover(f"{SCRIPT_NAVN} feilet")
