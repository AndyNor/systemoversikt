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
from systemoversikt.models import ApplicationLog, HRorg
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.db import transaction


class Command(BaseCommand):
	def handle(self, **options):

		runtime_t0 = time.time()

		logg_hits = 0
		logg_misses = 0

		print("Laster inn brukere...")


		LOCAL_DEBUG = False
		debug_file = os.path.dirname(os.path.abspath(__file__)) + "/usr.csv"

		if LOCAL_DEBUG == True:
			with open(debug_file, 'r', encoding='latin-1') as file:
				datastructure = list(csv.DictReader(file, delimiter=";"))

		else:
			url = os.environ["PRK_USERS_URL"]
			#apikey = os.environ["PRK_FORM_APIKEY"]
			headers = {}
			print("Kobler til %s" % url)
			r = requests.get(url, headers=headers)
			print("Encoding: %s" % r.encoding)
			print("Statuskode: %s" % r.status_code)
			if r.status_code == 200:
				datastructure = csv.DictReader(r.text.splitlines(), delimiter=";")
			else:
				sys.exit()



		@transaction.atomic
		def perform_atomic_update():
			nonlocal logg_hits
			nonlocal logg_misses
			nonlocal datastructure

			for line in datastructure:
				username = "%s%s" % (line["O"], line["EMPLOYEENUMBER"])
				usertype = "%s" % (line["EMPLOYEETYPENAME"])


				try:
					org_unit = HRorg.objects.get(ouid=line["OUID"])
				except:
					org_unit = None

				ansattnr = int(line["EMPLOYEENUMBER"])
				try:
					u = User.objects.get(username=username)
					logg_hits += 1

				except ObjectDoesNotExist:
					continue
					logg_misses += 1

				u.profile.usertype = usertype
				u.profile.org_unit = org_unit
				u.profile.ansattnr = ansattnr
				u.profile.from_prk = True
				u.save()

		perform_atomic_update()

		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		logg_entry_message = "Kjøretid: %s sekunder: %s treff, %s bom." % (
				round(logg_total_runtime, 1),
				logg_hits,
				logg_misses,
		)
		print(logg_entry_message)
		logg_entry = ApplicationLog.objects.create(
				event_type='PRK user import',
				message=logg_entry_message,
		)

