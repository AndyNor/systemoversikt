# -*- coding: utf-8 -*-
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
from django.db import transaction
import json, os, time
import pandas as pd
import numpy as np
from django.db.models import Q
import ipaddress
from functools import lru_cache
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_firewall"
		LOG_EVENT_TYPE = "Brannmurimport"
		KILDE = "Cisco ASA"
		PROTOKOLL = "SharePoint"
		BESKRIVELSE = "Brannmurregler og brannmurgrupper"
		FILNAVN = "firewall_2023-05-24.xlsx"
		URL = ""
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
		int_config.helsestatus = "Forbereder"
		int_config.save()

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
		runtime_t0 = time.time()

		try:

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

			from systemoversikt.views import sharepoint_get_file
			source_filepath = f"{FILNAVN}"
			result = sharepoint_get_file(source_filepath)
			destination_file = result["destination_file"]
			modified_date = result["modified_date"]
			print(f"Filen er datert {modified_date}")

			#debug = []

			def erstatte_grupper_med_ipadresser(adresser, oppslagsverk):
				# bare slå opp dersom det er noe annet enn et nettverk eller en ip-adresse
				nye_adresser = set()
				for a in adresser:

					a = a.strip()
					#print(f"-{a}-")

					if a in ["All-IPv4-Addresses", "All-Addresses", "All-IPv6-Addresses"]:
						nye_adresser.add(a)  # legger tilbake som den var
						continue
					try:
						ipaddress.ip_network(a)
						nye_adresser.add(a)  # legger tilbake som den var
						# hvis dette er et nettverk, gå til neste adresse
						continue
					except ValueError:
						pass # hvis ikke, fortsett
					try:
						ipaddress.ipaddress(a)
						nye_adresser.add(a)  # legger tilbake som den var
						# dette er en ipadresse, gå til neste adresse
						continue
					except:
						# det er hverken et nettverk eller ip-adresse, erstatt ved oppslag
						try:
							oppslag = oppslagsverk[a]
							#print(oppslag)
							for element in oppslag:
								nye_adresser.add(element)
							#print(f"erstatte_grupper_med_ipadresser() fant oppslag for {a}")
							continue
						except:
							nye_adresser.add(a)  # legger tilbake som den var
							#print(f"erstatte_grupper_med_ipadresser() feilet oppslag for {a}")
							#print(f"*** feilet oppslag mot navngitt ipgruppe {a}")

				return list(nye_adresser)


			def erstatte_portgrupper(data, oppslagsverk):
				nye_data = set()
				for p in data:
					if p in ["IP"]:
						nye_data.add("Alle porter (all IP)")
						continue
					try:
						oppslag = oppslagsverk[p]
						for element in oppslag:
							nye_data.add(element)
						continue
					except:
						nye_data.add(p)  # legger tilbake som den var
				return list(nye_data)


			def parse_firewall_port_groups(excel_file, sheet):
				print("Klargjør navngitte porter")
				named_groups = {}
				df = excel_file.parse(sheet,
						skiprows=0, # hvis de første radene er tomme
					)
				for index, row in df.iterrows():
					alias = row["Name"]
					description = row["Description"]
					try:
						named_groups[alias] = [s + " " + description for s in row["Content"].split(",")]
					except:
						print(f"* kunne ikke lese inn {alias} med verdi {description}")
						pass
						#debug.append(f"* kunne ikke lese inn {alias} med verdi {value}")
				return named_groups


			def parse_firewall_named_groups(excel_file, sheet):
				print("Klargjør navngitte nettverk")
				named_groups = {}

				df = excel_file.parse(sheet,
							skiprows=0, # hvis de første radene er tomme
						)

				#for column in df.columns:
				#	if not column.startswith("Unnamed"):
				#		named_groups[column] = df[column].dropna().tolist()#.to_dict('list')

				for index, row in df.iterrows():
					#print(type(row["Content"]))
					#print(row["Content"])
					alias = row["Name"]
					value = row["Content"]
					try:
						named_groups[alias] = value.split(",")
					except:
						#print(f"* kunne ikke lese inn {alias} med verdi {value}")
						#debug.append(f"* kunne ikke lese inn {alias} med verdi {value}")
						pass

				#utvide (expand) alle grupper slik at en gruppe ikke inneholder en annen gruppereferanse
				expanded_named_groups = []
				for ng in named_groups:
					#print(ng)
					named_groups[ng] = erstatte_grupper_med_ipadresser(named_groups[ng], named_groups)

				for el in named_groups:
					#debug.append(f"* {el} {named_groups[el]}")
					pass

				return named_groups


			def parse_target(target):
				if type(target) == int:
					try:
						n = str(target)
						if len(n) == 10:
							return "%s.%s.%s.%s" % (n[-10:-9], n[-9:-6], n[-6:-3], n[-3:])
						if len(n) == 11:
							return "%s.%s.%s.%s" % (n[-11:-9], n[-9:-6], n[-6:-3], n[-3:])
						if len(n) == 12:
							return "%s.%s.%s.%s" % (n[-12:-9], n[-9:-6], n[-6:-3], n[-3:])
					except:
						return target

				else:
					return target


			# klargjøre cachet data for nettverk
			cmdb_networks_buffer = {}
			all_cmdb_networks = NetworkContainer.objects.all().values("ip_address", "subnet_mask", "pk", "comment")
			for item in all_cmdb_networks:
				network = ("%s/%s") % (str(item["ip_address"]), item["subnet_mask"])
				if not network in cmdb_networks_buffer:
					cmdb_networks_buffer[network] = {"pk": item["pk"], "comment": item['comment']}
				else:
					print(f"Nettverk {network} kunne ikke legges til flere ganger")
					continue
			#print(cmdb_networks_buffer)

			@lru_cache(maxsize=512)
			def lookup_network(network):
				#return None
				try:
					#network = ipaddress.ip_network(network) # hvis dette er et nettverk..
					#nc = NetworkContainer.objects.get(ip_address=str(network.network_address), subnet_mask=network.prefixlen)
					#network_str = f"{nc.comment} ({network})"

					nc = cmdb_networks_buffer[network]
					comment = nc["comment"]
					pk = nc["pk"]
					network_str = f"{comment} ({network})"
					return {"pk": pk, "name": network_str}

				except:
					#print(f"** Oppslag feilet for nettverk {network}")
					return None



			# klargjøre cachet data for servere
			cmdb_server_buffer = {}
			all_cmdb_servers = CMDBdevice.objects.filter(device_type="SERVER") #.values("comp_ip_address", "pk", "comp_name", "tjenestenavn")
			for server in all_cmdb_servers:
				server_ip = server.comp_ip_address
				if server_ip == "":
					continue
				if not server_ip in cmdb_server_buffer:
					cmdb_server_buffer[server_ip] = {"pk": server.pk, "comp_name": server.comp_name, "sub_name": server.offering_navn()}
				else:
					#print(f"Server {server} kunne ikke legges til flere ganger")
					continue
			#print(cmdb_server_buffer)

			@lru_cache(maxsize=512)
			def lookup_device(ip_address):
				try:
					server = cmdb_server_buffer[ip_address]
					pk = server["pk"]
					comp_name = server["comp_name"]
					sub_name = server[sub_name]

					server_str = f"{comp_name} ({sub_name})"

					return {"pk": pk, "name": server_str}

				except:
					return None


			alle_viper = virtualIP.objects.all()
			@lru_cache(maxsize=512)
			def lookup_vip(ip_address):
				#return None
				try:
					ip_address = ipaddress.ip_address(ip_address)  # dette er en ipadresse..
					vip = virtualIP.objects.get(ip_address=str(ip_address))
					vip_str = vip.vip_name
					return {"pk": vip.pk, "name": vip_str}

				except (ObjectDoesNotExist, MultipleObjectsReturned):
					return None


			def oppslag_cmdb(data):
				# oppslag mot kjente nettverk
				raw_items = set()
				networks = set()
				servers = set()
				virtual_ips = set()
				#print(f"data = {data}")
				for n in data:

					#print(".", end="", flush=True)

					if n == None:
						continue

					if "/" in n: # et nettverk
						try:
							network = ipaddress.ip_network(n) # hvis dette er et nettverk,
							oppslag = lookup_network(n) # vi gjør en konvertering til nettverk i lookup_network() og ønsker å ha tilbake tekststring om den feiler
							if oppslag:
								raw_items.add(oppslag["name"])
								networks.add(oppslag["pk"])
								continue
							else:
								raw_items.add(n) # legger tilbake og fortsetter
								continue
						except:
							pass

					try:
						ip_address = ipaddress.ip_address(n)  # dette er en ipadresse..
						oppslag = lookup_device(n) # vi gjør en konvertering til ipadresse i lookup_device() og ønsker å ha tilbake tekststring om den feiler
						if oppslag:
							raw_items.add(oppslag["name"])
							servers.add(oppslag["pk"])
							continue
						else:
							pass
					except ValueError:
						pass

					try:
						ip_address = ipaddress.ip_address(n)  # dette er en ipadresse..
						oppslag = lookup_vip(ip_address) # vi gjør en konvertering til ipadresse i lookup_vip() og ønsker å ha tilbake tekststring om den feiler
						if oppslag:
							raw_items.add(oppslag["name"])
							virtual_ips.add(oppslag["pk"])
							continue
						else:
							pass
					except ValueError:
						pass

					# kommer vi så langt er det bare en string som vi må legge tilbake
					raw_items.add(n) # legger tilbake og fortsetter

				return {
					"raw_items": list(raw_items),
					"networks": list(networks),
					"servers": list(servers),
					"virtual_ips": list(virtual_ips),
					}


			# Her starter behandlingen
			filename = destination_file
			file_edit_stamp = os.path.getmtime(filename)
			file_edit_date = datetime.fromtimestamp(file_edit_stamp).strftime('%Y-%m-%d %H:%M:%S')
			print(f"Filen er fra {file_edit_date}")

			# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
			#import warnings
			#warnings.simplefilter("ignore")

			excel_file = pd.ExcelFile(filename)
			#print("Fant følgende ark i filen: %s" % excel_file.sheet_names)

			all_openings = {}

			for sheet in excel_file.sheet_names:
				print("Åpner ark %s" % sheet)

				if sheet == "README":
					#debug.append("* ingen relevante data")
					continue

				if sheet == "All FW network groups":
					named_network_groups = parse_firewall_named_groups(excel_file=excel_file, sheet=sheet)
					print("* navngitte nettverk er lastet")
					continue

				if sheet == "All FW service groups":
					named_port_groups = parse_firewall_port_groups(excel_file=excel_file, sheet=sheet)
					print("* navngitte porter er lastet")
					continue

				try:
					df = excel_file.parse(sheet,
								#skiprows=2, # de første radene er tomme
								#usecols=[2, 3, 4, 7, 9, 10, 14],
								skiprows=0, # de første radene er tomme
								usecols=[0, 1, 2, 3, 4, 6, 8],
								names=['rule_id', 'permit', 'source', 'destination', 'service', 'beskrivelse', 'enabled',]
							)
				except:
					print("* Ingen regler funnet")
					continue

				df['rule_id'].ffill(inplace=True)
				df = df.replace(np.nan, '', regex=True)
				data = df.to_dict('records')
				for line in data:
					try:
						sheet_rule_id = int(line["rule_id"])
						rule_id = f"{sheet}-{sheet_rule_id}"
					except:
						rule_id = "ID mangler"

					if not rule_id in all_openings:
						all_openings[rule_id] = {
								'firewall': sheet,
								'permit': line["permit"],
								'source': [parse_target(line["source"])],
								'destination': [parse_target(line["destination"])],
								'service': [line["service"]],
								'beskrivelse': line["beskrivelse"],
								'enabled': line["enabled"],
								}
					else:
						if line["source"] != "":
							all_openings[rule_id]["source"].append(parse_target(line["source"]))
						if line["destination"] != "":
							all_openings[rule_id]["destination"].append(parse_target(line["destination"]))
						if line["service"] != "":
							all_openings[rule_id]["service"].append(line["service"])

				print(f"* Fant {len(data)} regler")

			print(f"Det er {len(all_openings)} brannmurdefinisjoner i filen")

			# erstatte grupper med faktiske medlemmer (ip, nett og porter)
			for rule_id in all_openings:
				all_openings[rule_id]["source"] = erstatte_grupper_med_ipadresser(all_openings[rule_id]["source"], named_network_groups)
				all_openings[rule_id]["destination"] = erstatte_grupper_med_ipadresser(all_openings[rule_id]["destination"], named_network_groups)
				all_openings[rule_id]["service"] = erstatte_portgrupper(all_openings[rule_id]["service"], named_port_groups)

			# søke opp navn på vlan, servere vip-er fra databasen
			print("Søker opp kjente VLAN, servere og VIP-er fra CMDB...")
			for rule_id in all_openings:
				all_openings[rule_id]["source"] = oppslag_cmdb(all_openings[rule_id]["source"])
				all_openings[rule_id]["destination"] = oppslag_cmdb(all_openings[rule_id]["destination"])


			# lagre navngitte netterk til database
			@transaction.atomic
			def store_network_grp_to_db(named_network_groups):
				print("Sletter alle gamle navngitte nettverksgrupper i database")
				Nettverksgruppe.objects.all().delete()
				print("Lagrer til database...")
				for idx, members in named_network_groups.items():
					Nettverksgruppe.objects.create(
							name=idx,
							members=json.dumps(members),
						)
					#print(".", end="", flush=True)
				print("Lagret alle navngitte nettverksgrupper i databasen")

			# utføre lagring
			store_network_grp_to_db(named_network_groups)


			# lagre brannmurregler til database
			@transaction.atomic
			def store_to_db(all_openings):
				print("Sletter alle gamle brannmurregler i database")
				Brannmurregel.objects.all().delete()
				print("Lagrer til database...")
				for rule_id in all_openings:
					active = True if all_openings[rule_id]["enabled"] in ["Sann", True, "true"] else False
					permit = True if all_openings[rule_id]["permit"] in ["permit"] else False
					r = Brannmurregel.objects.create(
							regel_id=rule_id,
							brannmur=all_openings[rule_id]["firewall"],
							active=active,
							permit=permit,
							source=json.dumps(all_openings[rule_id]["source"]["raw_items"]),
							destination=json.dumps(all_openings[rule_id]["destination"]["raw_items"]),
							protocol=json.dumps(all_openings[rule_id]["service"]),
							comment=all_openings[rule_id]["beskrivelse"],
						)

					if all_openings[rule_id]["source"]["virtual_ips"] != None:
						r.ref_vip.add(*all_openings[rule_id]["source"]["virtual_ips"])

					if all_openings[rule_id]["source"]["servers"] != None:
						r.ref_server.add(*all_openings[rule_id]["source"]["servers"])

					if all_openings[rule_id]["source"]["networks"] != None:
						r.ref_vlan.add(*all_openings[rule_id]["source"]["networks"])

					if all_openings[rule_id]["destination"]["networks"] != None:
						r.ref_vip.add(*all_openings[rule_id]["destination"]["virtual_ips"])

					if all_openings[rule_id]["destination"]["networks"] != None:
						r.ref_server.add(*all_openings[rule_id]["destination"]["servers"])

					if all_openings[rule_id]["destination"]["networks"] != None:
						r.ref_vlan.add(*all_openings[rule_id]["destination"]["networks"])

					#print(".", end="", flush=True)
				print("Lagret alle brannmurregler i databasen")

			# utføre lagring
			store_to_db(all_openings)

			logg_message = f"Ferdig med import. {len(all_openings)} regler ble importert."
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = modified_date
			int_config.sist_status = logg_message
			int_config.elementer = int(len(all_openings))
			runtime_t1 = time.time()
			int_config.runtime = int(runtime_t1 - runtime_t0)
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


