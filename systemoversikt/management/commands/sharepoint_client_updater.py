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
from systemoversikt.views import push_pushover
import json, os, re, time, sys
import pandas as pd
import numpy as np
import warnings
from systemoversikt.views import sharepoint_get_file


class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_klienter"
		LOG_EVENT_TYPE = "CMDB klient import"
		KILDE = "Service Now"
		PROTOKOLL = "SMTP og SharePoint"
		BESKRIVELSE = "Klienter med eier og business service-kobling"
		FILNAVN = {"client_owner_source_filename": "A34_CMDB_clients.xlsx"}
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

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
		runtime_t0 = time.time()

		try:

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")
			client_owner_source_filename = FILNAVN["client_owner_source_filename"]
			source_filepath = f"{client_owner_source_filename}"
			result = sharepoint_get_file(source_filepath)
			client_owner_dest_file = result["destination_file"]
			client_owner_modified_date = result["modified_date"]
			print(f"Filen er datert {client_owner_modified_date}")

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

				# Koble maskin til sluttbruker
				print("Starter å koble maskin til sluttbruker")

				warnings.simplefilter("ignore")
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

					cmdbdevice.comp_os = record["Operating System"]
					cmdbdevice.comp_os_readable = os_readable
					cmdbdevice.client_model_id = record["Model ID"]
					cmdbdevice.client_sist_sett = str_to_date(str(record["Most recent discovery"]))
					cmdbdevice.client_last_loggedin_user_id = str_to_user(record["Owner"]) #_id setter direkte uten å først hente ned modelreferanse
					cmdbdevice.client_virksomhet = cmdbdevice.client_last_loggedin_user.profile.virksomhet if cmdbdevice.client_last_loggedin_user else None
					cmdbdevice.device_type = "KLIENT"

					cmdbdevice.save()


				#opprydding alle klienter ikke sett fra hovedimport
				for_gammelt = timezone.now() - timedelta(hours=12) # 12 timer gammelt, scriptet bruker bare noen minutter..
				ikke_oppdatert = CMDBdevice.objects.filter(device_type="KLIENT").filter(sist_oppdatert__lte=for_gammelt)
				antall_ikke_oppdatert = ikke_oppdatert.count()


				#ikke_oppdatert.delete() # virker ikke, da det kan være mer enn 999
				batch_size = 500
				while ikke_oppdatert.count():
					ids = ikke_oppdatert.values_list('pk', flat=True)[:batch_size]
					ikke_oppdatert.filter(pk__in=ids).delete()
					print(f"Slettet ny batch på {batch_size}..")


				# Oppsummering og logging
				logg_entry_message = f'Importerte {antall_records} klienter. {client_dropped} manglet navn. Slettet {antall_ikke_oppdatert} klienter som ikke ble sett.'
				logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)
				print(logg_entry_message)
				return logg_entry_message


			# eksekver
			logg_entry_message = import_cmdb_clients()
			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = client_owner_modified_date
			int_config.sist_status = logg_entry_message
			runtime_t1 = time.time()
			int_config.runtime = int(runtime_t1 - runtime_t0)
			int_config.save()


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			push_pushover(f"{SCRIPT_NAVN} feilet") # Push error

