# -*- coding: utf-8 -*-
# Change log:
# 2026-07-06: JSON API for risk framework taxonomy, mapping, and virksomhet assessments.

import json

from django.db import transaction
from django.db.models import Max
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods

from systemoversikt.models import (
	RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
	RiskFramework,
	RiskFrameworkNode,
	RiskScenario,
	RiskScenarioFrameworkLink,
	Virksomhet,
)
from systemoversikt.risk_display import annotate_scenario_display_ids
from systemoversikt.risk_framework import (
	apply_suggestion_to_assessment,
	archive_framework_node,
	build_rollup_tree,
	framework_nodes_queryset,
	get_active_framework,
	mapped_scenarios_detail,
	retire_node_with_reallocation,
	save_node_assessment,
	scenario_mapping_summary,
	search_scenarios_for_mapping,
	user_can_edit_framework,
	user_can_view_virksomhet_framework,
)
from systemoversikt.api_risiko import _json_error, _parse_json_body


def _json_ok(payload=None, status=200):
	data = {'ok': True}
	if payload:
		data.update(payload)
	return JsonResponse(data, status=status)


def _require_framework_edit(request):
	if not user_can_edit_framework(request.user):
		return _json_error('Ingen tilgang.', status=403)
	return None


def _require_framework_view(request, virksomhet_id):
	if not user_can_view_virksomhet_framework(request.user, virksomhet_id):
		return _json_error('Ingen tilgang.', status=403)
	return None


def _framework_or_404(slug):
	framework = get_active_framework(slug)
	if framework is None:
		raise Http404
	return framework


def _node_payload(node, include_children=False):
	data = {
		'pk': node.pk,
		'parent_pk': node.parent_id,
		'nummer': node.nummer,
		'display_code': node.display_code(),
		'title': node.title,
		'forklaring': node.forklaring,
		'status': node.status,
		'rekkefolge': node.rekkefolge,
		'is_leaf': node.is_leaf(),
		'link_count': node.scenario_links.count(),
		'assessment_count': node.virksomhet_assessments.count(),
	}
	if include_children:
		children = node.children.order_by('rekkefolge', 'nummer')
		data['children'] = [_node_payload(c) for c in children]
	return data


def _taxonomy_tree(framework, include_archived=False):
	nodes = list(framework_nodes_queryset(framework, include_archived=include_archived))
	categories = [n for n in nodes if n.parent_id is None]
	children_by_parent = {}
	for node in nodes:
		if node.parent_id:
			children_by_parent.setdefault(node.parent_id, []).append(node)
	return [
		{
			**_node_payload(cat),
			'children': [_node_payload(child) for child in children_by_parent.get(cat.pk, [])],
		}
		for cat in categories
	]


@require_GET
def api_risiko_rammeverk_taxonomy(request, slug):
	framework = _framework_or_404(slug)
	include_archived = request.GET.get('include_archived') == '1'
	return _json_ok({'tree': _taxonomy_tree(framework, include_archived=include_archived)})


@require_GET
def api_risiko_rammeverk_active_nodes(request, slug):
	framework = _framework_or_404(slug)
	leaves = RiskFrameworkNode.objects.filter(
		framework=framework,
		status=RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
		parent__isnull=False,
	).select_related('parent').order_by('parent__nummer', 'nummer')
	return _json_ok({
		'nodes': [
			{
				'pk': n.pk,
				'display_code': n.display_code(),
				'title': n.title,
				'parent_title': n.parent.title if n.parent_id else '',
			}
			for n in leaves
		],
	})


