# -*- coding: utf-8 -*-
# Change log:
# 2026-06-26: Scenario Tiltak column lists all linked actions (all statuses).
# 2026-06-26: Scenario tiltak ID list (T7, T8) for scenario table Tiltak column.
# 2026-06-26: Display-time R/T IDs and scope-level tiltak rows for risk module.


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
	if risk_id_by_scenario_pk is None:
		risk_id_by_scenario_pk = annotate_scenario_display_ids(scenarios)

	rows = []
	for index, action in enumerate(actions, start=1):
		risk_links = []
		for scenario in action.scenarios.all():
			risk_id = risk_id_by_scenario_pk.get(scenario.pk)
			if risk_id:
				risk_links.append({
					'risk_id': risk_id,
					'scenario_pk': scenario.pk,
				})
		risk_links.sort(key=lambda link: int(link['risk_id'][1:]))

		rows.append({
			'display_tiltak_id': 'T%d' % index,
			'action': action,
			'risk_links': risk_links,
		})
	return rows
