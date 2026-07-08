# -*- coding: utf-8 -*-
# Change log:
# 2026-07-08: Import success message shows detected Excel template (enkel/stor mal).
# 2026-07-08: Server-side scope search (q=) across all virksomheter on root list.
# 2026-07-07: change_riskvirksomhetgroup – virksomhetsadministrator scoped to profile virksomhet on tilgangsgrupper page.
# 2026-07-07: view_riskscope gates collection create/import; tilgangsgrupper page uses granular membership helpers.
# 2026-07-07: Editor context sannsynlighet_keys from editable sannsynlighetstyper; import redirects to rediger.
# 2026-07-07: Membership prefetch includes profile virksomhet for member display names.
# 2026-07-07: Report available for all statuses; godkjent-only gate removed from detail link and rapport view.
# 2026-07-07: risiko_scope_rapport + omfang file serve views for godkjent archive report.
# 2026-07-06: _render_risk_access_denied – sammenstilling context for group-owned access denied pages.
# 2026-07-06: _render_risk_access_denied – framework context for rammeverk access denied pages.
# 2026-07-06: risiko_scope_list – login_required; list is no longer open to anonymous users.
# 2026-07-02: virksomhet_tilgangsgrupper in list context for collection table filters.
# 2026-07-02: Rename RiskVirksomhetReadGroup → RiskVirksomhetGroup in imports and prefetch.
# 2026-07-02: Group participants count as members; participant_groups in scope detail context.
# 2026-07-01: Risk list context – nav virksomheter sorted by virksomhetsforkortelse.
# 2026-07-01: Custom risiko_access_denied page – explains owner/participant/read-group access.
# 2026-07-01: Dropped legacy /sikkerhet/risiko/<pk>/ redirect routes.
# 2026-07-01: Virksomhet viewpoints, collection URL prefix, read-group access on detail/list.
# 2026-07-01: Godkjent status locks collection read-only; owner may change status to unlock.
# 2026-07-01: Editor URL for virksomhet-scoped tiltak ansvarlig user search.
# 2026-06-30: List page – status column and lock icon for collections without access.
# 2026-06-30: Akseptkriterier JSON export/import – superuser page buttons for dev → prod.
# 2026-06-30: Global akseptkriterier – read-only page and superuser editor.
# 2026-06-30: risiko_scope_delete – owner-only POST delete from list page.
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

from datetime import date, datetime
import json
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_GET, require_http_methods
from openpyxl import load_workbook

from systemoversikt.models import (
	RISK_SCOPE_MEMBER_ROLE_OWNER,
	RISK_SCOPE_MEMBER_ROLE_PARTICIPANT,
	RiskCriteriaConfig,
	RiskScope,
	RiskScopeMember,
	RiskScopeOmfangFil,
	RiskVirksomhetGroup,
	RiskScenario,
	Virksomhet,
)
from systemoversikt.risk_criteria import (
	criteria_from_post,
	get_active_criteria,
	get_or_create_active_config,
	invalidate_criteria_cache,
	level_cell_css_class,
	risk_cell_css_class,
	validate_criteria,
	validate_slug_changes,
)
from systemoversikt.risk_display import (
	annotate_scenario_display_ids,
	annotate_scenarios_tiltak_ids,
	build_scope_tiltak_rows,
	tiltak_display_id_map,
)
from systemoversikt.risk_report import (
	besluttede_tiltak,
	build_scenario_report_sections,
	collect_scope_systems,
)
from systemoversikt.risk_criteria_transfer import (
	apply_imported_criteria,
	build_export_payload,
	parse_import_payload,
)
from systemoversikt.risk_import import import_risk_workbook
from systemoversikt.risk_membership import (
	create_risk_scope,
	nav_ordinary_virksomheter,
	profile_virksomhet,
	RISK_CREATE_PERMISSION,
	scopes_for_user_membership,
	scopes_for_virksomhet,
	search_scopes,
	search_scopes_for_virksomhet,
	user_can_access_risk_virksomhet_groups_page,
	user_can_create_risk_virksomhet_group,
	user_can_set_virksomhet_read_only_flag,
	user_member_display_name,
	user_has_scope_read_access,
	user_has_scope_write_access,
	user_is_scope_member,
)
from systemoversikt.views import formater_permissions

