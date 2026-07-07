# -*- coding: utf-8 -*-
# Change log:
# 2026-07-07: Normalize imported criteria – backfill sannsynlighetstyper on older export files.

from django.utils import timezone

from systemoversikt.risk_criteria import (
	get_active_criteria,
	invalidate_criteria_cache,
	normalize_criteria_dict,
	validate_criteria,
	validate_slug_changes,
)

EXPORT_FORMAT = 'systemoversikt.risk_criteria'
EXPORT_FORMAT_VERSION = 1


def build_export_payload(criteria_bundle, user, title='Standard akseptkriterier'):
	"""Build JSON-serializable export document from active criteria."""
	username = ''
	if user is not None and getattr(user, 'is_authenticated', False):
		username = user.get_username()
	return {
		'format': EXPORT_FORMAT,
		'format_version': EXPORT_FORMAT_VERSION,
		'title': title,
		'criteria': criteria_bundle.to_storage_dict(),
		'exported_at': timezone.now().isoformat(),
		'exported_by': username,
	}


def parse_import_payload(raw_dict):
	"""Parse and validate export file structure. Returns (title, criteria_dict)."""
	if not isinstance(raw_dict, dict):
		raise ValueError('Filen må være et JSON-objekt.')
	if raw_dict.get('format') != EXPORT_FORMAT:
		raise ValueError('Ukjent filformat (forventet %s).' % EXPORT_FORMAT)
	if raw_dict.get('format_version') != EXPORT_FORMAT_VERSION:
		raise ValueError('Ustøttet formatversjon.')
	criteria = raw_dict.get('criteria')
	if not isinstance(criteria, dict):
		raise ValueError('Mangler criteria-objekt i filen.')
	title = (raw_dict.get('title') or 'Standard akseptkriterier').strip()
	if not title:
		title = 'Standard akseptkriterier'
	return title, criteria


def apply_imported_criteria(criteria_dict, user, title='Standard akseptkriterier'):
	"""
	Validate and persist imported criteria as the active config.
	Returns a list of error messages (empty on success).
	"""
	errors = list(validate_criteria(normalize_criteria_dict(criteria_dict)))
	if errors:
		return errors
	errors = list(validate_slug_changes(get_active_criteria(), normalize_criteria_dict(criteria_dict)))
	if errors:
		return errors

	criteria_dict = normalize_criteria_dict(criteria_dict)

	from systemoversikt.models import RiskCriteriaConfig

	row = RiskCriteriaConfig.objects.filter(is_active=True).first()
	if row is None:
		row = RiskCriteriaConfig(title=title, is_active=True)
	else:
		row.title = title
	row.criteria = criteria_dict
	row.oppdatert_av = user
	row.is_active = True
	row.save()
	invalidate_criteria_cache()
	return []
