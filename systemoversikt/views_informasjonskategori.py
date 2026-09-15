# -*- coding: utf-8 -*-
# Change log:
# 2026-09-15: Full OKA overview page – searchable tree with expand/collapse.
# 2026-09-15: Superuser-only Last inn OKA page – upload Excel instead of manage.py.
# 2026-09-15: Search and save APIs for OKA informasjonskategorier on System and SystemBruk.

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q
import json

from systemoversikt.auto_oidc import render_access_denied
from systemoversikt.models import (
	ApplicationLog,
	InformasjonsKategori,
	SYSTEMBRUK_KATEGORI_TILLEGG,
	SYSTEMBRUK_KATEGORI_UNNTAK,
	System,
	SystemBruk,
	SystemBrukInformasjonsKategori,
)
from systemoversikt.object_change_log import format_m2m_diff, log_object_change
from systemoversikt.oka_import import (
	LOG_EVENT_TYPE,
	MAX_UPLOAD_BYTES,
	OkaImportError,
	import_oka_workbook,
)
from systemoversikt.oka_kode import NIVAA_FUNKSJON, NIVAA_HOVED, NIVAA_UNDER


def _kategori_qs():
	return InformasjonsKategori.objects.select_related('parent', 'parent__parent')


def _leaf_qs():
	return _kategori_qs().filter(nivaa=NIVAA_UNDER)


def _parse_id_list(raw_ids):
	ids = []
	for raw in raw_ids:
		try:
			ids.append(int(raw))
		except (TypeError, ValueError):
			return None
	return ids


@require_GET
def api_informasjonskategorier_sok(request):
	# 2026-09-15: Leaf OKA search for system/systembruk pickers.
	if not request.user.is_authenticated:
		return JsonResponse({'ok': False, 'error': 'session_expired'}, status=401)
	if not request.user.has_perm('systemoversikt.view_system'):
		return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)

	q = (request.GET.get('q') or '').strip()
	if len(q) < 2:
		return JsonResponse({'ok': True, 'results': []})

	qs = _leaf_qs().filter(aktiv=True).filter(
		Q(kode__icontains=q) | Q(kode_normalisert__icontains=q) | Q(tittel__icontains=q)
	).order_by('rekkefolge', 'kode_normalisert')

	exclude_raw = request.GET.getlist('exclude')
	exclude_ids = []
	for raw in exclude_raw:
		if raw.isdigit():
			exclude_ids.append(int(raw))
	if exclude_ids:
		qs = qs.exclude(pk__in=exclude_ids)

	results = [kategori.as_api_dict() for kategori in qs[:25]]
	return JsonResponse({'ok': True, 'results': results})


@require_POST
def system_lagre_informasjonskategorier(request, pk):
	# 2026-09-15: Save System standard OKA categories from the system detail page.
	system = get_object_or_404(System, pk=pk)
	if not request.user.has_perm('systemoversikt.change_system'):
		return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)

	try:
		data = json.loads(request.body.decode('utf-8'))
	except (ValueError, UnicodeDecodeError):
		return JsonResponse({'ok': False, 'error': 'invalid_json'}, status=400)

	ids = _parse_id_list(data.get('ids') or [])
	if ids is None:
		return JsonResponse({'ok': False, 'error': 'invalid_ids'}, status=400)

	valid = list(_leaf_qs().filter(pk__in=ids, aktiv=True))
	if len(valid) != len(set(ids)):
		return JsonResponse({'ok': False, 'error': 'unknown_kategori'}, status=400)
	by_id = {k.pk: k for k in valid}
	ordered = [by_id[i] for i in ids if i in by_id]

	old_items = list(system.informasjonskategorier.all())
	with transaction.atomic():
		system.informasjonskategorier.set(ordered)

	part = format_m2m_diff('Informasjonskategorier (OKA)', old_items, ordered)
	if part:
		log_object_change(request.user, system, part)

	return JsonResponse({
		'ok': True,
		'kategorier': [k.as_api_dict() for k in ordered],
	})


def _kobling_map(systembruk):
	result = {}
	for kobling in systembruk.informasjonskategori_koblinger.select_related(
		'kategori', 'kategori__parent', 'kategori__parent__parent'
	):
		result[kobling.kategori_id] = kobling
	return result


