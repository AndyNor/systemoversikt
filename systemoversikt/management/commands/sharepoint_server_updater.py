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
from collections import Counter
import pandas as pd
import numpy as np
from systemoversikt.views import get_ipaddr_instance
from systemoversikt.views import sharepoint_get_file

class Command(BaseCommand):

	antall_servere = 0

	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_virtual_machines"
		LOG_EVENT_TYPE = "CMDB server import"
		FILNAVN = {
			"filename_computers": "A34_CMDB_servers_to_service.xlsx",
			"filename_computers_without_service": "A34_CMDB_servers_without_service.xlsx",
			"filename_vmware": "vmware_data.xlsx",
			}
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
		int_config.helsestatus = "Forbereder"
		int_config.save()


		try:
			timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
			print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
			runtime_t0 = time.time()

			filename_computers = FILNAVN["filename_computers"]
			filename_computers_without_service = FILNAVN["filename_computers_without_service"]
			filename_vmware = FILNAVN["filename_vmware"]

			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="Starter..")

			# servere med kobling til offering, fra CMDB
			source_filepath = f"{filename_computers}"
			result = sharepoint_get_file(source_filepath)
			computers_destination_file = result["destination_file"]
			computers_destination_file_modified_date = result["modified_date"]
			print(f"Filen er datert {computers_destination_file_modified_date}")

			# servere uten kobling, men i CMDB
			source_filepath = f"{filename_computers_without_service}"
			result = sharepoint_get_file(source_filepath)
			computers_without_service_destination_file = result["destination_file"]
			computers_without_service_destination_file_modified_date = result["modified_date"]
			print(f"Filen er datert {computers_destination_file_modified_date}")

			# eksport fra VMware, ikke nødvendigivis i CMDB, men brukes kun for å hente ekstra informasjon
			source_filepath = f"{filename_vmware}"
			result = sharepoint_get_file(source_filepath)
			vmware_destination_file = result["destination_file"]
			vmware_destination_file_modified_date = result["modified_date"]
			print(f"Filen er datert {vmware_destination_file_modified_date}")


			@transaction.atomic
			def import_cmdb_servers():

				# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
				import warnings
				warnings.simplefilter("ignore")

				# konvertere: servere med offering
				dfRaw = pd.read_excel(computers_destination_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				computers_data = dfRaw.to_dict('records')
				antall_records = len(computers_data)

				# konvertere: servere uten offering
				dfRaw = pd.read_excel(computers_without_service_destination_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				computers_data_without_service = dfRaw.to_dict('records')
				antall_records += len(computers_data_without_service) # her legger vi til de servere som ikke har offering til totalen

				# prøver å slå dataene sammen, slik at resten av koden kan fungere som før
				computers_data = computers_data + computers_data_without_service
				Command.antall_servere = antall_records

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
					comp_name = comp_name.lower()

					try:
						return CMDBdevice.objects.get(comp_name=comp_name)
					except:
						pass

					comp_name = comp_name.replace(".oslo.kommune.no", "")
					try:
						return CMDBdevice.objects.get(comp_name=comp_name)
					except:
						pass

					if "-" in comp_name:
						comp_name = '-'.join(comp_name.split("-")[:-1]) # alt unntatt siste "-ettellernannet"
						try:
							return CMDBdevice.objects.get(comp_name=comp_name)
						except:
							pass

					return None

				def get_or_create_cmdb_instance(comp_name):
					try:
						cmdbdevice = CMDBdevice.objects.get(comp_name=comp_name.lower())
					except:
						cmdbdevice = CMDBdevice.objects.create(comp_name=comp_name.lower())
					return cmdbdevice


				# er det duplikater?
				alle_systemnavn = [server["Name"].lower() for server in computers_data]
				duplicates = [item for item, count in Counter(alle_systemnavn).items() if count > 1]
				print(f"Duplikater: {duplicates}")

				print("Alt lastet, oppdaterer databasen med servere med service offering..")

				servere_uten_offering = 0
				nye_servere_importert = 0
				server_dropped = 0

				for idx, record in enumerate(computers_data):

					if idx % 300 == 0:
						print(f"{idx} av {antall_records}")

					comp_name = record["Name"].lower()
					if comp_name == "":
						print(f"Maskinen mangler navn: {record}")
						server_dropped += 1
						continue  # Det må være en verdi på denne

					cmdbdevice, created = CMDBdevice.objects.get_or_create(comp_name=comp_name.lower(), device_type="SERVER")

					if created:
						nye_servere_importert += 1

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

					comp_ip_address = record["IP Address"]

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

					if 'Service' in record:
						sub_name = bss_cache(record["Service"])
						if sub_name == None:
							print(f'Business sub service {record["Service"]} for {comp_name} finnes ikke')
						cmdbdevice.service_offerings.add(sub_name) # det er OK at den er None
					else:
						servere_uten_offering += 1


					if 'Install Status' in record:
						cmdbdevice.service_now_install_status = record["Install Status"]

					if 'Updated' in record:
						#cmdbdevice.service_now_last_updated = datetime.strptime(record["Updated"], "%d.%m.%Y %H:%M:%S")
						cmdbdevice.service_now_last_updated = record["Updated"] # den blir automatisk konvertert

					# Linke IP-adresse
					ipaddr_ins = get_ipaddr_instance(comp_ip_address)
					if ipaddr_ins != None:
						if not cmdbdevice in ipaddr_ins.servere.all():
							ipaddr_ins.servere.add(cmdbdevice)
							ipaddr_ins.save()

					cmdbdevice.save()


				#opprydding alle servere ikke sett fra hovedimport
				antall_timer_slett = 12
				print(f"Rydder bort gamle servere som ikke er oppdatert på {antall_timer_slett} timer.")
				for_gammelt = timezone.now() - timedelta(hours=antall_timer_slett) # 12 timer gammelt, scriptet bruker bare noen minutter..
				ikke_oppdatert = CMDBdevice.objects.filter(device_type="SERVER").filter(sist_oppdatert__lte=for_gammelt)
				tekst_ikke_oppdatert = ",".join([device.comp_name for device in ikke_oppdatert.all()])
				if tekst_ikke_oppdatert == "":
					tekst_ikke_oppdatert = "<ingen>"
				antall_ikke_oppdatert = ikke_oppdatert.count()
				#ikke_oppdatert.delete() # feiler hvis det er for mange
				batch_size = 500
				while ikke_oppdatert.count():
					ids = ikke_oppdatert.values_list('pk', flat=True)[:batch_size]
					ikke_oppdatert.filter(pk__in=ids).delete()
					print(f"Slettet ny batch på {batch_size}..")
				print(f"Ferdig ryddet.")


				print("Går over til VMware-data. Setter disk allokert og brukt, samt disk tier og power consumption.")
				dfRaw = pd.read_excel(vmware_destination_file, sheet_name='Export', skiprows=0, usecols=[
						'Machine Name',
						'Allocated Disk Volume (GB)',
						'Used Disk Volume (GB)',
						'Disk Tier',
					])

				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				vmware_data = dfRaw.to_dict('records')

				# er det duplikater i vmware-dataene? (kommer egentlig fra powerbi-rapport)
				#alle_systemnavn_vmware = [vm["Machine Name"].lower() for vm in vmware_data]
				#print(f"VMware-filen har {len(alle_systemnavn_vmware)} systemer, men kun {len(set(alle_systemnavn_vmware))} unike.")
				#duplicates = [item for item, count in Counter(alle_systemnavn_vmware).items() if count > 1]
				#print(f"Duplikater VMware: {duplicates}")

				# hva er i vmware-data, men ikke i CMDB-data?
				#print(f"Det som kun er i VMware-data:")
				#print(list(set(alle_systemnavn_vmware) - set(alle_systemnavn)))

				# hva er i CMDB-data, men ikke i vmware-data?
				#print(f"Det som kun er i CMDB-data:")
				#print(list(set(alle_systemnavn) - set(alle_systemnavn_vmware)))



				# laste inn nye data fra vmware-filen
				for idx, vm in enumerate(vmware_data):

					if idx % 300 == 0:
						print("%s av %s" % (idx, antall_records))

					if vm["Machine Name"] == "Total":
						break # siste linjen, stopper

					cmdbdevice = get_cmdb_instance(vm["Machine Name"])
					if cmdbdevice:
						cmdbdevice.vm_disk_allocation = (float(vm["Allocated Disk Volume (GB)"]) * 1000 ** 3) if vm["Allocated Disk Volume (GB)"] != "" else 0
						cmdbdevice.vm_disk_usage = (float(vm["Used Disk Volume (GB)"]) * 1000 ** 3) if vm["Used Disk Volume (GB)"] != "" else 0
						cmdbdevice.vm_disk_tier = vm["Disk Tier"]
						cmdbdevice.save()


				#oppsummering og logging
				logg_entry_message = f'Importen inneholder {antall_records} servere. {nye_servere_importert} nye servere ble importert. {server_dropped} manglet navn. Slettet {antall_ikke_oppdatert} gamle serere som ikke ble sett: {tekst_ikke_oppdatert}. Det var {servere_uten_offering} servere uten knytning til service offering. Duplikater: {duplicates}.'
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
			int_config.elementer = int(Command.antall_servere)
			runtime_t1 = time.time()
			logg_total_runtime = int(runtime_t1 - runtime_t0)
			int_config.runtime = logg_total_runtime
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

