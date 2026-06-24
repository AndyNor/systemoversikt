# -*- coding: utf-8 -*-
# Change log:
# 2026-06-25: Scenario summary includes konsekvens/sannsynlighet lookup labels for table display.
# 2026-06-25: Scenario summary includes CSS classes for colored table cells.
# 2026-06-24: Scenario list API includes actions for tiltak section refresh.
# 2026-06-24: JSON API for risk scenario/tiltak AJAX editor (owner-only).

import json
from datetime import datetime

from django.db import transaction
from django.db.models import Max
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from systemoversikt.models import (
	RISIKOBEHANDLING_VALG,
	RISK_ACTION_STATUS_VALG,
	RiskAction,
	RiskScenario,
	RiskScope,
	System,
)
from systemoversikt.risk_criteria import (
	konsekvens_lookup_label,
	level_cell_css_class,
	meta_choices,
	parse_kit_dimensjoner,
	risk_cell_css_class,
	sannsynlighet_lookup_label,
)
from systemoversikt.views_risiko import _get_owned_scope, _get_owned_scenario

RISIKOBEHANDLING_VALUES = {v for v, _ in RISIKOBEHANDLING_VALG}
TILTAK_STATUS_VALUES = {v for v, _ in RISK_ACTION_STATUS_VALG}


def _json_error(message, status=400):
	return JsonResponse({'ok': False, 'error': message}, status=status)


def _parse_json_body(request):
	try:
		if not request.body:
			return {}
		return json.loads(request.body.decode('utf-8'))
	except (json.JSONDecodeError, UnicodeDecodeError):
		return None


def _parse_level(value):
	if value is None or value == '':
		return None
	try:
		n = int(value)
	except (TypeError, ValueError):
		return 'invalid'
	if 1 <= n <= 5:
		return n
	return 'invalid'


def _parse_date(value):
	if value is None or value == '':
		return None
	if isinstance(value, str):
		try:
			return datetime.strptime(value.strip()[:10], '%Y-%m-%d').date()
		except ValueError:
			return 'invalid'
	return 'invalid'


def _system_to_dict(system):
	return {
		'id': system.pk,
		'label': str(system),
		'url': reverse('systemdetaljer', kwargs={'pk': system.pk}),
	}


def _action_to_dict(action):
	return {
		'id': action.pk,
		'tiltak_nr': action.tiltak_nr,
		'beskrivelse': action.beskrivelse,
		'ansvarlig': action.ansvarlig,
		'frist': action.frist.isoformat() if action.frist else None,
		'status': action.status,
		'status_display': action.get_status_display(),
		'kilde': action.kilde,
	}


def _scenario_summary_dict(scenario):
	systems = [_system_to_dict(s) for s in scenario.systemer.all()]
	return {
		'id': scenario.pk,
		'risk_id': scenario.risk_id,
		'uonsket_hendelse': scenario.uonsket_hendelse,
		'kit_dimensjoner': scenario.kit_dimensjoner,
		'kit_tags': parse_kit_dimensjoner(scenario.kit_dimensjoner),
		'konsekvens_nivaa': scenario.konsekvens_nivaa,
		'sannsynlighet_nivaa': scenario.sannsynlighet_nivaa,
		'konsekvens_label': konsekvens_lookup_label(scenario.konsekvens_nivaa),
		'sannsynlighet_label': sannsynlighet_lookup_label(scenario.sannsynlighet_nivaa),
		'konsekvens_css': level_cell_css_class(scenario.konsekvens_nivaa),
		'sannsynlighet_css': level_cell_css_class(scenario.sannsynlighet_nivaa),
		'risiko_etikett': scenario.risiko_etikett,
		'restrisiko_etikett': scenario.restrisiko_etikett,
		'risiko_css': risk_cell_css_class(scenario.risiko_etikett),
		'restrisiko_css': risk_cell_css_class(scenario.restrisiko_etikett),
		'action_count': len(list(scenario.actions.all())),
		'actions': [_action_to_dict(a) for a in scenario.actions.all()],
		'systemer': systems,
	}


