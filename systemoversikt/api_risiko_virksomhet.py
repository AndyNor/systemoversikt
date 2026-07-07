# -*- coding: utf-8 -*-
# Change log:
# 2026-07-07: change_riskvirksomhetgroup – virksomhetsadministrator may mutate any group in profile virksomhet.
# 2026-07-07: Granular tilgangsgruppe API – open list, member-gated mutations, creator auto-join, change_riskvirksomhetgroup for virksomhet_read_only.
# 2026-07-06: Removed framework_owner_for / framework_read_for – sammenstilling ownership replaces framework M2M.
# 2026-07-02: API returns display_title (forkortelse/name) and bare title for editing.
# 2026-07-02: Include member names in groups list payload for inline table display.
# 2026-07-02: Rename RiskVirksomhetReadGroup → RiskVirksomhetGroup in API imports and queries.
# 2026-07-01: JSON API for per-virksomhet risk read-access groups – systemforvalter + own virksomhet only.

import json

from django.contrib.auth.models import User
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods

from systemoversikt.models import RiskVirksomhetGroup, RiskVirksomhetGroupMember, Virksomhet
from systemoversikt.risk_membership import (
	normalize_risk_group_title,
	risk_group_title_conflict,
	storage_risk_group_title,
	user_can_access_risk_virksomhet_groups_page,
	user_can_create_risk_virksomhet_group,
	user_can_mutate_risk_virksomhet_group,
	user_can_set_virksomhet_read_only_flag,
	user_display_name,
)


def _json_error(message, status=400):
	return JsonResponse({'ok': False, 'error': message}, status=status)


def _parse_json_body(request):
	try:
		if not request.body:
			return {}
		return json.loads(request.body.decode('utf-8'))
	except (json.JSONDecodeError, UnicodeDecodeError):
		return None


def _require_page_access_json(request, vid):
	virksomhet = get_object_or_404(Virksomhet, pk=vid)
	if not user_can_access_risk_virksomhet_groups_page(request.user, virksomhet):
		return None, _json_error('forbidden', status=403)
	return virksomhet, None


def _require_group_mutation_json(request, virksomhet, gid):
	group = get_object_or_404(RiskVirksomhetGroup, pk=gid, virksomhet=virksomhet)
	if not user_can_mutate_risk_virksomhet_group(request.user, group):
		return None, _json_error('forbidden', status=403)
	return group, None


def _group_mutation_flags(user, group):
	can_mutate = user_can_mutate_risk_virksomhet_group(user, group)
	return {
		'can_edit': can_mutate,
		'can_manage_members': can_mutate,
		'can_delete': can_mutate,
		'can_set_virksomhet_read_only': user_can_set_virksomhet_read_only_flag(
			user,
			group.virksomhet,
		),
	}


def _group_to_dict(group, virksomhet=None, user=None):
	virksomhet = virksomhet or group.virksomhet
	data = {
		'id': group.pk,
		'title': storage_risk_group_title(virksomhet, group.title),
		'display_title': normalize_risk_group_title(virksomhet, group.title),
		'beskrivelse': group.beskrivelse,
		'virksomhet_read_only': group.virksomhet_read_only,
		'member_count': getattr(group, 'member_count', group.memberships.count()),
	}
	if user is not None:
		data.update(_group_mutation_flags(user, group))
	return data


def _member_to_dict(membership):
	return {
		'user_id': membership.user_id,
		'name': user_display_name(membership.user),
		'username': membership.user.username,
	}


def _groups_payload(virksomhet, user):
	member_qs = RiskVirksomhetGroupMember.objects.select_related('user').order_by(
		'user__first_name', 'user__username',
	)
	groups = (
		RiskVirksomhetGroup.objects.filter(virksomhet=virksomhet)
		.annotate(member_count=Count('memberships'))
		.prefetch_related(Prefetch('memberships', queryset=member_qs))
		.order_by('title')
	)
	payload = []
	for group in groups:
		data = _group_to_dict(group, virksomhet=virksomhet, user=user)
		data['members'] = [_member_to_dict(m) for m in group.memberships.all()]
		payload.append(data)
	return {
		'groups': payload,
		'can_create_group': user_can_create_risk_virksomhet_group(user, virksomhet),
		'can_set_virksomhet_read_only': user_can_set_virksomhet_read_only_flag(user, virksomhet),
	}


def _group_members_payload(group, user=None):
	memberships = list(
		group.memberships.select_related('user').order_by('user__first_name', 'user__username')
	)
	payload = {
		'group': _group_to_dict(group, user=user),
		'members': [_member_to_dict(m) for m in memberships],
	}
	if user is not None:
		payload.update(_group_mutation_flags(user, group))
	return payload


def _validate_virksomhet_read_only_change(user, group, new_value):
	if new_value == group.virksomhet_read_only:
		return None
	if not user_can_set_virksomhet_read_only_flag(user, group.virksomhet):
		return _json_error('forbidden', status=403)
	return None


def _bruker_sok_queryset(q):
	terms = q.split()
	if not terms:
		return User.objects.none()
	field_queries = []
	for term in terms:
		field_queries.append(
			Q(username__icontains=term)
			| Q(first_name__icontains=term)
			| Q(last_name__icontains=term)
			| Q(email__icontains=term)
		)
	query = field_queries[0]
	for extra in field_queries[1:]:
		query &= extra
	return (
		User.objects.filter(query)
		.filter(is_active=True)
		.distinct()
		.order_by('first_name', 'last_name', 'username')[:15]
	)


