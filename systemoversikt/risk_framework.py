# -*- coding: utf-8 -*-
# Change log:
# 2026-07-06: Scenario rows on detail view include link_pk for unlink from sammenstilling page.
# 2026-07-06: Sammenstilling category matrix uses manual assessment only (no suggested fallback).
# 2026-07-06: Subcategory scenario/tiltak breakdown and per-category scenario matrix on detail view.
# 2026-07-06: Category-level manual assessment + nåværende-risiko matrix for sammenstilling.
# 2026-07-06: Kartlegging filter – scenarios with tiltak where eskaleres=True.
# 2026-07-06: Kartlegging API rows – per-scope display ids and explicit risk level fields.
# 2026-07-06: Kartlegging search – hendelse and samling only (not R-id).
# 2026-07-06: Rollup/mapping keyed by RiskSammenstilling; scope-level scenario search for kartlegging.
# 2026-07-06: Template taxonomy helpers – superuser-managed maler independent of virksomhet.

from datetime import date

from django.db.models import Exists, Max, OuterRef, Q

from systemoversikt.models import (
	RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
	RiskFramework,
	RiskFrameworkNode,
	RiskScenario,
	RiskSammenstillingNodeAssessment,
	RiskSammenstillingScenarioLink,
	RiskScopeMember,
	RiskVirksomhetGroupMember,
)
from systemoversikt.risk_display import annotate_scenario_display_ids, resolve_ansvarlig_display, tiltak_display_id_map

from systemoversikt.risk_criteria import (
	effective_residual_levels,
	risk_cell_css_class,
	risk_label,
)

SAMMENSTILLING_ACTIVE_TILTAK_STATUSES = frozenset(('besluttet', 'under_arbeid'))

RISK_LABEL_RANK = {
	'': 0,
	'Lav': 1,
	'Middels': 2,
	'Høy': 3,
}


def get_active_framework(slug):
	return RiskFramework.objects.filter(slug=slug, is_active=True).first()


def framework_nodes_queryset(framework, include_archived=False):
	qs = RiskFrameworkNode.objects.filter(framework=framework).select_related('parent')
	if not include_archived:
		qs = qs.filter(status=RISK_FRAMEWORK_NODE_STATUS_ACTIVE)
	return qs.order_by('parent__nummer', 'nummer')


def leaf_nodes_for_framework(framework, include_archived=False):
	nodes = list(framework_nodes_queryset(framework, include_archived=include_archived))
	leaves = []
	for node in nodes:
		if node.parent_id is None:
			continue
		if include_archived or node.status == RISK_FRAMEWORK_NODE_STATUS_ACTIVE:
			leaves.append(node)
	return leaves


def _scenario_current_label(scenario):
	return scenario.risiko_etikett or ''


def _scenario_residual_label(scenario):
	s, k = effective_residual_levels(scenario)
	return risk_label(s, k) or ''


def _levels_from_label(label):
	if not label:
		return None, None
	for s in range(5, 0, -1):
		for k in range(5, 0, -1):
			if risk_label(s, k) == label:
				return s, k
	return None, None


def _worst_label(labels):
	best = ''
	best_rank = 0
	for label in labels:
		rank = RISK_LABEL_RANK.get(label or '', 0)
		if rank > best_rank:
			best_rank = rank
			best = label or ''
	return best


def scenarios_for_node(sammenstilling, node):
	return RiskScenario.objects.filter(
		sammenstilling_links__sammenstilling=sammenstilling,
		sammenstilling_links__framework_node=node,
	).select_related('scope', 'scope__virksomhet').distinct()


def level_counts_for_scenarios(scenarios):
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


def suggested_level_for_node(sammenstilling, node):
	scenarios = list(scenarios_for_node(sammenstilling, node))
	if not scenarios:
		return {
			'label': '',
			'sannsynlighet': None,
			'konsekvens': None,
			'scenario_count': 0,
			'level_counts': level_counts_for_scenarios([]),
		}
	labels = [_scenario_current_label(s) for s in scenarios]
	worst = _worst_label(labels)
	s, k = _levels_from_label(worst)
	return {
		'label': worst,
		'sannsynlighet': s,
		'konsekvens': k,
		'scenario_count': len(scenarios),
		'level_counts': level_counts_for_scenarios(scenarios),
	}


