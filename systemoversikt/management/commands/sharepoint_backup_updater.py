from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
from systemoversikt.models import *
from django.db import transaction
import os
import json, os
import pandas as pd
import numpy as np
from django.db.models import Q


class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_backup"
		LOG_EVENT_TYPE="CMDB Backup import"
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")
		filnavn = "CommVault client backup volume (GB) with BS and NSS relations.xlsx"

		sp = da_tran_SP365(site_url = os.environ['SHAREPOINT_SITE'], client_id = os.environ['SHAREPOINT_CLIENT_ID'], client_secret = os.environ['SHAREPOINT_CLIENT_SECRET'])
		source = sp.create_link("https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filnavn)
		destination_file = 'systemoversikt/import/'+filnavn
		sp.download(sharepoint_location = source, local_location = destination_file)

		@transaction.atomic
		def main(destination_file, filnavn, LOG_EVENT_TYPE):

			if ".xlsx" in destination_file:
				#dfRaw = pd.read_excel(destination_file, sheet_name='CommVault Summary', skiprows=8, usecols=['Client', 'Total Protected App Size (GB)', 'Source Capture Date', 'Business Sub Service', ])
				dfRaw = pd.read_excel(destination_file, sheet_name='Export', skiprows=0, usecols=['Customer ID', 'Client', 'Total Protected App Size (GB)', 'Backup frequency', 'Business Service / Most Critical Service', 'Storage Policy',])
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				data = dfRaw.to_dict('records')

			if data == None:
				return

			failed_device = 0
			failed_bss = 0


			# fjerner alle registrerte innslag (finnes ingen identifikator)

			names = [line["Client"] for line in data]
			import collections
			counter = collections.Counter(names)
			flere_innslag = [k for k, v in counter.items() if v > 1]

			CMDBbackup.objects.all().delete()
			antall_linjer = len(data)

			for line in data:
				#print(line)
				if line['Customer ID'] == "Total": # end of content
					print("End of data")
					break
				try:
					device = CMDBdevice.objects.get(comp_name__iexact=line["Client"])
				except:
					device = None
					failed_device += 1
					print("%s feilet" % (line["Client"]))

				try:
					bss = CMDBRef.objects.get(navn__iexact=line["Business Sub Service"])
				except:
					bss = None
					failed_bss += 1


				#print(device)
				inst = CMDBbackup.objects.create(device=device, device_str=line["Client"])

				print(".", end="", flush=True)

				size = int(line["Total Protected App Size (GB)"] * 1000 * 1000 * 1000) # fra giga bytes til bytes (antar 1000 siden dette er et diskverktøy)
				inst.backup_size_bytes = size
				inst.backup_frequency = line["Backup frequency"]
				inst.storage_policy = line["Storage Policy"]
				#inst.export_date = line["Source Capture Date"]
				inst.bss = bss

				inst.save()


			logg_flere_innslag = ', '.join(flere_innslag)
			logg_entry_message = '%s innslag importert. %s feilet oppslag mot server. %s feilede bss oppslag. Duplikate innslag: %s' % (antall_linjer, failed_device, failed_bss, logg_flere_innslag)
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_entry_message,
				)
			print("\n")
			print(logg_entry_message)


		#eksekver
		main(destination_file, filnavn, LOG_EVENT_TYPE)