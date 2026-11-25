# -*- coding: utf-8 -*-
# Change log:
# 2026-11-25: Cross-collection uønskede hendelser list – ACL filter, risk-rank sort, GET filters.

from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Q, Value, When

from systemoversikt.risk_criteria import RISK_LEVEL_VALUES, get_active_criteria
from systemoversikt.risk_framework import RISK_LABEL_RANK
from systemoversikt.risk_membership import scenarios_visible_to_user

PAGE_SIZE = 50


def _sk_pairs_for_label(label):
	"""Return (sannsynlighet, konsekvens) pairs that map to the given risk etikett."""
	criteria = get_active_criteria()
	pairs = []
	for s, row in criteria.risk_matrix.items():
		for k, value in row.items():
			if value == label:
				pairs.append((s, k))
	return pairs


def annotate_inherent_risk_rank(qs):
	"""Annotate risiko_rank from active criteria matrix (Høy=3 … Lav=1)."""
	criteria = get_active_criteria()
	whens = []
	for s, row in criteria.risk_matrix.items():
		for k, label in row.items():
			rank = RISK_LABEL_RANK.get(label or '', 0)
			whens.append(
				When(
					sannsynlighet_nivaa=s,
					konsekvens_nivaa=k,
					then=Value(rank),
				)
			)
	return qs.annotate(
		risiko_rank=Case(*whens, default=Value(0), output_field=IntegerField()),
	)


def filter_scenarios_queryset(qs, params):
	q = (params.get('q') or '').strip()
	if q:
		qs = qs.filter(
			Q(uonsket_hendelse__icontains=q)
			| Q(risk_id__icontains=q)
			| Q(scope__title__icontains=q)
		)

	virksomhet_id = (params.get('virksomhet') or '').strip()
	if virksomhet_id.isdigit():
		qs = qs.filter(scope__virksomhet_id=int(virksomhet_id))

	risikonivaa = (params.get('risikonivaa') or '').strip()
	if risikonivaa in RISK_LEVEL_VALUES:
		pairs = _sk_pairs_for_label(risikonivaa)
		if pairs:
			level_q = Q()
			for s, k in pairs:
				level_q |= Q(
					sannsynlighet_nivaa=s,
					konsekvens_nivaa=k,
				)
			qs = qs.filter(level_q)
		else:
			qs = qs.none()

	return qs


def paginate_queryset(qs, params, page_size=PAGE_SIZE):
	try:
		page_number = int(params.get('page') or 1)
	except (TypeError, ValueError):
		page_number = 1
	paginator = Paginator(qs, page_size)
	return paginator.get_page(page_number)


def hendelser_overview_queryset(user, params):
	include_archived = (params.get('include_archived') or '').strip() in ('1', 'true', 'yes')
	qs = scenarios_visible_to_user(user, include_archived=include_archived)
	qs = qs.select_related('scope', 'scope__virksomhet')
	qs = filter_scenarios_queryset(qs, params)
	qs = annotate_inherent_risk_rank(qs)
	return qs.order_by('-risiko_rank', 'scope__title', 'rekkefolge', 'risk_id')


def filter_context_from_params(params):
	return {
		'search_query': (params.get('q') or '').strip(),
		'filter_risikonivaa': (params.get('risikonivaa') or '').strip(),
		'filter_virksomhet': (params.get('virksomhet') or '').strip(),
		'include_archived': (params.get('include_archived') or '').strip() in ('1', 'true', 'yes'),
		'risikonivaa_choices': RISK_LEVEL_VALUES,
	}