def suggested_level_for_category(sammenstilling, children):
	scenario_pks = set()
	scenarios = []
	for child in children:
		for scenario in scenarios_for_node(sammenstilling, child):
			if scenario.pk in scenario_pks:
				continue
			scenario_pks.add(scenario.pk)
			scenarios.append(scenario)
	if not scenarios:
		return {
			'label': '',
			'sannsynlighet': None,
			'konsekvens': None,
			'scenario_count': 0,
			'level_counts': level_counts_for_scenarios([]),
		}
	labels = [_scenario_current_label(s) for s in scenarios]
	worst = _worst_label(labels)
	s, k = _levels_from_label(worst)
	return {
		'label': worst,
		'sannsynlighet': s,
		'konsekvens': k,
		'scenario_count': len(scenarios),
		'level_counts': level_counts_for_scenarios(scenarios),
	}


def assessment_for_node(sammenstilling, node, assessments_by_node=None):
	if assessments_by_node is None:
		assessment = RiskSammenstillingNodeAssessment.objects.filter(
			sammenstilling=sammenstilling,
			framework_node=node,
		).first()
	else:
		assessment = assessments_by_node.get(node.pk)
	if assessment is None:
		return None
	manual_label = ''
	if assessment.sannsynlighet_nivaa and assessment.konsekvens_nivaa:
		manual_label = risk_label(assessment.sannsynlighet_nivaa, assessment.konsekvens_nivaa) or ''
	return {
		'pk': assessment.pk,
		'konsekvens_nivaa': assessment.konsekvens_nivaa,
		'sannsynlighet_nivaa': assessment.sannsynlighet_nivaa,
		'begrunnelse': assessment.begrunnelse,
		'sist_revidert': assessment.sist_revidert,
		'manual_label': manual_label,
		'manual_css': risk_cell_css_class(manual_label),
	}


def effective_node_level(sammenstilling, node, assessments_by_node=None):
	manual = assessment_for_node(sammenstilling, node, assessments_by_node)
	if manual and manual['manual_label']:
		return manual['manual_label'], 'manual'
	suggested = suggested_level_for_node(sammenstilling, node)
	if suggested['label']:
		return suggested['label'], 'suggested'
	return '', 'none'


def effective_category_level(sammenstilling, category, children, assessments_by_node=None):
	manual = assessment_for_node(sammenstilling, category, assessments_by_node)
	if manual and manual['manual_label']:
		return manual['manual_label'], 'manual'
	suggested = suggested_level_for_category(sammenstilling, children)
	if suggested['label']:
		return suggested['label'], 'suggested'
	return '', 'none'


def build_node_payload(sammenstilling, node, assessments_by_node=None):
	suggested = suggested_level_for_node(sammenstilling, node)
	manual = assessment_for_node(sammenstilling, node, assessments_by_node)
	effective_label, effective_source = effective_node_level(sammenstilling, node, assessments_by_node)
	return {
		'pk': node.pk,
		'nummer': node.nummer,
		'display_code': node.display_code(),
		'title': node.title,
		'forklaring': node.forklaring,
		'status': node.status,
		'is_leaf': node.is_leaf(),
		'suggested': suggested,
		'suggested_css': risk_cell_css_class(suggested['label']),
		'manual': manual,
		'effective_label': effective_label,
		'effective_css': risk_cell_css_class(effective_label),
		'effective_source': effective_source,
		'differs_from_suggested': bool(
			manual and manual['manual_label'] and suggested['label']
			and manual['manual_label'] != suggested['label']
		),
	}


