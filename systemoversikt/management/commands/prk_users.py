# -*- coding: utf-8 -*-
#Hensikten med denne koden er importere brukere i PRK for å kunne avdekke brukere som ikke burde være i AD.

from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.db import transaction
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
import os
import time
import sys
import json
import csv
import requests


class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "prk_users"
		LOG_EVENT_TYPE = 'PRK user import'
		KILDE = "PRK"
		PROTOKOLL = "REST"
		BESKRIVELSE = "Brukere"
		FILNAVN = ""
		URL = ""
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
			runtime_t0 = time.time()
			logg_hits = 0
			logg_misses = 0
			print("Laster inn brukere...")
			debug_file = os.path.dirname(os.path.abspath(__file__)) + "/usr.csv"

			if os.environ['THIS_ENV'] == "TEST":
				with open(debug_file, 'r', encoding='latin-1') as file:
					datastructure = list(csv.DictReader(file, delimiter=";"))


			if os.environ['THIS_ENV'] == "PROD":
				url = os.environ["PRK_USERS_URL"]
				#apikey = os.environ["PRK_FORM_APIKEY"]
				headers = {}
				print("Kobler til %s" % url)
				r = requests.get(url, headers=headers)
				print("Original encoding: %s" % r.encoding)
				r.encoding = "latin-1" # need to override
				print("New encoding: %s" % r.encoding)
				print("Statuskode: %s" % r.status_code)
				if r.status_code == 200:
					with open('systemoversikt/import/usr.csv', 'w') as file_handle:
							file_handle.write(r.text)
					print(f"Fil lastet ned")
					datastructure = csv.DictReader(r.text.splitlines(), delimiter=";")
				else:
					print(f"Error connecting: {r.status_code}.")


			print("Resetting profiles")
			Profile.objects.all().update(usertype=None)
			Profile.objects.all().update(org_unit=None)
			Profile.objects.all().update(ansattnr=None)
			Profile.objects.all().update(from_prk=False)

			for line in datastructure:
				#print(line["EMPLOYEENUMBER"])
				usertype = "%s" % (line["EMPLOYEETYPENAME"])
				ansattnr = int(line["EMPLOYEENUMBER"])
				try:
					org_unit = HRorg.objects.get(ouid=line["OUID"])
				except:
					org_unit = None

				usernames_str = ["%s%s" % (line["O"], line["EMPLOYEENUMBER"]),	"%s%s" % ("DRIFT", line["EMPLOYEENUMBER"])]
				usernames = []
				for u in usernames_str:
					try:
						usernames.append(User.objects.get(username__iexact=u))
					except:
						pass

				logg_hits += 1
				for u in usernames:

					u.profile.usertype = usertype
					u.profile.org_unit = org_unit
					u.profile.ansattnr = ansattnr
					u.profile.from_prk = True
					u.save()


			runtime_t1 = time.time()
			logg_total_runtime = runtime_t1 - runtime_t0
			logg_entry_message = "Kjøretid: %s sekunder: %s treff" % (
					round(logg_total_runtime, 1),
					logg_hits,
			)
			print(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_entry_message,
			)
			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
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

