# -*- coding: utf-8 -*-
# Change log:
# 2026-06-30: create_risk_scope – explicit forsteutkast status on new collections.
# 2026-06-30: create_risk_scope – creator as first owner with virksomhet from profile.

from django.db import transaction

from systemoversikt.models import (
	RISK_SCOPE_MEMBER_ROLE_OWNER,
	RiskScope,
	RiskScopeMember,
)


def creator_virksomhet(user):
	try:
		profile = user.profile
		return profile.virksomhet_innlogget_som or profile.virksomhet
	except Exception:
		return None


def user_display_name(user):
	if user is None:
		return ''
	full = user.get_full_name()
	return full.strip() if full else user.username


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
