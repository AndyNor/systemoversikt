# -*- coding: utf-8 -*-
# 2026-07-07: Mal JSON export/import – superuser-only transfer between environments.
# 2026-07-06: Kartlegging view passes risk matrix for client-side label fallback.
# 2026-07-06: Enrich rollup with subcategory scenario/tiltak breakdown for detail view.
# 2026-07-06: Category-level matrix on sammenstilling detail – nåværende risiko only.
# Change log:
# 2026-07-06: risiko_mal_rediger – superuser-only via user_can_edit_template.
# 2026-07-06: Import user_can_view_sammenstilling – fixes NameError on sammenstilling detail.
# 2026-07-06: Templates + group-owned sammenstillinger – mal editor superuser-only.
# 2026-07-06: Rollup/tilgangsgrupper links – fall back to framework virksomhet for superuser testers.
# 2026-07-06: Reuse virksomhet tilgangsgrupper – link to /virksomhet/<vid>/tilgangsgrupper/ for group admin.
# 2026-07-06: Framework tilgangsgrupper – per-framework access; virksomhet nav scoped to risk border.
# 2026-07-06: Risk framework pages – list, virksomhet rollup, mapping workspace, taxonomy editor.

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from systemoversikt.risk_criteria import get_active_criteria
from systemoversikt.risk_framework import (
	build_rollup_tree,
	build_sammenstilling_category_matrix,
	enrich_rollup_tree_detail,
	get_active_framework,
)
from systemoversikt.risk_framework_transfer import (
	apply_mal_import_to_framework,
	build_mal_export_payload,
	create_mal_from_import,
	parse_mal_import_payload,
)
from systemoversikt.risk_sammenstilling import (
	active_templates_queryset,
	groups_user_can_own_sammenstilling,
	sammenstillinger_visible_to_user,
	user_can_edit_template,
	user_can_map_sammenstilling,
	user_can_view_sammenstilling,
)
from systemoversikt.views_risiko import _render_risk_access_denied


def _require_template_edit(user):
	if not user_can_edit_template(user):
		raise Http404


def _read_json_upload(upload):
	try:
		raw_text = upload.read().decode('utf-8')
		return json.loads(raw_text)
	except (UnicodeDecodeError, json.JSONDecodeError) as exc:
		raise ValueError('Ugyldig JSON-fil: %s' % exc)


def _mal_api_urls(slug):
	return {
		'taxonomy': reverse('api_risiko_mal_taxonomy', kwargs={'slug': slug}),
		'nodeCreate': reverse('api_risiko_mal_node_create', kwargs={'slug': slug}),
		'nodeUpdate': reverse('api_risiko_mal_node_update', kwargs={'slug': slug, 'nid': 0}).replace('/0/', '/{id}/'),
		'nodeMove': reverse('api_risiko_mal_node_move', kwargs={'slug': slug, 'nid': 0}).replace('/0/', '/{id}/'),
		'activeNodes': reverse('api_risiko_mal_active_nodes', kwargs={'slug': slug}),
	}


def _sammenstilling_api_urls(pk):
	return {
		'taxonomy': reverse('api_risiko_sammenstilling_taxonomy', kwargs={'pk': pk}),
		'activeNodes': reverse('api_risiko_sammenstilling_active_nodes', kwargs={'pk': pk}),
		'scenarioSearch': reverse('api_risiko_sammenstilling_scenarios', kwargs={'pk': pk}),
		'linkCreate': reverse('api_risiko_sammenstilling_link_create', kwargs={'pk': pk}),
		'linkDelete': reverse('api_risiko_sammenstilling_link_delete', kwargs={'pk': pk, 'lid': 0}).replace('/0/', '/{id}/'),
		'rollup': reverse('api_risiko_sammenstilling_rollup', kwargs={'pk': pk}),
		'nodeScenarios': reverse('api_risiko_sammenstilling_node_scenarios', kwargs={'pk': pk, 'nid': 0}).replace('/nodes/0/', '/nodes/{id}/'),
		'assessmentSave': reverse('api_risiko_sammenstilling_assessment_save', kwargs={'pk': pk, 'nid': 0}).replace('/nodes/0/', '/nodes/{id}/'),
		'assessmentApply': reverse('api_risiko_sammenstilling_assessment_apply', kwargs={'pk': pk, 'nid': 0}).replace('/nodes/0/', '/nodes/{id}/'),
	}


