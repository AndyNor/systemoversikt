# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å fikse tilknytning virksomhet for DRIFT-brukere
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import PRKuser, ApplicationLog
from django.db import transaction
import time

class Command(BaseCommand):
	def handle(self, **options):

		runtime_t0 = time.time()

		@transaction.atomic
		def perform_atomic_update():
			for u in User.objects.all():

				if len(PRKuser.objects.filter(username=u.username)) > 0:
					from_prk = True
				else:
					from_prk = False

				if u.profile.from_prk == from_prk:
					continue
				else:
					u.profile.from_prk = from_prk
					u.save()

					print("Endret %s" % u)

		perform_atomic_update()

		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		logg_entry_message = "Kjøretid: %s" % (
				round(logg_total_runtime, 1),
		)
		print(logg_entry_message)
		logg_entry = ApplicationLog.objects.create(
				event_type='Oppslag bruker mot PRK',
				message=logg_entry_message,
		)
		logg_entry.save()
