# -*- coding: utf-8 -*-
# Change log:
# 2026-07-08: Maintenance guide – see risk_snapshot_MAINTENANCE.md when model/UI changes affect snapshots.
# 2026-07-08: Risk snapshot capture, serialization, retention pruning, and render helpers.

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta

from django.db import transaction
from django.utils import timezone

from systemoversikt.models import (
	RISK_SCOPE_MEMBER_ROLE_OWNER,
	RISK_SCOPE_MEMBER_ROLE_PARTICIPANT,
	RISK_SCOPE_STATUS_VALG,
	RISK_SNAPSHOT_BIN_DAILY,
	RISK_SNAPSHOT_JSON_SCHEMA_VERSION,
	RISK_SNAPSHOT_SOURCE_COLLECTION,
	RISK_SNAPSHOT_SOURCE_SAMMENSTILLING,
	RISK_SNAPSHOT_TEMPLATE_VERSION,
	RiskScope,
	RiskSammenstilling,
	RiskSnapshot,
)
from systemoversikt.risk_criteria import (
	get_active_criteria,
	level_cell_css_class,
	risk_cell_css_class,
)
from systemoversikt.risk_display import (
	build_ansvarlig_display_map,
	resolve_ansvarlig_display,
)
from systemoversikt.risk_framework import (
	build_rollup_tree,
	build_sammenstilling_category_matrix,
	enrich_rollup_tree_detail,
)
from systemoversikt.risk_membership import user_member_display_name as member_display_name
from systemoversikt.risk_report import build_scenario_report_sections, collect_scope_systems

_SCOPE_STATUS_DISPLAY = dict(RISK_SCOPE_STATUS_VALG)

_RETENTION_DAILY_DAYS = 7
_RETENTION_WEEKLY_DAYS = 90
_RETENTION_MONTHLY_DAYS = 365


def snapshot_template_name(template_version, base_name):
	return 'risk_snapshots/v%d/%s' % (template_version, base_name)


def normalize_payload_json(payload):
	return json.dumps(
		payload,
		sort_keys=True,
		ensure_ascii=False,
		separators=(',', ':'),
		default=_json_default,
	)


def payload_sha256(payload):
	return hashlib.sha256(normalize_payload_json(payload).encode('utf-8')).hexdigest()


def _json_default(value):
	if isinstance(value, (datetime, date)):
		return value.isoformat()
	if isinstance(value, uuid.UUID):
		return str(value)
	raise TypeError('Object of type %s is not JSON serializable' % type(value).__name__)


def _iso_date(value):
	if value is None:
		return None
	if isinstance(value, datetime):
		return value.date().isoformat()
	if isinstance(value, date):
		return value.isoformat()
	return str(value)


def _labels_dict_to_json(labels):
	return {str(k): v for k, v in labels.items()}


def _serialize_system(system):
	return {
		'pk': system.pk,
		'systemnavn': system.systemnavn or '',
	}


def _serialize_scenario(scenario, ansvarlig_lookup=None):
	risikobehandling_display = ''
	if scenario.risikobehandling:
		risikobehandling_display = scenario.get_risikobehandling_display()
	return {
		'pk': scenario.pk,
		'risk_id': scenario.risk_id,
		'display_risk_id': getattr(scenario, 'display_risk_id', scenario.risk_id),
		'uonsket_hendelse': scenario.uonsket_hendelse or '',
		'kit_dimensjoner': scenario.kit_dimensjoner or '',
		'konsekvenstyper': scenario.konsekvenstyper or '',
		'sannsynlighetstyper': scenario.sannsynlighetstyper or '',
		'arsaker_svakheter': scenario.arsaker_svakheter or '',
		'konsekvens_nivaa': scenario.konsekvens_nivaa,
		'sannsynlighet_nivaa': scenario.sannsynlighet_nivaa,
		'konsekvens_begrunnelse': scenario.konsekvens_begrunnelse or '',
		'sannsynlighetsbegrunnelse': scenario.sannsynlighetsbegrunnelse or '',
		'risikobehandling': scenario.risikobehandling or '',
		'risikobehandling_display': risikobehandling_display,
		'konsekvens_etter': scenario.konsekvens_etter,
		'sannsynlighet_etter': scenario.sannsynlighet_etter,
		'konsekvens_label': getattr(scenario, 'konsekvens_label', ''),
		'sannsynlighet_label': getattr(scenario, 'sannsynlighet_label', ''),
		'konsekvens_css': getattr(scenario, 'konsekvens_css', ''),
		'sannsynlighet_css': getattr(scenario, 'sannsynlighet_css', ''),
		'risiko_etikett': scenario.risiko_etikett or '',
		'restrisiko_etikett': scenario.restrisiko_etikett or '',
		'risiko_css': getattr(scenario, 'risiko_css', ''),
		'restrisiko_css': getattr(scenario, 'restrisiko_css', ''),
		'systemer': [_serialize_system(s) for s in scenario.systemer.all()],
	}


