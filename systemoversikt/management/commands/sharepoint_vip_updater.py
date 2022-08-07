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
					vip_inst = virtualIP.objects.get(vip_name=line["name"])
					# new, assume no change?
					vip_dropped += 1
				except:
					# update
					vip_inst = virtualIP.objects.create(
						vip_name=line["name"],
						pool_name=line["pool"],
						ip_address=line["ip_address"],
						port=line["port"],
						hitcount=line["hit_count"].replace(",",""),
						)
					print(".", end="", flush=True)
					vip_new += 1

				# Linke IP-adresse
				ipaddr_ins = get_ipaddr_instance(line["ip_address"])
				if ipaddr_ins != None:
					if not vip_inst in ipaddr_ins.viper.all():
						ipaddr_ins.viper.add(vip_inst)
						ipaddr_ins.save()


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
			#print("\n")
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
			pool_not_connected = 0

			import csv
			with open(destination_file, 'r', encoding='latin-1') as file:
				data = list(csv.DictReader(file, delimiter=","))

			if data == None:
				return

			antall_records = len(data)

			for line in data:
				if line["pool"] == "" or line["ip_address"] == "" or line["service_port"] == "":
					continue
				try:
					pool = VirtualIPPool.objects.get(pool_name=line["pool"], port=line["service_port"], ip_address=line["ip_address"])
					pool_dropped += 1
				except:
					pool = VirtualIPPool.objects.create(
						pool_name=line["pool"],
						port=line["service_port"],
						ip_address=line["ip_address"],
						)
					print(".", end="", flush=True)

				# Linke IP-adresse
				ipaddr_ins = get_ipaddr_instance(line["ip_address"])
				if ipaddr_ins != None:
					if not pool in ipaddr_ins.vip_pools.all():
						ipaddr_ins.vip_pools.add(pool)
						ipaddr_ins.save()


				try:
					alle_vip_treff = virtualIP.objects.filter(pool_name=line["pool"]).all()
					for vip in alle_vip_treff:
						pool.vip.add(vip)
					print("*", end="", flush=True)
				except:
					pool_not_connected += 1

				try:
					pool.server = CMDBdevice.objects.get(comp_ip_address=line["ip_address"])
					print("+", end="", flush=True)
				except:
					pass

				pool.save()

			logg_entry_message = 'Fant %s pools i %s. %s nye. %s unike. %s mangler VIP-knytning.' % (
					antall_records,
					filename,
					pool_new,
					pool_dropped,
					pool_not_connected,
				)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB VIP pool import',
					message=logg_entry_message,
				)
			#print("\n")
			print(logg_entry_message)

		#eksekver
		import_pool()

