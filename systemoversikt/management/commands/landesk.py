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
from systemoversikt.models import CMDBdevice, Virksomhet, ApplicationLog
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist


class Command(BaseCommand):
	def handle(self, **options):

		# *** Merk at det ikke er noe logikk her for å rydde opp. Dette er fordi eksporten inneholder ALT (også deaktivert og slettet).

		LOG_EVENT_TYPE = 'LANdesk-import'
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

		runtime_t0 = time.time()

		teller = 0

		file = settings.BASE_DIR + "/systemoversikt/import/landesk_intern_sone.csv"
		with open(file, 'r', encoding='utf-8-sig') as file:
			csv_data = list(csv.DictReader(file, delimiter=","))
		print("Det er %s linjer i filen" % len(csv_data))

		@transaction.atomic
		def perform_atomic_update():

			date_format = "%d.%m.%Y %H:%M:%S"
			# eksempel 21.04.2021 15:04:51

			def str_to_date(str):
				try:
					return make_aware(datetime.strptime(str, date_format))
				except:
					return None

			def str_to_user(username_string):
				try:
					username = username_string.lower()
					return User.objects.get(username__iexact=username)
				except:
					#print("Fant ikke", username_string)
					return None

			def update(ws, line):
				ws.kilde_landesk = True
				ws.landesk_nic = line["NIC Address"]
				ws.landesk_manufacturer = line["Manufacturer"]
				ws.landesk_os_release = line["Release ID"]
				ws.landesk_sist_sett = str_to_date(line["Last Policy Sync Date"])
				ws.landesk_os = line["OS Name"]
				ws.landesk_login = str_to_user(line["Login Name"])

				ws.save()
				return

			for line in csv_data:
				nonlocal teller
				teller += 1

				wsnummer = line["Device name"]
				try:
					ws = CMDBdevice.objects.get(comp_name=wsnummer)
				except Exception as e:
					ws = CMDBdevice.objects.create(comp_name=wsnummer)
					ws.landesk_opprettet_av_landesk = True
				update(ws, line)



		perform_atomic_update()

		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		logg_entry_message = "Kjøretid: %s sekunder.\nDet er %s klienter" % (
				round(logg_total_runtime, 1),
				teller
		)
		print(logg_entry_message)
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)