# Create/import gated by view_riskscope only; collection detail restricted to scope members.
RISK_CREATE_PERMISSIONS = [RISK_CREATE_PERMISSION]

RISK_SCOPE_SEARCH_MAX_LEN = 200


def _risiko_scope_search_query(request):
	return (request.GET.get('q') or '').strip()[:RISK_SCOPE_SEARCH_MAX_LEN]


def _filter_scopes_archived(qs, include_archived):
	if include_archived:
		return qs.filter(archived_at__isnull=False)
	return qs.filter(archived_at__isnull=True)


def _risiko_scope_archived_toggle_query(include_archived, search_query=''):
	parts = []
	if include_archived:
		parts.append('include_archived=0')
	else:
		parts.append('include_archived=1')
	if search_query:
		parts.append('q=%s' % quote(search_query))
	return '?' + '&'.join(parts)


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
	return user_is_scope_member(request.user, scope)


def _has_scope_read_access(request, scope):
	if not request.user.is_authenticated:
		return False
	return user_has_scope_read_access(request.user, scope)


def _get_readable_scope(request, scope_id):
	scope = get_object_or_404(
		RiskScope.objects.select_related('virksomhet').prefetch_related(
			Prefetch(
				'memberships',
				queryset=RiskScopeMember.objects.select_related(
					'user',
					'user__profile',
					'user__profile__virksomhet',
				).order_by('role', 'user__first_name', 'user__username'),
			),
		),
		pk=scope_id,
	)
	if not _has_scope_read_access(request, scope):
		raise Http404
	return scope


def _get_member_scope(request, scope_id):
	scope = _get_readable_scope(request, scope_id)
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
	scope = _get_readable_scope(request, scope_id)
	scenario = get_object_or_404(RiskScenario, pk=scenario_id, scope=scope)
	return scope, scenario


def _get_writable_scenario(request, scope_id, scenario_id):
	scope = _get_member_scope(request, scope_id)
	scenario = get_object_or_404(RiskScenario, pk=scenario_id, scope=scope)
	return scope, scenario


_get_owned_scenario = _get_member_scenario


def _scope_owner_names(scope):
	if scope is None:
		return []
	names = []
	for m in scope.memberships.all():
		if m.role == RISK_SCOPE_MEMBER_ROLE_OWNER:
			names.append(user_member_display_name(m.user))
	return names


def _scope_for_access_message(pk):
	return (
		RiskScope.objects.select_related('virksomhet')
		.prefetch_related(
			Prefetch(
				'memberships',
				queryset=RiskScopeMember.objects.filter(
					role=RISK_SCOPE_MEMBER_ROLE_OWNER,
				).select_related('user', 'user__profile', 'user__profile__virksomhet'),
			),
		)
		.filter(pk=pk)
		.first()
	)


def _render_risk_access_denied(request, reason, scope=None, virksomhet=None, framework=None, sammenstilling=None):
	# 2026-07-06: sammenstilling context for group-owned risikosammenstilling access denied pages.
	# 2026-07-01: Risk-specific 403 – module uses owner/participant/read-group, not Django model perms.
	return render(request, 'risiko_access_denied.html', {
		'request': request,
		'required_permissions': [],
		'risk_access_reason': reason,
		'scope': scope,
		'virksomhet': virksomhet or (scope.virksomhet if scope else None),
		'framework': framework or (sammenstilling.framework if sammenstilling else None),
		'sammenstilling': sammenstilling,
		'owner_names': _scope_owner_names(scope),
	}, status=403)


def _deny_scope_access(request, scope=None, reason='collection_read'):
	return _render_risk_access_denied(request, reason, scope=scope)


