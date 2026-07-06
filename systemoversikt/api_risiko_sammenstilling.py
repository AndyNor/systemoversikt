# -*- coding: utf-8 -*-
# 2026-07-06: Manual assessment restricted to main categories (hovedkategori).
# Change log:
# 2026-07-06: Kartlegging scenario search – eskaleres_only filter parameter.
# 2026-07-06: Kartlegging scenario search includes nåværende and etter-tiltak risk labels.
# 2026-07-06: Group-owned sammenstilling APIs – mapping, rollup, assessments with scope-level access.

from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods

from systemoversikt.models import (
	RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
	RiskFrameworkNode,
	RiskSammenstilling,
	RiskSammenstillingScenarioLink,
	RiskScenario,
)
from systemoversikt.risk_framework import (
	apply_suggestion_to_assessment,
	build_rollup_tree,
	kartlegging_scenario_rows,
	mapped_scenarios_detail,
	save_node_assessment,
	search_scenarios_for_mapping,
)
from systemoversikt.api_risiko_rammeverk import _taxonomy_tree as mal_taxonomy_tree
from systemoversikt.api_risiko import _json_error, _parse_json_body
from systemoversikt.risk_sammenstilling import (
	get_active_sammenstilling,
	groups_user_can_own_sammenstilling,
	user_can_create_sammenstilling,
	user_can_map_scenario,
	user_can_map_sammenstilling,
	user_can_view_sammenstilling,
)


def _json_ok(payload=None, status=200):
	data = {'ok': True}
	if payload:
		data.update(payload)
	return JsonResponse(data, status=status)


def _sammenstilling_or_404(pk):
	sammenstilling = get_active_sammenstilling(pk)
	if sammenstilling is None:
		raise Http404
	return sammenstilling


def _require_sammenstilling_view(request, sammenstilling):
	if not user_can_view_sammenstilling(request.user, sammenstilling):
		return _json_error('Ingen tilgang.', status=403)
	return None


def _require_sammenstilling_map(request, sammenstilling):
	if not user_can_map_sammenstilling(request.user, sammenstilling):
		return _json_error('Ingen tilgang.', status=403)
	return None


@require_http_methods(['POST'])
def api_risiko_sammenstilling_create(request):
	body = _parse_json_body(request)
	if body is None:
		return _json_error('Ugyldig JSON.')
	title = (body.get('title') or '').strip()
	framework_id = body.get('framework_id')
	owner_group_id = body.get('owner_group_id')
	if not title or not framework_id or not owner_group_id:
		return _json_error('Tittel, mal og eiergruppe er påkrevd.')
	from systemoversikt.models import RiskFramework, RiskVirksomhetGroup
	framework = get_object_or_404(RiskFramework, pk=framework_id, is_active=True)
	group = get_object_or_404(RiskVirksomhetGroup, pk=owner_group_id)
	if not user_can_create_sammenstilling(request.user, group):
		return _json_error('Du må være medlem av eiergruppen.', status=403)
	if RiskSammenstilling.objects.filter(owner_group=group, title=title).exists():
		return _json_error('Gruppen har allerede en sammenstilling med dette navnet.')
	sammenstilling = RiskSammenstilling.objects.create(
		title=title,
		beskrivelse=(body.get('beskrivelse') or '').strip(),
		framework=framework,
		owner_group=group,
		created_by=request.user,
	)
	return _json_ok({'pk': sammenstilling.pk})


@require_GET
def api_risiko_sammenstilling_create_options(request):
	groups = groups_user_can_own_sammenstilling(request.user)
	from systemoversikt.risk_sammenstilling import active_templates_queryset
	frameworks = active_templates_queryset()
	return _json_ok({
		'groups': [
			{
				'id': g.pk,
				'title': g.display_title,
				'virksomhet': g.virksomhet.virksomhetsforkortelse if g.virksomhet_id else '',
			}
			for g in groups
		],
		'frameworks': [
			{'id': f.pk, 'title': f.title, 'slug': f.slug}
			for f in frameworks
		],
	})


@require_GET
def api_risiko_sammenstilling_taxonomy(request, pk):
	sammenstilling = _sammenstilling_or_404(pk)
	denied = _require_sammenstilling_view(request, sammenstilling)
	if denied:
		return denied
	return _json_ok({'tree': mal_taxonomy_tree(sammenstilling.framework)})


@require_GET
def api_risiko_sammenstilling_active_nodes(request, pk):
	sammenstilling = _sammenstilling_or_404(pk)
	denied = _require_sammenstilling_map(request, sammenstilling)
	if denied:
		return denied
	framework = sammenstilling.framework
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


