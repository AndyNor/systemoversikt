# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from systemoversikt.views import push_pushover
from django.db import transaction
import json, os
import pandas as pd
import numpy as np
from django.db.models import Q

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_database_mssql"
		LOG_EVENT_TYPE = "CMDB database import"
		KILDE = "Manuelt uttrekk"
		PROTOKOLL = "SMTP og SharePoint"
		BESKRIVELSE = "MSSQL-databaser med tjenesteknytning"
		FILNAVN = "OK_db_sql.xlsx"
		URL = "https://soprasteria.service-now.com/"
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

		print(f"------------\nStarter {SCRIPT_NAVN}")

		try:
			from systemoversikt.views import sharepoint_get_file
			source_filepath = f"/sites/74722/Begrensede-dokumenter/{FILNAVN}"
			result = sharepoint_get_file(source_filepath)
			destination_file = result["destination_file"]
			modified_date = result["modified_date"]
			print(f"Filen er datert {modified_date}")


			@transaction.atomic
			def import_cmdb_databases():

				db_dropped = 0
				# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
				import warnings
				warnings.simplefilter("ignore")

				dfRaw = pd.read_excel(destination_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				data = dfRaw.to_dict('records')

				antall_records = len(data)
				all_existing_db = list(CMDBdatabase.objects.filter(~Q(db_version__startswith="Oracle"))) #alt som ikke er oracle og aktivt

				print("Alt lastet, oppdaterer databasen:")
				for idx, record in enumerate(data):
					#print(".", end="", flush=True)
					#if idx % 1000 == 0:
					#	print("\n%s av %s" % (idx, antall_records))

					db_name = record["Name"]
					if db_name == "":
						print(f"Database mangler navn {record}")
						db_dropped += 1
						continue  # Det må være en verdi på denne

					try:
						hostname = record["Comments"].split("@")[1]
					except:
						print("Database mangler informasjon om host (%s)" % (db_name))
						hostname = ""


					db_id = "%s@%s" % (db_name, hostname)
					# vi sjekker om databasen finnes fra før
					try:
						cmdb_db = CMDBdatabase.objects.get(Q(db_database=db_name) & Q(db_server=hostname))
						# fjerner fra oversikt over alle vi hadde før vi startet denne oppdateringen
						if cmdb_db in all_existing_db: # i tilfelle reintrodusert
							all_existing_db.remove(cmdb_db)
					except:
						# lager en ny
						cmdb_db = CMDBdatabase.objects.create(db_database=db_name, db_server=hostname)


					try:
						if hostname != "":
							cmdbdevice = CMDBdevice.objects.get(comp_name=hostname)
							cmdb_db.db_server_modelref = cmdbdevice
					except:
						cmdb_db.db_server_modelref = None

					if record["Operational status"] == "Operational":
						cmdb_db.db_operational_status = True
					else:
						cmdb_db.db_operational_status = False

					if record["Version"] != "":
						cmdb_db.db_version = "MSSQL " + record["Version"]
					else:
						cmdb_db.db_version = "MSSQL"

					try:
						filesize = int(record.get("DataFilesSizeKB", 0)) * 1000 # convert to bytes
					except:
						filesize = 0
					cmdb_db.db_u_datafilessizekb = filesize

					cmdb_db.db_used_for = record["Used for"]
					cmdb_db.db_comments = record["Comments"]
					cmdb_db.billable = record["Billable"]
					cmdb_db.db_status = record["Install Status"]

					cmdb_db.sub_name = None  # reset old lookups
					try:
						business_service = CMDBRef.objects.get(navn=record["Name.1"]) # dette er det andre "name"-feltet
						cmdb_db.sub_name = business_service # add this lookup
					except:
						pass

					cmdb_db.save()

				obsolete_devices = all_existing_db

				for item in obsolete_devices:
					item.delete()

				logg_entry_message = 'Fant %s databaser. %s manglet navn. Slettet %s inaktive databaser.' % (
						antall_records,
						db_dropped,
						len(obsolete_devices),
					)
				logg_entry = ApplicationLog.objects.create(
						event_type=LOG_EVENT_TYPE,
						message=logg_entry_message,
					)
				#print("\n")
				print(logg_entry_message)
				return logg_entry_message

			#eksekver
			logg_entry_message = import_cmdb_databases()
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


