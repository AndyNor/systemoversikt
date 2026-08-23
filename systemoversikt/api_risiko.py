# -*- coding: utf-8 -*-
# Change log:
# 2026-08-23: Unauthenticated risk JSON APIs return 401 session_expired (not 403).
# 2026-08-13: Person search uses shared risk_user_search (AND terms, email + virksomhet rank).
# 2026-08-13: Unntak CRUD APIs on collection tiltak; unntak_count in action payloads.
# 2026-08-10: Log scenario/tiltak/member activity to RiskActivityLog (create/delete/status/levels).
# 2026-07-09: api_risiko_scope_update – log scope_status_changed to RiskActivityLog.
# 2026-07-07: Scenario sannsynlighetstyper validated against active criteria slugs (editable in akseptkriterier).
# 2026-07-07: Member and bruker search labels include virksomhetsforkortelse – disambiguate same-name users.
# 2026-07-07: Omfang figur/original multipart upload APIs – bytes stored on RiskScopeOmfangFil.
# 2026-07-02: Participant group search returns first 5 without query; display normalized gruppenavn.
# 2026-07-02: Rename RiskVirksomhetReadGroup → RiskVirksomhetGroup in participant group APIs.
# 2026-07-01: Read-group access – GET APIs use readable scope; writes still require membership.
# 2026-07-01: Godkjent status locks collection – reject content mutations; owner may change status only.
# 2026-07-06: RiskAction.eskaleres in tiltak API payloads and validation.
# 2026-07-01: Tiltak ansvarlig search (virksomhet-scoped) and ansvarlig_display in action payloads.
# 2026-06-30: RiskScope status – workflow validation; sannsynlighetstyper on scenarios.
# 2026-06-30: api_risiko_meta uses global get_active_criteria() for editor dropdowns and matrix.
# 2026-06-30: Scenario konsekvenstyper – validate, save, serialize in scenario API.
# 2026-06-30: Tiltak status forslag/besluttet – default forslag for new tiltak; accept ikke_startet alias.
# 2026-06-30: Member vs owner API gates; membership and virksomhet management endpoints.
# 2026-06-26: Scope-level tiltak API; scenario save no longer syncs actions; drop eksisterende_tiltak.
# 2026-06-26: Scenario summary includes display_tiltak_ids for scenario table Tiltak column.
# 2026-06-26: Display-time R/T IDs; scope-level tiltak reused across scenarios via M2M.
# 2026-06-25: Scenario summary includes konsekvens/sannsynlighet lookup labels for table display.
# 2026-06-25: Scenario summary includes CSS classes for colored table cells.
# 2026-06-24: Scenario list API includes actions for tiltak section refresh.
# 2026-06-24: JSON API for risk scenario/tiltak AJAX editor (owner-only).

import json
from datetime import datetime

from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max, Q, Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from systemoversikt.models import (
	RISIKOBEHANDLING_VALG,
	RISK_ACTION_STATUS_VALG,
	RISK_SCOPE_MEMBER_ROLE_OWNER,
	RISK_SCOPE_MEMBER_ROLE_PARTICIPANT,
	RISK_SCOPE_STATUS_OWNER_ONLY,
	RISK_SCOPE_STATUS_VALG,
	RiskAction,
	RiskActionUnntak,
	RiskScenario,
	RiskScope,
	RiskScopeMember,
	RiskScopeOmfangFil,
	RiskVirksomhetGroup,
	System,
	Virksomhet,
)
from systemoversikt.risk_criteria import (
	get_active_criteria,
	konsekvens_lookup_label,
	konsekvenstype_tag_dicts,
	konsekvenstype_to_storage,
	level_cell_css_class,
	parse_kit_dimensjoner,
	parse_konsekvenstyper,
	parse_sannsynlighetstyper,
	risk_cell_css_class,
	sannsynlighet_lookup_label,
	sannsynlighetstype_tag_dicts,
	sannsynlighetstype_to_storage,
)
from systemoversikt.risk_files import (
	clear_figur_fields,
	clear_original_fields,
	guess_content_type,
	read_upload_bytes,
	validate_omfang_figur,
	validate_omfang_original,
)
from systemoversikt.risk_display import (
	annotate_scenario_display_ids,
	build_ansvarlig_display_map,
	build_scope_tiltak_rows,
	resolve_ansvarlig_display,
	scenario_display_tiltak_ids,
	tiltak_display_id_map,
	user_ansvarlig_display_name,
)
from systemoversikt.risk_activity_log import (
	RISK_ACTIVITY_ACTION_CREATED,
	RISK_ACTIVITY_ACTION_DELETED,
	RISK_ACTIVITY_ACTION_STATUS_CHANGED,
	RISK_ACTIVITY_MEMBER_ADDED,
	RISK_ACTIVITY_MEMBER_REMOVED,
	RISK_ACTIVITY_SCENARIO_CREATED,
	RISK_ACTIVITY_SCENARIO_DELETED,
	RISK_ACTIVITY_SCENARIO_RISK_LEVEL_CHANGED,
	RISK_ACTIVITY_SCENARIO_TREATMENT_CHANGED,
	RISK_ACTIVITY_SCOPE_STATUS_CHANGED,
	RISK_ACTIVITY_UNNTAK_CREATED,
	RISK_ACTIVITY_UNNTAK_DELETED,
	RISK_ACTIVITY_UNNTAK_UPDATED,
	log_risk_activity,
)
from systemoversikt.risk_membership import (
	normalize_risk_group_title,
	user_display_name,
	user_member_display_name,
	user_virksomhetsforkortelse,
)
from systemoversikt.risk_user_search import (
	preferred_virksomhet_for_scope,
	search_active_users,
)
from systemoversikt.views_risiko import (
	RiskApiUnauthorized,
	_get_managed_scope,
	_get_member_scope,
	_get_member_scenario,
	_get_readable_scope,
	_get_writable_scenario,
	_is_scope_owner,
)

RISIKOBEHANDLING_VALUES = {v for v, _ in RISIKOBEHANDLING_VALG}
TILTAK_STATUS_VALUES = {v for v, _ in RISK_ACTION_STATUS_VALG}
RISK_SCOPE_STATUS_VALUES = {v for v, _ in RISK_SCOPE_STATUS_VALG}


def _json_error(message, status=400):
	return JsonResponse({'ok': False, 'error': message}, status=status)


def _access_denied_json(exc):
	# 2026-08-23: Map RiskApiUnauthorized → 401 so AJAX clients can prompt re-login.
	if isinstance(exc, RiskApiUnauthorized):
		return _json_error('session_expired', status=401)
	return _json_error('forbidden', status=403)


def _require_member_json(request, scope_id):
	try:
		return _get_member_scope(request, scope_id), None
	except (Http404, RiskApiUnauthorized) as exc:
		return None, _access_denied_json(exc)


def _require_read_json(request, scope_id):
	try:
		return _get_readable_scope(request, scope_id), None
	except (Http404, RiskApiUnauthorized) as exc:
		return None, _access_denied_json(exc)


def _require_managed_json(request, scope_id):
	try:
		return _get_managed_scope(request, scope_id), None
	except (Http404, RiskApiUnauthorized) as exc:
		return None, _access_denied_json(exc)


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


def _ansvarlig_display_map_for_actions(actions):
	return build_ansvarlig_display_map(
		[a.ansvarlig for a in actions if getattr(a, 'ansvarlig', None)]
	)


