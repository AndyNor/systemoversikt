# -*- coding: utf-8 -*-
# Change log:
# 2026-06-30: Multiple owners/participants + virksomhet – member vs owner access checks.
# 2026-06-26: Scenario-scoped action URLs for tiltak editing inside scenario modal.
# 2026-06-26: Editor URLs for scope-level tiltak CRUD API.
# 2026-06-26: Scenario table Tiltak column shows T# IDs instead of action count.
# 2026-06-26: Display-time R/T IDs; scope-level tiltak rows; «Tilknyttede systemer» label.
# 2026-06-25: Scenario detail URL redirects to scope page edit modal.
# 2026-06-25: Akseptkriterier on detail – reference matrix table removed from partial.
# 2026-06-25: List all scopes; 403 on non-owner detail; manual create; akseptkriterier on detail page.
# 2026-06-24: Risk matrices on scope detail; /matrise/ redirects to anchor.
# 2026-06-24: Scope detail – AJAX editor config; legacy POST forms removed.
# 2026-06-24: Scope/scenario/action views owner-only; list page open but shows only own collections.
# 2026-06-24: Risk list open to all users; scope beskrivelse; edit metadata on detail page.
# 2026-06-24: Accept view_qualysvuln for risk views – same audience as vulnstats/BloodHound until group_permissions import.
# 2026-06-24: Security risk module views – list, import, detail, matrix, akseptkriterier.

from datetime import date

from django.contrib import messages
from django.db.models import Count, Exists, OuterRef, Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from openpyxl import load_workbook

from systemoversikt.models import (
	RISK_SCOPE_MEMBER_ROLE_OWNER,
	RISK_SCOPE_MEMBER_ROLE_PARTICIPANT,
	RiskScope,
	RiskScopeMember,
	RiskScenario,
)
from systemoversikt.risk_criteria import (
	KONSEKVENS_BESKRIVELSER,
	KONSEKVENS_DIMENSJONER,
	KONSEKVENS_LABELS,
	RISK_MATRIX,
	SANNSYNLIGHET_BESKRIVELSER,
	SANNSYNLIGHET_LABELS,
	level_cell_css_class,
	konsekvens_lookup_label,
	matrix_placements,
	risk_cell_css_class,
	risk_label,
	sannsynlighet_lookup_label,
)
from systemoversikt.risk_display import (
	annotate_scenario_display_ids,
	annotate_scenarios_tiltak_ids,
	build_scope_tiltak_rows,
)
from systemoversikt.risk_import import import_risk_workbook
from systemoversikt.risk_membership import create_risk_scope
from systemoversikt.views import formater_permissions

# Import restricted to security analysts; detail restricted to scope members.
RISK_WRITE_PERMISSIONS = ['systemoversikt.add_riskscope', 'systemoversikt.view_qualysvuln']


def _scope_membership(request, scope):
	if not request.user.is_authenticated:
		return None
	if hasattr(scope, '_user_membership'):
		return scope._user_membership
	membership = scope.memberships.filter(user_id=request.user.id).first()
	scope._user_membership = membership
	return membership


def _is_scope_owner(request, scope):
	membership = _scope_membership(request, scope)
	return membership is not None and membership.role == RISK_SCOPE_MEMBER_ROLE_OWNER


def _is_scope_member(request, scope):
	return _scope_membership(request, scope) is not None


def _get_member_scope(request, scope_id):
	scope = get_object_or_404(
		RiskScope.objects.select_related('virksomhet').prefetch_related(
			Prefetch(
				'memberships',
				queryset=RiskScopeMember.objects.select_related('user').order_by('role', 'user__first_name', 'user__username'),
			),
		),
		pk=scope_id,
	)
	if not _is_scope_member(request, scope):
		raise Http404
	return scope


def _get_managed_scope(request, scope_id):
	scope = _get_member_scope(request, scope_id)
	if not _is_scope_owner(request, scope):
		raise Http404
	return scope


# Backward-compatible aliases used by api_risiko imports.
_get_owned_scope = _get_member_scope


def _get_member_scenario(request, scope_id, scenario_id):
	scope = _get_member_scope(request, scope_id)
	scenario = get_object_or_404(RiskScenario, pk=scenario_id, scope=scope)
	return scope, scenario


_get_owned_scenario = _get_member_scenario


