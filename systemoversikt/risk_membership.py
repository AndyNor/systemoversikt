# -*- coding: utf-8 -*-
# Change log:
# 2026-07-09: create_risk_scope – log scope_created to RiskActivityLog.
# 2026-07-08: search_scopes – server-side title/beskrivelse search across all collections (existence is open).
# 2026-07-07: change_riskvirksomhetgroup – virksomhetsadministrator may change/delete any group in profile virksomhet.
# 2026-07-07: Granular tilgangsgruppe helpers – view_riskscope create, member-gated edit, change_riskvirksomhetgroup for virksomhet_read_only.
# 2026-07-07: user_member_display_name – disambiguate same-name users with virksomhetsforkortelse on collection pages.
# 2026-07-06: Superuser bypass in user_has_risk_virksomhet_read_access – testers can open framework rollup pages.
# 2026-07-06: user_has_risk_virksomhet_read_access – scope/participant/read-group border for framework mapping.
# 2026-07-06: annotate_scope_list – anonymous users get false membership flags (no user FK in queries).
# 2026-07-02: risk_group_tag_colors – deterministic HSL tag colors from group pk.
# 2026-07-02: Prefetch participant_groups on scope list tables.
# 2026-07-02: storage_risk_group_title – store given name without forced virksomhetsforkortelse prefix.
# 2026-07-02: normalize_risk_group_title – display-only virksomhetsforkortelse/name formatting.
# 2026-07-02: Rename RiskVirksomhetReadGroup → RiskVirksomhetGroup in imports and queries.
# 2026-07-01: nav_ordinary_virksomheter – all nav links sorted by virksomhetsforkortelse.
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
	RiskVirksomhetGroup,
	RiskVirksomhetGroupMember,
	Virksomhet,
)
from systemoversikt.risk_activity_log import RISK_ACTIVITY_SCOPE_CREATED, log_risk_activity

RISK_CREATE_PERMISSION = 'systemoversikt.view_riskscope'
RISK_VIRKSOMHET_GROUP_CHANGE_PERMISSION = 'systemoversikt.change_riskvirksomhetgroup'


def risk_group_title_prefix(virksomhet):
	return '%s/' % virksomhet.virksomhetsforkortelse


def storage_risk_group_title(virksomhet, title):
	"""Return the given name stored in DB (no forced virksomhetsforkortelse prefix)."""
	title = (title or '').strip()
	if not title or virksomhet is None:
		return title
	prefix = risk_group_title_prefix(virksomhet)
	if title.lower().startswith(prefix.lower()):
		return title[len(prefix):].lstrip('/')
	return title


def normalize_risk_group_title(virksomhet, title):
	"""Display title as virksomhetsforkortelse/given-name."""
	bare = storage_risk_group_title(virksomhet, title)
	if not bare or virksomhet is None:
		return bare
	return risk_group_title_prefix(virksomhet) + bare


def risk_group_title_conflict(virksomhet, title, exclude_pk=None):
	stored = storage_risk_group_title(virksomhet, title)
	if not stored:
		return False
	qs = RiskVirksomhetGroup.objects.filter(virksomhet=virksomhet)
	if exclude_pk is not None:
		qs = qs.exclude(pk=exclude_pk)
	for group in qs:
		if storage_risk_group_title(virksomhet, group.title) == stored:
			return True
	return False


def risk_group_tag_colors(group_id):
	hue = (int(group_id) * 137.508) % 360
	return {
		'background': 'hsl(%d, 45%%, 88%%)' % hue,
		'color': 'hsl(%d, 50%%, 25%%)' % hue,
	}


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


def user_virksomhetsforkortelse(user):
	if user is None:
		return ''
	try:
		virksomhet = user.profile.virksomhet
	except Exception:
		return ''
	if virksomhet is None:
		return ''
	return (virksomhet.virksomhetsforkortelse or '').strip()


def user_member_display_name(user):
	"""Display name with virksomhetsforkortelse when set – disambiguates duplicate names."""
	name = user_display_name(user)
	fork = user_virksomhetsforkortelse(user)
	if fork:
		return '%s (%s)' % (name, fork)
	return name


def user_is_scope_participant_via_group(user, scope):
	if not user.is_authenticated:
		return False
	return RiskVirksomhetGroupMember.objects.filter(
		user_id=user.id,
		group__participant_scopes=scope,
	).exists()


