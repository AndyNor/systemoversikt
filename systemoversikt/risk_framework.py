# -*- coding: utf-8 -*-
# Change log:
# 2026-07-06: Risk framework aggregation – suggested levels, roll-up, retire/reallocate helpers.

from datetime import date

from django.db import transaction
from django.db.models import Count, Prefetch, Q

from systemoversikt.models import (
	RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
	RISK_FRAMEWORK_NODE_STATUS_ARCHIVED,
	RiskFramework,
	RiskFrameworkNode,
	RiskScenario,
	RiskScenarioFrameworkLink,
	RiskVirksomhetNodeAssessment,
)
from systemoversikt.risk_criteria import (
	effective_residual_levels,
	risk_cell_css_class,
	risk_label,
)
from systemoversikt.risk_membership import user_has_virksomhet_read_group_access

RISK_FRAMEWORK_WRITE_PERMISSIONS = [
	'systemoversikt.add_riskscope',
	'systemoversikt.view_qualysvuln',
]

RISK_LABEL_RANK = {
	'': 0,
	'Lav': 1,
	'Middels': 2,
	'Høy': 3,
}


def user_can_edit_framework(user):
	if not user.is_authenticated:
		return False
	return any(user.has_perm(perm) for perm in RISK_FRAMEWORK_WRITE_PERMISSIONS)


def user_can_view_virksomhet_framework(user, virksomhet_id):
	if not user.is_authenticated or virksomhet_id is None:
		return False
	if user_can_edit_framework(user):
		return True
	return user_has_virksomhet_read_group_access(user, virksomhet_id)


def get_active_framework(slug):
	return RiskFramework.objects.filter(slug=slug, is_active=True).first()


def framework_nodes_queryset(framework, include_archived=False):
	qs = RiskFrameworkNode.objects.filter(framework=framework).select_related('parent')
	if not include_archived:
		qs = qs.filter(status=RISK_FRAMEWORK_NODE_STATUS_ACTIVE)
	return qs.order_by('parent__rekkefolge', 'parent__nummer', 'rekkefolge', 'nummer')


def leaf_nodes_for_framework(framework, include_archived=False):
	nodes = list(framework_nodes_queryset(framework, include_archived=include_archived))
	active_children = {}
	for node in nodes:
		if node.parent_id:
			active_children.setdefault(node.parent_id, 0)
			if node.status == RISK_FRAMEWORK_NODE_STATUS_ACTIVE:
				active_children[node.parent_id] += 1
	leaves = []
	for node in nodes:
		if node.parent_id is None:
			continue
		if include_archived or node.status == RISK_FRAMEWORK_NODE_STATUS_ACTIVE:
			if active_children.get(node.parent_id, 0) == 0 or node.parent_id:
				parent_child_count = sum(
					1 for n in nodes
					if n.parent_id == node.parent_id and n.status == RISK_FRAMEWORK_NODE_STATUS_ACTIVE
				)
				if parent_child_count > 0:
					leaves.append(node)
	return leaves


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


def scenarios_for_node(virksomhet_id, node, include_archived_links=False):
	qs = RiskScenario.objects.filter(
		framework_links__framework_node=node,
		scope__virksomhet_id=virksomhet_id,
	).select_related('scope').distinct()
	if not include_archived_links and node.status == RISK_FRAMEWORK_NODE_STATUS_ARCHIVED:
		pass
	return qs


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


def suggested_level_for_node(virksomhet_id, node):
	scenarios = list(scenarios_for_node(virksomhet_id, node))
	if not scenarios:
		return {
			'label': '',
			'sannsynlighet': None,
			'konsekvens': None,
			'scenario_count': 0,
			'level_counts': level_counts_for_scenarios([]),
		}
	labels = [_scenario_residual_label(s) for s in scenarios]
	worst = _worst_label(labels)
	s, k = _levels_from_label(worst)
	return {
		'label': worst,
		'sannsynlighet': s,
		'konsekvens': k,
		'scenario_count': len(scenarios),
		'level_counts': level_counts_for_scenarios(scenarios),
	}


