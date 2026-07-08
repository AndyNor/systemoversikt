# -*- coding: utf-8 -*-
# Change log:
# 2026-07-08: `include_archived=1` shows archived sammenstillinger only on list pages.
# 2026-07-07: reader_groups M2M – view access for group members; map still owner-group only.
# 2026-07-07: Superuser can reassign sammenstilling owner_group from rammeverk list UI.
# 2026-07-06: user_can_edit_template – Django superuser only (mal editor + mal APIs).
# 2026-07-06: Access helpers for group-owned risikosammenstillinger on shared templates.

from django.db.models import Q

from systemoversikt.models import (
	RiskFramework,
	RiskSammenstilling,
	RiskVirksomhetGroup,
	RiskVirksomhetGroupMember,
)
from systemoversikt.risk_membership import user_has_scope_read_access


def user_can_edit_template(user):
	return user.is_authenticated and user.is_superuser


def user_can_change_sammenstilling_owner_group(user):
	return user_can_edit_template(user)


def user_can_change_sammenstilling_reader_groups(user):
	return user_can_change_sammenstilling_owner_group(user)


def all_owner_groups_queryset():
	return RiskVirksomhetGroup.objects.select_related('virksomhet').order_by(
		'virksomhet__virksomhetsforkortelse',
		'title',
	)


def user_can_view_template(user, framework):
	return user.is_authenticated and framework is not None and framework.is_active


def active_templates_queryset():
	return RiskFramework.objects.filter(is_active=True).order_by('title')


def user_is_group_member(user, group):
	if not user.is_authenticated or group is None:
		return False
	return RiskVirksomhetGroupMember.objects.filter(
		user_id=user.id,
		group_id=group.pk,
	).exists()


def user_is_sammenstilling_reader(user, sammenstilling):
	if not user.is_authenticated or sammenstilling is None:
		return False
	return RiskVirksomhetGroupMember.objects.filter(
		user_id=user.id,
		group__reader_sammenstillinger=sammenstilling,
	).exists()


def user_can_create_sammenstilling(user, group):
	return user_is_group_member(user, group)


def user_can_view_sammenstilling(user, sammenstilling):
	if not user.is_authenticated or sammenstilling is None or not sammenstilling.is_active:
		return False
	if user_is_group_member(user, sammenstilling.owner_group):
		return True
	return user_is_sammenstilling_reader(user, sammenstilling)


def user_can_map_sammenstilling(user, sammenstilling):
	if not user.is_authenticated or sammenstilling is None or not sammenstilling.is_active:
		return False
	# 2026-07-08: Archived sammenstillinger are read-only.
	if sammenstilling.archived_at is not None:
		return False
	return user_is_group_member(user, sammenstilling.owner_group)


def sammenstillinger_visible_to_user(user, include_archived=False):
	# 2026-07-08: Archived sammenstillinger are hidden from list pages unless explicitly requested.
	qs = RiskSammenstilling.objects.filter(is_active=True).select_related(
		'framework',
		'owner_group',
		'owner_group__virksomhet',
	)
	# 2026-07-08: `include_archived=1` should show archived sammenstillinger only (not active + archived).
	if include_archived:
		qs = qs.filter(archived_at__isnull=False)
	else:
		qs = qs.filter(archived_at__isnull=True)
	if not user.is_authenticated:
		return qs.none()
	if user.is_superuser:
		return qs
	return qs.filter(
		Q(owner_group__memberships__user_id=user.id)
		| Q(reader_groups__memberships__user_id=user.id),
	).distinct()


def groups_user_can_own_sammenstilling(user):
	if not user.is_authenticated:
		return RiskVirksomhetGroup.objects.none()
	return RiskVirksomhetGroup.objects.filter(
		memberships__user_id=user.id,
	).select_related('virksomhet').order_by(
		'virksomhet__virksomhetsforkortelse',
		'title',
	).distinct()


def user_can_map_scenario(user, scenario):
	if scenario is None or scenario.scope_id is None:
		return False
	return user_has_scope_read_access(user, scenario.scope)


def get_active_sammenstilling(pk):
	return RiskSammenstilling.objects.filter(
		pk=pk,
		is_active=True,
	).select_related('framework', 'owner_group', 'owner_group__virksomhet').first()


def sammenstilling_for_access_message(pk):
	return RiskSammenstilling.objects.filter(pk=pk).select_related(
		'framework',
		'owner_group',
		'owner_group__virksomhet',
	).first()