@require_GET
def api_risiko_sammenstilling_scenarios(request, pk):
	sammenstilling = _sammenstilling_or_404(pk)
	denied = _require_sammenstilling_map(request, sammenstilling)
	if denied:
		return denied
	virksomhet_id = request.GET.get('virksomhet_id')
	scope_id = request.GET.get('scope_id')
	unmapped_only = request.GET.get('unmapped_only') == '1'
	eskaleres_only = request.GET.get('eskaleres_only') == '1'
	q = (request.GET.get('q') or '').strip()
	qs = search_scenarios_for_mapping(
		sammenstilling,
		request.user,
		virksomhet_id=int(virksomhet_id) if virksomhet_id else None,
		scope_id=int(scope_id) if scope_id else None,
		unmapped_only=unmapped_only,
		eskaleres_only=eskaleres_only,
		q=q,
	)[:200]
	rows = kartlegging_scenario_rows(sammenstilling, list(qs))
	return _json_ok({'scenarios': rows})


@require_http_methods(['POST'])
def api_risiko_sammenstilling_link_create(request, pk):
	sammenstilling = _sammenstilling_or_404(pk)
	denied = _require_sammenstilling_map(request, sammenstilling)
	if denied:
		return denied
	body = _parse_json_body(request)
	if body is None:
		return _json_error('Ugyldig JSON.')
	scenario_ids = body.get('scenario_ids') or []
	node_pk = body.get('node_pk')
	if not scenario_ids or not node_pk:
		return _json_error('Velg scenarioer og underkategori.')
	node = get_object_or_404(
		RiskFrameworkNode,
		pk=node_pk,
		framework=sammenstilling.framework,
		status=RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
		parent__isnull=False,
	)
	created = []
	skipped = 0
	with transaction.atomic():
		for sid in scenario_ids:
			scenario = get_object_or_404(RiskScenario, pk=sid)
			if not user_can_map_scenario(request.user, scenario):
				skipped += 1
				continue
			link, was_created = RiskSammenstillingScenarioLink.objects.get_or_create(
				sammenstilling=sammenstilling,
				scenario=scenario,
				framework_node=node,
				defaults={'mapped_by': request.user},
			)
			if was_created:
				created.append(link.pk)
	if not created and skipped:
		return _json_error('Ingen av scenarioene er innenfor din tilgang til risikosamlinger.', status=403)
	return _json_ok({'created_count': len(created), 'skipped_count': skipped})


@require_http_methods(['POST'])
def api_risiko_sammenstilling_link_delete(request, pk, lid):
	sammenstilling = _sammenstilling_or_404(pk)
	denied = _require_sammenstilling_map(request, sammenstilling)
	if denied:
		return denied
	link = get_object_or_404(
		RiskSammenstillingScenarioLink,
		pk=lid,
		sammenstilling=sammenstilling,
	)
	scenario = link.scenario
	if not user_can_map_scenario(request.user, scenario):
		return _json_error('Ingen tilgang til dette scenarioet.', status=403)
	link.delete()
	return _json_ok({})


@require_GET
def api_risiko_sammenstilling_rollup(request, pk):
	sammenstilling = _sammenstilling_or_404(pk)
	denied = _require_sammenstilling_view(request, sammenstilling)
	if denied:
		return denied
	return _json_ok({'tree': build_rollup_tree(sammenstilling)})


@require_GET
def api_risiko_sammenstilling_node_scenarios(request, pk, nid):
	sammenstilling = _sammenstilling_or_404(pk)
	denied = _require_sammenstilling_view(request, sammenstilling)
	if denied:
		return denied
	node = get_object_or_404(RiskFrameworkNode, pk=nid, framework=sammenstilling.framework)
	return _json_ok({'scenarios': mapped_scenarios_detail(sammenstilling, node)})


@require_http_methods(['POST'])
def api_risiko_sammenstilling_assessment_save(request, pk, nid):
	sammenstilling = _sammenstilling_or_404(pk)
	denied = _require_sammenstilling_map(request, sammenstilling)
	if denied:
		return denied
	node = get_object_or_404(RiskFrameworkNode, pk=nid, framework=sammenstilling.framework)
	if node.parent_id is not None:
		return _json_error('Risikonivå settes kun på hovedkategori.')
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
		sammenstilling,
		node,
		request.user,
		k,
		s,
		begrunnelse=(body.get('begrunnelse') or '').strip(),
	)
	return _json_ok({'assessment_pk': assessment.pk})


@require_http_methods(['POST'])
def api_risiko_sammenstilling_assessment_apply(request, pk, nid):
	sammenstilling = _sammenstilling_or_404(pk)
	denied = _require_sammenstilling_map(request, sammenstilling)
	if denied:
		return denied
	node = get_object_or_404(RiskFrameworkNode, pk=nid, framework=sammenstilling.framework)
	if node.parent_id is not None:
		return _json_error('Risikonivå settes kun på hovedkategori.')
	assessment = apply_suggestion_to_assessment(sammenstilling, node, request.user)
	if assessment is None:
		return _json_error('Ingen veiledende nivå å overføre.')
	return _json_ok({'assessment_pk': assessment.pk})
