from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
from django.db import transaction
from functools import lru_cache
import json, os, re, socket, time
import pandas as pd
import numpy as np

from systemoversikt.models import *
from systemoversikt.views import get_ipaddr_instance

client_business_services = ["OK-Tykklient", "OK-Støttemaskin", "OK-Tynnklient"]


class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_virtual_machines"
		LOG_EVENT_TYPE = "CMDB server import"
		FILNAVN = {"filename_computers": "OK_computers_bss.xlsx", "filename_vmware": "RAW data related to virtual servers.xlsx"}
		KILDE = "Service Now og VMware"
		PROTOKOLL = "SMTP og SharePoint"
		BESKRIVELSE = "Informasjon om virtuelle servere"
		URL = "https://soprasteria.service-now.com/"
		FREKVENS = "Hver natt (vmware av og til)"

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

		print(f"Starter {SCRIPT_NAVN}")



		filename_computers = FILNAVN["filename_computers"]
		filename_vmware = FILNAVN["filename_vmware"]

		runtime_t0 = time.time()
		logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="Starter..")

		sp_site = os.environ['SHAREPOINT_SITE']
		client_id = os.environ['SHAREPOINT_CLIENT_ID']
		client_secret = os.environ['SHAREPOINT_CLIENT_SECRET']
		sp = da_tran_SP365(site_url = sp_site, client_id = client_id, client_secret = client_secret)

		print("Laster ned fil med kobling maskiner-bss")
		computers_source_file = sp.create_link(f"https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/{filename_computers}")
		computers_destination_file = f'systemoversikt/import/{filename_computers}'
		sp.download(sharepoint_location = computers_source_file, local_location = computers_destination_file)

		print("Laster ned fil med informasjon om disk fra vmware")
		vmware_source_file = sp.create_link(f"https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/{filename_vmware}")
		#vmware_destination_file = 'systemoversikt/import/Storage - BS and BSS  A34-Oslo kommune_03-2022.xlsx'
		vmware_destination_file = f'systemoversikt/import/{filename_vmware}'
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
			all_existing_devices = list(CMDBdevice.objects.filter(device_type="SERVER"))


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

				comp_name = record["Name"].lower()
				if comp_name == "":
					print("Maskinen mangler navn")
					server_dropped += 1
					continue  # Det må være en verdi på denne

				# Sette type enhet
				if record["Name.1"] not in client_business_services:
					# vi sjekker om enheten finnes fra før
					cmdbdevice = get_cmdb_instance(comp_name)
					cmdbdevice.device_type = "SERVER"
					print(".", end="", flush=True)
				else:
					continue
					#cmdbdevice.device_type = "KLIENT"


				if idx % 200 == 0:
					print("\n%s av %s" % (idx, antall_records))



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

				if (comp_ip_address == None or comp_ip_address == "") and "ws" not in comp_name:
					#print("gethostbyname %s" % comp_name)
					try:
						full_comp_name = "%s%s" % (comp_name, ".oslofelles.oslo.kommune.no")
						comp_ip_address = socket.gethostbyname(full_comp_name)
						print(f"Oppslag av {full_comp_name} fant {comp_ip_address}")
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


			print("\nFerdig med import. Går over til VMware-data")
			dfRaw = pd.read_excel(vmware_destination_file, sheet_name='Export', skiprows=0, usecols=[
					'Customer ID',
					'Machine Name',
					'Allocated disk (GB)',
					'Total Disk Used (GB)',
					'Disk Tier',
					'CPU',
					#'CPU Usage (Avg 7days)%',
					'Mem-Capacity (GB)',
					#'Mem Usage (Avg 7days)%',
					'UUID',
					'Storage location',
				])

			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			vmware_data = dfRaw.to_dict('records')

			all_servers_before_vmware_import = list(CMDBdevice.objects.all().filter(device_type="SERVER"))

			for vm in vmware_data:
				if vm["Customer ID"] == "":
					break # siste linjen, stopper

				cmdbdevice = get_cmdb_instance(vm["Machine Name"])
				cmdbdevice.device_type = "SERVER" # never any clients in VMware

				cmdbdevice.vm_disk_allocation = int(vm["Allocated disk (GB)"]) * 1000 ** 3
				cmdbdevice.vm_disk_usage = int(vm["Total Disk Used (GB)"]) * 1000 ** 3
				cmdbdevice.vm_disk_tier = vm["Disk Tier"]

				cmdbdevice.save()

				try:
					all_servers_before_vmware_import.remove(cmdbdevice)
				except:
					pass # går ikke om den ikke finnes fra før av. Det kan skje.
					#print("Kan ikke fjerne %s fra listen over alle servere" % cmdbdevice)

				print(".", end="", flush=True)

			# clean up vmware disk import
			print("\nRydder opp gamle servere")
			servers_not_updateded_with_disk = all_servers_before_vmware_import
			print("Det var %s eksisterende servere som ikke ble oppdatert med VMware-data" % (len(servers_not_updateded_with_disk)))
			for cmdbdevice in servers_not_updateded_with_disk:
				if cmdbdevice.vm_disk_allocation != 0:
					cmdbdevice.vm_disk_allocation = 0
					cmdbdevice.vm_disk_usage = 0
					cmdbdevice.save()
					print("Setting VM disk size for %s to 0" % cmdbdevice)




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
					event_type=LOG_EVENT_TYPE,
					message=logg_entry_message,
				)
			print(logg_entry_message)

		# eksekver
		import_cmdb_servers()
