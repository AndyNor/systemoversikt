# -*- coding: utf-8 -*-
# Change log:
# 2026-10-13: Default tiltak status filter – besluttet, under_arbeid, kontinuerlig_oppfolging.
# 2026-10-13: Multi-status via getlist/checkboxes for tiltak overview filters.
# 2026-08-13: Server-side filters for global tiltak and unntak overviews.

from django.core.paginator import Paginator
from django.db.models import Count, Q

from systemoversikt.models import RISK_ACTION_STATUS_VALG
from systemoversikt.risk_criteria import RISK_LEVEL_VALUES, get_active_criteria
from systemoversikt.risk_membership import actions_visible_to_user, unntak_visible_to_user

PAGE_SIZE = 50

# Default when no status= is in the query – active follow-up statuses, not forslag/utført.
DEFAULT_TILTAK_STATUS_FILTER = (
	'besluttet',
	'under_arbeid',
	'kontinuerlig_oppfolging',
)


def _sk_pairs_for_label(label):
	"""Return (sannsynlighet, konsekvens) pairs that map to the given risk etikett."""
	criteria = get_active_criteria()
	pairs = []
	for s, row in criteria.risk_matrix.items():
		for k, value in row.items():
			if value == label:
				pairs.append((s, k))
	return pairs


def _status_filter_values(params, default=None):
	"""Unique valid status codes from repeated status= params and/or comma-separated values."""
	raw = []
	if hasattr(params, 'getlist'):
		raw.extend(params.getlist('status'))
	else:
		single = params.get('status')
		if single:
			raw.append(single)
	valid = {v for v, _ in RISK_ACTION_STATUS_VALG}
	seen = set()
	statuses = []
	for part in raw:
		for status in str(part).split(','):
			status = status.strip()
			if status in valid and status not in seen:
				seen.add(status)
				statuses.append(status)
	if not statuses and default is not None:
		return list(default)
	return statuses


def filter_actions_queryset(qs, params):
	q = (params.get('q') or '').strip()
	if q:
		qs = qs.filter(
			Q(beskrivelse__icontains=q)
			| Q(ansvarlig__icontains=q)
			| Q(scope__title__icontains=q)
			| Q(scenarios__risk_id__icontains=q)
			| Q(scenarios__uonsket_hendelse__icontains=q)
		).distinct()

	statuses = _status_filter_values(params, default=DEFAULT_TILTAK_STATUS_FILTER)
	if statuses:
		qs = qs.filter(status__in=statuses)

	eskaleres = (params.get('eskaleres') or '').strip().lower()
	if eskaleres in ('1', 'true', 'yes', 'ja'):
		qs = qs.filter(eskaleres=True)
	elif eskaleres in ('0', 'false', 'no', 'nei'):
		qs = qs.filter(eskaleres=False)

	har_unntak = (params.get('har_unntak') or '').strip().lower()
	if har_unntak in ('1', 'true', 'yes', 'ja'):
		qs = qs.filter(unntak__aktiv=True).distinct()
	elif har_unntak in ('0', 'false', 'no', 'nei'):
		qs = qs.exclude(unntak__aktiv=True).distinct()

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
					scenarios__sannsynlighet_nivaa=s,
					scenarios__konsekvens_nivaa=k,
				)
			qs = qs.filter(level_q).distinct()
		else:
			qs = qs.none()

	return qs


def filter_unntak_queryset(qs, params):
	q = (params.get('q') or '').strip()
	if q:
		qs = qs.filter(
			Q(beskrivelse__icontains=q)
			| Q(begrunnelse__icontains=q)
			| Q(action__beskrivelse__icontains=q)
			| Q(action__scope__title__icontains=q)
		).distinct()

	aktiv = (params.get('aktiv') or '').strip().lower()
	if aktiv in ('1', 'true', 'yes', 'ja'):
		qs = qs.filter(aktiv=True)
	elif aktiv in ('0', 'false', 'no', 'nei'):
		qs = qs.filter(aktiv=False)

	virksomhet_id = (params.get('virksomhet') or '').strip()
	if virksomhet_id.isdigit():
		qs = qs.filter(action__scope__virksomhet_id=int(virksomhet_id))

	statuses = _status_filter_values(params)
	if statuses:
		qs = qs.filter(action__status__in=statuses)

	eskaleres = (params.get('eskaleres') or '').strip().lower()
	if eskaleres in ('1', 'true', 'yes', 'ja'):
		qs = qs.filter(action__eskaleres=True)
	elif eskaleres in ('0', 'false', 'no', 'nei'):
		qs = qs.filter(action__eskaleres=False)

	risikonivaa = (params.get('risikonivaa') or '').strip()
	if risikonivaa in RISK_LEVEL_VALUES:
		pairs = _sk_pairs_for_label(risikonivaa)
		if pairs:
			level_q = Q()
			for s, k in pairs:
				level_q |= Q(
					action__scenarios__sannsynlighet_nivaa=s,
					action__scenarios__konsekvens_nivaa=k,
				)
			qs = qs.filter(level_q).distinct()
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


def tiltak_overview_queryset(user, params):
	include_archived = (params.get('include_archived') or '').strip() in ('1', 'true', 'yes')
	qs = actions_visible_to_user(user, include_archived=include_archived)
	qs = qs.select_related('scope', 'scope__virksomhet').prefetch_related('scenarios', 'unntak')
	qs = filter_actions_queryset(qs, params)
	qs = qs.annotate(
		unntak_aktiv_count=Count('unntak', filter=Q(unntak__aktiv=True)),
	).order_by('scope__title', 'pk')
	return qs


def unntak_overview_queryset(user, params):
	include_archived = (params.get('include_archived') or '').strip() in ('1', 'true', 'yes')
	qs = unntak_visible_to_user(user, include_archived=include_archived)
	qs = qs.select_related(
		'action',
		'action__scope',
		'action__scope__virksomhet',
		'opprettet_av',
	).prefetch_related('systemer', 'action__scenarios')
	qs = filter_unntak_queryset(qs, params)
	return qs.order_by('-aktiv', '-opprettet', 'pk')


def filter_context_from_params(params, default_statuses=None):
	# 2026-10-13: filter_statuses list for checkboxes; filter_status kept as comma-joined for links/selects.
	# 2026-10-13: default_statuses used on tiltak overview when no status= is present.
	statuses = _status_filter_values(params, default=default_statuses)
	return {
		'search_query': (params.get('q') or '').strip(),
		'filter_status': ','.join(statuses),
		'filter_statuses': statuses,
		'filter_eskaleres': (params.get('eskaleres') or '').strip(),
		'filter_risikonivaa': (params.get('risikonivaa') or '').strip(),
		'filter_har_unntak': (params.get('har_unntak') or '').strip(),
		'filter_aktiv': (params.get('aktiv') or '').strip(),
		'filter_virksomhet': (params.get('virksomhet') or '').strip(),
		'include_archived': (params.get('include_archived') or '').strip() in ('1', 'true', 'yes'),
		'status_choices': RISK_ACTION_STATUS_VALG,
		'risikonivaa_choices': RISK_LEVEL_VALUES,
	}
