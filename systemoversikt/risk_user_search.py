# -*- coding: utf-8 -*-
# Change log:
# 2026-08-13: Shared risiko person search – multi-word AND, exact email first, preferred virksomhet ranking.

from functools import reduce
from operator import and_

from django.contrib.auth.models import User
from django.db.models import Case, IntegerField, Q, Value, When

from systemoversikt.risk_membership import creator_virksomhet


def preferred_virksomhet_for_scope(scope, user):
	"""Collection virksomhet when set; otherwise logged-in user's virksomhet."""
	if scope is not None and getattr(scope, 'virksomhet', None) is not None:
		return scope.virksomhet
	return creator_virksomhet(user)


def _term_q(term):
	return (
		Q(username__icontains=term)
		| Q(first_name__icontains=term)
		| Q(last_name__icontains=term)
		| Q(email__icontains=term)
		| Q(profile__displayName__icontains=term)
	)


def search_active_users(q, *, prefer_virksomhet=None, restrict_virksomhet=None, limit=15):
	"""
	Active-user autocomplete for risiko person pickers.

	- Multi-word: each term must match (AND); per term OR across name/email/username/displayName.
	- Rank: exact email (full q) first, then preferred virksomhet, then alphabetical.
	- restrict_virksomhet hard-filters candidates (tiltak ansvarlig); prefer_virksomhet only ranks.
	"""
	q = (q or '').strip()
	terms = q.split()
	if not terms:
		return User.objects.none()

	query = reduce(and_, (_term_q(term) for term in terms))
	qs = (
		User.objects.filter(query)
		.filter(is_active=True)
		.select_related('profile', 'profile__virksomhet')
	)

	if restrict_virksomhet is not None:
		qs = qs.filter(profile__virksomhet=restrict_virksomhet)

	prefer_id = prefer_virksomhet.pk if prefer_virksomhet is not None else None
	annotations = {
		'email_exact': Case(
			When(email__iexact=q, then=Value(0)),
			default=Value(1),
			output_field=IntegerField(),
		),
	}
	if prefer_id is not None:
		annotations['same_virksomhet'] = Case(
			When(profile__virksomhet_id=prefer_id, then=Value(0)),
			default=Value(1),
			output_field=IntegerField(),
		)
		order = ['email_exact', 'same_virksomhet', 'first_name', 'last_name', 'username']
	else:
		order = ['email_exact', 'first_name', 'last_name', 'username']

	return qs.annotate(**annotations).distinct().order_by(*order)[:limit]
