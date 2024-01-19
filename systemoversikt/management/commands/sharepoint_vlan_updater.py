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
		FILNAVN = {"filename1": "infoblox_network_v4.csv", "filename2": "infoblox_network_v6.csv", "filename3": "infoblox_network_container_v4.csv", "filename4": "infoblox_network_container_v6.csv", "sone_design": "VLAN_sikkerhetssoner.xlsx"}
		URL = "https://infoblox.oslo.kommune.no/ui/"
		FREKVENS = "Manuelt på forespørsel"

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

			filename1 = FILNAVN["filename1"]
			filename2 = FILNAVN["filename2"]
			filename3 = FILNAVN["filename3"]
			filename4 = FILNAVN["filename4"]
			sone_design = FILNAVN["sone_design"]

			source_filepath = f"{filename1}"
			result = sharepoint_get_file(source_filepath)
			destination_file1 = result["destination_file"]
			destination_file1_modified_date = result["modified_date"]
			print(f"Filen er datert {destination_file1_modified_date}")

			source_filepath = f"{filename2}"
			result = sharepoint_get_file(source_filepath)
			destination_file2 = result["destination_file"]
			destination_file2_modified_date = result["modified_date"]
			print(f"Filen er datert {destination_file2_modified_date}")

			source_filepath = f"{filename3}"
			result = sharepoint_get_file(source_filepath)
			destination_file3 = result["destination_file"]
			destination_file3_modified_date = result["modified_date"]
			print(f"Filen er datert {destination_file3_modified_date}")

			source_filepath = f"{filename4}"
			result = sharepoint_get_file(source_filepath)
			destination_file4 = result["destination_file"]
			destination_file4_modified_date = result["modified_date"]
			print(f"Filen er datert {destination_file4_modified_date}")

			# sonedesign
			source_filepath = f"{sone_design}"
			result = sharepoint_get_file(source_filepath)
			destination_sone_design = result["destination_file"]
			destination_sone_design_modified_date = result["modified_date"]
			print(f"Filen er datert {destination_sone_design_modified_date}")


			@transaction.atomic
			def import_vlan(destination_file, logmessage, filename):

				vlan_dropped = 0
				vlan_new = 0
				vlan_deaktivert = 0

				sone_design_status = True


				# klargjøre sonedesignet
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
						#print("n", end="", flush=True)
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

					#print(".", end="", flush=True)
					nc.save()


				logg_entry_message = 'Fant %s VLAN/nettverk i %s. %s nye og %s kunne ikke importeres. %s deaktiverte.' % (
						antall_records,
						filename,
						vlan_new,
						vlan_dropped,
						vlan_deaktivert,
					)
				logg_entry = ApplicationLog.objects.create(
						event_type=f'{LOG_EVENT_TYPE} {logmessage}',
						message=logg_entry_message,
					)
				print(logg_entry_message)
				return logg_entry_message

			#eksekver

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

			logg_entry_message = ""

			logg_entry_message += import_vlan(destination_file1, "ipv4networks", filename1)
			logg_entry_message += import_vlan(destination_file1, "ipv6networks", filename2)
			logg_entry_message += import_vlan(destination_file2, "ipv4networkcontainers", filename3)
			logg_entry_message += import_vlan(destination_file3, "ipv6networkcontainers", filename4)


			#match opp alle IP-adresser mot VLAN
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
					if idx % 2000 == 0:
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
					ipadr.save()
					#print("%s med %s koblinger." % (ipadr, ant_vlan))
				ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="Fullført")

			print(f"Kobler sammen alle objekter med IP-adresse mot VLAN/subnet..")
			ip_vlan_kobling()
			print(f"Fullført")

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = destination_file1_modified_date # eller timezone.now()
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
			push_pushover(f"{SCRIPT_NAVN} feilet")