def _scenario_to_dict(scenario):
	data = _scenario_summary_dict(scenario)
	data.update({
		'arsaker_svakheter': scenario.arsaker_svakheter,
		'eksisterende_tiltak': scenario.eksisterende_tiltak,
		'konsekvens_begrunnelse': scenario.konsekvens_begrunnelse,
		'sannsynlighetsbegrunnelse': scenario.sannsynlighetsbegrunnelse,
		'risikobehandling': scenario.risikobehandling,
		'risikobehandling_display': scenario.get_risikobehandling_display() or '',
		'konsekvens_etter': scenario.konsekvens_etter,
		'sannsynlighet_etter': scenario.sannsynlighet_etter,
		'rekkefolge': scenario.rekkefolge,
		'actions': [_action_to_dict(a) for a in scenario.actions.all()],
	})
	return data


def _level_counts(scenarios):
	current = {'Lav': 0, 'Middels': 0, 'Høy': 0}
	residual = {'Lav': 0, 'Middels': 0, 'Høy': 0}
	for scenario in scenarios:
		cur = scenario.risiko_etikett or ''
		res = scenario.restrisiko_etikett or ''
		if cur in current:
			current[cur] += 1
		if res in residual:
			residual[res] += 1
	return {'current': current, 'residual': residual}


def _suggest_next_risk_id(scope):
	max_num = 0
	for risk_id in scope.scenarios.values_list('risk_id', flat=True):
		digits = ''.join(c for c in risk_id if c.isdigit())
		if digits:
			max_num = max(max_num, int(digits))
	return 'R%d' % (max_num + 1)


def _validate_scenario_fields(data, scope, scenario=None):
	errors = []
	risk_id = (data.get('risk_id') or '').strip()
	if not risk_id:
		errors.append('RiskID er påkrevd.')
	elif len(risk_id) > 20:
		errors.append('RiskID er for lang.')
	else:
		qs = RiskScenario.objects.filter(scope=scope, risk_id=risk_id)
		if scenario:
			qs = qs.exclude(pk=scenario.pk)
		if qs.exists():
			errors.append('RiskID %s finnes allerede i denne samlingen.' % risk_id)

	uonsket = (data.get('uonsket_hendelse') or '').strip()
	if not uonsket:
		errors.append('Uønsket hendelse er påkrevd.')

	level_fields = (
		('konsekvens_nivaa', 'Konsekvens'),
		('sannsynlighet_nivaa', 'Sannsynlighet'),
		('konsekvens_etter', 'Konsekvens etter tiltak'),
		('sannsynlighet_etter', 'Sannsynlighet etter tiltak'),
	)
	parsed_levels = {}
	for field, label in level_fields:
		val = _parse_level(data.get(field))
		if val == 'invalid':
			errors.append('%s må være 1–5 eller tom.' % label)
		else:
			parsed_levels[field] = val

	risikobehandling = data.get('risikobehandling') or ''
	if risikobehandling and risikobehandling not in RISIKOBEHANDLING_VALUES:
		errors.append('Ugyldig risikobehandling.')

	system_ids = data.get('system_ids')
	if system_ids is not None:
		if not isinstance(system_ids, list):
			errors.append('system_ids må være en liste.')
		else:
			try:
				system_ids = [int(x) for x in system_ids]
			except (TypeError, ValueError):
				errors.append('Ugyldige system-IDer.')
			else:
				found = set(System.objects.filter(pk__in=system_ids).values_list('pk', flat=True))
				unknown = set(system_ids) - found
				if unknown:
					errors.append('Ukjente system-IDer: %s' % ', '.join(map(str, sorted(unknown))))

	if errors:
		return None, errors

	return {
		'risk_id': risk_id,
		'uonsket_hendelse': uonsket,
		'kit_dimensjoner': (data.get('kit_dimensjoner') or '').strip(),
		'arsaker_svakheter': (data.get('arsaker_svakheter') or '').strip(),
		'eksisterende_tiltak': (data.get('eksisterende_tiltak') or '').strip(),
		'konsekvens_begrunnelse': (data.get('konsekvens_begrunnelse') or '').strip(),
		'sannsynlighetsbegrunnelse': (data.get('sannsynlighetsbegrunnelse') or '').strip(),
		'risikobehandling': risikobehandling,
		'system_ids': system_ids if system_ids is not None else None,
		**parsed_levels,
	}, []


