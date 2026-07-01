# -*- coding: utf-8 -*-
# Change log:
# 2026-07-01: Superuser cross-virksomhet read-group admin – temporary for testing; remove later.
# 2026-07-01: Virksomhet-scoped list helpers and read-group access checks for risk MVP.
# 2026-06-30: create_risk_scope – explicit forsteutkast status on new collections.
# 2026-06-30: create_risk_scope – creator as first owner with virksomhet from profile.

from django.db import transaction
from django.db.models import BooleanField, Case, Count, Exists, OuterRef, Prefetch, Q, Value, When

from systemoversikt.models import (
	RISK_SCOPE_MEMBER_ROLE_OWNER,
	RiskScope,
	RiskScopeMember,
	RiskVirksomhetReadGroupMember,
	Virksomhet,
)

RISK_VIRKSOMHET_GROUP_ADMIN_AD_GROUP = '/DS-SYSTEMOVERSIKT_FORVALTER_SYSTEMFORVALTER'


def creator_virksomhet(user):
	try:
		profile = user.profile
		return profile.virksomhet_innlogget_som or profile.virksomhet
	except Exception:
		return None


def profile_virksomhet(user):
	if not user.is_authenticated:
		return None
	try:
		return user.profile.virksomhet
	except Exception:
		return None


def user_display_name(user):
	if user is None:
		return ''
	full = user.get_full_name()
	return full.strip() if full else user.username


def user_is_scope_member(user, scope):
	if not user.is_authenticated:
		return False
	return scope.memberships.filter(user_id=user.id).exists()


def user_has_virksomhet_read_group_access(user, virksomhet_id):
	if not user.is_authenticated or virksomhet_id is None:
		return False
	return RiskVirksomhetReadGroupMember.objects.filter(
		user_id=user.id,
		group__virksomhet_id=virksomhet_id,
	).exists()


def user_has_scope_read_access(user, scope):
	if user_is_scope_member(user, scope):
		return True
	if scope.virksomhet_id is None:
		return False
	return user_has_virksomhet_read_group_access(user, scope.virksomhet_id)


def user_has_scope_write_access(user, scope):
	return user_is_scope_member(user, scope)


def user_can_manage_risk_virksomhet_groups(user, virksomhet):
	if not user.is_authenticated or virksomhet is None:
		return False
	# TODO: Remove superuser bypass – temporary so testers can manage read groups for any virksomhet.
	if user.is_superuser:
		return True
	if not user.groups.filter(name=RISK_VIRKSOMHET_GROUP_ADMIN_AD_GROUP).exists():
		return False
	try:
		return user.profile.virksomhet_id == virksomhet.pk
	except AttributeError:
		return False


def annotate_scope_list(qs, user):
	member_qs = RiskScopeMember.objects.filter(
		scope=OuterRef('pk'),
		user=user,
	)
	owner_qs = RiskScopeMember.objects.filter(
		scope=OuterRef('pk'),
		user=user,
		role=RISK_SCOPE_MEMBER_ROLE_OWNER,
	)
	read_group_qs = RiskVirksomhetReadGroupMember.objects.filter(
		user=user,
		group__virksomhet_id=OuterRef('virksomhet_id'),
	)
	qs = qs.annotate(
		scenario_count=Count('scenarios'),
		current_user_is_member=Exists(member_qs),
		current_user_is_owner=Exists(owner_qs),
		current_user_has_read_group_access=Exists(read_group_qs),
	)
	return qs.annotate(
		current_user_has_read_access=Case(
			When(
				Q(current_user_is_member=True) | Q(current_user_has_read_group_access=True),
				then=Value(True),
			),
			default=Value(False),
			output_field=BooleanField(),
		),
	)


def scope_list_base_queryset(user):
	return annotate_scope_list(
		RiskScope.objects.select_related('virksomhet').prefetch_related(
			Prefetch(
				'memberships',
				queryset=RiskScopeMember.objects.filter(
					role=RISK_SCOPE_MEMBER_ROLE_OWNER,
				).select_related('user'),
			),
		),
		user,
	).order_by('-sist_revidert', '-opprettet')


def scopes_for_virksomhet(user, virksomhet_id):
	qs = scope_list_base_queryset(user)
	if virksomhet_id is None:
		return qs.filter(virksomhet__isnull=True)
	return qs.filter(virksomhet_id=virksomhet_id)


def scopes_for_user_membership(user, exclude_virksomhet_id=None):
	qs = scope_list_base_queryset(user).filter(
		memberships__user=user,
	).distinct()
	if exclude_virksomhet_id is not None:
		qs = qs.exclude(virksomhet_id=exclude_virksomhet_id)
	return qs


def other_ordinary_virksomheter(profile_virksomhet_obj):
	qs = Virksomhet.objects.filter(ordinar_virksomhet=True).order_by('virksomhetsnavn')
	if profile_virksomhet_obj is not None:
		qs = qs.exclude(pk=profile_virksomhet_obj.pk)
	return qs


def create_risk_scope(user, **scope_kwargs):
	virksomhet = creator_virksomhet(user)
	scope_kwargs.setdefault('status', 'forsteutkast')
	with transaction.atomic():
		scope = RiskScope.objects.create(
			virksomhet=virksomhet,
			**scope_kwargs,
		)
		RiskScopeMember.objects.create(
			scope=scope,
			user=user,
			role=RISK_SCOPE_MEMBER_ROLE_OWNER,
			added_by=user,
		)
	return scope