def build_rollup_tree(sammenstilling, include_archived=False):
	framework = sammenstilling.framework
	assessments = RiskSammenstillingNodeAssessment.objects.filter(
		sammenstilling=sammenstilling,
		framework_node__framework=framework,
	)
	assessments_by_node = {a.framework_node_id: a for a in assessments}

	nodes = list(framework_nodes_queryset(framework, include_archived=include_archived))
	categories = [n for n in nodes if n.parent_id is None]
	children_by_parent = {}
	for node in nodes:
		if node.parent_id:
			children_by_parent.setdefault(node.parent_id, []).append(node)

	tree = []
	for category in categories:
		children = children_by_parent.get(category.pk, [])
		child_payloads = [
			build_node_payload(sammenstilling, child, assessments_by_node)
			for child in children
		]
		cat_suggested = suggested_level_for_category(sammenstilling, children)
		cat_manual = assessment_for_node(sammenstilling, category, assessments_by_node)
		cat_effective_label, cat_effective_source = effective_category_level(
			sammenstilling, category, children, assessments_by_node,
		)
		mapped_count = sum(c['suggested']['scenario_count'] for c in child_payloads)
		tree.append({
			'pk': category.pk,
			'nummer': category.nummer,
			'display_code': category.display_code(),
			'title': category.title,
			'forklaring': category.forklaring,
			'status': category.status,
			'suggested': cat_suggested,
			'suggested_label': cat_suggested['label'],
			'suggested_css': risk_cell_css_class(cat_suggested['label']),
			'manual': cat_manual,
			'effective_label': cat_effective_label,
			'effective_css': risk_cell_css_class(cat_effective_label),
			'effective_source': cat_effective_source,
			'differs_from_suggested': bool(
				cat_manual and cat_manual['manual_label'] and cat_suggested['label']
				and cat_manual['manual_label'] != cat_suggested['label']
			),
			'mapped_scenario_count': mapped_count,
			'children': child_payloads,
		})
	return tree


def build_sammenstilling_category_matrix(rollup_tree, criteria=None):
	from systemoversikt.risk_criteria import get_active_criteria

	if criteria is None:
		criteria = get_active_criteria()
	placements = {}
	for cat in rollup_tree:
		manual = cat.get('manual')
		if not manual or not manual.get('sannsynlighet_nivaa') or not manual.get('konsekvens_nivaa'):
			continue
		s, k = manual['sannsynlighet_nivaa'], manual['konsekvens_nivaa']
		placements.setdefault((int(s), int(k)), []).append(cat)
	grid = []
	for sannsynlighet in range(5, 0, -1):
		row_cells = []
		for konsekvens in range(1, 6):
			label = criteria.risk_label(sannsynlighet, konsekvens)
			row_cells.append({
				'sannsynlighet': sannsynlighet,
				'konsekvens': konsekvens,
				'label': label,
				'css_class': risk_cell_css_class(label),
				'categories': placements.get((sannsynlighet, konsekvens), []),
			})
		grid.append({
			'sannsynlighet': sannsynlighet,
			'sannsynlighet_label': criteria.sannsynlighet_labels[sannsynlighet],
			'cells': row_cells,
		})
	return grid


def _risk_id_map_for_scenarios(scenarios):
	by_scope = {}
	for scenario in scenarios:
		by_scope.setdefault(scenario.scope_id, []).append(scenario)
	risk_id_by_pk = {}
	for scope_scenarios in by_scope.values():
		scope_scenarios.sort(key=lambda s: (s.rekkefolge, s.risk_id))
		risk_id_by_pk.update(annotate_scenario_display_ids(scope_scenarios))
	return risk_id_by_pk


def _scenario_row_dict(scenario, risk_id_by_pk, link_pk=None):
	virksomhet = ''
	if scenario.scope.virksomhet_id:
		virksomhet = scenario.scope.virksomhet.virksomhetsforkortelse or ''
	row = {
		'pk': scenario.pk,
		'display_id': risk_id_by_pk.get(scenario.pk, scenario.risk_id),
		'scope_pk': scenario.scope_id,
		'scope_title': scenario.scope.title,
		'virksomhet': virksomhet,
		'uonsket_hendelse': scenario.uonsket_hendelse,
		'current_label': scenario.risiko_etikett or '',
		'current_css': risk_cell_css_class(scenario.risiko_etikett or ''),
	}
	if link_pk is not None:
		row['link_pk'] = link_pk
	return row


