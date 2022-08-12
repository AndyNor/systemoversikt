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
		filename1 = "infoblox_network_v4.csv"
		filename2 = "infoblox_network_v6.csv"
		filename3 = "infoblox_network_container_v4.csv"
		filename4 = "infoblox_network_container_v6.csv"
		sone_design = "VLAN_sikkerhetssoner.xlsx"

		source1 = sp.create_link("https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename1)
		source2 = sp.create_link("https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename2)
		source3 = sp.create_link("https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename3)
		source4 = sp.create_link("https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename4)
		source_sone_design = sp.create_link("https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+sone_design)

		destination_file1 = 'systemoversikt/import/'+filename1
		destination_file2 = 'systemoversikt/import/'+filename2
		destination_file3 = 'systemoversikt/import/'+filename3
		destination_file4 = 'systemoversikt/import/'+filename4
		destination_sone_design = 'systemoversikt/import/'+sone_design

		sp.download(sharepoint_location = source1, local_location = destination_file1)
		sp.download(sharepoint_location = source2, local_location = destination_file2)
		sp.download(sharepoint_location = source3, local_location = destination_file3)
		sp.download(sharepoint_location = source4, local_location = destination_file4)
		sp.download(sharepoint_location = source_sone_design, local_location = destination_sone_design)


		@transaction.atomic
		def import_vlan(destination_file, logmessage, filename):

			vlan_dropped = 0
			vlan_new = 0
			vlan_deaktivert = 0

			sone_design_status = True


			# klargjøre sonedesignet
			def load_sone_design(file):
				if ".xlsx" in file:
					dfRaw = pd.read_excel(file)
					dfRaw = dfRaw.replace(np.nan, '', regex=True)
					data = dfRaw.to_dict('records')
					return data

			sone_design = load_sone_design(destination_sone_design)
			if sone_design == None:
				print("VLAN import: Kunne ikke laste sonedesignet.")
				sone_design_status = False

			def identity_security_zone(ip_address):
				if sone_design_status:
					for zone in sone_design:
						supernett = ipaddress.IPv4Network(zone["Supernett"] + "/" + str(zone["Maske"]))
						if ipaddress.ip_address(ip_address) in supernett:
							print("Match %s with %s" % (ip_address, supernett))
							return (zone["Sikkerhetsnivå"], zone["Beskrivelse"])

				return (None, None)


			# klargjøre metoder for å behandle vlan-importfiler fra Infoblox
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
					nc.network_zone, nc.network_zone_description = identity_security_zone(nc.ip_address)

				nc.netcategory = line["EA-net-kategori"]

				if "disabled" in line:
					if line["disabled"] == "True":
						vlan_deaktivert += 1
						nc.disabled = True

				print(".", end="", flush=True)
				nc.save()


			logg_entry_message = 'Fant %s VLAN/nettverk i %s. %s nye og %s kunne ikke importeres. %s deaktiverte.' % (
					antall_records,
					filename,
					vlan_new,
					vlan_dropped,
					vlan_deaktivert,
				)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB VLAN import ' + logmessage,
					message=logg_entry_message,
				)
			print("\n")
			print(logg_entry_message)

		#eksekver

		LOG_EVENT_TYPE="CMDB VLAN import"
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

		import_vlan(destination_file1, "networks", filename1)
		import_vlan(destination_file1, "networks", filename2)
		import_vlan(destination_file2, "ipv4networks", filename3)
		import_vlan(destination_file3, "ipv6networks", filename4)



		#match opp alle IP-adresser mot VLAN
		@transaction.atomic
		def ip_vlan_kobling():

			LOG_EVENT_TYPE="CMDB VLAN IP-kobling"
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")
			from functools import lru_cache

			@lru_cache(maxsize=128)
			def make_network(network_str):
				return ipaddress.IPv4Network(network_str) if isinstance(network_ip, ipaddress.IPv4Address) else ipaddress.IPv6Network(network_str)

			alle_ip_adresser = NetworkIPAddress.objects.all()
			alle_vlan = NetworkContainer.objects.all()

			for ipadr in alle_ip_adresser:
				if ipadr.ip_address == None: # skal ikke skje, men det var en feil i et tidligere importscript (klienter)
					ipadr.delete()
					continue
				ant_vlan = 0
				for vlan in alle_vlan:
					network_ip = ipaddress.ip_address(vlan.ip_address)
					network_str = vlan.ip_address + "/" + str(vlan.subnet_mask)
					network = make_network(network_str)
					if ipaddress.ip_address(ipadr.ip_address) in network:
						ipadr.vlan.add(vlan)
						ant_vlan += 1
				ipadr.save()
				print("%s med %s koblinger." % (ipadr, ant_vlan))
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="Fullført")

		ip_vlan_kobling()