@require_GET
def api_risiko_read_groups_list(request, vid):
	virksomhet, err = _require_page_access_json(request, vid)
	if err:
		return err
	return JsonResponse({
		'ok': True,
		**_groups_payload(virksomhet, request.user),
	})


@require_http_methods(['POST'])
def api_risiko_read_group_create(request, vid):
	virksomhet = get_object_or_404(Virksomhet, pk=vid)
	if not user_can_create_risk_virksomhet_group(request.user, virksomhet):
		return _json_error('forbidden', status=403)

	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	title = storage_risk_group_title(virksomhet, data.get('title') or '')
	if not title:
		return _json_error('Gruppenavn er påkrevd.')

	beskrivelse = (data.get('beskrivelse') or '').strip()
	virksomhet_read_only = bool(data.get('virksomhet_read_only', False))
	if virksomhet_read_only and not user_can_set_virksomhet_read_only_flag(request.user, virksomhet):
		return _json_error('forbidden', status=403)
	if risk_group_title_conflict(virksomhet, title):
		return _json_error('Det finnes allerede en gruppe med dette gruppenavnet.')

	group = RiskVirksomhetGroup.objects.create(
		virksomhet=virksomhet,
		title=title,
		beskrivelse=beskrivelse,
		virksomhet_read_only=virksomhet_read_only,
		created_by=request.user,
	)
	RiskVirksomhetGroupMember.objects.create(
		group=group,
		user=request.user,
		added_by=request.user,
	)
	group.member_count = 1
	return JsonResponse({'ok': True, 'group': _group_to_dict(group, user=request.user)}, status=201)


@require_http_methods(['PATCH', 'POST'])
def api_risiko_read_group_update(request, vid, gid):
	virksomhet, err = _require_page_access_json(request, vid)
	if err:
		return err

	group, err = _require_group_mutation_json(request, virksomhet, gid)
	if err:
		return err

	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	if 'title' in data:
		title = storage_risk_group_title(virksomhet, data.get('title') or '')
		if not title:
			return _json_error('Gruppenavn er påkrevd.')
		if risk_group_title_conflict(virksomhet, title, exclude_pk=group.pk):
			return _json_error('Det finnes allerede en gruppe med dette gruppenavnet.')
		group.title = title

	if 'beskrivelse' in data:
		group.beskrivelse = (data.get('beskrivelse') or '').strip()

	if 'virksomhet_read_only' in data:
		new_read_only = bool(data.get('virksomhet_read_only'))
		err = _validate_virksomhet_read_only_change(request.user, group, new_read_only)
		if err:
			return err
		group.virksomhet_read_only = new_read_only

	group.save()
	return JsonResponse({'ok': True, 'group': _group_to_dict(group, user=request.user)})


@require_http_methods(['DELETE', 'POST'])
def api_risiko_read_group_delete(request, vid, gid):
	virksomhet, err = _require_page_access_json(request, vid)
	if err:
		return err

	group, err = _require_group_mutation_json(request, virksomhet, gid)
	if err:
		return err

	if request.method == 'POST':
		data = _parse_json_body(request) or {}
		if data.get('_method') != 'DELETE':
			return _json_error('invalid_method', status=405)

	group.delete()
	return JsonResponse({'ok': True, **_groups_payload(virksomhet, request.user)})


@require_GET
def api_risiko_read_group_members(request, vid, gid):
	virksomhet, err = _require_page_access_json(request, vid)
	if err:
		return err

	group = get_object_or_404(RiskVirksomhetGroup, pk=gid, virksomhet=virksomhet)
	return JsonResponse({'ok': True, **_group_members_payload(group, user=request.user)})


@require_http_methods(['POST'])
def api_risiko_read_group_member_add(request, vid, gid):
	virksomhet, err = _require_page_access_json(request, vid)
	if err:
		return err

	group, err = _require_group_mutation_json(request, virksomhet, gid)
	if err:
		return err

	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	try:
		user_id = int(data.get('user_id'))
	except (TypeError, ValueError):
		return _json_error('Ugyldig bruker.')

	target_user = get_object_or_404(User, pk=user_id, is_active=True)
	RiskVirksomhetGroupMember.objects.get_or_create(
		group=group,
		user=target_user,
		defaults={'added_by': request.user},
	)
	return JsonResponse({'ok': True, **_group_members_payload(group, user=request.user)}, status=201)


@require_http_methods(['DELETE', 'POST'])
def api_risiko_read_group_member_remove(request, vid, gid, user_id):
	virksomhet, err = _require_page_access_json(request, vid)
	if err:
		return err

	group, err = _require_group_mutation_json(request, virksomhet, gid)
	if err:
		return err

	if request.method == 'POST':
		data = _parse_json_body(request) or {}
		if data.get('_method') != 'DELETE':
			return _json_error('invalid_method', status=405)

	membership = get_object_or_404(RiskVirksomhetGroupMember, group=group, user_id=user_id)
	membership.delete()
	return JsonResponse({'ok': True, **_group_members_payload(group, user=request.user)})


@require_GET
def api_risiko_read_group_brukere_sok(request, vid, gid):
	virksomhet, err = _require_page_access_json(request, vid)
	if err:
		return err

	_, err = _require_group_mutation_json(request, virksomhet, gid)
	if err:
		return err

	q = request.GET.get('q', '').strip()
	if len(q) < 2:
		return JsonResponse({'ok': True, 'results': []})

	results = []
	for user in _bruker_sok_queryset(q):
		results.append({
			'id': user.pk,
			'label': '%s (%s)' % (user_display_name(user), user.username),
		})
	return JsonResponse({'ok': True, 'results': results})