def _sammenstilling_or_404(pk):
	from systemoversikt.risk_sammenstilling import get_active_sammenstilling
	sammenstilling = get_active_sammenstilling(pk)
	if sammenstilling is None:
		raise Http404('Sammenstillingen finnes ikke eller er deaktivert.')
	return sammenstilling


@login_required
def risiko_rammeverk_list(request):
	templates = active_templates_queryset()
	sammenstillinger = sammenstillinger_visible_to_user(request.user)
	owner_groups = groups_user_can_own_sammenstilling(request.user)
	return render(request, 'risiko_rammeverk_list.html', {
		'request': request,
		'required_permissions': [],
		'templates': templates,
		'sammenstillinger': sammenstillinger,
		'can_edit_template': user_can_edit_template(request.user),
		'can_create_sammenstilling': owner_groups.exists(),
	})


@login_required
@require_GET
def risiko_mal_eksporter(request, slug):
	# 2026-07-07: Superuser JSON download for moving mal taxonomy between environments.
	_require_template_edit(request.user)
	framework = get_active_framework(slug)
	if framework is None:
		raise Http404('Malen finnes ikke eller er deaktivert.')
	payload = build_mal_export_payload(framework, request.user)
	filename = 'risiko-mal-%s.json' % framework.slug
	response = HttpResponse(
		json.dumps(payload, ensure_ascii=False, indent=2),
		content_type='application/json; charset=utf-8',
	)
	response['Content-Disposition'] = 'attachment; filename="%s"' % filename
	return response


@login_required
@require_http_methods(['POST'])
def risiko_mal_importer(request, slug):
	# 2026-07-07: Superuser JSON upload – replaces mal taxonomy when no kartlegging data exists.
	_require_template_edit(request.user)
	framework = get_active_framework(slug)
	if framework is None:
		raise Http404('Malen finnes ikke eller er deaktivert.')
	if not request.POST.get('confirm_import'):
		messages.error(request, 'Bekreft at du vil erstatte taksonomien for denne malen.')
		return redirect('risiko_mal_rediger', slug=slug)

	upload = request.FILES.get('malfil')
	if not upload:
		messages.error(request, 'Velg en JSON-fil å laste opp.')
		return redirect('risiko_mal_rediger', slug=slug)

	try:
		raw_dict = _read_json_upload(upload)
	except ValueError as exc:
		messages.error(request, str(exc))
		return redirect('risiko_mal_rediger', slug=slug)

	try:
		framework_meta, taxonomy = parse_mal_import_payload(raw_dict)
	except ValueError as exc:
		messages.error(request, str(exc))
		return redirect('risiko_mal_rediger', slug=slug)

	errors = apply_mal_import_to_framework(framework, framework_meta, taxonomy)
	if errors:
		for err in errors:
			messages.error(request, err)
		return redirect('risiko_mal_rediger', slug=slug)

	messages.success(request, 'Malen «%s» er oppdatert fra fil.' % framework.title)
	return redirect('risiko_mal_rediger', slug=slug)