def assessment_for_node(virksomhet_id, node, assessments_by_node=None):
	if assessments_by_node is None:
		assessment = RiskVirksomhetNodeAssessment.objects.filter(
			virksomhet_id=virksomhet_id,
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


def effective_node_level(virksomhet_id, node, assessments_by_node=None):
	manual = assessment_for_node(virksomhet_id, node, assessments_by_node)
	if manual and manual['manual_label']:
		return manual['manual_label'], 'manual'
	suggested = suggested_level_for_node(virksomhet_id, node)
	if suggested['label']:
		return suggested['label'], 'suggested'
	return '', 'none'


def category_suggested_level(virksomhet_id, category, children, assessments_by_node=None):
	labels = []
	for child in children:
		label, _source = effective_node_level(virksomhet_id, child, assessments_by_node)
		if label:
			labels.append(label)
	return _worst_label(labels)


def build_node_payload(virksomhet_id, node, assessments_by_node=None):
	suggested = suggested_level_for_node(virksomhet_id, node)
	manual = assessment_for_node(virksomhet_id, node, assessments_by_node)
	effective_label, effective_source = effective_node_level(virksomhet_id, node, assessments_by_node)
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


def build_rollup_tree(framework, virksomhet_id, include_archived=False):
	assessments = RiskVirksomhetNodeAssessment.objects.filter(
		virksomhet_id=virksomhet_id,
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
			build_node_payload(virksomhet_id, child, assessments_by_node)
			for child in children
		]
		cat_suggested = category_suggested_level(virksomhet_id, category, children, assessments_by_node)
		mapped_count = sum(c['suggested']['scenario_count'] for c in child_payloads)
		tree.append({
			'pk': category.pk,
			'nummer': category.nummer,
			'display_code': category.display_code(),
			'title': category.title,
			'forklaring': category.forklaring,
			'status': category.status,
			'suggested_label': cat_suggested,
			'suggested_css': risk_cell_css_class(cat_suggested),
			'mapped_scenario_count': mapped_count,
			'children': child_payloads,
		})
	return tree


def save_node_assessment(virksomhet, node, user, konsekvens_nivaa, sannsynlighet_nivaa, begrunnelse=''):
	assessment, _created = RiskVirksomhetNodeAssessment.objects.get_or_create(
		virksomhet=virksomhet,
		framework_node=node,
	)
	assessment.konsekvens_nivaa = konsekvens_nivaa
	assessment.sannsynlighet_nivaa = sannsynlighet_nivaa
	assessment.begrunnelse = begrunnelse or ''
	assessment.sist_revidert = date.today()
	assessment.revidert_av = user
	assessment.save()
	return assessment


def apply_suggestion_to_assessment(virksomhet, node, user):
	suggested = suggested_level_for_node(virksomhet.pk, node)
	if not suggested['sannsynlighet'] or not suggested['konsekvens']:
		return None
	return save_node_assessment(
		virksomhet,
		node,
		user,
		suggested['konsekvens'],
		suggested['sannsynlighet'],
		begrunnelse='Overført fra veiledende nivå basert på kartlagte scenarioer.',
	)


def archive_framework_node(node):
	if node.children.filter(status=RISK_FRAMEWORK_NODE_STATUS_ACTIVE).exists():
		raise ValueError('Arkiver underkategorier først.')
	node.status = RISK_FRAMEWORK_NODE_STATUS_ARCHIVED
	node.save(update_fields=['status', 'sist_oppdatert'])
	return node


def _merge_assessments(source_assessment, target_assessment, user):
	if source_assessment is None:
		return target_assessment
	if target_assessment is None:
		return source_assessment

	source_label = risk_label(source_assessment.sannsynlighet_nivaa, source_assessment.konsekvens_nivaa) or ''
	target_label = risk_label(target_assessment.sannsynlighet_nivaa, target_assessment.konsekvens_nivaa) or ''
	if RISK_LABEL_RANK.get(source_label, 0) > RISK_LABEL_RANK.get(target_label, 0):
		target_assessment.konsekvens_nivaa = source_assessment.konsekvens_nivaa
		target_assessment.sannsynlighet_nivaa = source_assessment.sannsynlighet_nivaa
	notes = []
	if target_assessment.begrunnelse:
		notes.append(target_assessment.begrunnelse)
	if source_assessment.begrunnelse:
		notes.append(source_assessment.begrunnelse)
	target_assessment.begrunnelse = '\n\n'.join(notes)
	target_assessment.sist_revidert = date.today()
	target_assessment.revidert_av = user
	target_assessment.save()
	source_assessment.delete()
	return target_assessment


@transaction.atomic
def retire_node_with_reallocation(node, successor):
	if node.framework_id != successor.framework_id:
		raise ValueError('Etterfølger må tilhøre samme rammeverk.')
	if successor.status != RISK_FRAMEWORK_NODE_STATUS_ACTIVE:
		raise ValueError('Etterfølger må være aktiv.')
	if node.pk == successor.pk:
		raise ValueError('Etterfølger kan ikke være samme node.')

	for link in RiskScenarioFrameworkLink.objects.filter(framework_node=node):
		exists = RiskScenarioFrameworkLink.objects.filter(
			scenario_id=link.scenario_id,
			framework_node=successor,
		).exists()
		if exists:
			link.delete()
		else:
			link.framework_node = successor
			link.save(update_fields=['framework_node'])

	for assessment in RiskVirksomhetNodeAssessment.objects.filter(framework_node=node):
		target = RiskVirksomhetNodeAssessment.objects.filter(
			virksomhet_id=assessment.virksomhet_id,
			framework_node=successor,
		).first()
		if target is None:
			assessment.framework_node = successor
			assessment.save(update_fields=['framework_node', 'sist_oppdatert'])
		else:
			_merge_assessments(assessment, target, assessment.revidert_av)

	for child in node.children.filter(status=RISK_FRAMEWORK_NODE_STATUS_ACTIVE):
		retire_node_with_reallocation(child, successor)

	node.status = RISK_FRAMEWORK_NODE_STATUS_ARCHIVED
	node.save(update_fields=['status', 'sist_oppdatert'])
	return node


def search_scenarios_for_mapping(framework, virksomhet_id=None, scope_id=None, unmapped_only=False, q=''):
	qs = RiskScenario.objects.select_related('scope', 'scope__virksomhet').order_by(
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
			~Q(framework_links__framework_node__framework=framework)
		)
	if q:
		qs = qs.filter(
			Q(uonsket_hendelse__icontains=q)
			| Q(risk_id__icontains=q)
			| Q(scope__title__icontains=q)
		)
	return qs.distinct()


def scenario_mapping_summary(scenario, framework):
	links = scenario.framework_links.filter(
		framework_node__framework=framework,
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


def mapped_scenarios_detail(virksomhet_id, node):
	from systemoversikt.risk_display import annotate_scenario_display_ids

	scenarios = list(scenarios_for_node(virksomhet_id, node))
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
