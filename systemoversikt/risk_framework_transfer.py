# -*- coding: utf-8 -*-
# Change log:
# 2026-07-07: JSON export/import for risk framework maler – move templates between environments.

import re

from django.db import transaction
from django.utils import timezone

from systemoversikt.models import (
	RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
	RiskFramework,
	RiskFrameworkNode,
	RiskSammenstillingNodeAssessment,
	RiskSammenstillingScenarioLink,
)

EXPORT_FORMAT = 'systemoversikt.risk_framework_mal'
EXPORT_FORMAT_VERSION = 1
_SLUG_RE = re.compile(r'^[-a-z0-9]+$')


def build_mal_export_payload(framework, user):
	"""Build JSON-serializable export document for a risk framework template."""
	username = ''
	if user is not None and getattr(user, 'is_authenticated', False):
		username = user.get_username()

	categories = RiskFrameworkNode.objects.filter(
		framework=framework,
		parent__isnull=True,
		status=RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
	).order_by('nummer')

	taxonomy = []
	for category in categories:
		children = RiskFrameworkNode.objects.filter(
			parent=category,
			status=RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
		).order_by('nummer')
		taxonomy.append({
			'nummer': category.nummer,
			'title': category.title,
			'forklaring': category.forklaring,
			'children': [
				{
					'nummer': child.nummer,
					'title': child.title,
					'forklaring': child.forklaring,
				}
				for child in children
			],
		})

	return {
		'format': EXPORT_FORMAT,
		'format_version': EXPORT_FORMAT_VERSION,
		'framework': {
			'title': framework.title,
			'slug': framework.slug,
			'beskrivelse': framework.beskrivelse,
		},
		'taxonomy': taxonomy,
		'exported_at': timezone.now().isoformat(),
		'exported_by': username,
	}


def parse_mal_import_payload(raw_dict):
	"""Parse and validate export file structure. Returns (framework_meta, taxonomy)."""
	if not isinstance(raw_dict, dict):
		raise ValueError('Filen må være et JSON-objekt.')
	if raw_dict.get('format') != EXPORT_FORMAT:
		raise ValueError('Ukjent filformat (forventet %s).' % EXPORT_FORMAT)
	if raw_dict.get('format_version') != EXPORT_FORMAT_VERSION:
		raise ValueError('Ustøttet formatversjon.')
	framework_meta = raw_dict.get('framework')
	if not isinstance(framework_meta, dict):
		raise ValueError('Mangler framework-objekt i filen.')
	taxonomy = raw_dict.get('taxonomy')
	if not isinstance(taxonomy, list):
		raise ValueError('Mangler taxonomy-liste i filen.')
	return framework_meta, taxonomy


def _validate_taxonomy(taxonomy):
	errors = []
	if not taxonomy:
		errors.append('Taksonomien må ha minst én hovedkategori.')
		return errors

	seen_cat_nummer = set()
	for idx, cat in enumerate(taxonomy, start=1):
		if not isinstance(cat, dict):
			errors.append('Hovedkategori %d er ugyldig.' % idx)
			continue
		nummer = cat.get('nummer')
		title = (cat.get('title') or '').strip()
		if not isinstance(nummer, int) or nummer < 1:
			errors.append('Hovedkategori %d mangler gyldig nummer.' % idx)
		elif nummer in seen_cat_nummer:
			errors.append('Duplikat hovedkategorinummer %d.' % nummer)
		else:
			seen_cat_nummer.add(nummer)
		if not title:
			errors.append('Hovedkategori %d mangler tittel.' % idx)

		children = cat.get('children') or []
		if not isinstance(children, list):
			errors.append('Underkategorier for hovedkategori %d er ugyldige.' % idx)
			continue
		seen_child_nummer = set()
		for child_idx, child in enumerate(children, start=1):
			if not isinstance(child, dict):
				errors.append('Underkategori %d.%d er ugyldig.' % (idx, child_idx))
				continue
			child_nummer = child.get('nummer')
			child_title = (child.get('title') or '').strip()
			if not isinstance(child_nummer, int) or child_nummer < 1:
				errors.append('Underkategori %d.%d mangler gyldig nummer.' % (idx, child_idx))
			elif child_nummer in seen_child_nummer:
				errors.append('Duplikat underkategorinummer %d i hovedkategori %d.' % (child_nummer, idx))
			else:
				seen_child_nummer.add(child_nummer)
			if not child_title:
				errors.append('Underkategori %d.%d mangler tittel.' % (idx, child_idx))
	return errors


def _validate_slug(slug):
	slug = (slug or '').strip()
	if not slug:
		return 'Mangler slug.'
	if not _SLUG_RE.match(slug):
		return 'Slug må bare inneholde små bokstaver, tall og bindestrek.'
	return None


def framework_has_node_dependencies(framework):
	node_ids = RiskFrameworkNode.objects.filter(framework=framework).values_list('pk', flat=True)
	if not node_ids:
		return False
	if RiskSammenstillingScenarioLink.objects.filter(framework_node_id__in=node_ids).exists():
		return True
	if RiskSammenstillingNodeAssessment.objects.filter(framework_node_id__in=node_ids).exists():
		return True
	return False


def _apply_taxonomy(framework, taxonomy):
	RiskFrameworkNode.objects.filter(framework=framework).delete()
	for cat_data in taxonomy:
		category = RiskFrameworkNode.objects.create(
			framework=framework,
			parent=None,
			nummer=cat_data['nummer'],
			title=(cat_data.get('title') or '').strip(),
			forklaring=(cat_data.get('forklaring') or '').strip(),
			status=RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
			rekkefolge=cat_data['nummer'],
		)
		for child_data in cat_data.get('children') or []:
			RiskFrameworkNode.objects.create(
				framework=framework,
				parent=category,
				nummer=child_data['nummer'],
				title=(child_data.get('title') or '').strip(),
				forklaring=(child_data.get('forklaring') or '').strip(),
				status=RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
				rekkefolge=child_data['nummer'],
			)


def apply_mal_import_to_framework(framework, framework_meta, taxonomy):
	"""Replace taxonomy on an existing framework. Returns a list of error messages."""
	errors = list(_validate_taxonomy(taxonomy))
	if errors:
		return errors
	if framework_has_node_dependencies(framework):
		return [
			'Malen har kartleggingskoblinger eller vurderinger og kan ikke erstattes via import. '
			'Opprett en ny mal i stedet.',
		]

	with transaction.atomic():
		title = (framework_meta.get('title') or '').strip()
		if title:
			framework.title = title
		if 'beskrivelse' in framework_meta:
			framework.beskrivelse = (framework_meta.get('beskrivelse') or '').strip()
		framework.save()
		_apply_taxonomy(framework, taxonomy)
	return []


def create_mal_from_import(framework_meta, taxonomy, slug_override=None):
	"""Create a new framework from import data. Returns (framework, errors)."""
	errors = list(_validate_taxonomy(taxonomy))
	if errors:
		return None, errors

	slug = (slug_override or framework_meta.get('slug') or '').strip()
	slug_error = _validate_slug(slug)
	if slug_error:
		return None, [slug_error]
	if RiskFramework.objects.filter(slug=slug).exists():
		return None, ['Slug «%s» finnes allerede – velg annen slug.' % slug]

	title = (framework_meta.get('title') or '').strip()
	if not title:
		return None, ['Mangler tittel i filen.']

	with transaction.atomic():
		framework = RiskFramework.objects.create(
			slug=slug,
			title=title,
			beskrivelse=(framework_meta.get('beskrivelse') or '').strip(),
			is_active=True,
		)
		_apply_taxonomy(framework, taxonomy)
	return framework, []
