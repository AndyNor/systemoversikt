# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from systemoversikt.models import *
from django.db import transaction
import json, os, time
import pandas as pd
import numpy as np
from django.db.models import Q
from systemoversikt.views import get_ipaddr_instance
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_lastbalansering"
		LOG_EVENT_TYPE = "CMDB VIP import"
		KILDE = "Service Now"
		PROTOKOLL = "SMTP og SharePoint"
		BESKRIVELSE = "Ekstern og intern IP-adresse, navn på VIP og tilhørende pool med servere"
		FILNAVN = {"filename_vip": "OK Load Balancer Services with servers.csv", "filename_pool": "OK Load Balancer Pool Members.csv"}
		URL = ""
		FREKVENS = "Hver natt"

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
		runtime_t0 = time.time()

		try:

			filename_vip = FILNAVN["filename_vip"]
			filename_pool = FILNAVN["filename_pool"]

			from systemoversikt.views import sharepoint_get_file
			source_filepath = f"{filename_vip}"
			result = sharepoint_get_file(source_filepath)
			vip_destination_file = result["destination_file"]
			vip_modified_date = result["modified_date"]
			print(f"Filen er datert {vip_modified_date}")


			from systemoversikt.views import sharepoint_get_file
			source_filepath = f"{filename_pool}"
			result = sharepoint_get_file(source_filepath)
			pool_destination_file = result["destination_file"]
			pool_modified_date = result["modified_date"]
			print(f"Filen er datert {pool_modified_date}")

			logg_entry_message = ""

			@transaction.atomic
			def import_vip():

				vip_dropped = 0
				vip_new = 0

				import csv
				with open(vip_destination_file, 'r', encoding='latin-1') as file:
					data = list(csv.DictReader(file, delimiter=","))

				antall_records = len(data)

				for line in data:
					try:
						vip_inst = virtualIP.objects.get(vip_name=line["u_load_balancer_service_1"])
						vip_inst.pool_name = line["u_load_balancer_service_1.pool"]
						vip_inst.ip_address = line["u_load_balancer_service_1.ip_address"]
						vip_inst.port = line["u_load_balancer_service_1.port"]
						vip_inst.hitcount = line["u_load_balancer_service_1.hit_count"].replace(",","")
						vip_inst.save()
						vip_dropped += 1
						#print("u", end="", flush=True)

					except ObjectDoesNotExist:
						# finnes ikke, oppretter ny
						vip_inst = virtualIP.objects.create(
							vip_name=line["u_load_balancer_service_1"],
							pool_name=line["u_load_balancer_service_1.pool"],
							ip_address=line["u_load_balancer_service_1.ip_address"],
							port=line["u_load_balancer_service_1.port"],
							hitcount=line["u_load_balancer_service_1.hit_count"].replace(",",""),
						)
						vip_new += 1
						#print("+", end="", flush=True)


					# Linke IP-adresse
					ipaddr_ins = get_ipaddr_instance(line["u_load_balancer_service_1.ip_address"])
					if ipaddr_ins != None:
						if not vip_inst in ipaddr_ins.viper.all():
							ipaddr_ins.viper.add(vip_inst)
							ipaddr_ins.save()

				logg_entry_message = 'Fant %s VIP-er i %s. %s nye og %s eksisterende.' % (
						antall_records,
						filename_vip,
						vip_new,
						vip_dropped,
					)
				logg_entry = ApplicationLog.objects.create(
						event_type=LOG_EVENT_TYPE,
						message=logg_entry_message,
					)
				print(logg_entry_message)
				return logg_entry_message

			#eksekver
			print(f"Importerer VIP-data..")
			logg_entry_message += import_vip()



			# VIP-pool data
			@transaction.atomic
			def import_pool():

				pool_dropped = 0
				pool_new = 0
				pool_not_connected = 0

				import csv
				with open(pool_destination_file, 'r', encoding='latin-1') as file:
					data = list(csv.DictReader(file, delimiter=","))

				if data == None:
					return

				antall_records = len(data)

				for idx, line in enumerate(data):
					if idx % 500 == 0:
						print(f"{idx} av {len(data)}")

					if line["u_load_balancer_pool_member_1.pool"] == "" or line["u_load_balancer_pool_member_1.ip_address"] == "" or line["u_load_balancer_pool_member_1.service_port"] == "":
						continue
					try:
						pool = VirtualIPPool.objects.get(
								pool_name=line["u_load_balancer_pool_member_1.pool"],
								port=line["u_load_balancer_pool_member_1.service_port"],
								ip_address=line["u_load_balancer_pool_member_1.ip_address"]
							)
						#print(".", end="", flush=True)
						pool_dropped += 1
					except:
						pool = VirtualIPPool.objects.create(
								pool_name=line["u_load_balancer_pool_member_1.pool"],
								port=line["u_load_balancer_pool_member_1.service_port"],
								ip_address=line["u_load_balancer_pool_member_1.ip_address"],
							)
						#print("+", end="", flush=True)

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
						#print("p", end="", flush=True)
					except:
						pool_not_connected += 1
						#print("?", end="", flush=True)
						pass

					try:
						pool.server = CMDBdevice.objects.get(comp_ip_address=line["u_load_balancer_pool_member_1.ip_address"])
						#print("s", end="", flush=True)
					except:
						#print("?", end="", flush=True)
						pass

					pool.save()

				logg_entry_message = 'Fant %s pools i %s. %s nye. %s unike. %s mangler VIP-knytning.' % (
						antall_records,
						filename_pool,
						pool_new,
						pool_dropped,
						pool_not_connected,
					)
				logg_entry = ApplicationLog.objects.create(
						event_type=f'{LOG_EVENT_TYPE} pools',
						message=logg_entry_message,
					)
				#print("\n")
				print(logg_entry_message)
				return logg_entry_message

			#eksekver
			print(f"Importerer pool-data..")
			logg_entry_message += import_pool()

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = vip_modified_date # eller timezone.now()
			int_config.sist_status = logg_entry_message
			runtime_t1 = time.time()
			int_config.runtime = int(runtime_t1 - runtime_t0)
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