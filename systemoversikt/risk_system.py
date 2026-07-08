# -*- coding: utf-8 -*-
# Change log:
# 2026-07-08: System details risk overview – scenarios linked via M2M, exclude archived collections.

from systemoversikt.models import RiskAction, RiskScenario
from systemoversikt.risk_criteria import get_active_criteria
from systemoversikt.risk_display import (
	annotate_scenario_risk_display,
	annotate_scenarios_tiltak_ids,
	build_ansvarlig_display_map,
)
from systemoversikt.risk_framework import (
	_risk_id_map_for_scenarios,
	_tiltak_rows_for_node_scenarios,
)

SAARBARHETSOVERSIKT_SIKKERHETSANALYTIKER_GROUP = (
	'/DS-SYSTEMOVERSIKT_SAARBARHETSOVERSIKT_SIKKERHETSANALYTIKER'
)


def user_can_view_system_restricted_security(user, system):
	"""Same audience as Sårbarheter on system details, plus superuser."""
	if not user.is_authenticated:
		return False
	if user.is_superuser:
		return True
	if user.username in system.eiere():
		return True
	if user.groups.filter(name=SAARBARHETSOVERSIKT_SIKKERHETSANALYTIKER_GROUP).exists():
		return True
	return False


def _scenarios_for_system(system):
	return list(
		RiskScenario.objects.filter(
			systemer=system,
			scope__archived_at__isnull=True,
		).select_related('scope', 'scope__virksomhet')
		.prefetch_related('systemer', 'actions')
		.order_by('scope__title', 'rekkefolge', 'risk_id')
	)


def build_system_risk_context(system):
	scenarios = _scenarios_for_system(system)
	criteria = get_active_criteria()

	if not scenarios:
		return {
			'system_risk_has_data': False,
			'system_risk_scenarios': [],
			'system_risk_matrix_current': criteria.build_matrix_context([], use_residual=False),
			'system_risk_matrix_residual': criteria.build_matrix_context([], use_residual=True),
			'system_risk_konsekvens_labels': criteria.konsekvens_labels,
			'system_risk_tiltak_rows': [],
		}

	risk_id_by_pk = _risk_id_map_for_scenarios(scenarios)
	for scenario in scenarios:
		scenario.display_risk_id = risk_id_by_pk.get(scenario.pk, scenario.risk_id)
		annotate_scenario_risk_display(scenario, criteria)

	by_scope = {}
	for scenario in scenarios:
		by_scope.setdefault(scenario.scope_id, []).append(scenario)

	scope_ids = list(by_scope.keys())
	actions = list(
		RiskAction.objects.filter(scope_id__in=scope_ids)
		.select_related('scope')
		.prefetch_related('scenarios')
		.order_by('scope_id', 'pk')
	)

	for scope_id, scope_scenarios in by_scope.items():
		scope_actions = [action for action in actions if action.scope_id == scope_id]
		annotate_scenarios_tiltak_ids(scope_scenarios, scope_actions)

	ansvarlig_lookup = build_ansvarlig_display_map([action.ansvarlig for action in actions])
	tiltak_rows = _tiltak_rows_for_node_scenarios(
		scenarios,
		actions,
		risk_id_by_pk,
		ansvarlig_lookup,
	)

	return {
		'system_risk_has_data': True,
		'system_risk_scenarios': scenarios,
		'system_risk_matrix_current': criteria.build_matrix_context(scenarios, use_residual=False),
		'system_risk_matrix_residual': criteria.build_matrix_context(scenarios, use_residual=True),
		'system_risk_konsekvens_labels': criteria.konsekvens_labels,
		'system_risk_tiltak_rows': tiltak_rows,
	}