def _tiltak_rows_for_node_scenarios(scenarios, actions, risk_id_by_pk, ansvarlig_lookup):
	scenario_pks = {s.pk for s in scenarios}
	if not scenario_pks:
		return []
	relevant = [
		action for action in actions
		if any(s.pk in scenario_pks for s in action.scenarios.all())
	]
	if not relevant:
		return []
	by_scope = {}
	for action in relevant:
		by_scope.setdefault(action.scope_id, []).append(action)
	rows = []
	for scope_id in sorted(by_scope.keys()):
		scope_actions = sorted(by_scope[scope_id], key=lambda a: a.pk)
		tiltak_map = tiltak_display_id_map(scope_actions)
		scope_title = scope_actions[0].scope.title
		for action in scope_actions:
			risk_links = []
			for scenario in action.scenarios.all():
				if scenario.pk not in scenario_pks:
					continue
				risk_id = risk_id_by_pk.get(scenario.pk)
				if not risk_id:
					continue
				etikett = scenario.risiko_etikett or ''
				risk_links.append({
					'risk_id': risk_id,
					'scenario_pk': scenario.pk,
					'risiko_etikett': etikett,
					'risiko_css': risk_cell_css_class(etikett),
				})
			risk_links.sort(key=lambda link: int(link['risk_id'][1:]))
			rows.append({
				'display_tiltak_id': tiltak_map[action.pk],
				'scope_pk': action.scope_id,
				'scope_title': scope_title,
				'beskrivelse': action.beskrivelse,
				'ansvarlig': resolve_ansvarlig_display(action.ansvarlig, ansvarlig_lookup),
				'frist': action.frist,
				'status': action.status,
				'status_display': action.get_status_display(),
				'risk_links': risk_links,
			})
	return rows


def build_scenario_matrix_for_scenarios(scenarios, risk_id_by_pk, criteria=None):
	from systemoversikt.risk_criteria import get_active_criteria, matrix_placements

	if criteria is None:
		criteria = get_active_criteria()
	placements = matrix_placements(scenarios, use_residual=False, criteria=criteria)
	enriched = {}
	for key, scenario_list in placements.items():
		enriched[key] = [
			_scenario_row_dict(scenario, risk_id_by_pk)
			for scenario in scenario_list
		]
	grid = []
	for sannsynlighet in range(5, 0, -1):
		row_cells = []
		for konsekvens in range(1, 6):
			label = criteria.risk_label(sannsynlighet, konsekvens)
			cell_scenarios = enriched.get((sannsynlighet, konsekvens), [])
			cell_scenarios.sort(key=lambda row: (row['scope_title'], row['display_id']))
			row_cells.append({
				'sannsynlighet': sannsynlighet,
				'konsekvens': konsekvens,
				'label': label,
				'css_class': risk_cell_css_class(label),
				'scenarios': cell_scenarios,
			})
		grid.append({
			'sannsynlighet': sannsynlighet,
			'sannsynlighet_label': criteria.sannsynlighet_labels[sannsynlighet],
			'cells': row_cells,
		})
	return grid


