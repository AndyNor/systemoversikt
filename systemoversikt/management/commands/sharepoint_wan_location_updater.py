# -*- coding: utf-8 -*-
import os, sys, time, json
import pandas as pd
import numpy as np
import warnings
from django.db.models import Q
from systemoversikt.views import sharepoint_get_file
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError

class Command(BaseCommand):

	INGEN_MATCH = []

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
		int_config.helsestatus = "Forbereder"
		int_config.save()

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
		runtime_t0 = time.time()

		try:

			source_filepath = f"{FILNAVN}"
			result = sharepoint_get_file(source_filepath)
			destination_file = result["destination_file"]
			modified_date = result["modified_date"]
			print(f"Filen er datert {modified_date}")

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="Starter..")
			warnings.simplefilter("ignore")
			dfRaw = pd.read_excel(destination_file)
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			wan_lokasjoner = dfRaw.to_dict('records')

			if wan_lokasjoner == None:
				ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="Datafilen var tom..")

			print("Sletter gammel data..")
			WANLokasjon.objects.all().delete()

			print(f"Legger til WANLokasjoner")
			antall_records = len(wan_lokasjoner)
			for line in wan_lokasjoner:

				try:
					lokasjons_id = line["LokasjonID"]
					virksomhetsforkortelse = lokasjons_id[0:3]
				except:
					continue

				try:
					virksomhet = Virksomhet.objects.get(virksomhetsforkortelse__iexact=virksomhetsforkortelse)
				except:
					try:
						virksomhet = Virksomhet.objects.get(gamle_virksomhetsforkortelser__icontains=virksomhetsforkortelse)
					except:
						virksomhet = None
						Command.INGEN_MATCH.append(lokasjons_id)
						print(f"ingen match for {lokasjons_id}")

				w, created = WANLokasjon.objects.get_or_create(lokasjons_id=lokasjons_id)
				w.virksomhet = virksomhet
				w.aksess_type = line["AksessType"]
				w.adresse = line["Adresse"]
				w.beskrivelse = line["Virksomhet"]
				w.save()

			logg_entry_message = f"Fant {antall_records} WAN-lokasjoner. Ingen match for {', '.join(loc.strip() for loc in Command.INGEN_MATCH)}."
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)

			print(logg_entry_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = modified_date
			int_config.sist_status = logg_entry_message
			runtime_t1 = time.time()
			int_config.runtime = int(runtime_t1 - runtime_t0)
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



