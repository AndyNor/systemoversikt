# -*- coding: utf-8 -*-
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
from django.db import transaction
from functools import lru_cache
import json, os, re, socket, time
import pandas as pd
import numpy as np
from systemoversikt.views import get_ipaddr_instance


CLIENT_BUSINESS_SERVICES = ["OK-Tykklient", "OK-Støttemaskin", "OK-Tynnklient"]


class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_virtual_machines"
		LOG_EVENT_TYPE = "CMDB server import"
		FILNAVN = {"filename_computers": "A34_CMDB_servers_to_service.xlsx", "filename_vmware": "RAW data related to virtual servers.xlsx"}
		KILDE = "Service Now og VMware"
		PROTOKOLL = "SMTP og SharePoint"
		BESKRIVELSE = "Informasjon om virtuelle servere"
		URL = "https://soprasteria.service-now.com/"
		FREKVENS = "Hver natt (vmware på forespørsel)"

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

			filename_computers = FILNAVN["filename_computers"]
			filename_vmware = FILNAVN["filename_vmware"]

			runtime_t0 = time.time()
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="Starter..")


			from systemoversikt.views import sharepoint_get_file

			source_filepath = f"{filename_computers}"
			result = sharepoint_get_file(source_filepath)
			computers_destination_file = result["destination_file"]
			computers_destination_file_modified_date = result["modified_date"]
			print(f"Filen er datert {computers_destination_file_modified_date}")


			source_filepath = f"{filename_vmware}"
			result = sharepoint_get_file(source_filepath)
			vmware_destination_file = result["destination_file"]
			vmware_destination_file_modified_date = result["modified_date"]
			print(f"Filen er datert {vmware_destination_file_modified_date}")

			@transaction.atomic
			def import_cmdb_servers():

				server_dropped = 0

				# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
				import warnings
				warnings.simplefilter("ignore")

				dfRaw = pd.read_excel(computers_destination_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				computers_data = dfRaw.to_dict('records')

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
						#print("Opprettet %s" % comp_name)
					return cmdbdevice

				antall_servere = 0
				print("Alt lastet, oppdaterer databasen:")

				for idx, record in enumerate(computers_data):

					#if idx % 1000 == 0:
					#	print("%s av %s" % (idx, antall_records))

					comp_name = record["Name"].lower()
					if comp_name == "":
						print(f"Maskinen mangler navn: {record}")
						server_dropped += 1
						continue  # Det må være en verdi på denne

					# Sette type enhet
					if record["Name.1"] not in CLIENT_BUSINESS_SERVICES:
						# vi sjekker om enheten finnes fra før
						cmdbdevice = get_cmdb_instance(comp_name)
						cmdbdevice.device_type = "SERVER"
						#print(".", end="", flush=True)
					else:
						continue
						#cmdbdevice.device_type = "KLIENT"



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
					antall_servere += 1


				print("Ferdig med import. Går over til VMware-data. Setter disk tier, allocated og total disk usage.")
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

					#print(".", end="", flush=True)

				# clean up vmware disk import
				print("Rydder opp gamle servere")
				servers_not_updateded_with_disk = all_servers_before_vmware_import
				print("Det var %s eksisterende servere som ikke ble oppdatert med VMware-data" % (len(servers_not_updateded_with_disk)))
				for cmdbdevice in servers_not_updateded_with_disk:
					if cmdbdevice.vm_disk_allocation != 0:
						cmdbdevice.vm_disk_allocation = 0
						cmdbdevice.vm_disk_usage = 0
						cmdbdevice.save()
						#print("Setting VM disk size for %s to 0" % cmdbdevice)


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

				logg_entry_message = f'Fant {antall_records} maskiner. {antall_servere} av disse er servere. {server_dropped} manglet navn eller tilhørighet. Satte {devices_set_inactive} servere inaktiv. Tok {total_runtime} sekunder'
				logg_entry = ApplicationLog.objects.create(
						event_type=LOG_EVENT_TYPE,
						message=logg_entry_message,
					)
				print(logg_entry_message)
				return logg_entry_message

			# eksekver
			logg_entry_message = import_cmdb_servers()

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = computers_destination_file_modified_date # eller timezone.now()
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
