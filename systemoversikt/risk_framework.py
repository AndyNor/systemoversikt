# -*- coding: utf-8 -*-
# Change log:
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
from systemoversikt.risk_criteria import (
	effective_residual_levels,
	risk_cell_css_class,
	risk_label,
)

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


def category_suggested_level(sammenstilling, category, children, assessments_by_node=None):
	labels = []
	for child in children:
		label, _source = effective_node_level(sammenstilling, child, assessments_by_node)
		if label:
			labels.append(label)
	return _worst_label(labels)


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
		cat_suggested = category_suggested_level(sammenstilling, category, children, assessments_by_node)
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


def search_scenarios_for_mapping(sammenstilling, user, virksomhet_id=None, scope_id=None, unmapped_only=False, q=''):
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
	if q:
		qs = qs.filter(
			Q(uonsket_hendelse__icontains=q)
			| Q(risk_id__icontains=q)
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
