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
		filename = "OK Load Balancer Services.csv"
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
					vip_inst = virtualIP.objects.get(vip_name=line["u_load_balancer_service_1"])
					# new, assume no change?
					vip_dropped += 1
					print(".", end="", flush=True)
				except:
					# update
					vip_inst = virtualIP.objects.create(
						vip_name=line["u_load_balancer_service_1"],
					)
					vip_new += 1
					print("+", end="", flush=True)

				vip_inst.pool_name = line["u_load_balancer_service_1.pool"]
				vip_inst.ip_address = line["u_load_balancer_service_1.ip_address"]
				vip_inst.port = line["u_load_balancer_service_1.port"]
				vip_inst.hitcount = line["u_load_balancer_service_1.hit_count"].replace(",","")
				vip_inst.save()


				# Linke IP-adresse
				ipaddr_ins = get_ipaddr_instance(line["u_load_balancer_service_1.ip_address"])
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
		filename = "OK Load Balancer Pool Members.csv"
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
				if line["u_load_balancer_pool_member_1.pool"] == "" or line["u_load_balancer_pool_member_1.ip_address"] == "" or line["u_load_balancer_pool_member_1.service_port"] == "":
					continue
				try:
					pool = VirtualIPPool.objects.get(
							pool_name=line["u_load_balancer_pool_member_1.pool"],
							port=line["u_load_balancer_pool_member_1.service_port"],
							ip_address=line["u_load_balancer_pool_member_1.ip_address"]
						)
					print(".", end="", flush=True)
					pool_dropped += 1
				except:
					pool = VirtualIPPool.objects.create(
							pool_name=line["u_load_balancer_pool_member_1.pool"],
							port=line["u_load_balancer_pool_member_1.service_port"],
							ip_address=line["u_load_balancer_pool_member_1.ip_address"],
						)
					print("+", end="", flush=True)

				# Linke IP-adresse
				ipaddr_ins = get_ipaddr_instance(line["u_load_balancer_pool_member_1.ip_address"])
				if ipaddr_ins != None:
					if not pool in ipaddr_ins.vip_pools.all():
						ipaddr_ins.vip_pools.add(pool)
						ipaddr_ins.save()

				try:
					alle_vip_treff = virtualIP.objects.filter(pool_name=line["u_load_balancer_pool_member_1.pool"]).all()
					for vip in alle_vip_treff:
						pool.vip.add(vip)
					print("p", end="", flush=True)
				except:
					pool_not_connected += 1
					print("?", end="", flush=True)

				try:
					pool.server = CMDBdevice.objects.get(comp_ip_address=line["u_load_balancer_pool_member_1.ip_address"])
					print("s", end="", flush=True)
				except:
					print("?", end="", flush=True)
					#pass

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