def _serialize_action(action, ansvarlig_lookup):
	return {
		'pk': action.pk,
		'beskrivelse': action.beskrivelse or '',
		'ansvarlig': action.ansvarlig or '',
		'ansvarlig_display': resolve_ansvarlig_display(action.ansvarlig, ansvarlig_lookup),
		'frist': _iso_date(action.frist),
		'status': action.status,
		'status_display': action.get_status_display(),
	}


def _serialize_tiltak_entry(entry, ansvarlig_lookup):
	action = entry['action']
	return {
		'display_tiltak_id': entry['display_tiltak_id'],
		'action': _serialize_action(action, ansvarlig_lookup),
	}


def _serialize_tiltak_row(row, ansvarlig_lookup):
	return {
		'display_tiltak_id': row['display_tiltak_id'],
		'action': _serialize_action(row['action'], ansvarlig_lookup),
		'risk_links': list(row.get('risk_links') or []),
	}


def _serialize_matrix(matrix):
	rows = []
	for row in matrix:
		cells = []
		for cell in row['cells']:
			scenarios = []
			for scenario in cell.get('scenarios') or []:
				if isinstance(scenario, dict):
					scenarios.append(scenario)
				else:
					scenarios.append({
						'pk': scenario.pk,
						'display_risk_id': getattr(scenario, 'display_risk_id', scenario.risk_id),
						'uonsket_hendelse': scenario.uonsket_hendelse or '',
					})
			cells.append({
				'sannsynlighet': cell['sannsynlighet'],
				'konsekvens': cell['konsekvens'],
				'label': cell.get('label', ''),
				'css_class': cell.get('css_class', ''),
				'scenarios': scenarios,
			})
		rows.append({
			'sannsynlighet': row['sannsynlighet'],
			'sannsynlighet_label': row['sannsynlighet_label'],
			'cells': cells,
		})
	return rows


def _annotate_scenario_display(scenario, criteria):
	scenario.konsekvens_css = level_cell_css_class(scenario.konsekvens_nivaa)
	scenario.sannsynlighet_css = level_cell_css_class(scenario.sannsynlighet_nivaa)
	scenario.konsekvens_label = criteria.konsekvens_lookup_label(scenario.konsekvens_nivaa)
	scenario.sannsynlighet_label = criteria.sannsynlighet_lookup_label(scenario.sannsynlighet_nivaa)
	scenario.risiko_css = risk_cell_css_class(scenario.risiko_etikett)
	scenario.restrisiko_css = risk_cell_css_class(scenario.restrisiko_etikett)
	return scenario


def _scope_omfang_fil_meta(scope):
	try:
		omfang_fil = scope.omfang_fil
	except Exception:
		return {
			'has_figur': False,
			'figur_filnavn': '',
			'scope_pk': scope.pk,
		}
	return {
		'has_figur': omfang_fil.has_figur(),
		'figur_filnavn': omfang_fil.figur_filnavn or '',
		'scope_pk': scope.pk,
	}


