# -*- coding: utf-8 -*-
# Change log:
# 2026-09-09: Shared LogEntry helper for inline (non-admin) object edits.
#
# Convention: after a successful user mutation outside Django admin, call
# log_object_change. One LogEntry per user action (one Lagre), not one per
# field unless fields are saved independently. Skip no-op saves.
# Risk workflow stays on RiskActivityLog; jobs/APIs stay on ApplicationLog.

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType

_LOG_MESSAGE_LIMIT = 8000
_OBJECT_REPR_LIMIT = 200


def log_object_change(user, obj, message, action_flag=CHANGE):
	"""Write one Django admin LogEntry for a non-admin object mutation."""
	if user is None or not getattr(user, 'pk', None):
		return None
	if not message:
		return None
	if len(message) > _LOG_MESSAGE_LIMIT:
		message = message[:_LOG_MESSAGE_LIMIT] + '… (truncated)'
	return LogEntry.objects.log_action(
		user_id=user.pk,
		content_type_id=ContentType.objects.get_for_model(obj).pk,
		object_id=obj.pk,
		object_repr=str(obj)[:_OBJECT_REPR_LIMIT],
		action_flag=action_flag,
		change_message=message,
	)


def format_m2m_diff(field_label, old_items, new_items):
	"""Norwegian added/removed summary for one M2M field, or '' if unchanged."""
	old_map = {item.pk: str(item) for item in old_items}
	new_map = {item.pk: str(item) for item in new_items}
	added = [new_map[pk] for pk in new_map if pk not in old_map]
	removed = [old_map[pk] for pk in old_map if pk not in new_map]
	if not added and not removed:
		return ''
	parts = []
	if added:
		parts.append('lagt til %s' % ', '.join(added))
	if removed:
		parts.append('fjernet %s' % ', '.join(removed))
	return '%s %s' % (field_label, '; '.join(parts))