def user_is_scope_member(user, scope):
	if not user.is_authenticated:
		return False
	if scope.memberships.filter(user_id=user.id).exists():
		return True
	return user_is_scope_participant_via_group(user, scope)


def user_has_virksomhet_read_group_access(user, virksomhet_id):
	if not user.is_authenticated or virksomhet_id is None:
		return False
	return RiskVirksomhetGroupMember.objects.filter(
		user_id=user.id,
		group__virksomhet_id=virksomhet_id,
		group__virksomhet_read_only=True,
	).exists()


def user_has_risk_virksomhet_read_access(user, virksomhet_id):
	if not user.is_authenticated or virksomhet_id is None:
		return False
	# TODO: Remove superuser bypass – temporary so testers can open virksomhet rollup and mapping pages.
	if user.is_superuser:
		return True
	if user_has_virksomhet_read_group_access(user, virksomhet_id):
		return True
	return RiskScope.objects.filter(
		virksomhet_id=virksomhet_id,
	).filter(
		Q(memberships__user_id=user.id)
		| Q(participant_groups__memberships__user_id=user.id)
	).exists()


def virksomheter_with_risk_read_access(user, as_queryset=True):
	if not user.is_authenticated:
		if as_queryset:
			return Virksomhet.objects.none()
		return []
	if user.is_superuser:
		qs = Virksomhet.objects.filter(ordinar_virksomhet=True).order_by('virksomhetsforkortelse')
		return qs if as_queryset else list(qs)
	read_group_ids = RiskVirksomhetGroupMember.objects.filter(
		user_id=user.id,
		group__virksomhet_read_only=True,
	).values_list('group__virksomhet_id', flat=True)
	scope_virksomhet_ids = RiskScope.objects.filter(
		Q(memberships__user_id=user.id)
		| Q(participant_groups__memberships__user_id=user.id)
	).values_list('virksomhet_id', flat=True)
	accessible_ids = set(read_group_ids) | set(scope_virksomhet_ids)
	accessible_ids.discard(None)
	qs = Virksomhet.objects.filter(
		pk__in=accessible_ids,
		ordinar_virksomhet=True,
	).order_by('virksomhetsforkortelse')
	return qs if as_queryset else list(qs)


def user_has_scope_read_access(user, scope):
	if user_is_scope_member(user, scope):
		return True
	if scope.virksomhet_id is None:
		return False
	return user_has_virksomhet_read_group_access(user, scope.virksomhet_id)


def user_has_scope_write_access(user, scope):
	# 2026-07-08: Archived scopes are read-only (no edits/deletes via scope APIs).
	if scope is not None and getattr(scope, 'archived_at', None) is not None:
		return False
	return user_is_scope_member(user, scope)


def user_can_create_risk_collection(user):
	return user.is_authenticated and user.has_perm(RISK_CREATE_PERMISSION)


def user_can_create_risk_virksomhet_group(user, virksomhet):
	if not user_can_create_risk_collection(user) or virksomhet is None:
		return False
	profile_v = profile_virksomhet(user)
	return profile_v is not None and profile_v.pk == virksomhet.pk


def user_is_risk_virksomhet_group_member(user, group):
	if not user.is_authenticated or group is None:
		return False
	return RiskVirksomhetGroupMember.objects.filter(
		user_id=user.id,
		group_id=group.pk,
	).exists()


def user_is_risk_virksomhet_group_member_in_virksomhet(user, virksomhet):
	if not user.is_authenticated or virksomhet is None:
		return False
	return RiskVirksomhetGroupMember.objects.filter(
		user_id=user.id,
		group__virksomhet_id=virksomhet.pk,
	).exists()


def user_can_access_risk_virksomhet_groups_page(user, virksomhet):
	if not user.is_authenticated or virksomhet is None:
		return False
	if user_can_create_risk_virksomhet_group(user, virksomhet):
		return True
	if user_can_manage_risk_virksomhet_groups(user, virksomhet):
		return True
	return user_is_risk_virksomhet_group_member_in_virksomhet(user, virksomhet)


def user_can_manage_risk_virksomhet_groups(user, virksomhet):
	"""Virksomhetsadministrator: change/delete any tilgangsgruppe in profile virksomhet."""
	if not user.is_authenticated or virksomhet is None:
		return False
	if not user.has_perm(RISK_VIRKSOMHET_GROUP_CHANGE_PERMISSION):
		return False
	profile_v = profile_virksomhet(user)
	return profile_v is not None and profile_v.pk == virksomhet.pk


