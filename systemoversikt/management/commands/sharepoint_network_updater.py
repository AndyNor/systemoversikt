from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
from systemoversikt.models import *
from django.db import transaction
import os
import json, os
import pandas as pd
import numpy as np
from django.db.models import Q
from systemoversikt.views import get_ipaddr_instance

class Command(BaseCommand):
	def handle(self, **options):

		sp_site = os.environ['SHAREPOINT_SITE']
		client_id = os.environ['SHAREPOINT_CLIENT_ID']
		client_secret = os.environ['SHAREPOINT_CLIENT_SECRET']
		sp = da_tran_SP365(site_url = sp_site, client_id = client_id, client_secret = client_secret)


		# bigip-data
		filename = "OK - Kartoteket F5 Big-IP.xlsx"
		source_filepath_bigip = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename
		destination_file_bigip = 'systemoversikt/import/'+filename
		sp.download(sharepoint_location = sp.create_link(source_filepath_bigip), local_location = destination_file_bigip)


		# router-data
		filename = "OK - Kartoteket Network Gear.xlsx"
		source_filepath_cisco = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename
		destination_file_cisco = 'systemoversikt/import/'+filename
		sp.download(sharepoint_location = sp.create_link(source_filepath_cisco), local_location = destination_file_cisco)


		@transaction.atomic
		def import_network():

			### BigIP
			if ".xlsx" in destination_file_bigip:
				dfRaw = pd.read_excel(destination_file_bigip)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				data = dfRaw.to_dict('records')
			if data == None:
				return

			for line in data:
				print(line)
				try:
					inst = NetworkDevice.objects.get(name=line["Name"])
				except:
					inst = NetworkDevice.objects.create(name=line["Name"])

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


			logg_entry_message = 'BigIP ferdig' % (

				)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB Networkdevice import',
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

			for line in data:
				print(line)
				try:
					inst = NetworkDevice.objects.get(name=line["Name.1"])
				except:
					inst = NetworkDevice.objects.create(name=line["Name.1"])

				inst.ip_address = line["IP Address"]
				model = "%s %s %s" % (line["Manufacturer"], line["Class version"], line["Name.2"])
				inst.model = model
				inst.firmware = line["Firmware version"]
				inst.save()

				# Linke IP-adresse
				ipaddr_ins = get_ipaddr_instance(inst.ip_address)
				if ipaddr_ins != None:
					if not inst in ipaddr_ins.networkdevices.all():
						ipaddr_ins.networkdevices.add(inst)
						ipaddr_ins.save()


			logg_entry_message = 'Ciscoutstyr ferdig.' % (

				)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB Networkdevice import',
					message=logg_entry_message,
				)
			print(logg_entry_message)



		#eksekver
		import_network()

