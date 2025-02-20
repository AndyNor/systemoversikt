# -*- coding: utf-8 -*-
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
from django.db import transaction
import time, json, os
import pandas as pd
import numpy as np


class Command(BaseCommand):

	ANTALL_DISKER = 0

	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_server_disk"
		LOG_EVENT_TYPE = "CMDB disk import"
		KILDE = "Service Now"
		PROTOKOLL = "SMTP og SharePoint"
		BESKRIVELSE = "Diskstørrelser til virtuelle maskiner"
		FILNAVN = "A34_CMDB_disk_partitions.xlsx"
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

			runtime_t0 = time.time()

			from systemoversikt.views import sharepoint_get_file
			source_filepath = f"{FILNAVN}"
			result = sharepoint_get_file(source_filepath)
			destination_file = result["destination_file"]
			modified_date = result["modified_date"]
			print(f"Filen er datert {modified_date}")

			@transaction.atomic
			def import_cmdb_disk():

				# sletter alle gamle
				print("Sletter alle gamle disker")
				CMDBDisk.objects.all().delete()

				disk_dropped = 0

				# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
				import warnings
				warnings.simplefilter("ignore")

				dfRaw = pd.read_excel(destination_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				data = dfRaw.to_dict('records')

				antall_records = len(data)
				Command.ANTALL_DISKER = antall_records

				def convertToInt(string, multiplier=1):
					try:
						number = int(string)
					except:
						return None

					return number * multiplier

				print("Data lastet, oppdaterer databasen..")
				for idx, record in enumerate(data):
					#print(".", end="", flush=True)
					if idx % 2000 == 0:
						print("%s av %s" % (idx, antall_records))

					disk_name = record["Name"]
					mount_point = record["Mount point"]
					computer = record["Computer"]

					if mount_point == "" and disk_name != "":
						mount_point = disk_name

					if mount_point == "":
						disk_dropped += 1
						print(f'Disk for {computer} manglet mount point')
						continue

					# lager en ny
					cmdb_disk = CMDBDisk.objects.create(computer=record["Computer"], mount_point=mount_point)


					cmdb_disk.operational_status = True
					cmdb_disk.name = disk_name
					cmdb_disk.size_bytes = convertToInt(record["Size bytes"], 1)
					cmdb_disk.free_space_bytes = convertToInt(record["Free space bytes"], 1)
					cmdb_disk.file_system = record["File system"]

					try:
						computer_ref = CMDBdevice.objects.get(comp_name=record["Computer"])
						cmdb_disk.computer_ref = computer_ref
					except:
						disk_dropped += 1
						cmdb_disk.delete()
						continue

					cmdb_disk.save()

				logg_entry_message = f'{antall_records} disker funnet. {disk_dropped} manglet vesentlig informasjon og ble ikke importert.'
				logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)
				print(logg_entry)
				return logg_entry_message

			#eksekver
			logg_entry_message = import_cmdb_disk()
			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = modified_date # eller timezone.now()
			int_config.sist_status = logg_entry_message
			int_config.elementer = int(Command.ANTALL_DISKER)
			runtime_t1 = time.time()
			int_config.runtime = int(runtime_t1 - runtime_t0)
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