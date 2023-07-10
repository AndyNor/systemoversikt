from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
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

		sp_site = os.environ['SHAREPOINT_SITE']
		client_id = os.environ['SHAREPOINT_CLIENT_ID']
		client_secret = os.environ['SHAREPOINT_CLIENT_SECRET']

		sp = da_tran_SP365(site_url = sp_site, client_id = client_id, client_secret = client_secret)

		source_filepath = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/OK_db_oracle%20.xlsx"
		source_file = sp.create_link(source_filepath)
		destination_file = 'systemoversikt/import/OK_db_oracle.xlsx'
		sp.download(sharepoint_location = source_file, local_location = destination_file)

		db_dropped = 0
		db_servermissing = 0

		if ".xlsx" in destination_file:
			dfRaw = pd.read_excel(destination_file, engine="openpyxl")
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			data = dfRaw.to_dict('records')

		if data == None:
			print("Problemer med innlasting fra SharePoint: Oracledatabaser")
			return


		print("OK")
		antall_records = len(data)
		all_existing_db = list(CMDBdatabase.objects.filter(Q(db_version__startswith="Oracle")))


		print("Alt lastet, oppdaterer databasen:")
		for idx, record in enumerate(data):
			print(".", end="", flush=True)

			try:
				db_fullname = record["Name"] # det er to felt som heter "name" og dette er det første...
				db_name = record["Name"].split("@")[0] # første del er databasenavnet
				db_server = record["Name"].split("@")[1] # andre del etter @ er servernavn.
			except:
				db_dropped += 1
				continue # hvis dette ikke går er navnet feilformattert.
			if db_name == "":
				print("Database mangler navn")
				db_dropped += 1
				continue  # Det må være en verdi på denne

			# vi sjekker om enheten finnes fra før
			try:
				cmdb_db = CMDBdatabase.objects.get(Q(db_database=db_name) & Q(db_server=db_server))
				# fjerner fra oversikt over alle vi hadde før vi startet
				if cmdb_db in all_existing_db: # i tilfelle reintrodusert
					all_existing_db.remove(cmdb_db)
			except:
				# lager en ny
				cmdb_db = CMDBdatabase.objects.create(db_database=db_name, db_server=db_server)

			cmdb_db.db_server = db_server

			if record["Operational status"] == "Operational":
				cmdb_db.db_operational_status = True
			else:
				cmdb_db.db_operational_status = False

			cmdb_db.db_version = "Oracle " + record["Version"]


			if db_server != "":
				try:
					cmdbdevice = CMDBdevice.objects.get(comp_name=db_server)
					cmdb_db.db_server_modelref = cmdbdevice
				except:
					print("\nFeilet for %s" % record)
					db_servermissing += 1
					pass

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



		# cleanup
		obsolete_devices = all_existing_db

		for item in obsolete_devices:
			item.delete()



		# overskrive størrelser på databaser fra egen eksportfil
		#try:
		source_filepath = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/oracle_database_size.xlsx"
		source_file = sp.create_link(source_filepath)
		oracle_size_file = 'systemoversikt/import/oracle_database_size.xlsx'
		sp.download(sharepoint_location = source_file, local_location = oracle_size_file)
		print("Lastet ned separat oversikt over filstørrelser..")

		dfRaw = pd.read_excel(oracle_size_file, sheet_name='IS_DATABASE_SIZE_OEM03072023')
		dfRaw = dfRaw.replace(np.nan, '', regex=True)
		oracle_size_ez = dfRaw.to_dict('records')

		dfRaw = pd.read_excel(oracle_size_file, sheet_name='SS_DATABASE_SIZE_OEM03072023')
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
			import_server = record["SERVER"].strip().split(".")[0]
			try:
				dbinstance = CMDBdatabase.objects.get(db_database=import_databasenavn,db_server=import_server)
			except:
				#print(f"No matching database with name {import_databasenavn} for server {import_server}")
				antall_feilet += 1
				feilet_for.append("%s@%s" % (import_databasenavn, import_server))
				continue

			new_size = int(record["SIZE IN GB"] * 1000 * 1000 * 1000)
			old_size = dbinstance.db_u_datafilessizekb
			if old_size != new_size:
				dbinstance.db_u_datafilessizekb = new_size
				dbinstance.save()
				print(f"Oppdaterte størrelse på {import_databasenavn}@{import_server} fra {old_size} til {new_size}")
				antall_endret += 1
			else:
				#print(f"Ingen endring på {import_databasenavn}")
				antall_ingen_endring += 1


		logg_entry_message = f"Oppdaterte størrelser på Orcale-databaser. {antall_endret} endret. {antall_ingen_endring} som før. {antall_feilet} oppslag feilet: {feilet_for}"
		logg_entry = ApplicationLog.objects.create(
				event_type='CMDB database import (Oracle)',
				message=logg_entry_message,
			)
		print(f"\n {logg_entry_message}")


		#eksekver
		#import_cmdb_databases_oracle()