def _deny_scope_access(request):
	# 2026-06-25: 403 (not 404) when list shows all collections – existence is already public.
	return render(request, '403.html', {
		'request': request,
		'required_permissions': [],
		'groups': request.user.groups,
	})


def _check_permissions(request, required_permissions):
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {
			'required_permissions': required_permissions,
			'groups': request.user.groups,
		})
	return None


def _risiko_editor_urls(scope_pk):
	pk = scope_pk
	return {
		'meta': reverse('api_risiko_meta', kwargs={'pk': pk}),
		'scenarios': reverse('api_risiko_scenarios_list', kwargs={'pk': pk}),
		'scenarioCreate': reverse('api_risiko_scenario_create', kwargs={'pk': pk}),
		'scenarioDetail': reverse('api_risiko_scenario_detail', kwargs={'pk': pk, 'sid': 0}).replace('/0/', '/{id}/'),
		'scenarioUpdate': reverse('api_risiko_scenario_update', kwargs={'pk': pk, 'sid': 0}).replace('/0/', '/{id}/'),
		'scenarioDelete': reverse('api_risiko_scenario_delete', kwargs={'pk': pk, 'sid': 0}).replace('/0/', '/{id}/'),
		'scenarioActionCreate': reverse('api_risiko_action_create', kwargs={'pk': pk, 'sid': 0}).replace('/scenarios/0/', '/scenarios/{scenarioId}/'),
		'scenarioActionUpdate': reverse('api_risiko_action_update', kwargs={'pk': pk, 'sid': 0, 'aid': 0}).replace('/scenarios/0/', '/scenarios/{scenarioId}/').replace('/actions/0/', '/actions/{id}/'),
		'scenarioActionDelete': reverse('api_risiko_action_delete', kwargs={'pk': pk, 'sid': 0, 'aid': 0}).replace('/scenarios/0/', '/scenarios/{scenarioId}/').replace('/actions/0/', '/actions/{id}/'),
		'actionCreate': reverse('api_risiko_scope_action_create', kwargs={'pk': pk}),
		'actionUpdate': reverse('api_risiko_scope_action_update', kwargs={'pk': pk, 'aid': 0}).replace('/0/', '/{id}/'),
		'actionDelete': reverse('api_risiko_scope_action_delete', kwargs={'pk': pk, 'aid': 0}).replace('/0/', '/{id}/'),
		'scopeUpdate': reverse('api_risiko_scope_update', kwargs={'pk': pk}),
		'systemSearch': reverse('api_risiko_systemer_sok'),
		'members': reverse('api_risiko_members_list', kwargs={'pk': pk}),
		'memberAdd': reverse('api_risiko_member_add', kwargs={'pk': pk}),
		'memberRemove': reverse('api_risiko_member_remove', kwargs={'pk': pk, 'user_id': 0}).replace('/0/', '/{userId}/'),
		'scopeVirksomhet': reverse('api_risiko_scope_virksomhet', kwargs={'pk': pk}),
		'brukerSearch': reverse('api_risiko_brukere_sok', kwargs={'pk': pk}),
		'virksomhetSearch': reverse('api_risiko_virksomheter_sok', kwargs={'pk': pk}),
		'scopePage': reverse('risiko_scope_detail', kwargs={'pk': pk}),
	}


def risiko_scope_list(request):
	# 2026-06-30: Green checkmark on list when current user is owner or participant.
	# 2026-06-25: Open landing page lists all collections; detail remains member-only.
	member_qs = RiskScopeMember.objects.filter(
		scope=OuterRef('pk'),
		user=request.user,
	)
	scopes = (
		RiskScope.objects.select_related('virksomhet')
		.prefetch_related(
			Prefetch(
				'memberships',
				queryset=RiskScopeMember.objects.filter(
					role=RISK_SCOPE_MEMBER_ROLE_OWNER,
				).select_related('user'),
			),
		)
		.annotate(
			scenario_count=Count('scenarios'),
			current_user_is_member=Exists(member_qs),
		)
		.order_by('-sist_revidert', '-opprettet')
	)
	can_write = any(map(request.user.has_perm, RISK_WRITE_PERMISSIONS))
	return render(request, 'risiko_scope_list.html', {
		'request': request,
		'required_permissions': [],
		'scopes': scopes,
		'can_import': can_write,
		'can_create': can_write,
	})