def _validate_action_item(item, index):
	errors = []
	if not isinstance(item, dict):
		return None, ['Tiltak %d: ugyldig data.' % index]

	beskrivelse = (item.get('beskrivelse') or '').strip()
	if not beskrivelse:
		errors.append('Tiltak %d: beskrivelse er påkrevd.' % index)

	try:
		tiltak_nr = int(item.get('tiltak_nr') or index)
	except (TypeError, ValueError):
		errors.append('Tiltak %d: ugyldig nummer.' % index)
		tiltak_nr = index

	status = item.get('status') or 'ikke_startet'
	if status not in TILTAK_STATUS_VALUES:
		errors.append('Tiltak %d: ugyldig status.' % index)

	frist = _parse_date(item.get('frist'))
	if frist == 'invalid':
		errors.append('Tiltak %d: ugyldig frist.' % index)
		frist = None

	action_id = item.get('id')
	if action_id is not None:
		try:
			action_id = int(action_id)
		except (TypeError, ValueError):
			errors.append('Tiltak %d: ugyldig id.' % index)
			action_id = None

	if errors:
		return None, errors

	return {
		'id': action_id,
		'tiltak_nr': tiltak_nr,
		'beskrivelse': beskrivelse,
		'ansvarlig': (item.get('ansvarlig') or '').strip(),
		'frist': frist,
		'status': status,
	}, []


def _sync_actions(scenario, actions_data):
	existing = {a.pk: a for a in scenario.actions.all()}
	keep_ids = set()
	for index, item in enumerate(actions_data, start=1):
		parsed, errors = _validate_action_item(item, index)
		if errors:
			raise ValueError('; '.join(errors))
		if parsed['id'] and parsed['id'] in existing:
			action = existing[parsed['id']]
			keep_ids.add(action.pk)
			action.tiltak_nr = parsed['tiltak_nr']
			action.beskrivelse = parsed['beskrivelse']
			action.ansvarlig = parsed['ansvarlig']
			action.frist = parsed['frist']
			action.status = parsed['status']
			action.save()
		else:
			RiskAction.objects.create(
				scenario=scenario,
				tiltak_nr=parsed['tiltak_nr'],
				beskrivelse=parsed['beskrivelse'],
				ansvarlig=parsed['ansvarlig'],
				frist=parsed['frist'],
				status=parsed['status'],
				kilde='manual',
			)
	for pk, action in existing.items():
		if pk not in keep_ids:
			action.delete()


def _apply_scenario_fields(scenario, fields):
	for attr in (
		'risk_id', 'uonsket_hendelse', 'kit_dimensjoner', 'arsaker_svakheter',
		'eksisterende_tiltak', 'konsekvens_begrunnelse', 'sannsynlighetsbegrunnelse',
		'risikobehandling', 'konsekvens_nivaa', 'sannsynlighet_nivaa',
		'konsekvens_etter', 'sannsynlighet_etter',
	):
		setattr(scenario, attr, fields[attr])
	scenario.save()
	if fields.get('system_ids') is not None:
		scenario.systemer.set(fields['system_ids'])


def _require_owner_json(request, scope_id):
	try:
		return _get_owned_scope(request, scope_id), None
	except Http404:
		return None, _json_error('forbidden', status=403)


def _reload_scenario(scenario_id):
	return RiskScenario.objects.prefetch_related('systemer', 'actions').get(pk=scenario_id)


@require_GET
def api_risiko_meta(request, pk):
	scope, err = _require_owner_json(request, pk)
	if err:
		return err
	return JsonResponse({'ok': True, 'meta': meta_choices()})


