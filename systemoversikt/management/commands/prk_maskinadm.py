# -*- coding: utf-8 -*-
"""
DENNE SKAL FASES UT
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
import os
import time
import sys
import csv
from datetime import datetime
from django.utils.timezone import make_aware
import requests
from systemoversikt.models import CMDBdevice, Virksomhet, ApplicationLog
from django.core.exceptions import ObjectDoesNotExist
from py_topping.data_connection.sharepoint import da_tran_SP365


class Command(BaseCommand):
	def handle(self, **options):

		# *** Merk at det ikke er noe logikk her for å rydde opp. Dette er fordi eksporten inneholder ALT (også deaktivert og slettet).

		LOG_EVENT_TYPE = 'PRK maskinadm-import'
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

		runtime_t0 = time.time()

		teller_innmeldt = 0
		teller_slettet = 0
		teller_utmeldt = 0


		sp_site = os.environ['SHAREPOINT_SITE']
		client_id = os.environ['SHAREPOINT_CLIENT_ID']
		client_secret = os.environ['SHAREPOINT_CLIENT_SECRET']
		sp = da_tran_SP365(site_url = sp_site, client_id = client_id, client_secret = client_secret)
		filename = "prk-klienter.csv"
		source_filepath = "https://oslokommune.sharepoint.com/:x:/r"+filename
		source_file = sp.create_link(source_filepath)
		destination_file = 'systemoversikt/import/'+filename
		sp.download(sharepoint_location = source_file, local_location = destination_file)

		with open(destination_file, 'r', encoding='latin-1') as destination_file:
			csv_data = list(csv.DictReader(destination_file, delimiter=","))
		print("Det er %s linjer i filen" % len(csv_data))

		@transaction.atomic
		def perform_atomic_update():

			date_format = "%Y-%m-%dT%H:%M:%S"

			def str_to_date(str):
				return make_aware(datetime.strptime(str, date_format))

			def str_to_virk(str):
				try:
					return Virksomhet.objects.get(virksomhetsforkortelse=str)
				except:
					return None

			def update(ws, line):
				ws.kilde_prk = True
				ws.device_type = "KLIENT"
				ws.maskinadm_virksomhet = str_to_virk(line["virksomhet"])
				ws.maskinadm_virksomhet_str = line["virksomhet"]
				ws.maskinadm_klienttype = line["klienttype"]
				ws.maskinadm_sone = line["sone"]
				ws.maskinadm_lokasjon = line["lokasjon_kortnavn"]
				ws.maskinadm_sist_oppdatert = str_to_date(line["sist_oppdatert"])
				ws.maskinadm_status = line["status"]

				ws.save()
				return

			for line in csv_data:
				wsnummer = line["wsnummer"].lower()

				status = line["status"]
				nonlocal teller_innmeldt
				nonlocal teller_slettet
				nonlocal teller_utmeldt
				if status == "INNMELDT":
					teller_innmeldt += 1
				if status == "SLETTET":
					teller_slettet += 1
				if status == "UTMELDT":
					teller_utmeldt += 1

				try:
					ws = CMDBdevice.objects.get(comp_name=wsnummer)
					update(ws, line)
				except Exception as e:
					ws = CMDBdevice.objects.create(comp_name=wsnummer)
					update(ws, line)


		perform_atomic_update()

		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		logg_entry_message = "Kjøretid: %s sekunder.\nDet er %s innmeldt, %s utmeldt og %s slettet." % (
				round(logg_total_runtime, 1),
				teller_innmeldt,
				teller_slettet,
				teller_utmeldt,
		)
		print(logg_entry_message)
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)