def _check_permissions(request, required_permissions):
	if not any(map(request.user.has_perm, required_permissions)):
		return _render_risk_access_denied(request, 'create_collection')
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
		'participantGroupAdd': reverse('api_risiko_participant_group_add', kwargs={'pk': pk}),
		'participantGroupRemove': reverse('api_risiko_participant_group_remove', kwargs={'pk': pk, 'gid': 0}).replace('/0/', '/{groupId}/'),
		'participantGroupSearch': reverse('api_risiko_participant_groups_sok', kwargs={'pk': pk}),
		'scopeVirksomhet': reverse('api_risiko_scope_virksomhet', kwargs={'pk': pk}),
		'brukerSearch': reverse('api_risiko_brukere_sok', kwargs={'pk': pk}),
		'tiltakAnsvarligSearch': reverse('api_risiko_tiltak_ansvarlig_sok', kwargs={'pk': pk}),
		'virksomhetSearch': reverse('api_risiko_virksomheter_sok', kwargs={'pk': pk}),
		'omfangFigur': reverse('api_risiko_omfang_figur', kwargs={'pk': pk}),
		'omfangFigurOriginal': reverse('api_risiko_omfang_figur_original', kwargs={'pk': pk}),
		'omfangFigurFile': reverse('risiko_scope_fil_omfang', kwargs={'pk': pk}),
		'omfangOriginalFile': reverse('risiko_scope_fil_omfang_original', kwargs={'pk': pk}),
		'scopePage': reverse('risiko_scope_detail', kwargs={'pk': pk}),
		'scopeReport': reverse('risiko_scope_rapport', kwargs={'pk': pk}),
	}


def _risiko_list_context(request, scopes, list_virksomhet=None):
	can_write = request.user.has_perm(RISK_CREATE_PERMISSION)
	profile_v = profile_virksomhet(request.user)
	ctx = {
		'request': request,
		'required_permissions': [],
		'scopes': scopes,
		'can_import': can_write,
		'can_create': can_write,
		'profile_virksomhet': profile_v,
		'list_virksomhet': list_virksomhet,
		'can_access_tilgangsgrupper': (
			list_virksomhet is not None
			and user_can_access_risk_virksomhet_groups_page(request.user, list_virksomhet)
		),
	}
	ctx['nav_virksomheter'] = nav_ordinary_virksomheter()
	if list_virksomhet is not None:
		ctx['virksomhet_tilgangsgrupper'] = list(
			RiskVirksomhetGroup.objects.filter(virksomhet=list_virksomhet)
			.select_related('virksomhet')
			.order_by('title')
		)
	else:
		ctx['virksomhet_tilgangsgrupper'] = []
	return ctx


@login_required
def risiko_scope_list(request):
	# 2026-07-01: Root list – profile virksomhet collections plus cross-virksomhet memberships.
	include_archived = request.GET.get('include_archived') == '1'
	search_query = _risiko_scope_search_query(request)
	profile_v = profile_virksomhet(request.user)
	archived_toggle_query = _risiko_scope_archived_toggle_query(include_archived, search_query)
	search_reset_url = reverse('risiko_scope_list')
	if include_archived:
		search_reset_url += '?include_archived=1'

	if search_query:
		# 2026-07-08: Server search across all virksomheter – existence is open, read flags per row.
		search_results = _filter_scopes_archived(
			search_scopes(request.user, search_query),
			include_archived,
		)
		return render(request, 'risiko_scope_list.html', {
			**_risiko_list_context(request, search_results, list_virksomhet=profile_v),
			'search_query': search_query,
			'search_results': search_results,
			'search_scope_hint': 'Søker i tittel og beskrivelse på tvers av alle virksomheter.',
			'search_reset_url': search_reset_url,
			'virksomhet_scopes': [],
			'my_scopes': [],
			'is_root_list': True,
			'include_archived': include_archived,
			'archived_toggle_query': archived_toggle_query,
		})

	virksomhet_scopes = scopes_for_virksomhet(
		request.user,
		profile_v.pk if profile_v else None,
	)
	my_scopes = scopes_for_user_membership(
		request.user,
		exclude_virksomhet_id=profile_v.pk if profile_v else None,
	)
	# 2026-07-08: `include_archived=1` should show archived scopes only (not active + archived).
	virksomhet_scopes = _filter_scopes_archived(virksomhet_scopes, include_archived)
	my_scopes = _filter_scopes_archived(my_scopes, include_archived)
	return render(request, 'risiko_scope_list.html', {
		**_risiko_list_context(request, virksomhet_scopes, list_virksomhet=profile_v),
		'search_query': '',
		'search_results': None,
		'search_scope_hint': 'Søker i tittel og beskrivelse på tvers av alle virksomheter.',
		'search_reset_url': search_reset_url,
		'virksomhet_scopes': virksomhet_scopes,
		'my_scopes': my_scopes,
		'is_root_list': True,
		'include_archived': include_archived,
		'archived_toggle_query': archived_toggle_query,
	})


