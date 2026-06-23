# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: Nightly/manual BloodHound preventive analysis (BH-01–BH-07).
import os
import time
import traceback
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from systemoversikt.bloodhound.analyze import analyze_snapshot
from systemoversikt.models import ApplicationLog, BloodHoundSnapshot, IntegrasjonKonfigurasjon
from systemoversikt.views import push_pushover

INTEGRASJON_KODEORD = 'bloodhound_ad'
LOG_EVENT_TYPE = 'BloodHound analyse'
KILDE = 'Active Directory OSLOFELLES'
PROTOKOLL = 'bloodhound-python'
BESKRIVELSE = 'BloodHound AD-snapshot (preventiv analyse)'


class Command(BaseCommand):
	help = 'Kjør preventive BloodHound-sjekker (BH-01–BH-07) på sist importerte JSON.'

	def add_arguments(self, parser):
		parser.add_argument(
			'--snapshot-id',
			dest='snapshot_id',
			help='Snapshot-ID (YYYYMMDDHHMMSS). Default: siste BloodHoundSnapshot.',
		)

	def handle(self, **options):
		try:
			int_config = IntegrasjonKonfigurasjon.objects.get(kodeord=INTEGRASJON_KODEORD)
		except IntegrasjonKonfigurasjon.DoesNotExist:
			int_config = IntegrasjonKonfigurasjon.objects.create(
				kodeord=INTEGRASJON_KODEORD,
				kilde=KILDE,
				protokoll=PROTOKOLL,
				informasjon=BESKRIVELSE,
				sp_filnavn='',
				url='',
				frekvensangivelse='Nattlig / manuell',
				log_event_type=LOG_EVENT_TYPE,
				script_navn='bloodhound_analyze.py',
			)

		script_navn = os.path.basename(__file__)
		int_config.script_navn = script_navn
		int_config.helsestatus = 'Forbereder'
		int_config.save()

		print(f"\n\n{datetime.now():%Y-%m-%d %H:%M:%S} ------ Starter {script_navn} ------")
		runtime_t0 = time.time()
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message='starter..')

		try:
			snapshot_id = options.get('snapshot_id')
			if snapshot_id:
				snapshot = BloodHoundSnapshot.objects.get(snapshot_id=snapshot_id)
			else:
				snapshot = BloodHoundSnapshot.objects.order_by('-snapshot_id').first()
				if not snapshot:
					raise BloodHoundSnapshot.DoesNotExist('ingen snapshot')

			count = analyze_snapshot(snapshot)
			runtime = int(time.time() - runtime_t0)
			logg_message = (
				f'Analyse {snapshot.snapshot_id} ferdig: {count} funn '
				f'({runtime}s)'
			)
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)

			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message
			int_config.runtime = runtime
			int_config.helsestatus = 'Vellykket'
			int_config.save()

		except Exception as exc:
			logg_message = f'{script_navn} feilet: {exc}'
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			print(traceback.format_exc())
			int_config.helsestatus = f'Feilet\n{traceback.format_exc()}'
			int_config.save()
			push_pushover(f'{script_navn} feilet')
