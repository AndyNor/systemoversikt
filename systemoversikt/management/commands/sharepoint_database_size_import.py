from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
from systemoversikt.models import *
from django.db import transaction
import os
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

		filename = "A34 - Database - Status and size.xlsx"

		source_filepath = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename
		source_file = sp.create_link(source_filepath)
		destination_file = 'systemoversikt/import/'+filename

		sp.download(sharepoint_location = source_file, local_location = destination_file)


		@transaction.atomic
		def import_cmdb_database_size():

			db_dropped = 0
			feilede_oppslag = 0

			if ".xlsx" in destination_file:
				dfRaw = pd.read_excel(destination_file, skiprows=2)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				data = dfRaw.to_dict('records')

			if data == None:
				return

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

			for line in data:
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
				print("Oppdaterte %s fra %s til %s bytes" % (db_database, old_size, new_size))
				#print("%s %s %s %s" % (line["Name"], line["Operational State"], line["Database Size"], line["Transaction Log Size"]))


			logg_entry_message = 'Fant %s databaser i %s. %s feilet oppslag mot eksisterende database' % (
					antall_records,
					filename,
					feilede_oppslag,
				)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB database size import',
					message=logg_entry_message,
				)
			print("\n")
			print(logg_entry_message)

		#eksekver
		import_cmdb_database_size()


