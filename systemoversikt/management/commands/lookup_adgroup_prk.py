# -*- coding: utf-8 -*-

"""
Hensikten med denne koden er å tagge alle AD-grupper med informasjon om de stammer fra PRK eller ikke.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
import os
import time
import sys
import json
from django.db import transaction
from systemoversikt.models import ApplicationLog, PRKvalg, ADgroup
from django.db.models import Q
import requests

class Command(BaseCommand):
	def handle(self, **options):

		LOG_EVENT_TYPE = 'Oppslag AD-PRK-bruker'
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

		runtime_t0 = time.time()
		count_hits = 0
		count_misses = 0

		@transaction.atomic
		def perform_atomic_update():
			for valg in PRKvalg.objects.all():
				if valg.ad_group_ref != None:
					continue  # skip if reference already exist

				print(valg.gruppenavn)
				try:
					ad_group = ADgroup.objects.get(distinguishedname__iexact=valg.gruppenavn)
					ad_group.from_prk = True   # AD-grupper har denne som default False, settes True hvis vi matcher
					ad_group.save()
					valg.ad_group_ref.add(ad_group)
					valg.in_active_directory = True
					valg.save()
					nonlocal count_hits
					count_hits += 1
				except:
					valg.in_active_directory = False
					valg.save()
					nonlocal count_misses
					count_misses += 1

		perform_atomic_update()

		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		logg_entry_message = "Kjøretid: %s. %s treff og %s bom." % (
				round(logg_total_runtime, 1),
				count_hits,
				count_misses,
		)
		print(logg_entry_message)
		logg_entry = ApplicationLog.objects.create(
				event_type=LOG_EVENT_TYPE,
				message=logg_entry_message,
		)
