# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from systemoversikt.models import *
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
import json, os
import pandas as pd
import numpy as np


class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_backup"
		LOG_EVENT_TYPE="CMDB Backup import"
		KILDE = "CommVault"
		PROTOKOLL = "N/A"
		BESKRIVELSE = "Backupmetadata for servere og databaser"
		FILNAVN = "commvault_backup.xlsx"
		URL = ""
		FREKVENS = "Manuelt på forespørsel"

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


			@transaction.atomic
			def main(destination_file, FILNAVN, LOG_EVENT_TYPE):


				# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
				import warnings
				warnings.simplefilter("ignore")

				if ".xlsx" in destination_file:
					#dfRaw = pd.read_excel(destination_file, sheet_name='CommVault Summary', skiprows=8, usecols=['Client', 'Total Protected App Size (GB)', 'Source Capture Date', 'Business Sub Service', ])
					dfRaw = pd.read_excel(destination_file, sheet_name='Export', skiprows=0, usecols=['Client', 'Total Protected App Size (GB)', 'Backup frequency', 'Business Service / Most Critical Service',])
					dfRaw = dfRaw.replace(np.nan, '', regex=True)
					data = dfRaw.to_dict('records')

				if data == None:
					return

				failed_device = 0

				# fjerner alle registrerte innslag (finnes ingen identifikator)

				CMDBbackup.objects.all().delete()
				antall_linjer = len(data)

				for line in data:
					#print(line)
					if line['Client'] == "": # end of content
						print("End of data")
						break
					try:
						device = CMDBdevice.objects.get(comp_name__iexact=line["Client"])
					except:
						device = None
						failed_device += 1
						#print("%s feilet" % (line["Client"]))



					#print(device)
					inst = CMDBbackup.objects.create(device=device, device_str=line["Client"])

					#print(".", end="", flush=True)

					size = int(line["Total Protected App Size (GB)"] * 1000 * 1000 * 1000) # fra giga bytes til bytes (antar 1000 siden dette er et diskverktøy)
					inst.backup_size_bytes = size
					inst.backup_frequency = line["Backup frequency"]
					try:
						inst.storage_policy = line["Storage Policy"]
					except:
						pass
					#inst.export_date = line["Source Capture Date"]

					inst.save()


				logg_entry_message = f'{antall_linjer} innslag importert. {failed_device} feilet oppslag mot server.'
				logg_entry = ApplicationLog.objects.create(
						event_type=LOG_EVENT_TYPE,
						message=logg_entry_message,
					)
				print(logg_entry_message)
				return logg_entry_message


			#eksekver
			logg_entry_message = main(destination_file, FILNAVN, LOG_EVENT_TYPE)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = modified_date
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