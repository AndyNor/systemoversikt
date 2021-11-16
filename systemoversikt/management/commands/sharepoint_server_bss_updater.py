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

		source_filepath = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/OK_computers_bss.xlsx"
		source_file = sp.create_link(source_filepath)
		destination_file = 'systemoversikt/import/OK_computers_bss.xlsx'

		sp.download(sharepoint_location = source_file, local_location = destination_file)

		@transaction.atomic
		def import_cmdb_servers():

			from functools import lru_cache

			import json, os
			import pandas as pd
			import numpy as np

			server_dropped = 0

			if ".xlsx" in destination_file:
				dfRaw = pd.read_excel(destination_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				data = dfRaw.to_dict('records')

			if data == None:
				return

			antall_records = len(data)
			all_existing_devices = list(CMDBdevice.objects.all())


			@lru_cache(maxsize=512)
			def bss_cache(bss_name):
				try:
					sub_name = CMDBRef.objects.get(navn=record["Name.1"])
					return sub_name
				except:
					return None

			def convertToInt(string, multiplier=1):
				try:
					number = int(string)
				except:
					return None

				return number * multiplier


			print("Alt lastet, oppdaterer databasen:")
			for idx, record in enumerate(data):
				print(".", end="", flush=True)
				if idx % 1000 == 0:
					print("\n%s av %s" % (idx, antall_records))

				comp_name = record["Name"].lower()
				if comp_name == "":
					print("Maskinen mangler navn")
					server_dropped += 1
					continue  # Det må være en verdi på denne

				# vi sjekker om enheten finnes fra før
				try:
					cmdbdevice = CMDBdevice.objects.get(comp_name=comp_name)
					# fjerner fra oversikt over alle vi hadde før vi startet
					if cmdbdevice in all_existing_devices: # i tilfelle reintrodusert
						all_existing_devices.remove(cmdbdevice)
				except:
					# lager en ny
					cmdbdevice = CMDBdevice.objects.create(comp_name=comp_name)

				cmdbdevice.active = True
				cmdbdevice.kilde_cmdb = True
				cmdbdevice.comp_disk_space = convertToInt(record["Disk space (GB)"])
				cmdbdevice.comp_cpu_core_count = convertToInt(record["CPU total"])
				cmdbdevice.comp_ram = convertToInt(record["RAM (MB)"])
				cmdbdevice.comp_ip_address = record["IP Address"]
				cmdbdevice.comp_cpu_speed = convertToInt(record["CPU speed (MHz)"])
				cmdbdevice.comp_os = record["Operating System"]
				cmdbdevice.comp_os_version = record["OS Version"]
				cmdbdevice.comp_os_service_pack = record["OS Service Pack"]
				cmdbdevice.comp_location = record["Location"]
				cmdbdevice.comments = record["Comments"]
				cmdbdevice.description = record["Description"]
				cmdbdevice.billable = record["Billable"]

				sub_name = bss_cache(record["Name.1"])
				if sub_name != None:
					cmdbdevice.sub_name = sub_name
				else:
					print('Business sub service %s for %s finnes ikke' % (record["sub_name"], comp_name))
					server_dropped += 1
					continue

				cmdbdevice.save()

			obsolete_devices = all_existing_devices
			devices_set_inactive = 0

			for item in obsolete_devices:
				if item.active == True:
					item.active = False
					devices_set_inactive += 1
					item.save()

			runtime_t1 = time.time()
			total_runtime = round(runtime_t1 - runtime_t0, 1)

			logg_entry_message = 'Fant %s maskiner. %s manglet navn eller tilhørighet. Satte %s servere inaktiv. Tok %s sekunder' % (
					antall_records,
					server_dropped,
					devices_set_inactive,
					total_runtime,
				)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB server import',
					message=logg_entry_message,
				)
			print(logg_entry_message)


		# eksekver
		import_cmdb_servers()