def enrich_rollup_tree_detail(sammenstilling, rollup_tree, criteria=None):
	from collections import defaultdict

	from systemoversikt.models import RiskAction, RiskSammenstillingScenarioLink
	from systemoversikt.risk_criteria import get_active_criteria
	from systemoversikt.risk_display import build_ansvarlig_display_map

	if criteria is None:
		criteria = get_active_criteria()

	child_pks = [child['pk'] for cat in rollup_tree for child in cat.get('children', [])]
	if not child_pks:
		for cat in rollup_tree:
			cat['scenario_matrix'] = build_scenario_matrix_for_scenarios([], {}, criteria)
		return rollup_tree

	links = RiskSammenstillingScenarioLink.objects.filter(
		sammenstilling=sammenstilling,
		framework_node_id__in=child_pks,
	).select_related(
		'scenario', 'scenario__scope', 'scenario__scope__virksomhet',
	)

	scenarios_by_node = defaultdict(list)
	all_scenarios = {}
	for link in links:
		scenario = link.scenario
		all_scenarios.setdefault(scenario.pk, scenario)
		scenarios_by_node[link.framework_node_id].append((link.pk, scenario))

	all_scenario_list = list(all_scenarios.values())
	risk_id_by_pk = _risk_id_map_for_scenarios(all_scenario_list)

	actions = []
	if all_scenarios:
		actions = list(
			RiskAction.objects.filter(
				scenarios__pk__in=all_scenarios.keys(),
				status__in=SAMMENSTILLING_ACTIVE_TILTAK_STATUSES,
			).select_related('scope').prefetch_related('scenarios').order_by('scope_id', 'pk').distinct(),
		)
	ansvarlig_lookup = build_ansvarlig_display_map([a.ansvarlig for a in actions if a.ansvarlig])

	def _scenario_sort_key(scenario):
		virk = ''
		if scenario.scope.virksomhet_id:
			virk = scenario.scope.virksomhet.virksomhetsforkortelse or ''
		return (virk, scenario.scope.title, scenario.rekkefolge, scenario.risk_id)

	for cat in rollup_tree:
		category_scenarios = []
		category_scenario_pks = set()
		for child in cat.get('children', []):
			node_links = sorted(scenarios_by_node.get(child['pk'], []), key=lambda item: _scenario_sort_key(item[1]))
			node_scenarios = [scenario for _link_pk, scenario in node_links]
			child['scenarios'] = [
				_scenario_row_dict(scenario, risk_id_by_pk, link_pk=link_pk)
				for link_pk, scenario in node_links
			]
			child['actions'] = _tiltak_rows_for_node_scenarios(
				node_scenarios, actions, risk_id_by_pk, ansvarlig_lookup,
			)
			for scenario in node_scenarios:
				if scenario.pk in category_scenario_pks:
					continue
				category_scenario_pks.add(scenario.pk)
				category_scenarios.append(scenario)
		cat['scenario_matrix'] = build_scenario_matrix_for_scenarios(
			category_scenarios, risk_id_by_pk, criteria,
		)
	return rollup_tree


def save_node_assessment(sammenstilling, node, user, konsekvens_nivaa, sannsynlighet_nivaa, begrunnelse=''):
	assessment, _created = RiskSammenstillingNodeAssessment.objects.get_or_create(
		sammenstilling=sammenstilling,
		framework_node=node,
	)
	assessment.konsekvens_nivaa = konsekvens_nivaa
	assessment.sannsynlighet_nivaa = sannsynlighet_nivaa
	assessment.begrunnelse = begrunnelse or ''
	assessment.sist_revidert = date.today()
	assessment.revidert_av = user
	assessment.save()
	return assessment


def apply_suggestion_to_assessment(sammenstilling, node, user):
	if node.parent_id is None:
		children = list(
			RiskFrameworkNode.objects.filter(
				parent=node,
				status=RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
			),
		)
		suggested = suggested_level_for_category(sammenstilling, children)
	else:
		suggested = suggested_level_for_node(sammenstilling, node)
	if not suggested['sannsynlighet'] or not suggested['konsekvens']:
		return None
	return save_node_assessment(
		sammenstilling,
		node,
		user,
		suggested['konsekvens'],
		suggested['sannsynlighet'],
		begrunnelse='Overført fra veiledende nivå basert på kartlagte scenarioer.',
	)


def move_framework_node(node, new_parent):
	if new_parent is not None:
		if new_parent.framework_id != node.framework_id:
			raise ValueError('Ny kategori må tilhøre samme mal.')
		if new_parent.parent_id is not None:
			raise ValueError('Underkategori kan bare flyttes til en hovedkategori.')
	if node.parent_id is None:
		raise ValueError('Hovedkategorier kan ikke flyttes.')
	siblings = RiskFrameworkNode.objects.filter(
		framework=node.framework,
		parent=new_parent,
	).exclude(pk=node.pk)
	max_nummer = siblings.aggregate(m=Max('nummer'))['m'] or 0
	node.parent = new_parent
	node.nummer = max_nummer + 1
	node.save(update_fields=['parent', 'nummer', 'sist_oppdatert'])
	return node


def _scenarios_with_scope_read_access_qs(user):
	if not user.is_authenticated:
		return RiskScenario.objects.none()
	direct_member = RiskScopeMember.objects.filter(
		scope_id=OuterRef('scope_id'),
		user_id=user.id,
	)
	group_participant = RiskVirksomhetGroupMember.objects.filter(
		user_id=user.id,
		group__participant_scopes=OuterRef('scope_id'),
	)
	read_group = RiskVirksomhetGroupMember.objects.filter(
		user_id=user.id,
		group__virksomhet_id=OuterRef('scope__virksomhet_id'),
		group__virksomhet_read_only=True,
	)
	return RiskScenario.objects.filter(
		Exists(direct_member) | Exists(group_participant) | Exists(read_group),
	)


