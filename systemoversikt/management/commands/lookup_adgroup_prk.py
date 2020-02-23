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
from systemoversikt.models import ApplicationLog, PRKvalg, ADgroup
from django.db.models import Q
import requests

class Command(BaseCommand):
	def handle(self, **options):

		runtime_t0 = time.time()

		count_hits = 0
		count_misses = 0
		misses = []

		for valg in PRKvalg.objects.all():
			if len(valg.ad_group_ref.all()) > 0:
				continue  # skip and go to next

			print(valg.gruppenavn)
			try:
				ad_group = ADgroup.objects.get(distinguishedname__iexact=valg.gruppenavn)
				ad_group.from_prk = True   # AD-grupper har denne som default False, settes True hvis vi matcher
				ad_group.save()
				valg.ad_group_ref.add(ad_group)
				valg.in_active_directory = True
				valg.save()
				count_hits += 1
			except:
				count_misses += 1
				valg.in_active_directory = False
				valg.save()


		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		logg_entry_message = "Kjøretid: %s. Treff: %s. Bom: %s" % (
				round(logg_total_runtime, 1),
				count_hits,
				count_misses,
		)
		print(logg_entry_message)
		logg_entry = ApplicationLog.objects.create(
				event_type='AD-gruppe PRK-oppslag',
				message=logg_entry_message,
		)