def build_collection_snapshot_payload(scope, captured_at=None):
	# 2026-07-08: Mirror live rapport context as JSON-safe dicts for versioned templates.
	from systemoversikt.risk_display import annotate_scenario_display_ids, annotate_scenarios_tiltak_ids, tiltak_display_id_map
	from systemoversikt.views_risiko import _besluttede_rapport_tiltak_rows

	if captured_at is None:
		captured_at = timezone.now()
	criteria = get_active_criteria()

	scenarios = list(scope.scenarios.prefetch_related('systemer', 'actions').order_by('rekkefolge', 'risk_id'))
	annotate_scenario_display_ids(scenarios)
	actions = list(scope.actions.prefetch_related('scenarios').order_by('pk'))
	annotate_scenarios_tiltak_ids(scenarios, actions)
	for scenario in scenarios:
		_annotate_scenario_display(scenario, criteria)

	owner_memberships = [m for m in scope.memberships.all() if m.role == RISK_SCOPE_MEMBER_ROLE_OWNER]
	participant_memberships = [
		m for m in scope.memberships.all() if m.role == RISK_SCOPE_MEMBER_ROLE_PARTICIPANT
	]
	participant_groups = list(scope.participant_groups.all())
	tiltak_map = tiltak_display_id_map(actions)
	scenario_sections = build_scenario_report_sections(scenarios, tiltak_map)
	besluttede_rows = _besluttede_rapport_tiltak_rows(scenarios, actions)

	ansvarlig_values = [a.ansvarlig for a in actions if a.ansvarlig]
	ansvarlig_lookup = build_ansvarlig_display_map(ansvarlig_values)

	virksomhet_name = ''
	virksomhet_code = ''
	if scope.virksomhet_id:
		virksomhet_name = scope.virksomhet.virksomhetsnavn or ''
		virksomhet_code = scope.virksomhet.virksomhetsforkortelse or ''

	status_display = _SCOPE_STATUS_DISPLAY.get(scope.status, scope.status)

	payload = {
		'template_version': RISK_SNAPSHOT_TEMPLATE_VERSION,
		'json_schema_version': RISK_SNAPSHOT_JSON_SCHEMA_VERSION,
		'source_type': RISK_SNAPSHOT_SOURCE_COLLECTION,
		'source_pk': scope.pk,
		'snapshot_generated_at': captured_at.isoformat(),
		'scope': {
			'pk': scope.pk,
			'title': scope.title,
			'virksomhet_name': virksomhet_name,
			'virksomhet_code': virksomhet_code,
			'status': scope.status,
			'status_display': status_display,
			'sist_revidert': _iso_date(scope.sist_revidert),
			'beskrivelse': scope.beskrivelse or '',
		},
		'owners_display': [member_display_name(m.user) for m in owner_memberships],
		'participants_display': [member_display_name(m.user) for m in participant_memberships],
		'participant_groups_display': [
			'%s (gruppe)' % g.display_title for g in participant_groups
		],
		'omfang_fil': _scope_omfang_fil_meta(scope),
		'scope_systems': [_serialize_system(s) for s in collect_scope_systems(scenarios)],
		'matrix_current': _serialize_matrix(criteria.build_matrix_context(scenarios, use_residual=False)),
		'matrix_residual': _serialize_matrix(criteria.build_matrix_context(scenarios, use_residual=True)),
		'konsekvens_labels': _labels_dict_to_json(criteria.konsekvens_labels),
		'besluttede_tiltak_rows': [
			_serialize_tiltak_row(row, ansvarlig_lookup) for row in besluttede_rows
		],
		'scenario_sections': [
			{
				'scenario': _serialize_scenario(section['scenario'], ansvarlig_lookup),
				'tiltak_utfort_entries': [
					_serialize_tiltak_entry(entry, ansvarlig_lookup)
					for entry in section['tiltak_utfort_entries']
				],
				'tiltak_pending_entries': [
					_serialize_tiltak_entry(entry, ansvarlig_lookup)
					for entry in section['tiltak_pending_entries']
				],
			}
			for section in scenario_sections
		],
	}
	return payload


def _serialize_rollup_tree(rollup_tree):
	# Dates and nested structures from enrich_rollup_tree_detail are mostly JSON-safe.
	return json.loads(normalize_payload_json(rollup_tree))


def _serialize_sammenstilling_matrix(matrix):
	rows = []
	for row in matrix:
		cells = []
		for cell in row['cells']:
			categories = []
			for cat in cell.get('categories') or []:
				if isinstance(cat, dict):
					categories.append({
						'pk': cat.get('pk'),
						'display_code': cat.get('display_code', ''),
						'title': cat.get('title', ''),
					})
				else:
					categories.append({
						'pk': cat.pk,
						'display_code': cat.display_code(),
						'title': cat.title,
					})
			cells.append({
				'sannsynlighet': cell['sannsynlighet'],
				'konsekvens': cell['konsekvens'],
				'label': cell.get('label', ''),
				'css_class': cell.get('css_class', ''),
				'categories': categories,
			})
		rows.append({
			'sannsynlighet': row['sannsynlighet'],
			'sannsynlighet_label': row['sannsynlighet_label'],
			'cells': cells,
		})
	return rows


