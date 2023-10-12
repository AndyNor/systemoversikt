# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.db import transaction
from functools import lru_cache
from datetime import datetime
from django.utils.timezone import make_aware
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from systemoversikt.models import *
from systemoversikt.management.commands.sharepoint_server_updater import client_business_services
from systemoversikt.views import push_pushover
import json, os, re, time, sys
import pandas as pd
import numpy as np


class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_klienter"
		LOG_EVENT_TYPE = "CMDB klient import"
		KILDE = "Service Now"
		PROTOKOLL = "SMTP og SharePoint"
		BESKRIVELSE = "Klienter med eier og business service-kobling"
		FILNAVN = {"client_owner_source_filename": "OK_computers.xlsx",  "client_bss_source_filename": "OK_computers_bss.xlsx"}
		URL = "https://soprasteria.service-now.com/"
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
		int_config.save()

		print(f"------------\nStarter {SCRIPT_NAVN}")

		try:

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

			client_owner_source_filename = FILNAVN["client_owner_source_filename"]
			client_bss_source_filename = FILNAVN["client_bss_source_filename"]
			from systemoversikt.views import sharepoint_get_file

			# kobling eier-maskin
			source_filepath = f"/sites/74722/Begrensede-dokumenter/{client_owner_source_filename}"
			result = sharepoint_get_file(source_filepath)
			client_owner_dest_file = result["destination_file"]
			client_owner_modified_date = result["modified_date"]
			print(f"Filen er datert {client_owner_modified_date}")

			# kobling maskin-bss
			source_filepath = f"/sites/74722/Begrensede-dokumenter/{client_bss_source_filename}"
			result = sharepoint_get_file(source_filepath)
			client_bss_dest_file = result["destination_file"]
			client_bss_modified_date = result["modified_date"]
			print(f"Filen er datert {client_bss_modified_date}")


			@transaction.atomic
			def import_cmdb_clients():

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


				def str_to_date(datotidspunkt):
					if datotidspunkt == "NaT":
						return None
					try:
						return make_aware(datetime.strptime(datotidspunkt, date_format))
					except:
						return None


				all_users = dict(User.objects.values_list("username", "pk"))

				def str_to_user(str):
					if len(str) == 0:
						return None
					name = str.replace("OSLOFELLES\\", "")
					try:
						return all_users[name.lower()]
					except:
						return None


				def get_cmdb_instance(comp_name):
					try:
						cmdbdevice = CMDBdevice.objects.get(comp_name=comp_name.lower())
					except:
						cmdbdevice = CMDBdevice.objects.create(comp_name=comp_name.lower())
						#print("Opprettet %s" % comp_name.lower())
					return cmdbdevice


				# OS-håndtering
				def os_readable(os, version, sp):
					if "Windows" in os:
						readable = os.replace("64-bit", "").replace("32-bit", "").replace(",","").strip()
					elif "Linux" in os:
						version_match = re.search(r'(\d).\d', os_version)
						if version_match:
							readable = "%s %s" % (os, version_match[1])
					else:
						readable = os

					return readable.strip() if readable != '' else 'Ukjent'


				client_dropped = 0
				runtime_t0 = time.time()

				# oppdatere alle klienter med bss-kobling

				# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
				import warnings
				warnings.simplefilter("ignore")

				dfRaw = pd.read_excel(client_bss_dest_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				client_bss_data = dfRaw.to_dict('records')

				if client_bss_data == None:
					ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="Feilet, fant ikke klient-bss data.")
					return

				print("Starter å opprette klientinstanser og koble dem til business sub service")
				antall_records = len(client_bss_data)
				for idx, record in enumerate(client_bss_data):

					if idx % 2000 == 0:
						print("%s av %s" % (idx, antall_records))

					comp_name = record["Name"].lower()
					if comp_name == "":
						print(f"Maskinen mangler navn: {record}")
						client_dropped += 1
						continue  # Det må være en verdi på denne

					# Sette type enhet
					if record["Name.1"] in client_business_services:
						# vi sjekker om enheten finnes fra før
						cmdbdevice = get_cmdb_instance(comp_name)
						cmdbdevice.device_type = "KLIENT"
						#print(".", end="", flush=True)
					else:
						continue
						#cmdbdevice.device_type = "SERVER" # handled in another script

					if record["Disk space (GB)"] != "":
						cmdbdevice.comp_disk_space = convertToInt(record["Disk space (GB)"])*1000**3 # returnert som bytes (fra GB)
					cmdbdevice.comp_cpu_core_count = convertToInt(record["CPU total"])
					cmdbdevice.comp_ram = convertToInt(record["RAM (MB)"])
					cmdbdevice.comp_cpu_speed = convertToInt(record["CPU speed (MHz)"])
					cmdbdevice.comp_os = record["Operating System"]
					cmdbdevice.comp_os_version = record["OS Version"]
					cmdbdevice.comp_os_service_pack = record["OS Service Pack"]
					cmdbdevice.comp_os_readable = os_readable(record["Operating System"], record["OS Version"], record["OS Service Pack"])
					cmdbdevice.comp_location = record["Location"]
					cmdbdevice.comments = record["Comments"]
					cmdbdevice.description = record["Description"]
					cmdbdevice.device_active = True
					cmdbdevice.kilde_cmdb = True
					#cmdbdevice.billable = record["Billable"] #finnes ikke lenger i denne rapporten

					sub_name = bss_cache(record["Name.1"])
					if sub_name == None:
						print('Business sub service %s for %s finnes ikke' % (record["Name.1"], comp_name))
					cmdbdevice.sub_name = sub_name # det er OK at den er None
					cmdbdevice.save()



				# Koble maskin til sluttbruker
				print("Starter å koble maskin til sluttbruker")
				dfRaw = pd.read_excel(client_owner_dest_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				client_ower_data = dfRaw.to_dict('records')

				if client_ower_data == None:
					return

				antall_records = len(client_ower_data)
				for idx, record in enumerate(client_ower_data):
					#print(".", end="", flush=True)
					if idx % 2000 == 0:
						print("%s av %s" % (idx, antall_records))

					comp_name = record["Name"].lower()
					if comp_name == "":
						print(f"Klienten mangler navn: {record}")
						client_dropped += 1
						continue  # Det må være en verdi på denne

					# vi sjekker om enheten finnes fra før
					cmdbdevice = get_cmdb_instance(comp_name)

					os_readable = record["Operating System"]
					os_readable = re.sub('microsoft', '', os_readable, flags=re.IGNORECASE)
					os_readable = re.sub('edition', '', os_readable, flags=re.IGNORECASE)
					os_readable.strip()
					if os_readable == '':
						os_readable = 'Ukjent'

					cmdbdevice.device_active = True
					cmdbdevice.kilde_cmdb = True
					cmdbdevice.comp_os = record["Operating System"]
					cmdbdevice.comp_os_readable = os_readable
					cmdbdevice.model_id = record["Model ID"]
					cmdbdevice.sist_sett = str_to_date(str(record["Most recent discovery"]))
					cmdbdevice.last_loggedin_user_id = str_to_user(record["Owner"]) #_id setter direkte uten å først hente ned modelreferanse

					# fjernes siden
					cmdbdevice.maskinadm_virksomhet = cmdbdevice.last_loggedin_user.profile.virksomhet if cmdbdevice.last_loggedin_user else None
					cmdbdevice.maskinadm_sist_oppdatert = cmdbdevice.sist_sett
					cmdbdevice.landesk_login = cmdbdevice.last_loggedin_user
					cmdbdevice.device_type = "KLIENT"
					cmdbdevice.save()



				# Opprydding av gamle ting ikke sett ved oppdatering
				devices_set_inactive = 0

				utdaterte_klienter = CMDBdevice.objects.filter(device_type="KLIENT", sist_oppdatert__lte=timezone.now()-timedelta(hours=12)) # det vil aldri gå mer enn noen få minutter, men for å være sikker..
				print(f"Setter {len(utdaterte_klienter)} utdaterte klienter til deaktivert")
				for klient in utdaterte_klienter:
					klient.device_active = False
					klient.save()
					devices_set_inactive += 1


				# Oppsummering og logging
				runtime_t1 = time.time()
				total_runtime = round(runtime_t1 - runtime_t0, 1)

				logg_entry_message = f'Fant {antall_records} klienter. {client_dropped} manglet navn. Satte {devices_set_inactive} tynne klienter inaktive. Import tok {total_runtime} sekunder'
				logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)
				print(logg_entry_message)
				return logg_entry_message


			# eksekver
			logg_entry_message = import_cmdb_clients()
			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = client_owner_modified_date
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

