# -*- coding: utf-8 -*-
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
from systemoversikt.models import *
from django.db import transaction
import os, json, time
import pandas as pd
import numpy as np
from django.db.models import Q
from functools import lru_cache
import ipaddress
from systemoversikt.views import sharepoint_get_file
from netaddr import IPNetwork, IPAddress

class Command(BaseCommand):

	antall_ip_koblinger_totalt = 0

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
		int_config.helsestatus = "Forbereder"
		int_config.save()

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")

		def print_with_timestamp(message):
			current_time = datetime.now()
			print(f"{current_time.hour}:{current_time.minute} {message}")

		try:

			runtime_t0 = time.time()
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

				int_config.elementer = int(antall_records)
				logg_entry_message = f'Fant {antall_records} VLAN/nettverk i {filename}. {antall_networkcontainer} IPv4 containere, {antall_network} IPv4 nett, {antall_ipv6networkcontainer} IPv6 containere, {antall_ipv6network} IPv6 nettverk, {vlan_new} nye nettverk. {vlan_dropped} kunne ikke importeres. {vlan_deaktivert} er merket som deaktiverte.'
				print_with_timestamp(logg_entry_message)
				return logg_entry_message


			@lru_cache(maxsize=128)
			def make_network(network_str, network_ip):
				return ipaddress.IPv4Network(network_str) if isinstance(network_ip, ipaddress.IPv4Address) else ipaddress.IPv6Network(network_str)


			def ip_vlan_kobling():
				alle_ip_adresser = list(NetworkIPAddress.objects.all())
				alle_vlan = list(NetworkContainer.objects.all())

				# Precompute networks and store in a dictionary
				vlan_networks = {}
				for vlan in alle_vlan:
					network_str = f"{vlan.ip_address}/{vlan.subnet_mask}"
					vlan_networks[vlan.pk] = IPNetwork(network_str)

				antall_ip_adresser = len(alle_ip_adresser)
				chunk_size = 1000

				def process_chunk(chunk):
					vlan_m2m_updates = []

					for ipadr in chunk:
						if ipadr.ip_address is None:  # skal ikke skje, men det var en feil i et tidligere importscript (klienter)
							ipadr.delete()
							continue
						ip = IPAddress(ipadr.ip_address)
						for vlan_pk, network in vlan_networks.items():
							if ip in network:
								Command.antall_ip_koblinger_totalt += 1
								if write_mode:
									vlan_m2m_updates.append((ipadr, vlan_pk))

					# Handle many-to-many relationships
					@transaction.atomic
					def handle_m2m():
						print("Lagrer chunk til database...")
						for ipadr, vlan_pk in vlan_m2m_updates:
							vlan = NetworkContainer.objects.get(pk=vlan_pk)
							ipadr.vlan.add(vlan)
					handle_m2m()

				for i in range(0, antall_ip_adresser, chunk_size):
					chunk = alle_ip_adresser[i:i + chunk_size]
					print_with_timestamp(f"Processing chunk {i} to {i + chunk_size} of {antall_ip_adresser}")
					process_chunk(chunk)

				ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="IP-kobling fullført")


			"""
			def ip_vlan_kobling():
				alle_ip_adresser = list(NetworkIPAddress.objects.all())
				vlan_cache = {vlan.pk: (vlan.ip_address, vlan.subnet_mask) for vlan in NetworkContainer.objects.all()}

				antall_ip_adresser = len(alle_ip_adresser)
				chunk_size = 500

				def process_chunk(chunk):
					vlan_m2m_updates = []

					for ipadr in chunk:
						if ipadr.ip_address is None:  # skal ikke skje, men det var en feil i et tidligere importscript (klienter)
							ipadr.delete()
							continue
						for vlan_pk, (ip_address, subnet_mask) in vlan_cache.items():
							network_ip = ipaddress.ip_address(ip_address)
							network_str = ip_address + "/" + str(subnet_mask)
							network = make_network(network_str, network_ip)
							if ipaddress.ip_address(ipadr.ip_address) in network:
								if write_mode:
									vlan_m2m_updates.append((ipadr, vlan_pk))

					# Handle many-to-many relationships
					@transaction.atomic
					def handle_m2m():
						print("Lagrer chunk til database...")
						for ipadr, vlan_pk in vlan_m2m_updates:
							vlan = NetworkContainer.objects.get(pk=vlan_pk)
							ipadr.vlan.add(vlan)
					handle_m2m()

				for i in range(0, antall_ip_adresser, chunk_size):
					chunk = alle_ip_adresser[i:i + chunk_size]
					print_with_timestamp(f"Processing chunk {i} to {i + chunk_size} of {antall_ip_adresser}")
					process_chunk(chunk)

				ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="IP-kobling fullført")
			"""

			"""
			#newer but old code
			def ip_vlan_kobling():
				alle_ip_adresser = list(NetworkIPAddress.objects.all())
				alle_vlan = list(NetworkContainer.objects.all())


				antall_ip_adresser = len(alle_ip_adresser)
				chunk_size = 500


				def process_chunk(chunk):
					vlan_m2m_updates = []

					for ipadr in chunk:
						if ipadr.ip_address is None:  # skal ikke skje, men det var en feil i et tidligere importscript (klienter)
							ipadr.delete()
							continue
						for vlan in alle_vlan:
							network_ip = ipaddress.ip_address(vlan.ip_address)
							network_str = vlan.ip_address + "/" + str(vlan.subnet_mask)
							network = make_network(network_str, network_ip)
							if ipaddress.ip_address(ipadr.ip_address) in network:
								if write_mode:
									vlan_m2m_updates.append((ipadr, vlan))

					# Handle many-to-many relationships
					@transaction.atomic
					def handle_m2m():
						print("Lagrer chunk til database...")
						for ipadr, vlan in vlan_m2m_updates:
							ipadr.vlan.add(vlan)
					handle_m2m()


				for i in range(0, antall_ip_adresser, chunk_size):
					chunk = alle_ip_adresser[i:i + chunk_size]
					print_with_timestamp(f"Processing chunk {i} to {i + chunk_size} of {antall_ip_adresser}")
					process_chunk(chunk)

				ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="IP-kobling fullført")
			"""

			"""
			#OLD CODE
			@transaction.atomic
			def ip_vlan_kobling():
				alle_ip_adresser = NetworkIPAddress.objects.all()
				alle_vlan = NetworkContainer.objects.all()

				antall_ip_adresser = len(alle_ip_adresser)
				for idx, ipadr in enumerate(alle_ip_adresser):
					if idx % 500 == 0:
						print_with_timestamp(f"{idx} av {antall_ip_adresser}")
					if ipadr.ip_address == None: # skal ikke skje, men det var en feil i et tidligere importscript (klienter)
						ipadr.delete()
						continue
					ant_vlan = 0
					for vlan in alle_vlan:
						network_ip = ipaddress.ip_address(vlan.ip_address)
						network_str = vlan.ip_address + "/" + str(vlan.subnet_mask)
						network = make_network(network_str, network_ip)
						if ipaddress.ip_address(ipadr.ip_address) in network:
							Command.antall_ip_koblinger_totalt += 1
							ipadr.vlan.add(vlan)
							ant_vlan += 1
					if write_mode:
						ipadr.save()
					#print("%s med %s koblinger." % (ipadr, ant_vlan))
				ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="IP-kobling fullført")
			"""


			#eksekver
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter prosessering..")

			print("Starter import til databasen...")
			ApplicationLog.objects.create(event_type=f"{LOG_EVENT_TYPE} IP-kobling", message="starter..")
			message = import_vlan(destination_infoblox_data, "Infoblox", infoblox_data)

			print(f"Sletter gamle innslag..")
			for_gammelt = timezone.now() - timedelta(hours=6) # 6 timer gammelt
			ikke_oppdatert = NetworkContainer.objects.filter(sist_oppdatert__lte=for_gammelt)
			batch_size = 500
			while ikke_oppdatert.count():
				ids = ikke_oppdatert.values_list('pk', flat=True)[:batch_size]
				ikke_oppdatert.filter(pk__in=ids).delete()
				print(f"Slettet ny batch på {batch_size}..")

			if koble_ip:
				print(f"Kobler sammen alle objekter med IP-adresse mot VLAN/subnet..")
				ip_vlan_kobling()

			print(f"Fullført")




			# lagre sist oppdatert tidspunkt
			runtime_t1 = time.time()
			logg_total_runtime = int(runtime_t1 - runtime_t0)
			logg_entry_message = f"Kjøretid:{logg_total_runtime}: write_mode: {write_mode}, koble_ip: {koble_ip}, {message}, {Command.antall_ip_koblinger_totalt} VLAN-IP koblinger"
			print(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(event_type=f'{LOG_EVENT_TYPE}', message=logg_entry_message,)

			int_config.dato_sist_oppdatert = destination_infoblox_data_modified_date # eller timezone.now()
			int_config.sist_status = logg_entry_message
			int_config.runtime = logg_total_runtime
			int_config.helsestatus = "Vellykket"
			int_config.save()


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			import traceback
			int_config.helsestatus = f"Feilet\n{traceback.format_exc()}"
			int_config.save()
			push_pushover(f"{SCRIPT_NAVN} feilet") # Push error