def risiko_virksomhet_list(request, vid):
	include_archived = request.GET.get('include_archived') == '1'
	search_query = _risiko_scope_search_query(request)
	virksomhet = get_object_or_404(Virksomhet, pk=vid)
	archived_toggle_query = _risiko_scope_archived_toggle_query(include_archived, search_query)
	search_reset_url = reverse('risiko_virksomhet_list', kwargs={'vid': vid})
	if include_archived:
		search_reset_url += '?include_archived=1'

	if search_query:
		scopes = _filter_scopes_archived(
			search_scopes_for_virksomhet(request.user, virksomhet.pk, search_query),
			include_archived,
		)
	else:
		scopes = scopes_for_virksomhet(request.user, virksomhet.pk)
		scopes = _filter_scopes_archived(scopes, include_archived)

	return render(request, 'risiko_virksomhet_list.html', {
		**_risiko_list_context(request, scopes, list_virksomhet=virksomhet),
		'virksomhet': virksomhet,
		'search_query': search_query,
		'search_results': scopes if search_query else None,
		'search_scope_hint': 'Søker i tittel og beskrivelse for denne virksomheten.',
		'search_reset_url': search_reset_url,
		'include_archived': include_archived,
		'archived_toggle_query': archived_toggle_query,
	})


def risiko_virksomhet_tilgangsgrupper(request, vid):
	virksomhet = get_object_or_404(Virksomhet, pk=vid)
	if not user_can_access_risk_virksomhet_groups_page(request.user, virksomhet):
		return _render_risk_access_denied(request, 'read_groups_manage', virksomhet=virksomhet)
	api_urls = {
		'groups': reverse('api_risiko_read_groups_list', kwargs={'vid': vid}),
		'groupCreate': reverse('api_risiko_read_group_create', kwargs={'vid': vid}),
		'groupDetail': reverse('api_risiko_read_group_update', kwargs={'vid': vid, 'gid': 0}).replace('/0/', '/{id}/'),
		'groupDelete': reverse('api_risiko_read_group_delete', kwargs={'vid': vid, 'gid': 0}).replace('/0/', '/{id}/'),
		'members': reverse('api_risiko_read_group_members', kwargs={'vid': vid, 'gid': 0}).replace('/groups/0/', '/groups/{id}/'),
		'memberAdd': reverse('api_risiko_read_group_member_add', kwargs={'vid': vid, 'gid': 0}).replace('/groups/0/', '/groups/{id}/'),
		'memberRemove': reverse('api_risiko_read_group_member_remove', kwargs={'vid': vid, 'gid': 0, 'user_id': 0}).replace('/groups/0/', '/groups/{groupId}/').replace('/members/0/', '/members/{userId}/'),
		'brukerSearch': reverse('api_risiko_read_group_brukere_sok', kwargs={'vid': vid, 'gid': 0}).replace('/groups/0/', '/groups/{id}/'),
	}
	return render(request, 'risiko_virksomhet_tilgangsgrupper.html', {
		'request': request,
		'required_permissions': [],
		'virksomhet': virksomhet,
		'can_create_group': user_can_create_risk_virksomhet_group(request.user, virksomhet),
		'can_set_virksomhet_read_only': user_can_set_virksomhet_read_only_flag(request.user, virksomhet),
		'api_urls_json': json.dumps(api_urls),
	})