@login_required
@require_http_methods(['POST'])
def risiko_mal_opprett_fra_fil(request):
	# 2026-07-07: Superuser creates a new mal from exported JSON file.
	_require_template_edit(request.user)
	if not request.POST.get('confirm_create'):
		messages.error(request, 'Bekreft at du vil opprette en ny mal fra filen.')
		return redirect('risiko_rammeverk_list')

	upload = request.FILES.get('malfil')
	if not upload:
		messages.error(request, 'Velg en JSON-fil å laste opp.')
		return redirect('risiko_rammeverk_list')

	try:
		raw_dict = _read_json_upload(upload)
	except ValueError as exc:
		messages.error(request, str(exc))
		return redirect('risiko_rammeverk_list')

	try:
		framework_meta, taxonomy = parse_mal_import_payload(raw_dict)
	except ValueError as exc:
		messages.error(request, str(exc))
		return redirect('risiko_rammeverk_list')

	slug_override = (request.POST.get('slug') or '').strip() or None
	framework, errors = create_mal_from_import(framework_meta, taxonomy, slug_override=slug_override)
	if errors:
		for err in errors:
			messages.error(request, err)
		return redirect('risiko_rammeverk_list')

	messages.success(request, 'Ny mal «%s» er opprettet.' % framework.title)
	return redirect('risiko_mal_rediger', slug=framework.slug)


@login_required
def risiko_mal_rediger(request, slug):
	framework = get_active_framework(slug)
	if framework is None:
		raise Http404('Malen finnes ikke eller er deaktivert.')
	if not user_can_edit_template(request.user):
		return _render_risk_access_denied(request, 'template_edit', framework=framework)
	return render(request, 'risiko_mal_rediger.html', {
		'request': request,
		'required_permissions': [],
		'framework': framework,
		'framework_slug': slug,
		'api_urls_json': json.dumps(_mal_api_urls(slug)),
	})


@login_required
def risiko_sammenstilling_create(request):
	owner_groups = list(groups_user_can_own_sammenstilling(request.user))
	if not owner_groups:
		return _render_risk_access_denied(request, 'sammenstilling_create')
	templates = list(active_templates_queryset())
	if not templates:
		return _render_risk_access_denied(request, 'sammenstilling_no_templates')
	return render(request, 'risiko_sammenstilling_create.html', {
		'request': request,
		'required_permissions': [],
		'templates': templates,
		'owner_groups': owner_groups,
		'api_urls_json': json.dumps({
			'create': reverse('api_risiko_sammenstilling_create'),
			'options': reverse('api_risiko_sammenstilling_create_options'),
		}),
	})


@login_required
def risiko_sammenstilling_detail(request, pk):
	sammenstilling = _sammenstilling_or_404(pk)
	if not user_can_view_sammenstilling(request.user, sammenstilling):
		return _render_risk_access_denied(request, 'sammenstilling_view', sammenstilling=sammenstilling)
	rollup_tree = enrich_rollup_tree_detail(sammenstilling, build_rollup_tree(sammenstilling))
	criteria = get_active_criteria()
	return render(request, 'risiko_sammenstilling_detail.html', {
		'request': request,
		'required_permissions': [],
		'sammenstilling': sammenstilling,
		'framework': sammenstilling.framework,
		'can_map': user_can_map_sammenstilling(request.user, sammenstilling),
		'rollup_tree': rollup_tree,
		'matrix_current': build_sammenstilling_category_matrix(rollup_tree, criteria),
		'konsekvens_labels': criteria.konsekvens_labels,
		'api_urls_json': json.dumps(_sammenstilling_api_urls(pk)),
	})


@login_required
def risiko_sammenstilling_kartlegging(request, pk):
	sammenstilling = _sammenstilling_or_404(pk)
	if not user_can_map_sammenstilling(request.user, sammenstilling):
		return _render_risk_access_denied(request, 'sammenstilling_map', sammenstilling=sammenstilling)
	return render(request, 'risiko_sammenstilling_kartlegging.html', {
		'request': request,
		'required_permissions': [],
		'sammenstilling': sammenstilling,
		'framework': sammenstilling.framework,
		'api_urls_json': json.dumps(_sammenstilling_api_urls(pk)),
		'risk_meta_json': json.dumps({
			'risk_matrix': get_active_criteria().risk_matrix,
		}),
	})
