# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: Keep one BloodHoundSnapshot row – flat files on disk per upload.
# 2026-06-23: Verbose ApplicationLog + JSON debug on upload failures.
# 2026-06-23: BloodHound tar.gz upload API for collector server.
import json
import os
import tempfile
import time
import traceback

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from systemoversikt.bloodhound.ingest import (
	BloodHoundIngestError,
	bloodhound_upload_max_bytes,
	ingest_tar_gz_archive,
	list_tar_member_names,
)
from systemoversikt.models import APIKeys, ApplicationLog, BloodHoundSnapshot, IntegrasjonKonfigurasjon
from systemoversikt.views import get_client_ip

LOG_EVENT_TYPE = 'BloodHound upload'
INTEGRASJON_KODEORD = 'bloodhound_ad'
INTEGRASJON_KILDE = 'Active Directory OSLOFELLES'
INTEGRASJON_PROTOKOLL = 'bloodhound-python'
INTEGRASJON_BESKRIVELSE = 'BloodHound AD-snapshot (preventiv analyse)'
_LOG_MESSAGE_LIMIT = 8000


def _log_upload(source_ip, message):
	"""Write to ApplicationLog; truncate very long diagnostics."""
	if len(message) > _LOG_MESSAGE_LIMIT:
		message = message[:_LOG_MESSAGE_LIMIT] + '… (truncated)'
	ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=message)
	print(f'{LOG_EVENT_TYPE}: {message}')


def _format_debug(debug):
	if not debug:
		return ''
	try:
		return json.dumps(debug, ensure_ascii=False, default=str)
	except TypeError:
		return str(debug)


def _error_response(source_ip, status, error, phase=None, debug=None, log_extra=''):
	body = {'error': error}
	if phase:
		body['phase'] = phase
	if debug:
		body['debug'] = debug
	log_parts = [f'Feilet fra {source_ip}']
	if phase:
		log_parts.append(f'phase={phase}')
	log_parts.append(str(error))
	if log_extra:
		log_parts.append(log_extra)
	if debug:
		log_parts.append(f'debug={_format_debug(debug)}')
	_log_upload(source_ip, ' | '.join(log_parts))
	return JsonResponse(body, status=status)


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
	BloodHoundSnapshot.objects.exclude(snapshot_id=snapshot.snapshot_id).delete()
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
	_log_upload(source_ip, f'Innkommende kall fra {source_ip} method={request.method}')

	if request.method != 'POST':
		return _error_response(source_ip, 405, 'Invalid request method', phase='request')

	if not _api_key_ok(request):
		has_key = bool(request.headers.get('key'))
		return _error_response(
			source_ip,
			403,
			"Missing or wrong key. Supply HTTP header 'key'",
			phase='auth',
			debug={'key_header_present': has_key},
		)

	upload = request.FILES.get('archive')
	if not upload:
		return _error_response(
			source_ip,
			400,
			"Missing multipart field 'archive' (tar.gz)",
			phase='upload',
			debug={
				'files_fields': sorted(request.FILES.keys()),
				'content_type': request.content_type,
			},
		)

	upload_name = getattr(upload, 'name', '') or ''
	upload_size = upload.size
	upload_content_type = getattr(upload, 'content_type', '') or ''
	max_bytes = bloodhound_upload_max_bytes()
	_log_upload(
		source_ip,
		f'Mottatt archive name={upload_name!r} size={upload_size} content_type={upload_content_type!r} '
		f'max_bytes={max_bytes}',
	)

	if upload_size > max_bytes:
		return _error_response(
			source_ip,
			413,
			'Archive exceeds maximum allowed size',
			phase='upload',
			debug={
				'upload_size': upload_size,
				'max_bytes': max_bytes,
				'upload_name': upload_name,
			},
		)

	runtime_t0 = time.time()
	tmp_path = None
	try:
		with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as tmp:
			for chunk in upload.chunks():
				tmp.write(chunk)
			tmp_path = tmp.name

		_log_upload(source_ip, f'Lagret midlertidig arkiv {tmp_path} ({upload_size} byte), starter ingest')
		ingest_result = ingest_tar_gz_archive(tmp_path)
		snapshot = _persist_snapshot(ingest_result, source_ip)
		runtime = time.time() - runtime_t0
		logg_message = (
			f'Snapshot {snapshot.snapshot_id} mottatt ({snapshot.file_count} filer, '
			f'{snapshot.count_users} brukere, {snapshot.count_computers} maskiner) '
			f'runtime={int(runtime)}s'
		)
		_log_upload(source_ip, logg_message)
		_update_integrasjon_success(runtime, logg_message)

		return JsonResponse({
			'snapshot_id': snapshot.snapshot_id,
			'received_at': snapshot.received_at.isoformat(),
			'counts': ingest_result['counts'],
			'shards': ingest_result.get('shards', {}),
			'files': snapshot.file_count,
			'total_bytes': snapshot.total_bytes,
			'removed_files': ingest_result.get('removed_files', []),
		}, status=200)

	except BloodHoundIngestError as exc:
		tb = traceback.format_exc()
		_update_integrasjon_failure(tb)
		debug = dict(exc.debug)
		if tmp_path and os.path.isfile(tmp_path) and 'tar_members' not in debug:
			debug['tar_members'] = list_tar_member_names(tmp_path)
		return _error_response(
			source_ip,
			400,
			str(exc),
			phase=exc.phase,
			debug=debug,
		)

	except Exception as exc:
		tb = traceback.format_exc()
		_update_integrasjon_failure(tb)
		debug = {}
		if tmp_path and os.path.isfile(tmp_path):
			debug['tar_members'] = list_tar_member_names(tmp_path)
		_log_upload(source_ip, f'Uventet feil fra {source_ip}: {exc}\n{tb}')
		body = {'error': str(exc), 'phase': 'unexpected'}
		if debug:
			body['debug'] = debug
		return JsonResponse(body, status=400)

	finally:
		if tmp_path and os.path.isfile(tmp_path):
			try:
				os.remove(tmp_path)
			except OSError:
				pass
