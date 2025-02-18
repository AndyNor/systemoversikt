# -*- coding: utf-8 -*-
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from systemoversikt.models import *
from django.core.management.base import BaseCommand
from django.db import transaction
import json, os, time
import pandas as pd
import numpy as np
from django.db.models import Q
from functools import lru_cache
import warnings

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_qualys"
		LOG_EVENT_TYPE = "Qualys import"
		KILDE = "Qualys via PowerBI"
		PROTOKOLL = "Manuelt uttrekk og SharePoint"
		BESKRIVELSE = "Sårbarheter fra Qualys dashboard"
		FILNAVN = "qualys.xlsx"
		URL = ""
		FREKVENS = "Manuell"

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

			runtime_t0 = time.time()
			from systemoversikt.views import sharepoint_get_file

			source_filepath = FILNAVN
			result = sharepoint_get_file(source_filepath)
			destination_file = result["destination_file"]
			destination_file_modified_date = result["modified_date"]
			print(f"Filen er datert {destination_file_modified_date}")

			# tømme alle gamle innslag og starte på nytt
			QualysVuln.objects.all().delete()


			def ansvar_basisdrift(vulnerability):

				"""
				patches_av_drift = [
						"Splunk Universal Forwarder",
						"Microsoft Azure Connected Machine Agent",
						"Windows Server Security Update for",
						"Transport Layer Security (TLS) ciphers",
						"Microsoft Windows Security Update Registry Key Configuration Missing",
						"SMB Signing",
						"Cached Logon Credential",
						"Microsoft Edge",
						"AutoPlay Not Disabled",
						"Citrix Workspace App",
						"VMware Tools",
						"Allowed Null Session",
						"Microsoft Internet Explorer Cumulative Security Update",
						"Rocky Linux Security Update for kernel",
						"Red Hat Update for",
					]
				"""
				patches_av_drift = QualysVulnBasisPatching.objects.all()
				for basispatch in patches_av_drift:
					if basispatch.title.lower() in vulnerability.title.lower():
						return {"basispatch": True, "akseptert": basispatch.akseptert}
				return {"basispatch": False, "akseptert": False}


			ALL_EXPLOITED_CVES = list(ExploitedVulnerability.objects.values_list('cve_id', flat=True))

			@lru_cache(maxsize=384)
			def lookup_server(servername):
				try:
					return CMDBdevice.objects.get(comp_name__iexact=servername)
				except:
					return None

			@lru_cache(maxsize=64)
			def lookup_ip(ip):
				matches = CMDBdevice.objects.filter(comp_ip_address__iexact=ip)
				if len(matches) < 1:
					return None
				if len(matches) > 1:
					print(f"Det er flere treff på {ip}, velger den første")
				return matches[0]


			@transaction.atomic
			def save_to_database(data):
				processed = 0
				fixed = 0
				failed_server_lookups = 0
				for line in data:
					try:
						item_id = int(line['ID'])
					except:
						item_id = None
					if not item_id:
						continue

					if line["Status"] == "Fixed": # dropper de som er rettet
						fixed += 1
						continue

					source = f"{line['Hostname']} {line['IP']}"
					processed += 1

					q = QualysVuln.objects.create(
							source=source,
							title=line['Title'],
							severity=int(line['Severity']),
							first_seen=line['First detected'],
							last_seen=line['Last detected'],
							public_facing=line['Public Facing'],
							cve_info=line['CVE ID'],
							result=line['Results'],
							os=line['OS'],
							status=line['Status'],
						)

					ab = ansvar_basisdrift(q)
					q.ansvar_basisdrift = ab["basispatch"]
					q.akseptert = ab["akseptert"]

					server = lookup_server(line["Hostname"])
					if not server:
						server = lookup_ip(line["IP"])
					if not server:
						failed_server_lookups += 1
						serer = None
					q.server = server

					# sette known exploited
					for cve in q.cve_info.split(","):
						if cve in ALL_EXPLOITED_CVES:
							q.known_exploited = True

					q.save()

				return (processed, failed_server_lookups, fixed)


			def import_qualys():

				print("Åpner filen...")
				warnings.simplefilter("ignore")
				dfRaw = pd.read_excel(destination_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				data = dfRaw.to_dict('records')

				linjer_kilde = len(data)
				split_size = 1000
				antall_totalt = 0
				failed_server_lookups = 0
				antall_fixed = 0

				for i in range(0, len(data), split_size):
					return_data = save_to_database(data[i:i + split_size])
					antall_totalt += return_data[0]
					failed_server_lookups += return_data[1]
					antall_fixed += return_data[2]
					print(f"Processing batch {i}-{i+split_size}/{linjer_kilde}. Saved {antall_totalt} vulnerabilities, where {failed_server_lookups} failed server match and {antall_fixed} was fixed and not saved")

				int_config.elementer = int(antall_totalt)
				logg_entry_message = f'\nDone importing {antall_totalt} vulnerabilities, where {failed_server_lookups} of them failed server lookup'
				logg_entry = ApplicationLog.objects.create(
						event_type=LOG_EVENT_TYPE,
						message=logg_entry_message,
					)
				print(logg_entry_message)
				return logg_entry_message


			# eksekvere
			logg_entry_message = import_qualys()


			# logge resultatet
			runtime_t1 = time.time()
			logg_total_runtime = int(runtime_t1 - runtime_t0)
			int_config.dato_sist_oppdatert = destination_file_modified_date # eller timezone.now()
			int_config.sist_status = logg_entry_message
			int_config.runtime = logg_total_runtime
			int_config.save()

		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			push_pushover(f"{SCRIPT_NAVN} feilet") # Push error



