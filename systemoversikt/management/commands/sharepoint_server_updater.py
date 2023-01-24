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
import socket
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

		print("Laster ned fil med kobling maskiner-bss")
		computers_source_file = sp.create_link("https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/OK_computers_bss.xlsx")
		computers_destination_file = 'systemoversikt/import/OK_computers_bss.xlsx'
		sp.download(sharepoint_location = computers_source_file, local_location = computers_destination_file)

		print("Laster ned fil med informasjon om disk fra vmware")
		vmware_source_file = sp.create_link("https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/Virtual Servers.xlsx")
		#vmware_destination_file = 'systemoversikt/import/Storage - BS and BSS  A34-Oslo kommune_03-2022.xlsx'
		vmware_destination_file = 'systemoversikt/import/Virtual Servers.xlsx'
		sp.download(sharepoint_location = vmware_source_file, local_location = vmware_destination_file)


		@transaction.atomic
		def import_cmdb_servers():

			server_dropped = 0

			if ".xlsx" in computers_destination_file:
				dfRaw = pd.read_excel(computers_destination_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				computers_data = dfRaw.to_dict('records')
			if computers_data == None:
				return

			antall_records = len(computers_data)
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


			def get_cmdb_instance(comp_name):
				try:
					cmdbdevice = CMDBdevice.objects.get(comp_name=comp_name.lower())
					# fjerner fra oversikt over alle vi hadde før vi startet
					nonlocal all_existing_devices
					if cmdbdevice in all_existing_devices: # i tilfelle reintrodusert
						all_existing_devices.remove(cmdbdevice)
				except:
					# lager en ny
					cmdbdevice = CMDBdevice.objects.create(comp_name=comp_name.lower())
					print("Opprettet %s" % comp_name)
				return cmdbdevice


			print("Alt lastet, oppdaterer databasen:")

			for idx, record in enumerate(computers_data):
				print(".", end="", flush=True)
				if idx % 1000 == 0:
					print("\n%s av %s" % (idx, antall_records))

				comp_name = record["Name"].lower()
				if comp_name == "":
					print("Maskinen mangler navn")
					server_dropped += 1
					continue  # Det må være en verdi på denne

				# vi sjekker om enheten finnes fra før
				cmdbdevice = get_cmdb_instance(comp_name)

				# OS-håndtering
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

				if comp_ip_address == None or comp_ip_address == "":
					print("gethostbyname %s" % comp_name)
					try:
						full_comp_name = "%s%s" % (comp_name, ".oslofelles.oslo.kommune.no")
						comp_ip_address = socket.gethostbyname(full_comp_name)
						print(comp_ip_address)
					except:
						#print("gethostbyname failed %s" % comp_name)
						pass


				cmdbdevice.device_active = True
				cmdbdevice.kilde_cmdb = True
				if record["Disk space (GB)"] != "":
					cmdbdevice.comp_disk_space = convertToInt(record["Disk space (GB)"])*1000**3 # returnert som bytes (fra GB)
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
				if sub_name == None:
					print('Business sub service %s for %s finnes ikke' % (record["Name.1"], comp_name))
				cmdbdevice.sub_name = sub_name # det er OK at den er None
				#else:
				#	server_dropped += 1
				#	continue


				# Linke IP-adresse
				#if cmdbdevice.device_type == "SERVER": # vi trenger ikke alle klientene
				ipaddr_ins = get_ipaddr_instance(comp_ip_address)
				if ipaddr_ins != None:
					if not cmdbdevice in ipaddr_ins.servere.all():
						ipaddr_ins.servere.add(cmdbdevice)
						ipaddr_ins.save()

				# Lagre
				cmdbdevice.save()

			# gjennomgang av data fra vmware
			"""
			def decode_disk(vm):
				if vm["HE disk Allocated (GB)"] != "":
					return (vm["HE disk Allocated (GB)"]*1000**3, vm["HE disk Used (GB)"]*1000**3, "HE")
				if vm["HE-S disk Allocated (GB)"] != "":
					return (vm["HE-S disk Allocated (GB)"]*1000**3, vm["HE-S disk Used (GB)"]*1000**3, "HE-S")

				if vm["MR disk Allocated (GB)"] != "":
					return (vm["MR disk Allocated (GB)"]*1000**3, vm["MR disk Used (GB)"]*1000**3, "MR")
				if vm["MR-S disk Allocated (GB)"] != "":
					return (vm["MR-S disk Allocated (GB)"]*1000**3, vm["MR-S disk Used (GB)"]*1000**3, "MR-S")

				if vm["LE disk Allocated (GB)"] != "":
					return (vm["LE disk Allocated (GB)"]*1000**3, vm["LE disk Used (GB)"]*1000**3, "LE")
				if vm["LE-S disk Allocated (GB)"] != "":
					return (vm["LE-S disk Allocated (GB)"]*1000**3, vm["LE-S disk Used (GB)"]*1000**3, "LE-S")

				return (None, None, None)
			"""

			if ".xlsx" in vmware_destination_file:
				"""
				dfRaw = pd.read_excel(vmware_destination_file, sheet_name='Summarized', skiprows=8, usecols=[
						'VM Name',
						'HE disk Allocated (GB)',
						'HE disk Used (GB)',
						'HE-S disk Allocated (GB)',
						'HE-S disk Used (GB)',
						'MR disk Allocated (GB)',
						'MR disk Used (GB)',
						'MR-S disk Allocated (GB)',
						'MR-S disk Used (GB)',
						'LE disk Allocated (GB)',
						'LE disk Used (GB)',
						'LE-S disk Allocated (GB)',
						'LE-S disk Used (GB)',
						'VM CPU Usage (%)',
						'VM Memory Usage (%)',
						'PowerState',
						'# of disks installed',
					])
				"""

				dfRaw = pd.read_excel(vmware_destination_file, sheet_name='Export', skiprows=0, usecols=[
						'Customer ID',
						'VM Name',
						'Business Sub Service',
						'Allocated disk (GB)',
						'Total Disk Used (GB)',
						'Disk Tier',
						'CPU',
						'CPU Usage (Avg 7days)%',
						'Mem-Capacity (GB)',
						'Mem Usage (Avg 7days)%',
						'UUID',
						'Storage location',
					])

				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				vmware_data = dfRaw.to_dict('records')

				all_servers_before_vmware_import = list(CMDBdevice.objects.all().filter(device_type="SERVER"))

				#print(vmware_data[0])
				for vm in vmware_data:
					if vm["Customer ID"] == "":
						break

					cmdbdevice = get_cmdb_instance(vm["VM Name"])
					#cmdbdevice.vm_poweredon = True if (vm["PowerState"] == "POWEREDON") else False # we don't have this value here anymore
					cmdbdevice.device_type = "SERVER" # never any clients in VMware
					if vm["Mem Usage (Avg 7days)%"] != "":
						cmdbdevice.vm_comp_ram_usage = vm["Mem Usage (Avg 7days)%"]
					if vm["CPU Usage (Avg 7days)%"] != "":
						cmdbdevice.vm_comp_cpu_usage = vm["CPU Usage (Avg 7days)%"]
					#cmdbdevice.vm_disk_allocation, cmdbdevice.vm_disk_usage, cmdbdevice.vm_disk_tier = decode_disk(vm) # not used any more
					cmdbdevice.vm_disk_allocation = vm["Allocated disk (GB)"]*1000**3
					cmdbdevice.vm_disk_usage = vm["Total Disk Used (GB)"]*1000**3
					cmdbdevice.vm_disk_tier = vm["Disk Tier"]
					#print(decode_disk(vm))
					#cmdbdevice.vm_disks_installed = vm["# of disks installed"]
					#print("%s: vm %s - cmdb %s" % (cmdbdevice.comp_name, cmdbdevice.vm_disk_allocation, cmdbdevice.comp_disk_space))

					cmdbdevice.save()
					try:
						all_servers_before_vmware_import.remove(cmdbdevice)
					except:
						print("Kan ikke fjerne %s fra listen over alle servere" % cmdbdevice)
					print(".", end="", flush=True)

				# clean up vmware disk import
				servers_not_updateded_with_disk = all_servers_before_vmware_import
				print("Det var %s eksisterende servere som ikke ble oppdatert" % (len(servers_not_updateded_with_disk)))
				for cmdbdevice in servers_not_updateded_with_disk:
					if cmdbdevice.vm_disk_allocation != 0:
						cmdbdevice.vm_disk_allocation = 0
						cmdbdevice.vm_disk_usage = 0
						cmdbdevice.save()
						print("Setting VM disk size for %s to 0" % cmdbdevice)

			else:
				print("Filen med VMware-data var ikke på riktig dataformat.")



			#opprydding alle servere ikke sett fra hovedimport
			obsolete_devices = all_existing_devices
			devices_set_inactive = 0

			for item in obsolete_devices:
				if item.device_active == True:
					item.device_active = False
					devices_set_inactive += 1
					item.save()


			#oppsummering og logging
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