@require_http_methods(['POST'])
def risiko_scope_delete(request, pk):
	# 2026-06-30: Only scope owners may delete a risikosamling.
	try:
		scope = _get_managed_scope(request, pk)
	except Http404:
		scope = _scope_for_access_message(pk)
		if scope and user_has_scope_read_access(request.user, scope):
			return _render_risk_access_denied(request, 'collection_owner', scope=scope)
		return _deny_scope_access(request, scope=scope)
	if scope.archived_at is not None:
		messages.info(request, 'Risikosamlingen «%s» er allerede arkivert.' % scope.title)
		return redirect('risiko_scope_list')
	title = scope.title
	scope.archive()
	messages.success(request, 'Risikosamling «%s» er arkivert.' % title)
	return redirect('risiko_scope_list')


def risiko_import(request):
	denied = _check_permissions(request, RISK_CREATE_PERMISSIONS)
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
				fmt_label = 'stor mal' if result.format == 'large' else 'enkel mal'
				messages.success(
					request,
					'Importert (%s) %d scenarioer og %d tiltak.' % (
						fmt_label, result.scenario_count, result.action_count,
					),
				)
				return redirect('risiko_scope_detail', pk=result.scope.pk)
			except Exception as exc:
				messages.error(request, 'Import feilet: %s' % exc)

	return render(request, 'risiko_import.html', {
		'request': request,
		'required_permissions': formater_permissions(RISK_CREATE_PERMISSIONS),
	})


def risiko_scope_create(request):
	# 2026-06-25: Manual collection create – same audience as Excel import.
	denied = _check_permissions(request, RISK_CREATE_PERMISSIONS)
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
						'required_permissions': formater_permissions(RISK_CREATE_PERMISSIONS),
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
		'required_permissions': formater_permissions(RISK_CREATE_PERMISSIONS),
		'title': '',
		'beskrivelse': '',
		'sist_revidert': date.today().isoformat(),
	})


def _annotate_scenario_display(scenario, criteria):
	scenario.konsekvens_css = level_cell_css_class(scenario.konsekvens_nivaa)
	scenario.sannsynlighet_css = level_cell_css_class(scenario.sannsynlighet_nivaa)
	scenario.konsekvens_label = criteria.konsekvens_lookup_label(scenario.konsekvens_nivaa)
	scenario.sannsynlighet_label = criteria.sannsynlighet_lookup_label(scenario.sannsynlighet_nivaa)
	scenario.risiko_css = risk_cell_css_class(scenario.risiko_etikett)
	scenario.restrisiko_css = risk_cell_css_class(scenario.restrisiko_etikett)
	return scenario


def _build_tiltak_rows(scope, scenarios):
	actions = list(scope.actions.prefetch_related('scenarios').order_by('pk'))
	risk_id_by_pk = annotate_scenario_display_ids(scenarios)
	return build_scope_tiltak_rows(scenarios, actions, risk_id_by_pk)


def _scope_omfang_fil(scope):
	try:
		return scope.omfang_fil
	except RiskScopeOmfangFil.DoesNotExist:
		return None


def _besluttede_rapport_tiltak_rows(scenarios, actions):
	from systemoversikt.risk_report import BESLUTTET_TILTAK_STATUSES, besluttede_tiltak

	risk_id_by_pk = annotate_scenario_display_ids(scenarios)
	tiltak_map = tiltak_display_id_map(actions)
	ordered = besluttede_tiltak(actions, tiltak_map)
	order_index = {action.pk: index for index, action in enumerate(ordered)}
	all_rows = build_scope_tiltak_rows(scenarios, actions, risk_id_by_pk)
	rows = [row for row in all_rows if row['action'].status in BESLUTTET_TILTAK_STATUSES]
	rows.sort(key=lambda row: order_index.get(row['action'].pk, 9999))
	return rows


