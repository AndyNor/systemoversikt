from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
from systemoversikt.models import *
from django.db import transaction
import os
import time

class Command(BaseCommand):
	def handle(self, **options):

		runtime_t0 = time.time()

		sp_site = os.environ['SHAREPOINT_SITE']
		client_id = os.environ['SHAREPOINT_CLIENT_ID']
		client_secret = os.environ['SHAREPOINT_CLIENT_SECRET']

		sp = da_tran_SP365(site_url = sp_site, client_id = client_id, client_secret = client_secret)

		source_filepath = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/OK_disk_information.xlsx"
		source_file = sp.create_link(source_filepath)
		destination_file = 'systemoversikt/import/OK_disk_information.xlsx'

		sp.download(sharepoint_location = source_file, local_location = destination_file)



		@transaction.atomic
		def import_cmdb_disk():
			import json, os
			import pandas as pd
			import numpy as np

			disk_dropped = 0

			if ".xlsx" in destination_file:
				dfRaw = pd.read_excel(destination_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				data = dfRaw.to_dict('records')

			if data == None:
				return

			antall_records = len(data)

			all_existing_devices = list(CMDBDisk.objects.all())

			def convertToInt(string, multiplier=1):
				try:
					number = int(string)
				except:
					return None

				return number * multiplier

			ikke_koblet = 0

			print("Alt lastet, oppdaterer databasen:")
			for idx, record in enumerate(data):
				print(".", end="", flush=True)
				if idx % 1000 == 0:
					print("\n%s av %s" % (idx, antall_records))

				disk_name = record["Name"]
				mount_point = record["Mount point"]

				if mount_point == "" and disk_name != "":
					mount_point = disk_name

				if mount_point == "":
					disk_dropped += 1
					print('Disk manglet mount point')
					continue

				# vi sjekker om disken finnes fra før
				try:
					cmdb_disk = CMDBDisk.objects.get(Q(computer=record["Computer"]) & Q(mount_point=mount_point))
					# fjerner fra oversikt over alle vi hadde før vi startet
					if cmdb_disk in all_existing_devices: # i tilfelle reintrodusert
						all_existing_devices.remove(cmdb_disk)
				except:
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

			obsolete_devices = all_existing_devices
			for item in obsolete_devices:
				item.delete()

			runtime_t1 = time.time()
			total_runtime = round(runtime_t1 - runtime_t0, 1)

			logg_entry_message = '%s disker funnet. %s manglet vesentlig informasjon og ble ikke importert. %s gamle slettet. Tok %s sekunder' % (
					antall_records,
					disk_dropped,
					len(obsolete_devices),
					total_runtime,
				)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB disk import',
					message=logg_entry_message,
				)
			print("\n")
			print(logg_entry)


		#eksekver
		import_cmdb_disk()