def _action_to_dict(action, display_tiltak_id=None, risk_ids=None, scenario_ids=None, ansvarlig_display_map=None):
	ansvarlig_display = ''
	if action.ansvarlig:
		ansvarlig_display = resolve_ansvarlig_display(action.ansvarlig, ansvarlig_display_map)
	unntak_list = getattr(action, '_prefetched_objects_cache', {}).get('unntak')
	if unntak_list is not None:
		unntak_count = len(unntak_list)
		unntak_payload = [_unntak_to_dict(u) for u in unntak_list]
	else:
		unntak_count = action.unntak.count() if action.pk else 0
		unntak_payload = None
	data = {
		'id': action.pk,
		'display_tiltak_id': display_tiltak_id or '',
		'beskrivelse': action.beskrivelse,
		'ansvarlig': action.ansvarlig,
		'ansvarlig_display': ansvarlig_display,
		'frist': action.frist.isoformat() if action.frist else None,
		'status': action.status,
		'status_display': action.get_status_display(),
		'kilde': action.kilde,
		'eskaleres': action.eskaleres,
		'unntak_count': unntak_count,
	}
	if unntak_payload is not None:
		data['unntak'] = unntak_payload
	if risk_ids is not None:
		data['risk_ids'] = risk_ids
	if scenario_ids is not None:
		data['scenario_ids'] = scenario_ids
	return data


def _unntak_to_dict(unntak):
	systems = []
	# Prefer prefetched M2M when available.
	try:
		systems = [_system_to_dict(s) for s in unntak.systemer.all()]
	except Exception:
		systems = []
	return {
		'id': unntak.pk,
		'beskrivelse': unntak.beskrivelse or '',
		'begrunnelse': unntak.begrunnelse or '',
		'gyldig_til': unntak.gyldig_til.isoformat() if unntak.gyldig_til else None,
		'aktiv': bool(unntak.aktiv),
		'systemer': systems,
	}


def _load_scope_scenarios(scope):
	return list(
		scope.scenarios.prefetch_related(
			'systemer',
			'actions',
			'actions__unntak',
			'actions__unntak__systemer',
		)
		.order_by('rekkefolge', 'risk_id')
	)


def _load_scope_actions(scope):
	return list(
		scope.actions.prefetch_related('scenarios', 'unntak', 'unntak__systemer')
		.order_by('pk')
	)


def _scenario_summary_dict(scenario, tiltak_id_map=None, risk_id_by_pk=None, ansvarlig_display_map=None):
	systems = [_system_to_dict(s) for s in scenario.systemer.all()]
	display_risk_id = getattr(scenario, 'display_risk_id', None)
	if not display_risk_id and risk_id_by_pk:
		display_risk_id = risk_id_by_pk.get(scenario.pk, '')
	actions = list(scenario.actions.all())
	action_dicts = []
	for action in actions:
		tid = (tiltak_id_map or {}).get(action.pk, '')
		action_dicts.append(_action_to_dict(
			action,
			display_tiltak_id=tid,
			ansvarlig_display_map=ansvarlig_display_map,
		))
	display_tiltak_ids = (
		scenario_display_tiltak_ids(scenario, tiltak_id_map)
		if tiltak_id_map else '–'
	)
	return {
		'id': scenario.pk,
		'display_risk_id': display_risk_id or '',
		'uonsket_hendelse': scenario.uonsket_hendelse,
		'kit_dimensjoner': scenario.kit_dimensjoner,
		'kit_tags': parse_kit_dimensjoner(scenario.kit_dimensjoner),
		'konsekvenstyper': parse_konsekvenstyper(scenario.konsekvenstyper),
		'konsekvenstype_tags': konsekvenstype_tag_dicts(scenario.konsekvenstyper),
		'sannsynlighetstyper': parse_sannsynlighetstyper(scenario.sannsynlighetstyper),
		'sannsynlighetstype_tags': sannsynlighetstype_tag_dicts(scenario.sannsynlighetstyper),
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
		'action_count': len(actions),
		'display_tiltak_ids': display_tiltak_ids,
		'actions': action_dicts,
		'systemer': systems,
	}


def _scenario_to_dict(scenario, tiltak_id_map=None, risk_id_by_pk=None, ansvarlig_display_map=None):
	data = _scenario_summary_dict(scenario, tiltak_id_map, risk_id_by_pk, ansvarlig_display_map)
	data.update({
		'arsaker_svakheter': scenario.arsaker_svakheter,
		'konsekvens_begrunnelse': scenario.konsekvens_begrunnelse,
		'sannsynlighetsbegrunnelse': scenario.sannsynlighetsbegrunnelse,
		'risikobehandling': scenario.risikobehandling,
		'risikobehandling_display': scenario.get_risikobehandling_display() or '',
		'konsekvens_etter': scenario.konsekvens_etter,
		'sannsynlighet_etter': scenario.sannsynlighet_etter,
		'rekkefolge': scenario.rekkefolge,
	})
	return data


def _tiltak_list_dict(scope, scenarios, actions, ansvarlig_display_map=None):
	if ansvarlig_display_map is None:
		ansvarlig_display_map = _ansvarlig_display_map_for_actions(actions)
	risk_id_by_pk = annotate_scenario_display_ids(scenarios)
	tiltak_map = tiltak_display_id_map(actions)
	rows = build_scope_tiltak_rows(scenarios, actions, risk_id_by_pk)
	result = []
	for row in rows:
		action = row['action']
		entry = _action_to_dict(
			action,
			display_tiltak_id=row['display_tiltak_id'],
			risk_ids=[link['risk_id'] for link in row['risk_links']],
			scenario_ids=[link['scenario_pk'] for link in row['risk_links']],
			ansvarlig_display_map=ansvarlig_display_map,
		)
		entry['risk_links'] = row['risk_links']
		result.append(entry)
	return result, tiltak_map, risk_id_by_pk


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


def _auto_risk_id(scope):
	"""Internal uniquifier for DB; display uses position-based R# instead."""
	count = scope.scenarios.count()
	return 'R%d' % (count + 1)


def _validate_scenario_fields(data, scope, scenario=None):
	errors = []

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

	raw_konsekvenstyper = data.get('konsekvenstyper', [])
	if raw_konsekvenstyper is None:
		konsekvenstyper_parts = []
	elif isinstance(raw_konsekvenstyper, str):
		konsekvenstyper_parts = [p.strip() for p in raw_konsekvenstyper.split(',') if p.strip()]
	elif isinstance(raw_konsekvenstyper, list):
		konsekvenstyper_parts = [str(p).strip() for p in raw_konsekvenstyper if str(p).strip()]
	else:
		errors.append('konsekvenstyper må være en liste.')
		konsekvenstyper_parts = []
	unknown_konsekvenstyper = sorted({p for p in konsekvenstyper_parts if p not in get_active_criteria().konsekvenstype_slugs})
	if unknown_konsekvenstyper:
		errors.append('Ugyldige konsekvenstyper: %s' % ', '.join(unknown_konsekvenstyper))

	raw_sannsynlighetstyper = data.get('sannsynlighetstyper', [])
	if raw_sannsynlighetstyper is None:
		sannsynlighetstyper_parts = []
	elif isinstance(raw_sannsynlighetstyper, str):
		sannsynlighetstyper_parts = [p.strip() for p in raw_sannsynlighetstyper.split(',') if p.strip()]
	elif isinstance(raw_sannsynlighetstyper, list):
		sannsynlighetstyper_parts = [str(p).strip() for p in raw_sannsynlighetstyper if str(p).strip()]
	else:
		errors.append('sannsynlighetstyper må være en liste.')
		sannsynlighetstyper_parts = []
	unknown_sannsynlighetstyper = sorted({
		p for p in sannsynlighetstyper_parts if p not in get_active_criteria().sannsynlighetstype_slugs
	})
	if unknown_sannsynlighetstyper:
		errors.append('Ugyldige sannsynlighetstyper: %s' % ', '.join(unknown_sannsynlighetstyper))

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
		'uonsket_hendelse': uonsket,
		'kit_dimensjoner': (data.get('kit_dimensjoner') or '').strip(),
		'konsekvenstyper': konsekvenstype_to_storage(konsekvenstyper_parts),
		'sannsynlighetstyper': sannsynlighetstype_to_storage(sannsynlighetstyper_parts),
		'arsaker_svakheter': (data.get('arsaker_svakheter') or '').strip(),
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
		int(item.get('tiltak_nr') or 0)
	except (TypeError, ValueError):
		pass

	status = item.get('status') or 'forslag'
	if status == 'ikke_startet':
		status = 'besluttet'
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
		'beskrivelse': beskrivelse,
		'ansvarlig': (item.get('ansvarlig') or '').strip(),
		'frist': frist,
		'status': status,
		'eskaleres': bool(item.get('eskaleres')),
	}, []