def user_can_mutate_risk_virksomhet_group(user, group):
	if group is None:
		return False
	if user_is_risk_virksomhet_group_member(user, group):
		return True
	return user_can_manage_risk_virksomhet_groups(user, group.virksomhet)


def user_can_set_virksomhet_read_only_flag(user, virksomhet):
	return user_can_manage_risk_virksomhet_groups(user, virksomhet)


def annotate_scope_list(qs, user):
	if not user.is_authenticated:
		return qs.annotate(
			scenario_count=Count('scenarios'),
			current_user_is_direct_member=Value(False, output_field=BooleanField()),
			current_user_is_group_participant=Value(False, output_field=BooleanField()),
			current_user_is_owner=Value(False, output_field=BooleanField()),
			current_user_has_read_group_access=Value(False, output_field=BooleanField()),
			current_user_is_member=Value(False, output_field=BooleanField()),
			current_user_has_read_access=Value(False, output_field=BooleanField()),
		)
	user_id = user.pk
	member_qs = RiskScopeMember.objects.filter(
		scope=OuterRef('pk'),
		user_id=user_id,
	)
	owner_qs = RiskScopeMember.objects.filter(
		scope=OuterRef('pk'),
		user_id=user_id,
		role=RISK_SCOPE_MEMBER_ROLE_OWNER,
	)
	group_participant_qs = RiskVirksomhetGroupMember.objects.filter(
		user_id=user_id,
		group__participant_scopes=OuterRef('pk'),
	)
	read_group_qs = RiskVirksomhetGroupMember.objects.filter(
		user_id=user_id,
		group__virksomhet_id=OuterRef('virksomhet_id'),
		group__virksomhet_read_only=True,
	)
	qs = qs.annotate(
		scenario_count=Count('scenarios'),
		current_user_is_direct_member=Exists(member_qs),
		current_user_is_group_participant=Exists(group_participant_qs),
		current_user_is_owner=Exists(owner_qs),
		current_user_has_read_group_access=Exists(read_group_qs),
	)
	return qs.annotate(
		current_user_is_member=Case(
			When(
				Q(current_user_is_direct_member=True) | Q(current_user_is_group_participant=True),
				then=Value(True),
			),
			default=Value(False),
			output_field=BooleanField(),
		),
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
			Prefetch(
				'participant_groups',
				queryset=RiskVirksomhetGroup.objects.select_related('virksomhet').order_by('title'),
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
	if not user.is_authenticated:
		return RiskScope.objects.none()
	qs = scope_list_base_queryset(user).filter(
		Q(memberships__user_id=user.pk)
		| Q(participant_groups__memberships__user_id=user.pk),
	).distinct()
	if exclude_virksomhet_id is not None:
		qs = qs.exclude(virksomhet_id=exclude_virksomhet_id)
	return qs


def search_scopes(user, query):
	"""Match title/beskrivelse across all collections; annotate per-user read access for the list UI."""
	query = (query or '').strip()
	if not query:
		return RiskScope.objects.none()
	return scope_list_base_queryset(user).filter(
		Q(title__icontains=query) | Q(beskrivelse__icontains=query),
	)


def search_scopes_for_virksomhet(user, virksomhet_id, query):
	"""Match title/beskrivelse within one virksomhet's collections."""
	query = (query or '').strip()
	if not query:
		return RiskScope.objects.none()
	return scopes_for_virksomhet(user, virksomhet_id).filter(
		Q(title__icontains=query) | Q(beskrivelse__icontains=query),
	)


def nav_ordinary_virksomheter():
	return Virksomhet.objects.filter(ordinar_virksomhet=True).order_by('virksomhetsforkortelse')


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
	vlabel = ''
	if scope.virksomhet_id:
		vlabel = scope.virksomhet.virksomhetsforkortelse
	log_risk_activity(
		RISK_ACTIVITY_SCOPE_CREATED,
		'%s opprettet risikosamling «%s»%s.' % (
			user.get_username(),
			scope.title,
			(' (%s)' % vlabel) if vlabel else '',
		),
		user=user,
		scope=scope,
	)
	return scope
