# -*- coding: utf-8 -*-
#Hensikten med denne koden er å tagge alle AD-grupper med informasjon om de stammer fra PRK eller ikke.

from django.core.management.base import BaseCommand
from django.conf import settings
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

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "lokal_match_grp_prk"
		LOG_EVENT_TYPE = 'Oppslag ADgrp-PRKgrp'
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")
		KILDE = "Lokal"
		PROTOKOLL = "N/A"
		BESKRIVELSE = "Matcher AD-gruppe med PRK-valg"
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

			runtime_t0 = time.time()
			count_hits = 0
			count_misses = 0

			@transaction.atomic
			def perform_atomic_update():
				tomme_prk_valg = PRKvalg.objects.filter(ad_group_ref=None)
				antall_records = len(tomme_prk_valg)
				idx = 0
				for valg in tomme_prk_valg:
					#print(valg.gruppenavn)
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

					idx += 1
					if idx % 500 == 0:
						print(f"{idx} av {antall_records}")

			perform_atomic_update()

			runtime_t1 = time.time()
			logg_total_runtime = runtime_t1 - runtime_t0
			logg_entry_message = "Kjøretid %s sekunder. %s var vellykket og %s feilet." % (
					round(logg_total_runtime, 1),
					count_hits,
					count_misses,
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

