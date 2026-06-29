# -*- coding: utf-8 -*-
# Change log:
# 2026-06-29: Adaptive lookback – 3h when last success ≤2h ago, else 3 days (offline catch-up).
# 2026-06-29: Hourly sync – 3-hour Graph lookback; --dager kept for manual backfill.
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

	SYNC_HOURS = 3
	CATCHUP_DAYS = 3
	GAP_THRESHOLD_HOURS = 2
	BACKFILL_DAYS = 30
	MAX_RESULTS = 500

	def add_arguments(self, parser):
		parser.add_argument(
			'--timer',
			type=int,
			default=None,
			help=(
				f'Overstyrer automatisk lookback: hent siste N timer '
				f'(standard ved normal drift: {Command.SYNC_HOURS}).'
			),
		)
		parser.add_argument(
			'--dager',
			type=int,
			default=None,
			help=(
				f'Overstyrer automatisk lookback: hent siste N dager '
				f'(f.eks. {Command.BACKFILL_DAYS} for manuell backfill).'
			),
		)

	def _resolve_lookback(self, last_success_at, sync_days, sync_hours):
		# 2026-06-29: Short window on schedule; widen after gaps (server offline, failed runs).
		if sync_days is not None:
			if sync_days < 1:
				raise CommandError('--dager må være minst 1')
			return 'days', sync_days, f"{sync_days} dager (manuell --dager)"

		if sync_hours is not None:
			if sync_hours < 1:
				raise CommandError('--timer må være minst 1')
			return 'hours', sync_hours, f"{sync_hours} timer (manuell --timer)"

		if last_success_at is None:
			return 'days', Command.CATCHUP_DAYS, f"{Command.CATCHUP_DAYS} dager (første kjøring)"

		age = timezone.now() - last_success_at
		if age <= datetime.timedelta(hours=Command.GAP_THRESHOLD_HOURS):
			return 'hours', Command.SYNC_HOURS, (
				f"{Command.SYNC_HOURS} timer (sist vellykket {self._format_age(age)} siden)"
			)

		return 'days', Command.CATCHUP_DAYS, (
			f"{Command.CATCHUP_DAYS} dager (sist vellykket {self._format_age(age)} siden, "
			f"> {Command.GAP_THRESHOLD_HOURS} timer)"
		)

	@staticmethod
	def _format_age(age):
		total_minutes = int(age.total_seconds() // 60)
		if total_minutes < 60:
			return f"{total_minutes} min"
		hours = total_minutes // 60
		minutes = total_minutes % 60
		if minutes:
			return f"{hours} t {minutes} min"
		return f"{hours} t"

	def handle(self, **options):
		INTEGRASJON_KODEORD = "device_code_signins"
		LOG_EVENT_TYPE = "Device code sign-in sync"
		KILDE = "Azure Graph"
		PROTOKOLL = "REST"
		BESKRIVELSE = "Device code-innlogginger (kombinasjoner)"
		FREKVENS = "Hver time"

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

		last_success_at = int_config.dato_sist_oppdatert

		SCRIPT_NAVN = os.path.basename(__file__)
		int_config.script_navn = SCRIPT_NAVN
		int_config.frekvensangivelse = FREKVENS
		int_config.helsestatus = "Forbereder"
		int_config.save()

		timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
		runtime_t0 = time.time()

		lookback_mode, lookback_value, lookback_label = self._resolve_lookback(
			last_success_at,
			options['dager'],
			options['timer'],
		)

		try:
			if lookback_mode == 'days':
				sign_ins, truncated, error_message = fetch_device_code_signins_from_graph(
					dager=lookback_value,
					max_results=Command.MAX_RESULTS,
				)
			else:
				sign_ins, truncated, error_message = fetch_device_code_signins_from_graph(
					timer=lookback_value,
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
				f"Hentet {len(sign_ins)} sign-ins ({lookback_label}). "
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
