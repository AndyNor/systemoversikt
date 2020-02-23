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
from systemoversikt.models import ApplicationLog, PRKuser
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.db import transaction


# nå importert alle brukere

class Command(BaseCommand):
	def handle(self, **options):

		runtime_t0 = time.time()

		logg_new = 0
		logg_deleted = 0
		logg_existing = 0

		print("Laster inn brukere...")

		url = os.environ["PRK_USERS_URL"]
		#apikey = os.environ["PRK_FORM_APIKEY"]
		headers = {}

		print("Kobler til %s" % url)
		r = requests.get(url, headers=headers)
		print("Encoding: %s" % r.encoding)
		r.encoding = 'latin-1'
		print("Endrer til %s" % r.encoding)
		print("Statuskode: %s" % r.status_code)
		if r.status_code == 200:
			vlan_datastructure = csv.DictReader(r.text.splitlines(), delimiter=";")
		else:
			sys.exit()

		existing_users = list(PRKuser.objects.all())

		@transaction.atomic
		def perform_atomic_update():
			nonlocal logg_new
			nonlocal logg_deleted
			nonlocal logg_existing
			nonlocal vlan_datastructure
			nonlocal existing_users

			for line in vlan_datastructure:
				username = "%s%s" % (line["O"], line["EMPLOYEENUMBER"])
				usertype = "%s" % (line["EMPLOYEETYPENAME"])
				try:
					u = PRKuser.objects.get(username=username)
					logg_existing += 1
					existing_users.remove(u)
					continue
				except ObjectDoesNotExist:
					u = PRKuser.objects.create(username=username, usertype=usertype)
					logg_new += 1

			for u in existing_users:
				u.delete()
				# fjerne "i PRK" fra users (en eller to?)
				logg_deleted += 1

		perform_atomic_update()

		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		logg_entry_message = "Kjøretid: %s sekunder: %s som før, %s nye og %s slettede" % (
				round(logg_total_runtime, 1),
				logg_existing,
				logg_new,
				logg_deleted
		)
		print(logg_entry_message)
		logg_entry = ApplicationLog.objects.create(
				event_type='PRK user import',
				message=logg_entry_message,
		)
		logg_entry.save()
