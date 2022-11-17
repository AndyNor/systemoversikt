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

		#@transaction.atomic
		#def import_cmdb_databases_oracle():

		db_dropped = 0
		db_servermissing = 0

		#temporary file with oracle disk size (no process of data update!)
		#print("Laster inn manuell fil med databasestørrelser:")
		#filepath_size = "systemoversikt/import/oracle_disksize.xlsx"
		#dfRaw = pd.read_excel(filepath_size)
		#dfRaw = dfRaw.replace(np.nan, '', regex=True)
		#size_data = dfRaw.to_dict('records')
		#size_data = {"%s@%s" % (item["SID"], item["Server Name"]):item["Bytes Used (GB)"] for item in size_data}

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
			#if idx % 1000 == 0:
			#	print("\n%s av %s" % (idx, antall_records))

			try:
				db_fullname = record["Name"] # det er to felt som heter "name" og dette er det første...
				db_name = record["Name"].split("@")[0] # første del er databasenavnet
				db_server = record["Name"].split("@")[1] # andre del etter @ er servernavn.
			except:
				db_dropped += 1
				continue # hvis dette ikke går er navnet feilformattert.
			#print(db_name)
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

			#try:
			#	size_bytes = int(size_data[db_fullname]) * 1024 * 1024 * 1024  # kommer som string i GB.
			#	cmdb_db.db_u_datafilessizekb = size_bytes
			#	#print(size_bytes)
			#except:
			#	#print("failed")
			#	cmdb_db.db_u_datafilessizekb = 0


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
			cmdb_db.db_status = record["Status"]

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

		dfRaw = pd.read_excel(oracle_size_file, sheet_name='size_database_IZ')
		dfRaw = dfRaw.replace(np.nan, '', regex=True)
		oracle_size_is = dfRaw.to_dict('records')

		dfRaw = pd.read_excel(oracle_size_file, sheet_name='size_database_SZ')
		dfRaw = dfRaw.replace(np.nan, '', regex=True)
		oracle_size_ss = dfRaw.to_dict('records')

		oracle_size = oracle_size_is + oracle_size_ss

		database_size_not_found = []
		for oracle_db in CMDBdatabase.objects.filter(db_version__icontains="Oracle").filter(db_operational_status=True):
			for idx, record in enumerate(oracle_size):
				try:
					server = record["Host name"]
				except:
					server = record["Host Name"]

				server = re.search(r'^([^.]*).*$', server, re.I)[0]
				database_name = re.search(r'^([a-zA-Z0-9]*)', record["Database Name"], re.I)[0]

				if (oracle_db.db_database.lower() == database_name.lower()) and (oracle_db.db_server.lower() in server.lower()):
					# databases are often set up redundant. Same size on both serveres.
					# databasenavn og server stemmer, oppdater størrelse

					new_size = int(record["Size (GB)"] * 1024 * 1024 * 1024)
					old_size = oracle_db.db_u_datafilessizekb
					#print("%s = %s" % (old_size, size))
					if old_size != new_size:
						oracle_db.db_u_datafilessizekb = new_size



						#oracle_db.save()




						#print(oracle_db.db_u_datafilessizekb)
						print("Oppdaterer %s@%s (%s@%s) fra %s til %s bytes" % (oracle_db.db_database, oracle_db.db_server, database_name, server, old_size, new_size))
						break

			# loop complete, did not find any match
			database_size_not_found.append(oracle_db)

		for oracle_db in database_size_not_found:
			pass
			#print("Fant ikke data på %s@%s" % (oracle_db.db_database, oracle_db.db_server))



		logg_entry_message = 'Fant %s databaser. %s manglet navn. %s manglet serverknytning. Slettet %s inaktive databaser. %s mangler størrelse' % (
					antall_records,
					db_dropped,
					db_servermissing,
					len(obsolete_devices),
					len(database_size_not_found),
					)
		logg_entry = ApplicationLog.objects.create(
				event_type='CMDB database import (Oracle)',
				message=logg_entry_message,
			)
		print("\n")
		print(logg_entry_message)


		#eksekver
		#import_cmdb_databases_oracle()

