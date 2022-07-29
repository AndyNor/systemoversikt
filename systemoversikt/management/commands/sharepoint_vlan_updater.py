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

		sp_site = os.environ['SHAREPOINT_SITE']
		client_id = os.environ['SHAREPOINT_CLIENT_ID']
		client_secret = os.environ['SHAREPOINT_CLIENT_SECRET']
		sp = da_tran_SP365(site_url = sp_site, client_id = client_id, client_secret = client_secret)


		# VIP-data
		filename = "cmdb_ci_lb_service.csv"
		source_filepath = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename
		source_file = sp.create_link(source_filepath)
		destination_file = 'systemoversikt/import/'+filename

		sp.download(sharepoint_location = source_file, local_location = destination_file)


		@transaction.atomic
		def import_vip():

			vip_dropped = 0
			vip_new = 0

			import csv
			with open(destination_file, 'r', encoding='latin-1') as file:
				data = list(csv.DictReader(file, delimiter=","))

			if data == None:
				return

			antall_records = len(data)

			for line in data:
				try:
					virtualIP.objects.get(vip_name=line["name"])
					# new, assume no change?
					vip_dropped += 1
				except:
					# update
					virtualIP.objects.create(
						vip_name=line["name"],
						pool_name=line["pool"],
						ip_address=line["ip_address"],
						port=line["port"],
						hitcount=line["hit_count"].replace(",",""),
						)
					vip_new += 1


			logg_entry_message = 'Fant %s VIP-er i %s. %s nye og %s eksisterende.' % (
					antall_records,
					filename,
					vip_new,
					vip_dropped,
				)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB VIP import',
					message=logg_entry_message,
				)
			print("\n")
			print(logg_entry_message)

		#eksekver
		import_vip()



		# VIP-pool data
		filename = "cmdb_ci_lb_pool_member.csv"
		source_filepath = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename
		source_file = sp.create_link(source_filepath)
		destination_file = 'systemoversikt/import/'+filename

		sp.download(sharepoint_location = source_file, local_location = destination_file)


		@transaction.atomic
		def import_pool():

			pool_dropped = 0
			pool_new = 0

			import csv
			with open(destination_file, 'r', encoding='latin-1') as file:
				data = list(csv.DictReader(file, delimiter=","))

			if data == None:
				return

			antall_records = len(data)

			for line in data:
				if line["pool"] == "" or line["name"] == "" or line["service_port"] == "":
					continue
				try:
					VirtualIPPool.objects.get(pool_name=line["name"], port=line["service_port"])
					# old, assume no change?
					pool_dropped += 1
				except:
					# new entry
					#print(line["name"])
					#print(line["service_port"])
					#print(line["ip_address"])
					#print(line["pool"])
					v = VirtualIPPool.objects.create(
						pool_name=line["name"],
						ip_address=line["ip_address"],
						port=line["service_port"],
						)
					try:
						vip = virtualIP.objects.get(pool_name=line["pool"])
						v.vip = vip
						v.save()
					except:
						pass
					pool_new += 1


			logg_entry_message = 'Fant %s VIP-er i %s. %s nye og %s eksisterende.' % (
					antall_records,
					filename,
					pool_new,
					pool_dropped,
				)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB VIP pool import',
					message=logg_entry_message,
				)
			print("\n")
			print(logg_entry_message)

		#eksekver
		import_pool()

