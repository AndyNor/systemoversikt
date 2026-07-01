# -*- coding: utf-8 -*-
# Change log:
# 2026-07-01: JSON API for per-virksomhet risk read-access groups – systemforvalter + own virksomhet only.

import json

from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods

from systemoversikt.models import RiskVirksomhetReadGroup, RiskVirksomhetReadGroupMember, Virksomhet
from systemoversikt.risk_membership import user_can_manage_risk_virksomhet_groups, user_display_name


def _json_error(message, status=400):
	return JsonResponse({'ok': False, 'error': message}, status=status)


def _parse_json_body(request):
	try:
		if not request.body:
			return {}
		return json.loads(request.body.decode('utf-8'))
	except (json.JSONDecodeError, UnicodeDecodeError):
		return None


def _require_group_admin_json(request, vid):
	virksomhet = get_object_or_404(Virksomhet, pk=vid)
	if not user_can_manage_risk_virksomhet_groups(request.user, virksomhet):
		return None, None, _json_error('forbidden', status=403)
	return virksomhet, None, None


def _group_to_dict(group):
	return {
		'id': group.pk,
		'title': group.title,
		'beskrivelse': group.beskrivelse,
		'member_count': getattr(group, 'member_count', group.memberships.count()),
	}


def _member_to_dict(membership):
	return {
		'user_id': membership.user_id,
		'name': user_display_name(membership.user),
		'username': membership.user.username,
	}


def _groups_payload(virksomhet):
	groups = (
		RiskVirksomhetReadGroup.objects.filter(virksomhet=virksomhet)
		.annotate(member_count=Count('memberships'))
		.order_by('title')
	)
	return {'groups': [_group_to_dict(g) for g in groups]}


def _group_members_payload(group):
	memberships = list(
		group.memberships.select_related('user').order_by('user__first_name', 'user__username')
	)
	return {
		'group': _group_to_dict(group),
		'members': [_member_to_dict(m) for m in memberships],
	}


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
	virksomhet, _, err = _require_group_admin_json(request, vid)
	if err:
		return err
	return JsonResponse({'ok': True, **_groups_payload(virksomhet)})


@require_http_methods(['POST'])
def api_risiko_read_group_create(request, vid):
	virksomhet, _, err = _require_group_admin_json(request, vid)
	if err:
		return err

	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	title = (data.get('title') or '').strip()
	if not title:
		return _json_error('Tittel er påkrevd.')

	beskrivelse = (data.get('beskrivelse') or '').strip()
	if RiskVirksomhetReadGroup.objects.filter(virksomhet=virksomhet, title=title).exists():
		return _json_error('Det finnes allerede en gruppe med denne tittelen.')

	group = RiskVirksomhetReadGroup.objects.create(
		virksomhet=virksomhet,
		title=title,
		beskrivelse=beskrivelse,
		created_by=request.user,
	)
	group.member_count = 0
	return JsonResponse({'ok': True, 'group': _group_to_dict(group)}, status=201)


@require_http_methods(['PATCH', 'POST'])
@require_http_methods(['PATCH', 'POST'])
def api_risiko_read_group_update(request, vid, gid):
	virksomhet, _, err = _require_group_admin_json(request, vid)
	if err:
		return err

	group = get_object_or_404(RiskVirksomhetReadGroup, pk=gid, virksomhet=virksomhet)
	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	if 'title' in data:
		title = (data.get('title') or '').strip()
		if not title:
			return _json_error('Tittel er påkrevd.')
		if RiskVirksomhetReadGroup.objects.filter(virksomhet=virksomhet, title=title).exclude(pk=group.pk).exists():
			return _json_error('Det finnes allerede en gruppe med denne tittelen.')
		group.title = title

	if 'beskrivelse' in data:
		group.beskrivelse = (data.get('beskrivelse') or '').strip()

	group.save()
	return JsonResponse({'ok': True, 'group': _group_to_dict(group)})


@require_http_methods(['DELETE', 'POST'])
def api_risiko_read_group_delete(request, vid, gid):
	virksomhet, _, err = _require_group_admin_json(request, vid)
	if err:
		return err

	group = get_object_or_404(RiskVirksomhetReadGroup, pk=gid, virksomhet=virksomhet)
	if request.method == 'POST':
		data = _parse_json_body(request) or {}
		if data.get('_method') != 'DELETE':
			return _json_error('invalid_method', status=405)

	group.delete()
	return JsonResponse({'ok': True, **_groups_payload(virksomhet)})


@require_GET
def api_risiko_read_group_members(request, vid, gid):
	virksomhet, _, err = _require_group_admin_json(request, vid)
	if err:
		return err

	group = get_object_or_404(RiskVirksomhetReadGroup, pk=gid, virksomhet=virksomhet)
	return JsonResponse({'ok': True, **_group_members_payload(group)})


@require_http_methods(['POST'])
def api_risiko_read_group_member_add(request, vid, gid):
	virksomhet, _, err = _require_group_admin_json(request, vid)
	if err:
		return err

	group = get_object_or_404(RiskVirksomhetReadGroup, pk=gid, virksomhet=virksomhet)
	data = _parse_json_body(request)
	if data is None:
		return _json_error('invalid_json')

	try:
		user_id = int(data.get('user_id'))
	except (TypeError, ValueError):
		return _json_error('Ugyldig bruker.')

	target_user = get_object_or_404(User, pk=user_id, is_active=True)
	RiskVirksomhetReadGroupMember.objects.get_or_create(
		group=group,
		user=target_user,
		defaults={'added_by': request.user},
	)
	return JsonResponse({'ok': True, **_group_members_payload(group)}, status=201)


@require_http_methods(['DELETE', 'POST'])
def api_risiko_read_group_member_remove(request, vid, gid, user_id):
	virksomhet, _, err = _require_group_admin_json(request, vid)
	if err:
		return err

	group = get_object_or_404(RiskVirksomhetReadGroup, pk=gid, virksomhet=virksomhet)
	if request.method == 'POST':
		data = _parse_json_body(request) or {}
		if data.get('_method') != 'DELETE':
			return _json_error('invalid_method', status=405)

	membership = get_object_or_404(RiskVirksomhetReadGroupMember, group=group, user_id=user_id)
	membership.delete()
	return JsonResponse({'ok': True, **_group_members_payload(group)})


@require_GET
def api_risiko_read_group_brukere_sok(request, vid):
	_, _, err = _require_group_admin_json(request, vid)
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
