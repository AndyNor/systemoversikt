# -*- coding: utf-8 -*-
# Change log:
# 2026-07-06: Active nodes API – parent display code for kartlegging dropdown grouping.
# 2026-07-06: Mal taxonomy APIs require superuser for all methods – editor-only endpoints.
# 2026-07-06: Automatic category numbering – create always assigns next nummer; update ignores nummer.
# 2026-07-06: Superuser-only template taxonomy APIs – maler independent of virksomhet.

from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods

from systemoversikt.models import (
	RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
	RiskFrameworkNode,
)
from systemoversikt.risk_framework import (
	framework_nodes_queryset,
	get_active_framework,
	move_framework_node,
)
from systemoversikt.risk_sammenstilling import user_can_edit_template
from systemoversikt.api_risiko import _json_error, _parse_json_body


def _json_ok(payload=None, status=200):
	data = {'ok': True}
	if payload:
		data.update(payload)
	return JsonResponse(data, status=status)


def _framework_or_404(slug):
	framework = get_active_framework(slug)
	if framework is None:
		raise Http404
	return framework


def _require_template_edit(request):
	if not user_can_edit_template(request.user):
		return _json_error('Ingen tilgang.', status=403)
	return None


def _node_payload(node, include_children=False):
	data = {
		'pk': node.pk,
		'parent_pk': node.parent_id,
		'nummer': node.nummer,
		'display_code': node.display_code(),
		'title': node.title,
		'forklaring': node.forklaring,
		'status': node.status,
		'is_leaf': node.is_leaf(),
		'link_count': node.sammenstilling_links.count(),
		'assessment_count': node.sammenstilling_assessments.count(),
	}
	if include_children:
		children = node.children.order_by('nummer')
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


@login_required
@require_GET
def api_risiko_mal_taxonomy(request, slug):
	framework = _framework_or_404(slug)
	denied = _require_template_edit(request)
	if denied:
		return denied
	include_archived = request.GET.get('include_archived') == '1'
	return _json_ok({'tree': _taxonomy_tree(framework, include_archived=include_archived)})


@login_required
@require_GET
def api_risiko_mal_active_nodes(request, slug):
	framework = _framework_or_404(slug)
	denied = _require_template_edit(request)
	if denied:
		return denied
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
				'parent_pk': n.parent_id,
				'parent_display_code': n.parent.display_code() if n.parent_id else '',
				'parent_title': n.parent.title if n.parent_id else '',
			}
			for n in leaves
		],
		'categories': [
			{'pk': n.pk, 'display_code': n.display_code(), 'title': n.title}
			for n in RiskFrameworkNode.objects.filter(
				framework=framework,
				status=RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
				parent__isnull=True,
			).order_by('nummer')
		],
	})


@login_required
@require_http_methods(['POST'])
def api_risiko_mal_node_create(request, slug):
	framework = _framework_or_404(slug)
	denied = _require_template_edit(request)
	if denied:
		return denied
	body = _parse_json_body(request)
	if body is None:
		return _json_error('Ugyldig JSON.')

	parent_pk = body.get('parent_pk')
	parent = None
	if parent_pk not in (None, '', 0, '0'):
		parent = get_object_or_404(RiskFrameworkNode, pk=parent_pk, framework=framework)

	siblings = RiskFrameworkNode.objects.filter(framework=framework, parent=parent)
	next_nummer = (siblings.aggregate(m=Max('nummer'))['m'] or 0) + 1

	node = RiskFrameworkNode.objects.create(
		framework=framework,
		parent=parent,
		nummer=next_nummer,
		title=(body.get('title') or 'Ny kategori').strip(),
		forklaring=(body.get('forklaring') or '').strip(),
	)
	return _json_ok({'node': _node_payload(node)})


@login_required
@require_http_methods(['POST'])
def api_risiko_mal_node_update(request, slug, nid):
	framework = _framework_or_404(slug)
	denied = _require_template_edit(request)
	if denied:
		return denied
	node = get_object_or_404(RiskFrameworkNode, pk=nid, framework=framework)
	body = _parse_json_body(request)
	if body is None:
		return _json_error('Ugyldig JSON.')

	if 'title' in body:
		node.title = (body.get('title') or '').strip()
	if 'forklaring' in body:
		node.forklaring = (body.get('forklaring') or '').strip()
	node.save()
	return _json_ok({'node': _node_payload(node)})


@login_required
@require_http_methods(['POST'])
def api_risiko_mal_node_move(request, slug, nid):
	framework = _framework_or_404(slug)
	denied = _require_template_edit(request)
	if denied:
		return denied
	node = get_object_or_404(RiskFrameworkNode, pk=nid, framework=framework)
	body = _parse_json_body(request)
	if body is None:
		return _json_error('Ugyldig JSON.')
	parent_pk = body.get('parent_id') or body.get('parent_pk')
	if not parent_pk:
		return _json_error('Velg hovedkategori.')
	new_parent = get_object_or_404(
		RiskFrameworkNode,
		pk=parent_pk,
		framework=framework,
		parent__isnull=True,
	)
	try:
		move_framework_node(node, new_parent)
	except ValueError as exc:
		return _json_error(str(exc))
	return _json_ok({'node': _node_payload(node)})
