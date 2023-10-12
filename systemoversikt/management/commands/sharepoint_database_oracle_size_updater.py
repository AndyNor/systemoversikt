# -*- coding: utf-8 -*-
from django.utils import timezone
from datetime import timedelta
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
from systemoversikt.models import *
from django.db import transaction
import os
import re
import json, os
import pandas as pd
import numpy as np
from django.db.models import Q


class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_database_oracle_size"
		LOG_EVENT_TYPE = "CMDB database import (Oracle size)"
		KILDE = "ServiceNow"
		PROTOKOLL = "SMTP og SharePoint"
		BESKRIVELSE = "Informasjon om Oracle-databaser og deres størrelser."
		FILNAVN = "oracle_database_size.xlsx"
		URL = ""
		FREKVENS = "Manuelt en gang per måned"

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

		print(f"------------\nStarter {SCRIPT_NAVN}")

		try:

			from systemoversikt.views import sharepoint_get_file
			source_filepath = f"/sites/74722/Begrensede-dokumenter/{FILNAVN}"
			result = sharepoint_get_file(source_filepath)
			destination_file = result["destination_file"]
			modified_date = result["modified_date"]
			print(f"Filen er datert {modified_date}")

			dfRaw = pd.read_excel(destination_file, sheet_name='IS')
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			oracle_size_ez = dfRaw.to_dict('records')

			dfRaw = pd.read_excel(destination_file, sheet_name='SS')
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			oracle_size_is = dfRaw.to_dict('records')

			oracle_sizes = oracle_size_ez + oracle_size_is

			antall_endret = 0
			antall_ingen_endring = 0
			antall_feilet = 0
			feilet_for = []

			database_size_not_found = []
			for idx, record in enumerate(oracle_sizes):
				import_databasenavn = record["DATABASE NAME"].strip()
				import_server = record["DATABASE SERVER"].strip().split(".")[0]
				try:
					dbinstance = CMDBdatabase.objects.get(db_database=import_databasenavn,db_server=import_server)
				except:
					#print(f"No matching database with name {import_databasenavn} for server {import_server}")
					antall_feilet += 1
					feilet_for.append("%s@%s" % (import_databasenavn, import_server))
					continue

				new_size = int(record["DATABASE SIZE"] * 1000 * 1000 * 1000)
				old_size = dbinstance.db_u_datafilessizekb
				if old_size != new_size:
					dbinstance.db_u_datafilessizekb = new_size
					dbinstance.save()
					#print(f"Oppdaterte størrelse på {import_databasenavn}@{import_server} fra {old_size} til {new_size}")
					antall_endret += 1
				else:
					#print(f"Ingen endring på {import_databasenavn}")
					antall_ingen_endring += 1


			logg_entry_message = f"Oppdaterte størrelser på Orcale-databaser. {antall_endret} endret. {antall_ingen_endring} som før. {antall_feilet} oppslag feilet: {feilet_for}"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_entry_message,
				)
			print(f"{logg_entry_message}")

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = modified_date
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