@require_GET
def api_risiko_scenarios_list(request, pk):
	scope, err = _require_owner_json(request, pk)
	if err:
		return err
	scenarios = list(
		scope.scenarios.prefetch_related('systemer', 'actions')
		.order_by('rekkefolge', 'risk_id')
	)
	return JsonResponse({
		'ok': True,
		'scenarios': [_scenario_summary_dict(s) for s in scenarios],
		'level_counts': _level_counts(scenarios),
	})


@require_GET
def api_risiko_scenario_detail(request, pk, sid):
	try:
		scope, scenario = _get_owned_scenario(request, pk, sid)
	except Http404:
		return _json_error('forbidden', status=403)
	scenario = _reload_scenario(scenario.pk)
	return JsonResponse({'ok': True, 'scenario': _scenario_to_dict(scenario)})


@require_http_methods(['POST'])
def api_risiko_scenario_create(request, pk):
	scope, err = _require_owner_json(request, pk)
	if err:
		return err
	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	if not data.get('risk_id'):
		data['risk_id'] = _suggest_next_risk_id(scope)

	fields, errors = _validate_scenario_fields(data, scope)
	if errors:
		return _json_error('; '.join(errors))

	max_rekke = scope.scenarios.aggregate(m=Max('rekkefolge'))['m'] or 0

	try:
		with transaction.atomic():
			scenario = RiskScenario.objects.create(
				scope=scope,
				rekkefolge=max_rekke + 1,
				risk_id=fields['risk_id'],
				uonsket_hendelse=fields['uonsket_hendelse'],
				kit_dimensjoner=fields['kit_dimensjoner'],
				arsaker_svakheter=fields['arsaker_svakheter'],
				eksisterende_tiltak=fields['eksisterende_tiltak'],
				konsekvens_begrunnelse=fields['konsekvens_begrunnelse'],
				sannsynlighetsbegrunnelse=fields['sannsynlighetsbegrunnelse'],
				risikobehandling=fields['risikobehandling'],
				konsekvens_nivaa=fields['konsekvens_nivaa'],
				sannsynlighet_nivaa=fields['sannsynlighet_nivaa'],
				konsekvens_etter=fields['konsekvens_etter'],
				sannsynlighet_etter=fields['sannsynlighet_etter'],
			)
			if fields.get('system_ids') is not None:
				scenario.systemer.set(fields['system_ids'])
			if 'actions' in data:
				_sync_actions(scenario, data.get('actions') or [])
	except ValueError as exc:
		return _json_error(str(exc))

	scenario = _reload_scenario(scenario.pk)
	scenarios = list(scope.scenarios.prefetch_related('systemer', 'actions').order_by('rekkefolge', 'risk_id'))
	return JsonResponse({
		'ok': True,
		'scenario': _scenario_to_dict(scenario),
		'level_counts': _level_counts(scenarios),
	}, status=201)


@require_http_methods(['PATCH', 'POST'])
def api_risiko_scenario_update(request, pk, sid):
	try:
		scope, scenario = _get_owned_scenario(request, pk, sid)
	except Http404:
		return _json_error('forbidden', status=403)

	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	fields, errors = _validate_scenario_fields(data, scope, scenario=scenario)
	if errors:
		return _json_error('; '.join(errors))

	try:
		with transaction.atomic():
			_apply_scenario_fields(scenario, fields)
			if 'actions' in data:
				_sync_actions(scenario, data.get('actions') or [])
	except ValueError as exc:
		return _json_error(str(exc))

	scenario = _reload_scenario(scenario.pk)
	scenarios = list(scope.scenarios.prefetch_related('systemer', 'actions').order_by('rekkefolge', 'risk_id'))
	return JsonResponse({
		'ok': True,
		'scenario': _scenario_to_dict(scenario),
		'level_counts': _level_counts(scenarios),
	})