def build_sammenstilling_snapshot_payload(sammenstilling, captured_at=None):
	if captured_at is None:
		captured_at = timezone.now()
	criteria = get_active_criteria()
	rollup_tree = enrich_rollup_tree_detail(
		sammenstilling,
		build_rollup_tree(sammenstilling),
		criteria=criteria,
	)
	matrix_current = build_sammenstilling_category_matrix(rollup_tree, criteria)

	return {
		'template_version': RISK_SNAPSHOT_TEMPLATE_VERSION,
		'json_schema_version': RISK_SNAPSHOT_JSON_SCHEMA_VERSION,
		'source_type': RISK_SNAPSHOT_SOURCE_SAMMENSTILLING,
		'source_pk': sammenstilling.pk,
		'snapshot_generated_at': captured_at.isoformat(),
		'sammenstilling_title': sammenstilling.title,
		'framework_title': sammenstilling.framework.title,
		'owner_group_display_title': sammenstilling.owner_group.display_title,
		'rollup_tree': _serialize_rollup_tree(rollup_tree),
		'matrix_current': _serialize_sammenstilling_matrix(matrix_current),
		'konsekvens_labels': _labels_dict_to_json(criteria.konsekvens_labels),
	}


def latest_snapshot(source_type, source_pk):
	return RiskSnapshot.objects.filter(
		source_type=source_type,
		source_pk=source_pk,
	).order_by('-captured_at').first()


def _bin_key_for_snapshot(snapshot, now):
	age = now - snapshot.captured_at
	if age <= timedelta(days=_RETENTION_DAILY_DAYS):
		return ('daily', snapshot.captured_at.date().isoformat())
	if age <= timedelta(days=_RETENTION_WEEKLY_DAYS):
		d = snapshot.captured_at.date()
		week_start = d - timedelta(days=d.weekday())
		return ('weekly', week_start.isoformat())
	if age <= timedelta(days=_RETENTION_MONTHLY_DAYS):
		d = snapshot.captured_at.date()
		return ('monthly', '%04d-%02d' % (d.year, d.month))
	d = snapshot.captured_at.date()
	return ('yearly', str(d.year))


def prune_snapshots_for_source(source_type, source_pk, now=None):
	# 2026-07-08: Keep one snapshot per retention bin; delete older duplicates.
	if now is None:
		now = timezone.now()
	qs = RiskSnapshot.objects.filter(source_type=source_type, source_pk=source_pk).order_by('-captured_at')
	keep_ids = set()
	best_per_bin = {}
	for snapshot in qs:
		bin_kind, bin_key = _bin_key_for_snapshot(snapshot, now)
		key = (bin_kind, bin_key)
		if key not in best_per_bin:
			best_per_bin[key] = snapshot.pk
			keep_ids.add(snapshot.pk)
	to_delete = qs.exclude(pk__in=keep_ids)
	count = to_delete.count()
	if count:
		to_delete.delete()
	return count


def capture_snapshot(source_type, source_pk, payload, title='', captured_at=None, dry_run=False):
	if captured_at is None:
		captured_at = timezone.now()
	digest = payload_sha256(payload)
	latest = latest_snapshot(source_type, source_pk)
	if latest and latest.payload_sha256 == digest:
		return None, 'unchanged'
	if dry_run:
		return None, 'would_save'
	snapshot = RiskSnapshot.objects.create(
		snapshot_id=uuid.uuid4(),
		source_type=source_type,
		source_pk=source_pk,
		captured_at=captured_at,
		time_bin=RISK_SNAPSHOT_BIN_DAILY,
		template_version=payload.get('template_version', RISK_SNAPSHOT_TEMPLATE_VERSION),
		json_schema_version=payload.get('json_schema_version', RISK_SNAPSHOT_JSON_SCHEMA_VERSION),
		payload=payload,
		payload_sha256=digest,
		title=title,
	)
	prune_snapshots_for_source(source_type, source_pk, now=captured_at)
	return snapshot, 'saved'


def capture_collection_snapshot(scope, dry_run=False, captured_at=None):
	payload = build_collection_snapshot_payload(scope, captured_at=captured_at)
	return capture_snapshot(
		RISK_SNAPSHOT_SOURCE_COLLECTION,
		scope.pk,
		payload,
		title=scope.title,
		captured_at=captured_at,
		dry_run=dry_run,
	)


