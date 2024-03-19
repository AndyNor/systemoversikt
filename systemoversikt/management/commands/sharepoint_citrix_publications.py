# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from systemoversikt.models import *
from django.db import transaction
import json, os
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_citrix"
		LOG_EVENT_TYPE = "Citrix publikasjon"
		KILDE = "Citrix"
		PROTOKOLL = "Manuelt"
		BESKRIVELSE = "Citrixpubliseringer fra intern og sikker sone"
		FILNAVN = {"citrix_is": "citrix_publikasjoner_is.json", "citrix_ss": "citrix_publikasjoner_ss.json"}
		URL = ""
		FREKVENS = "Manuelt"

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
			from systemoversikt.views import sharepoint_get_file

			def hent_fil(filnavn):
				source_filepath = f"{filnavn}"
				result = sharepoint_get_file(source_filepath)
				destination_file = result["destination_file"]
				modified_date = result["modified_date"]
				print(f"{filnavn} er datert {modified_date}")
				return (destination_file, modified_date)

			fil_citrix_is = FILNAVN["citrix_is"]
			citrix_is_data, citrix_is_date = hent_fil(fil_citrix_is)
			fil_citrix_ss = FILNAVN["citrix_ss"]
			citrix_ss_data, citrix_ss_date = hent_fil(fil_citrix_ss)
			logg_entry_message = ""

			print(citrix_is_data)

			@transaction.atomic
			def import_citrix(filnavn, data, dato):

				# åpne fil

				antall_records = len(data)

				#for line in data:
					#print(line)
					# bearbeide


				logg_entry_message = f'Fant {antall_records} publikasjoner datert {dato}'
				return logg_entry_message

			#eksekver
			print(f"Importerer fra {fil_citrix_is}")
			logg_entry_message += import_citrix(fil_citrix_is, citrix_is_data, citrix_is_date)
			print(f"Importerer fra {fil_citrix_ss}")
			logg_entry_message += import_citrix(fil_citrix_ss, citrix_ss_data, citrix_ss_date)


			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = citrix_is_date # eller timezone.now()
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