def _parse_scenario_ids(raw):
	if raw is None:
		return None
	if not isinstance(raw, (list, tuple)):
		return 'invalid'
	ids = []
	for value in raw:
		try:
			ids.append(int(value))
		except (TypeError, ValueError):
			return 'invalid'
	return ids


def _validate_scenario_ids(scope, scenario_ids):
	if scenario_ids == 'invalid':
		return None, ['Ugyldige scenario-IDer.']
	if not scenario_ids:
		return [], []
	found = set(
		RiskScenario.objects.filter(scope=scope, pk__in=scenario_ids).values_list('pk', flat=True)
	)
	unknown = set(scenario_ids) - found
	if unknown:
		return None, ['Ukjente scenario-IDer: %s' % ', '.join(map(str, sorted(unknown)))]
	return scenario_ids, []


def _apply_action_scenarios(action, scope, scenario_ids):
	if scenario_ids is None:
		return
	valid, errors = _validate_scenario_ids(scope, scenario_ids)
	if errors:
		raise ValueError('; '.join(errors))
	action.scenarios.set(valid)


def _tiltak_refresh_payload(scope):
	scenarios = _load_scope_scenarios(scope)
	actions = _load_scope_actions(scope)
	ansvarlig_display_map = _ansvarlig_display_map_for_actions(actions)
	tiltak_list, tiltak_map, risk_map = _tiltak_list_dict(
		scope, scenarios, actions, ansvarlig_display_map
	)
	return {
		'scenarios': [
			_scenario_summary_dict(s, tiltak_map, risk_map, ansvarlig_display_map)
			for s in scenarios
		],
		'tiltak': tiltak_list,
		'level_counts': _level_counts(scenarios),
	}


def _cleanup_orphan_actions(scope):
	for action in scope.actions.prefetch_related('scenarios'):
		if not action.scenarios.exists():
			action.delete()


def _apply_scenario_fields(scenario, fields):
	for attr in (
		'uonsket_hendelse', 'kit_dimensjoner', 'konsekvenstyper', 'sannsynlighetstyper',
		'arsaker_svakheter',
		'konsekvens_begrunnelse', 'sannsynlighetsbegrunnelse',
		'risikobehandling', 'konsekvens_nivaa', 'sannsynlighet_nivaa',
		'konsekvens_etter', 'sannsynlighet_etter',
	):
		setattr(scenario, attr, fields[attr])
	scenario.save()
	if fields.get('system_ids') is not None:
		scenario.systemer.set(fields['system_ids'])


def _log_snippet(text, limit=60):
	text = (text or '').strip().replace('\n', ' ')
	if len(text) <= limit:
		return text
	return text[:limit].rstrip() + '…'


def _level_pair_label(sannsynlighet, konsekvens):
	s_label = str(sannsynlighet) if sannsynlighet is not None else '–'
	k_label = str(konsekvens) if konsekvens is not None else '–'
	return 'S%s/K%s' % (s_label, k_label)


def _scenario_log_label(scenario):
	snippet = _log_snippet(scenario.uonsket_hendelse)
	risk_id = scenario.risk_id or ('#%s' % scenario.pk)
	if snippet:
		return '%s «%s»' % (risk_id, snippet)
	return risk_id


def _action_log_label(action, display_id=None):
	prefix = display_id or ('#%s' % action.pk)
	snippet = _log_snippet(action.beskrivelse)
	if snippet:
		return '%s «%s»' % (prefix, snippet)
	return prefix


def _log_scenario_create(request, scope, scenario):
	# 2026-08-10: Log scenario create for risk activity overview.
	log_risk_activity(
		RISK_ACTIVITY_SCENARIO_CREATED,
		'%s opprettet risiko %s.' % (
			request.user.get_username(),
			_scenario_log_label(scenario),
		),
		user=request.user,
		scope=scope,
	)


def _log_scenario_delete(request, scope, scenario):
	# 2026-08-10: Log scenario delete for risk activity overview.
	log_risk_activity(
		RISK_ACTIVITY_SCENARIO_DELETED,
		'%s slettet risiko %s.' % (
			request.user.get_username(),
			_scenario_log_label(scenario),
		),
		user=request.user,
		scope=scope,
	)


def _log_scenario_field_changes(request, scope, scenario, old_levels, old_treatment, fields):
	# 2026-08-10: Log risk-level and treatment changes when values actually change.
	username = request.user.get_username()
	label = _scenario_log_label(scenario)
	treatment_labels = dict(RISIKOBEHANDLING_VALG)

	current_changed = (
		old_levels['sannsynlighet_nivaa'] != fields['sannsynlighet_nivaa']
		or old_levels['konsekvens_nivaa'] != fields['konsekvens_nivaa']
	)
	residual_changed = (
		old_levels['sannsynlighet_etter'] != fields['sannsynlighet_etter']
		or old_levels['konsekvens_etter'] != fields['konsekvens_etter']
	)
	if current_changed or residual_changed:
		parts = []
		if current_changed:
			parts.append(
				'nåværende fra %s til %s' % (
					_level_pair_label(old_levels['sannsynlighet_nivaa'], old_levels['konsekvens_nivaa']),
					_level_pair_label(fields['sannsynlighet_nivaa'], fields['konsekvens_nivaa']),
				)
			)
		if residual_changed:
			parts.append(
				'restrisiko fra %s til %s' % (
					_level_pair_label(old_levels['sannsynlighet_etter'], old_levels['konsekvens_etter']),
					_level_pair_label(fields['sannsynlighet_etter'], fields['konsekvens_etter']),
				)
			)
		log_risk_activity(
			RISK_ACTIVITY_SCENARIO_RISK_LEVEL_CHANGED,
			'%s endret risiknivå på %s (%s).' % (username, label, '; '.join(parts)),
			user=request.user,
			scope=scope,
		)

	new_treatment = fields['risikobehandling']
	if old_treatment != new_treatment:
		log_risk_activity(
			RISK_ACTIVITY_SCENARIO_TREATMENT_CHANGED,
			'%s endret risikobehandling på %s fra %s til %s.' % (
				username,
				label,
				treatment_labels.get(old_treatment, old_treatment or '–'),
				treatment_labels.get(new_treatment, new_treatment or '–'),
			),
			user=request.user,
			scope=scope,
		)


def _log_action_create(request, scope, action, display_id=None):
	# 2026-08-10: Log tiltak create for risk activity overview.
	log_risk_activity(
		RISK_ACTIVITY_ACTION_CREATED,
		'%s opprettet tiltak %s.' % (
			request.user.get_username(),
			_action_log_label(action, display_id),
		),
		user=request.user,
		scope=scope,
	)


