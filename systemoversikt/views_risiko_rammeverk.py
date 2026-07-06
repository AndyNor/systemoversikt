# -*- coding: utf-8 -*-
# Change log:
# 2026-07-06: Risk framework pages – list, virksomhet rollup, mapping workspace, taxonomy editor.

import json

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from systemoversikt.models import RiskFramework, Virksomhet
from systemoversikt.risk_framework import (
	build_rollup_tree,
	get_active_framework,
	user_can_edit_framework,
	user_can_view_virksomhet_framework,
)
from systemoversikt.risk_membership import nav_ordinary_virksomheter, profile_virksomhet
from systemoversikt.views_risiko import _render_risk_access_denied


def _framework_or_404(slug):
	framework = get_active_framework(slug)
	if framework is None:
		raise Http404('Rammeverket finnes ikke eller er deaktivert.')
	return framework


def _framework_context(request, framework, slug):
	can_edit = user_can_edit_framework(request.user)
	return {
		'request': request,
		'required_permissions': [],
		'framework': framework,
		'framework_slug': slug,
		'can_edit_framework': can_edit,
		'nav_virksomheter': nav_ordinary_virksomheter(),
		'profile_virksomhet': profile_virksomhet(request.user),
	}


def _rammeverk_api_urls(slug, vid=None):
	urls = {
		'taxonomy': reverse('api_risiko_rammeverk_taxonomy', kwargs={'slug': slug}),
		'nodeCreate': reverse('api_risiko_rammeverk_node_create', kwargs={'slug': slug}),
		'nodeUpdate': reverse('api_risiko_rammeverk_node_update', kwargs={'slug': slug, 'nid': 0}).replace('/0/', '/{id}/'),
		'nodeArchive': reverse('api_risiko_rammeverk_node_archive', kwargs={'slug': slug, 'nid': 0}).replace('/0/', '/{id}/'),
		'nodeRetire': reverse('api_risiko_rammeverk_node_retire', kwargs={'slug': slug, 'nid': 0}).replace('/0/', '/{id}/'),
		'scenarioSearch': reverse('api_risiko_rammeverk_scenarios', kwargs={'slug': slug}),
		'linkCreate': reverse('api_risiko_rammeverk_link_create', kwargs={'slug': slug}),
		'linkDelete': reverse('api_risiko_rammeverk_link_delete', kwargs={'slug': slug, 'lid': 0}).replace('/0/', '/{id}/'),
		'activeNodes': reverse('api_risiko_rammeverk_active_nodes', kwargs={'slug': slug}),
	}
	if vid is not None:
		urls['rollup'] = reverse('api_risiko_rammeverk_rollup', kwargs={'slug': slug, 'vid': vid})
		urls['assessmentSave'] = reverse('api_risiko_rammeverk_assessment_save', kwargs={'slug': slug, 'vid': vid, 'nid': 0}).replace('/nodes/0/', '/nodes/{id}/')
		urls['assessmentApply'] = reverse('api_risiko_rammeverk_assessment_apply', kwargs={'slug': slug, 'vid': vid, 'nid': 0}).replace('/nodes/0/', '/nodes/{id}/')
		urls['nodeScenarios'] = reverse('api_risiko_rammeverk_node_scenarios', kwargs={'slug': slug, 'vid': vid, 'nid': 0}).replace('/nodes/0/', '/nodes/{id}/')
	return urls


def risiko_rammeverk_list(request):
	frameworks = RiskFramework.objects.filter(is_active=True).order_by('title')
	return render(request, 'risiko_rammeverk_list.html', {
		'request': request,
		'required_permissions': [],
		'frameworks': frameworks,
		'can_edit_framework': user_can_edit_framework(request.user),
		'profile_virksomhet': profile_virksomhet(request.user),
	})


def risiko_rammeverk_virksomhet(request, slug, vid):
	framework = _framework_or_404(slug)
	virksomhet = get_object_or_404(Virksomhet, pk=vid)
	if not user_can_view_virksomhet_framework(request.user, virksomhet.pk):
		return _render_risk_access_denied(request, 'collection_read', virksomhet=virksomhet)

	rollup_tree = build_rollup_tree(framework, virksomhet.pk)
	ctx = _framework_context(request, framework, slug)
	ctx.update({
		'virksomhet': virksomhet,
		'list_virksomhet': virksomhet,
		'rollup_tree': rollup_tree,
		'api_urls_json': json.dumps(_rammeverk_api_urls(slug, vid=virksomhet.pk)),
	})
	return render(request, 'risiko_rammeverk_virksomhet.html', ctx)


def risiko_rammeverk_kartlegging(request, slug):
	framework = _framework_or_404(slug)
	if not user_can_edit_framework(request.user):
		return _render_risk_access_denied(request, 'create_collection')

	ctx = _framework_context(request, framework, slug)
	ctx.update({
		'api_urls_json': json.dumps(_rammeverk_api_urls(slug)),
		'nav_virksomheter': nav_ordinary_virksomheter(),
	})
	return render(request, 'risiko_rammeverk_kartlegging.html', ctx)


def risiko_rammeverk_rediger(request, slug):
	framework = _framework_or_404(slug)
	if not user_can_edit_framework(request.user):
		return _render_risk_access_denied(request, 'create_collection')

	ctx = _framework_context(request, framework, slug)
	ctx['api_urls_json'] = json.dumps(_rammeverk_api_urls(slug))
	return render(request, 'risiko_rammeverk_rediger.html', ctx)
