# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: BloodHound tar.gz upload API for collector server.
import os
import tempfile
import time
import traceback

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from systemoversikt.bloodhound.ingest import (
	bloodhound_upload_max_bytes,
	ingest_tar_gz_archive,
)
from systemoversikt.models import APIKeys, ApplicationLog, BloodHoundSnapshot, IntegrasjonKonfigurasjon
from systemoversikt.views import get_client_ip

LOG_EVENT_TYPE = 'BloodHound upload'
INTEGRASJON_KODEORD = 'bloodhound_ad'
INTEGRASJON_KILDE = 'Active Directory OSLOFELLES'
INTEGRASJON_PROTOKOLL = 'bloodhound-python'
INTEGRASJON_BESKRIVELSE = 'BloodHound AD-snapshot (preventiv analyse)'


def _allowed_upload_keys():
	return list(
		APIKeys.objects.filter(navn__startswith='bloodhound_collector').values_list('key', flat=True)
	)


def _api_key_ok(request):
	key = request.headers.get('key', None)
	if os.environ.get('THIS_ENV') == 'TEST':
		return True
	return key in _allowed_upload_keys()


def _ensure_integrasjon_config():
	try:
		return IntegrasjonKonfigurasjon.objects.get(kodeord=INTEGRASJON_KODEORD)
	except IntegrasjonKonfigurasjon.DoesNotExist:
		return IntegrasjonKonfigurasjon.objects.create(
			kodeord=INTEGRASJON_KODEORD,
			kilde=INTEGRASJON_KILDE,
			protokoll=INTEGRASJON_PROTOKOLL,
			informasjon=INTEGRASJON_BESKRIVELSE,
			sp_filnavn='',
			url='',
			frekvensangivelse='Ved opplasting fra collector',
			log_event_type=LOG_EVENT_TYPE,
			script_navn='api_bloodhound_upload',
		)


def _persist_snapshot(ingest_result, source_ip):
	counts = ingest_result['counts']
	snapshot, _created = BloodHoundSnapshot.objects.update_or_create(
		snapshot_id=ingest_result['snapshot_id'],
		defaults={
			'storage_path': ingest_result['storage_path'],
			'status': 'indexed',
			'error_message': '',
			'count_users': counts.get('users', 0),
			'count_computers': counts.get('computers', 0),
			'count_groups': counts.get('groups', 0),
			'count_gpos': counts.get('gpos', 0),
			'count_ous': counts.get('ous', 0),
			'count_domains': counts.get('domains', 0),
			'count_containers': counts.get('containers', 0),
			'shard_counts': ingest_result.get('shards', {}),
			'file_count': ingest_result.get('file_count', 0),
			'total_bytes': ingest_result.get('total_bytes', 0),
			'collection_methods': ingest_result.get('collection_methods'),
			'meta_version': ingest_result.get('meta_version'),
			'source_ip': source_ip,
		},
	)
	return snapshot


def _update_integrasjon_success(runtime_seconds, message):
	int_config = _ensure_integrasjon_config()
	int_config.script_navn = 'api_bloodhound_upload'
	int_config.dato_sist_oppdatert = timezone.now()
	int_config.sist_status = message
	int_config.runtime = int(runtime_seconds)
	int_config.helsestatus = 'Vellykket'
	int_config.save()


def _update_integrasjon_failure(exc_text):
	int_config = _ensure_integrasjon_config()
	int_config.helsestatus = f'Feilet\n{exc_text}'
	int_config.save()


@csrf_exempt
def api_bloodhound_upload(request):
	source_ip = get_client_ip(request)
	ApplicationLog.objects.create(
		event_type=LOG_EVENT_TYPE,
		message=f'Innkommende kall fra {source_ip}',
	)

	if request.method != 'POST':
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=f'Ugyldig metode fra {source_ip}')
		return JsonResponse({'error': 'Invalid request method'}, status=405)

	if not _api_key_ok(request):
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=f'Feil eller tom API-nøkkel fra {source_ip}')
		return JsonResponse(
			{'message': "Missing or wrong key. Supply HTTP header 'key'", 'data': None},
			status=403,
		)

	upload = request.FILES.get('archive')
	if not upload:
		return JsonResponse({'error': "Missing multipart field 'archive' (tar.gz)"}, status=400)

	if upload.size > bloodhound_upload_max_bytes():
		return JsonResponse({'error': 'Archive exceeds maximum allowed size'}, status=413)

	runtime_t0 = time.time()
	tmp_path = None
	try:
		with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as tmp:
			for chunk in upload.chunks():
				tmp.write(chunk)
			tmp_path = tmp.name

		ingest_result = ingest_tar_gz_archive(tmp_path)
		snapshot = _persist_snapshot(ingest_result, source_ip)
		runtime = time.time() - runtime_t0
		logg_message = (
			f'Snapshot {snapshot.snapshot_id} mottatt ({snapshot.file_count} filer, '
			f'{snapshot.count_users} brukere, {snapshot.count_computers} maskiner)'
		)
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
		_update_integrasjon_success(runtime, logg_message)

		return JsonResponse({
			'snapshot_id': snapshot.snapshot_id,
			'received_at': snapshot.received_at.isoformat(),
			'counts': ingest_result['counts'],
			'shards': ingest_result.get('shards', {}),
			'files': snapshot.file_count,
			'total_bytes': snapshot.total_bytes,
			'removed_snapshots': ingest_result.get('removed_snapshots', []),
		}, status=200)

	except Exception as exc:
		tb = traceback.format_exc()
		ApplicationLog.objects.create(
			event_type=LOG_EVENT_TYPE,
			message=f'Feilet fra {source_ip}: {exc}',
		)
		_update_integrasjon_failure(tb)
		return JsonResponse({'error': str(exc)}, status=400)

	finally:
		if tmp_path and os.path.isfile(tmp_path):
			try:
				os.remove(tmp_path)
			except OSError:
				pass