@require_POST
def systembruk_lagre_informasjonskategorier(request, pk):
	# 2026-09-15: Save SystemBruk extras and opt-outs (optional begrunnelse) from bruksdetaljer.
	bruk = get_object_or_404(SystemBruk.objects.select_related('system'), pk=pk)
	if not request.user.has_perm('systemoversikt.change_systembruk'):
		return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)

	try:
		data = json.loads(request.body.decode('utf-8'))
	except (ValueError, UnicodeDecodeError):
		return JsonResponse({'ok': False, 'error': 'invalid_json'}, status=400)

	unntak_raw = data.get('unntak') or []
	tillegg_raw = data.get('tillegg') or []
	if not isinstance(unntak_raw, list) or not isinstance(tillegg_raw, list):
		return JsonResponse({'ok': False, 'error': 'invalid_payload'}, status=400)

	def _parse_rows(rows, status):
		parsed = []
		ids = []
		for row in rows:
			if not isinstance(row, dict):
				return None, None
			try:
				kategori_id = int(row.get('id'))
			except (TypeError, ValueError):
				return None, None
			begrunnelse = (row.get('begrunnelse') or '').strip()
			parsed.append({'id': kategori_id, 'status': status, 'begrunnelse': begrunnelse})
			ids.append(kategori_id)
		return parsed, ids

	unntak_rows, unntak_ids = _parse_rows(unntak_raw, SYSTEMBRUK_KATEGORI_UNNTAK)
	tillegg_rows, tillegg_ids = _parse_rows(tillegg_raw, SYSTEMBRUK_KATEGORI_TILLEGG)
	if unntak_rows is None or tillegg_rows is None:
		return JsonResponse({'ok': False, 'error': 'invalid_payload'}, status=400)

	overlap = set(unntak_ids) & set(tillegg_ids)
	if overlap:
		return JsonResponse({'ok': False, 'error': 'overlap'}, status=400)

	standard_ids = set(bruk.system.informasjonskategorier.values_list('pk', flat=True))
	if set(unntak_ids) - standard_ids:
		return JsonResponse({'ok': False, 'error': 'unntak_not_default'}, status=400)
	if set(tillegg_ids) & standard_ids:
		return JsonResponse({'ok': False, 'error': 'tillegg_is_default'}, status=400)

	wanted_ids = set(unntak_ids) | set(tillegg_ids)
	valid = {
		k.pk: k
		for k in _leaf_qs().filter(pk__in=wanted_ids)
	}
	if wanted_ids - set(valid.keys()):
		return JsonResponse({'ok': False, 'error': 'unknown_kategori'}, status=400)

	old_koblinger = _kobling_map(bruk)
	old_unntak = [k.kategori for k in old_koblinger.values() if k.status == SYSTEMBRUK_KATEGORI_UNNTAK]
	old_tillegg = [k.kategori for k in old_koblinger.values() if k.status == SYSTEMBRUK_KATEGORI_TILLEGG]
	old_begrunnelse = {
		k.kategori_id: (k.begrunnelse or '')
		for k in old_koblinger.values()
	}

	wanted_by_id = {}
	for row in unntak_rows + tillegg_rows:
		wanted_by_id[row['id']] = row

	with transaction.atomic():
		for kategori_id, kobling in list(old_koblinger.items()):
			if kategori_id not in wanted_by_id:
				kobling.delete()
		for kategori_id, row in wanted_by_id.items():
			kobling = old_koblinger.get(kategori_id)
			if kobling is None:
				SystemBrukInformasjonsKategori.objects.create(
					systembruk=bruk,
					kategori=valid[kategori_id],
					status=row['status'],
					begrunnelse=row['begrunnelse'],
				)
			else:
				if kobling.status != row['status'] or (kobling.begrunnelse or '') != row['begrunnelse']:
					kobling.status = row['status']
					kobling.begrunnelse = row['begrunnelse']
					kobling.save()

	new_unntak = [valid[i] for i in unntak_ids]
	new_tillegg = [valid[i] for i in tillegg_ids]
	diff_parts = []
	part = format_m2m_diff('Unntatte standardkategorier', old_unntak, new_unntak)
	if part:
		diff_parts.append(part)
	part = format_m2m_diff('Tilleggskategorier', old_tillegg, new_tillegg)
	if part:
		diff_parts.append(part)
	for kategori_id, row in wanted_by_id.items():
		old_text = old_begrunnelse.get(kategori_id, '')
		new_text = row['begrunnelse']
		if old_text != new_text:
			kategori = valid[kategori_id]
			diff_parts.append(
				'Begrunnelse for %s: «%s» → «%s»' % (kategori, old_text or '–', new_text or '–')
			)
	if diff_parts:
		log_object_change(request.user, bruk, 'Informasjonskategorier: %s' % '; '.join(diff_parts))

	return JsonResponse({'ok': True})


