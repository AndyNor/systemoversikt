# -*- coding: utf-8 -*-
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
from django.db import transaction
import json, os
import pandas as pd
import numpy as np
from django.db.models import Q
from systemoversikt.views import get_ipaddr_instance

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_nettwork_eq"
		LOG_EVENT_TYPE = "CMDB Networkdevice import"
		KILDE = "Service Now"
		PROTOKOLL = "SMTP og SharePoint"
		BESKRIVELSE = "BigIP instanser og nettverksinstanser"
		FILNAVN = {"filename1": "OK - Kartoteket F5 Big-IP.xlsx", "filename2": "OK - Kartoteket Network Gear.xlsx"}
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

		print(f"Starter {SCRIPT_NAVN}")

		try:

			sp_site = os.environ['SHAREPOINT_SITE']
			client_id = os.environ['SHAREPOINT_CLIENT_ID']
			client_secret = os.environ['SHAREPOINT_CLIENT_SECRET']
			sp = da_tran_SP365(site_url = sp_site, client_id = client_id, client_secret = client_secret)


			# bigip-data
			filename1 = FILNAVN["filename1"]
			source_filepath_bigip = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename1
			destination_file_bigip = 'systemoversikt/import/'+filename1
			sp.download(sharepoint_location = sp.create_link(source_filepath_bigip), local_location = destination_file_bigip)


			# router-data
			filename2 = FILNAVN["filename2"]
			source_filepath_cisco = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename2
			destination_file_cisco = 'systemoversikt/import/'+filename2
			sp.download(sharepoint_location = sp.create_link(source_filepath_cisco), local_location = destination_file_cisco)


			@transaction.atomic
			def import_network():

				num_cisco = 0
				num_cisco_new = 0
				num_bigip = 0
				num_bigip_new = 0

				### BigIP
				if ".xlsx" in destination_file_bigip:
					dfRaw = pd.read_excel(destination_file_bigip)
					dfRaw = dfRaw.replace(np.nan, '', regex=True)
					data = dfRaw.to_dict('records')
				if data == None:
					return


				num_bigip = len(data)
				for line in data:
					try:
						inst = NetworkDevice.objects.get(name=line["Name"])
					except:
						inst = NetworkDevice.objects.create(name=line["Name"], ip_address=line["IP Address"])
						num_bigip_new += 1

					print(inst.name)
					inst.ip_address = line["IP Address"]
					inst.model = line["Model ID"]
					inst.firmware = ""
					inst.save()

					# Linke IP-adresse
					ipaddr_ins = get_ipaddr_instance(inst.ip_address)
					if ipaddr_ins != None:
						if not inst in ipaddr_ins.networkdevices.all():
							ipaddr_ins.networkdevices.add(inst)
							ipaddr_ins.save()


				logg_entry_message = '%s bigip-enheter funnet. %s nye lagt til.' % (
						num_bigip,
						num_bigip_new,
					)
				logg_entry = ApplicationLog.objects.create(
						event_type=LOG_EVENT_TYPE,
						message=logg_entry_message,
					)
				print(logg_entry_message)


				### Cisco
				if ".xlsx" in destination_file_cisco:
					dfRaw = pd.read_excel(destination_file_cisco)
					dfRaw = dfRaw.replace(np.nan, '', regex=True)
					data = dfRaw.to_dict('records')
				if data == None:
					return

				num_cisco = len(data)
				for line in data:
					try:
						inst = NetworkDevice.objects.get(name=line["Name"])
					except:
						inst = NetworkDevice.objects.create(name=line["Name"], ip_address=line["IP Address"])
						num_cisco_new += 1

					print(inst.name)
					inst.ip_address = line["IP Address"]
					model = "%s %s %s" % (line["Manufacturer"], line["Class"], line["Name.1"])
					inst.model = model
					inst.firmware = line["Firmware version"]
					inst.save()

					# Linke IP-adresse
					ipaddr_ins = get_ipaddr_instance(inst.ip_address)
					if ipaddr_ins != None:
						if not inst in ipaddr_ins.networkdevices.all():
							ipaddr_ins.networkdevices.add(inst)
							ipaddr_ins.save()


				logg_entry_message = '%s cisco-enheter funnet. %s nye lagt til.' % (
						num_cisco,
						num_cisco_new,
					)
				logg_entry = ApplicationLog.objects.create(
						event_type=LOG_EVENT_TYPE,
						message=logg_entry_message,
					)
				print(logg_entry_message)



			#eksekver
			import_network()

		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# Push error
			push_pushover(f"{SCRIPT_NAVN} feilet")

