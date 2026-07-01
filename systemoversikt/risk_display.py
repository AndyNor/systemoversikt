# -*- coding: utf-8 -*-
# Change log:
# 2026-07-01: Ansvarlig display resolution – map email/UPN to Profile displayName for tiltak UI.
# 2026-06-30: Tiltak risk_links include nåværende risiko CSS for colored Risk ID tags.
# 2026-06-26: Scenario Tiltak column lists all linked actions (all statuses).
# 2026-06-26: Scenario tiltak ID list (T7, T8) for scenario table Tiltak column.
# 2026-06-26: Display-time R/T IDs and scope-level tiltak rows for risk module.

from django.contrib.auth.models import User
from django.db.models import Q


def looks_like_email_upn(value):
	return bool(value and '@' in str(value))


def user_ansvarlig_display_name(user):
	profile = getattr(user, 'profile', None)
	if profile and profile.displayName:
		name = profile.displayName.strip()
		if name:
			return name
	full = user.get_full_name()
	if full and full.strip():
		return full.strip()
	return user.username


def build_ansvarlig_display_map(raw_values):
	candidates = []
	seen = set()
	for raw in raw_values or []:
		if not raw:
			continue
		val = str(raw).strip()
		if not looks_like_email_upn(val):
			continue
		key = val.lower()
		if key not in seen:
			seen.add(key)
			candidates.append(val)
	if not candidates:
		return {}

	query = Q()
	for val in candidates:
		query |= Q(email__iexact=val) | Q(username__iexact=val)

	by_key = {}
	for user in User.objects.filter(query).select_related('profile'):
		display = user_ansvarlig_display_name(user)
		if user.email:
			by_key[user.email.lower()] = display
		by_key[user.username.lower()] = display

	result = {}
	for raw in raw_values or []:
		if not raw:
			continue
		val = str(raw).strip()
		if not looks_like_email_upn(val):
			result[val] = val
		else:
			result[val] = by_key.get(val.lower(), val)
	return result


def resolve_ansvarlig_display(value, lookup=None):
	if not value:
		return ''
	val = str(value).strip()
	if not looks_like_email_upn(val):
		return val
	if lookup is not None:
		return lookup.get(val, lookup.get(val.lower(), val))
	return build_ansvarlig_display_map([val]).get(val, val)


def annotate_scenario_display_ids(scenarios):
	"""Assign display_risk_id (R1, R2, …) from scenario order within a collection."""
	mapping = {}
	for index, scenario in enumerate(scenarios, start=1):
		display_id = 'R%d' % index
		scenario.display_risk_id = display_id
		mapping[scenario.pk] = display_id
	return mapping


def tiltak_display_id_map(actions):
	"""Map action pk -> display tiltak id (T1, T2, …) by stable scope order."""
	mapping = {}
	for index, action in enumerate(actions, start=1):
		mapping[action.pk] = 'T%d' % index
	return mapping


def scenario_display_tiltak_ids(scenario, tiltak_id_map):
	"""Comma-separated T# labels for all actions linked to a scenario."""
	ids = []
	for action in scenario.actions.all():
		tid = tiltak_id_map.get(action.pk)
		if tid:
			ids.append(tid)
	ids.sort(key=lambda label: int(label[1:]))
	return ', '.join(ids) if ids else '–'


def annotate_scenarios_tiltak_ids(scenarios, actions):
	"""Set scenario.display_tiltak_ids on each scenario; return tiltak id map."""
	tiltak_map = tiltak_display_id_map(actions)
	for scenario in scenarios:
		scenario.display_tiltak_ids = scenario_display_tiltak_ids(scenario, tiltak_map)
	return tiltak_map


def build_scope_tiltak_rows(scenarios, actions, risk_id_by_scenario_pk=None):
	"""
	One row per scope-level tiltak: T#, description, linked Risk ID(s).
	actions should be ordered consistently (e.g. by pk).
	"""
	from systemoversikt.risk_criteria import risk_cell_css_class

	if risk_id_by_scenario_pk is None:
		risk_id_by_scenario_pk = annotate_scenario_display_ids(scenarios)

	scenario_by_pk = {scenario.pk: scenario for scenario in scenarios}

	rows = []
	for index, action in enumerate(actions, start=1):
		risk_links = []
		for scenario in action.scenarios.all():
			risk_id = risk_id_by_scenario_pk.get(scenario.pk)
			if risk_id:
				full = scenario_by_pk.get(scenario.pk, scenario)
				etikett = full.risiko_etikett or ''
				risk_links.append({
					'risk_id': risk_id,
					'scenario_pk': scenario.pk,
					'risiko_etikett': etikett,
					'risiko_css': risk_cell_css_class(etikett),
				})
		risk_links.sort(key=lambda link: int(link['risk_id'][1:]))

		rows.append({
			'display_tiltak_id': 'T%d' % index,
			'action': action,
			'risk_links': risk_links,
		})
	return rows