@require_http_methods(['POST'])
def api_risiko_rammeverk_node_create(request, slug):
	denied = _require_framework_edit(request)
	if denied:
		return denied
	framework = _framework_or_404(slug)
	body = _parse_json_body(request)
	if body is None:
		return _json_error('Ugyldig JSON.')

	parent_pk = body.get('parent_pk')
	parent = None
	if parent_pk not in (None, '', 0, '0'):
		parent = get_object_or_404(RiskFrameworkNode, pk=parent_pk, framework=framework)

	siblings = RiskFrameworkNode.objects.filter(framework=framework, parent=parent)
	next_nummer = (siblings.aggregate(m=Max('nummer'))['m'] or 0) + 1
	next_rekke = (siblings.aggregate(m=Max('rekkefolge'))['m'] or 0) + 1

	node = RiskFrameworkNode.objects.create(
		framework=framework,
		parent=parent,
		nummer=body.get('nummer') or next_nummer,
		title=(body.get('title') or 'Ny kategori').strip(),
		forklaring=(body.get('forklaring') or '').strip(),
		rekkefolge=body.get('rekkefolge') or next_rekke,
	)
	return _json_ok({'node': _node_payload(node)})


@require_http_methods(['POST'])
def api_risiko_rammeverk_node_update(request, slug, nid):
	denied = _require_framework_edit(request)
	if denied:
		return denied
	framework = _framework_or_404(slug)
	node = get_object_or_404(RiskFrameworkNode, pk=nid, framework=framework)
	body = _parse_json_body(request)
	if body is None:
		return _json_error('Ugyldig JSON.')

	if 'title' in body:
		node.title = (body.get('title') or '').strip()
	if 'forklaring' in body:
		node.forklaring = (body.get('forklaring') or '').strip()
	if 'nummer' in body and body.get('nummer'):
		node.nummer = int(body['nummer'])
	if 'rekkefolge' in body and body.get('rekkefolge') is not None:
		node.rekkefolge = int(body['rekkefolge'])
	node.save()
	return _json_ok({'node': _node_payload(node)})


@require_http_methods(['POST'])
def api_risiko_rammeverk_node_archive(request, slug, nid):
	denied = _require_framework_edit(request)
	if denied:
		return denied
	framework = _framework_or_404(slug)
	node = get_object_or_404(RiskFrameworkNode, pk=nid, framework=framework)
	try:
		archive_framework_node(node)
	except ValueError as exc:
		return _json_error(str(exc))
	return _json_ok({'node': _node_payload(node)})


@require_http_methods(['POST'])
def api_risiko_rammeverk_node_retire(request, slug, nid):
	denied = _require_framework_edit(request)
	if denied:
		return denied
	framework = _framework_or_404(slug)
	node = get_object_or_404(RiskFrameworkNode, pk=nid, framework=framework)
	body = _parse_json_body(request)
	if body is None:
		return _json_error('Ugyldig JSON.')
	successor_pk = body.get('successor_pk')
	if not successor_pk:
		return _json_error('Velg etterfølger-node.')
	successor = get_object_or_404(RiskFrameworkNode, pk=successor_pk, framework=framework)
	try:
		retire_node_with_reallocation(node, successor)
	except ValueError as exc:
		return _json_error(str(exc))
	return _json_ok({'node': _node_payload(node)})


@require_GET
def api_risiko_rammeverk_scenarios(request, slug):
	if not user_can_edit_framework(request.user):
		return _json_error('Ingen tilgang.', status=403)
	framework = _framework_or_404(slug)
	virksomhet_id = request.GET.get('virksomhet_id')
	scope_id = request.GET.get('scope_id')
	unmapped_only = request.GET.get('unmapped_only') == '1'
	q = (request.GET.get('q') or '').strip()
	qs = search_scenarios_for_mapping(
		framework,
		virksomhet_id=int(virksomhet_id) if virksomhet_id else None,
		scope_id=int(scope_id) if scope_id else None,
		unmapped_only=unmapped_only,
		q=q,
	)[:200]
	scenarios = list(qs)
	annotate_scenario_display_ids(scenarios)
	rows = []
	for scenario in scenarios:
		rows.append({
			'pk': scenario.pk,
			'display_id': getattr(scenario, 'display_id', scenario.risk_id),
			'uonsket_hendelse': scenario.uonsket_hendelse,
			'scope_pk': scenario.scope_id,
			'scope_title': scenario.scope.title,
			'virksomhet': scenario.scope.virksomhet.virksomhetsforkortelse if scenario.scope.virksomhet_id else '',
			'mappings': scenario_mapping_summary(scenario, framework),
		})
	return _json_ok({'scenarios': rows})