def search_scenarios_for_mapping(sammenstilling, user, virksomhet_id=None, scope_id=None, unmapped_only=False, eskaleres_only=False, q=''):
	qs = _scenarios_with_scope_read_access_qs(user).select_related(
		'scope', 'scope__virksomhet',
	).order_by(
		'scope__virksomhet__virksomhetsforkortelse',
		'scope__title',
		'rekkefolge',
		'risk_id',
	)
	if virksomhet_id:
		qs = qs.filter(scope__virksomhet_id=virksomhet_id)
	if scope_id:
		qs = qs.filter(scope_id=scope_id)
	if unmapped_only:
		qs = qs.filter(
			~Q(sammenstilling_links__sammenstilling=sammenstilling),
		)
	if eskaleres_only:
		qs = qs.filter(actions__eskaleres=True)
	if q:
		qs = qs.filter(
			Q(uonsket_hendelse__icontains=q)
			| Q(scope__title__icontains=q)
		)
	return qs.distinct()


def scenario_mapping_summary(scenario, sammenstilling):
	links = scenario.sammenstilling_links.filter(
		sammenstilling=sammenstilling,
	).select_related('framework_node', 'framework_node__parent')
	return [
		{
			'link_pk': link.pk,
			'node_pk': link.framework_node_id,
			'display_code': link.framework_node.display_code(),
			'title': link.framework_node.title,
			'status': link.framework_node.status,
		}
		for link in links
	]


def kartlegging_scenario_rows(sammenstilling, scenarios):
	"""Serialize scenarios for sammenstilling kartlegging search API."""
	risk_id_by_pk = _risk_id_map_for_scenarios(scenarios)
	rows = []
	for scenario in scenarios:
		current_label = scenario.risiko_etikett or ''
		residual_label = scenario.restrisiko_etikett or ''
		rows.append({
			'pk': scenario.pk,
			'display_id': risk_id_by_pk.get(scenario.pk, scenario.risk_id),
			'uonsket_hendelse': scenario.uonsket_hendelse,
			'scope_pk': scenario.scope_id,
			'scope_title': scenario.scope.title,
			'virksomhet': scenario.scope.virksomhet.virksomhetsforkortelse if scenario.scope.virksomhet_id else '',
			'konsekvens_nivaa': scenario.konsekvens_nivaa,
			'sannsynlighet_nivaa': scenario.sannsynlighet_nivaa,
			'konsekvens_etter': scenario.konsekvens_etter,
			'sannsynlighet_etter': scenario.sannsynlighet_etter,
			'current_label': current_label,
			'residual_label': residual_label,
			'risiko_etikett': current_label,
			'restrisiko_etikett': residual_label,
			'current_css': risk_cell_css_class(current_label),
			'residual_css': risk_cell_css_class(residual_label),
			'risiko_css': risk_cell_css_class(current_label),
			'restrisiko_css': risk_cell_css_class(residual_label),
			'mappings': scenario_mapping_summary(scenario, sammenstilling),
		})
	return rows


def mapped_scenarios_detail(sammenstilling, node):
	from systemoversikt.risk_display import annotate_scenario_display_ids

	scenarios = list(scenarios_for_node(sammenstilling, node))
	annotate_scenario_display_ids(scenarios)
	rows = []
	for scenario in scenarios:
		rows.append({
			'pk': scenario.pk,
			'display_id': getattr(scenario, 'display_id', scenario.risk_id),
			'uonsket_hendelse': scenario.uonsket_hendelse,
			'scope_pk': scenario.scope_id,
			'scope_title': scenario.scope.title,
			'current_label': scenario.risiko_etikett or '',
			'residual_label': scenario.restrisiko_etikett or '',
			'current_css': risk_cell_css_class(scenario.risiko_etikett or ''),
			'residual_css': risk_cell_css_class(scenario.restrisiko_etikett or ''),
		})
	return rows
