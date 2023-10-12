# -*- coding: utf-8 -*-
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
from django.db import transaction
import os, sys
import json
import pandas as pd
import numpy as np
from django.db.models import Q

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_wan"
		LOG_EVENT_TYPE = "WAN location import"
		KILDE = "Manuell oversikt"
		PROTOKOLL = "SharePoint"
		BESKRIVELSE = "Oversikt over kommunens (nettverks)lokasjoner"
		FILNAVN = "WAN_lokasjoner_2023-06-26.xlsx"
		URL = ""
		FREKVENS = "Manuelt på forespørsel"

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

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="Starter..")

			# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
			import warnings
			warnings.simplefilter("ignore")

			dfRaw = pd.read_excel(destination_file)
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			wan_lokasjoner = dfRaw.to_dict('records')

			if wan_lokasjoner == None:
				ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="Datafilen var tom..")
				sys.exit()

			# tømmel gamle data
			WANLokasjon.objects.all().delete()
			print(f"Slettet alle eksisterende WANLokasjon-er")

			antall_records = len(wan_lokasjoner)
			for line in wan_lokasjoner:

				try:
					lokasjons_id = line["LokasjonID"]
					virksomhetsforkortelse = lokasjons_id[0:3]
				except:
					continue

				try:
					#print(virksomhetsforkortelse)
					virksomhet = Virksomhet.objects.get(virksomhetsforkortelse__iexact=virksomhetsforkortelse)
				except:
					try:
						virksomhet = Virksomhet.objects.get(gamle_virksomhetsforkortelser__icontains=virksomhetsforkortelse)
					except:
						virksomhet = None
						virksomhet
						print(f"ingen match for {lokasjons_id}")

				from django.db import IntegrityError
				try:
					w = WANLokasjon.objects.create(lokasjons_id=lokasjons_id)
					w.virksomhet = virksomhet
					w.aksess_type = line["AksessType"]
					w.adresse = line["Adresse"]
					w.beskrivelse = line["Virksomhet"]
					w.save()
					#print(f"lagret {lokasjons_id}")
				except IntegrityError as e:
					print(f"Integritetsfeil {e} for {lokasjons_id}")

			logg_entry_message = 'Fant %s WAN-lokasjoneri.' % (
					antall_records,
				)
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)

			print(logg_entry_message)

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



