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
		BESKRIVELSE = "Oppdaterte data fra ardoc"
		FILNAVN = "eksport_ardoq.xlsx"
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

		print(f"------ Starter {SCRIPT_NAVN} ------")

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

			for record in data:
				try:
					ardoc_system_id = int(record["Kartoteket SysID"])
				except:
					ardoc_system_id = None

				ardoc_konklusjon = record["Konklusjon"].replace("\\", "")
				ardoc_konklusjon_beskrivelse = record["Konklusjon Beskrivelse"].replace("\\", "")

				#try:
				system_ref = System.objects.get(pk=ardoc_system_id)

				system_ref.inv_konklusjon = ardoc_konklusjon
				system_ref.inv_konklusjon_beskrivelse = ardoc_konklusjon_beskrivelse
				system_ref.save()

				ardoc_virk_eier = record["Organisatorisk systemeier"].split("(")[0].strip()
				print(ardoc_virk_eier)
				ardoc_virk_eier = Virksomhet.objects.get(virksomhetsnavn=ardoc_virk_eier)

				ardoc_virk_forvalter = record["Organisatorisk systemforvalter"].split("(")[0].strip()
				print(ardoc_virk_forvalter)
				ardoc_virk_forvalter = Virksomhet.objects.get(virksomhetsnavn=ardoc_virk_forvalter)


				#if system_ref.systemnavn != ardoc_systemnavn:
				#	print(f"Systemnavn blir endret fra '{system_ref.systemnavn}' til '{ardoc_systemnavn}'.")
				#	system_ref.systemnavn = ardoc_systemnavn
				#	system_ref.save()

				#if ardoc_systembeskrivelse != "":
				#	measure = SequenceMatcher(a=system_ref.systembeskrivelse,b=ardoc_systembeskrivelse).ratio()
				#	if measure < 0.96:
				#		print(f"{system_ref}: {measure}")
				#		#system_ref.systembeskrivelse = ardoc_systembeskrivelse
				#		#system_ref.save()


				#if ardoc_livsløpsstatus != None:
				#	if system_ref.livslop_status != int(ardoc_livsløpsstatus):
				#		print(f"Livsløpstatus for '{system_ref.systemnavn}' blir endret fra '{system_ref.livslop_status}' til '{ardoc_livsløpsstatus}'.")
				#		system_ref.livslop_status = int(ardoc_livsløpsstatus)
				#		system_ref.save()


			logg_entry_message = f"Det var {antall_records} systemer i filen"
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