def _log_action_delete(request, scope, action, display_id=None):
	# 2026-08-10: Log tiltak delete for risk activity overview.
	log_risk_activity(
		RISK_ACTIVITY_ACTION_DELETED,
		'%s slettet tiltak %s.' % (
			request.user.get_username(),
			_action_log_label(action, display_id),
		),
		user=request.user,
		scope=scope,
	)


def _log_action_status_change(request, scope, action, old_status, new_status, display_id=None):
	# 2026-08-10: Log tiltak status change when status actually changes.
	if old_status == new_status:
		return
	status_labels = dict(RISK_ACTION_STATUS_VALG)
	log_risk_activity(
		RISK_ACTIVITY_ACTION_STATUS_CHANGED,
		'%s endret tiltakstatus på %s fra %s til %s.' % (
			request.user.get_username(),
			_action_log_label(action, display_id),
			status_labels.get(old_status, old_status),
			status_labels.get(new_status, new_status),
		),
		user=request.user,
		scope=scope,
	)


def _require_owner_json(request, scope_id):
	# Legacy name – content APIs use member access.
	return _require_member_json(request, scope_id)


def _reject_if_content_locked(scope):
	if scope.is_content_locked():
		return _json_error(
			'Risikosamlingen er godkjent og kan ikke redigeres. En eier må endre status for å åpne for redigering.',
			status=403,
		)
	return None


def _reload_scenario(scenario_id):
	return RiskScenario.objects.prefetch_related(
		'systemer',
		'actions',
		'actions__unntak',
		'actions__unntak__systemer',
	).get(pk=scenario_id)


def _scenario_response(scope, scenario):
	scenarios = _load_scope_scenarios(scope)
	actions = _load_scope_actions(scope)
	ansvarlig_display_map = _ansvarlig_display_map_for_actions(actions)
	tiltak_list, tiltak_map, risk_map = _tiltak_list_dict(
		scope, scenarios, actions, ansvarlig_display_map
	)
	scenario = _reload_scenario(scenario.pk)
	return {
		'scenario': _scenario_to_dict(scenario, tiltak_map, risk_map, ansvarlig_display_map),
		'scenarios': [
			_scenario_summary_dict(s, tiltak_map, risk_map, ansvarlig_display_map)
			for s in scenarios
		],
		'tiltak': tiltak_list,
		'level_counts': _level_counts(scenarios),
	}


@require_GET
def api_risiko_meta(request, pk):
	scope, err = _require_read_json(request, pk)
	if err:
		return err
	return JsonResponse({'ok': True, 'meta': get_active_criteria().meta_choices()})


@require_GET
def api_risiko_scenarios_list(request, pk):
	scope, err = _require_read_json(request, pk)
	if err:
		return err
	scenarios = _load_scope_scenarios(scope)
	actions = _load_scope_actions(scope)
	ansvarlig_display_map = _ansvarlig_display_map_for_actions(actions)
	tiltak_list, tiltak_map, risk_map = _tiltak_list_dict(
		scope, scenarios, actions, ansvarlig_display_map
	)
	return JsonResponse({
		'ok': True,
		'scenarios': [
			_scenario_summary_dict(s, tiltak_map, risk_map, ansvarlig_display_map)
			for s in scenarios
		],
		'tiltak': tiltak_list,
		'level_counts': _level_counts(scenarios),
	})


@require_GET
def api_risiko_scenario_detail(request, pk, sid):
	try:
		scope, scenario = _get_member_scenario(request, pk, sid)
	except (Http404, RiskApiUnauthorized) as exc:
		return _access_denied_json(exc)
	scenario = _reload_scenario(scenario.pk)
	scenarios = _load_scope_scenarios(scope)
	actions = _load_scope_actions(scope)
	ansvarlig_display_map = _ansvarlig_display_map_for_actions(actions)
	_, tiltak_map, risk_map = _tiltak_list_dict(scope, scenarios, actions, ansvarlig_display_map)
	return JsonResponse({
		'ok': True,
		'scenario': _scenario_to_dict(scenario, tiltak_map, risk_map, ansvarlig_display_map),
	})


