# -*- coding: utf-8 -*-
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from systemoversikt.models import *
from django.core.management.base import BaseCommand
from django.db import transaction
import json, os
import pandas as pd
import numpy as np
from django.db.models import Q
from systemoversikt.views import get_ipaddr_instance
from functools import lru_cache
import warnings

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_qualys"
		LOG_EVENT_TYPE = "Qualys import"
		KILDE = "PowerBI"
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

		from systemoversikt.views import sharepoint_get_file

		source_filepath = FILNAVN
		result = sharepoint_get_file(source_filepath)
		destination_file = result["destination_file"]
		destination_file_modified_date = result["modified_date"]
		print(f"Filen er datert {destination_file_modified_date}")

		# tømme alle gamle innslag og starte på nytt
		QualysVuln.objects.all().delete()



		@lru_cache(maxsize=384)
		def lookup_server(servername):
			try:
				server = CMDBdevice.objects.get(comp_name=line["servername"])
				return server
			except:
				return None


		@transaction.atomic
		def save_to_database(data):
			processed = 0
			for line in data:
				try:
					int(line['ID'])
				except:
					continue # Det må være en gyldig ID i denne kolonnen

				if line["Status"] != "Fixed": # dropper de som er rettet

					source = f"{line['Hostname']} {line['IP']}"
					processed += 1

					q = QualysVuln.objects.create(
							source=source,
							title=line['Title'],
							severity=int(line['Severity']),
							first_seen=line['First detected'],
							last_seen=line['Last detected'],
							pulic_facing=line['Public Facing'],
							cve_info=line['CVE ID'],
							result=line['Results'],
							os=line['OS'],
							status=line['Status'],
						)

					server = lookup_server(line["Hostname"])
					if server:
						q.server = server
						q.save()

			return processed


		def import_qualys():

			print("Åpner filen...")
			warnings.simplefilter("ignore")
			dfRaw = pd.read_excel(destination_file)
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			data = dfRaw.to_dict('records')

			split_size = 5000
			antall_totalt = 0

			for i in range(0, len(data), split_size):
				antall_totalt += save_to_database(data[i:i + split_size])
				print(f"Ferdig med {antall_totalt}")

			logg_entry_message = f'utført'
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_entry_message,
				)
			print(logg_entry_message)
			return logg_entry_message


		# eksekvere
		logg_entry_message = import_qualys()


		# logge resultatet
		int_config.dato_sist_oppdatert = destination_file_modified_date # eller timezone.now()
		int_config.sist_status = logg_entry_message
		int_config.save()