def risiko_import(request):
	denied = _check_permissions(request, RISK_WRITE_PERMISSIONS)
	if denied:
		return denied

	if request.method == 'POST':
		upload = request.FILES.get('risikofil')
		if not upload:
			messages.error(request, 'Velg en Excel-fil (.xlsx) å laste opp.')
		elif not upload.name.lower().endswith(('.xlsx', '.xlsm')):
			messages.error(request, 'Kun .xlsx/.xlsm-filer støttes.')
		else:
			try:
				workbook = load_workbook(upload, data_only=True)
				result = import_risk_workbook(workbook, request.user, upload.name)
				for warning in result.warnings:
					messages.warning(request, warning)
				messages.success(
					request,
					'Importert %d scenarioer og %d tiltak.' % (result.scenario_count, result.action_count),
				)
				return redirect('risiko_scope_detail', pk=result.scope.pk)
			except Exception as exc:
				messages.error(request, 'Import feilet: %s' % exc)

	return render(request, 'risiko_import.html', {
		'request': request,
		'required_permissions': formater_permissions(RISK_WRITE_PERMISSIONS),
	})


def risiko_scope_create(request):
	# 2026-06-25: Manual collection create – same audience as Excel import.
	denied = _check_permissions(request, RISK_WRITE_PERMISSIONS)
	if denied:
		return denied

	if request.method == 'POST':
		title = (request.POST.get('title') or '').strip()
		beskrivelse = (request.POST.get('beskrivelse') or '').strip()
		sist_revidert_raw = (request.POST.get('sist_revidert') or '').strip()
		if not title:
			messages.error(request, 'Navn er påkrevd.')
		else:
			sist_revidert = date.today()
			if sist_revidert_raw:
				try:
					sist_revidert = date.fromisoformat(sist_revidert_raw[:10])
				except ValueError:
					messages.error(request, 'Ugyldig dato – bruk format ÅÅÅÅ-MM-DD.')
					return render(request, 'risiko_scope_create.html', {
						'request': request,
						'required_permissions': formater_permissions(RISK_WRITE_PERMISSIONS),
						'title': title,
						'beskrivelse': beskrivelse,
						'sist_revidert': sist_revidert_raw,
					})
			scope = create_risk_scope(
				request.user,
				title=title,
				beskrivelse=beskrivelse,
				sist_revidert=sist_revidert,
			)
			messages.success(request, 'Risikosamling opprettet.')
			return redirect('risiko_scope_detail', pk=scope.pk)

	return render(request, 'risiko_scope_create.html', {
		'request': request,
		'required_permissions': formater_permissions(RISK_WRITE_PERMISSIONS),
		'title': '',
		'beskrivelse': '',
		'sist_revidert': date.today().isoformat(),
	})


def _annotate_scenario_display(scenario):
	scenario.konsekvens_css = level_cell_css_class(scenario.konsekvens_nivaa)
	scenario.sannsynlighet_css = level_cell_css_class(scenario.sannsynlighet_nivaa)
	scenario.konsekvens_label = konsekvens_lookup_label(scenario.konsekvens_nivaa)
	scenario.sannsynlighet_label = sannsynlighet_lookup_label(scenario.sannsynlighet_nivaa)
	scenario.risiko_css = risk_cell_css_class(scenario.risiko_etikett)
	scenario.restrisiko_css = risk_cell_css_class(scenario.restrisiko_etikett)
	return scenario


def _build_tiltak_rows(scope, scenarios):
	actions = list(scope.actions.prefetch_related('scenarios').order_by('pk'))
	risk_id_by_pk = annotate_scenario_display_ids(scenarios)
	return build_scope_tiltak_rows(scenarios, actions, risk_id_by_pk)