@require_http_methods(['POST'])
def api_risiko_rammeverk_link_create(request, slug):
	denied = _require_framework_edit(request)
	if denied:
		return denied
	framework = _framework_or_404(slug)
	body = _parse_json_body(request)
	if body is None:
		return _json_error('Ugyldig JSON.')
	scenario_ids = body.get('scenario_ids') or []
	node_pk = body.get('node_pk')
	if not scenario_ids or not node_pk:
		return _json_error('Velg scenarioer og rammeverk-node.')
	node = get_object_or_404(
		RiskFrameworkNode,
		pk=node_pk,
		framework=framework,
		status=RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
		parent__isnull=False,
	)
	created = []
	with transaction.atomic():
		for sid in scenario_ids:
			scenario = get_object_or_404(RiskScenario, pk=sid)
			link, was_created = RiskScenarioFrameworkLink.objects.get_or_create(
				scenario=scenario,
				framework_node=node,
				defaults={'mapped_by': request.user},
			)
			if was_created:
				created.append(link.pk)
	return _json_ok({'created_count': len(created)})


@require_http_methods(['POST'])
def api_risiko_rammeverk_link_delete(request, slug, lid):
	denied = _require_framework_edit(request)
	if denied:
		return denied
	_framework_or_404(slug)
	link = get_object_or_404(RiskScenarioFrameworkLink, pk=lid, framework_node__framework__slug=slug)
	link.delete()
	return _json_ok({})


@require_GET
def api_risiko_rammeverk_rollup(request, slug, vid):
	framework = _framework_or_404(slug)
	denied = _require_framework_view(request, vid)
	if denied:
		return denied
	return _json_ok({'tree': build_rollup_tree(framework, vid)})


@require_GET
def api_risiko_rammeverk_node_scenarios(request, slug, vid, nid):
	framework = _framework_or_404(slug)
	denied = _require_framework_view(request, vid)
	if denied:
		return denied
	node = get_object_or_404(RiskFrameworkNode, pk=nid, framework=framework)
	return _json_ok({'scenarios': mapped_scenarios_detail(vid, node)})


@require_http_methods(['POST'])
def api_risiko_rammeverk_assessment_save(request, slug, vid, nid):
	framework = _framework_or_404(slug)
	if not user_can_edit_framework(request.user):
		return _json_error('Ingen tilgang.', status=403)
	virksomhet = get_object_or_404(Virksomhet, pk=vid)
	node = get_object_or_404(RiskFrameworkNode, pk=nid, framework=framework)
	body = _parse_json_body(request)
	if body is None:
		return _json_error('Ugyldig JSON.')
	try:
		k = int(body['konsekvens_nivaa'])
		s = int(body['sannsynlighet_nivaa'])
	except (KeyError, TypeError, ValueError):
		return _json_error('Konsekvens og sannsynlighet må være tall 1–5.')
	if not (1 <= k <= 5 and 1 <= s <= 5):
		return _json_error('Konsekvens og sannsynlighet må være mellom 1 og 5.')
	assessment = save_node_assessment(
		virksomhet,
		node,
		request.user,
		k,
		s,
		begrunnelse=(body.get('begrunnelse') or '').strip(),
	)
	return _json_ok({'assessment_pk': assessment.pk})


@require_http_methods(['POST'])
def api_risiko_rammeverk_assessment_apply(request, slug, vid, nid):
	framework = _framework_or_404(slug)
	if not user_can_edit_framework(request.user):
		return _json_error('Ingen tilgang.', status=403)
	virksomhet = get_object_or_404(Virksomhet, pk=vid)
	node = get_object_or_404(RiskFrameworkNode, pk=nid, framework=framework)
	assessment = apply_suggestion_to_assessment(virksomhet, node, request.user)
	if assessment is None:
		return _json_error('Ingen veiledende nivå å overføre.')
	return _json_ok({'assessment_pk': assessment.pk})