def _build_rapport_context(scope, criteria):
	scenarios = list(scope.scenarios.prefetch_related('systemer', 'actions').order_by('rekkefolge', 'risk_id'))
	annotate_scenario_display_ids(scenarios)
	actions = list(scope.actions.prefetch_related('scenarios').order_by('pk'))
	annotate_scenarios_tiltak_ids(scenarios, actions)
	for scenario in scenarios:
		_annotate_scenario_display(scenario, criteria)

	owner_memberships = [m for m in scope.memberships.all() if m.role == RISK_SCOPE_MEMBER_ROLE_OWNER]
	participant_memberships = [m for m in scope.memberships.all() if m.role == RISK_SCOPE_MEMBER_ROLE_PARTICIPANT]
	participant_groups = list(scope.participant_groups.all())
	tiltak_map = tiltak_display_id_map(actions)

	return {
		'scope': scope,
		'omfang_fil': _scope_omfang_fil(scope),
		'scenarios': scenarios,
		'scenario_sections': build_scenario_report_sections(scenarios, tiltak_map),
		'scope_systems': collect_scope_systems(scenarios),
		'besluttede_tiltak_rows': _besluttede_rapport_tiltak_rows(scenarios, actions),
		'matrix_current': criteria.build_matrix_context(scenarios, use_residual=False),
		'matrix_residual': criteria.build_matrix_context(scenarios, use_residual=True),
		'konsekvens_labels': criteria.konsekvens_labels,
		'owner_memberships': owner_memberships,
		'participant_memberships': participant_memberships,
		'participant_groups': participant_groups,
		'generated_at': datetime.now(),
		'report_mode': True,
	}


def risiko_scope_detail(request, pk):
	scope = get_object_or_404(
		RiskScope.objects.select_related('virksomhet').prefetch_related(
			Prefetch(
				'memberships',
				queryset=RiskScopeMember.objects.select_related(
					'user',
					'user__profile',
					'user__profile__virksomhet',
				).order_by('role', 'user__first_name', 'user__username'),
			),
			Prefetch(
				'participant_groups',
				queryset=RiskVirksomhetGroup.objects.select_related('virksomhet').order_by('title'),
			),
		),
		pk=pk,
	)
	if not _has_scope_read_access(request, scope):
		return _deny_scope_access(request, scope=scope)
	# 2026-07-01: Godkjent status locks content; read-group viewers never get write access.
	scope_is_locked = scope.is_content_locked()
	is_owner = _is_scope_owner(request, scope)
	is_member = _is_scope_member(request, scope)
	can_write = user_has_scope_write_access(request.user, scope)
	can_edit_scope = can_write and not scope_is_locked
	can_manage_scope = is_owner and not scope_is_locked
	can_change_locked_status = is_owner and scope_is_locked and scope.archived_at is None
	is_read_only_viewer = not is_member and _has_scope_read_access(request, scope)
	criteria = get_active_criteria()

	scenarios = list(scope.scenarios.prefetch_related('systemer', 'actions').order_by('rekkefolge', 'risk_id'))
	annotate_scenario_display_ids(scenarios)
	annotate_scenarios_tiltak_ids(scenarios, list(scope.actions.order_by('pk')))
	for scenario in scenarios:
		_annotate_scenario_display(scenario, criteria)

	edit_scenario_id = None
	raw = request.GET.get('edit', '').strip()
	if raw.isdigit():
		edit_scenario_id = int(raw)

	aksept = criteria.build_akseptkriterier_context()

	owner_memberships = [m for m in scope.memberships.all() if m.role == RISK_SCOPE_MEMBER_ROLE_OWNER]
	participant_memberships = [m for m in scope.memberships.all() if m.role == RISK_SCOPE_MEMBER_ROLE_PARTICIPANT]
	participant_groups = list(scope.participant_groups.all())
	omfang_fil = _scope_omfang_fil(scope)

	return render(request, 'risiko_scope_detail.html', {
		'request': request,
		'required_permissions': [],
		'scope': scope,
		'omfang_fil': omfang_fil,
		'scenarios': scenarios,
		'tiltak_rows': _build_tiltak_rows(scope, scenarios),
		'can_edit_scope': can_edit_scope,
		'can_manage_scope': can_manage_scope,
		'can_change_locked_status': can_change_locked_status,
		'is_read_only_viewer': is_read_only_viewer,
		'owner_memberships': owner_memberships,
		'participant_memberships': participant_memberships,
		'participant_groups': participant_groups,
		'editor_urls': _risiko_editor_urls(pk),
		'edit_scenario_id': edit_scenario_id,
		'matrix_current': criteria.build_matrix_context(scenarios, use_residual=False),
		'matrix_residual': criteria.build_matrix_context(scenarios, use_residual=True),
		'konsekvens_labels': criteria.konsekvens_labels,
		**aksept,
	})


