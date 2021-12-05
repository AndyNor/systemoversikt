from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
from systemoversikt.models import *
from django.db import transaction
import os

class Command(BaseCommand):
	def handle(self, **options):

		sp_site = os.environ['SHAREPOINT_SITE']
		client_id = os.environ['SHAREPOINT_CLIENT_ID']
		client_secret = os.environ['SHAREPOINT_CLIENT_SECRET']

		sp = da_tran_SP365(site_url = sp_site, client_id = client_id, client_secret = client_secret)

		source_filepath = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/OK_db_sql.xlsx"
		source_file = sp.create_link(source_filepath)
		destination_file = 'systemoversikt/import/OK_db_sql.xlsx'

		sp.download(sharepoint_location = source_file, local_location = destination_file)


		@transaction.atomic
		def import_cmdb_databases():

			import json, os
			import pandas as pd
			import numpy as np

			from django.db.models import Q

			db_dropped = 0

			if ".xlsx" in destination_file:
				dfRaw = pd.read_excel(destination_file)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				data = dfRaw.to_dict('records')

			if data == None:
				return

			antall_records = len(data)
			all_existing_db = list(CMDBdatabase.objects.filter(~Q(db_version__startswith="Oracle"))) #alt som ikke er oracle og aktivt

			print("Alt lastet, oppdaterer databasen:")
			for idx, record in enumerate(data):
				print(".", end="", flush=True)
				#if idx % 1000 == 0:
				#	print("\n%s av %s" % (idx, antall_records))

				db_name = record["Name"]
				if db_name == "":
					print("Database mangler navn")
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


				if hostname != "":
					cmdbdevice = CMDBdevice.objects.get(comp_name=hostname)
					cmdb_db.db_server_modelref = cmdbdevice

				if record["Operational status"] == "Operational":
					cmdb_db.db_operational_status = True
				else:
					cmdb_db.db_operational_status = False

				if record["Version"] != "":
					cmdb_db.db_version = record["Version"]
				else:
					cmdb_db.db_version = "MSSQL"

				try:
					filesize = int(record.get("DataFilesSizeKB", 0)) * 1024 # convert to bytes
				except:
					filesize = 0
				cmdb_db.db_u_datafilessizekb = filesize

				cmdb_db.db_used_for = record["Used for"]
				cmdb_db.db_comments = record["Comments"]
				cmdb_db.billable = record["Billable"]
				cmdb_db.db_status = record["Status"]

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
					event_type='CMDB database import',
					message=logg_entry_message,
				)
			print("\n")
			print(logg_entry_message)

		#eksekver
		import_cmdb_databases()