def _user_is_systemadministrator(user):
	return user.is_authenticated and user.is_superuser


def _parent_chain_has(child, parent, by_id):
	node = parent
	seen = set()
	while node is not None and node.pk not in seen:
		if node.pk == child.pk:
			return True
		seen.add(node.pk)
		node = by_id.get(node.parent_id)
	return False


def _oka_tre():
	# 2026-09-15: Build parent/child lists in memory so the overview template needs no extra queries.
	kategorier = list(
		InformasjonsKategori.objects.order_by('rekkefolge', 'kode_normalisert')
	)
	by_id = {}
	for kat in kategorier:
		kat.barn_liste = []
		by_id[kat.pk] = kat
	rotnoder = []
	for kat in kategorier:
		parent = by_id.get(kat.parent_id)
		if parent is None or _parent_chain_has(kat, parent, by_id):
			rotnoder.append(kat)
		else:
			parent.barn_liste.append(kat)
	hovedfunksjoner = [k for k in rotnoder if k.nivaa == NIVAA_HOVED]
	andre_rotnoder = [k for k in rotnoder if k.nivaa != NIVAA_HOVED]
	return kategorier, hovedfunksjoner, andre_rotnoder


def oka_oversikt(request):
	# 2026-09-15: Read-only OKA tree for assignment helpers (system/systembruk open this in a new tab).
	required_permissions = ['systemoversikt.view_system']
	if not request.user.is_authenticated or not request.user.has_perm('systemoversikt.view_system'):
		return render_access_denied(request, required_permissions)

	kategorier, hovedfunksjoner, andre_rotnoder = _oka_tre()
	siste_import = (
		ApplicationLog.objects
		.filter(event_type=LOG_EVENT_TYPE)
		.exclude(message__startswith='starter')
		.order_by('-opprettet')
		.first()
	)
	return render(request, 'oka_oversikt.html', {
		'request': request,
		'required_permissions': [p.replace('.', ': ').replace('_', ' ') for p in required_permissions],
		'hovedfunksjoner': hovedfunksjoner,
		'andre_rotnoder': andre_rotnoder,
		'antall_totalt': len(kategorier),
		'antall_aktive': sum(1 for k in kategorier if k.aktiv),
		'antall_hovedfunksjon': sum(1 for k in kategorier if k.nivaa == NIVAA_HOVED),
		'antall_funksjon': sum(1 for k in kategorier if k.nivaa == NIVAA_FUNKSJON),
		'antall_underfunksjon': sum(1 for k in kategorier if k.nivaa == NIVAA_UNDER),
		'siste_import': siste_import,
		'forhandsutfylt_sok': (request.GET.get('q') or '').strip(),
	})


def oka_last_inn(request):
	# 2026-09-15: Systemadministrator (Django superuser) uploads OKA Excel; no manage.py needed.
	if not _user_is_systemadministrator(request.user):
		return render_access_denied(request, ['systemadministrator'])

	if request.method == 'POST':
		upload = request.FILES.get('okafil')
		if not upload:
			messages.error(request, 'Velg en Excel-fil (.xlsx) å laste opp.')
		elif not upload.name.lower().endswith(('.xlsx', '.xlsm')):
			messages.error(request, 'Kun .xlsx/.xlsm-filer støttes.')
		elif upload.size and upload.size > MAX_UPLOAD_BYTES:
			messages.error(request, 'Filen er for stor (maks 15 MB).')
		else:
			try:
				result = import_oka_workbook(upload, filename=upload.name)
				messages.success(request, result['message'])
				return redirect('oka_last_inn')
			except OkaImportError as exc:
				messages.error(request, 'Import feilet: %s' % exc)
			except Exception as exc:
				messages.error(request, 'Import feilet: %s' % exc)

	siste_import = (
		ApplicationLog.objects
		.filter(event_type=LOG_EVENT_TYPE)
		.exclude(message__startswith='starter')
		.order_by('-opprettet')
		.first()
	)
	return render(request, 'cmdb_oka_last_inn.html', {
		'request': request,
		'required_permissions': ['systemadministrator'],
		'antall_aktive': InformasjonsKategori.objects.filter(aktiv=True).count(),
		'antall_underfunksjon': InformasjonsKategori.objects.filter(
			aktiv=True, nivaa=NIVAA_UNDER
		).count(),
		'siste_import': siste_import,
	})
