# -*- coding: utf-8 -*-

"""
Hensikten med denne koden er importere brukere i PRK for å kunne avdekke brukere som ikke burde være i AD.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
import os
import time
import sys
import json
import csv
import requests
from django.contrib.auth.models import User
from systemoversikt.models import ApplicationLog, HRorg, Profile
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.db import transaction


class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "prk_users"
		LOG_EVENT_TYPE = 'PRK user import'
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

		runtime_t0 = time.time()

		logg_hits = 0
		logg_misses = 0

		print("Laster inn brukere...")

		debug_file = os.path.dirname(os.path.abspath(__file__)) + "/usr.csv"

		if os.environ['THIS_ENV'] == "TEST":
			with open(debug_file, 'r', encoding='latin-1') as file:
				datastructure = list(csv.DictReader(file, delimiter=";"))

		else: # production code
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
				datastructure = csv.DictReader(r.text.splitlines(), delimiter=";")
			else:
				sys.exit()



		@transaction.atomic
		def perform_atomic_update():
			nonlocal logg_hits
			nonlocal datastructure

			print("Resetting profiles")
			Profile.objects.all().update(usertype=None)
			Profile.objects.all().update(org_unit=None)
			Profile.objects.all().update(ansattnr=None)
			Profile.objects.all().update(from_prk=False)

			for line in datastructure:
				print(line["EMPLOYEENUMBER"])
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

		perform_atomic_update()

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

