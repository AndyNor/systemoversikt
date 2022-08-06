from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
from systemoversikt.models import *
from django.contrib.auth.models import User
from django.db import transaction
import os
import time
from functools import lru_cache
import json, os
import pandas as pd
import numpy as np
from datetime import datetime
from django.utils.timezone import make_aware
import re

class Command(BaseCommand):
	def handle(self, **options):

		runtime_t0 = time.time()

		sp_site = os.environ['SHAREPOINT_SITE']
		client_id = os.environ['SHAREPOINT_CLIENT_ID']
		client_secret = os.environ['SHAREPOINT_CLIENT_SECRET']

		sp = da_tran_SP365(site_url = sp_site, client_id = client_id, client_secret = client_secret)

		source_filepath = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/OK_computers.xlsx"
		source_file = sp.create_link(source_filepath)
		destination_file = 'systemoversikt/import/OK_computers.xlsx'

		sp.download(sharepoint_location = source_file, local_location = destination_file)


		date_format = "%Y-%m-%d %H:%M:%S"
		# eksempel 22.05.2022  17:48:10
		def str_to_date(datotidspunkt):
			if datotidspunkt == "NaT":
				return None
			try:
				return make_aware(datetime.strptime(datotidspunkt, date_format))
			except:
				return None

		def str_to_user(str):
			if len(str) == 0:
				return None
			name = str.replace("OSLOFELLES\\", "")
			try:
				return User.objects.get(username__iexact=name)
			except:
				return None

		@transaction.atomic
		def import_cmdb_clients():

			client_dropped = 0

			if ".xlsx" in destination_file:
				dfRaw = pd.read_excel(destination_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				data = dfRaw.to_dict('records')

			if data == None:
				return

			antall_records = len(data)
			all_existing_devices = list(CMDBdevice.objects.filter(device_type="KLIENT")) # denne filen inneholder bare klienter. Tykke, støtte og VDI er allerede i OK_computers_bss.xlsx

			print("Alt lastet, oppdaterer databasen:")
			for idx, record in enumerate(data):
				print(".", end="", flush=True)
				if idx % 1000 == 0:
					print("\n%s av %s" % (idx, antall_records))

				comp_name = record["Name"].lower()
				if comp_name == "":
					print("Klienten mangler navn")
					client_dropped += 1
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
				cmdbdevice.last_loggedin_user = str_to_user(record["Owner"])

				# koble IP-adresse
				# Det er ikke IP-adresser i filen (med noen veldig få unntak)

				# fjernes siden
				cmdbdevice.maskinadm_virksomhet = cmdbdevice.last_loggedin_user.profile.virksomhet if cmdbdevice.last_loggedin_user else None
				cmdbdevice.maskinadm_sist_oppdatert = cmdbdevice.sist_sett
				cmdbdevice.landesk_login = cmdbdevice.last_loggedin_user

				if record["Type"] == "TYNNKLIENT": #TYKK, STØTTE OG VDI er allerede merket fra OK_computers_bss.xlsx
					cmdbdevice.device_type = "KLIENT"

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

			logg_entry_message = 'Fant %s klienter. %s manglet navn. Satte %s tynne klienter inaktive. Import tok %s sekunder' % (
					antall_records,
					client_dropped,
					devices_set_inactive,
					total_runtime,
				)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB klient import',
					message=logg_entry_message,
				)
			print(logg_entry_message)


		# eksekver
		import_cmdb_clients()

