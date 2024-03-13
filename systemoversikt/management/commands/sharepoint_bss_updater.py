# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from systemoversikt.views import push_pushover
from systemoversikt.models import *
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
import pandas as pd
import numpy as np
import os


class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_business_services"
		LOG_EVENT_TYPE = "CMDB business service import"
		KILDE = "Service Now"
		PROTOKOLL = "E-post"
		BESKRIVELSE = "Tjenestegrupperinger fra driftsleverandør"
		FILNAVN = "A34_CMDB_services.xlsx"
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

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")

		try:

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

			source_filepath = f"{FILNAVN}"
			from systemoversikt.views import sharepoint_get_file
			result = sharepoint_get_file(source_filepath)
			destination_file = result["destination_file"]
			modified_date = result["modified_date"]
			print(f"Filen er datert {modified_date}")

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

				print(f"Åpner filen..")

				# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
				import warnings
				warnings.simplefilter("ignore")

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

				for record in data:

					#print(".", end="", flush=True)
					bss_dropped = 0
					bs_dropped = 0
					bss_name = record["Name"]
					bss_id = record["Sys ID"]
					bs_name = record["Parent"]
					bs_id = record["Sys ID.1"]

					if bs_name == "" or bss_name == "":
						print(f"Business service navn eller BSS-navn mangler ({record})")
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
								event_type=LOG_EVENT_TYPE,
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
						event_type=LOG_EVENT_TYPE,
						message=logg_entry_message,
					)
				print(logg_entry_message)
				return logg_entry_message

			# eksekver
			logg_entry_message = import_business_services()
			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = modified_date # her setter vi filens dato, ikke dato for kjøring av script
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



