# -*- coding: utf-8 -*-
# Change log:
# 2026-06-21: Nightly cleanup of leverandører with no model references (same rules as /systemer/leverandor/ stats).

from datetime import datetime
import json
import os
import time
import traceback

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from systemoversikt.leverandor_referanser import leverandor_uten_kobling_queryset
from systemoversikt.models import ApplicationLog, IntegrasjonKonfigurasjon
from systemoversikt.views import push_pushover


class Command(BaseCommand):
	def handle(self, **options):
		INTEGRASJON_KODEORD = "lokal_rydde_leverandor"
		LOG_EVENT_TYPE = 'Rydde leverandører'
		KILDE = "Lokal"
		PROTOKOLL = "N/A"
		BESKRIVELSE = "Fjerne leverandører uten referanser fra andre modeller"
		FILNAVN = ""
		URL = ""
		FREKVENS = "Hver natt"

		try:
			int_config = IntegrasjonKonfigurasjon.objects.get(kodeord=INTEGRASJON_KODEORD)
		except IntegrasjonKonfigurasjon.DoesNotExist:
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
		int_config.helsestatus = "Forbereder"
		int_config.save()

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")

		try:
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

			runtime_t0 = time.time()
			antall_slettet = 0

			@transaction.atomic
			def perform_atomic_update():
				uten_kobling = list(leverandor_uten_kobling_queryset().order_by('leverandor_navn'))
				print(f"Fant {len(uten_kobling)} leverandører uten referanser\n")

				for leverandor in uten_kobling:
					print(f"* {leverandor} slettes")
					message = (
						f"{leverandor.leverandor_navn} (pk={leverandor.pk}) "
						f"er ikke koblet til noe. Slettet automatisk."
					)
					ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=message)
					leverandor.delete()
					nonlocal antall_slettet
					antall_slettet += 1

			perform_atomic_update()

			runtime_t1 = time.time()
			logg_total_runtime = runtime_t1 - runtime_t0
			logg_entry_message = (
				f"Kjøretid: {round(logg_total_runtime, 1)} sekunder. "
				f"Slettet {antall_slettet} leverandører uten referanser."
			)
			print(logg_entry_message)
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)

			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_entry_message
			int_config.runtime = int(logg_total_runtime)
			int_config.helsestatus = "Vellykket"
			int_config.save()

		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			int_config.helsestatus = f"Feilet\n{traceback.format_exc()}"
			int_config.save()
			push_pushover(f"{SCRIPT_NAVN} feilet")
