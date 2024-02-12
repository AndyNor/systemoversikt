# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from systemoversikt.views import push_pushover
from systemoversikt.models import *
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
import pandas as pd
import numpy as np
import os
from difflib import SequenceMatcher


class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_ardoc_import"
		LOG_EVENT_TYPE = "CMDB ardoq import"
		KILDE = "Ardoq"
		PROTOKOLL = "Sharepoint"
		BESKRIVELSE = "Oppdaterte data fra ardoc v2 - kun eiere og forvaltere"
		FILNAVN = "INV eksport til kartoteket-med konklusjon.xlsx"
		URL = ""
		FREKVENS = "Ved behov"

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

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

			source_filepath = f"{FILNAVN}"
			from systemoversikt.views import sharepoint_get_file
			result = sharepoint_get_file(source_filepath)
			destination_file = result["destination_file"]
			modified_date = result["modified_date"]
			print(f"Filen er datert {modified_date}")

			print(f"Åpner filen..")
			# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
			import warnings
			warnings.simplefilter("ignore")

			dfRaw = pd.read_excel(destination_file)
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			data = dfRaw.to_dict('records')

			antall_records = len(data)

			log = ""

			for record in data:
				ardoc_system_id = int(record["Kartoteket SysID"])
				try:
					system_ref = System.objects.get(pk=ardoc_system_id)
				except:
					log += f"Fant ikke systemet med ID {ardoc_system_id}\n"

				nye_eiere = record["Systemeier epost"].split(",").strip()
				for ny_eier in nye_eiere:
					try:
						ansvarlig = Ansvarlig.objects.get(brukernavn__email=ny_eier)
					except:
						try:
							user = User.objects.get(email=ny_eier)
							ansvarlig = Ansvarlig.objects.create(brukernavn=user)
							log += f"Opprettet ansvarlig knyttet til {user}\n"
						except:
							log += f"fant ingen bruker med epost {ny_eier}\n"

					if ansvarlig not in system_ref.systemeier_kontaktpersoner_referanse.all():
						system_ref.systemeier_kontaktpersoner_referanse.add(ansvarlig)
						log += f"{system_ref}: la til eier {ansvarlig}\n"



				nye_forvaltere = record["Systemforvalter epost"].split(",").strip()
				for ny_forvalter in nye_eiere:
					try:
						ansvarlig = Ansvarlig.objects.get(brukernavn__email=ny_forvalter)
					except:
						try:
							user = User.objects.get(email=ny_forvalter)
							ansvarlig = Ansvarlig.objects.create(brukernavn=user)
							log += f"Opprettet ansvarlig knyttet til {user}\n"
						except:
							log += f"fant ingen bruker med epost {ny_forvalter}\n"

					if ansvarlig not in system_ref.systemforvalter_kontaktpersoner_referanse.all():
						system_ref.systemforvalter_kontaktpersoner_referanse.add(ansvarlig)
						log += f"{system_ref}: la til forvalter {ansvarlig}\n"


			logg_entry_message = f"Det var {antall_records} systemer i filen.\n {log}"
			print(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_entry_message,
				)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = modified_date # her setter vi filens dato, ikke dato for kjøring av script
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



