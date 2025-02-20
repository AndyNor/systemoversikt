# -*- coding: utf-8 -*-
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
import json, os, time
import pandas as pd
import numpy as np

### Er denne i bruk? ###

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_database_mssql_size"
		LOG_EVENT_TYPE = "CMDB database size import"
		KILDE = "Manuelt uttrekk"
		PROTOKOLL = "E-post"
		BESKRIVELSE = "Størrelse på MSSQL-databaser"
		FILNAVN = "A34 - Database - Status and size.xlsx"
		URL = ""
		FREKVENS = "Månedlig"

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

			from systemoversikt.views import sharepoint_get_file
			source_filepath = f"{FILNAVN}"
			result = sharepoint_get_file(source_filepath)
			destination_file = result["destination_file"]
			modified_date = result["modified_date"]
			print(f"Filen er datert {modified_date}")

			@transaction.atomic
			def import_cmdb_database_size():

				db_dropped = 0
				feilede_oppslag = 0

				# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
				import warnings
				warnings.simplefilter("ignore")
				dfRaw = pd.read_excel(destination_file, skiprows=2)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				data = dfRaw.to_dict('records')

				antall_records = len(data)

				def size_str_to_bytes(data):
					if data == "":
						return 0
					value = float(data.split()[0])
					order = data[-2:]
					#print("%s %s" % (value, order))
					if order == "KB":
						return value * 1000
					if order == "MB":
						return value * 1000 * 1000
					if order == "GB":
						return value * 1000 * 1000 * 1000
					if order == "TB":
						return value * 1000 * 1000 * 1000 * 1000
					return 0

				antall_unmanaged = 0

				for line in data:
					if line["Status"] == "Unmanaged":
						antall_unmanaged += 1
						continue

					try:
						db_server = line["Server Name"].replace(".oslofelles.oslo.kommune.no", "")
						db_database = line["Name"]
						db = CMDBdatabase.objects.get(db_database__iexact=db_database, db_server__iexact=db_server)
					except:
						#print("Fant ikke databasen %s" % line["Name"])
						feilede_oppslag += 1
						continue

					#print("%s %s" % (db_server, db_database))
					old_size = db.db_u_datafilessizekb
					new_size = int(size_str_to_bytes(line["Database Size"]) + size_str_to_bytes(line["Transaction Log Size"]))
					db.db_u_datafilessizekb = new_size
					db.save()
					#print("Oppdaterte %s fra %s til %s bytes" % (db_database, old_size, new_size))
					#print("%s %s %s %s" % (line["Name"], line["Operational State"], line["Database Size"], line["Transaction Log Size"]))


				logg_entry_message = f'Fant {antall_records} databaser. {antall_unmanaged} er "unmanaged". {feilede_oppslag} feilet oppslag mot eksisterende database'
				logg_entry = ApplicationLog.objects.create(
						event_type=LOG_EVENT_TYPE,
						message=logg_entry_message,
					)
				print(logg_entry_message)
				return logg_entry_message

			#eksekver
			logg_entry_message = import_cmdb_database_size()

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = modified_date
			int_config.sist_status = logg_entry_message
			runtime_t1 = time.time()
			logg_total_runtime = int(runtime_t1 - runtime_t0)
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