@require_http_methods(['DELETE', 'POST'])
def api_risiko_scenario_delete(request, pk, sid):
	try:
		scope, scenario = _get_owned_scenario(request, pk, sid)
	except Http404:
		return _json_error('forbidden', status=403)

	if request.method == 'POST':
		data = _parse_json_body(request) or {}
		if data.get('_method') != 'DELETE':
			return _json_error('invalid_method', status=405)

	scenario.delete()
	scenarios = list(scope.scenarios.prefetch_related('systemer', 'actions').order_by('rekkefolge', 'risk_id'))
	return JsonResponse({
		'ok': True,
		'level_counts': _level_counts(scenarios),
	})


@require_http_methods(['PATCH', 'POST'])
def api_risiko_scope_update(request, pk):
	scope, err = _require_owner_json(request, pk)
	if err:
		return err

	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	title = (data.get('title') or '').strip()
	if not title:
		return _json_error('Navn kan ikke være tomt.')

	beskrivelse = (data.get('beskrivelse') or '').strip()
	sist_revidert_raw = (data.get('sist_revidert') or '').strip()
	sist_revidert = scope.sist_revidert
	if sist_revidert_raw:
		parsed = _parse_date(sist_revidert_raw)
		if parsed == 'invalid':
			return _json_error('Ugyldig dato – bruk format ÅÅÅÅ-MM-DD.')
		sist_revidert = parsed

	scope.title = title
	scope.beskrivelse = beskrivelse
	scope.sist_revidert = sist_revidert
	scope.save()

	return JsonResponse({
		'ok': True,
		'scope': {
			'title': scope.title,
			'beskrivelse': scope.beskrivelse,
			'sist_revidert': scope.sist_revidert.isoformat(),
		},
	})


@require_GET
def api_risiko_systemer_sok(request):
	if not request.user.has_perm('systemoversikt.view_system'):
		return _json_error('forbidden', status=403)

	q = request.GET.get('q', '').strip()
	if len(q) < 2:
		return JsonResponse({'ok': True, 'results': []})

	systems = (
		System.objects.filter(systemnavn__icontains=q)
		.order_by('systemnavn')[:15]
	)
	return JsonResponse({
		'ok': True,
		'results': [_system_to_dict(s) for s in systems],
	})


@require_http_methods(['POST'])
def api_risiko_action_create(request, pk, sid):
	try:
		scope, scenario = _get_owned_scenario(request, pk, sid)
	except Http404:
		return _json_error('forbidden', status=403)

	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	parsed, errors = _validate_action_item(data, 1)
	if errors:
		return _json_error('; '.join(errors))

	action = RiskAction.objects.create(
		scenario=scenario,
		tiltak_nr=parsed['tiltak_nr'],
		beskrivelse=parsed['beskrivelse'],
		ansvarlig=parsed['ansvarlig'],
		frist=parsed['frist'],
		status=parsed['status'],
		kilde='manual',
	)
	return JsonResponse({'ok': True, 'action': _action_to_dict(action)}, status=201)


@require_http_methods(['PATCH', 'POST'])
def api_risiko_action_update(request, pk, sid, aid):
	try:
		scope, scenario = _get_owned_scenario(request, pk, sid)
	except Http404:
		return _json_error('forbidden', status=403)

	action = get_object_or_404(RiskAction, pk=aid, scenario=scenario)
	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	data['id'] = action.pk
	parsed, errors = _validate_action_item(data, 1)
	if errors:
		return _json_error('; '.join(errors))

	action.tiltak_nr = parsed['tiltak_nr']
	action.beskrivelse = parsed['beskrivelse']
	action.ansvarlig = parsed['ansvarlig']
	action.frist = parsed['frist']
	action.status = parsed['status']
	action.save()

	return JsonResponse({'ok': True, 'action': _action_to_dict(action)})


@require_http_methods(['DELETE', 'POST'])
def api_risiko_action_delete(request, pk, sid, aid):
	try:
		scope, scenario = _get_owned_scenario(request, pk, sid)
	except Http404:
		return _json_error('forbidden', status=403)

	action = get_object_or_404(RiskAction, pk=aid, scenario=scenario)

	if request.method == 'POST':
		data = _parse_json_body(request) or {}
		if data.get('_method') != 'DELETE':
			return _json_error('invalid_method', status=405)

	action.delete()
	return JsonResponse({'ok': True})
