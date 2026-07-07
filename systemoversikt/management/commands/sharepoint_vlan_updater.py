# -*- coding: utf-8 -*-
# Change log:
# 2026-07-07: Import Infoblox host/fixed/A/PTR records and extra network EAs for IP search.
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
from systemoversikt.views import sharepoint_get_file, get_ipaddr_instance
from netaddr import IPNetwork, IPAddress
from systemoversikt.import_cleanup_guard import IMPORT_CLEANUP_MIN_AGE_HOURS

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


			INFOBLOX_DNS_SOURCE = "Infoblox"
			INFOBLOX_RECORD_PREFIXES = (
				"networkcontainer,", "network,", "ipv6networkcontainer,", "ipv6network,",
				"hostrecord,", "hostaddress,", "fixedaddress,", "arecord,", "ptrrecord,",
			)

			def split_infoblox_fqdn(fqdn):
				fqdn = (fqdn or "").strip().rstrip(".")
				if not fqdn:
					return "", ""
				domain = "oslo.kommune.no"
				suffix = "." + domain
				if fqdn.endswith(suffix):
					return fqdn[:-len(suffix)], domain
				if fqdn == domain:
					return "", domain
				return fqdn, ""

			def field_or_none(decoded_line, key):
				if key not in decoded_line:
					return None
				value = decoded_line[key]
				if value is None or value == "":
					return None
				return value

			def upsert_infoblox_host(network_ip, record_type, fqdn, decoded_line, mac_address=None):
				fqdn = (fqdn or "").strip()
				defaults = {
					"mac_address": mac_address or field_or_none(decoded_line, "mac_address"),
					"comment": field_or_none(decoded_line, "comment"),
					"disabled": decoded_line.get("disabled") == "True",
					"locationid": field_or_none(decoded_line, "EA-LokasjonsID"),
					"orgname": field_or_none(decoded_line, "EA-ORG-navn"),
					"equipment_label": field_or_none(decoded_line, "EA-Utstyrsbetegnelse"),
					"vrfname": field_or_none(decoded_line, "EA-VRF-navn"),
					"netcategory": field_or_none(decoded_line, "EA-net-kategori"),
					"interface_label": field_or_none(decoded_line, "EA-interface"),
				}
				ih, created = InfobloxHost.objects.get_or_create(
					network_ip=network_ip,
					record_type=record_type,
					fqdn=fqdn,
					defaults=defaults,
				)
				if not created:
					for attr, value in defaults.items():
						setattr(ih, attr, value)
					ih.save()
				return created

			def upsert_infoblox_dns(dns_name, dns_type, ip_address, ttl, dns_domain):
				if not dns_name:
					return 0
				try:
					dns_inst = DNSrecord.objects.get(
						dns_name=dns_name,
						dns_type=dns_type,
						source=INFOBLOX_DNS_SOURCE,
					)
					dns_inst.ip_address = ip_address
					dns_inst.ttl = ttl
					dns_inst.dns_domain = dns_domain or ""
					dns_inst.save()
					created = 0
				except DNSrecord.DoesNotExist:
					dns_inst = DNSrecord.objects.create(
						dns_name=dns_name,
						dns_type=dns_type,
						source=INFOBLOX_DNS_SOURCE,
						ip_address=ip_address,
						ttl=ttl,
						dns_domain=dns_domain or "",
					)
					created = 1

				ipaddr_ins = get_ipaddr_instance(ip_address)
				if ipaddr_ins is not None and dns_inst not in ipaddr_ins.dns.all():
					ipaddr_ins.dns.add(dns_inst)
				return created

			@transaction.atomic
			def import_infoblox(destination_file, logmessage, filename):

				vlan_dropped = 0
				vlan_new = 0
				vlan_deaktivert = 0
				host_new = 0
				dns_new = 0

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
								return (zone["Sikkerhetsnivå"], zone["Beskrivelse"])

					return (None, None)

				def prefixlen(ip, netmask):
					i = ipaddress.ip_address(ip)
					network = ip + "/" + netmask
					if isinstance(i, ipaddress.IPv4Address):
						network = ipaddress.IPv4Network(network)
					else:
						network = ipaddress.IPv6Network(network)
					return network.prefixlen

				def apply_network_eas(nc, decoded_line, is_ipv4):
					nc.comment = decoded_line.get("comment") or None
					nc.locationid = field_or_none(decoded_line, "EA-LokasjonsID")
					nc.orgname = field_or_none(decoded_line, "EA-ORG-navn")
					nc.vlanid = field_or_none(decoded_line, "EA-VLAN")
					nc.vrfname = field_or_none(decoded_line, "EA-VRF-navn")
					nc.netcategory = field_or_none(decoded_line, "EA-net-kategori")
					nc.vlan_name = field_or_none(decoded_line, "EA-VLAN-navn")
					nc.location_name = field_or_none(decoded_line, "EA-Lokasjon")
					nc.ip_helper = field_or_none(decoded_line, "EA-IP-helper")
					if is_ipv4:
						nc.network_zone, nc.network_zone_description = identity_security_zone(nc.ip_address)
					if decoded_line.get("disabled") == "True":
						nc.disabled = True

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
				antall_hostrecord = 0
				antall_hostaddress = 0
				antall_fixedaddress = 0
				antall_arecord = 0
				antall_ptrrecord = 0
				current_header = None

				for line in data:

					if line.startswith("header-"):
						current_header = line
						continue

					if current_header is None:
						continue

					if not line.startswith(INFOBLOX_RECORD_PREFIXES):
						continue

					decoded_line = list(csv.DictReader(StringIO(f"{current_header}\n{line}"), delimiter=","))[0]
					antall_records += 1

					if line.startswith(("networkcontainer,", "network,", "ipv6networkcontainer,", "ipv6network,")):
						if line.startswith("networkcontainer,"):
							antall_networkcontainer += 1
						if line.startswith("network,"):
							antall_network += 1
						if line.startswith("ipv6networkcontainer,"):
							antall_ipv6networkcontainer += 1
						if line.startswith("ipv6network,"):
							antall_ipv6network += 1

						if "netmask*" in decoded_line:
							if decoded_line["address*"] == "" or decoded_line["netmask*"] == "":
								vlan_dropped += 1
								continue
							subnetint = prefixlen(decoded_line["address*"], decoded_line["netmask*"])
							is_ipv4 = True
						elif "cidr*" in decoded_line:
							if decoded_line["address*"] == "" or decoded_line["cidr*"] == "":
								vlan_dropped += 1
								continue
							subnetint = prefixlen(decoded_line["address*"], decoded_line["cidr*"])
							is_ipv4 = False
						else:
							vlan_dropped += 1
							continue

						try:
							nc = NetworkContainer.objects.get(ip_address=decoded_line["address*"], subnet_mask=subnetint)
						except NetworkContainer.DoesNotExist:
							nc = NetworkContainer.objects.create(
								ip_address=decoded_line["address*"],
								subnet_mask=subnetint,
							)
							vlan_new += 1

						apply_network_eas(nc, decoded_line, is_ipv4)
						if decoded_line.get("disabled") == "True":
							vlan_deaktivert += 1

						if write_mode:
							nc.save()
						continue

					if line.startswith("hostrecord,"):
						antall_hostrecord += 1
						fqdn = field_or_none(decoded_line, "fqdn*")
						addresses = decoded_line.get("addresses") or ""
						if not fqdn or not addresses.strip():
							vlan_dropped += 1
							continue
						for ip_str in addresses.split(","):
							ip_str = ip_str.strip()
							if not ip_str:
								continue
							network_ip = get_ipaddr_instance(ip_str)
							if network_ip is None:
								vlan_dropped += 1
								continue
							if upsert_infoblox_host(network_ip, "hostrecord", fqdn, decoded_line):
								host_new += 1
						continue

					if line.startswith("hostaddress,"):
						antall_hostaddress += 1
						ip_str = field_or_none(decoded_line, "address*")
						fqdn = field_or_none(decoded_line, "parent*")
						if not ip_str:
							vlan_dropped += 1
							continue
						network_ip = get_ipaddr_instance(ip_str)
						if network_ip is None:
							vlan_dropped += 1
							continue
						if upsert_infoblox_host(network_ip, "hostaddress", fqdn or "", decoded_line):
							host_new += 1
						continue

					if line.startswith("fixedaddress,"):
						antall_fixedaddress += 1
						ip_str = field_or_none(decoded_line, "ip_address*")
						if not ip_str:
							vlan_dropped += 1
							continue
						network_ip = get_ipaddr_instance(ip_str)
						if network_ip is None:
							vlan_dropped += 1
							continue
						fqdn = field_or_none(decoded_line, "name") or ""
						if upsert_infoblox_host(network_ip, "fixedaddress", fqdn, decoded_line):
							host_new += 1
						continue

					if line.startswith("arecord,"):
						antall_arecord += 1
						ip_str = field_or_none(decoded_line, "address*")
						fqdn = field_or_none(decoded_line, "fqdn*")
						if not ip_str or not fqdn:
							vlan_dropped += 1
							continue
						dns_name, dns_domain = split_infoblox_fqdn(fqdn)
						if not dns_name and dns_domain:
							dns_name = fqdn
						ttl = field_or_none(decoded_line, "ttl")
						ttl = int(ttl) if ttl is not None else None
						dns_new += upsert_infoblox_dns(dns_name, "A record", ip_str, ttl, dns_domain)
						continue

					if line.startswith("ptrrecord,"):
						antall_ptrrecord += 1
						ip_str = field_or_none(decoded_line, "address")
						dns_name = field_or_none(decoded_line, "fqdn") or field_or_none(decoded_line, "dname*")
						if not ip_str or not dns_name:
							vlan_dropped += 1
							continue
						ttl = field_or_none(decoded_line, "ttl")
						ttl = int(ttl) if ttl is not None else None
						dns_new += upsert_infoblox_dns(dns_name, "PTR", ip_str, ttl, "")
						continue

				int_config.elementer = int(antall_records)
				logg_entry_message = (
					f'Fant {antall_records} Infoblox-rader i {filename}. '
					f'Nettverk: {antall_networkcontainer} IPv4 containere, {antall_network} IPv4 nett, '
					f'{antall_ipv6networkcontainer} IPv6 containere, {antall_ipv6network} IPv6 nettverk '
					f'({vlan_new} nye, {vlan_dropped} droppet, {vlan_deaktivert} deaktiverte). '
					f'Host: {antall_hostrecord} hostrecord, {antall_hostaddress} hostaddress, '
					f'{antall_fixedaddress} fixedaddress ({host_new} nye). '
					f'DNS: {antall_arecord} A, {antall_ptrrecord} PTR ({dns_new} nye).'
				)
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
			message = import_infoblox(destination_infoblox_data, "Infoblox", infoblox_data)

			print(f"Sletter gamle innslag..")
			for_gammelt = timezone.now() - timedelta(hours=IMPORT_CLEANUP_MIN_AGE_HOURS)
			for model, label in (
				(NetworkContainer, "nettverk"),
				(InfobloxHost, "Infoblox-host"),
			):
				ikke_oppdatert = model.objects.filter(sist_oppdatert__lte=for_gammelt)
				batch_size = 500
				while ikke_oppdatert.count():
					ids = ikke_oppdatert.values_list('pk', flat=True)[:batch_size]
					ikke_oppdatert.filter(pk__in=ids).delete()
					print(f"Slettet batch på {batch_size} gamle {label}..")

			gamle_infoblox_dns = DNSrecord.objects.filter(
				source=INFOBLOX_DNS_SOURCE,
				sist_oppdatert__lte=for_gammelt,
			)
			antall_slettet_dns = gamle_infoblox_dns.count()
			if antall_slettet_dns:
				gamle_infoblox_dns.delete()
				print(f"Slettet {antall_slettet_dns} gamle Infoblox DNS-rader..")

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

