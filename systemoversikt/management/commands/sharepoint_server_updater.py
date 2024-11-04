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
from systemoversikt.views import sharepoint_get_file

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_virtual_machines"
		LOG_EVENT_TYPE = "CMDB server import"
		FILNAVN = {"filename_computers": "A34_CMDB_servers_to_service.xlsx", "filename_vmware": "vmware_data.xlsx"}
		KILDE = "Service Now og VMware"
		PROTOKOLL = "E-post"
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

				@lru_cache(maxsize=512)
				def bss_cache(bss_name):
					try:
						sub_name = CMDBRef.objects.get(navn=record["Service"])
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
						return CMDBdevice.objects.get(comp_name=comp_name.lower())
					except:
						return None


				def get_or_create_cmdb_instance(comp_name):
					try:
						cmdbdevice = CMDBdevice.objects.get(comp_name=comp_name.lower())
					except:
						cmdbdevice = CMDBdevice.objects.create(comp_name=comp_name.lower())
					return cmdbdevice


				print("Alt lastet, oppdaterer databasen:")

				for idx, record in enumerate(computers_data):

					if idx % 300 == 0:
						print("%s av %s" % (idx, antall_records))

					comp_name = record["Name"].lower()
					if comp_name == "":
						print(f"Maskinen mangler navn: {record}")
						server_dropped += 1
						continue  # Det må være en verdi på denne

					cmdbdevice = get_cmdb_instance(comp_name)
					if cmdbdevice == None:
						continue


					cmdbdevice.device_type = "SERVER"

					# OS-håndtering
					os = record["Operating System"]
					os_version = record["OS Version"]
					os_sp = record["OS Service Pack"]

					if "Windows" in os:
						os_readable = os.replace("64-bit", "").replace("32-bit", "").replace(",","").strip()
					elif "Linux" in os:
						version_match = re.search(r'(^\d+.\d+)', os_version)
						if version_match:
							os_readable = "%s %s" % (os, version_match[1])
						else:
							os_readable = os
					else:
						os_readable = os
					os_readable = os_readable.strip().lower()

					if os_readable == '':
						os_readable = 'Ukjent'


					end_of_life_os = [ # all lowercase in order to match
							"windows 2012",
							"windows 2008",
							"windows 2000",
							"red hat 6",
							"red hat 5",
							"red hat 4",
							"red hat 3",
							"centos linux 7"
						]

					if any(version in os_readable for version in end_of_life_os):
						derived_os_endoflife = True
					else:
						derived_os_endoflife = False


					#print(os_readable)
					comp_ip_address = record["IP Address"]

					#if comp_ip_address == None or comp_ip_address == "":
						#print("gethostbyname %s" % comp_name)
						#try:
							#full_comp_name = "%s%s" % (comp_name, ".oslofelles.oslo.kommune.no")
							#comp_ip_address = socket.gethostbyname(full_comp_name)
							#print(f"Oppslag av {full_comp_name} fant {comp_ip_address}")
						#except:
							#print("gethostbyname failed %s" % comp_name)
							#pass

					if record["Disk space (GB)"] != "":
						cmdbdevice.comp_disk_space = convertToInt(record["Disk space (GB)"])*1000**3 # returnert som bytes (fra GB)
					cmdbdevice.comp_ram = convertToInt(record["RAM (MB)"])
					cmdbdevice.comp_ip_address = comp_ip_address
					cmdbdevice.comp_os = os
					cmdbdevice.comp_os_version = os_version
					cmdbdevice.comp_os_service_pack = os_sp
					cmdbdevice.comp_os_readable = os_readable
					cmdbdevice.comp_location = record["Location"]
					cmdbdevice.comments = record["Comments"]
					cmdbdevice.description = record["Description"]
					cmdbdevice.derived_os_endoflife = derived_os_endoflife

					sub_name = bss_cache(record["Service"])
					if sub_name == None:
						print('Business sub service %s for %s finnes ikke' % (record["Service"], comp_name))
					cmdbdevice.service_offerings.add(sub_name) # det er OK at den er None


					# Linke IP-adresse
					ipaddr_ins = get_ipaddr_instance(comp_ip_address)
					if ipaddr_ins != None:
						if not cmdbdevice in ipaddr_ins.servere.all():
							ipaddr_ins.servere.add(cmdbdevice)
							ipaddr_ins.save()

					cmdbdevice.save()



				print("Ferdig med import. Går over til VMware-data. Setter disk allokert og brukt, samt disk tier og power consumption.")
				dfRaw = pd.read_excel(vmware_destination_file, sheet_name='Export', skiprows=0, usecols=[
						'Machine Name',
						'Allocated Disk Volume (GB)',
						'Power Consumption',
						'Used Disk Volume (GB)',
						'Disk Tier',
					])

				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				vmware_data = dfRaw.to_dict('records')

				for idx, vm in enumerate(vmware_data):

					if idx % 300 == 0:
						print("%s av %s" % (idx, antall_records))

					if vm["Machine Name"] == "Total":
						break # siste linjen, stopper

					cmdbdevice = get_cmdb_instance(vm["Machine Name"])
					cmdbdevice.vm_disk_allocation = (float(vm["Allocated Disk Volume (GB)"]) * 1000 ** 3) if vm["Allocated Disk Volume (GB)"] != "" else 0
					cmdbdevice.vm_disk_usage = (float(vm["Used Disk Volume (GB)"]) * 1000 ** 3) if vm["Used Disk Volume (GB)"] != "" else 0
					cmdbdevice.vm_disk_tier = vm["Disk Tier"]
					cmdbdevice.power = float(vm["Power Consumption"]) if vm["Power Consumption"] != "" else 0
					cmdbdevice.save()


				#opprydding alle servere ikke sett fra hovedimport
				for_gammelt = timezone.now() - timedelta(hours=12) # 12 timer gammelt, scriptet bruker bare noen minutter..
				ikke_oppdatert = CMDBdevice.objects.filter(device_type="SERVER").filter(sist_oppdatert__lte=for_gammelt)
				tekst_ikke_oppdatert = ",".join([device.comp_name for device in ikke_oppdatert.all()])
				antall_ikke_oppdatert = ikke_oppdatert.count()
				ikke_oppdatert.delete()


				#oppsummering og logging
				runtime_t1 = time.time()
				total_runtime = round(runtime_t1 - runtime_t0, 1)

				logg_entry_message = f'Importerte {antall_records} servere. {server_dropped} manglet navn eller tilhørighet. Slettet {antall_ikke_oppdatert} gamle serere som ikke ble sett: {tekst_ikke_oppdatert}. Import tok {total_runtime} sekunder.'
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

