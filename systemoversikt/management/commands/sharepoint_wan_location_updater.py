from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
from systemoversikt.models import *
from django.db import transaction
import os, sys
import json
import pandas as pd
import numpy as np
from django.db.models import Q

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_wan"
		FILNAVN = "WAN_lokasjoner_2023-06-26.xlsx"
		EVENT_TYPE = "WAN location import"


		sp_site = os.environ['SHAREPOINT_SITE']
		client_id = os.environ['SHAREPOINT_CLIENT_ID']
		client_secret = os.environ['SHAREPOINT_CLIENT_SECRET']
		sp = da_tran_SP365(site_url = sp_site, client_id = client_id, client_secret = client_secret)

		# WAN location data
		wan_data_file = FILNAVN
		source = sp.create_link("https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+wan_data_file)
		destination_file = 'systemoversikt/import/'+wan_data_file
		sp.download(sharepoint_location = source, local_location = destination_file)


		LOG_EVENT_TYPE = EVENT_TYPE
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="Starter..")


		if not ".xlsx" in destination_file:
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="Fant ikke riktig datafil..")
			sys.exit()

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
					print(f"ingen match mot {virksomhetsforkortelse}")

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

		logg_entry_message = 'Fant %s WAN-lokasjoneri %s.' % (
				antall_records,
				wan_data_file,
			)
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)

		print("\n")
		print(logg_entry_message)



