from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
from systemoversikt.models import *
from django.db import transaction
import os
import json, os
import pandas as pd
import numpy as np
from django.db.models import Q
import ipaddress

class Command(BaseCommand):
	def handle(self, **options):

		sp_site = os.environ['SHAREPOINT_SITE']
		client_id = os.environ['SHAREPOINT_CLIENT_ID']
		client_secret = os.environ['SHAREPOINT_CLIENT_SECRET']
		sp = da_tran_SP365(site_url = sp_site, client_id = client_id, client_secret = client_secret)


		# VIP-data
		filename1 = "infoblox_network.csv"
		filename2 = "infoblox_network_container_v4.csv"
		filename3 = "infoblox_network_container_v6.csv"

		source_filepath1 = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename1
		source_filepath2 = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename2
		source_filepath3 = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename3

		source_file1 = sp.create_link(source_filepath1)
		source_file2 = sp.create_link(source_filepath2)
		source_file3 = sp.create_link(source_filepath3)

		destination_file1 = 'systemoversikt/import/'+filename1
		destination_file2 = 'systemoversikt/import/'+filename2
		destination_file3 = 'systemoversikt/import/'+filename3

		sp.download(sharepoint_location = source_file1, local_location = destination_file1)
		sp.download(sharepoint_location = source_file2, local_location = destination_file2)
		sp.download(sharepoint_location = source_file3, local_location = destination_file3)


		@transaction.atomic
		def import_vlan(destination_file, logmessage, filename):

			vlan_dropped = 0
			vlan_new = 0


			def prefixlen(ip, netmask):
				i = ipaddress.ip_address(ip)
				network = ip + "/" + netmask
				if isinstance(i, ipaddress.IPv4Address):
					network = ipaddress.IPv4Network(network)
				else:
					network = ipaddress.IPv6Network(network)
				return network.prefixlen

			import csv
			with open(destination_file, 'r', encoding='utf-8') as file:
				data = list(csv.DictReader(file, delimiter=","))

			if data == None:
				return

			antall_records = len(data)

			for line in data:

				if "disabled" in line:
					if line["disabled"] == "True":
						vlan_dropped += 1
						continue

				if "netmask*" in line: # ipv4 eksport
					subnetint = prefixlen(line["address*"], line["netmask*"])

					if line["address*"] == "" or line["netmask*"] == "":
						vlan_dropped += 1
						continue

				if "cidr*" in line: #ipv4 eksport
					subnetint = prefixlen(line["address*"], line["cidr*"])

					if line["address*"] == "" or line["cidr*"] == "":
						vlan_dropped += 1
						continue


				try:
					nc = NetworkContainer.objects.get(ip_address=line["address*"], subnet_mask=subnetint)
					# new, assume no change?
				except:
					# update
					nc = NetworkContainer.objects.create(
						ip_address=line["address*"],
						subnet_mask=subnetint,
						)
					print("n", end="", flush=True)
					vlan_new += 1

				nc.comment = line["comment"]
				nc.locationid = line["EA-LokasjonsID"]
				if not "cidr*" in line: # disse er ikke med i v6-eksporten..
					nc.orgname = line["EA-ORG-navn"]
					nc.vlanid = line["EA-VLAN"]
					nc.vrfname = line["EA-VRF-navn"]

				nc.netcategory = line["EA-net-kategori"]

				print(".", end="", flush=True)
				nc.save()


			logg_entry_message = 'Fant %s VLAN/nettverk i %s. %s nye og %s kunne ikke importeres.' % (
					antall_records,
					filename,
					vlan_new,
					vlan_dropped,
				)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB VLAN import ' + logmessage,
					message=logg_entry_message,
				)
			print("\n")
			print(logg_entry_message)

		#eksekver
		import_vlan(destination_file1, "networks", filename1)
		import_vlan(destination_file2, "ipv4networks", filename2)
		import_vlan(destination_file3, "ipv6networks", filename3)