def risiko_scenario_detail(request, pk, sid):
	# 2026-06-25: Scenario editing is in scope-detail modal – redirect legacy URLs.
	scope = get_object_or_404(RiskScope, pk=pk)
	if not _has_scope_read_access(request, scope):
		return _deny_scope_access(request, scope=scope)
	get_object_or_404(RiskScenario, pk=sid, scope=scope)
	return redirect(reverse('risiko_scope_detail', kwargs={'pk': pk}) + '?edit=%s' % sid)


def risiko_akseptkriterier(request):
	# 2026-06-30: Global read-only akseptkriterier – shared by all risikosamlinger.
	criteria = get_active_criteria()
	aksept = criteria.build_akseptkriterier_context()
	return render(request, 'risiko_akseptkriterier.html', {
		'request': request,
		'required_permissions': [],
		'konsekvens_labels': criteria.konsekvens_labels,
		'matrix_rows': criteria.build_matrix_reference_context(),
		'can_edit_criteria': request.user.is_authenticated and request.user.is_superuser,
		**aksept,
	})


def _criteria_editor_context(criteria, form_data=None):
	edit_data = form_data if form_data is not None else criteria.to_storage_dict()
	# 2026-07-07: Sannsynlighetskategori-kolonner følger redigerbare sannsynlighetstype-slugs.
	sannsynlighet_keys = [
		(item['slug'], item['label'])
		for item in edit_data.get('sannsynlighetstyper') or criteria.sannsynlighetstyper
	]
	return {
		'criteria': criteria,
		'edit_data': edit_data,
		'risk_levels': ('Lav', 'Middels', 'Høy'),
		'levels_desc': list(range(5, 0, -1)),
		'sannsynlighet_keys': sannsynlighet_keys,
	}


def _require_superuser_criteria(request):
	if not request.user.is_authenticated or not request.user.is_superuser:
		raise PermissionDenied


@require_http_methods(['GET'])
def risiko_akseptkriterier_eksporter(request):
	# 2026-06-30: Superuser JSON download for moving criteria between environments.
	_require_superuser_criteria(request)
	criteria = get_active_criteria()
	row = RiskCriteriaConfig.objects.filter(is_active=True).first()
	title = row.title if row else 'Standard akseptkriterier'
	payload = build_export_payload(criteria, request.user, title=title)
	filename = 'akseptkriterier-%s.json' % date.today().isoformat()
	response = HttpResponse(
		json.dumps(payload, ensure_ascii=False, indent=2),
		content_type='application/json; charset=utf-8',
	)
	response['Content-Disposition'] = 'attachment; filename="%s"' % filename
	return response


@require_http_methods(['POST'])
def risiko_akseptkriterier_importer(request):
	# 2026-07-07: Redirect to editor page after import (export/import UI lives there).
	# 2026-06-30: Superuser JSON upload – replaces active akseptkriterier after validation.
	_require_superuser_criteria(request)
	if not request.POST.get('confirm_import'):
		messages.error(request, 'Bekreft at du vil erstatte aktive akseptkriterier.')
		return redirect('risiko_akseptkriterier_rediger')

	upload = request.FILES.get('kriteriefil')
	if not upload:
		messages.error(request, 'Velg en JSON-fil å laste opp.')
		return redirect('risiko_akseptkriterier_rediger')

	try:
		raw_text = upload.read().decode('utf-8')
		raw_dict = json.loads(raw_text)
	except (UnicodeDecodeError, json.JSONDecodeError) as exc:
		messages.error(request, 'Ugyldig JSON-fil: %s' % exc)
		return redirect('risiko_akseptkriterier_rediger')

	try:
		title, criteria_dict = parse_import_payload(raw_dict)
	except ValueError as exc:
		messages.error(request, str(exc))
		return redirect('risiko_akseptkriterier_rediger')

	errors = apply_imported_criteria(criteria_dict, request.user, title=title)
	if errors:
		for err in errors:
			messages.error(request, err)
		return redirect('risiko_akseptkriterier_rediger')

	messages.success(request, 'Akseptkriterier er importert. Endringene gjelder alle risikosamlinger.')
	return redirect('risiko_akseptkriterier_rediger')


