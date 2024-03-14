# -*- coding: utf-8 -*-
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
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

		INTEGRASJON_KODEORD = "sp_vlan"
		LOG_EVENT_TYPE = "CMDB VLAN import"
		KILDE = "Infoblox"
		PROTOKOLL = "SharePoint"
		BESKRIVELSE = "Nettverkssegmenter med IP-nettverk og beskrivelse"
		FILNAVN = {"infoblox_data": "infoblox.csv", "sone_design": "VLAN_sikkerhetssoner.xlsx"}
		URL = "https://infoblox.oslo.kommune.no/ui/"
		FREKVENS = "Manuelt på forespørsel"

		write_mode = True
		koble_ip = True

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

		try:

			from systemoversikt.views import sharepoint_get_file

			infoblox_data = FILNAVN["infoblox_data"]
			sone_design = FILNAVN["sone_design"]

			# VLAN data
			result = sharepoint_get_file(infoblox_data)
			destination_infoblox_data = result["destination_file"]
			destination_infoblox_data_modified_date = result["modified_date"]
			print(f"Filen er datert {destination_infoblox_data_modified_date}")

			# sonedesign
			result = sharepoint_get_file(sone_design)
			destination_sone_design = result["destination_file"]
			destination_sone_design_modified_date = result["modified_date"]
			print(f"Filen er datert {destination_sone_design_modified_date}")


			@transaction.atomic
			def import_vlan(destination_file, logmessage, filename):

				vlan_dropped = 0
				vlan_new = 0
				vlan_deaktivert = 0

				# klargjøre sonedesignet
				sone_design_status = True
				def load_sone_design(file):
					# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
					import warnings
					warnings.simplefilter("ignore")

					dfRaw = pd.read_excel(file)
					dfRaw = dfRaw.replace(np.nan, '', regex=True)
					data = dfRaw.to_dict('records')
					return data

				sone_design = load_sone_design(destination_sone_design)
				if sone_design == None:
					print("VLAN import: Kunne ikke laste sonedesignet.")
					sone_design_status = False

				def identity_security_zone(ip_address):
					if sone_design_status == True:
						for zone in sone_design:
							supernett = ipaddress.IPv4Network(zone["Supernett"] + "/" + str(zone["Maske"]))
							if ipaddress.ip_address(ip_address) in supernett:
								#print("Match %s with %s" % (ip_address, supernett))
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
				from io import StringIO

				with open(destination_file, 'r', encoding='utf-8') as file:
					data = file.readlines()

				if data == None:
					print("Fant ingen data i filen")
					return

				antall_records = 0
				antall_networkcontainer = 0
				antall_network = 0
				antall_ipv6networkcontainer = 0
				antall_ipv6network = 0

				for line in data:

					if line.startswith("header-"):
						current_header = line
						continue

					if not line.startswith(("networkcontainer,", "network,", "ipv6networkcontainer,", "ipv6network,")):
						continue

					if line.startswith("networkcontainer,"):
						antall_networkcontainer += 1
					if line.startswith("network,"):
						antall_network += 1
					if line.startswith("ipv6networkcontainer,"):
						antall_ipv6networkcontainer += 1
					if line.startswith("ipv6network,"):
						antall_ipv6network += 1


					decoded_line = list(csv.DictReader(StringIO(f"{current_header}\n{line}"), delimiter=","))[0]
					antall_records += 1

					if "netmask*" in decoded_line:
						if decoded_line["address*"] == "" or decoded_line["netmask*"] == "":
							vlan_dropped += 1
							continue
						subnetint = prefixlen(decoded_line["address*"], decoded_line["netmask*"])


					if "cidr*" in decoded_line:
						if decoded_line["address*"] == "" or decoded_line["cidr*"] == "":
							vlan_dropped += 1
							continue
						subnetint = prefixlen(decoded_line["address*"], decoded_line["cidr*"])

					try:
						nc = NetworkContainer.objects.get(ip_address=decoded_line["address*"], subnet_mask=subnetint)
					except:
						nc = NetworkContainer.objects.create(
							ip_address=decoded_line["address*"],
							subnet_mask=subnetint,
							)
						#print("n", end="", flush=True)
						vlan_new += 1

					nc.comment = decoded_line["comment"]
					nc.locationid = decoded_line["EA-LokasjonsID"]
					if not "cidr*" in decoded_line: # disse er ikke med i v6-eksporten..
						nc.orgname = decoded_line["EA-ORG-navn"]
						nc.vlanid = decoded_line["EA-VLAN"]
						nc.vrfname = decoded_line["EA-VRF-navn"]
						nc.network_zone, nc.network_zone_description = identity_security_zone(nc.ip_address)

					nc.netcategory = decoded_line["EA-net-kategori"]

					if "disabled" in decoded_line:
						if decoded_line["disabled"] == "True":
							vlan_deaktivert += 1
							nc.disabled = True

					#print(".", end="", flush=True)
					if write_mode:
						nc.save()

				logg_entry_message = f'Fant {antall_records} VLAN/nettverk i {filename}.\n{antall_networkcontainer} IPv4 containere\n{antall_network} IPv4 nett:\n{antall_ipv6networkcontainer} IPv6 containere:\n{antall_ipv6network} IPv6 nettverk.\n{vlan_new} nye nettverk. {vlan_dropped} kunne ikke importeres. {vlan_deaktivert} er merket som deaktiverte.'
				logg_entry = ApplicationLog.objects.create(
						event_type=f'{LOG_EVENT_TYPE} {logmessage}',
						message=logg_entry_message,
					)
				print(logg_entry_message)
				return logg_entry_message



			@transaction.atomic
			def ip_vlan_kobling():

				ApplicationLog.objects.create(event_type=f"{LOG_EVENT_TYPE} IP-kobling", message="starter..")
				from functools import lru_cache

				@lru_cache(maxsize=128)
				def make_network(network_str):
					return ipaddress.IPv4Network(network_str) if isinstance(network_ip, ipaddress.IPv4Address) else ipaddress.IPv6Network(network_str)

				alle_ip_adresser = NetworkIPAddress.objects.all()
				alle_vlan = NetworkContainer.objects.all()

				antall_ip_adresser = len(alle_ip_adresser)
				for idx, ipadr in enumerate(alle_ip_adresser):
					if idx % 200 == 0:
						print(f"{idx} av {antall_ip_adresser}")
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
					if write_mode:
						ipadr.save()
					#print("%s med %s koblinger." % (ipadr, ant_vlan))
				ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="IP-kobling fullført")

			#eksekver
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter prosessering..")
			logg_entry_message = import_vlan(destination_infoblox_data, "Infoblox", infoblox_data)

			print(f"Kobler sammen alle objekter med IP-adresse mot VLAN/subnet..")
			if koble_ip:
				ip_vlan_kobling()
			print(f"Fullført")

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = destination_infoblox_data_modified_date # eller timezone.now()
			int_config.sist_status = logg_entry_message
			int_config.save()


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# Push error
			#push_pushover(f"{SCRIPT_NAVN} feilet")



