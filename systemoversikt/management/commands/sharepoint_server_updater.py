from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
from systemoversikt.models import *
from django.db import transaction
import os
import time
from functools import lru_cache
import json, os
import pandas as pd
import numpy as np
import re
from systemoversikt.views import get_ipaddr_instance


class Command(BaseCommand):
	def handle(self, **options):

		runtime_t0 = time.time()
		EVENT_TYPE = "CMDB server import"
		logg_entry = ApplicationLog.objects.create(event_type=EVENT_TYPE, message="Starter..")

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

			server_dropped = 0

			if ".xlsx" in destination_file:
				dfRaw = pd.read_excel(destination_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				data = dfRaw.to_dict('records')

			if data == None:
				return

			antall_records = len(data)
			all_existing_devices = list(CMDBdevice.objects.all())#filter(device_type="SERVER"))


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

				os = record["Operating System"]
				os_version = record["OS Version"]
				os_sp = record["OS Service Pack"]

				if "Windows" in os:
					os_readable = os.replace("64-bit", "").replace("32-bit", "").replace(",","").strip()
				elif "Linux" in os:
					version_match = re.search(r'(\d).\d', os_version)
					if version_match:
						os_readable = "%s %s" % (os, version_match[1])
					else:
						os_readable = os
				else:
					os_readable = os
				os_readable = os_readable.strip()

				if os_readable == '':
					os_readable = 'Ukjent'

				#print(os_readable)
				comp_ip_address = record["IP Address"]

				cmdbdevice.device_active = True
				cmdbdevice.kilde_cmdb = True
				cmdbdevice.comp_disk_space = convertToInt(record["Disk space (GB)"])
				cmdbdevice.comp_cpu_core_count = convertToInt(record["CPU total"])
				cmdbdevice.comp_ram = convertToInt(record["RAM (MB)"])
				cmdbdevice.comp_ip_address = comp_ip_address
				cmdbdevice.comp_cpu_speed = convertToInt(record["CPU speed (MHz)"])
				cmdbdevice.comp_os = os
				cmdbdevice.comp_os_version = os_version
				cmdbdevice.comp_os_service_pack = os_sp
				cmdbdevice.comp_os_readable = os_readable
				cmdbdevice.comp_location = record["Location"]
				cmdbdevice.comments = record["Comments"]
				cmdbdevice.description = record["Description"]
				#cmdbdevice.billable = record["Billable"] #finnes ikke lenger i denne rapporten


				# Sette type enhet
				if record["Name.1"] in ["OK-Tykklient", "OK-Støttemaskin", "OK-Tynnklient"]:
					cmdbdevice.device_type = "KLIENT"
				else:
					cmdbdevice.device_type = "SERVER"

				sub_name = bss_cache(record["Name.1"])
				if sub_name != None:
					cmdbdevice.sub_name = sub_name
				else:
					print('Business sub service %s for %s finnes ikke' % (record["Name.1"], comp_name))
					server_dropped += 1
					continue


				# Linke IP-adresse
				if cmdbdevice.device_type == "SERVER": # vi trenger ikke alle klientene
					ipaddr_ins = get_ipaddr_instance(comp_ip_address)
					if ipaddr_ins != None:
						if not cmdbdevice in ipaddr_ins.servere.all():
							ipaddr_ins.servere.add(cmdbdevice)
							ipaddr_ins.save()

				# Lagre
				cmdbdevice.save()

			obsolete_devices = all_existing_devices
			devices_set_inactive = 0

			for item in obsolete_devices:
				if item.device_active == True:
					item.device_active = False
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

