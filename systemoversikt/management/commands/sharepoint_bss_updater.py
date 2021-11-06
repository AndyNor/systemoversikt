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

		source_filepath = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/OK_business_services.xlsx"
		source_file = sp.create_link(source_filepath)
		destination_file = 'systemoversikt/import/OK_business_services.xlsx'

		sp.download(sharepoint_location = source_file, local_location = destination_file)


		def konverter_kritikalitet(str):
			oppslagsmatrise = {
				"": None,  # ukjent
				"4 - not critical": 4,
				"3 - less critical": 3,
				"2 - somewhat critical": 2,
				"1 - most critical": 1,
			}
			try:
				return oppslagsmatrise[str.lower()]  # lowercase for å slippe unødige feil
			except:
				print('Konvertere kritikalitet: fant ikke %s' % (str))
				return None  # Ukjent

		def konverter_environment(str):
			oppslagsmatrise = {
				"": 8,  # ukjent
				"production": 1,
				"staging": 6,
				"test": 2,
				"qa": 7,
				"development": 3,
				"training": 4,
				"demonstration": 2,
				"disaster recovery": 9,
			}
			try:
				return oppslagsmatrise[str.lower()]  # lowercase for å slippe unødige feil
			except:
				print('Konvertere environment: fant ikke %s' % (str))
				return 8  # Ukjent


		@transaction.atomic
		def import_business_services():

			import pandas as pd
			import numpy as np
			dfRaw = pd.read_excel(destination_file)
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			data = dfRaw.to_dict('records')

			# Gå igjennom alle eksisterende business services, dersom ikke i ny fil, merk med "utgått"
			alle_eksisterende_cmdbref = list(CMDBRef.objects.all()) #bss
			alle_eksisterende_cmdbbs = list(CMDBbs.objects.all()) #bs

			# Importere enheter (andre data i importfil nummer 2)
			antall_nye_bs = 0
			antall_deaktiverte_bs = 0
			antall_nye_bss = 0
			antall_slettede_bss = 0

			antall_records = len(data)

			print("Alt lastet, oppdaterer databasen:")

			for record in data:

				print(".", end="", flush=True)
				bss_dropped = 0
				bs_dropped = 0
				bss_name = record["Name"]
				bs_name = record["Name.1"]
				bss_id = record["Sys ID.1"]
				bs_id = record["Sys ID"]

				if bs_name == "" or bss_name == "":
					print("Business service navn eller BSS-navn mangler")
					bss_dropped += 1
					continue  # Det må være en verdi på denne

				# sjekke om bs finnes fra før, om ikke opprette
				if len(bs_id) < 32:
					print("Business service %s manglet unik ID" % bs_name)
					bs_dropped += 1
					continue

				try:
					business_service = CMDBbs.objects.get(bs_external_ref=bs_id)
					if business_service in alle_eksisterende_cmdbbs:
						alle_eksisterende_cmdbbs.remove(business_service)
					if business_service.navn != bs_name:
						print("Nytt og gammelt navn stemmer ikke overens for %s og %s" % (business_service.navn, bs_name))
				except:
					antall_nye_bs += 1
					business_service = CMDBbs.objects.create(
							bs_external_ref=bs_id,
					)
				business_service.navn = bs_name
				business_service.save()

				# sjekke om bss finnes fra før, om ikke opprette
				if len(bss_id) < 32:
					print("Business sub service %s manglet unik ID" % bss_name)
					bss_dropped += 1
					continue

				try:
					business_sub_service = CMDBRef.objects.get(bss_external_ref=bss_id)
					if business_sub_service in alle_eksisterende_cmdbref:
						alle_eksisterende_cmdbref.remove(business_sub_service)
					if business_sub_service.navn != bss_name:
						message = "Nytt og gammelt navn stemmer ikke overens for %s og %s" % (business_sub_service.navn, bss_name)
						logg_entry = ApplicationLog.objects.create(
							event_type='CMDB business service import',
							message=message,
							)
						print(message)
				except:
					antall_nye_bs += 1
					business_sub_service = CMDBRef.objects.create(
							bss_external_ref=bss_id,
					)

				business_sub_service.navn = bss_name
				business_sub_service.environment=konverter_environment(record["Environment"])
				business_sub_service.kritikalitet=konverter_kritikalitet(record["Business criticality"])
				business_sub_service.u_service_availability=record["Service Availability"]
				business_sub_service.u_service_operation_factor = record["Service Operation Factor"]
				business_sub_service.u_service_complexity = record["Service Complexity"]
				business_sub_service.operational_status = True if record["Operational status"] == "Operational" else False
				business_sub_service.u_service_billable = True if record["Service Billable"] == "Yes" else False
				business_sub_service.parent_ref = business_service
				business_sub_service.service_classification = record["Service classification"]
				business_sub_service.comments = record["Short Description"]

				business_sub_service.save()

			# deaktiverer alle bs og sletter alle bss som er igjen
			for cmdbbs in alle_eksisterende_cmdbbs:
				if cmdbbs.operational_status == True:
					cmdbbs.operational_status = False
					antall_deaktiverte_bs += 1
					cmdbbs.save()

			for cmdbref in alle_eksisterende_cmdbref:
				antall_slettede_bss += 1
				cmdbref.delete()

			logg_entry_message = "Antall BSS: %s. Nye BS: %s (%s satt inaktiv), nye BSS: %s (%s slettede). %s BS og %s BSS feilet." % (
						antall_records,
						antall_nye_bs,
						antall_deaktiverte_bs,
						antall_nye_bss,
						antall_slettede_bss,
						bs_dropped,
						bss_dropped,
					)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB business service import',
					message=logg_entry_message,
				)
			print("\n")
			print(logg_entry_message)

		# eksekver
		import_business_services()


