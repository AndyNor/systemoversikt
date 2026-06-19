# -*- coding: utf-8 -*-
# Change log:
# 2026-06-19: Nightly sync of device code sign-in combos from Graph (3-day window).
# 2026-06-19: Set helsestatus Advarsel when Graph max_results cap is reached.
# 2026-06-19: Optional --dager for manual backfill (e.g. 30 days).
from django.core.management.base import BaseCommand, CommandError
import datetime
import os
import time
import traceback

from django.utils import timezone

from systemoversikt.device_code_signins import (
	DEVICE_CODE_HISTORY_DAYS,
	fetch_device_code_signins_from_graph,
	prune_device_code_combos,
	upsert_device_code_combos,
)
from systemoversikt.models import ApplicationLog, DeviceCodeSignInCombo, IntegrasjonKonfigurasjon
from systemoversikt.views import push_pushover


class Command(BaseCommand):

	SYNC_DAYS = 3
	MAX_RESULTS = 500

	def add_arguments(self, parser):
		parser.add_argument(
			'--dager',
			type=int,
			default=Command.SYNC_DAYS,
			help=f'Antall dager tilbake i tid å hente fra Graph (standard: {Command.SYNC_DAYS}).',
		)

	def handle(self, **options):
		INTEGRASJON_KODEORD = "device_code_signins"
		LOG_EVENT_TYPE = "Device code sign-in sync"
		KILDE = "Azure Graph"
		PROTOKOLL = "REST"
		BESKRIVELSE = "Device code-innlogginger (kombinasjoner)"
		FREKVENS = "Hver natt"

		try:
			int_config = IntegrasjonKonfigurasjon.objects.get(kodeord=INTEGRASJON_KODEORD)
		except IntegrasjonKonfigurasjon.DoesNotExist:
			int_config = IntegrasjonKonfigurasjon.objects.create(
				kodeord=INTEGRASJON_KODEORD,
				kilde=KILDE,
				protokoll=PROTOKOLL,
				informasjon=BESKRIVELSE,
				sp_filnavn="",
				url="",
				frekvensangivelse=FREKVENS,
				log_event_type=LOG_EVENT_TYPE,
			)

		SCRIPT_NAVN = os.path.basename(__file__)
		int_config.script_navn = SCRIPT_NAVN
		int_config.helsestatus = "Forbereder"
		int_config.save()

		timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
		runtime_t0 = time.time()
		sync_days = options['dager']
		if sync_days < 1:
			raise CommandError('--dager må være minst 1')

		try:
			sign_ins, truncated, error_message = fetch_device_code_signins_from_graph(
				dager=sync_days,
				max_results=Command.MAX_RESULTS,
			)
			if error_message:
				raise RuntimeError(error_message)

			new_noteworthy_count = upsert_device_code_combos(sign_ins)
			pruned_count = prune_device_code_combos(retention_days=DEVICE_CODE_HISTORY_DAYS)
			total_combos = DeviceCodeSignInCombo.objects.count()

			if new_noteworthy_count > 0:
				push_pushover(f"Device code: {new_noteworthy_count} nye kombinasjoner")

			logg_message = (
				f"Hentet {len(sign_ins)} sign-ins ({sync_days} dager). "
				f"Nye merkverdige kombinasjoner: {new_noteworthy_count}. "
				f"Slettet {pruned_count} gamle rader. Totalt {total_combos} kombinasjoner."
			)
			if truncated:
				logg_message += (
					f" ADVARSEL: Graph returnerte flere treff enn grensen "
					f"({Command.MAX_RESULTS}); synk kan være ufullstendig."
				)

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)

			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message
			int_config.elementer = total_combos
			int_config.runtime = int(time.time() - runtime_t0)
			if truncated:
				int_config.helsestatus = (
					f"Advarsel: Graph-treff begrenset til {Command.MAX_RESULTS}"
				)
			else:
				int_config.helsestatus = "Vellykket"
			int_config.save()

		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			print(traceback.format_exc())
			int_config.helsestatus = f"Feilet\n{traceback.format_exc()}"
			int_config.save()
			push_pushover(f"{SCRIPT_NAVN} feilet")