def capture_sammenstilling_snapshot(sammenstilling, dry_run=False, captured_at=None):
	payload = build_sammenstilling_snapshot_payload(sammenstilling, captured_at=captured_at)
	return capture_snapshot(
		RISK_SNAPSHOT_SOURCE_SAMMENSTILLING,
		sammenstilling.pk,
		payload,
		title=sammenstilling.title,
		captured_at=captured_at,
		dry_run=dry_run,
	)


def collection_render_context(payload, live_scope=None):
	# 2026-07-08: Rehydrate dict payload for versioned snapshot templates.
	konsekvens_labels = {int(k): v for k, v in payload.get('konsekvens_labels', {}).items()}
	scope = dict(payload.get('scope') or {})
	if live_scope is not None:
		scope['pk'] = live_scope.pk
	return {
		'scope': scope,
		'omfang_fil': payload.get('omfang_fil') or {},
		'scenarios': [],  # legacy; sections drive rapport
		'scenario_sections': payload.get('scenario_sections') or [],
		'scope_systems': payload.get('scope_systems') or [],
		'besluttede_tiltak_rows': payload.get('besluttede_tiltak_rows') or [],
		'matrix_current': payload.get('matrix_current') or [],
		'matrix_residual': payload.get('matrix_residual') or [],
		'konsekvens_labels': konsekvens_labels,
		'owners_display': payload.get('owners_display') or [],
		'participants_display': payload.get('participants_display') or [],
		'participant_groups_display': payload.get('participant_groups_display') or [],
		'generated_at': payload.get('snapshot_generated_at', ''),
		'report_mode': True,
		'is_snapshot': True,
		'snapshot_generated_at': payload.get('snapshot_generated_at', ''),
	}


def sammenstilling_render_context(payload):
	konsekvens_labels = {int(k): v for k, v in payload.get('konsekvens_labels', {}).items()}
	return {
		'sammenstilling': {
			'title': payload.get('sammenstilling_title', ''),
			'pk': payload.get('source_pk'),
		},
		'framework': {
			'title': payload.get('framework_title', ''),
		},
		'owner_group_display_title': payload.get('owner_group_display_title', ''),
		'rollup_tree': payload.get('rollup_tree') or [],
		'matrix_current': payload.get('matrix_current') or [],
		'konsekvens_labels': konsekvens_labels,
		'is_snapshot': True,
		'snapshot_generated_at': payload.get('snapshot_generated_at', ''),
		'can_map': False,
		'is_reader_only': True,
	}


def iter_collection_sources():
	# 2026-07-08: Archived scopes are immutable – no new collection snapshots needed.
	return RiskScope.objects.filter(archived_at__isnull=True).order_by('pk')


def iter_sammenstilling_sources():
	# 2026-07-08: Archived sammenstillinger are immutable – no new sammenstilling snapshots needed.
	return RiskSammenstilling.objects.filter(is_active=True, archived_at__isnull=True).select_related(
		'framework',
		'owner_group',
		'owner_group__virksomhet',
	).order_by('pk')


def capture_all(source_types=None, dry_run=False):
	if source_types is None:
		source_types = {RISK_SNAPSHOT_SOURCE_COLLECTION, RISK_SNAPSHOT_SOURCE_SAMMENSTILLING}
	stats = {'saved': 0, 'unchanged': 0, 'errors': 0}
	captured_at = timezone.now()
	with transaction.atomic():
		if RISK_SNAPSHOT_SOURCE_COLLECTION in source_types:
			for scope in iter_collection_sources():
				try:
					_snapshot, status = capture_collection_snapshot(
						scope, dry_run=dry_run, captured_at=captured_at,
					)
					if status in ('saved', 'would_save'):
						stats['saved'] += 1
					elif status == 'unchanged':
						stats['unchanged'] += 1
				except Exception:
					stats['errors'] += 1
		if RISK_SNAPSHOT_SOURCE_SAMMENSTILLING in source_types:
			for sammenstilling in iter_sammenstilling_sources():
				try:
					_snapshot, status = capture_sammenstilling_snapshot(
						sammenstilling, dry_run=dry_run, captured_at=captured_at,
					)
					if status in ('saved', 'would_save'):
						stats['saved'] += 1
					elif status == 'unchanged':
						stats['unchanged'] += 1
				except Exception:
					stats['errors'] += 1
	return stats