@require_http_methods(['GET', 'POST'])
def risiko_akseptkriterier_rediger(request):
	# 2026-06-30: Superuser-only editor for global akseptkriterier.
	_require_superuser_criteria(request)

	get_or_create_active_config(request.user)
	criteria = get_active_criteria()

	if request.method == 'POST':
		new_data = criteria_from_post(request.POST)
		errors = validate_criteria(new_data)
		errors.extend(validate_slug_changes(criteria, new_data))
		if errors:
			for err in errors:
				messages.error(request, err)
			ctx = _criteria_editor_context(criteria, form_data=new_data)
			ctx['request'] = request
			ctx['required_permissions'] = []
			return render(request, 'risiko_akseptkriterier_rediger.html', ctx)

		row = RiskCriteriaConfig.objects.filter(is_active=True).first()
		if row is None:
			row = RiskCriteriaConfig(title='Standard akseptkriterier', is_active=True)
		row.criteria = new_data
		row.oppdatert_av = request.user
		row.is_active = True
		row.save()
		invalidate_criteria_cache()
		messages.success(request, 'Akseptkriterier er oppdatert. Endringene gjelder alle risikosamlinger.')
		return redirect('risiko_akseptkriterier')

	return render(request, 'risiko_akseptkriterier_rediger.html', {
		'request': request,
		'required_permissions': [],
		**_criteria_editor_context(criteria),
	})


def risiko_matrise(request, pk):
	# 2026-06-24: Matrices moved to scope detail page top.
	scope = get_object_or_404(RiskScope, pk=pk)
	if not _has_scope_read_access(request, scope):
		return _deny_scope_access(request, scope=scope)
	return redirect(reverse('risiko_scope_detail', kwargs={'pk': pk}) + '#risikomatriser')


def _serve_scope_omfang_file(request, pk, kind):
	scope = _get_readable_scope(request, pk)
	omfang_fil = _scope_omfang_fil(scope)
	if omfang_fil is None:
		raise Http404

	if kind == 'figur':
		if not omfang_fil.has_figur():
			raise Http404
		content = bytes(omfang_fil.figur_data)
		content_type = omfang_fil.figur_content_type or 'application/octet-stream'
		disposition = 'inline'
		filename = omfang_fil.figur_filnavn or 'omfang-figur'
	else:
		if not omfang_fil.has_original():
			raise Http404
		content = bytes(omfang_fil.original_data)
		content_type = omfang_fil.original_content_type or 'application/octet-stream'
		disposition = 'attachment'
		filename = omfang_fil.original_filnavn or 'omfang-original'

	response = HttpResponse(content, content_type=content_type)
	response['Content-Disposition'] = content_disposition_header(disposition, filename)
	return response


@require_GET
def risiko_scope_fil_omfang(request, pk):
	# 2026-07-07: Authenticated inline serve of scope figure bytes from DB.
	return _serve_scope_omfang_file(request, pk, 'figur')


@require_GET
def risiko_scope_fil_omfang_original(request, pk):
	# 2026-07-07: Authenticated download of scope figure source file from DB.
	return _serve_scope_omfang_file(request, pk, 'original')


@require_GET
def risiko_scope_rapport(request, pk):
	# 2026-07-07: Print-friendly HTML report; available for all statuses (draft banner when not godkjent).
	scope = get_object_or_404(
		RiskScope.objects.select_related('virksomhet').prefetch_related(
			Prefetch(
				'memberships',
				queryset=RiskScopeMember.objects.select_related(
					'user',
					'user__profile',
					'user__profile__virksomhet',
				).order_by('role', 'user__first_name', 'user__username'),
			),
			Prefetch(
				'participant_groups',
				queryset=RiskVirksomhetGroup.objects.select_related('virksomhet').order_by('title'),
			),
		),
		pk=pk,
	)
	if not _has_scope_read_access(request, scope):
		return _deny_scope_access(request, scope=scope)

	criteria = get_active_criteria()
	return render(request, 'risiko_scope_rapport.html', {
		'request': request,
		'required_permissions': [],
		**_build_rapport_context(scope, criteria),
	})

