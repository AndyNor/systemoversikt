# -*- coding: utf-8 -*-

"""
Hensikten med denne koden er å
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
from systemoversikt.models import Klientutstyr, Virksomhet
from django.core.exceptions import ObjectDoesNotExist


class Command(BaseCommand):
	def handle(self, **options):

		runtime_t0 = time.time()

		teller_innmeldt = 0
		teller_slettet = 0
		teller_utmeldt = 0

		file = os.path.dirname(os.path.abspath(__file__)) + "/prk-klienter.csv"
		with open(file, 'r', encoding='latin-1') as file:
			csv_data = list(csv.DictReader(file, delimiter=","))
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
				ws.maskinadm_virksomhet = str_to_virk(line["virksomhet"])
				ws.maskinadm_virksomhet_str = line["virksomhet"]
				ws.maskinadm_klienttype = line["klienttype"]
				ws.maskinadm_sone = line["sone"]
				ws.maskinadm_servicenivaa = line["servicenivaa"]
				ws.maskinadm_sist_oppdatert = str_to_date(line["sist_oppdatert"])

				ws.save()
				return

			for line in csv_data:
				wsnummer = line["wsnummer"]

				status = line["status"]
				if status == "INNMELDT":
					nonlocal teller_innmeldt
					nonlocal teller_slettet
					nonlocal teller_utmeldt
					teller_innmeldt += 1
				if status == "SLETTET":
					teller_slettet += 1
					continue # gå til neste
				if status == "UTMELDT":
					teller_utmeldt += 1
					continue # gå til neste

				try:
					ws = Klientutstyr.objects.get(maskinadm_wsnummer=wsnummer)
					update(ws, line)
				except Exception as e:
					ws = Klientutstyr.objects.create(maskinadm_wsnummer=wsnummer)
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

