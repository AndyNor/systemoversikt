# -*- coding: utf-8 -*-

# scriptet krever hvitlisting av utgående IP-adresse hos HelseCERT!

from django.core.management.base import BaseCommand
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
import time
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

			status_hente = ""
			status_levere = ""

			runtime_t0 = time.time()

			username = os.environ['HELSECERT_BLOCKLIST_USERNAME']
			password = os.environ['HELSECERT_BLOCKLIST_PASSWORD']

			url = 'https://data.helsecert.no/blocklist/v2/'

			print(f"Kobler til {url}")
			response = requests.get(url, auth=HTTPBasicAuth(username, password))

			if response.status_code == 200:
				print('Autentisering var vellykket')
				print(f"Det er {len(response.text)} elementer i blocklist")
				blocklist = response.text
				status_hente = "Lastet ned blocklist."

			else:
				print('Autentisering feilet')
				print('Status Code:', response.status_code)
				print('Response:', response.text)
				blocklist = None
				status_hente = "Feilet nedlasting av blocklist."


			if blocklist:  # Koble til Azure blob storage og lagre filen der

				blob = "https://ukecsirtstorage001.blob.core.windows.net/helsecert/ip.csv"
				sp = "racwd"
				st = "2024-11-28T12:16:43Z"
				se = "2028-01-01T20:16:43Z"
				sip = os.environ['BLOCKLIST_AZURE_SIP']
				spr = "https"
				sv = "2022-11-02"
				sr = "b"
				sig = os.environ['BLOCKLIST_AZURE_SIG']

				url = f"{blob}?sp={sp}&st={st}&se={se}&sip={sip}&spr={spr}&sv={sv}&sr={sr}&sig={sig}"
				#print(url)
				headers = {
					"x-ms-blob-type": "BlockBlob",
					"Content-Type": "text/csv"
				}

				azure_response = requests.put(url, headers=headers, data=blocklist)

				if azure_response.status_code == 201: # http 201 er "created"
					status_levere = "Lastet opp til Azure-blob."
					print(f"Lastet opp blocklist til Azure blob (HTTP {azure_response.status_code})")
				else:
					status_levere = "Feilet opplasting til Azure-blob."
					print(f"Feilet å laste opp Azure blob. Statuskode HTTP {azure_response.status_code} og respons {azure_response.text}.")


			runtime_t1 = time.time()
			logg_total_runtime = round(runtime_t1 - runtime_t0, 1)
			logg_entry_message = f"{status_hente} {status_levere} Kjøretid: {logg_total_runtime} sekunder"
			#print(logg_entry_message)
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