@require_http_methods(['POST'])
def api_risiko_scenario_create(request, pk):
	scope, err = _require_owner_json(request, pk)
	if err:
		return err
	err = _reject_if_content_locked(scope)
	if err:
		return err
	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	fields, errors = _validate_scenario_fields(data, scope)
	if errors:
		return _json_error('; '.join(errors))

	max_rekke = scope.scenarios.aggregate(m=Max('rekkefolge'))['m'] or 0

	try:
		with transaction.atomic():
			scenario = RiskScenario.objects.create(
				scope=scope,
				rekkefolge=max_rekke + 1,
				risk_id=_auto_risk_id(scope),
				uonsket_hendelse=fields['uonsket_hendelse'],
				kit_dimensjoner=fields['kit_dimensjoner'],
				konsekvenstyper=fields['konsekvenstyper'],
				sannsynlighetstyper=fields['sannsynlighetstyper'],
				arsaker_svakheter=fields['arsaker_svakheter'],
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
	except ValueError as exc:
		return _json_error(str(exc))

	_log_scenario_create(request, scope, scenario)

	resp = _scenario_response(scope, scenario)
	return JsonResponse({'ok': True, **resp}, status=201)


@require_http_methods(['PATCH', 'POST'])
def api_risiko_scenario_update(request, pk, sid):
	try:
		scope, scenario = _get_writable_scenario(request, pk, sid)
	except (Http404, RiskApiUnauthorized) as exc:
		return _access_denied_json(exc)

	err = _reject_if_content_locked(scope)
	if err:
		return err

	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	fields, errors = _validate_scenario_fields(data, scope, scenario=scenario)
	if errors:
		return _json_error('; '.join(errors))

	old_levels = {
		'sannsynlighet_nivaa': scenario.sannsynlighet_nivaa,
		'konsekvens_nivaa': scenario.konsekvens_nivaa,
		'sannsynlighet_etter': scenario.sannsynlighet_etter,
		'konsekvens_etter': scenario.konsekvens_etter,
	}
	old_treatment = scenario.risikobehandling

	try:
		with transaction.atomic():
			_apply_scenario_fields(scenario, fields)
	except ValueError as exc:
		return _json_error(str(exc))

	_log_scenario_field_changes(request, scope, scenario, old_levels, old_treatment, fields)

	resp = _scenario_response(scope, scenario)
	return JsonResponse({'ok': True, **resp})


@require_http_methods(['DELETE', 'POST'])
def api_risiko_scenario_delete(request, pk, sid):
	try:
		scope, scenario = _get_writable_scenario(request, pk, sid)
	except (Http404, RiskApiUnauthorized) as exc:
		return _access_denied_json(exc)

	err = _reject_if_content_locked(scope)
	if err:
		return err

	if request.method == 'POST':
		data = _parse_json_body(request) or {}
		if data.get('_method') != 'DELETE':
			return _json_error('invalid_method', status=405)

	_log_scenario_delete(request, scope, scenario)
	scenario.delete()
	_cleanup_orphan_actions(scope)
	scenarios = _load_scope_scenarios(scope)
	actions = _load_scope_actions(scope)
	ansvarlig_display_map = _ansvarlig_display_map_for_actions(actions)
	tiltak_list, tiltak_map, risk_map = _tiltak_list_dict(
		scope, scenarios, actions, ansvarlig_display_map
	)
	return JsonResponse({
		'ok': True,
		'scenarios': [
			_scenario_summary_dict(s, tiltak_map, risk_map, ansvarlig_display_map)
			for s in scenarios
		],
		'tiltak': tiltak_list,
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

	# 2026-07-08: Archived scopes are read-only (archive replaces delete).
	if scope.archived_at is not None:
		return _json_error('Risikosamlingen er arkivert og kan ikke redigeres.', status=403)

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

	# 2026-07-01: Godkjent – only owners may change status; other fields must stay unchanged.
	if scope.is_content_locked():
		if not _is_scope_owner(request, scope):
			return _json_error(
				'Risikosamlingen er godkjent og kan ikke redigeres. En eier må endre status for å åpne for redigering.',
				status=403,
			)
		if (
			title != scope.title
			or beskrivelse != scope.beskrivelse
			or sist_revidert != scope.sist_revidert
		):
			return _json_error('Godkjente samlinger kan kun ha status endret.', status=403)

	new_status = scope.status
	if 'status' in data:
		status = (data.get('status') or '').strip()
		if status not in RISK_SCOPE_STATUS_VALUES:
			return _json_error('Ugyldig status.')
		if not _is_scope_owner(request, scope):
			if status != scope.status:
				if scope.status in RISK_SCOPE_STATUS_OWNER_ONLY:
					return _json_error('Kun eiere kan endre status etter at samlingen er sendt til godkjenning.', status=403)
				if status in RISK_SCOPE_STATUS_OWNER_ONLY:
					return _json_error('Kun eiere kan sette denne statusen.', status=403)
		new_status = status

	old_status = scope.status
	status_labels = dict(RISK_SCOPE_STATUS_VALG)
	scope.title = title
	scope.beskrivelse = beskrivelse
	scope.sist_revidert = sist_revidert
	scope.status = new_status
	scope.save()

	if new_status != old_status:
		log_risk_activity(
			RISK_ACTIVITY_SCOPE_STATUS_CHANGED,
			'%s endret status på «%s» fra %s til %s.' % (
				request.user.get_username(),
				scope.title,
				status_labels.get(old_status, old_status),
				status_labels.get(new_status, new_status),
			),
			user=request.user,
			scope=scope,
		)

	return JsonResponse({
		'ok': True,
		'scope': {
			'title': scope.title,
			'beskrivelse': scope.beskrivelse,
			'sist_revidert': scope.sist_revidert.isoformat(),
			'status': scope.status,
			'status_display': scope.get_status_display(),
		},
		'scope_status_choices': [
			{'value': value, 'label': label}
			for value, label in RISK_SCOPE_STATUS_VALG
			if value not in RISK_SCOPE_STATUS_OWNER_ONLY or _is_scope_owner(request, scope)
		],
	})


@require_GET
def api_risiko_systemer_sok(request):
	if not request.user.is_authenticated:
		return _json_error('session_expired', status=401)
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
		scope, scenario = _get_writable_scenario(request, pk, sid)
	except (Http404, RiskApiUnauthorized) as exc:
		return _access_denied_json(exc)

	err = _reject_if_content_locked(scope)
	if err:
		return err

	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	parsed, errors = _validate_action_item(data, 1)
	if errors:
		return _json_error('; '.join(errors))

	action = RiskAction.objects.create(
		scope=scope,
		beskrivelse=parsed['beskrivelse'],
		ansvarlig=parsed['ansvarlig'],
		frist=parsed['frist'],
		status=parsed['status'],
		eskaleres=parsed['eskaleres'],
		kilde='manual',
	)
	action.scenarios.add(scenario)
	scenarios = _load_scope_scenarios(scope)
	actions = _load_scope_actions(scope)
	tiltak_map = tiltak_display_id_map(actions)
	_log_action_create(request, scope, action, tiltak_map.get(action.pk))
	return JsonResponse({
		'ok': True,
		'action': _action_to_dict(action, tiltak_map.get(action.pk, '')),
	}, status=201)


@require_http_methods(['PATCH', 'POST'])
def api_risiko_action_update(request, pk, sid, aid):
	try:
		scope, scenario = _get_writable_scenario(request, pk, sid)
	except (Http404, RiskApiUnauthorized) as exc:
		return _access_denied_json(exc)

	err = _reject_if_content_locked(scope)
	if err:
		return err

	action = get_object_or_404(RiskAction, pk=aid, scope=scope)
	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	data['id'] = action.pk
	parsed, errors = _validate_action_item(data, 1)
	if errors:
		return _json_error('; '.join(errors))

	old_status = action.status
	action.beskrivelse = parsed['beskrivelse']
	action.ansvarlig = parsed['ansvarlig']
	action.frist = parsed['frist']
	action.status = parsed['status']
	action.eskaleres = parsed['eskaleres']
	action.save()

	scenarios = _load_scope_scenarios(scope)
	actions = _load_scope_actions(scope)
	tiltak_map = tiltak_display_id_map(actions)
	_log_action_status_change(
		request, scope, action, old_status, action.status, tiltak_map.get(action.pk)
	)
	risk_map = annotate_scenario_display_ids(scenarios)
	risk_ids = [
		risk_map.get(sc.pk, '')
		for sc in action.scenarios.all()
		if risk_map.get(sc.pk)
	]
	return JsonResponse({
		'ok': True,
		'action': _action_to_dict(action, tiltak_map.get(action.pk, ''), risk_ids),
	})


@require_http_methods(['DELETE', 'POST'])
def api_risiko_action_delete(request, pk, sid, aid):
	try:
		scope, scenario = _get_writable_scenario(request, pk, sid)
	except (Http404, RiskApiUnauthorized) as exc:
		return _access_denied_json(exc)

	err = _reject_if_content_locked(scope)
	if err:
		return err

	action = get_object_or_404(RiskAction, pk=aid, scope=scope)

	if request.method == 'POST':
		data = _parse_json_body(request) or {}
		if data.get('_method') != 'DELETE':
			return _json_error('invalid_method', status=405)

	tiltak_map = tiltak_display_id_map(_load_scope_actions(scope))
	_log_action_delete(request, scope, action, tiltak_map.get(action.pk))
	action.delete()
	return JsonResponse({'ok': True})


@require_http_methods(['POST'])
def api_risiko_scope_action_create(request, pk):
	scope, err = _require_owner_json(request, pk)
	if err:
		return err
	err = _reject_if_content_locked(scope)
	if err:
		return err

	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	parsed, errors = _validate_action_item(data, 1)
	if errors:
		return _json_error('; '.join(errors))

	scenario_ids = _parse_scenario_ids(data.get('scenario_ids'))
	if scenario_ids == 'invalid':
		return _json_error('Ugyldige scenario-IDer.')

	try:
		with transaction.atomic():
			action = RiskAction.objects.create(
				scope=scope,
				beskrivelse=parsed['beskrivelse'],
				ansvarlig=parsed['ansvarlig'],
				frist=parsed['frist'],
				status=parsed['status'],
				eskaleres=parsed['eskaleres'],
				kilde='manual',
			)
			_apply_action_scenarios(action, scope, scenario_ids if scenario_ids is not None else [])
	except ValueError as exc:
		return _json_error(str(exc))

	payload = _tiltak_refresh_payload(scope)
	tiltak_map = tiltak_display_id_map(_load_scope_actions(scope))
	_log_action_create(request, scope, action, tiltak_map.get(action.pk))
	return JsonResponse({
		'ok': True,
		'action': _action_to_dict(
			action,
			tiltak_map.get(action.pk, ''),
			scenario_ids=list(action.scenarios.values_list('pk', flat=True)),
		),
		**payload,
	}, status=201)


@require_http_methods(['PATCH', 'POST'])
def api_risiko_scope_action_update(request, pk, aid):
	scope, err = _require_owner_json(request, pk)
	if err:
		return err
	err = _reject_if_content_locked(scope)
	if err:
		return err

	action = get_object_or_404(RiskAction, pk=aid, scope=scope)
	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	data['id'] = action.pk
	parsed, errors = _validate_action_item(data, 1)
	if errors:
		return _json_error('; '.join(errors))

	scenario_ids = None
	if 'scenario_ids' in data:
		scenario_ids = _parse_scenario_ids(data.get('scenario_ids'))
		if scenario_ids == 'invalid':
			return _json_error('Ugyldige scenario-IDer.')

	old_status = action.status
	try:
		with transaction.atomic():
			action.beskrivelse = parsed['beskrivelse']
			action.ansvarlig = parsed['ansvarlig']
			action.frist = parsed['frist']
			action.status = parsed['status']
			action.eskaleres = parsed['eskaleres']
			action.save()
			_apply_action_scenarios(action, scope, scenario_ids)
	except ValueError as exc:
		return _json_error(str(exc))

	payload = _tiltak_refresh_payload(scope)
	tiltak_map = tiltak_display_id_map(_load_scope_actions(scope))
	_log_action_status_change(
		request, scope, action, old_status, action.status, tiltak_map.get(action.pk)
	)
	risk_map = annotate_scenario_display_ids(_load_scope_scenarios(scope))
	risk_ids = [
		risk_map.get(sc.pk, '')
		for sc in action.scenarios.all()
		if risk_map.get(sc.pk)
	]
	return JsonResponse({
		'ok': True,
		'action': _action_to_dict(
			action,
			tiltak_map.get(action.pk, ''),
			risk_ids,
			list(action.scenarios.values_list('pk', flat=True)),
		),
		**payload,
	})


@require_http_methods(['DELETE', 'POST'])
def api_risiko_scope_action_delete(request, pk, aid):
	scope, err = _require_owner_json(request, pk)
	if err:
		return err
	err = _reject_if_content_locked(scope)
	if err:
		return err

	action = get_object_or_404(RiskAction, pk=aid, scope=scope)

	if request.method == 'POST':
		data = _parse_json_body(request) or {}
		if data.get('_method') != 'DELETE':
			return _json_error('invalid_method', status=405)

	tiltak_map = tiltak_display_id_map(_load_scope_actions(scope))
	_log_action_delete(request, scope, action, tiltak_map.get(action.pk))
	action.delete()
	payload = _tiltak_refresh_payload(scope)
	return JsonResponse({'ok': True, **payload})


def _member_to_dict(membership):
	return {
		'user_id': membership.user_id,
		'name': user_member_display_name(membership.user),
		'username': membership.user.username,
		'role': membership.role,
	}


def _participant_group_to_dict(group):
	virksomhet = group.virksomhet
	return {
		'id': group.pk,
		'title': normalize_risk_group_title(virksomhet, group.title),
		'member_count': getattr(group, 'member_count', group.memberships.count()),
	}


def _members_payload(scope):
	memberships = list(
		scope.memberships.select_related(
			'user',
			'user__profile',
			'user__profile__virksomhet',
		).order_by('role', 'user__first_name', 'user__username')
	)
	owners = [_member_to_dict(m) for m in memberships if m.role == RISK_SCOPE_MEMBER_ROLE_OWNER]
	participants = [_member_to_dict(m) for m in memberships if m.role == RISK_SCOPE_MEMBER_ROLE_PARTICIPANT]
	participant_groups = list(
		scope.participant_groups.select_related('virksomhet').annotate(
			member_count=Count('memberships'),
		).order_by('title')
	)
	virksomhet = None
	if scope.virksomhet_id:
		v = scope.virksomhet
		virksomhet = {
			'id': v.pk,
			'label': '%s – %s' % (v.virksomhetsforkortelse or '-', v.virksomhetsnavn or ''),
		}
	return {
		'owners': owners,
		'participants': participants,
		'participant_groups': [_participant_group_to_dict(g) for g in participant_groups],
		'virksomhet': virksomhet,
	}


@require_GET
def api_risiko_members_list(request, pk):
	scope, err = _require_read_json(request, pk)
	if err:
		return err
	return JsonResponse({'ok': True, **_members_payload(scope)})


@require_http_methods(['POST'])
def api_risiko_member_add(request, pk):
	scope, err = _require_managed_json(request, pk)
	if err:
		return err
	err = _reject_if_content_locked(scope)
	if err:
		return err

	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	role = (data.get('role') or '').strip()
	if role not in (RISK_SCOPE_MEMBER_ROLE_OWNER, RISK_SCOPE_MEMBER_ROLE_PARTICIPANT):
		return _json_error('Ugyldig rolle.')

	try:
		user_id = int(data.get('user_id'))
	except (TypeError, ValueError):
		return _json_error('Ugyldig bruker.')

	target_user = get_object_or_404(User, pk=user_id, is_active=True)
	existing = RiskScopeMember.objects.filter(scope=scope, user=target_user).first()
	created = False
	if existing:
		if existing.role == role:
			return JsonResponse({'ok': True, **_members_payload(scope)})
		if role == RISK_SCOPE_MEMBER_ROLE_OWNER:
			existing.role = RISK_SCOPE_MEMBER_ROLE_OWNER
			existing.added_by = request.user
			existing.save(update_fields=['role', 'added_by'])
		else:
			return _json_error('Brukeren er allerede eier.')
	else:
		RiskScopeMember.objects.create(
			scope=scope,
			user=target_user,
			role=role,
			added_by=request.user,
		)
		created = True

	# 2026-08-10: Log member add for risk activity overview.
	if created:
		role_label = 'eier' if role == RISK_SCOPE_MEMBER_ROLE_OWNER else 'deltaker'
		log_risk_activity(
			RISK_ACTIVITY_MEMBER_ADDED,
			'%s la til %s (%s) som %s i «%s».' % (
				request.user.get_username(),
				user_member_display_name(target_user),
				target_user.username,
				role_label,
				scope.title,
			),
			user=request.user,
			scope=scope,
		)

	return JsonResponse({'ok': True, **_members_payload(scope)}, status=201)


@require_http_methods(['DELETE', 'POST'])
def api_risiko_member_remove(request, pk, user_id):
	scope, err = _require_managed_json(request, pk)
	if err:
		return err
	err = _reject_if_content_locked(scope)
	if err:
		return err

	if request.method == 'POST':
		data = _parse_json_body(request) or {}
		if data.get('_method') != 'DELETE':
			return _json_error('invalid_method', status=405)

	membership = get_object_or_404(RiskScopeMember, scope=scope, user_id=user_id)
	if membership.role == RISK_SCOPE_MEMBER_ROLE_OWNER:
		owner_count = scope.memberships.filter(role=RISK_SCOPE_MEMBER_ROLE_OWNER).count()
		if owner_count <= 1:
			return _json_error('Kan ikke fjerne siste eier.')

	target_user = membership.user
	role_label = 'eier' if membership.role == RISK_SCOPE_MEMBER_ROLE_OWNER else 'deltaker'
	membership.delete()
	# 2026-08-10: Log member remove for risk activity overview.
	log_risk_activity(
		RISK_ACTIVITY_MEMBER_REMOVED,
		'%s fjernet %s (%s) som %s fra «%s».' % (
			request.user.get_username(),
			user_member_display_name(target_user),
			target_user.username,
			role_label,
			scope.title,
		),
		user=request.user,
		scope=scope,
	)
	return JsonResponse({'ok': True, **_members_payload(scope)})


@require_http_methods(['POST'])
def api_risiko_participant_group_add(request, pk):
	scope, err = _require_managed_json(request, pk)
	if err:
		return err
	err = _reject_if_content_locked(scope)
	if err:
		return err

	if scope.virksomhet_id is None:
		return _json_error('Samlingen må ha virksomhet for å tildele deltakergrupper.')

	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	try:
		group_id = int(data.get('group_id'))
	except (TypeError, ValueError):
		return _json_error('Ugyldig gruppe.')

	group = get_object_or_404(
		RiskVirksomhetGroup,
		pk=group_id,
		virksomhet_id=scope.virksomhet_id,
	)
	if scope.participant_groups.filter(pk=group.pk).exists():
		return JsonResponse({'ok': True, **_members_payload(scope)})

	scope.participant_groups.add(group)
	return JsonResponse({'ok': True, **_members_payload(scope)}, status=201)


@require_http_methods(['DELETE', 'POST'])
def api_risiko_participant_group_remove(request, pk, gid):
	scope, err = _require_managed_json(request, pk)
	if err:
		return err
	err = _reject_if_content_locked(scope)
	if err:
		return err

	if request.method == 'POST':
		data = _parse_json_body(request) or {}
		if data.get('_method') != 'DELETE':
			return _json_error('invalid_method', status=405)

	group = get_object_or_404(RiskVirksomhetGroup, pk=gid)
	if not scope.participant_groups.filter(pk=group.pk).exists():
		return JsonResponse({'ok': True, **_members_payload(scope)})

	scope.participant_groups.remove(group)
	return JsonResponse({'ok': True, **_members_payload(scope)})


@require_GET
def api_risiko_participant_groups_sok(request, pk):
	scope, err = _require_managed_json(request, pk)
	if err:
		return err

	if scope.virksomhet_id is None:
		return JsonResponse({'ok': True, 'results': []})

	q = request.GET.get('q', '').strip()
	qs = RiskVirksomhetGroup.objects.filter(
		virksomhet_id=scope.virksomhet_id,
	).exclude(
		participant_scopes=scope,
	).select_related('virksomhet').annotate(member_count=Count('memberships')).order_by('title')

	if q:
		qs = qs.filter(title__icontains=q)
		limit = 15
	else:
		limit = 5

	results = []
	for group in qs[:limit]:
		display_title = normalize_risk_group_title(group.virksomhet, group.title)
		label = display_title
		if group.member_count:
			label = '%s (%d medlemmer)' % (display_title, group.member_count)
		results.append({
			'id': group.pk,
			'label': label,
		})
	return JsonResponse({'ok': True, 'results': results})


@require_http_methods(['PATCH', 'POST'])
def api_risiko_scope_virksomhet(request, pk):
	scope, err = _require_managed_json(request, pk)
	if err:
		return err
	err = _reject_if_content_locked(scope)
	if err:
		return err

	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	try:
		virksomhet_id = int(data.get('virksomhet_id'))
	except (TypeError, ValueError):
		return _json_error('Ugyldig virksomhet.')

	virksomhet = get_object_or_404(Virksomhet, pk=virksomhet_id)
	if scope.virksomhet_id != virksomhet.pk:
		scope.participant_groups.clear()
	scope.virksomhet = virksomhet
	scope.save(update_fields=['virksomhet', 'sist_oppdatert'])

	v = scope.virksomhet
	return JsonResponse({
		'ok': True,
		'virksomhet': {
			'id': v.pk,
			'label': '%s – %s' % (v.virksomhetsforkortelse or '-', v.virksomhetsnavn or ''),
		},
	})


@require_GET
def api_risiko_brukere_sok(request, pk):
	# 2026-08-13: Rank by exact email and scope/user virksomhet; multi-word AND via shared search.
	scope, err = _require_managed_json(request, pk)
	if err:
		return err

	q = request.GET.get('q', '').strip()
	if len(q) < 2:
		return JsonResponse({'ok': True, 'results': []})

	prefer = preferred_virksomhet_for_scope(scope, request.user)
	results = []
	for user in search_active_users(q, prefer_virksomhet=prefer):
		fork = user_virksomhetsforkortelse(user)
		suffix = fork or user.username
		results.append({
			'id': user.pk,
			'label': '%s (%s)' % (user_display_name(user), suffix),
		})
	return JsonResponse({'ok': True, 'results': results})


@require_GET
def api_risiko_tiltak_ansvarlig_sok(request, pk):
	# 2026-08-13: Shared search with virksomhet hard-filter; AND terms + exact email rank.
	scope, err = _require_member_json(request, pk)
	if err:
		return err

	scope = RiskScope.objects.select_related('virksomhet').get(pk=scope.pk)
	q = request.GET.get('q', '').strip()
	if len(q) < 2:
		return JsonResponse({'ok': True, 'results': []})

	if scope.virksomhet is None:
		return JsonResponse({'ok': True, 'results': []})

	results = []
	for user in search_active_users(q, restrict_virksomhet=scope.virksomhet):
		email = (user.email or '').strip() or user.username
		display = user_ansvarlig_display_name(user)
		results.append({
			'email': email,
			'label': '%s (%s)' % (display, email),
		})
	return JsonResponse({'ok': True, 'results': results})


@require_GET
def api_risiko_virksomheter_sok(request, pk):
	_, err = _require_managed_json(request, pk)
	if err:
		return err

	q = request.GET.get('q', '').strip()
	if len(q) < 2:
		return JsonResponse({'ok': True, 'results': []})

	virksomheter = (
		Virksomhet.objects.filter(
			Q(virksomhetsforkortelse__icontains=q) | Q(virksomhetsnavn__icontains=q)
		)
		.order_by('virksomhetsforkortelse', 'virksomhetsnavn')[:15]
	)
	return JsonResponse({
		'ok': True,
		'results': [
			{
				'id': v.pk,
				'label': '%s – %s' % (v.virksomhetsforkortelse or '-', v.virksomhetsnavn or ''),
			}
			for v in virksomheter
		],
	})


def _get_or_create_omfang_fil(scope):
	omfang_fil, _created = RiskScopeOmfangFil.objects.get_or_create(scope=scope)
	return omfang_fil


def _omfang_fil_payload(omfang_fil):
	if omfang_fil is None:
		return {
			'has_figur': False,
			'figur_filnavn': '',
			'has_original': False,
			'original_filnavn': '',
		}
	return {
		'has_figur': omfang_fil.has_figur(),
		'figur_filnavn': omfang_fil.figur_filnavn or '',
		'has_original': omfang_fil.has_original(),
		'original_filnavn': omfang_fil.original_filnavn or '',
	}


@require_http_methods(['POST', 'DELETE'])
def api_risiko_omfang_figur(request, pk):
	scope, err = _require_member_json(request, pk)
	if err:
		return err
	err = _reject_if_content_locked(scope)
	if err:
		return err

	omfang_fil = _get_or_create_omfang_fil(scope)
	if request.method == 'DELETE':
		clear_figur_fields(omfang_fil)
		omfang_fil.save(update_fields=['figur_data', 'figur_content_type', 'figur_filnavn'])
		return JsonResponse({'ok': True, 'omfang_fil': _omfang_fil_payload(omfang_fil)})

	upload = request.FILES.get('fil')
	try:
		data = read_upload_bytes(upload, validate_omfang_figur)
	except ValidationError as exc:
		return _json_error(exc.messages[0] if exc.messages else str(exc))

	filename = (upload.name or '').strip()
	omfang_fil.figur_data = data
	omfang_fil.figur_content_type = guess_content_type(filename, 'image/png')
	omfang_fil.figur_filnavn = filename[:300]
	omfang_fil.save(update_fields=['figur_data', 'figur_content_type', 'figur_filnavn'])
	return JsonResponse({'ok': True, 'omfang_fil': _omfang_fil_payload(omfang_fil)})


@require_http_methods(['POST', 'DELETE'])
def api_risiko_omfang_figur_original(request, pk):
	scope, err = _require_member_json(request, pk)
	if err:
		return err
	err = _reject_if_content_locked(scope)
	if err:
		return err

	omfang_fil = _get_or_create_omfang_fil(scope)
	if request.method == 'DELETE':
		clear_original_fields(omfang_fil)
		omfang_fil.save(update_fields=['original_data', 'original_content_type', 'original_filnavn'])
		return JsonResponse({'ok': True, 'omfang_fil': _omfang_fil_payload(omfang_fil)})

	upload = request.FILES.get('fil')
	try:
		data = read_upload_bytes(upload, validate_omfang_original)
	except ValidationError as exc:
		return _json_error(exc.messages[0] if exc.messages else str(exc))

	filename = (upload.name or '').strip()
	omfang_fil.original_data = data
	omfang_fil.original_content_type = guess_content_type(filename)
	omfang_fil.original_filnavn = filename[:300]
	omfang_fil.save(update_fields=['original_data', 'original_content_type', 'original_filnavn'])
	return JsonResponse({'ok': True, 'omfang_fil': _omfang_fil_payload(omfang_fil)})


def _parse_unntak_fields(data):
	errors = []
	beskrivelse = (data.get('beskrivelse') or '').strip()
	if not beskrivelse:
		errors.append('Unntaksbeskrivelse er påkrevd.')
	begrunnelse = (data.get('begrunnelse') or '').strip()
	gyldig_til = _parse_date(data.get('gyldig_til'))
	if gyldig_til == 'invalid':
		errors.append('Ugyldig gyldig-til-dato.')
		gyldig_til = None
	aktiv = data.get('aktiv')
	if aktiv is None:
		aktiv = True
	else:
		aktiv = bool(aktiv)
	system_ids = data.get('system_ids')
	if system_ids is None:
		system_ids = None
	elif not isinstance(system_ids, (list, tuple)):
		errors.append('Ugyldige system-IDer.')
		system_ids = None
	else:
		parsed_ids = []
		for value in system_ids:
			try:
				parsed_ids.append(int(value))
			except (TypeError, ValueError):
				errors.append('Ugyldige system-IDer.')
				parsed_ids = None
				break
		system_ids = parsed_ids
	if errors:
		return None, errors
	return {
		'beskrivelse': beskrivelse,
		'begrunnelse': begrunnelse,
		'gyldig_til': gyldig_til,
		'aktiv': aktiv,
		'system_ids': system_ids,
	}, []


def _apply_unntak_systems(unntak, system_ids):
	if system_ids is None:
		return
	if not system_ids:
		unntak.systemer.clear()
		return
	found = list(System.objects.filter(pk__in=system_ids))
	if len(found) != len(set(system_ids)):
		raise ValueError('Ukjente system-IDer.')
	unntak.systemer.set(found)


def _log_unntak_event(request, scope, action, event_type, message):
	log_risk_activity(
		event_type,
		message,
		user=request.user,
		scope=scope,
	)


@require_http_methods(['GET', 'POST'])
def api_risiko_action_unntak_list_create(request, pk, aid):
	# 2026-08-13: List/create coverage-gap exceptions for a tiltak.
	if request.method == 'GET':
		scope, err = _require_read_json(request, pk)
		if err:
			return err
		action = get_object_or_404(RiskAction, pk=aid, scope=scope)
		unntak_qs = action.unntak.prefetch_related('systemer').order_by('-aktiv', '-opprettet', 'pk')
		return JsonResponse({
			'ok': True,
			'unntak': [_unntak_to_dict(u) for u in unntak_qs],
		})

	scope, err = _require_owner_json(request, pk)
	if err:
		return err
	err = _reject_if_content_locked(scope)
	if err:
		return err
	action = get_object_or_404(RiskAction, pk=aid, scope=scope)
	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')
	parsed, errors = _parse_unntak_fields(data)
	if errors:
		return _json_error('; '.join(errors))
	try:
		with transaction.atomic():
			unntak = RiskActionUnntak.objects.create(
				action=action,
				beskrivelse=parsed['beskrivelse'],
				begrunnelse=parsed['begrunnelse'],
				gyldig_til=parsed['gyldig_til'],
				aktiv=parsed['aktiv'],
				opprettet_av=request.user,
			)
			_apply_unntak_systems(unntak, parsed['system_ids'] if parsed['system_ids'] is not None else [])
	except ValueError as exc:
		return _json_error(str(exc))

	tiltak_map = tiltak_display_id_map(_load_scope_actions(scope))
	display_id = tiltak_map.get(action.pk, 'T?')
	_log_unntak_event(
		request,
		scope,
		action,
		RISK_ACTIVITY_UNNTAK_CREATED,
		'%s opprettet unntak på %s.' % (
			user_member_display_name(request.user),
			display_id,
		),
	)
	return JsonResponse({
		'ok': True,
		'unntak': _unntak_to_dict(unntak),
		**_tiltak_refresh_payload(scope),
	}, status=201)


@require_http_methods(['PATCH', 'POST', 'DELETE'])
def api_risiko_action_unntak_detail(request, pk, aid, uid):
	# 2026-08-13: Update/delete a tiltak unntak.
	scope, err = _require_owner_json(request, pk)
	if err:
		return err
	err = _reject_if_content_locked(scope)
	if err:
		return err
	action = get_object_or_404(RiskAction, pk=aid, scope=scope)
	unntak = get_object_or_404(RiskActionUnntak, pk=uid, action=action)

	method = request.method
	data = None
	if method == 'POST':
		data = _parse_json_body(request) or {}
		if data.get('_method') == 'DELETE':
			method = 'DELETE'
		else:
			method = 'PATCH'

	tiltak_map = tiltak_display_id_map(_load_scope_actions(scope))
	display_id = tiltak_map.get(action.pk, 'T?')

	if method == 'DELETE':
		unntak.delete()
		_log_unntak_event(
			request,
			scope,
			action,
			RISK_ACTIVITY_UNNTAK_DELETED,
			'%s slettet unntak på %s.' % (
				user_member_display_name(request.user),
				display_id,
			),
		)
		return JsonResponse({'ok': True, **_tiltak_refresh_payload(scope)})

	if data is None:
		data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')
	parsed, errors = _parse_unntak_fields(data)
	if errors:
		return _json_error('; '.join(errors))
	try:
		with transaction.atomic():
			unntak.beskrivelse = parsed['beskrivelse']
			unntak.begrunnelse = parsed['begrunnelse']
			unntak.gyldig_til = parsed['gyldig_til']
			unntak.aktiv = parsed['aktiv']
			unntak.save()
			_apply_unntak_systems(unntak, parsed['system_ids'])
	except ValueError as exc:
		return _json_error(str(exc))

	_log_unntak_event(
		request,
		scope,
		action,
		RISK_ACTIVITY_UNNTAK_UPDATED,
		'%s endret unntak på %s.' % (
			user_member_display_name(request.user),
			display_id,
		),
	)
	return JsonResponse({
		'ok': True,
		'unntak': _unntak_to_dict(unntak),
		**_tiltak_refresh_payload(scope),
	})

