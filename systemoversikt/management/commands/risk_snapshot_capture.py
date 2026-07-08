# -*- coding: utf-8 -*-
# Change log:
# 2026-07-08: Daily capture of collection rapport and sammenstilling JSON snapshots with dedup.

from datetime import datetime
import os
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from systemoversikt.models import (
	RISK_SNAPSHOT_SOURCE_COLLECTION,
	RISK_SNAPSHOT_SOURCE_SAMMENSTILLING,
)
from systemoversikt.risk_snapshot import capture_all
from systemoversikt.views import push_pushover


class Command(BaseCommand):
	help = 'Capture JSON snapshots of risk collections and sammenstillinger (dedup by SHA-256).'

	def add_arguments(self, parser):
		parser.add_argument(
			'--source-types',
			default='collection,sammenstilling',
			help='Comma-separated: collection, sammenstilling',
		)
		parser.add_argument(
			'--dry-run',
			action='store_true',
			help='Compute payloads and dedup without writing to the database.',
		)

	def handle(self, *args, **options):
		INTEGRASJON_KODEORD = 'risk_snapshot_capture'
		LOG_EVENT_TYPE = 'Risk snapshot capture'
		KILDE = 'Lokal'
		PROTOKOLL = 'N/A'
		BESKRIVELSE = 'JSON-snapshots av risikosamlinger og risikosammenstillinger'
		FILNAVN = ''
		URL = ''
		FREKVENS = 'Daglig (planlagt)'

		from systemoversikt.models import ApplicationLog, IntegrasjonKonfigurasjon

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
		int_config.helsestatus = 'Forbereder'
		int_config.save()

		timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		self.stdout.write('\n\n%s ------ Starter %s ------' % (timestamp, SCRIPT_NAVN))
		runtime_t0 = time.time()

		raw_types = (options.get('source_types') or '').strip().lower()
		type_map = {
			'collection': RISK_SNAPSHOT_SOURCE_COLLECTION,
			'sammenstilling': RISK_SNAPSHOT_SOURCE_SAMMENSTILLING,
		}
		source_types = set()
		for part in raw_types.split(','):
			part = part.strip()
			if part in type_map:
				source_types.add(type_map[part])
		if not source_types:
			source_types = set(type_map.values())

		dry_run = bool(options.get('dry_run'))

		try:
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message='starter..')
			stats = capture_all(source_types=source_types, dry_run=dry_run)
			msg = (
				'Snapshots lagret: %d, uendret (hoppet over): %d, feil: %d%s'
				% (
					stats['saved'],
					stats['unchanged'],
					stats['errors'],
					' (dry-run)' if dry_run else '',
				)
			)
			self.stdout.write(msg)
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=msg)

			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = msg
			int_config.runtime = int(time.time() - runtime_t0)
			int_config.helsestatus = 'Vellykket'
			int_config.save()
		except Exception as exc:
			logg_message = '%s feilet med meldingen %s' % (SCRIPT_NAVN, exc)
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			self.stderr.write(logg_message)
			import traceback
			int_config.helsestatus = 'Feilet\n%s' % traceback.format_exc()
			int_config.save()
			push_pushover('%s feilet' % SCRIPT_NAVN)
			raise
