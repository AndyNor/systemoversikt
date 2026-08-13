# -*- coding: utf-8 -*-
# Change log:
# 2026-08-13: Unntak create/update/delete event types for tiltak coverage gaps.
# 2026-08-10: Scenario/tiltak/member event types for extended risk activity logging.
# 2026-07-09: Dedicated risk module activity log – helper and event-type constants.

from systemoversikt.models import RiskActivityLog

_LOG_MESSAGE_LIMIT = 8000

# Event-type constants (single source of truth).
RISK_ACTIVITY_SCOPE_CREATED = 'scope_created'
RISK_ACTIVITY_SCOPE_STATUS_CHANGED = 'scope_status_changed'
RISK_ACTIVITY_SCOPE_ARCHIVED = 'scope_archived'
RISK_ACTIVITY_SAMMENSTILLING_CREATED = 'sammenstilling_created'
RISK_ACTIVITY_SAMMENSTILLING_ARCHIVED = 'sammenstilling_archived'
RISK_ACTIVITY_CRITERIA_UPDATED = 'criteria_updated'
RISK_ACTIVITY_CRITERIA_IMPORTED = 'criteria_imported'
RISK_ACTIVITY_MAL_NODE_CREATED = 'mal_node_created'
RISK_ACTIVITY_MAL_NODE_UPDATED = 'mal_node_updated'
RISK_ACTIVITY_MAL_NODE_MOVED = 'mal_node_moved'
RISK_ACTIVITY_MAL_IMPORTED = 'mal_imported'
RISK_ACTIVITY_MAL_CREATED = 'mal_created'
RISK_ACTIVITY_SCENARIO_CREATED = 'scenario_created'
RISK_ACTIVITY_SCENARIO_DELETED = 'scenario_deleted'
RISK_ACTIVITY_SCENARIO_RISK_LEVEL_CHANGED = 'scenario_risk_level_changed'
RISK_ACTIVITY_SCENARIO_TREATMENT_CHANGED = 'scenario_treatment_changed'
RISK_ACTIVITY_ACTION_CREATED = 'action_created'
RISK_ACTIVITY_ACTION_DELETED = 'action_deleted'
RISK_ACTIVITY_ACTION_STATUS_CHANGED = 'action_status_changed'
RISK_ACTIVITY_UNNTAK_CREATED = 'unntak_created'
RISK_ACTIVITY_UNNTAK_UPDATED = 'unntak_updated'
RISK_ACTIVITY_UNNTAK_DELETED = 'unntak_deleted'
RISK_ACTIVITY_MEMBER_ADDED = 'member_added'
RISK_ACTIVITY_MEMBER_REMOVED = 'member_removed'

RISK_ACTIVITY_EVENT_LABELS = {
	RISK_ACTIVITY_SCOPE_CREATED: 'Risikosamling opprettet',
	RISK_ACTIVITY_SCOPE_STATUS_CHANGED: 'Status endret',
	RISK_ACTIVITY_SCOPE_ARCHIVED: 'Risikosamling arkivert',
	RISK_ACTIVITY_SAMMENSTILLING_CREATED: 'Sammenstilling opprettet',
	RISK_ACTIVITY_SAMMENSTILLING_ARCHIVED: 'Sammenstilling arkivert',
	RISK_ACTIVITY_CRITERIA_UPDATED: 'Akseptkriterier endret',
	RISK_ACTIVITY_CRITERIA_IMPORTED: 'Akseptkriterier importert',
	RISK_ACTIVITY_MAL_NODE_CREATED: 'Mal: node opprettet',
	RISK_ACTIVITY_MAL_NODE_UPDATED: 'Mal: node endret',
	RISK_ACTIVITY_MAL_NODE_MOVED: 'Mal: node flyttet',
	RISK_ACTIVITY_MAL_IMPORTED: 'Mal importert fra fil',
	RISK_ACTIVITY_MAL_CREATED: 'Mal opprettet fra fil',
	RISK_ACTIVITY_SCENARIO_CREATED: 'Risiko opprettet',
	RISK_ACTIVITY_SCENARIO_DELETED: 'Risiko slettet',
	RISK_ACTIVITY_SCENARIO_RISK_LEVEL_CHANGED: 'Risiknivå endret',
	RISK_ACTIVITY_SCENARIO_TREATMENT_CHANGED: 'Risikobehandling endret',
	RISK_ACTIVITY_ACTION_CREATED: 'Tiltak opprettet',
	RISK_ACTIVITY_ACTION_DELETED: 'Tiltak slettet',
	RISK_ACTIVITY_ACTION_STATUS_CHANGED: 'Tiltakstatus endret',
	RISK_ACTIVITY_UNNTAK_CREATED: 'Unntak opprettet',
	RISK_ACTIVITY_UNNTAK_UPDATED: 'Unntak endret',
	RISK_ACTIVITY_UNNTAK_DELETED: 'Unntak slettet',
	RISK_ACTIVITY_MEMBER_ADDED: 'Medlem lagt til',
	RISK_ACTIVITY_MEMBER_REMOVED: 'Medlem fjernet',
}


def display_label(event_type):
	return RISK_ACTIVITY_EVENT_LABELS.get(event_type, event_type)


def log_risk_activity(event_type, message, *, user=None, scope=None, sammenstilling=None, framework=None):
	"""Append one risk workflow event to RiskActivityLog."""
	if len(message) > _LOG_MESSAGE_LIMIT:
		message = message[:_LOG_MESSAGE_LIMIT] + '… (truncated)'
	RiskActivityLog.objects.create(
		event_type=event_type,
		message=message,
		user=user,
		scope=scope,
		sammenstilling=sammenstilling,
		framework=framework,
	)
