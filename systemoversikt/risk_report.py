# -*- coding: utf-8 -*-
# Change log:
# 2026-07-07: Report helpers – scenario/tiltak sorting and scope system aggregation for godkjent rapport.

from systemoversikt.risk_display import tiltak_display_id_map

TILTAK_STATUS_ORDER = ('utfort', 'under_arbeid', 'besluttet', 'forslag')
BESLUTTET_TILTAK_STATUSES = frozenset(('besluttet', 'under_arbeid', 'utfort'))
TILTAK_STATUS_RANK = {status: index for index, status in enumerate(TILTAK_STATUS_ORDER)}


def scenario_risk_score(scenario):
	s = scenario.sannsynlighet_nivaa
	k = scenario.konsekvens_nivaa
	if s is None or k is None:
		return 0
	return int(s) * int(k)


def sort_scenarios_for_report(scenarios):
	return sorted(
		scenarios,
		key=lambda scenario: (-scenario_risk_score(scenario), scenario.rekkefolge, scenario.risk_id),
	)


def _tiltak_sort_key(action, tiltak_map):
	tid = tiltak_map.get(action.pk, 'T9999')
	try:
		num = int(tid[1:])
	except (TypeError, ValueError):
		num = 9999
	return (TILTAK_STATUS_RANK.get(action.status, 99), num)


def sort_tiltak_for_report(actions, tiltak_map=None):
	if tiltak_map is None:
		tiltak_map = tiltak_display_id_map(actions)
	return sorted(actions, key=lambda action: _tiltak_sort_key(action, tiltak_map))


def collect_scope_systems(scenarios):
	seen = {}
	for scenario in scenarios:
		for system in scenario.systemer.all():
			seen[system.pk] = system
	return sorted(seen.values(), key=lambda system: (system.systemnavn or '').lower())


def besluttede_tiltak(actions, tiltak_map=None):
	if tiltak_map is None:
		tiltak_map = tiltak_display_id_map(actions)
	filtered = [action for action in actions if action.status in BESLUTTET_TILTAK_STATUSES]
	return sort_tiltak_for_report(filtered, tiltak_map)


def build_scenario_report_sections(scenarios, tiltak_map=None):
	if tiltak_map is None:
		all_actions = []
		for scenario in scenarios:
			all_actions.extend(scenario.actions.all())
		tiltak_map = tiltak_display_id_map(all_actions)

	sections = []
	for scenario in sort_scenarios_for_report(scenarios):
		actions = sort_tiltak_for_report(list(scenario.actions.all()), tiltak_map)
		sections.append({
			'scenario': scenario,
			'tiltak_entries': [
				{
					'action': action,
					'display_tiltak_id': tiltak_map.get(action.pk, ''),
				}
				for action in actions
			],
		})
	return sections