def risiko_scope_detail(request, pk):
	scope = get_object_or_404(
		RiskScope.objects.select_related('virksomhet').prefetch_related(
			Prefetch(
				'memberships',
				queryset=RiskScopeMember.objects.select_related('user').order_by('role', 'user__first_name', 'user__username'),
			),
		),
		pk=pk,
	)
	if not _is_scope_member(request, scope):
		return _deny_scope_access(request)
	can_edit_scope = True
	can_manage_scope = _is_scope_owner(request, scope)

	scenarios = list(scope.scenarios.prefetch_related('systemer', 'actions').order_by('rekkefolge', 'risk_id'))
	annotate_scenario_display_ids(scenarios)
	annotate_scenarios_tiltak_ids(scenarios, list(scope.actions.order_by('pk')))
	for scenario in scenarios:
		_annotate_scenario_display(scenario)

	edit_scenario_id = None
	raw = request.GET.get('edit', '').strip()
	if raw.isdigit():
		edit_scenario_id = int(raw)

	aksept = _build_akseptkriterier_context()

	owner_memberships = [m for m in scope.memberships.all() if m.role == RISK_SCOPE_MEMBER_ROLE_OWNER]
	participant_memberships = [m for m in scope.memberships.all() if m.role == RISK_SCOPE_MEMBER_ROLE_PARTICIPANT]

	return render(request, 'risiko_scope_detail.html', {
		'request': request,
		'required_permissions': [],
		'scope': scope,
		'scenarios': scenarios,
		'tiltak_rows': _build_tiltak_rows(scope, scenarios),
		'can_edit_scope': can_edit_scope,
		'can_manage_scope': can_manage_scope,
		'owner_memberships': owner_memberships,
		'participant_memberships': participant_memberships,
		'editor_urls': _risiko_editor_urls(pk),
		'edit_scenario_id': edit_scenario_id,
		'matrix_current': _build_matrix_context(scenarios, use_residual=False),
		'matrix_residual': _build_matrix_context(scenarios, use_residual=True),
		'konsekvens_labels': KONSEKVENS_LABELS,
		**aksept,
	})


def risiko_scenario_detail(request, pk, sid):
	# 2026-06-25: Scenario editing is in scope-detail modal – redirect legacy URLs.
	scope = get_object_or_404(RiskScope, pk=pk)
	if not _is_scope_member(request, scope):
		return _deny_scope_access(request)
	get_object_or_404(RiskScenario, pk=sid, scope=scope)
	return redirect(reverse('risiko_scope_detail', kwargs={'pk': pk}) + '?edit=%s' % sid)


def _build_matrix_context(scenarios, use_residual):
	cells = matrix_placements(scenarios, use_residual=use_residual)
	grid = []
	for sannsynlighet in range(5, 0, -1):
		row_cells = []
		for konsekvens in range(1, 6):
			label = risk_label(sannsynlighet, konsekvens)
			row_cells.append({
				'sannsynlighet': sannsynlighet,
				'konsekvens': konsekvens,
				'label': label,
				'css_class': risk_cell_css_class(label),
				'scenarios': cells.get((sannsynlighet, konsekvens), []),
			})
		grid.append({
			'sannsynlighet': sannsynlighet,
			'sannsynlighet_label': SANNSYNLIGHET_LABELS[sannsynlighet],
			'cells': row_cells,
		})
	return grid


def risiko_matrise(request, pk):
	# 2026-06-24: Matrices moved to scope detail page top.
	scope = get_object_or_404(RiskScope, pk=pk)
	if not _is_scope_member(request, scope):
		return _deny_scope_access(request)
	return redirect(reverse('risiko_scope_detail', kwargs={'pk': pk}) + '#risikomatriser')


def _build_akseptkriterier_context():
	konsekvens_rows = []
	for level in range(5, 0, -1):
		konsekvens_rows.append({
			'level': level,
			'label': KONSEKVENS_LABELS[level],
			'level_css': level_cell_css_class(level),
			'dimensjoner': [
				{'navn': navn, 'tekst': tekst}
				for navn, tekst in zip(KONSEKVENS_DIMENSJONER, KONSEKVENS_BESKRIVELSER[level])
			],
		})

	sannsynlighet_rows = []
	for level in range(5, 0, -1):
		sannsynlighet_rows.append({
			'level': level,
			'label': SANNSYNLIGHET_LABELS[level],
			'level_css': level_cell_css_class(level),
			'beskrivelse': SANNSYNLIGHET_BESKRIVELSER[level],
		})

	return {
		'konsekvens_rows': konsekvens_rows,
		'sannsynlighet_rows': sannsynlighet_rows,
	}


def risiko_akseptkriterier(request):
	# 2026-06-25: Reference content moved to scope detail page – redirect legacy URL.
	return redirect('risiko_scope_list')
