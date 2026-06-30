# -*- coding: utf-8 -*-
# Change log:
# 2026-06-30: RiskScenario.konsekvenstyper – multi-select consequence dimension tags.
# 2026-06-30: RiskAction default status forslag for new manual tiltak.
# 2026-06-30: RiskAction status forslag + besluttet (replaces ikke_startet) – proposal vs committed workflow.
# 2026-06-30: RiskScopeMember + virksomhet on RiskScope – multiple owners/participants replace single eier.
# 2026-06-26: Drop RiskScenario.eksisterende_tiltak – eksisterende tiltak are RiskAction rows (status utfort).
# 2026-06-24: RiskScope.beskrivelse – named collections with description on public list page.
# 2026-06-26: RiskAction scope-level with M2M scenarios – reuse tiltak across scenarios.
# 2026-06-24: RiskScope, RiskScenario, RiskAction – security risk module MVP.
# 2026-06-24: CA overview tile detail_url – path /rules/<pk>/ for single Azure policy.
# 2026-06-24: CA location filter chips – display name only, no IP range suffix.
# 2026-06-24: CA overview filters – Locations group for named and all-locations tags.
# 2026-06-24: CA app display names – strip leading «OK - » prefix on overview tags.
# 2026-06-24: CA overview filters – risk group, excluded conditions in filter_tags; clickable tile tags.
# 2026-06-24: CA overview – flexible rule title split (ID + gray suffix); grant labels as filter dicts.
# 2026-06-24: CA overview – user tags collapsed to count; Breakglass singled out; All users/locations use entity kinds.
# 2026-06-23: CA overview roles – count tags only (no directory role lookup).
# 2026-06-23: CA overview conditions – included/excluded tags with GUID lookup like rules report.
# 2026-06-23: CA overview – app tags for filtering; include/exclude roles counted only.
# 2026-06-23: CA overview tiles – filter tags, exclude counts, skip termsOfUse policies.
# 2026-06-23: conditional_access_build_overview_tiles – tile summaries for CA overview.
# 2026-06-23: CA named locations – show IP ranges on rules report; exact displayName match; skip countries.
# 2026-06-23: BloodHoundFinding + snapshot analysis fields for preventive checks.
# 2026-06-23: BloodHoundSnapshot – metadata and object counts from bloodhound-python JSON uploads.
# 2026-06-23: Batch GUID lookup for Conditional Access – fixes N+1 queries on CA changes report.
# 2026-06-23: Removed cache_systemprioritet – priority is computed on demand only.
# 2026-06-23: systemprioritet_poeng() – numeric score for sorting.
# 2026-06-23: Virksomhet.intern_tjenesteleverandor – replaces hardcoded DIG virksomhet id in prioriteringer links.
# 2026-06-23: systemprioritet() – use service_offerings.exists() so systems without CMDB link get T2/D2 defaults.
# 2026-06-23: Tjeneste/systemoversikt API – update api_tjeneste_systemoversikt_docs.py when model fields affect API JSON (url name: api_tjeneste_systemoversikt_docs).
# 2026-06-22: drift_dimensjoner(), driftes_av_dig (DIG forkortelse), home drift chart support.
# 2026-06-22: Driftsmodell.er_saas and System.er_egenutviklet – explicit SaaS and self-developed flags.
# 2026-06-21: Removed commented IpProtocol model – never used in production.
# 2026-06-21: Profile.virksomhet_forkortelse – replaces virksomhet_til_bruker view helper.
# 2026-06-21: chart_service_component, chart_external_system – tjeneste ecosystem graph palette.
# 2026-06-21: Removed PRKvalg, PRKgruppe, PRKskjema – PRK form import retired; AD groups hold access metadata.
# 2026-06-21: Removed UBW module models/forms – feature retired, URLs already disabled.
# 2026-06-21: Removed ProgramvareBruk.programvareleverandor – supplier belongs on Programvare only.
# 2026-06-21: Removed BehandlingerPersonopplysninger, DPIA, and related lookup models – migrated to Behandlingsoversikten.
# 2026-06-21: Softer chart palette; component uses muted lavender instead of cyan.
# 2026-06-21: SystemGraphLayout model – per-system dependency chart layout persistence.
# 2026-06-22: Leverandor.land blank=False, null=True – required in forms, no Ukjent choice; NULL kept in DB.
# 2026-06-22: Removed obsolete Driftsmodell security/location fields and Region model – unused in production.
# 2026-06-22: chart_programvare – dark black leaf nodes in system/tjeneste dependency graphs.
# 2026-06-21: chart_url, chart_cmdb_bss, chart_cmdb_bs colors for system dependency graph.
# 2026-06-08: User-facing UKE labels on Virksomhet/System fields renamed to DIG.
# 2026-06-08: VirksomhetRollerForm – edit sentrale roller from virksomhet detail page.
# 2026-06-08: Swapped ukjent (light red) and infrastruktur_chart (light gray) in SYSTEM_COLORS.
# 2026-06-08: Added infrastruktur_chart color for combined seksjon chart legend.
# 2026-06-07: Added land field to Leverandor – country of operation for supplier overview.
from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from simple_history.models import HistoricalRecords
from django import forms
import json
import re
from django.db.models import Sum
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry
from django.utils import timezone
from datetime import timedelta
import ast
from django.db.models import Q
from django.utils.timezone import now


# Endre __str__ for User-klassen. User er innebygget i Django. User viser som standard bare "self.username". Vi ønsker å vise fult navn.
def new_display_name(self):
	if self.profile.displayName:
		return(self.profile.displayName + " (" + self.username + ")")
	else:
		return(self.first_name + " " + self.last_name + " (" + self.username + ")")
User.add_to_class("__str__", new_display_name)



class RequestLogs(models.Model):
	path = models.CharField(max_length=500)
	method = models.CharField(max_length=10)
	user = models.CharField(max_length=150, null=True, blank=True)
	status_code = models.IntegerField()
	duration_ms = models.FloatField()
	sql_queries = models.IntegerField(default=0)
	sql_time_ms = models.FloatField(default=0)
	source_ip = models.CharField(max_length=45, null=True, blank=True)  # IPv4/IPv6
	timestamp = models.DateTimeField(default=now)

	def __str__(self):
		return f"{self.method} {self.path} - {self.duration_ms} ms ({self.sql_queries} queries)"

	class Meta:
		verbose_name_plural = "System: Page load statistics"



_CONDITIONAL_ACCESS_GUID_PATTERN = re.compile(
	r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'
)


def conditional_access_guids_in_text(data):
	if not data:
		return ()
	return _CONDITIONAL_ACCESS_GUID_PATTERN.findall(str(data))


def azure_named_location_ca_label(nl):
	"""CA report label: display name plus IP ranges when cached (not countries/regions)."""
	name = nl.displayName or nl.ipNamedLocation_id
	if not nl.ipRanges:
		return name
	try:
		ranges = json.loads(nl.ipRanges)
	except (TypeError, ValueError):
		return name
	if not ranges:
		return name
	return '%s (%s)' % (name, ', '.join(str(r) for r in ranges))


def azure_named_location_display_name_cache():
	"""Map exact displayName to CA label for includeLocations/excludeLocations enrichment."""
	cache = {}
	for nl in AzureNamedLocations.objects.exclude(displayName__isnull=True).exclude(displayName=''):
		cache[nl.displayName] = azure_named_location_ca_label(nl)
	return cache


def conditional_access_enrich_policy_locations(policy_data, display_name_cache=None):
	"""Enrich includeLocations/excludeLocations with IP ranges via exact displayName match."""
	if display_name_cache is None:
		display_name_cache = azure_named_location_display_name_cache()

	def enrich_list(items):
		if not isinstance(items, list):
			return items
		return [display_name_cache.get(item, item) for item in items]

	policies = policy_data.get('value')
	if not isinstance(policies, list):
		return policy_data

	for policy in policies:
		conditions = policy.get('conditions') or {}
		locations = conditions.get('locations') or {}
		if 'includeLocations' in locations:
			locations['includeLocations'] = enrich_list(locations['includeLocations'])
		if 'excludeLocations' in locations:
			locations['excludeLocations'] = enrich_list(locations['excludeLocations'])

	return policy_data


def conditional_access_guid_lookup_cache(guids):
	"""Map Azure object GUIDs to display strings using batched DB lookups."""
	guids = {g for g in guids if g}
	if not guids:
		return {}

	cache = {}
	for obj in AzureApplication.objects.filter(appId__in=guids):
		cache[obj.appId] = str(obj)

	remaining = guids.difference(cache)
	if remaining:
		for obj in AzureNamedLocations.objects.filter(ipNamedLocation_id__in=remaining):
			cache[obj.ipNamedLocation_id] = azure_named_location_ca_label(obj)

	remaining = guids.difference(cache)
	if remaining:
		for obj in AzureUser.objects.filter(guid__in=remaining):
			cache[obj.guid] = str(obj)

	remaining = guids.difference(cache)
	if remaining:
		for obj in AzureGroup.objects.filter(guid__in=remaining):
			cache[obj.guid] = str(obj)

	remaining = guids.difference(cache)
	if remaining:
		for obj in AzureDirectoryRole.objects.filter(guid__in=remaining):
			cache[obj.guid] = str(obj)

	return cache


def conditional_access_replace_guid(data, guid_lookup=None):
	def lookup_azure_id(azure_id):
		if guid_lookup is not None:
			return guid_lookup.get(azure_id, azure_id)
		try:
			return AzureApplication.objects.get(appId=azure_id).__str__()
		except AzureApplication.DoesNotExist:
			pass
		try:
			return azure_named_location_ca_label(
				AzureNamedLocations.objects.get(ipNamedLocation_id=azure_id)
			)
		except AzureNamedLocations.DoesNotExist:
			pass
		try:
			return AzureUser.objects.get(guid=azure_id).__str__()
		except AzureUser.DoesNotExist:
			pass
		try:
			return AzureGroup.objects.get(guid=azure_id).__str__()
		except AzureGroup.DoesNotExist:
			pass
		try:
			return AzureDirectoryRole.objects.get(guid=azure_id).__str__()
		except AzureDirectoryRole.DoesNotExist:
			pass
		return azure_id

	def replace_id(match):
		azure_id = match.group(0)
		return lookup_azure_id(azure_id)

	# Replace all IDs in the data
	data = _CONDITIONAL_ACCESS_GUID_PATTERN.sub(replace_id, data)
	return data


_CA_GRANT_LABELS = {
	'block': 'Block',
	'mfa': 'MFA',
	'compliantDevice': 'Compliant',
	'domainJoinedDevice': 'Domain joined',
	'approvedApplication': 'Approved app',
	'compliantApplication': 'Compliant app',
	'passwordChange': 'Password change',
	'unknownFutureValue': 'Unknown',
}

_CA_GRANT_FILTER_TAGS = {
	'mfa': 'mfa',
	'compliantDevice': 'compliant',
	'domainJoinedDevice': 'domain-joined',
}

_CA_APP_LITERAL_LABELS = {
	'Office365': 'Office 365',
}

# Leading «OK - » on enterprise app display names (stripped on CA overview tags).
_CA_APP_DISPLAY_PREFIX_RE = re.compile(r'^OK\s*-\s+', re.IGNORECASE)


def _ca_normalize_app_display_name(name):
	if not name:
		return name
	stripped = _CA_APP_DISPLAY_PREFIX_RE.sub('', str(name), count=1).strip()
	return stripped or name


def _ca_location_filter_label(text):
	"""Filter chip label for a named location – name only, without appended IP ranges."""
	if not text or text == 'All locations':
		return text
	if ' (' in text and text.endswith(')'):
		name = text.rsplit(' (', 1)[0].strip()
		return name or text
	return text

_CA_PLATFORM_LABELS = {
	'android': 'Android',
	'androidForWork': 'Android for work',
	'iOS': 'iOS',
	'macOS': 'macOS',
	'windows': 'Windows',
	'windowsPhone': 'Windows Phone',
	'linux': 'Linux',
	'all': 'All platforms',
}

_CA_CLIENT_APP_LABELS = {
	'all': 'All client apps',
	'browser': 'Browser',
	'mobileAppsAndDesktopClients': 'Mobile & desktop',
	'exchangeActiveSync': 'Exchange ActiveSync',
	'other': 'Other',
}

_CA_FILTER_GROUPS = (
	('grant_mode', 'Grant'),
	('grant_control', 'Grant controls'),
	('scope', 'Scope'),
	('groups', 'Groups'),
	('apps', 'Apps'),
	('locations', 'Locations'),
	('platform', 'Platforms'),
	('client', 'Client apps'),
	('risk', 'Risk'),
)

# Splits «ID - description» rule names; accepts hyphen, en-dash and em-dash with surrounding spaces.
_CA_RULE_NAME_SPLIT_RE = re.compile(r'\s+[-–—]\s+')

_CA_CLOUD_APP_SECURITY_LABELS = {
	'blockDownloads': 'Block downloads',
	'mcasConfigured': 'Defender for Cloud Apps',
	'monitorOnly': 'Monitor only',
}


def conditional_access_is_terms_of_use_policy(policy):
	grant_controls = policy.get('grantControls') or {}
	return bool(grant_controls.get('termsOfUse'))


def conditional_access_split_rule_display_name(display_name):
	"""Split a CA rule display name into ID (before dash) and descriptive suffix."""
	if not display_name:
		return 'Unnamed rule', ''
	display_name = display_name.strip()
	parts = _CA_RULE_NAME_SPLIT_RE.split(display_name, maxsplit=1)
	if len(parts) == 1:
		return parts[0], ''
	return parts[0].strip(), parts[1].strip()


def conditional_access_rule_short_name(display_name):
	short_name, _suffix = conditional_access_split_rule_display_name(display_name)
	return short_name


def conditional_access_rule_title_suffix(display_name):
	"""Text after the rule ID separator (shown in smaller gray on overview tiles)."""
	_short_name, suffix = conditional_access_split_rule_display_name(display_name)
	return suffix


def _ca_overview_grant_label(text, filter_tag=None, kind='grant'):
	return {
		'text': text,
		'filter': filter_tag,
		'kind': kind,
	}


def _ca_prepare_overview_label(label):
	label = dict(label)
	tag = label.get('filter')
	if tag:
		group = _ca_filter_group_for_tag(tag)
		if group:
			label['filter_group'] = group
	return label


def _ca_prepare_overview_labels(labels):
	return [_ca_prepare_overview_label(label) for label in (labels or [])]


def conditional_access_summarize_grant(grant_controls):
	empty = {
		'mode': 'unknown',
		'summary': 'No grant',
		'operator': None,
		'labels': [],
		'filter_tags': [],
	}
	if not grant_controls:
		return empty

	controls = [
		c for c in (grant_controls.get('builtInControls') or [])
		if c and c != 'unknownFutureValue'
	]
	operator = (grant_controls.get('operator') or 'AND').upper()

	if 'block' in controls:
		return {
			'mode': 'block',
			'summary': 'Block',
			'operator': None,
			'labels': [_ca_overview_grant_label('Block', 'block', 'grant-block')],
			'filter_tags': ['block'],
		}

	grant_labels = [_ca_overview_grant_label('Allow', 'allow', 'grant')]
	for control in controls:
		text = _CA_GRANT_LABELS.get(control, control)
		tag = _CA_GRANT_FILTER_TAGS.get(control)
		grant_labels.append(_ca_overview_grant_label(text, tag, 'grant'))
	filter_tags = ['allow']
	for control in controls:
		tag = _CA_GRANT_FILTER_TAGS.get(control)
		if tag:
			filter_tags.append(tag)

	auth_strength = grant_controls.get('authenticationStrength') or {}
	strength_name = auth_strength.get('displayName')
	if strength_name:
		grant_labels.append(_ca_overview_grant_label(strength_name, None, 'grant'))

	if len(grant_labels) == 1:
		return {
			'mode': 'allow',
			'summary': 'Allow',
			'operator': operator,
			'labels': grant_labels,
			'filter_tags': filter_tags,
		}

	label_texts = [label['text'] for label in grant_labels[1:]]
	joined = (' %s ' % operator).join(label_texts)
	return {
		'mode': 'allow',
		'summary': joined,
		'operator': operator,
		'labels': grant_labels,
		'filter_tags': filter_tags,
	}


def conditional_access_summarize_session(session_controls):
	if not session_controls:
		return []

	lines = []
	aer = session_controls.get('applicationEnforcedRestrictions') or {}
	if aer.get('isEnabled'):
		lines.append('App enforced restrictions')

	cas = session_controls.get('cloudAppSecurity') or {}
	if cas.get('isEnabled'):
		ctype = cas.get('cloudAppSecurityType') or 'configured'
		lines.append(_CA_CLOUD_APP_SECURITY_LABELS.get(ctype, ctype))

	pb = session_controls.get('persistentBrowser') or {}
	if pb.get('isEnabled'):
		mode = pb.get('mode') or 'never'
		lines.append('Persistent browser: %s' % mode)

	sif = session_controls.get('signInFrequency') or {}
	if sif.get('isEnabled'):
		value = sif.get('value')
		period = sif.get('type') or 'hours'
		if value is not None:
			lines.append('Sign-in frequency: every %s %s' % (value, period))
		else:
			lines.append('Sign-in frequency')

	if session_controls.get('disableResilienceDefaults'):
		lines.append('Disable resilience defaults')

	return lines


def _ca_app_display_name(app_id, guid_lookup, enriched_name=None):
	if enriched_name is not None:
		name = enriched_name
	elif app_id in _CA_APP_LITERAL_LABELS:
		name = _CA_APP_LITERAL_LABELS[app_id]
	else:
		name = guid_lookup.get(app_id, app_id)
	return _ca_normalize_app_display_name(name)


def _ca_display_at(items_raw, items_enriched, index, guid_lookup):
	if items_enriched is not None and index < len(items_enriched):
		return items_enriched[index]
	raw = items_raw[index]
	return guid_lookup.get(raw, raw)


def _ca_append_entity_tags(target, items_raw, items_enriched, tag_prefix, kind, guid_lookup):
	for index, raw in enumerate(items_raw or []):
		if not raw:
			continue
		text = _ca_display_at(items_raw, items_enriched, index, guid_lookup)
		if kind == 'app':
			text = _ca_normalize_app_display_name(text)
		target.append({
			'text': text,
			'filter': '%s:%s' % (tag_prefix, raw),
			'kind': kind,
		})


def _ca_user_display_is_breakglass(display_name):
	return 'breakglass' in (display_name or '').lower()


def _ca_append_user_tags(target, items_raw, items_enriched, guid_lookup):
	"""Overview tags for users: Breakglass by name, others as a single count tag."""
	entries = []
	for index, raw in enumerate(items_raw or []):
		if not raw:
			continue
		text = _ca_display_at(items_raw, items_enriched, index, guid_lookup)
		entries.append((raw, text))

	breakglass_entries = [entry for entry in entries if _ca_user_display_is_breakglass(entry[1])]
	other_entries = [entry for entry in entries if not _ca_user_display_is_breakglass(entry[1])]

	if breakglass_entries:
		target.append({
			'text': 'Breakglass',
			'filter': 'user:%s' % breakglass_entries[0][0],
			'kind': 'user',
		})

	if other_entries:
		count = len(other_entries)
		word = 'user' if count == 1 else 'users'
		target.append({
			'text': '%d %s' % (count, word),
			'filter': None,
			'kind': 'user',
		})


def _ca_append_role_count_tag(target, roles):
	count = len([role for role in (roles or []) if role])
	if not count:
		return
	word = 'role' if count == 1 else 'roles'
	target.append({
		'text': '%d %s' % (count, word),
		'filter': None,
		'kind': 'role',
	})


def conditional_access_tile_conditions(enriched_conditions, raw_conditions=None, guid_lookup=None):
	"""Included/excluded condition tags; display names from enriched JSON (same as rules report)."""
	guid_lookup = guid_lookup or {}
	raw = raw_conditions if raw_conditions is not None else (enriched_conditions or {})
	enriched = enriched_conditions or {}

	included_labels = []
	excluded_labels = []
	filter_tags = []

	users_raw = raw.get('users') or {}
	users_enriched = enriched.get('users') or {}

	if 'All' in (users_raw.get('includeUsers') or []):
		included_labels.append({'text': 'All users', 'filter': 'all-users', 'kind': 'user'})
		filter_tags.append('all-users')
	else:
		_ca_append_user_tags(
			included_labels,
			users_raw.get('includeUsers'),
			users_enriched.get('includeUsers'),
			guid_lookup,
		)

	_ca_append_entity_tags(
		included_labels,
		users_raw.get('includeGroups'),
		users_enriched.get('includeGroups'),
		'group', 'group', guid_lookup,
	)
	_ca_append_role_count_tag(included_labels, users_raw.get('includeRoles'))

	_ca_append_user_tags(
		excluded_labels,
		users_raw.get('excludeUsers'),
		users_enriched.get('excludeUsers'),
		guid_lookup,
	)
	_ca_append_entity_tags(
		excluded_labels,
		users_raw.get('excludeGroups'),
		users_enriched.get('excludeGroups'),
		'group', 'group', guid_lookup,
	)
	_ca_append_role_count_tag(excluded_labels, users_raw.get('excludeRoles'))

	applications_raw = raw.get('applications') or {}
	applications_enriched = enriched.get('applications') or {}
	include_apps_raw = applications_raw.get('includeApplications') or []
	include_apps_enriched = applications_enriched.get('includeApplications') or []

	if 'All' in include_apps_raw:
		included_labels.append({'text': 'All apps', 'filter': 'all-apps', 'kind': 'app'})
		filter_tags.append('all-apps')
	for index, app_id in enumerate(include_apps_raw):
		if not app_id or app_id == 'All':
			continue
		text = _ca_app_display_name(
			app_id,
			guid_lookup,
			enriched_name=_ca_display_at(include_apps_raw, include_apps_enriched, index, guid_lookup),
		)
		included_labels.append({
			'text': text,
			'filter': 'app:%s' % app_id,
			'kind': 'app',
		})

	_ca_append_entity_tags(
		excluded_labels,
		applications_raw.get('excludeApplications'),
		applications_enriched.get('excludeApplications'),
		'app', 'app', guid_lookup,
	)

	for index, action in enumerate(applications_raw.get('includeUserActions') or []):
		if not action:
			continue
		text = _ca_display_at(
			applications_raw.get('includeUserActions'),
			applications_enriched.get('includeUserActions'),
			index,
			guid_lookup,
		)
		included_labels.append({
			'text': text,
			'filter': 'action:%s' % action,
			'kind': 'action',
		})

	locations_raw = raw.get('locations') or {}
	locations_enriched = enriched.get('locations') or {}
	if 'All' in (locations_raw.get('includeLocations') or []):
		included_labels.append({'text': 'All locations', 'filter': 'all-locations', 'kind': 'location'})
		filter_tags.append('all-locations')
	else:
		_ca_append_entity_tags(
			included_labels,
			locations_raw.get('includeLocations'),
			locations_enriched.get('includeLocations'),
			'location', 'location', guid_lookup,
		)

	_ca_append_entity_tags(
		excluded_labels,
		locations_raw.get('excludeLocations'),
		locations_enriched.get('excludeLocations'),
		'location', 'location', guid_lookup,
	)

	platforms_raw = raw.get('platforms') or {}
	platforms_enriched = enriched.get('platforms') or {}
	for platform in platforms_raw.get('includePlatforms') or []:
		text = _CA_PLATFORM_LABELS.get(platform, platform)
		tag = 'platform:%s' % platform
		included_labels.append({'text': text, 'filter': tag, 'kind': 'platform'})
		filter_tags.append(tag)

	for platform in platforms_raw.get('excludePlatforms') or []:
		text = _CA_PLATFORM_LABELS.get(platform, platform)
		excluded_labels.append({
			'text': text,
			'filter': 'platform:%s' % platform,
			'kind': 'platform',
		})

	for client_type in raw.get('clientAppTypes') or []:
		text = _CA_CLIENT_APP_LABELS.get(client_type, client_type)
		tag = 'client:%s' % client_type
		included_labels.append({'text': text, 'filter': tag, 'kind': 'client'})
		filter_tags.append(tag)

	for level in raw.get('signInRiskLevels') or []:
		included_labels.append({'text': 'Sign-in risk: %s' % level, 'filter': 'signin-risk:%s' % level, 'kind': 'risk'})

	for level in raw.get('userRiskLevels') or []:
		included_labels.append({'text': 'User risk: %s' % level, 'filter': 'user-risk:%s' % level, 'kind': 'risk'})

	devices_raw = raw.get('devices') or {}
	devices_enriched = enriched.get('devices') or {}
	_ca_append_entity_tags(
		included_labels,
		devices_raw.get('includeDevices'),
		devices_enriched.get('includeDevices'),
		'device', 'device', guid_lookup,
	)
	_ca_append_entity_tags(
		excluded_labels,
		devices_raw.get('excludeDevices'),
		devices_enriched.get('excludeDevices'),
		'device', 'device', guid_lookup,
	)

	device_filter = devices_raw.get('deviceFilter')
	if device_filter:
		included_labels.append({
			'text': 'Device filter',
			'filter': 'device-filter',
			'kind': 'device',
		})

	for label in included_labels:
		tag = label.get('filter')
		if tag and tag not in filter_tags and _ca_filter_group_for_tag(tag):
			filter_tags.append(tag)

	for label in excluded_labels:
		tag = label.get('filter')
		if tag and tag not in filter_tags and _ca_filter_group_for_tag(tag):
			filter_tags.append(tag)

	return {
		'included_labels': included_labels,
		'excluded_labels': excluded_labels,
		'filter_tags': filter_tags,
	}


def _ca_filter_group_for_tag(tag):
	if tag in ('block', 'allow'):
		return 'grant_mode'
	if tag in ('mfa', 'compliant', 'domain-joined'):
		return 'grant_control'
	if tag in ('all-users',):
		return 'scope'
	if tag in ('all-locations',) or tag.startswith('location:'):
		return 'locations'
	if tag == 'all-apps' or tag.startswith('app:'):
		return 'apps'
	if tag.startswith('group:'):
		return 'groups'
	if tag.startswith('platform:'):
		return 'platform'
	if tag.startswith('client:'):
		return 'client'
	if tag.startswith('signin-risk:') or tag.startswith('user-risk:'):
		return 'risk'
	return None


def conditional_access_collect_overview_filters(tiles):
	"""Build filter chip definitions from tile tags, grouped for the overview UI."""
	seen = {group_id: {} for group_id, _ in _CA_FILTER_GROUPS}
	static_filters = {
		'grant_mode': [
			('allow', 'Allow'),
			('block', 'Block'),
		],
		'grant_control': [
			('mfa', 'MFA'),
			('compliant', 'Compliant'),
			('domain-joined', 'Domain joined'),
		],
		'scope': [
			('all-users', 'All users'),
		],
		'apps': [
			('all-apps', 'All apps'),
		],
		'locations': [
			('all-locations', 'All locations'),
		],
	}
	for group_id, options in static_filters.items():
		for tag, label in options:
			seen[group_id][tag] = label

	for tile in tiles:
		for label in tile.get('conditions_included') or []:
			tag = label.get('filter')
			if not tag:
				continue
			group_id = _ca_filter_group_for_tag(tag)
			if group_id:
				label_text = label['text']
				if group_id == 'locations':
					label_text = _ca_location_filter_label(label_text)
				seen[group_id][tag] = label_text

	for tile in tiles:
		for label in tile.get('conditions_excluded') or []:
			tag = label.get('filter')
			if not tag:
				continue
			group_id = _ca_filter_group_for_tag(tag)
			if group_id:
				label_text = label['text']
				if group_id == 'locations':
					label_text = _ca_location_filter_label(label_text)
				seen[group_id][tag] = label_text

	for tile in tiles:
		for tag in tile.get('filter_tags') or []:
			group_id = _ca_filter_group_for_tag(tag)
			if not group_id:
				continue
			if tag in seen[group_id]:
				continue
			if group_id == 'platform':
				seen[group_id][tag] = tag.split(':', 1)[1]
			elif group_id == 'client':
				key = tag.split(':', 1)[1]
				seen[group_id][tag] = _CA_CLIENT_APP_LABELS.get(key, key)
			elif group_id == 'locations':
				seen[group_id][tag] = _ca_location_filter_label(tag.split(':', 1)[-1])
			else:
				seen[group_id][tag] = tag

	groups = []
	for group_id, title in _CA_FILTER_GROUPS:
		options = seen.get(group_id) or {}
		if not options:
			continue
		groups.append({
			'id': group_id,
			'title': title,
			'options': [
				{'tag': tag, 'label': label}
				for tag, label in sorted(options.items(), key=lambda item: item[1].lower())
			],
		})
	return groups


def conditional_access_build_overview_tiles(policies, guid_lookup=None, raw_policies_by_id=None):
	"""Build overview tile data for active CA policies (state == enabled, not terms of use)."""
	guid_lookup = guid_lookup or {}
	raw_policies_by_id = raw_policies_by_id or {}
	tiles = []
	if not isinstance(policies, list):
		return tiles

	for policy in policies:
		if policy.get('state') != 'enabled':
			continue
		if conditional_access_is_terms_of_use_policy(policy):
			continue

		policy_id = policy.get('id')
		if not policy_id:
			continue

		raw_policy = raw_policies_by_id.get(policy_id) or policy
		display_name = policy.get('displayName') or policy_id
		grant = conditional_access_summarize_grant(policy.get('grantControls'))
		grant['labels'] = _ca_prepare_overview_labels(grant.get('labels'))
		conditions = conditional_access_tile_conditions(
			policy.get('conditions'),
			raw_conditions=raw_policy.get('conditions'),
			guid_lookup=guid_lookup,
		)
		filter_tags = list(dict.fromkeys(
			(grant.get('filter_tags') or []) + (conditions.get('filter_tags') or [])
		))

		tiles.append({
			'id': policy_id,
			'short_name': conditional_access_rule_short_name(display_name),
			'title_suffix': conditional_access_rule_title_suffix(display_name),
			'full_name': display_name,
			'detail_url': reverse('rapport_conditional_access_rule', kwargs={'pk': policy_id}),
			'grant': grant,
			'session_lines': conditional_access_summarize_session(policy.get('sessionControls')),
			'conditions_included': _ca_prepare_overview_labels(conditions['included_labels']),
			'conditions_excluded': _ca_prepare_overview_labels(conditions['excluded_labels']),
			'filter_tags': filter_tags,
		})

	tiles.sort(key=lambda tile: tile['short_name'].lower())
	return tiles


class EpostMottakere(models.Model):
	epost = models.CharField(
			verbose_name="E-postadresse",
			blank=False,
			null=False,
			max_length=100,
		)
	utsending_id = models.CharField(
			verbose_name="Utsending ID",
			blank=False,
			null=False,
			max_length=30,
		)
	class Meta:
		verbose_name_plural = "System: E-postmottakere"
		default_permissions = ('add', 'change', 'delete', 'view')
		get_latest_by = 'timestamp'


# Entra ID Conditional Access-policyer hentet ned via Graph API
class EntraIDConditionalAccessPolicies(models.Model):
	timestamp = models.DateTimeField(
			verbose_name="Lastet inn",
			auto_now=True,
		)
	json_policy = models.TextField(
			verbose_name="Policy raw JSON",
			blank=False,
			null=False,
		)
	modification = models.BooleanField(
			verbose_name="Endret siden sist?",
			default=False,
		)
	changes = models.TextField(
			verbose_name="Endringer siden sist",
			blank=True,
			null=True,
		)

	def __str__(self):
		return f"CA policy {self.timestamp}"

	class Meta:
		verbose_name_plural = "Azure: Conditional Access policyer"
		default_permissions = ('add', 'change', 'delete', 'view')
		get_latest_by = 'timestamp'



	def changes_to_json(self, guid_lookup=None):
		import re
		policy = json.loads(self.json_policy)["value"]

		def ca_rule_name(number):
			return policy[number]["displayName"]

		try:
			data = json.dumps(ast.literal_eval(self.changes), indent=4)
			data = conditional_access_replace_guid(data, guid_lookup=guid_lookup)

			def replacer(match):
				number = int(match.group(1))
				return ca_rule_name(number)

			data = re.sub(r"root\['[^']+'\]\[(\d+)\]", replacer, data)
			return data
		except Exception as e:
			return {}



	def json_policy_as_json(self, guid_lookup=None, display_name_cache=None):
		data = self.json_policy
		data = conditional_access_replace_guid(data, guid_lookup=guid_lookup)
		policy_data = json.loads(data)
		return conditional_access_enrich_policy_locations(
			policy_data,
			display_name_cache=display_name_cache,
		)


def global_azureid_lookup(value):
	# Regular expression to match the Azure ID format
	id_pattern = re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b')
	# Function to replace each ID with the lookup result
	def replace_id(match):
		azure_id = match.group(0)
		return lookup_azure_id(azure_id)
	# Replace all IDs in the value
	return id_pattern.sub(replace_id, value)


# Importering av Citrix-publikasjoner som knyttes til systemer.
class CitrixPublication(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
		)
	sone = models.CharField(
			verbose_name="sone",
			blank=False,
			null=False,
			max_length=10,
		)
	publikasjon_json = models.TextField(
			verbose_name="Publikasjon JSON",
			blank=False,
			null=False,
		)
	application_name = models.CharField(
			verbose_name="Application Name",
			blank=False,
			null=False,
			max_length=999,
		)
	publikasjon_UUID = models.CharField(
			verbose_name="Publikasjon UUID",
			blank=False,
			null=False,
			unique=True,
			max_length=40,
		)
	display_name = models.CharField(
			verbose_name="Visningsnavn",
			blank=True,
			null=True,
			max_length=500,
		)
	publikasjon_active = models.BooleanField(
			verbose_name="Aktiv",
			default=True,
		)
	cache_antall_publisert_til = models.BigIntegerField(
			verbose_name="Antall publisert til (cache)",
			null=True,
		)
	type_vApp = models.BooleanField(
			verbose_name="Er en vApp",
			default=False,
		)
	type_nettleser = models.BooleanField(
			verbose_name="Via nettleser",
			default=False,
		)
	type_remotedesktop = models.BooleanField(
			verbose_name="Er remote desktop",
			default=False,
		)
	type_produksjon = models.BooleanField(
			verbose_name="For produksjon",
			default=True,
		)
	type_medlemmer = models.BooleanField(
			verbose_name="Er publisert",
			default=True,
		)
	type_nhn = models.BooleanField(
			verbose_name="Norsk Helsenett-side",
			default=False,
		)
	type_executable = models.BooleanField(
			verbose_name="Executable file?",
			default=False,
		)
	type_vbs = models.BooleanField(
			verbose_name="VBS file?",
			default=False,
		)
	type_ps1 = models.BooleanField(
			verbose_name="PS1 file?",
			default=False,
		)
	type_bat = models.BooleanField(
			verbose_name="BAT file?",
			default=False,
		)
	type_cmd = models.BooleanField(
			verbose_name="BAT file?",
			default=False,
		)
	bruk_times_opened = models.BigIntegerField(
			verbose_name="Bruksdata: antall ganger åpnet",
			blank=True,
			null=True,
		)
	bruk_unique_users = models.BigIntegerField(
			verbose_name="Bruksdata: antall unike brukere",
			blank=True,
			null=True,
		)
	bruk_unique_departments = models.TextField(
			verbose_name="Bruksdata: unike virksomheter",
			blank=True,
			null=True,
		)

	def __str__(self):
		return f"{self.display_name} {self.sone}"

	class Meta:
		verbose_name_plural = "CMDB: Citrixpublikasjoner"
		default_permissions = ('add', 'change', 'delete', 'view')


# Informasjon som vises øverst på siden med gul bakgrunn. Viktig informasjon som kan skrus av og på via admin-grensesnittet.
class Fellesinformasjon(models.Model):
	message = models.TextField(
			verbose_name="message",
			blank=False,
			null=False,
			)
	aktiv = models.BooleanField(
			verbose_name="Aktiv",
			default=True,
			help_text=u"",
			)
	def __str__(self):
		return u'%s' % (self.message)

	class Meta:
		verbose_name_plural = "System: Fellesinformasjon"
		default_permissions = ('view')


# Logge endringer på brukere, basert på oppslag mot AD. Hovedsakelig aktivering og deaktivering av brukere
class UserChangeLog(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	event_type = models.CharField(
			verbose_name="event_type",
			max_length=30,
			blank=False,
			null=False,
			help_text=u"event_type",
			)
	message = models.TextField(
			verbose_name="message",
			blank=False,
			null=False,
			help_text=u"message",
			)
	def __str__(self):
		return u'%s %s' % (self.event_type, self.message)

	class Meta:
		verbose_name_plural = "System: Brukerendringer"
		default_permissions = ('add', 'change', 'delete', 'view')


# Informasjon om hva som er nytt i Kartoteket
class NyeFunksjoner(models.Model):
	tidspunkt = models.DateTimeField(
			verbose_name="Tidspunkt",
			null=False,
			blank=False,
			help_text=u"Kan dateres tilbake i tid.",
			)
	beskrivelse = models.TextField(
			verbose_name="Beskrivelse",
			blank=False,
			null=False,
			help_text=u"Hva får sluttbruker tilgang til å gjøre?",
			)
	reverse_url = models.CharField(
			verbose_name="URL-oppslagstekst",
			max_length=250,
			blank=True,
			null=True,
			help_text=u"URL-navnet som skal bli til en link.",
			)
	def __str__(self):
		return f'{self.beskrivelse}'

	class Meta:
		verbose_name_plural = "System: Nye funksjoner"
		default_permissions = ('add', 'change', 'delete', 'view')


# Oversikt over alle integrasjoner. Alle management-script oppdaterer sin respektive instans med sist kjørt og status.
class IntegrasjonKonfigurasjon(models.Model):
	kodeord = models.CharField(
		max_length=50,
		blank=False,
		null=False,
		unique=True,
	)
	kilde = models.CharField(
		max_length=100,
		blank=False,
		null=False,
	)
	protokoll = models.CharField(
		max_length=30,
		blank=False,
		null=False,
	)
	informasjon = models.CharField(
		max_length=250,
		blank=False,
		null=False,
	)
	sp_filnavn = models.CharField(
		verbose_name="Filnavn i SharePoint",
		max_length=500,
		blank=True,
		null=True,
		help_text=u"Kun relevant dersom hentet fra Kartotekets SharePoint-site.",
	)
	url = models.URLField(
		max_length=300,
		blank=True,
		null=True,
	)
	frekvensangivelse = models.CharField(
		max_length=300,
		blank=True,
		null=True,
	)
	dato_sist_oppdatert = models.DateTimeField(
		help_text=u"Settes automatisk basert på dato fra kilden. Dersom fra SharePoint, settes filens sist oppdaterte dato.",
		blank=True,
		null=True,
	)
	script_navn = models.CharField(
		max_length=400,
		blank=True,
		null=True,
		help_text=u"Settes automatisk når script kjører og oppdaterer sist oppdatert.",
	)
	log_event_type = models.CharField(
		max_length=300,
		blank=False,
		null=False,
	)
	sist_status = models.TextField(
		verbose_name="Sist status",
		blank=True,
		null=True,
	)
	runtime = models.BigIntegerField(
			verbose_name="Kjøretid",
			blank=True,
			null=True,
			)
	elementer = models.BigIntegerField(
			verbose_name="Elementer",
			blank=True,
			null=True,
			)
	helsestatus = models.TextField(
		verbose_name="Helsestatus",
		default="Vellykket",
		blank=True,
		null=False,
	)

	def __str__(self):
		return f'{self.kilde} {self.protokoll} {self.informasjon}'

	def color(self):
		if self.dato_sist_oppdatert:
			from datetime import datetime
			#from django.utils import timezone
			today = timezone.now()
			difference = today - self.dato_sist_oppdatert
			if difference < timedelta(days=1):
				return "#b8e1ca"
			if difference < timedelta(days=28):
				return "#e1cfa3"
		return "#cf949a"


	class Meta:
		verbose_name_plural = "System: Integrasjonskonfigurasjoner"
		default_permissions = ('add', 'change', 'delete', 'view')


# Holder API-nøkler utdelt for eksport av data
class APIKeys(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	key = models.CharField(
			verbose_name="Nøkkel / passord",
			max_length=256,
			blank=False,
			null=False,
			unique=False,
			)
	navn = models.CharField(
			verbose_name="Navn på nøkkel",
			blank=False,
			max_length=64,
			null=False,
			unique=True,
			)
	kommentar = models.TextField(
			verbose_name="Kommentar",
			blank=True,
			null=True,
			)
	def __str__(self):
		return u'%s (%s)' % (self.navn, self.kommentar)

	class Meta:
		verbose_name_plural = "System: API-nøkler"
		default_permissions = ('add', 'change', 'delete', 'view')



# Hovedlogg over hva Kartoteket gjør. Loggen over systemendringer er utenfor, og det er noen andre utsplittede logger.
class ApplicationLog(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	event_type = models.CharField(
			verbose_name="event_type",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"event_type",
			)
	message = models.TextField(
			verbose_name="message",
			blank=False,
			null=False,
			help_text=u"message",
			)
	def __str__(self):
		return u'%s %s %s' % (self.opprettet.strftime('%Y-%m-%d %H:%M:%S'), self.event_type, self.message)

	class Meta:
		verbose_name_plural = "System: Applikasjonslogger"
		default_permissions = ('add', 'change', 'delete', 'view')


# Hjelpeobjekt som mellomledd mellom User (brukere) og objekter som trenger å angi hvem som er ansvarlig. F.eks. System har systemforvalter --> ansvarlig --> user --> profile.
class Ansvarlig(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	brukernavn = models.OneToOneField(
			to=User,
			verbose_name="Personkobling",
			related_name="ansvarlig_brukernavn",
			on_delete=models.PROTECT,
			blank=False,
			null=False,
			help_text=u"Dette er personen roller er knyttet til. Endrer du denne, vil alle roller og ansvar flyttes over til personen du velger.",
			)
	kommentar = models.TextField(
			verbose_name="Kommentar (fases ut)",
			blank=True,
			null=True,
			help_text=u"Fritekst",
			)
	cache_seksjon = models.ForeignKey(
			to='HRorg',
			related_name='ansvarlig',
			verbose_name="Seksjon (cache)",
			blank=True,
			null=True,
			on_delete=models.SET_NULL,
			help_text=u"Seksjon ansvarlige sist ble sett knyttet til",
			)
	history = HistoricalRecords()


	def org_tilhorighet(self):
		try:
			enhet = self.brukernavn.profile.org_unit
			enhet_str = "%s" % (enhet)
			current_level = enhet.level
			while current_level > 3:  # level 2 er virksomheter, så vi ønsket et nivå ned (en verdi opp).
				mor_enhet = enhet.direkte_mor
				enhet_str = "%s - %s" % (mor_enhet, enhet_str)
				mor_level = mor_enhet.level
				if current_level > mor_level:
					enhet = mor_enhet
					current_level = mor_level
				else:
					break
			return enhet_str
		except:
			return "Ukjent tilhørighet"


	def __str__(self):
		if self.brukernavn:
			if self.brukernavn.profile.virksomhet:
				return u'%s %s (%s)' % (self.brukernavn.first_name, self.brukernavn.last_name, self.brukernavn.profile.virksomhet.virksomhetsforkortelse)
			else:
				return u'%s %s (%s)' % (self.brukernavn.first_name, self.brukernavn.last_name, "?")
		else:
			return u'%s (tastet inn)' % (self.navn)

	class Meta:
		verbose_name_plural = "Organisasjon: Ansvarlige"
		default_permissions = ('add', 'change', 'delete', 'view')


#hjelpeobjekt for å forvalte sertifikatbestillere.
class AutorisertBestiller(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	person = models.ForeignKey(
			to=Ansvarlig,
			related_name='autorisertbestiller_person',
			verbose_name="Autoriserte sertifikatbestillere",
			blank=True,
			on_delete=models.PROTECT,
			help_text=u"Personer i virksomheten som er autorisert til å bestille sertifikater via DIG. Det må da foreligge en fullmakt gitt til DIGs driftsleverandør.",
			)
	dato_fullmakt = models.DateField(
			verbose_name="Dato fullmakt gitt",
			blank=False,
			null=False,
			help_text=u"Dato fra fullmaktskjema.",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.person)

	class Meta:
		verbose_name_plural = "Organisasjon: Autoriserte sertifikatbestillere"
		default_permissions = ('add', 'change', 'delete', 'view')


# Valgmenyer brukt av virksomhet objektet
RESULTATENHET_VALG = (
	('OF', 'Felles IKT-plattform'),
	('Egen', 'Egen drift'),
)

OFFICE365_VALG = (
	(1, 'Felles tenant'),
	(2, 'Felles tenant med egen klientdrift'),
	(3, 'Egen tenant'),
)


### SENTRAL KLASSE ###
# 2026-06-23: Exposed via /api/virksomheter/ – update api_tjeneste_systemoversikt_docs.py when changing relevant API output (url name: api_tjeneste_systemoversikt_docs).
class Virksomhet(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	ordinar_virksomhet = models.BooleanField(
			verbose_name="Er dette en ordinær virksomhet?",
			default=True,
			help_text=u'Hvis du tar bort dette valget, vises ikke virksomheten i virksomhetsoversikten eller i dashboard. Brukes i forbindelse med import av driftsbrukere og i forbindelse med forvaltning av sertifikater.',
			)
	intern_tjenesteleverandor = models.BooleanField(
			verbose_name="Intern tjenesteleverandør",
			default=False,
			help_text=u'Krysses av for virksomheter som leverer interne IKT-tjenester (f.eks. DIG). Brukes bl.a. for hurtiglenker til systemprioriteringer.',
			)
	virksomhetsforkortelse = models.CharField(
			unique=True,
			verbose_name="Virksomhetsforkortelse",
			blank=True,
			null=True,
			max_length=10,
			db_index=True,
			help_text=u"Normalt en trebokstavsforkortelse. Forkortelsen brukes også for å koble brukeridenter fra AD automatisk til til din virksomhet.",
			)
	gamle_virksomhetsforkortelser = models.CharField(
			verbose_name="Alternative virksomhetsforkortelse",
			blank=True,
			null=True,
			max_length=100,
			help_text=u"Alternative/gamle virksomhetsforkortelser. Bruk mellomrom dersom flere. Brukes ved tildeling av WAN-lokasjoner og for filtrering av brukeridenter.",
			)
	virksomhetsnavn = models.CharField(
			unique=True,
			verbose_name="Virksomhetsnavn",
			max_length=250,
			help_text=u"Fult navnet på virksomheten",
			)
	overordnede_virksomheter = models.ManyToManyField(
			to="Virksomhet",
			related_name='underliggende_virksomheter',
			verbose_name="Tilhører byrådsavdeling",
			blank=True,
			help_text=u'Her angir du byråden din virksomhet er underlagt.',
			)
	kan_representeres = models.BooleanField(
			verbose_name="Kan representeres",
			default=False,
			help_text=u'Dersom huket av, kan din overordede byrådsavdeling logge inn på vegne av denne virksomheten.',
			)
	resultatenhet = models.CharField(
			choices=RESULTATENHET_VALG,
			verbose_name="Driftsmodell for klientflate",
			max_length=30,
			blank=True,
			null=True,
			default='',
			help_text=u"Dette feltet brukes for å angi om dere er på sentral klientplattform eller om dere har lokal drift av klienter.",
			)
	uke_kam_referanse = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_uke_kam',
			verbose_name='Kundeansvarlig fra intern tjenesteleverandør',
			blank=True,
			help_text=u"Dette er deres kundeansvarlig i DIG. Feltet bør oppdateres av DIG.",
			)
	intranett_url = models.URLField(
			verbose_name="På intranett (internt)",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Her oppgir du link til virksomhetens interne intranettside.",
			)
	www_url = models.URLField(
			verbose_name="Hjemmeområde web",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Her oppgir du link til virksomhetens hjemmeområde på de åpne nettsidene.",
			)
	ikt_kontakt = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_ikt_kontakt',
			verbose_name='IKT-hovedkontakter',
			blank=True,
			help_text=u"Din virksomhets kontaktpunkt for generelle IKT-relaterte henvendelser.",
			)
	autoriserte_bestillere_tjenester = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_autoriserte_bestillere_tjenester',
			verbose_name='Autoriserte bestillere i InfoTorg',
			blank=True,
			help_text=u"Autorisert bestiller med tilgang til InfoTorg som kan bestille tilgang til det sentrale folkeregistret for virksomheten.",
			)
	autoriserte_bestillere_tjenester_uke = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_autoriserte_bestillere_tjenester_uke',
			verbose_name='Autoriserte bestillere av tjenester fra intern tjenesteleverandør.',
			blank=True,
			help_text=u"Personer i virksomheten din autorisert til å bestille tjenester fra DIG.",
			)
	orgnummer = models.CharField(
			verbose_name="Virksomhetens organisasjonsnummer",
			max_length=30,
			blank=True,
			null=True,
			help_text=u"9 siffer uten mellomrom.",
			)
	autoriserte_bestillere_sertifikater = models.ManyToManyField(
			to=AutorisertBestiller,
			related_name='virksomhet_autoriserte_bestillere_sertifikater',
			verbose_name="Autoriserte sertifikatbestillere",
			blank=True,
			help_text=u"Personer som kan godkjenne utstedelse av nye websertifikater og virksomhetssertifikater.",
			)
	sertifikatfullmakt_avgitt_web = models.BooleanField(
			verbose_name="Avgitt sertifikatfullmakt til Buypass?",
			blank=True,
			null=True,
			default=False,
			help_text=u"Krysses av dersom virksomhet har avgitt fullmakt til driftsleverandør for å utstede digitale sertifikater for sitt org.nummer.",
			)
	rutine_tilgangskontroll = models.URLField(
			verbose_name="Rutiner for tilgangskontroll",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til dokument i virksomhetens styringssystem.",
			)
	rutine_behandling_personopplysninger = models.URLField(
			verbose_name="Rutiner for behandling av personopplysninger",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til dokument i virksomhetens styringssystem",
			)
	rutine_klage_behandling = models.URLField(
			verbose_name="Rutine for behandling av klage på behandling",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til dokument i virksomhetens styringssystem",
			)
	personvernkoordinator = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_personvernkoordinator',
			verbose_name='Personvernkoordinator (PKO)',
			blank=True,
			help_text=u"Person(er) i rollen som personvernkoordinator.",
			)
	informasjonssikkerhetskoordinator = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_informasjonssikkerhetskoordinator',
			verbose_name='Informasjonssikkerhetskoordinator (ISK)',
			blank=True,
			help_text=u"Person(er) i rollen som informasjonssikkerhetskoordinator.",
			)
	styringssystem = models.URLField(
			verbose_name="Styringssystem (URL)",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Her oppgir du link til virksomhetens styringssystem.",
			)
	arkitekturkontakter = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_arkitekturkontakter',
			verbose_name='Arkitekturkontakter',
			blank=True,
			help_text=u"Personer som jobber med overordnet arkitektur knyttet til virksomhetens ibruktakelse av IKT",
			)
	office365 = models.BigIntegerField(
		choices=OFFICE365_VALG,
			verbose_name="Modell for kontorstøtte",
			blank=True,
			null=True,
			default=1,
			help_text=u"Dette feltet brukes for å angi virksomhetens valg knyttet til office365",
			)
	ks_fiks_admin_ref = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_ks_fiks_ansvarlig',
			verbose_name='Administrator for søk i KS Fiks folkeregister portal',
			blank=True,
			help_text=u"Virksomhtens lokale administratorer på KS Fiks folkeregister (forvaltning.fiks.ks.no).",
			)
	varslingsmottak_sikkerhet_ref = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_varslingsmottak_sikkerhet',
			verbose_name='Postbokser for mottak av sikkerhetsvarsler',
			blank=True,
			help_text=u"Her kan du angi postmottaks dere ønsker sikkerhetsvarsler levert til. Brukes av DIG CSIRT og driftsleverandør for varslinger ved sikkerhetshendelser. Dersom ikke fylt ut, går varsler til ISK og sekundært til IKT-hovedkontakt.",
			)
	history = HistoricalRecords()

	def leder_hr(self):
		try:
			return HRorg.objects.filter(virksomhet_mor=self.pk).filter(level=3)[0].leder
		except:
			pass
		try:
			return HRorg.objects.filter(virksomhet_mor=self.pk).filter(level=2)[0].leder
		except:
			return None


	def antall_lokasjoner(self):
		return WANLokasjon.objects.filter(virksomhet=self).count()

	def antall_klienter(self):
		#from django.db.models import Q
		return CMDBdevice.objects.filter(client_virksomhet=self).count()

	def antall_brukeridenter(self):
		return Profile.objects.filter(virksomhet=self).count()

	def antall_interne_brukeridenter(self):
		return Profile.objects.filter(virksomhet=self.pk).filter(ekstern_ressurs=False).filter(accountdisable=False).count()

	def antall_eksterne_brukeridenter(self):
		return Profile.objects.filter(virksomhet=self.pk).filter(ekstern_ressurs=True).filter(accountdisable=False).count()


	def __str__(self):
		return u'%s (%s)' % (self.virksomhetsnavn, self.virksomhetsforkortelse)

	class Meta:
		verbose_name_plural = "Organisasjon: Virksomheter"
		default_permissions = ('add', 'change', 'delete', 'view')


class VirksomhetRollerForm(forms.ModelForm):
	# 2026-06-08: Scoped form for sentrale roller – same fields as VirksomhetAdmin "Organisatorisk" fieldset.
	class Meta:
		model = Virksomhet
		fields = (
			'arkitekturkontakter',
			'ikt_kontakt',
			'personvernkoordinator',
			'informasjonssikkerhetskoordinator',
			'varslingsmottak_sikkerhet_ref',
			'uke_kam_referanse',
			'autoriserte_bestillere_tjenester',
			'ks_fiks_admin_ref',
			'autoriserte_bestillere_tjenester_uke',
		)
		widgets = {
			field: forms.SelectMultiple(attrs={'class': 'form-control', 'size': '6'})
			for field in fields
		}


# hjelpeklasse for system_telle_koblede_brukere. Ved oppslag via AD/LDAP hentes det ut ansattnummer, og flere brukere kan kobles til samme nummer
class AnsattID(models.Model):
	ansattnr = models.BigIntegerField(
			db_index=True,
		)

	def __str__(self):
		return u'%s' % (self.ansattnr)

	class Meta:
		verbose_name_plural = "Organisasjon: Ansattnummer"
		default_permissions = ('add', 'change', 'delete', 'view')


LISENCE_VALG = (
	(0, 'Ingen'),
	(1, 'G1 E3 (Tykklient)'),
	(2, 'G2 F3 (Flerbruker)'),
	(3, 'G3 F1 (Ingen epost)'),
	(4, 'G4 A3 (Education)'),
)


# manuell liste over AD-grupper som anses som privilegerte
PRIVILEGERTE_GRUPPER_AD = [
	"Access Control Assistance Operators",
	"Account Operators",
	"Administrators",
	"Allowed RODC Password Replication",
	"Backup Operators",
	"Certificate Service DCOM Access",
	"Cert Publishers",
	"Cloneable Domain Controllers",
	"Cryptographic Operators",
	"Denied RODC Password Replication",
	"Device Owners",
	"DHCP Administrators",
	"DHCP Users",
	"Distributed COM Users",
	"DnsUpdateProxy",
	"DnsAdmins",
	"Domain Admins",
	"Domain Computers",
	"Domain Controllers",
	"Enterprise Admins",
	"Enterprise Key Admins",
	"Enterprise Read-only Domain Controllers",
	"Event Log Readers",
	"Group Policy Creator Owners",
	"Hyper-V Administrators",
	"IIS_IUSRS",
	"Incoming Forest Trust Builders",
	"Key Admins",
	"Network Configuration Operators",
	"Performance Log Users",
	"Performance Monitor Users",
	"Pre–Windows 2000 Compatible Access",
	"Print Operators",
	"Protected Users",
	"RAS and IAS Servers",
	"RDS Endpoint Servers",
	"RDS Management Servers",
	"RDS Remote Access Servers",
	"Read-only Domain Controllers",
	"Remote Desktop Users",
	"Remote Management Users",
	"Replicator",
	"Schema Admins",
	"Server Operators",
	"Storage Replica Administrators",
	"System Managed Accounts",
	"Terminal Server License Servers",
	"Windows Authorization Access",
	"WinRMRemoteWMIUsers_",
	# server admins
	"GS-OpsRole-ErgoGroup-AdminAlleMemberServere",
	"GS-OpsRole-Ergogroup-ServerAdmins",
	"Task-OF2-ServerAdmin-AllMemberServers",
	"Role-OF2-Admin-Citrix Services",
	"DS-MemberServer-Admin-AlleManagementServere",
	"DS-MemberServer-Admin-AlleManagementServere",
	"DS-DRIFT_DRIFTSPERSONELL_SERVERMGMT_SERVERADMIN",
	"Role-OF2-AdminAlleMemberServere",
	# domain admins
	"Role-Domain-Admins-UVA",
	"On-Prem Enterprise Admins",
	"On-Prem Domain Admins",
	"009378fe-ecdf-4f49-bd65-d82411703915",
	# PRK admins
	#"DS-GKAT_BRGR_SYSADM",
	#"DS-GKAT_ADMSENTRALESKJEMA_ALLE",
	#"DS-GKAT_ADMSENTRALESKJEMA_KOKS",
	#"DS-GKAT_IMPSKJEMA_TIGIMP",
	#"DS-GKAT_IMPSKJEMA_TSIMP",
	#"DS-GKAT_MODULER_GLOBAL_ADMINISTRASJON",
	#"DS-GKAT_DSGLOKALESKJEMA_ALLE",
	#"DS-GKAT_DSGLOKALESKJEMA_INFOCARE",
	#"DS-GKAT_DSGLOKALESKJEMA_OPPRETTE",
	#"DS-GKAT_DSGSENTRALESKJEMA_ALLE",
	#"DS-GKAT_DSGSENTRALESKJEMA_OPPRETTE",
	#"DS-GKAT_ADMLOKALESKJEMA_ALLE",
	#"DS-GKAT_ADMLOKALESKJEMA_APPLIKASJON",
	# IDA
	"DS-IDA_ALLE_SUPPORT",
	"DS-IDA_ALLE_FORVALTERE",
	"DS-IDA_ALLE_USS",
	"DS-IDA_ALLE_SERVICEDESK",
	# SQL admins
	"GS-UKE-MSSQL-DBA",
	"DS-OF2-SQL-SYSADMIN",
	"DS-DRIFT_DRIFTSPERSONELL_DATABASE_SQL",
	"GS-Role-MSSQL-DBA",
	"GS-UKE-MSSQL-DBA",
	"DS-Role-MSSQL-DBA",
	"DS-DRIFT_DRIFTSPERSONELL_DATABASE_ORACLE",
	"DS-OF2-TASK-SQLCluster",
	# Citrix admins
	"Task-OF2-Admin-Citrix XenApp",
	"DS-DRIFT_DRIFTSPERSONELL_REMOTE_CITRIXDIRECTOR",
	"DS-DRIFT_DRIFTSPERSONELL_CITRIX_APPV_ADMIN",
	"DS-DRIFT_DRIFTSPERSONELL_CITRIX_CITRIX_NETSCALER_ADM",
	"DS-DRIFT_DRIFTSPERSONELL_CITRIX_ADMINISTRATOR",
	"DS-DRIFT_DRIFTSPERSONELL_CITRIX_DRIFT",
	# annet
	"DS-DRIFT_DRIFTSPERSONELL_SERVERMGMT_ADMINDC",
	"DS-DRIFT_DRIFTSPERSONELL_MAIL_EXH_FULL_ADMINISTRATOR",
	"DS-DRIFT_DRIFTSPERSONELL_ACCESSMGMT_OVERGREPSMOTTAKET",
	"Steria Admin",
	"GS-SAM-SharepointAdmin_IS",
	"GS-NAE-EQUITRAC_ADMIN",
	"Task-OF2-EGE-JumpserverAdmin",
	"DS-DRIFT_DRIFTSPERSONELL_ACCESSMGMT_BRUKERADMIN",
	"DS-Computer-FullControl-AlleServerObjekter",
	"DS-Computer-FullControl-Steria-SektorSystemer-AlleServere",
	"DS-File-FullControl-SO",
	"DS-Groups-FullControl-AlleOKTilgangsgrupper",
	"DS-Groups-FullControl-ErgoGroup-Infrastruktur-AdmGrupper",
	"DS-Groups-FullControl-OK-AdmGrupper",
	"DS-Users-FullControl-InfoCare-MgmtUsers",
	"DS-Users-FullControl-Steria-MgmtUsers",
	"Task-OF2-ServerAdmin-InfoCare",
	"DRIFT_DML_DRIFTTILGANG_DRIFTTILGANGIS",
	"DRIFT_DML_DRIFTTILGANG_DRIFTTILGANGSS",
	"Task-OF2-EGE-JumpserverEkstern",
	"DS-DRIFT_DRIFTSPERSONELL_ACCESSMGMT_ADUSERSANDCOMPUTERS",
	"DRIFT_DML_STERIA_STERIA",
	"DS-DRIFT_DRIFTSPERSONELL_SERVERMGMT_RDP_ACCESS_ORIGO_PROFDOC",
	"Task-OF2-Admin-VDI Creation",
	"DRIFT_DRIFTSPERSONELL_ACCESSMGMT_MACHINEMGMT",
	"DRIFT_DRIFTSPERSONELL_ACCESSMGMT_GRPUPMGMT",
	"DRIFT_DRIFTSPERSONELL_SERVERMGMT_RDPALLESERVEREUKE",
	"DRIFT_DRIFTSPERSONELL_SERVERMGMT_INFOBLOX_RW",
	"DRIFT_DRIFTSPERSONELL_ACCESSMGMT_DOMADMAZUR",
	# Solid cloud
	"DS-DRIFT_SC2_"
]


# hjelpeklasse til innebygde User. For å lagre mer informasjon om bruker. Nås som user.profile
class Profile(models.Model):
	#https://simpleisbetterthancomplex.com/tutorial/2016/07/22/how-to-extend-django-user-model.html
	ad_sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert fra AD",
			null=True,
			blank=True,
			)
	user = models.OneToOneField(
			to=User,
			on_delete=models.CASCADE,  # slett profilen når brukeren slettes
			)
	distinguishedname = models.TextField(
			verbose_name="Distinguishedname (AD)",
			blank=True,
			null=True,
			db_index=True,
			)
	ou = models.ForeignKey(
			to="ADOrgUnit",
			related_name='profile_ou',
			on_delete=models.PROTECT,
			verbose_name="OU-parent",
			blank=True,
			null=True,
			)
	displayName = models.CharField(
			verbose_name="Visningsnavn (AD)",
			max_length=300,
			blank=True,
			null=True,
			)
	lastLogonTimestamp = models.DateTimeField(
			verbose_name="Sist innlogget (AD)",
			null=True,
			blank=True,
			)
	userPasswordExpiry = models.DateTimeField(
			verbose_name="Dato neste passordbytte",
			null=True,
			blank=True,
			)
	whenCreated = models.DateTimeField(
			verbose_name="Bruker opprettet",
			null=True,
			blank=True,
			)
	pwdLastSet = models.DateTimeField(
			verbose_name="Passord sist endret",
			null=True,
			blank=True,
			)
	virksomhet = models.ForeignKey(
			to=Virksomhet,
			related_name='brukers_virksomhet',
			on_delete=models.SET_NULL,
			verbose_name="Virksomhet / Etat: Representerer",
			blank=True,
			null=True,
			)
	virksomhet_innlogget_som = models.ForeignKey(
			to=Virksomhet,
			related_name='brukers_virksomhet_innlogget_som',
			on_delete=models.SET_NULL,
			verbose_name="Virksomhet / Etat: Innlogget som",
			blank=True,
			null=True,
			)
	from_prk = models.BooleanField(
			verbose_name="Fra HR-systemet?",
			default=False,
			)
	ekstern_ressurs = models.BooleanField(
			verbose_name="Ekstern ressurs? (AD)",
			null=True,
			blank=True,
			default=None,
			)
	usertype = models.CharField(
			verbose_name="Brukertype (HR)",
			max_length=20,
			null=True,
			blank=True,
			)
	account_type = models.CharField(
			verbose_name="Brukertype (AD)",
			max_length=30,
			null=True,
			blank=True,
			)
	description = models.TextField(
			verbose_name="Beskrivelse (AD)",
			blank=True,
			null=True,
			)
	userAccountControl = models.TextField(
			verbose_name="User Account Control (AD)",
			blank=True,
			null=True,
			)
	accountdisable = models.BooleanField(
			verbose_name="Account disable (AD)",
			default=False,
			help_text="Importeres fra AD",
			)
	lockout = models.BooleanField(
			verbose_name="Lockout (AD)",
			default=False,
			)
	passwd_notreqd = models.BooleanField(
			verbose_name="Passwd notreqd (AD)",
			default=False,
			)
	dont_expire_password = models.BooleanField(
			verbose_name="Dont expire password (AD)",
			default=False,
			)
	password_expired = models.BooleanField(
			verbose_name="Password expired (AD)",
			default=False,
			)
	org_unit = models.ForeignKey(
			to='HRorg',
			related_name='profile_org_unit',
			on_delete=models.SET_NULL,
			verbose_name='Organisatorisk tilhørighet (PRK)',
			null=True,
			blank=True,
			)
	ansattnr = models.BigIntegerField(
			verbose_name="Ansattnr (PRK)",
			blank=True,
			null=True,
			)
	ansattnr_ref = models.ForeignKey(
			to="AnsattID",
			related_name='userprofile',
			on_delete=models.SET_NULL,
			null=True,
			blank=True,
			)
	ansattnr_antall = models.BigIntegerField(
			verbose_name="Antall koblede kontoer",
			blank=True,
			null=True,
			)
	adgrupper = models.ManyToManyField(
			to="ADgroup",
			related_name='user',
			verbose_name="Medlemskap i grupper (AD)",
			blank=True,
			help_text=u'Settes via automatiske jobber',
			)
	adgrupper_antall = models.BigIntegerField(
			verbose_name="Antall gruppemedlemskap",
			blank=True,
			null=True,
			help_text=u'Settes via automatiske jobber',
			)
	trusted_for_delegation = models.BooleanField(
			verbose_name="trusted_for_delegation",
			blank=True,
			null=True,
			default=False,
			)
	trusted_to_auth_for_delegation = models.BooleanField(
			verbose_name="trusted_for_delegation",
			blank=True,
			null=True,
			default=False,
			)
	not_delegated = models.BooleanField(
			verbose_name="not_delegated",
			blank=True,
			null=True,
			)
	dont_req_preauth = models.BooleanField(
			verbose_name="dont_req_preauth",
			blank=True,
			null=True,
			)
	#o365lisence = models.BigIntegerField(
	#		choices=LISENCE_VALG,
	#		verbose_name="Lisenser Office365",
	#		blank=True,
	#		default=0,
	#		help_text=u'Settes automatisk',
	#		)
	service_principal_name = models.CharField(
		verbose_name="Service Principal Name (AD)",
		max_length=1024,
		blank=True,
		null=True,
		)
	object_sid = models.CharField(
		verbose_name="Object SID",
		max_length=128,
		blank=True,
		null=True,
		db_index=True,
		)
	ny365lisens = models.CharField(
		verbose_name="Office365-lisens",
		max_length=256,
		blank=True,
		null=True,
		db_index=True,
		)
	auth_methods = models.TextField(
		verbose_name="Autentiseringsmetoder (JSON)",
		blank=True,
		null=True,
		)
	auth_methods_last_update = models.DateTimeField(
		verbose_name="Autentiseringsmetode sist synkronisert",
		null=True,
		blank=True,
		)
	job_title = models.TextField(
		verbose_name="Jobbtittel",
		blank=True,
		null=True,
		)
	min_leder = models.ForeignKey(
		to=User,
		on_delete=models.SET_NULL,
		related_name='leder_for',
		verbose_name="Leder for",
		blank=True, null=True,
		help_text=u"Settes basert på automatikk",
		)
	mail_enabled_groups = models.ManyToManyField(
		to="ADgroup",
		related_name='user_profile',
		verbose_name="Medlemskap i mail enabled groups",
		blank=True,
		help_text=u'Settes via automatiske jobber',
		)
	# med vilje er det ikke HistoricalRecords() på denne

	def virksomhet_forkortelse(self):
		try:
			return self.virksomhet.virksomhetsforkortelse
		except:
			return False

	def __str__(self):
		return u'%s' % (self.user)

	class Meta:
		verbose_name_plural = "System: Brukerprofiler"

	@receiver(post_save, sender=User)
	def create_user_profile(sender, instance, created, **kwargs):
		if created:
			Profile.objects.create(user=instance)

	@receiver(post_save, sender=User)
	def save_user_profile(sender, instance, **kwargs):
		instance.profile.save()

	def entra_id_auth(self):
		if self.auth_methods == None:
			return []
		metoder = []
		if "voiceAuthenticationMethod" in self.auth_methods:
			metoder.append("Telefon voice")
		if "phoneAuthenticationMethod" in self.auth_methods:
			metoder.append("Telefon SMS")
		if "certificateBasedAuthentication" in self.auth_methods:
			metoder.append("Sertifikat")
		if "temporaryAccessPassAuthenticationMethod" in self.auth_methods:
			metoder.append("TAP")
		if "fido2AuthenticationMethod" in self.auth_methods:
			metoder.append("FIDO2")
		if "microsoftAuthenticatorAuthenticationMethod" in self.auth_methods:
			metoder.append("Authenticator")
		if "oathSoftwareTokenAuthenticationMethod" in self.auth_methods:
			metoder.append("OAuth software")
		if "oathHardwareTokenAuthenticationMethod" in self.auth_methods:
			metoder.append("OAuth hardware")
		return metoder

	def auth_sms(self):
		if self.auth_methods == None:
			return None
		return True if "phoneAuthenticationMethod" in self.auth_methods else False
	def auth_fido2(self):
		if self.auth_methods == None:
			return None
		return True if "fido2AuthenticationMethod" in self.auth_methods else False
	def auth_authenticator(self):
		if self.auth_methods == None:
			return None
		return True if "microsoftAuthenticatorAuthenticationMethod" in self.auth_methods else False


	def levtilgangprofil(self):
		alle_levprofiler = Leverandortilgang.objects.all()
		alle_grupper = self.adgrupper.all()
		systemer = list()

		for levprofile in alle_levprofiler:
			for adgrp in levprofile.adgrupper.all():
				if adgrp in alle_grupper:
					systemer.extend(levprofile.systemer.all())

		return [system.systemnavn for system in systemer]


	def kopiav(self):
		username = self.user.username.lower()
		if username.startswith("t-"):
			try:
				username = username.replace("t-","")
				return User.objects.get(username=username)
			except:
				pass
		if username.startswith("t_"):
			try:
				username = username.replace("t_","")
				return User.objects.get(username=username)
			except:
				pass
		if "_t" in username:
			try:
				username = username.split("_t")[0]
				return User.objects.get(username=username)
			except:
				pass
		return "Ukjent"

	def org_tilhorighet(self):
		try:
			enhet = self.org_unit
			enhet_str = "%s" % (enhet)
			current_level = enhet.level
			while current_level > 3:  # level 2 er virksomheter, så vi ønsket et nivå over
				mor_enhet = enhet.direkte_mor
				enhet_str = "%s - %s" % (mor_enhet, enhet_str)
				mor_level = mor_enhet.level
				if current_level > mor_level:
					enhet = mor_enhet
					current_level = mor_level
				else:
					break
			return enhet_str
		except:
			return "Ukjent tilhørighet"

	def avdeling(self):
		try:
			enhet = self.org_unit
			current_level = enhet.level
			while current_level > 3:  # level 2 er virksomheter, så vi ønsket et nivå over
				mor_enhet = enhet.direkte_mor
				mor_level = mor_enhet.level
				if current_level > mor_level:
					enhet = mor_enhet
					current_level = mor_level
				else:
					break
			return enhet
		except:
			return None

	def ou_lesbar(self):
		if self.distinguishedname != None:
			return self.distinguishedname.split(",")[1:-4]
		return ""


	def ad_grp_lookup(self):
		try:
			from systemoversikt.views import ldap_users_securitygroups, convert_distinguishedname_cn
			return sorted(convert_distinguishedname_cn(ldap_users_securitygroups(self.user.username)))
		except:
			return  ["AD ikke tilgjengelig"]

	def privilegert_bruker(self):
		for gruppe in self.adgrupper.all():
			if any(pg.lower() in gruppe.common_name.lower() for pg in PRIVILEGERTE_GRUPPER_AD):
				return "Ja"
		return "Nei"



LEVERANDOR_LAND_VALG = (
	('AU', 'Australia'),
	('BE', 'Belgia'),
	('BR', 'Brasil'),
	('CA', 'Canada'),
	('CN', 'Kina'),
	('CZ', 'Tsjekkia'),
	('DK', 'Danmark'),
	('EE', 'Estland'),
	('ES', 'Spania'),
	('FI', 'Finland'),
	('FR', 'Frankrike'),
	('GB', 'Storbritannia'),
	('DE', 'Tyskland'),
	('IN', 'India'),
	('IE', 'Irland'),
	('IS', 'Island'),
	('IL', 'Israel'),
	('JP', 'Japan'),
	('KR', 'Sør-Korea'),
	('NL', 'Nederland'),
	('NO', 'Norge'),
	('PL', 'Polen'),
	('PT', 'Portugal'),
	('RO', 'Romania'),
	('SE', 'Sverige'),
	('CH', 'Sveits'),
	('SG', 'Singapore'),
	('UA', 'Ukraina'),
	('US', 'USA'),
	('VN', 'Vietnam'),
)


### SENTRAL KLASSE ###
# 2026-06-23: Exposed via /api/leverandorer/ – update api_tjeneste_systemoversikt_docs.py when changing relevant API output (url name: api_tjeneste_systemoversikt_docs).
class Leverandor(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	leverandor_navn = models.CharField(
			unique=True,
			verbose_name="Leverandørens navn",
			max_length=350,
			help_text=u"",
			)
	kontaktpersoner = models.TextField(
			verbose_name="Adresse og kontaktpersoner",
			blank=True,
			null=True,
			help_text=u"",
			)
	orgnummer = models.CharField(
			verbose_name="Organisasjonsnummer",
			max_length=30,
			blank=True,
			null=True,
			help_text=u"",
			)
	land = models.CharField(
			verbose_name="Land",
			max_length=2,
			choices=LEVERANDOR_LAND_VALG,
			blank=False,
			null=True,
			help_text=u"Land leverandøren opererer fra",
			)
	notater = models.TextField(
			verbose_name="Notater",
			blank=True,
			null=True,
			help_text=u"",
			)
	godkjent_opptaks_sertifiseringsordning = models.TextField(
			verbose_name="Er leverandørene registrert på en godkjent opptaks- eller sertifiseringsordning? Beskriv hvilke.",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.leverandor_navn)

	class Meta:
		verbose_name_plural = "Organisasjon: Leverandører"
		default_permissions = ('add', 'change', 'delete', 'view')


# Dynamisk valgmeny benyttet for System-klassen. F.eks. A personopplysninger, B sikkerhetsgradert, D lagres i norge osv.
class InformasjonsKlasse(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.TextField(
			verbose_name="Navn på klasse",
			blank=True,
			null=True,
			help_text=u"",
			)
	beskrivelse = models.TextField(
			verbose_name="Beskrivelse av informasjonsklassen",
			blank=True,
			null=True,
			help_text=u"F.eks. henvisning til lover som gjelder",
			)

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Behandling: Informasjonsklasser"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['navn']



# Dynamisk valgmeny for å klassifisere systemer i kommune-spesifikke kategorier
class SystemKategori(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	kategorinavn = models.CharField(
			unique=True,
			verbose_name="Kategorinavn",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"",
			)
	hovedkategori = models.ForeignKey(
			to="SystemHovedKategori",
			related_name='systemkategori_hovedkategori',
			on_delete=models.PROTECT,
			verbose_name="Hovedkategori",
			null=True,
			blank=True,
			help_text=u'Velg en hovedkategori denne kategorien skal tilhøre.',
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"Slik at andre kan vurdere passende kategorier",
			)
	history = HistoricalRecords()

	def __str__(self):
		if len(self.systemhovedkategori_systemkategorier.all()) > 0:
			# hvis flere, tar vi den første. Det skal ikke være flere, men det er litt knotete å endre til foreignkey-relasjon
			return u'%s (%s)' % (self.kategorinavn, self.systemhovedkategori_systemkategorier.all()[0].hovedkategorinavn)
		else:
			return u'%s' % (self.kategorinavn)

	class Meta:
		verbose_name_plural = "Systemkategori: Systemkategorier"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['kategorinavn']


# Dynamisk valgmeny for å kategoriere SystemKategori-er
class SystemHovedKategori(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	hovedkategorinavn = models.CharField(
			unique=True,
			verbose_name="Kategorinavn",
			max_length=30,
			blank=False,
			null=False,
			help_text=u"",
			)
	definisjon = models.CharField(
			verbose_name="Definisjon",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Slik at andre kan vurdere passende kategorier",
			)
	subkategorier = models.ManyToManyField(
			to=SystemKategori,
			related_name='systemhovedkategori_systemkategorier',
			verbose_name="Subkategorier",
			blank=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.hovedkategorinavn)

	class Meta:
		verbose_name_plural = "Systemkategori: Systemhovedkategorier"
		verbose_name = "systemhovedkategori"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['hovedkategorinavn']


# menyvalg for SystemUrl
MAALGRUPPE_VALG = (
	(1, 'Innbyggere'),
	(2, 'Ansatte'),
	(3, 'Leverandører'),
)

SIKKERHETSTESTING_VALG = (
	(1, "1 Svært lite aktuelt"),
	(2, "2 Lite aktuelt"),
	(3, "3 Kan vurderes"),
	(4, "4 Aktuelt"),
	(5, "5 Meget aktuelt"),
)


# Støtteklasse for å registrere informasjon om en URL ut over selve adressen. Brukes inn mot System
class SystemUrl(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	domene = models.URLField(
			unique=True,
			verbose_name="Domene",
			max_length=600,
			blank=False,
			null=False,
			help_text=u"",
			)
	https = models.BooleanField(
			verbose_name="Sikret med https?",
			blank=True,
			null=True,
			default=None,
			help_text=u"",
			)
	maalgruppe = models.BigIntegerField(
			choices=MAALGRUPPE_VALG,
			verbose_name="Målgruppe",
			blank=True,
			null=True,
			help_text=u'Hvem kan bruke / nå tjenesten på denne URL-en?',
			)
	vurdering_sikkerhetstest = models.BigIntegerField(
			choices=SIKKERHETSTESTING_VALG,
			verbose_name="Vurdering sikkerhetstest",
			blank=True,
			null=True,
			help_text=u'Hvor aktuelt er det å sikkerhetsteste denne tjenesten?',
			)
	registrar = models.ForeignKey(
			to=Leverandor,
			related_name='systemurl_registrar',
			on_delete=models.PROTECT,
			verbose_name="Domeneregistrar",
			null=True,
			blank=True,
			help_text=u'Leverandør som domenet er registrert hos',
			)
	eier = models.ForeignKey(
			to=Virksomhet,
			on_delete=models.PROTECT,
			verbose_name="Eier av domenet",
			related_name='systemurl_eier',
			null=True,
			blank=True,
			help_text=u'Virksomheten som eier domenet',
			)
	kommentar = models.TextField(
			verbose_name="Kommentar (fritekst)",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.domene)

	def vis_registrar(self):
		if "oslo.kommune.no" in self.domene:
			return "Oslo kommune"
		return self.registrar

	def own_domain(self):
		# hardkodet her
		if "oslo.kommune.no" in self.domene:
			return True
		else:
			return False

	class Meta:
		verbose_name_plural = "Systemoversikt: URL-er"
		verbose_name = "URL"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['domene']


# statike valgmenyer for CMDB

CMDB_KRITIKALITET_VALG = (
	(1, '1: most critical'),
	(2, '2: somewhat critical'),
	(3, '3: less critical'),
	(4, '4: not critical'),
)


#brukes ikke
#CMDB_TYPE_VALG = (
#	(1, 'Et system'),
#	(2, 'Ukjent'),
#	(3, 'En infrastrukturkomponent'),
#	(4, 'En samlekategori (BusinessService)'),
#	(5, 'For fakturering'),
#	(6, 'Tom / ikke i bruk'),
#)

CMDB_ENV_VALG = (
	(1, 'Produksjon'),
	(2, 'Test/demonstration'),
	(3, 'Utvikling'),
	(4, 'Kurs'),
	(5, 'Referansemiljø'),
	(6, 'Staging'),
	(7, 'QA'),
	(8, 'Ukjent'),
	(9, "Disaster recovery"),
)

CMDB_OPERATIONAL_STATUS = (
	(1, 'Operational'),
	(0, 'Not operational'),
)

# Dette er nivå 1 av CMDB-modellen, såkalt "business Service" i Service Now Common Service Data Model
class CMDBbs(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.CharField(
			verbose_name="CMDB-navn",
			max_length=600,
			blank=False,
			null=False,
			help_text=u"Importert",
			)
	bs_external_ref = models.CharField(
			unique=True,
			verbose_name="ForeignKey mot ServiceNow",
			max_length=64,
			blank=False,
			null=True,
			help_text=u"Importert",
			)
	operational_status = models.BooleanField(
			verbose_name="I bruk i ServiceNow",
			default=True,
			)
	eksponert_for_bruker = models.BooleanField(
			verbose_name="Eksponert mot bruker",
			default=True,
			)
	# med vilje er det ikke HistoricalRecords() på denne da den importeres regelmessig

	def __str__(self):
		return u'%s' % (self.navn)

	def backup_size(self):
		total = 0
		for bss in self.cmdb_bss_to_bs.all():
			total += bss.backup_size()
		return total

	def san_used(self):
		total = 0
		for bss in self.cmdb_bss_to_bs.all():
			total += bss.san_used()
		return total

	def san_allocated(self):
		total = 0
		for bss in self.cmdb_bss_to_bs.all():
			total += bss.san_allocated()
		return total

	def san_unallocated(self):
		total = 0
		for bss in self.cmdb_bss_to_bs.all():
			total += bss.san_unallocated()
		return total

	def san_used_pct(self):
		if self.san_allocated() != 0:
			return int(self.san_used() / self.san_allocated() * 100)
		return "NaN"

	def ram_allocated(self):
		total = 0
		for bss in self.cmdb_bss_to_bs.all():
			total += bss.ram_allocated()
		return total

	def ant_bss(self):
		return self.cmdb_bss_to_bs.all().count()

	def ant_devices(self):
		counter = 0
		for bss in self.cmdb_bss_to_bs.all():
			counter += bss.ant_devices()
		return counter

	def ant_databaser(self):
		counter = 0
		for bss in self.cmdb_bss_to_bs.all():
			counter += bss.ant_databaser()
		return counter

	def most_common_child_service_classification(self):
		import collections
		own_sub_services = self.cmdb_bss_to_bs.all()
		service_classifications = [bss.service_classification for bss in own_sub_services]
		counter = collections.Counter(service_classifications)
		most_common = counter.most_common(1)
		try:
			return(most_common[0][0])
		except:
			return("Ikke mulig å identifisere")

	class Meta:
		verbose_name_plural = "CMDB: Business services"
		verbose_name = "business service"
		default_permissions = ('add', 'change', 'delete', 'view')



# Dette er nivå 2 av CMDB-modellen, såkalt "Business Service Offering" i Service Now Common Service Data Model
# Importert fra CMDB via importscript
# representerer et "miljø", for produksjonsmiljøet for et gitt system.
# Er koblet til nivå 1, men nivå 1 er bare en "sekkepost" eller kategori, og er derfor ikke nyttig.
# Det er under disse servere og databaser kobles inn.
# Systemer har kobling til 0, 1 eller flere slike nivå2 offerings.
class CMDBRef(models.Model): # BSS
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.CharField(
			unique=False, # eksporter fra cmdb er ikke konsistente desverre..
			verbose_name="Sub service navn",
			max_length=600,
			blank=False,
			null=False,
			help_text=u"Importert",
			db_index=True,
			)
	operational_status = models.BigIntegerField(
			choices=CMDB_OPERATIONAL_STATUS,
			verbose_name="Operational status",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	parent_ref = models.ForeignKey(
			to=CMDBbs,
			related_name='cmdb_bss_to_bs',
			on_delete=models.CASCADE,
			blank=True,
			null=True,
			verbose_name="Tilhørerende Business service",
			help_text=u"Importert",
			)
	environment = models.BigIntegerField(
			choices=CMDB_ENV_VALG,
			verbose_name="Miljø",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	kritikalitet = models.BigIntegerField(
			choices=CMDB_KRITIKALITET_VALG,
			verbose_name="Busines criticality (SLA)",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	u_service_availability = models.CharField(
			max_length=50,
			verbose_name="Availability",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	u_service_operation_factor = models.CharField(
			max_length=50,
			verbose_name="operation factor",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	u_service_complexity = models.CharField(
			max_length=50,
			verbose_name="Complexity",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	u_service_billable = models.BooleanField(
			verbose_name="Billable?",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	service_classification = models.CharField(
			max_length=150,
			verbose_name="service classification",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	comments = models.TextField(
			verbose_name="Kommentar",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	bss_external_ref = models.CharField(
			unique=True,
			verbose_name="ForeignKey mot ServiceNow",
			max_length=64,
			blank=False,
			null=True,
			help_text=u"Importert",
			)
	# med vilje er det ikke HistoricalRecords() på denne da den importeres regelmessig

	def __str__(self):
		return f"{self.navn}"

	def er_produksjon(self):
		if self.environment == 1:
			return True
		return False

	def alle_dns(self):
		dnsrecords = set()
		for server in self.servers.all():
			# direkte dns-navn mot server
			for netaddr in server.network_ip_address.all():
				for dnsrec in netaddr.dns.all():
					dnsrecords.add(dnsrec)

			# indirekte dns-navn mot vip knyttet mot pool som server er medlem i
			for pool in server.vip_pool.all():
				#print("0", pool)
				for vip in pool.vip.all():
					#print("1",vip)
					for netaddr in vip.network_ip_address.all():
						#print("2",netaddr)
						for dnsrec in netaddr.dns.all():
							dnsrecords.add(dnsrec)
							#print("3",dnsrec)

		return dnsrecords

	def antall_dns_rec(self):
		return len(self.alle_dns())


	def backup_size(self):
		total = CMDBbackup.objects.filter(device__service_offerings=self).aggregate(Sum('backup_size_bytes'))["backup_size_bytes__sum"]
		if total == None:
			return 0
		return total

	def san_used(self):
		total = CMDBdevice.objects.filter(service_offerings=self).aggregate(Sum('vm_disk_usage'))["vm_disk_usage__sum"]
		if total == None:
			return 0
		return total

	def san_allocated(self):
		total = CMDBdevice.objects.filter(service_offerings=self).aggregate(Sum('vm_disk_allocation'))["vm_disk_allocation__sum"]
		if total == None:
			return 0
		return total

	def san_unallocated(self):
		return self.san_allocated() - self.san_used()

	def san_used_pct(self):
		if self.san_allocated() != 0:
			return int(self.san_used() / self.san_allocated() * 100)
		return "NaN"

	def ram_allocated(self):
		total = CMDBdevice.objects.filter(service_offerings=self).aggregate(Sum('comp_ram'))["comp_ram__sum"]
		if total == None:
			return 0
		return total * 1000**2 # MB til bytes

	def u_service_availability_text(self):
		lookup = {
			"T1": "T1🟢: 24/7/365, 99.9%",
			"T2": "T2🟢: 07-20 alle dager, 99.5%",
			"T3": "T3🟡: 07-16 virkedager, 99%",
			"T4": "T4🔴: Best effort",
			"E1": "E1🟡: Egendrift",
		}
		try:
			return lookup[self.u_service_availability]
		except:
			return self.u_service_availability


	def u_service_operation_factor_text(self):
		lookup = {
			"D1": "D1🔴: Liv og helse",
			"D2": "D2🔴: Virksomhetskritisk",
			"D3": "D3🟡: Kritisk",
			"D4": "D4🟡: Periodisk kritisk",
			"D5": "D5🟢: Ikke kritisk",
		}
		try:
			return lookup[self.u_service_operation_factor]
		except:
			return self.u_service_operation_factor


	def u_service_complexity_text(self):
		lookup = {
			"K1": "K1 🟢: 0-100 brukere, enkelt omfang",
			"K2": "K2 🟡: 0-100 brukere, middels omfang",
			"K3": "K3 🔴: 0-100 brukere, høyt omfang",
			"K4": "K4 🟡: 100-1000 brukere, enkelt omfang",
			"K5": "K5 🟡: 100-1000 brukere, middels omfang",
			"K6": "K6 🔴: 100-1000 brukere, høyt omfang",
			"K7": "K7 🟡: 1000+ brukere, enkelt omfang",
			"K8": "K8 🔴: 1000+ brukere, middels omfang",
			"K9": "K9 🔴: 1000+ brukere, høyt omfang",
		}
		try:
			return lookup[self.u_service_complexity]
		except:
			return self.u_service_complexity

	def er_infrastruktur_tom_bs(self):
		if self.cmdb_type in [3, 4, 6]:
			return True
		else:
			return False

	def er_ukjent(self):
		if self.cmdb_type == 2:
			return True
		else:
			return False

	def ant_devices(self):
		return CMDBdevice.objects.filter(service_offerings=self.pk).count()

	def ant_databaser(self):
		return CMDBdatabase.objects.filter(sub_name=self.pk, db_operational_status=True).count()

	def is_bss(self):
		if self.service_classification == "Business Service":
			return True
		else:
			return False

	def vlan(self):
		alle_vlan = set()
		for server in CMDBdevice.objects.filter(service_offerings=self.pk):
			for ipaddr in server.network_ip_address.all():
				for vlan in ipaddr.vlan.all():
					alle_vlan.add(vlan)


		for database in CMDBdatabase.objects.filter(sub_name=self.pk, db_operational_status=True):
			dbserver = CMDBdevice.objects.get(comp_name=database.db_server)
			for ipaddr in dbserver.network_ip_address.all():
				for vlan in ipaddr.vlan.all():
					alle_vlan.add(vlan)

		return list(alle_vlan)


	class Meta:
		verbose_name_plural = "CMDB: Business service offerings"
		verbose_name = "service offering"
		default_permissions = ('add', 'change', 'delete', 'view')


# Klasse for å representere virtuell lastbalanserte endepunkter. Er igjen knyttet til pools (VirtualIPPool), importert via importscript
class virtualIP(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	vip_name = models.CharField(
			max_length=200,
			null=True,
			unique=True,
			verbose_name="VIP name",
			)
	pool_name =models.CharField(
			max_length=200,
			null=True,
			verbose_name="Pool name",
			)
	ip_address = models.GenericIPAddressField(
			null=False,
			verbose_name="IP-adresse",
			)
	port = models.BigIntegerField(
			null=False,
			verbose_name="Port",
			)
	hitcount = models.BigIntegerField(
			null=False,
			verbose_name="Hitcount",
			)

	def __str__(self):
		return self.vip_name

	class Meta:
		verbose_name_plural = "CMDB: Virtual IPs"
		verbose_name = "virtual IP"
		default_permissions = ('add', 'change', 'delete', 'view')

	def nested_pool_members(self):
		members = []
		candidates = list(self.pool_members.all())
		already_seen = []

		while candidates:
			current_candidate = candidates.pop()
			already_seen.append(current_candidate)
			#print(current_candidate)
			if current_candidate.server:
				members.append(current_candidate)
				continue

			new_candidates = list(current_candidate.indirect_pool_members())
			for candidate in new_candidates:
				if candidate not in candidates and candidate not in already_seen:
					candidates.append(candidate)

		return members


# Klasse for å representere kilder (pools) for et gitt virtuell lastbalansert endepunkt
class VirtualIPPool(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	pool_name = models.CharField(
			max_length=200,
			null=False,
			verbose_name="Pool name",
			)
	ip_address = models.GenericIPAddressField(
			null=False,
			verbose_name="IP-adresse",
			)
	port = models.BigIntegerField(
			null=False,
			verbose_name="Port",
			)
	vip = models.ManyToManyField(
			to='virtualIP',
			related_name='pool_members',
			verbose_name="Tilhørende VIP",
			)
	server = models.ForeignKey(
			to='CMDBdevice',
			related_name='vip_pool',
			on_delete=models.SET_NULL,
			null=True,
			verbose_name="Server",
			)
	def __str__(self):
		return self.pool_name

	def indirect_pool_members(self):
		try:
			vip = virtualIP.objects.get(ip_address=self.ip_address, port=self.port)
			return vip.pool_members.all()
		except:
			return []


	class Meta:
		unique_together = ('pool_name', 'ip_address', 'port')
		verbose_name_plural = "CMDB: VIP pools"
		verbose_name = "VIP pool"
		default_permissions = ('add', 'change', 'delete', 'view')


# For å representere IP-nettverk fra infoblox, importert via importscript
class NetworkContainer(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	comment = models.CharField(
			max_length=200,
			null=True,
			verbose_name="Beskrivelse",
			)
	disabled = models.BooleanField(
			verbose_name="Deaktivert",
			default=False,
			)
	ip_address = models.GenericIPAddressField(
			null=False,
			verbose_name="IP-adresse",
			)
	subnet_mask = models.BigIntegerField(
			null=False,
			verbose_name="Netmask",
			)
	locationid = models.CharField(
			max_length=50,
			null=True,
			verbose_name="Location ID",
			)
	orgname = models.CharField(
			max_length=200,
			null=True,
			verbose_name="Org name",
			)
	vlanid = models.CharField(
			max_length=50,
			null=True,
			verbose_name="VLAN ID",
			)
	vrfname = models.CharField(
			max_length=200,
			null=True,
			verbose_name="VRF name",
			)
	netcategory = models.CharField(
			max_length=200,
			null=True,
			verbose_name="Kateogi",
			)
	network_zone = models.CharField(
			max_length=100,
			null=True,
			verbose_name="Nettverkssone",
			)
	network_zone_description = models.CharField(
			max_length=400,
			null=True,
			verbose_name="Nettverkssonebeskrivelse",
			)

	def __str__(self):
		return u'%s/%s' % (self.ip_address, self.subnet_mask)

	class Meta:
		unique_together = ("ip_address", "subnet_mask")
		verbose_name_plural = "CMDB: VLAN"
		verbose_name = "network container"
		default_permissions = ('add', 'change', 'delete', 'view')


# Klasse med informasjon om IP-adresser. Brukes overalt hvor en IP-adresse må representeres.
class NetworkIPAddress(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	ip_address = models.GenericIPAddressField(
		null=False,
		unique=True,
		verbose_name="IP-adresse",
	)
	ip_address_integer = models.BigIntegerField(
		verbose_name="IP-adresse heltall",
		null=True,
	)
	servere = models.ManyToManyField(
		to='CMDBdevice',
		verbose_name="Serverkobling",
		related_name='network_ip_address',
	)
	viper = models.ManyToManyField(
		to='virtualIP',
		verbose_name="Kobling til VIP-er",
		related_name='network_ip_address',
	)
	vip_pools = models.ManyToManyField(
		to='VirtualIPPool',
		verbose_name="Kobling til VIP pool-er",
		related_name='network_ip_address',
	)
	dns = models.ManyToManyField(
		to='DNSrecord',
		verbose_name="Kobling til DNS-records",
		related_name='network_ip_address',
	)
	vlan = models.ManyToManyField(
		to='NetworkContainer',
		verbose_name="Kobling til VLAN",
		related_name='network_ip_address',
	)

	class Meta:
		verbose_name_plural = "CMDB: Network IP-address"
		verbose_name = "IP-address"
		default_permissions = ('add', 'change', 'delete', 'view')

	def __str__(self):
		return u'%s' % self.ip_address

	def ant_servere(self):
		return self.servere.all().count()

	def ant_dns(self):
		return self.dns.all().count()

	def ant_vlan(self):
		return self.vlan.all().count()

	def ant_viper(self):
		return self.viper.all().count()

	def ant_pools(self):
		return self.vip_pools.all().count()

	def dominant_vlan(self):
		if self.ant_vlan() > 0:
			return self.vlan.all().order_by('-subnet_mask')[0]
		return []


# DNS-data (kobling navn-IP), importert fra DNS via importscript
class DNSrecord(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	dns_name = models.CharField(
			max_length=500,
			verbose_name="DNS name",
			)
	source = models.CharField(
			max_length=50,
			null=True,
			verbose_name="Kilde",
			)
	dns_type = models.CharField(
			max_length=50,
			null=True,
			verbose_name="DNS type",
			)
	ip_address = models.GenericIPAddressField(
			null=True,
			verbose_name="IP-adresse",
			)
	ttl = models.BigIntegerField(
			null=True,
			verbose_name="Time to live (TTL)",
			)
	dns_target = models.CharField(
			max_length=200,
			null=True,
			verbose_name="DNS target (hvis CNAME eller MX)",
			)
	dns_domain = models.CharField(
			max_length=200,
			null=False,
			verbose_name="Domain",
			)
	txt = models.TextField(
			verbose_name="txt-data",
			blank=True,
			null=True,
			help_text=u"DNS TXT",
			)
	unique_together = ('dns_name', 'dns_type', 'source')

	def __str__(self):
		return u'%s: %s' % (self.dns_type, self.dns_name)

	def dns_full_name(self):
		return u'%s.%s' % (self.dns_name, self.dns_domain)

	class Meta:
		verbose_name_plural = "CMDB: DNS records"
		verbose_name = "DNS-record"
		default_permissions = ('add', 'change', 'delete', 'view')


# Statisk valgmeny populert fra DSB sitt rammeverk, nivå 1 hovedkategorier
KRITISKE_KATEGORIER = (
	(1, 'Styringsevne og suvernitet'),
	(2, 'Befolkningens sikkerhet'),
	(3, 'Samfunnets funksjonalitet'),
)


# Dynamisk valgmeny populert fra DSB sitt rammeverk, nivå 3 funksjon under kapabilitetene. Brukes for å tagge systemer.
# 2026-06-23: Exposed via /api/kritiske_funksjoner/ – update api_tjeneste_systemoversikt_docs.py when changing relevant API output (url name: api_tjeneste_systemoversikt_docs).
class KritiskFunksjon(models.Model):
	navn = models.CharField(
			max_length=150,
			null=False,
			verbose_name="Funksjon",
			)
	kategori = models.BigIntegerField(
			choices=KRITISKE_KATEGORIER,
			verbose_name="Hovedkategori",
			blank=False, null=False,
			)
	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemkategori: Kritiske funksjoner"
		verbose_name = "kritisk funksjon"
		default_permissions = ('add', 'change', 'delete', 'view')

	def systemer(self):
		systemer = set()
		for kapabilitet in self.funksjoner.all():
			for system in kapabilitet.systemer.all():
				systemer.add(system)
		return list(systemer)


# Dynamisk valgmeny populert fra DSB sitt rammeverk, nivå 2 kapabiliteter under hovedkategoriene
# 2026-06-23: Exposed via /api/kritiske_kapabiliteter/ – update api_tjeneste_systemoversikt_docs.py when changing relevant API output (url name: api_tjeneste_systemoversikt_docs).
class KritiskKapabilitet(models.Model):
	navn = models.CharField(
			max_length=150,
			null=False,
			verbose_name="Kapabilitet",
			)
	funksjon = models.ForeignKey(
			to=KritiskFunksjon,
			related_name='funksjoner',
			verbose_name="Tilhørende funksjon",
			on_delete=models.CASCADE,
			blank=False,
			null=False,
		)
	beskrivelse = models.TextField(
			verbose_name="Beskrivelse",
			blank=True,
			null=True,
			)
	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemkategori: Kritiske kapabiliteter"
		verbose_name = "kritisk kapabilitet"
		default_permissions = ('add', 'change', 'delete', 'view')


# Oppbevaring av informasjon om databaser, importert fra CMDB via importscript
class CMDBdatabase(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	db_operational_status = models.BooleanField(
			verbose_name="db_operational_status",
			default=True,
			)
	db_version = models.TextField(
			verbose_name="db_version",
			blank=True,
			null=True,
			help_text=u"Importert: db_version",
			)
	billable = models.BooleanField(
			verbose_name="Billable",
			default=False,
			)
	db_u_datafilessizekb = models.BigIntegerField( ### Det er faktisk bytes som skrives til denne. Gammelt navn fra CMDB-rapport.
			verbose_name="db_u_datafilessizekb",
			blank=True,
			null=False,
			default=0,
			help_text=u"Størrelse på database i Bytes",
			)
	db_database = models.TextField(
			verbose_name="db_database",
			blank=True,
			null=True,  # importscriptet vil ikke tillate dette, men datamodellen bryr seg ikke
			help_text=u"Importert: db_database",
			)
	db_server = models.TextField(
			verbose_name="db_server",
			blank=True,
			null=True,  # importscriptet vil ikke tillate dette, men datamodellen bryr seg ikke
			help_text=u"Importert: db_server",
			)
	db_server_modelref = models.ForeignKey(
			to="CMDBdevice",
			related_name='database_server',
			verbose_name="Referanse til server",
			on_delete=models.CASCADE,
			blank=True,
			null=True,
			help_text=u"Slått opp basert på kommentarfelt med maskinnavn",
			)
	db_used_for = models.TextField(
			verbose_name="db_used_for",
			blank=True,
			null=True,
			help_text=u"Importert: db_used_for",
			)
	db_comments = models.TextField(
			verbose_name="db_comments",
			blank=True,
			null=True,
			help_text=u"Importert: db_comments",
			)
	db_status = models.TextField(
			verbose_name="Install status",
			blank=True,
			null=True,
			help_text=u"Importert: (tidligere db_status)",
			)
	sub_name = models.ForeignKey(
			to=CMDBRef,
			related_name='cmdbdatabase_sub_name',
			verbose_name="Business Sub Service",
			on_delete=models.CASCADE,
			blank=True,
			null=True,
			help_text=u"Slått opp basert på comment-felt",
			)
	unique_together = ('db_database', 'db_server')
	# med vilje er det ikke HistoricalRecords() på denne da den importeres regelmessig

	def __str__(self):
		return u'%s' % (self.db_database)

	class Meta:
		verbose_name_plural = "CMDB: Databaser"
		verbose_name = "database"
		default_permissions = ('add', 'change', 'delete', 'view')


# Dynamisk valgmeny for å manuelt kunne legge til stringer av sårbarheter som basisdrift er ansvarlig for
class QualysVulnBasisPatching(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	title = models.TextField()

	def __str__(self):
		return f"{self.title}"

	class Meta:
		verbose_name_plural = "Qualys: Basispatching"
		verbose_name = "Basispatchet"
		default_permissions = ('add', 'change', 'delete', 'view')


# 2026-06-21: Title substring rules for accepted risk – independent of basisdrift patching ownership.
class QualysVulnRiskAcceptance(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	title = models.TextField()

	def __str__(self):
		return f"{self.title}"

	class Meta:
		verbose_name = "Akseptert risiko"
		verbose_name_plural = "Qualys: Aksepterte risikoer"
		default_permissions = ('add', 'change', 'delete', 'view')


# Programvaresårbarheter, importert fra Qualys, knyttet til server som igjen er knyttet indirekte til system.
class QualysVuln(models.Model):
	source = models.TextField()
	server = models.ForeignKey(
			to="CMDBdevice",
			on_delete=models.SET_NULL,
			related_name='qualys_vulnerabilities',
			null=True
			)
	title = models.TextField()
	severity = models.BigIntegerField()
	known_exploited = models.BooleanField(default=False)
	first_seen = models.DateTimeField(null=True)
	last_seen = models.DateTimeField(null=True)
	public_facing = models.BooleanField()
	cve_info = models.TextField()
	result = models.TextField()
	os = models.TextField()
	status = models.TextField(null=True)
	ansvar_basisdrift = models.BooleanField(default=False)
	akseptert = models.BooleanField(default=False)
	raw = models.JSONField(null=True)

	def __str__(self):
		return f"{self.title}"

	def known_exploited_info(self):
		try:
			cves = self.cve_info.split(",")
			exploited = ExploitedVulnerability.objects.filter(cve_id__in=cves)
			return ", ".join(f"{e.cve_id}" for e in exploited)
		except:
			return f"known_exploited_info() feilet"

	def source_readable(self):
		return self.source

	def csv_readable(self):
		if "CVSS3.1" in self.raw:
			return f"{self.raw['CVSS3.1']}"
		#if "CVSS" in self.raw:
		#		return f"{self.raw['CVSS']} (CVSS)"
		return "-"

	def raw_readable(self):
		return json.dumps(self.raw, indent=4)


	class Meta:
		verbose_name_plural = "Qualys: Sårbarheter"
		verbose_name = "sårbarhet"
		default_permissions = ('add', 'change', 'delete', 'view')


# Devices fra CMDB, servere eller klienter. Importeres fra CMDB. device_type angir type enhet. Koblet til service offerings som igjen er koblet til systemer
class CMDBdevice(models.Model):
	opprettet = models.DateTimeField( # system
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField( # system
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	device_type = models.CharField( # SERVER, CLIENT, NETWORK
			max_length=50,
			blank=False,
			null=True,
			verbose_name="Enhetstype",
			help_text="Settes automatisk ved import",
			)
	client_model_id = models.CharField( # egen fil med detaljer som lastes etter computers-filen. Bare for klienter.
			verbose_name="Klientmodell",
			max_length=200,
			blank=True,
			null=True,
			)
	client_sist_sett = models.DateTimeField( # INGEN KILDE LENGER?
			verbose_name="Sist sett",
			null=True,
			blank=True,
			)
	client_last_loggedin_user = models.ForeignKey( # INGEN KILDE LENGER?
			to=User,
			on_delete=models.SET_NULL,
			related_name='client',
			verbose_name="Sist innloggede bruker",
			null=True,
			blank=True,
			)
	billable = models.BooleanField( # Fra CMDB computers
			verbose_name="Billable",
			default=False,
			)
	comp_name = models.CharField( # Unikt navn på server.
			unique=True,
			verbose_name="Computer name",
			max_length=600,
			blank=False,
			null=False,
			help_text=u"",
			db_index=True,
			)
	comp_disk_space = models.BigIntegerField(  # lagres i bytes
			verbose_name="Lagring",
			blank=True,
			null=True,
			help_text=u"",
			)
	service_offerings = models.ManyToManyField(
			to=CMDBRef,
			related_name='servers',
			verbose_name="Service Offerings",
			blank=True,
			)
	comp_ip_address = models.CharField(
			verbose_name="IP-address",
			max_length=100,
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_os = models.CharField(
			verbose_name="Operativsystem",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_os_version = models.CharField(
			verbose_name="OS versjon",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_os_readable = models.CharField(
			verbose_name="OS readable",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_os_service_pack = models.CharField(
			verbose_name="OS service pack",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_cpu_core_count = models.BigIntegerField(
			verbose_name="CPU core count",
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_ram = models.BigIntegerField(  # lagres i antall MB
			verbose_name="RAM",
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_location = models.CharField(
			verbose_name="Datasenter",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	comments = models.TextField(
			verbose_name="Comments",
			null=True,
			blank=True,
			)
	description = models.TextField(
			verbose_name="Description",
			null=True,
			blank=True,
			)
	client_virksomhet = models.ForeignKey(
			to="Virksomhet",
			on_delete=models.SET_NULL,
			verbose_name="Klientens tilhørende virksomhet",
			related_name='cmdbdevice_virksomhet',
			null=True,
			blank=True,
			)
	vm_disk_allocation = models.FloatField( # denne verdien resettes hver gang vmwaredata importeres, og kan brukes for å summere opp faktisk allokert disk for maskiner som er "deaktivert"
			verbose_name="VM: Disk allokert",
			null=True, blank=True,
			)
	vm_disk_usage = models.FloatField(
			verbose_name="VM: Disk i bruk",
			null=True, blank=True,
			)
	vm_disk_tier = models.CharField(
			verbose_name="VM: Disk tier",
			max_length=300,
			null=True, blank=True,
			)
	eksternt_eksponert_dato = models.DateTimeField( # settes av csirt_iplookup_api()
			verbose_name="Sist eksponert mot Internett dato",
			null=True, blank=True,
			)
	citrix_desktop_group = models.CharField(
			verbose_name="Citrix-import: desktop group name",
			max_length=500,
			null=True, blank=True,
			)
	derived_os_endoflife = models.BooleanField(
			default=False
			)
	service_now_install_status = models.CharField(
			verbose_name="Install status fra service now",
			max_length=200,
			null=True, blank=True,
			)
	service_now_last_updated = models.DateTimeField(
			verbose_name="Dato sist skannet av Service Now",
			null=True, blank=True,
			)
	# med vilje er det ikke HistoricalRecords() på denne da den importeres



	def __str__(self):
		return u'%s' % (self.comp_name)

	def offering_navn(self):
		return ', '.join(offering.navn for offering in self.service_offerings.all())

	def disk_usage_free(self):
		if self.vm_disk_usage != None and self.vm_disk_allocation not in [None, 0]:
			return 100 - int(self.vm_disk_usage / self.vm_disk_allocation * 100)
		return "? "

	def comp_ram_byes(self):
		if self.comp_ram != None:
			return self.comp_ram * 1000**2
		return "? "

	def nat(self):
		return 'ikke implementert'

	def vlan(self):
		try:
			return ', '.join([vlan.comment for vlan in self.network_ip_address.all()[0].vlan.all()])
		except:
			return 'ingen data'

	def dns(self):
		try:
			return ', '.join([dns.dns_full_name() for dns in self.network_ip_address.all()[0].dns.all()])
		except:
			return 'ingen data'

	def backup_size(self):
		if self.backup:
			return [b.backup_size_bytes for b in self.backup.all()]
		else:
			return None

	def ratio_backup_disk(self):
		backupsize = self.backup_size() # det vil i praksis aldri være flere verdier selv om det per datamodell er mulig
		vm_disk_usage = self.vm_disk_usage
		try:
			return round(backupsize[0] / vm_disk_usage) # begge er bytes
		except:
			return "error"

	def vip(self):
		try:
			vip_names = []
			for pool in self.network_ip_address.all()[0].vip_pools.all():
				for vip in pool.vip.all():
					vip_names.append(vip)
			return ', '.join([vip.vip_name for vip in vip_names])
		except:
			return 'ingen data'

	def vulnerabilities(self):
		return self.qualys_vulnerabilities.all()

	class Meta:
		verbose_name_plural = "CMDB: Enheter"
		verbose_name = "maskin"
		default_permissions = ('add', 'change', 'delete', 'view')


# Oppbevaring av backup fra leverandørrapport. Kilde, størrelse og policy, knyttet til server.
class CMDBbackup(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	device_str = models.CharField(
			verbose_name="Device string",
			max_length=200,
			blank=True,
			null=True,
			)
	device = models.ForeignKey(
			to="CMDBdevice",
			related_name='backup',
			on_delete=models.CASCADE,
			verbose_name="Backup av",
			null=True,
			)
	source_type = models.CharField(
			verbose_name="Source type",
			max_length=20,
			blank=True,
			null=True,
			)
	backup_size_bytes = models.BigIntegerField(
			null=True,
			)
	#tas vekk 23.01.2023 da den ikke ligger i powerBI-dashboardet
	#export_date = models.DateTimeField(
	#		verbose_name="Dato uttrekk",
	#		null=True,
	#		)

	# fjernet fordi den nå har blitt mange til mange, og vi følger heller kobling fra server.
	# reintrodusert
	storage_size_bytes = models.BigIntegerField(
			null=True,
			)
	bss = models.ForeignKey(
			to=CMDBRef,
			related_name='backup',
			verbose_name="Business Sub Service",
			on_delete=models.CASCADE,
			blank=True,
			null=True,
			help_text=u"",
			)
	backup_frequency = models.CharField(
			verbose_name="Backup frequency",
			max_length=20,
			blank=True,
			null=True,
			)
	storage_policy = models.CharField(
			verbose_name="Storage Policy",
			max_length=150,
			blank=True,
			null=True,
			)
	environment = models.BigIntegerField(
			choices=CMDB_ENV_VALG,
			verbose_name="Miljø",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	# vurdere unique_together med device_str og device?

	class Meta:
		verbose_name_plural = "CMDB: Sikkerhetskopier"
		verbose_name = "sikkerhetskopi"
		default_permissions = ('add', 'change', 'delete', 'view')

	def __str__(self):
		return u'%s %s' % (self.device, self.backup_size_bytes)



class CMDBDisk(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	operational_status = models.BooleanField(
			verbose_name="operational_status",
			default=False,
			)
	size_bytes = models.BigIntegerField(
			verbose_name="Size in bytes",
			blank=True,
			null=True,
			)
	#capacity = models.BigIntegerField(
	#		verbose_name="capacity",
	#		blank=True, null=True,
	#		)
	name = models.TextField(
			verbose_name="Name",
			unique=False,
			null=True
			)
	mount_point = models.TextField(
			verbose_name="mount_point",
			unique=False,
			null=True
			)
	#available_space = models.BigIntegerField(
	#		verbose_name="available_space",
	#		blank=True, null=True,
	#		)
	file_system = models.TextField(
			verbose_name="file_system",
			unique=False,
			null=True
			)
	free_space_bytes = models.BigIntegerField(
			verbose_name="free_space_bytes",
			blank=True,
			null=True,
			)
	computer = models.CharField(
			verbose_name="Computer ID",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	computer_ref = models.ForeignKey(
			to="CMDBdevice",
			related_name='cmdbdisk_computer',
			on_delete=models.CASCADE,
			verbose_name="Computer ref",
			blank=False,
			null=True,
			help_text=u"Mor-gruppe (importert)",
			)
	unique_together = ('computer_ref', 'mount_point')
	# med vilje er det ikke HistoricalRecords() på denne da den importeres

	def __str__(self):
		return u'%s' % (self.size_bytes)

	class Meta:
		verbose_name_plural = "CMDB: Serverdisker"
		verbose_name = "disk"
		default_permissions = ('add', 'change', 'delete', 'view')



class ADOrgUnit(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	distinguishedname = models.TextField(
			verbose_name="Fully Distinguished Name",
			unique=True,
			null=False
			)
	ou = models.CharField(
			verbose_name="Name",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	when_created = models.CharField(
			verbose_name="When created",
			max_length=30,
			blank=True,
			null=True,
			help_text=u"",
			)
	parent = models.ForeignKey(
			to="ADOrgUnit",
			related_name='adorgunit_parent',
			on_delete=models.CASCADE,
			verbose_name="Parent",
			blank=True,
			null=True,
			help_text=u"Mor-gruppe (importert)",
			)
	# med vilje er det ikke HistoricalRecords() på denne da den importeres

	def __str__(self):
		return u'%s' % (self.distinguishedname)

	class Meta:
		verbose_name_plural = "Active Directory: OU-er"
		verbose_name = "OU"
		default_permissions = ('add', 'change', 'delete', 'view')

	def cn(self):
		if len(self.distinguishedname) > 39:
			return self.distinguishedname[0:-39]
		else:
			return self.distinguishedname


class Leverandortilgang(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.CharField(
			verbose_name="Visningsnavn",
			help_text="Valgfritt å fylle ut",
			blank=True,
			null=True,
			max_length=100,
			)
	systemer = models.ManyToManyField(
			to='System',
			related_name='leverandortilgang',
			verbose_name="Systemtilknytning",
			blank=False,
			help_text=u"Brukes for tilgang til følgende systemer",
			)
	adgrupper = models.ManyToManyField(
			to='ADgroup',
			related_name='leverandortilganger',
			verbose_name="AD-gruppeknytninger",
			blank=False,
			help_text=u"Gis tilgang via følgende AD-gruppe",
			)
	kommentar = models.TextField(
			verbose_name="Kommentar",
			help_text=u"Utdypende detaljer",
			blank=True,
			null=True,
			)
	history = HistoricalRecords()

	def __str__(self):
		if self.navn != None:
			return u'%s' % (self.navn)
		try:
			return u'Leverandørtilgang for %s' % (', '.join(s.systemnavn for s in self.systemer.all()))
		except:
			return u'Leverandørtilgang %s' % self.pk

	def systemer_vis(self):
		return ", ".join([
			system.systemnavn for system in self.systemer.all()
		])
		systemer_vis.short_description = "Systemer"

	class Meta:
		verbose_name_plural = "Systemoversikt: Leverandørtilganger"
		default_permissions = ('add', 'change', 'delete', 'view')


class ADgroup(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	distinguishedname = models.TextField(
			verbose_name="Fully Distinguished Name",
			unique=True,
			db_index=True,
			)
	display_name = models.TextField(
			verbose_name="Display Name",
			unique=False,
			null=True,
			)
	common_name = models.TextField(
			verbose_name="Common Name",
			db_index=True,
			null=True,
			)
	member = models.TextField(
			verbose_name="Medlemmer",
			blank=True,
			null=True,
			)
	membercount = models.BigIntegerField(
			verbose_name="Antall medlemmer",
			blank=True,
			null=True,
			)
	memberof = models.TextField(
			verbose_name="Er medlem av",
			blank=True,
			null=True,
			)
	memberofcount = models.BigIntegerField(
			verbose_name="Antall medlem av",
			blank=True,
			null=True,
			)
	description = models.TextField(
			verbose_name="Beskrivelse",
			blank=True,
			null=True,
			)
	from_prk = models.BooleanField(
			verbose_name="Finnes i PRK?",
			default=False,
			help_text=u"Historical flag: group was provisioned via PRK (no longer updated).",
			)
	mail = models.TextField(
			verbose_name="Mail",
			blank=True,
			null=True,
			)
	parent = models.ForeignKey(
			to=ADOrgUnit,
			related_name='adgroup_parent',
			on_delete=models.CASCADE,
			verbose_name="Parent",
			blank=True,
			null=True,
			help_text=u"Mor-gruppe (importert)",
			)
	systemer = models.ManyToManyField(
			to="System",
			related_name='adgrupper',
			verbose_name="Systemer basert på navneoppslag",
			)
	# med vilje er det ikke HistoricalRecords() på denne da den importeres

	def __str__(self):
		if self.display_name == "" or self.display_name == None:
			return u'%s' % (self.common_name)
		return u'%s' % (self.display_name)

	class Meta:
		verbose_name_plural = "Active Directory: AD-grupper"
		verbose_name = "AD-gruppe"
		default_permissions = ('add', 'change', 'delete', 'view')

	def cn(self):
		if len(self.distinguishedname) > 39:
			return self.distinguishedname[0:-39]
		else:
			return self.distinguishedname

	def short(self):
		return self.distinguishedname[3:].split(",")[0]  # fjerner cn= og alt etter komma


	def brukere_for_virksomhet(self, virksomhet):
		try:
			alle_brukere = json.loads(self.member)
			matchede_brukere = []
			for bruker in alle_brukere:
				brukernavn = re.search(r'cn=([^\,]*)', bruker, re.I).groups()[0]
				if brukernavn.startswith(virksomhet.virksomhetsforkortelse):
					matchede_brukere.append(brukernavn)
			return len(matchede_brukere)
		except:
			return "error"

	def antall_underliggende_medlemmer(self):
		from systemoversikt.views import adgruppe_utnosting
		underliggende_grupper = adgruppe_utnosting(self)
		antall = 0
		for g in underliggende_grupper:
			antall += g.membercount
		return antall - (len(underliggende_grupper) - 1) # det er alltid én gruppe om det ikke er undergrupper

	def ou_lesbar(self):
		if self.distinguishedname != None:
			return self.distinguishedname.split(",")[1:-4]
		return ""



AVTALETYPE_VALG = (
	(1, 'Databehandleravtale'),
	(2, 'Driftsavtale (SSA-D)'),
	(3, 'Vedlikeholdsavtale (SSA-V)'),
	(4, 'Bistandsavtale (SSA-B)'),
	(5, 'Løpende tjenestekjøpsavtale (SSA-L)'),
	(6, 'Kjøpsavtale (SSA-K)'),
	(7, 'Forvaltningsavtale'),
	(8, 'Tjenesteavtale'),
)



class Avtale(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	avtaletype = models.BigIntegerField(
			choices=AVTALETYPE_VALG,
			verbose_name="Avtaletype",
			blank=True,
			null=True,
			help_text=u"Hva slags kategori avtale er dette?",
			)
	intern_avtalereferanse = models.ManyToManyField(
			to="Avtale",
			related_name='avtale_intern_avtalereferanse',
			verbose_name="Intern avtaleavhengighet",
			blank=True,
			help_text=u"Databehandleravtaler er ofte forankret i SSA-avtaler.",
			)
	kortnavn = models.CharField(
			unique=True,
			verbose_name="Kortnavn på avtale",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"Noe som er lett å søke opp. Maks 100 tegn. Må være unik",
			)
	for_system = models.ManyToManyField(
			to="System",
			related_name="avtale_for_system",
			verbose_name="Gjelder for følgende systemer",
			blank=True,
			help_text=u"For å angi system avtalen gjelder for",
			)
	for_driftsmodell = models.ManyToManyField(
			to="Driftsmodell",
			related_name="avtale",
			verbose_name="Gjelder for platformene",
			blank=True,
			help_text=u"For å angi plattform avtalen gjelder for",
			)
	beskrivelse = models.TextField(
			verbose_name="Detaljer om avtalen (fritekst)",
			blank=True,
			null=True,
			help_text=u"Her kan du utdype det du ønsker om avtalen",
			)
	virksomhet = models.ForeignKey(
			to=Virksomhet,
			related_name='databehandleravtale_virksomhet',
			on_delete=models.PROTECT,
			verbose_name="Avtalepart Oslo kommune (virksomhet)",
			blank=False,
			null=False,
			help_text=u"Den virksomhet som eier avtalen.",
			)
	avtaleansvarlig = models.ManyToManyField(
			to=Ansvarlig,
			related_name='databehandleravtale_avtaleansvarlig',
			verbose_name="Avtaleforvalter",
			blank=True,
			help_text=u"Den person (rolle) som forvalter avtalen.",
			)
	avtaleansvarlig_seksjon = models.ForeignKey(
			to='HRorg',
			related_name='avtale',
			on_delete=models.SET_NULL,
			verbose_name='Ansvarlig seksjon',
			null=True,
			blank=True,
			)
	leverandor = models.ForeignKey(
			to=Leverandor,
			related_name='databehandleravtale_leverandor',
			on_delete=models.PROTECT,
			verbose_name="Avtalepart ekstern leverandør",
			blank=True,
			null=True,
			help_text=u"Brukes dersom avtalepart er en ekstern leverandør.",
			)
	leverandor_intern = models.ForeignKey(
			to=Virksomhet,
			related_name='databehandleravtale_leverandor_intern',
			on_delete=models.PROTECT,
			verbose_name="Avtalepart intern leverandør",
			blank=True,
			null=True,
			help_text=u"Brukes dersom avtalepart er en annen virksomhet i Oslo kommune.",
			)
	avtalereferanse = models.CharField(
			verbose_name="Avtalereferanse",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Avtalereferanse, helst referanse fra et arkivsystem. Referansen bør være unik i Oslo kommune.",
			)
	dokumenturl = models.URLField(
			verbose_name="Dokument-URL",
			max_length=400,
			blank=True,
			null=True,
			help_text=u"En URL til et annet system der avtalen kan leses.",
			)
	fornying_dato = models.DateField(
			verbose_name="Dato for fornying",
			null=True,
			blank=True,
			)
	dato_signert = models.DateField(
			verbose_name="Signert dato",
			null=True,
			blank=True,
			)
	fornying_varsling_valg = models.BooleanField(
			verbose_name="Aktiver varsling",
			default=False,
			help_text=u"Denne varslingen går til avtaleforvalter. Du kan angi flere mottakere under.",
			)
	fornying_ekstra_varsling = models.ManyToManyField(
			to=Ansvarlig,
			related_name='avtale_ekstra_varsling_utlop',
			verbose_name="Andre som skal varsles før utløp",
			help_text=u"",
			blank=True,
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s med %s (%s)' % (self.kortnavn, self.leverandor, self.get_avtaletype_display())

	class Meta:
		verbose_name_plural = "Organisasjon: Avtaler"
		default_permissions = ('add', 'change', 'delete', 'view')



# 2026-06-23: Exposed via /api/systemtyper/ – update api_tjeneste_systemoversikt_docs.py when changing relevant API output (url name: api_tjeneste_systemoversikt_docs).
class Systemtype(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	kategorinavn = models.CharField(
			unique=True,
			verbose_name="Systemtypenavn",
			max_length=50,
			blank=False,
			null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"Beskrivelse av kategori og noen eksempler.",
			)
	har_url = models.BooleanField(
			verbose_name="Har slike systemer en URL?",
			default=False,
			help_text=u"Krysses av dersom det er forventet at systemer i denne kategorien har en URL.",
			)
	er_infrastruktur = models.BooleanField(
			verbose_name="Er denne kategorien infrastruktur?",
			default=False,
			help_text=u"Brukes for å identifisere systemet som er infrastruktur.",
			)
	er_integrasjon = models.BooleanField(
			verbose_name="Er denne kategorien en integrasjon?",
			default=False,
			help_text=u"Brukes for å identifisere systemet som er integrasjoner.",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.kategorinavn)

	class Meta:
		verbose_name_plural = "Systemkategori: Systemtyper"
		default_permissions = ('add', 'change', 'delete', 'view')



"""
SYSTEMTYPE_VALG = (
	('STANDALONE', 'Selvstendig klientapplikasjon'),
	('SERVERCLIENT', 'Serer-klientapplikasjon'),
	('WEB', 'Webbasert applikasjon'),
	('IOSAPP', 'iOS-App'),
	('ANDROIDAPP', 'Android-App'),
)
"""

TJENESTENIVAA_VALG = (
	('GULL', 'Gull'),
	('SOLV', 'Sølv'),
	('BRONSE', 'Bronse'),
	('AVTALE', 'Egen avtale'),
	('KAPASITET', 'Kapasitet'),
	('SERVERDRIFT', 'Serverdrift'),
	('INGEN AVTALE', 'Ingen avtale'),
	('', 'Ukjent'),
)

SYSTEMEIERSKAPSMODELL_VALG = (
	('VIRKSOMHETSSYSTEM', 'Virksomhetssystem'),
	('SEKTORSYSTEM', 'Sektorsystem'),
	('TVERRSEKTORIELT', 'Tverrsektorielt system'),
	('FELLESSYSTEM', 'Fellessystem (valgfritt)'),
	('FELLESSYSTEM_OBLIGATORISK', 'Fellessystem (obligatorisk)'),
	('STOTTE', 'IKT-støttesystem'),
	('NASJONALFELLESK', 'Nasjonal felleskomponent')
)

# må lage et script som inverterer verdiene i databasen 5 til 1 og 4 til 2 samtidig som disse inverteres.
VURDERINGER_SIKKERHET_VALG = (
	(1, '🔴5 Svært alvorlig'),
	(2, '🔴4 Alvorlig'),
	(3, '🟡3 Moderat'),
	(4, '🟢2 Lav'),
	(5, '🟢1 Ubetydelig'),
	(6, '0 Ikke vurdert'),
)

#☹ 😕 😐 🙂 😃

VURDERINGER_TEKNISK_VALG = (
	(1, '1 💔 Ingen'),
	(2, '2 🧡 Delvis'),
	(3, '3 💛 Akseptabel'),
	(4, '4 💚 God'),
	(5, '5 💙 Meget god'),
)

VURDERINGER_STRATEGISK_VALG = (
	(1, '1 💔 Ingen'),
	(2, '2 🧡 Delvis'),
	(3, '3 💛 God knytning'),
	(4, '4 💚 Tydelig knytning'),
	(5, '5 💙 Sterk knytning'),
)

VURDERINGER_FUNKSJONELL_VALG = (
	(1, '1 💔 Ikke akseptabel'),
	(2, '2 🧡 Store mangler'),
	(3, '3 💛 Akseptabelt'),
	(4, '4 💚 Godt egnet'),
	(5, '5 💙 Meget godt egnet'),
)

PROGRAMVAREKATEGORI_VALG = (
	(1, 'Hyllevare'),
	(2, 'Tilpasset hyllevare'),
	(3, 'Egenutviklet'),
	(4, 'Skreddersøm'),
)

LIVSLOEP_VALG = (
	(None, '0 Ikke vurdert'),
	(1, '1 💡 Under anskaffelse/utvikling'),
	(2, '2 🤞 Nytt og moderne, men fortsatt litt umodent'),
	(3, '3 👌 Moderne og modent'),
	(4, '4 👍 Modent, men ikke lengre moderne'),
	(5, '5 ☢️ Bør/skal byttes ut'),
	(6, '6 💾 Ute av bruk, men tilgjengelig'),
	(7, '7 ❌ Fullstendig avviklet'),
	(8, '8 ❓ Ukjent'),
)

SELVBETJENING_VALG = (
	(1, 'Ja'),
	(2, 'Nei'),
	(3, 'Planlagt'),
)

SIKKERHETSNIVAA_VALG = (
	(1, '🟢 Åpen'),
	(2, '🟡 Intern'),
	(5, '🔴 Beskyttet'),
	(3, '🔴 Strengt beskyttet'),
	(4, '🔴 Gradert')
)

LEVERANSEMODELL_VALG = (
	(0, 'Vet ikke'),
	(1, 'Applikasjonsdrift'),
	(2, 'Basisdrift'),
	(3, 'Nettverksdrift'),
	(4, 'App-V'),
	(5, 'LANDesk/image'),
	(6, 'Snarvei')
)

VALG_KLARGJORT_SIKKERHETSMODELL = (
	(None, "❔ Ikke vurdert"),
	(1, "🟢 Klargjort via Azure Web Application Proxy"),
	(2, "🟢 Klargjort som Citrix publisert applikasjon"),
	(3, "🟢 Direkteeksponert webtjeneste med Azure AD-pålogging"),
	(4, "🟢 Desktopapplikasjon uten avhengigheter, ferdig pakket"),
	(9, "🟢 Publisert på dedikerte AVD-maskiner"),
	(5, "🟡 Ikke klargjort, skal til Azure Web Application Proxy"),
	(9, "🟡 Ikke klargjort, skal direkteeksponeres og ha Azure AD autentisering"),
	(6, "🟡 Ikke klargjort, skal publiseres som Citrix strømmet app"),
	(7, "🟡 Ikke klargjort, skal kun pakkes som desktop applikasjon"),
	(10, "🟡 Ikke klargjort, skal til dedikerte AVD-maskiner"),
	(8, "🔴 Ingen løsning klar enda"),
)


# 2026-06-23: Exposed via /api/vulnapp/programvare/ – update api_vulnapp_docs.py when changing til_cveoversikt_og_nyheter output (url name: api_vulnapp_docs).
# 2026-06-23: Exposed via /api/programvarer/ – update api_tjeneste_systemoversikt_docs.py when changing relevant API output (url name: api_tjeneste_systemoversikt_docs).
class Programvare(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	programvarenavn = models.CharField(
			unique=True,
			verbose_name="Programvarenavn",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"",
			)
	alias = models.TextField(
			verbose_name="Alternative navn / alias",
			blank=True,
			null=True,
			help_text=u"Alternative navn på programvaren for å avhjelpe søk. Kun enkeltord. Du kan skrive inn flere alias, gjerne separert med komma eller på hver sin linje. Disse alias brukes også for å søke opp tilgangsgrupper tilhørende systemet.",
			)
	programvarekategori = models.BigIntegerField(
			choices=PROGRAMVAREKATEGORI_VALG,
			verbose_name="Tilpassing",
			blank=True,
			null=True,
			help_text=u"Er programvaren spesialtilpasset våre behov?",
			)
	programvaretyper = models.ManyToManyField(
			to=Systemtype,
			related_name='programvare_programvaretyper',
			verbose_name="Programvaretype",
			blank=True,
			help_text=u"Kategori programvare?",
			)
	programvarebeskrivelse = models.TextField(
			verbose_name="Programvarebeskrivelse",
			blank=True,
			null=True,
			help_text=u"Beskriv lisensmodell, leveranseform (on-prem/SaaS) og eventuelle spesielle publiseringsforhold.",
			)
	programvareleverandor = models.ManyToManyField(
			to=Leverandor,
			related_name='programvare_programvareleverandor',
			verbose_name="Programvareleverandør",
			blank=True,
			help_text=u"Primær registrering av programvareleverandør. System som bruker programvaren arver denne via kobling.",
			)
	kategorier = models.ManyToManyField(
			to=SystemKategori,
			related_name='programvare_systemkategorier',
			verbose_name="Kategorier",
			blank=True,
			help_text=u"")
	kommentar = models.TextField(
			verbose_name="Kommentar (ikke bruk)",
			blank=True,
			null=True,
			help_text=u"",
			)
	strategisk_egnethet = models.BigIntegerField(
			choices=VURDERINGER_STRATEGISK_VALG,
			verbose_name="Strategisk egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	funksjonell_egnethet = models.BigIntegerField(
			choices=VURDERINGER_FUNKSJONELL_VALG,
			verbose_name="Funksjonell egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	teknisk_egnethet = models.BigIntegerField(
			choices=VURDERINGER_TEKNISK_VALG,
			verbose_name="Teknisk egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	selvbetjening = models.BigIntegerField(
			choices=SELVBETJENING_VALG,
			verbose_name="Selvbetjening",
			blank=True,
			null=True,
			help_text=u"Dersom ja betyr dette at systemet har et brukergrensesnitt der brukere selv kan registrere nødvendig informasjon i systemet.",
			)
	livslop_status = models.BigIntegerField(
			choices=LIVSLOEP_VALG,
			verbose_name="Livsløpstatus",
			blank=True,
			null=True,
			help_text=u"",
			)
	klargjort_ny_sikkerhetsmodell = models.BigIntegerField(
			choices=VALG_KLARGJORT_SIKKERHETSMODELL,
			verbose_name="Status SMART-klienter",
			blank=True, null=True,
			help_text=u"Besnyttes for å kartlegge hvilke virksomheter som er klare for ny klientmodell uten permanent VPN.",
			)
	systemdokumentasjon_url = models.URLField(
			verbose_name="Systemdokumentasjon",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"URL til systemdokumentasjon",
			)
	til_cveoversikt_og_nyheter = models.BooleanField(
			verbose_name="Overføres til sårbarhetsoversikten (CVE/nyheter)",
			default=True,
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.programvarenavn)

	def alias_oppdelt(self):
		if self.alias == None:
			return []
		return self.alias.split()

	class Meta:
		verbose_name_plural = "Systemoversikt: Programvarer"
		default_permissions = ('add', 'change', 'delete', 'view')


DRIFTSTYPE_VALG = (
	(0, 'Ukjent miljø'),
	(1, 'Privat datasenter'),
	(2, 'Offentlig datasenter'),
)


# 2026-06-23: Exposed via /api/driftsplattformer/ (JSON class Driftsmodell) – update api_tjeneste_systemoversikt_docs.py when changing relevant API output (url name: api_tjeneste_systemoversikt_docs).
class Driftsmodell(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.CharField(
			verbose_name="Navn på driftsmodell",
			unique=True,
			max_length=100,
			blank=False,
			null=False,
			help_text=u"Navn på kjøremiljøet eller tenanten, f.eks. OpenShift PROD, Azure AKS eller SaaS-Visma.",
			)
	ansvarlig_virksomhet = models.ForeignKey(
			to=Virksomhet,
			related_name='driftsmodell_ansvarlig_virksomhet',
			on_delete=models.PROTECT,
			verbose_name="Forvalter (virksomhet)",
			blank=True,
			null=True,
			help_text=u"Virksomhet som forvalter driftsplattformen (f.eks. DIG eller sektor/virksomhet).",
			)
	kommentar = models.TextField(
			verbose_name="Kommentarer til modellen",
			blank=True,
			null=True,
			help_text=u"Notater",
			)
	leverandor = models.ManyToManyField(
			to=Leverandor,
			related_name='driftsmodell_leverandor',
			verbose_name="Leverandør som drifter driftsplattformen",
			blank=True,
			help_text=u"Basisdriftsleverandør for plattformen (f.eks. hyperscaler eller intern drift).",
			)
	underleverandorer = models.ManyToManyField(
			to=Leverandor,
			related_name='driftsmodell_underleverandorer',
			verbose_name="Underleverandører av driftsleverandør",
			blank=True,
			help_text=u"Underleverandører knyttet til plattformens basisdrift.",
			)
	avtaler = models.ManyToManyField(
			to=Avtale,
			related_name='driftsmodell_avtaler',
			verbose_name="Avtalereferanser",
			blank=True,
			)
	type_plattform = models.BigIntegerField(
			choices=DRIFTSTYPE_VALG,
			verbose_name="Type driftsmiljø",
			default=0,
			blank=False,
			null=False,
			help_text=u"Privat eller offentlig datasenter. Uavhengig av om plattformen er SaaS.",
			)
	overordnet_plattform = models.ForeignKey(
			to="Driftsmodell",
			related_name='driftsmodell_overordnet_plattform',
			verbose_name="Overordnet plattform",
			blank=True,
			null=True,
			on_delete=models.PROTECT,
			help_text=u'Dersom dette er en "plattform på en plattform" kan du her henvise til hvilken plattform denne kjører på.',
			)
	utviklingsplattform = models.BooleanField(
			verbose_name="Er utviklingsplattform?",
			blank=True, null=False,
			default=False,
			help_text=u"Legacy-felt. Egenutvikling registreres på System.er_egenutviklet.",
			)
	samarbeidspartner = models.BooleanField(
			verbose_name="Er samarbeidspartner?",
			blank=True, null=False,
			default=False,
			help_text=u"Plattform for systemer levert av samarbeidspartnere (f.eks. KS, PIT).",
			)
	er_saas = models.BooleanField(
			verbose_name="Er SaaS-plattform?",
			blank=True, null=False,
			default=False,
			help_text=u"Leverandør leverer full stack (Software as a Service). Det kan finnes flere SaaS-plattformer.",
			)
	sort_order = models.BigIntegerField(
			verbose_name="Sorteringsrekkefølge",
			default=3,
			blank=False,
			null=False,
			help_text=u'Lavere tall vises først.',
			)
	applikasjonsdriftleverandor = models.ForeignKey(
			to=Leverandor,
			related_name='driftsmodell_standard_applikasjonsleverandor',
			verbose_name="Plattformens standard applikasjonsdriftsleverandør",
			blank=True,
			null=True,
			on_delete=models.PROTECT,
			help_text=u"Hovedleverandør som sørger for at systemer fungerer som de skal på driftsplattformen.",
			)
	history = HistoricalRecords()

	def __str__(self):
		if self.ansvarlig_virksomhet:
			return u'%s (%s)' % (self.navn, self.ansvarlig_virksomhet.virksomhetsforkortelse)
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemoversikt: Driftsplattformer"
		verbose_name = "driftsplattform"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['navn']

	def antall_systemer(self):
		return self.systemer.filter(~Q(livslop_status=7)).count()

	def plattform_nivaa(self):
		if self.overordnet_plattform == None:
			return 1

		seen = []
		level = 1
		while self.overordnet_plattform != None:
			if self.overordnet_plattform in seen:
				return level
			seen.append(self.overordnet_plattform)
			level += 1
		return level


class Autorisasjonsmetode(models.Model):
	navn = models.CharField(
			verbose_name="Navn på metode",
			unique=True,
			max_length=100,
			blank=False,
			null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemkategori: Autorisasjonsmetoder"
		default_permissions = ('add', 'change', 'delete', 'view')



class Autentiseringsteknologi(models.Model):
	navn = models.CharField(
			verbose_name="Autentiseringsteknologi",
			unique=True,
			max_length=100,
			blank=False,
			null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemkategori: Autentiseringsteknologi"
		default_permissions = ('add', 'change', 'delete', 'view')


class Autentiseringsmetode(models.Model):
	navn = models.CharField(
			verbose_name="Autentiseringsnivå",
			unique=True,
			max_length=100,
			blank=False,
			null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemkategori: Autentiseringsmetoder"
		default_permissions = ('add', 'change', 'delete', 'view')


class Loggkategori(models.Model):
	navn = models.CharField(
			verbose_name="Loggtype", unique=True,
			max_length=100,
			blank=False,
			null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "System: Loggkategorier"
		default_permissions = ('add', 'change', 'delete', 'view')


DB_VALG = (
	(1, 'MSSQL: Hotell på felles IKT-plattform'),
	(2, 'MSSQL: Annen drift'),
	(3, 'Oracle: Hotell på felles IKT-plattform'),
	(4, 'Oracle: Annen drift'),
	(5, 'SQLite'),
	(6, 'PostgreSQL'),
	(7, 'MySQL'),
	(8, 'Firebird'),
)

VALG_RISIKOVURDERING_BEHOVSVURDERING = (
	(0, 'Ikke behov / inngår i annet systems risikovurdering'),
	(1, 'Bør utføres, men ikke høyt prioritert'),
	(2, 'Må utføres, prioritert'),
)



class RapportGruppemedlemskaper(models.Model):
	opprettet = models.DateTimeField(
			auto_now_add=True,
			null=True,
			)
	kategori = models.CharField(
			max_length=100,
			blank=False,
			null=False,
			)
	beskrivelse = models.CharField(
			max_length=250,
			blank=False,
			null=False,
			)
	kommentar = models.CharField(
			max_length=250,
			blank=True,
			null=True,
			)
	grupper = models.ManyToManyField(
			to=ADgroup,
			related_name='rapport_enkel',
			)
	AND_grupper = models.ManyToManyField(
			to=ADgroup,
			related_name='rapport_kombinasjon',
			blank=True,
			)
	tidslinjedata = models.TextField(
			blank=True,
			null=True,
			)

	def __str__(self):
		return f'{self.kategori} {self.beskrivelse}'

	class Meta:
		verbose_name_plural = "Rapport: Innhentingsbehov AD-grupper"
		default_permissions = ('add', 'change', 'delete', 'view')



class Oppdatering(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	tidspunkt = models.DateTimeField(
			verbose_name="Tidspunkt",
			blank=True,
			null=True,
			help_text=u"YYYY-MM-DD eksempel 2019-05-05 (tidspunkt er påkrevet - sett 'Nå')",
			)
	kommentar = models.CharField(
			verbose_name="Kort kommentar",
			max_length=200,
			blank=False, null=False,
			help_text=u""
			)
	user = models.OneToOneField(
			to=User,
			on_delete=models.PROTECT,
			)

	def __str__(self):
		return u'Oppdatering %s' % (self.pk)

	class Meta:
		verbose_name_plural = "System: Dataoppdateringer"
		default_permissions = ('add', 'change', 'delete', 'view')


class Database(models.Model):
	navn = models.CharField(
			verbose_name="Navn",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"Navn på databasetype"
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemkategori: Databasetyper"
		verbose_name = "databasetype"
		default_permissions = ('add', 'change', 'delete', 'view')



SYSTEM_COLORS = {
	"samarbeidspartner": "#ffde76",
	"ukjent": '#FFD6D6',
	"saas": '#c89df9',
	"drift_uke_privat": '#b7eb95',
	"drift_uke_sky": '#aac1ff',
	"drift_virksomhet_privat": '#b7eb95',
	"drift_virksomhet_sky": '#aac1ff',
	"infrastruktur": '#d2b5d9',
	"infrastruktur_chart": '#E0E0E0',
	"integrasjon": '#b189bb',
	"egenutviklet": '#e3b27f',
	"chart_current_system": '#D97070',
	"chart_integration": '#72A872',
	"chart_authentication": '#C988C4',
	"chart_publication": '#DCC468',
	"chart_component": '#A39ABB',
	"chart_url": '#7B9FD6',
	"chart_cmdb_bss": '#F2B26E',
	"chart_cmdb_bs": '#DE9655',
	"chart_programvare": '#1a1a1a',
	"chart_service_component": '#2A2859',
	"chart_external_system": '#9AAFC9',
}


VALG_SYSTEM_INTEGRATION_DIRECTION = (
	("RECIEVE", "Mottar opplysninger fra destinasjon"),
	("DELIVER", "Avleverer opplysninger til destinasjon"),
	("BOTH", "Overføring av opplysninger begge retninger"),
)

VALG_SYSTEM_INTEGRATION_TYPE = (
	("INTEGRATION", "Informasjonsoverføring"),
	("AUTHENTICATION", "Federert pålogging"),
	("PUBLICATION", "Applikasjonspublisering"),
	("COMPONENT", "Tilhørende systemkomponent"),
)


# 2026-06-23: Exposed via /api/systemintegrasjoner/ – update api_tjeneste_systemoversikt_docs.py when changing relevant API output (url name: api_tjeneste_systemoversikt_docs).
class SystemIntegration(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	source_system = models.ForeignKey(
			to='System',
			related_name='system_integration_source',
			on_delete=models.CASCADE,
			verbose_name="Kildesystem",
			blank=False,
			null=False,
			)
	destination_system = models.ForeignKey(
			to='System',
			related_name='system_integration_destination',
			on_delete=models.CASCADE,
			verbose_name="Destinasjonssystem",
			blank=False,
			null=False,
			)
	integration_type = models.CharField(
			choices=VALG_SYSTEM_INTEGRATION_TYPE,
			verbose_name="Type avhengighet",
			max_length=50,
			blank=False,
			null=False,
		)
	personopplysninger = models.BooleanField(
			verbose_name="Overføres personopplysninger?",
			blank=True,
			null=True,
			)
	description = models.TextField(
			verbose_name="Tekstlig beskrivelse",
			blank=True,
			null=True,
			help_text=u"Relevant informasjon om integrasjonen. F.eks. hva som overføres av informasjon, frekvens og protokoll.",
			)
	history = HistoricalRecords()

	unique_together = ('source_system', 'destination_system', 'integration_type')



	def __str__(self):
		return f'{self.integration_type} fra {self.source_system} til {self.destination_system}'

	class Meta:
		verbose_name_plural = "Systemoversikt: Systemavhengigheter"
		verbose_name = "systemintegrasjon"
		default_permissions = ('add', 'change', 'delete', 'view')

	def color(self):
		if self.integration_type == "INTEGRATION":
			return SYSTEM_COLORS["chart_integration"]
		if self.integration_type == "AUTHENTICATION":
			return SYSTEM_COLORS["chart_authentication"]
		if self.integration_type == "PUBLICATION":
			return SYSTEM_COLORS["chart_publication"]
		if self.integration_type == "COMPONENT":
			return SYSTEM_COLORS["chart_component"]

		return "black"


class Tjeneste(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.CharField(
			verbose_name="Tjenestenavn",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"Navn på tjenesten",
			)
	systemer = models.ManyToManyField(
			to='System',
			related_name='tjenester',
			verbose_name="Tilhørende systemkomponenter",
			blank=True,
			help_text=u"Tilhørende systemkomponenter tjenesten består av",
			)
	beskrivelse = models.TextField(
			verbose_name="Tjenestebeskrivelse",
			blank=True,
			null=True,
			help_text=u"Tekstlig beskrivelse av hva tjenesten går ut på",
			)
	history = HistoricalRecords()

	def __str__(self):
		return f'{self.navn}'

	class Meta:
		verbose_name_plural = "Systemoversikt: Tjenester"
		verbose_name = "tjeneste"
		default_permissions = ('add', 'change', 'delete', 'view')

	def tjenesteeier_virksomhet(self):
		virksomheter = []
		for systemkomponent in self.systemer.all():
			virksomheter.append(systemkomponent.systemeier)
		return set(virksomheter)

	def tjenesteeier_personer(self):
		personer = []
		for systemkomponent in self.systemer.all():
			personer.extend(systemkomponent.systemeier_kontaktpersoner_referanse.all())
		return set(personer)

	def tjenesteforvalter_virksomhet(self):
		virksomheter = []
		for systemkomponent in self.systemer.all():
			virksomheter.append(systemkomponent.systemforvalter)
		return set(virksomheter)

	def tjenesteforvalter_personer(self):
		personer = []
		for systemkomponent in self.systemer.all():
			personer.extend(systemkomponent.systemforvalter_kontaktpersoner_referanse.all())
		return set(personer)

	def tjenesteforvalter_epost(self):
		eposter = []
		for systemkomponent in self.systemer.all():
			eposter.append(systemkomponent.forvaltning_epost)
		return set(eposter)

	def tjenesteforvalter_organisasjonsledd(self):
		organisasjonsledd = []
		for systemkomponent in self.systemer.all():
			organisasjonsledd.append(systemkomponent.systemforvalter_avdeling_referanse)
		return set(organisasjonsledd)

	def kritisk_kapabilitet(self):
		kapabiliteter = []
		for systemkomponent in self.systemer.all():
			kapabiliteter.extend(systemkomponent.kritisk_kapabilitet.all())
		return kapabiliteter

	def los_kommunale_ord(self):
		kommunale_ord = []
		for systemkomponent in self.systemer.all():
			kommunale_ord.extend(systemkomponent.LOSref.all())
		return kommunale_ord


# 2026-06-23: Exposed via /api/systemer/ – update api_tjeneste_systemoversikt_docs.py when changing relevant API output (url name: api_tjeneste_systemoversikt_docs).
class System(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	ibruk = models.BooleanField(
			verbose_name="Er systemet i bruk?",
			blank=True,
			null=False,
			default=True,
			help_text=u"Ble tidligere benyttet for å skjule system fra noen visninger. Bruk heller Livsløpstatus-feltet.",
			)
	kvalitetssikret = models.OneToOneField(
			to=Oppdatering,
			related_name='system_kvalitetssikret',
			verbose_name="Kvalitetssikret",
			blank=True,
			null=True,
			on_delete=models.PROTECT,
			help_text=u"Tidspunkt informasjonen er kvalitetssikret.",
			)
	informasjon_kvalitetssikret = models.BooleanField(
			verbose_name="Er informasjonen kvalitetssikret av forvalter?",
			default=False,
			help_text=u"Krysses av når ansvarlig har kontrollert at opplysningene oppgitt for dette systemet stemmer. Obligatoriske felter er de som automatisk er ekspandert. Det er foreslått at denne verdien settes tilbake til 'nei' etter en viss tid, men per nå er ikke dette implementert.",
			)
	systemnavn = models.CharField(
			verbose_name="Systemnavn",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"Se <a target='_blank' href='/definisjon/System/'>definisjon av system</a>. Undersøk om systemet er registrert før du eventuelt registrerer et nytt. Tidligere navn angis under Alias. Virksomhetsforkortelse til forvalter blir lagt til automatisk i visninger. Merk at programvare som kjører på en klient skal registrers som <a target='_blank' href='/admin/systemoversikt/programvare/add/'>programvare</a>.",
			)
	alias = models.TextField(
			verbose_name="Alias",
			blank=True,
			null=True,
			help_text=u"Alternative navn på systemet for å avhjelpe søk. Kun enkeltord. Du kan skrive inn flere alias, gjerne separert med komma eller på hver sin linje. Disse alias brukes også for å søke opp tilgangsgrupper tilhørende systemet.",
			)
	systembeskrivelse = models.TextField(
			verbose_name="Systembeskrivelse",
			blank=True,
			null=True,
			help_text=u"Tekstlig beskrivelse av hva systemet gjør/brukes til",
			)
	systemeier = models.ForeignKey(
			to=Virksomhet,
			related_name='systemer_eier',
			on_delete=models.SET_NULL,
			verbose_name="Organisatorisk systemeier",
			blank=True,
			null=True,
			help_text=u"For fellessystemer er dette normalt FIN. For sektorsystemer tilhører de nærmeste byrådsavdeling. For virksomhetssystemer typisk en konkret virksomhet.",
			)
	systemeier_kontaktpersoner_referanse = models.ManyToManyField(
			to=Ansvarlig,
			related_name='system_eier_for',
			verbose_name="Systemeier (personer)",
			blank=True,
			help_text=u"Person(er) med operativt systemeierskap. Legg til hovedforvalter. Dersom dere er et forvaltningsteam, kan du angi resten av teamet under \"Godkjente Kompass-bestillere\". Hvis du ikke finner personen du leter etter, kan du legge til med +-tegnet.",
			)
	systemforvalter = models.ForeignKey(
			to=Virksomhet,
			related_name='systemer_systemforvalter',
			on_delete=models.PROTECT,
			verbose_name="Organisatorisk systemforvalter",
			blank=False,
			null=False,
			help_text=u"Virksomheten som har ansvar for forvaltning av systemet (teknologikomponenten). Normalt er dette en etat underlagt byrådsavdelingen som har systemeierskapet",
			)
	systemforvalter_kontaktpersoner_referanse = models.ManyToManyField(
			to=Ansvarlig,
			related_name='system_forvalter_for',
			verbose_name="Systemforvalter (personer)",
			blank=True,
			help_text=u"Person(er) med operativt forvalteransvar. Hvis du ikke finner personen du leter etter, kan du legge til med det grønne +-tegnet.",
			)
	systemforvalter_avdeling_referanse = models.ForeignKey(
			to='HRorg',
			related_name='system_systemforvalter_avdeling_referanse',
			verbose_name="Systemforvalter (avdeling)",
			blank=True,
			null=True,
			on_delete=models.SET_NULL,
			help_text=u"Seksjon forvaltning er plassert til. Dersom denne settes tom, vil den automatisk fylles ut basert på forvalters organisasjonstilhørighet (kjøres nattlig).",
			)
	forvaltning_epost = models.EmailField(
			verbose_name="E-post til forvaltergruppen",
			blank=True,
			null=True,
			help_text=u"Fylles ut dersom forvaltergruppen har en dedikert fellespostboks.",

			)
	superbrukere = models.TextField(
			verbose_name="Superbrukere",
			blank=True,
			null=True,
			help_text=u"Personer som kjenner systemet godt. I mange tilfeller har disse administratortilganger. Dette er personer som egner seg godt når systemet må testes grunnet endringer.",
			)
	nokkelpersonell = models.TextField(
			verbose_name="Nøkkelpersonell",
			blank=True,
			null=True,
			help_text=u"Viktige personer fra leverandører og tilsvarende",
			)
	driftsmodell_foreignkey = models.ForeignKey(
			to=Driftsmodell,
			related_name='systemer',
			on_delete=models.PROTECT,
			verbose_name="Driftsplattform",
			blank=True,
			null=True,
			help_text=u"Kjøremiljø for denne systemkomponenten. Flere miljøer = flere systemer koblet med integrasjon.",
			)
	er_egenutviklet = models.BooleanField(
			verbose_name="Er egenutviklet?",
			blank=True, null=False,
			default=False,
			help_text=u"Systemet er utviklet av kommunen, uavhengig av hvilken driftsplattform det kjører på.",
			)
	leveransemodell_fip = models.BigIntegerField(
			choices=LEVERANSEMODELL_VALG,
			verbose_name="Leveransemodell (for felles IKT-plattform)",
			blank=True,
			null=True,
			help_text=u'Brukes ifm migreringsprosjektet. Dette datafeltet bør splittes og brukes ned mot programvare.',
			)
	tjenestenivaa = models.CharField(
			verbose_name="Tjenestenivå med DIG (gamle tjenesteavtaler)",
			choices=TJENESTENIVAA_VALG,
			max_length=50,
			blank=True,
			null=True,
			help_text=u"Gammelt nivå for oppetidsgaranti (gull, sølv og brosje)",
			)
	service_offerings = models.ManyToManyField(
			to=CMDBRef,
			related_name='system',
			verbose_name="Service offerings fra Sopra Steria CMDB",
			blank=True,
			help_text=u"Her velger du alle service offerings knyttet til dette systemet. Ta kontakt med DIG om du trenger hjelp med denne koblingen.",
			)
	sikkerhetsnivaa = models.BigIntegerField(
			choices=SIKKERHETSNIVAA_VALG,
			verbose_name="Konfidensialitetsnivå",
			blank=True,
			null=True,
			help_text=u'Sikkerhetsnivå for felles IKT-plattform i hht <a target="_blank" href="https://confluence.oslo.kommune.no/x/y8seAw">Informasjonstyper og behandlingskrav</a>',
			)
	programvarer = models.ManyToManyField(
			to=Programvare,
			related_name='systemer',
			verbose_name="Tilknyttet programvare",
			blank=True,
			help_text=u"Programvare benyttet av- eller knyttet til systemet. Her kan du legge inn programvare som er installert på klienter og programvare systemet består av på serversiden. Bruk det kommersielle navnet på programvaren. For å bli varslet av DIG CSIRT om programvaresårbarheter i nyhetsbildet, må du registrere programvare her.",
			)
	avhengigheter = models.TextField(
			verbose_name="Beskrivelse av avhengigheter (fritekst)",
			blank=True,
			null=True,
			help_text=u"Her kan du gi utdypende beskrivelse knyttet til systemtekniske avhengigeheter.",
			)
	avhengigheter_referanser = models.ManyToManyField(
			to="System",
			related_name='system_avhengigheter_referanser',
			verbose_name="Systemtekniske avhengigheter til andre systemer",
			blank=True,
			help_text=u"Her lister du opp andre systemer dette systemet er avhengig av. brukes blant annet for opptegning av avhengighetsfiguren. Kan F.eks. være påloggingsportaler (AD, FEIDE, ID-porten), databasehotell (Oracle, MSSQL..), RPA-prosesser, integrasjoner osv.",
			)
	datautveksling_mottar_fra = models.ManyToManyField(
			to="System",
			related_name='system_datautveksling_mottar_fra',
			verbose_name="Mottar personopplysninger fra følgende systemer",
			blank=True,
			help_text=u"Her lister du opp systemer dette systemet mottar personopplysinger fra. Dersom overføringen skjer via en integrasjon, velges integrasjonen her.",
			)
	datautveksling_avleverer_til = models.ManyToManyField(
			to="System",
			related_name='system_datautveksling_avleverer_til',
			verbose_name="Avleverer personopplysninger til følgende systemer",
			blank=True,
			help_text=u"Her lister du opp systemer dette systemet avleverer personopplysinger til. Dersom overføringen skjer via en integrasjon, velges integrasjonen her.",
			)
	systemeierskapsmodell = models.CharField(
			choices=SYSTEMEIERSKAPSMODELL_VALG,
			verbose_name="Systemklassifisering",
			max_length=50,
			blank=True,
			null=True,
			help_text=u"I henhold til Oslo kommunes IKT-reglement.",
			)
	programvarekategori = models.BigIntegerField(
			choices=PROGRAMVAREKATEGORI_VALG,
			verbose_name="Programvaretype (flyttet til programvare)",
			blank=True,
			null=True,
			help_text=u"Anbefaler at du heller registrerer programvare og knytter programvaren til systemet.",
			)
	systemtyper = models.ManyToManyField(
			to=Systemtype,
			related_name='system_systemtyper',
			verbose_name="Grensesnitt",
			blank=True,
			help_text=u"Her beskriver hva slags type funksjon systemet har. Systmer merket med integrasjonskomponent eller infrastrukturkomponent blir skjult i en del visninger",
			)
	systemkategorier = models.ManyToManyField(
			to=SystemKategori,
			related_name='system_systemkategorier',
			verbose_name="Systemkategorier",
			blank=True,
			help_text=u"Dette er et sett med kategorier som forvaltes av DIG ved seksjon for information management (IM). Velg det som passer best.",
			)
	systemurl = models.ManyToManyField(
			to=SystemUrl,
			related_name='system_systemurl',
			verbose_name="URL",
			blank=True,
			default=None,
			help_text=u"Fylles ut dersom systemet har en web-frontend. Adressen systemet nås på via nettleser. Hvis du ikke finner adressen i listen må du opprette ny med +-tegnet.",
			)
	systemleverandor_vedlikeholdsavtale = models.BooleanField(
			verbose_name="Er det gyldig vedlikeholdsavtale med programvareleverandør?",
			default=None,
			null=True,
			help_text=u"",
			)
	systemleverandor = models.ManyToManyField(
			to=Leverandor,
			related_name='system_systemleverandor',
			verbose_name="Programvareleverandør",
			blank=True,
			help_text=u"Leverandør som har utviklet systemet. Registrer helst programvareleverandør på tilknyttet programvare.",
			)
	basisdriftleverandor = models.ManyToManyField(
			to=Leverandor,
			related_name='system_driftsleverandor',
			verbose_name="Basisdriftleverandør",
			blank=True,
			help_text=u"Leverandør som drifter plattformen systemet kjører på. Normalt tom for ren SaaS.",
			)
	applikasjonsdriftleverandor = models.ManyToManyField(
			to=Leverandor,
			related_name='system_applikasjonsdriftleverandor',
			verbose_name="Applikasjonsdriftsleverandør",
			blank=True,
			help_text=u"Leverandør som sørger for at systemet fungerer på plattformen. For SaaS er dette typisk tjenesteleverandøren.",
			)
	applikasjonsdrift_behov_databehandleravtale = models.BooleanField(
			verbose_name="Behov for (egen) DBA mot applikasjonsdriftsleverandør?",
			default=True,
			help_text=u"Kryss av når egen databehandleravtale trengs mot applikasjonsdriftsleverandør. Ofte ikke nødvendig ved SaaS dersom DBA allerede finnes.",
			)
	datamodell_url = models.URLField(
			verbose_name="Datamodell",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til beskrivelse av datamodell",
			)
	datasett_url = models.URLField(
			verbose_name="Datasett",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til beskrivelse av datasett",
			)
	api_url = models.URLField(
			verbose_name="API",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til beskrivelse av API",
			)
	kildekode_url = models.URLField(
			verbose_name="Kildekode",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til kildekode",
			)
	kontaktgruppe_url = models.URLField(
			verbose_name="Brukerstøttegruppe",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til gruppe på Viva Engage eller f.eks. en intranettside.",
			)
	high_level_design_url = models.URLField(
			verbose_name="Systemdokumentasjon",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"High level design",
			)
	low_level_design_url = models.URLField(
			verbose_name="Driftsdokumentasjon",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Low level design",
			)
	brukerdokumentasjon_url = models.URLField(
			verbose_name="Brukerdokumentasjon",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til brukerdokumentasjon",
			)
	kommentar = models.TextField(
			verbose_name="Kommentar (fritekst) (fases ut)",
			blank=True,
			null=True,
			help_text=u"Ikke bruk dette feltet",
			)
	selvbetjening = models.BigIntegerField(
			choices=SELVBETJENING_VALG,
			verbose_name="Selvbetjening (fases ut)",
			blank=True,
			null=True,
			help_text=u"Dersom ja betyr dette at systemet har et brukergrensesnitt der brukere selv kan registrere nødvendig informasjon i systemet.",
			)
	livslop_status = models.BigIntegerField(
			choices=LIVSLOEP_VALG,
			verbose_name="Livsløpstatus",
			blank=True,
			null=True,
			help_text=u"Setter du 1 under anskaffelse vil systemet anses som ikke i bruk (enda). Setter du status 5 eller 6 vil systemet havne på 'End of life (EOL)'-listen.",
			)
	strategisk_egnethet = models.BigIntegerField(
			choices=VURDERINGER_STRATEGISK_VALG,
			verbose_name="Strategisk egnethet (fases ut)",
			blank=True,
			null=True,
			help_text=u"Hvor viktig systemet er opp mot virksomhetens oppdrag",
			)
	funksjonell_egnethet = models.BigIntegerField(
			choices=VURDERINGER_FUNKSJONELL_VALG,
			verbose_name="Funksjonell egnethet",
			blank=True,
			null=True,
			help_text=u"Hvor godt systemet løser behovet",
			)
	teknisk_egnethet = models.BigIntegerField(
			choices=VURDERINGER_TEKNISK_VALG,
			verbose_name="Teknisk egnethet",
			blank=True,
			null=True,
			help_text=u"Moderne teknologi eller masse teknisk gjeld?",
			)


	#### DENNE BRUKES IKKE??
	konfidensialitetsvurdering = models.BigIntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Oppsummert konfidensialitetsvurdering (utfases)",
			blank=True,
			null=True,
			help_text=u"Hvor sensitive er opplysningene?",
			)



	integritetsvurdering = models.BigIntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Integritetsvurdering",
			blank=True,
			null=True,
			help_text=u"Hvor kritisk er det at opplysningene stemmer?",
			)
	tilgjengelighetsvurdering = models.BigIntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Tilgjengelighetsvurdering",
			blank=True,
			null=True,
			default=6,
			help_text=u"Hvor kritisk er det at systemet virker?",
			)
	tilgjengelighet_kritiske_perioder = models.TextField(
			verbose_name="Kritiske perioder og konsekvenser ved nedetid",
			blank=True,
			null=True,
			help_text=u"Her begrunner du hvorfor systemet er kritisk, samt dokumenterer perioder av året hvor det er særskilt behov for at systemet er tilgjengelig. F.eks. knyttet til frister som eiendomsskatt, barnehageopptak eller lønnskjøring.",
			)
	tilgjengelighet_periodisk_kritisk = models.BooleanField(
			verbose_name="Kritisk kun i perioder?",
			default=False,
			help_text=u"Kryss av dersom systemet kun er kritisk i visse perioder i løpet av måneden eller året.",
			)
	tilgjengelighet_timer_til_kritisk = models.BigIntegerField(
			verbose_name="Timer til kritisk",
			blank=True,
			null=True,
			help_text=u"Hvor mange timer tar det fra systemet blir utilgjengelig til det er kritisk?",
			)
	risikovurdering_behovsvurdering = models.BigIntegerField(
			choices=VALG_RISIKOVURDERING_BEHOVSVURDERING,
			verbose_name="Behov for risikovurdering?",
			blank=False, null=False, default=2, # 2: Prioriteres
			help_text=u"Brukes i grafisk fremvisning av RoS-status, samt ved utsending av varsel om utdatert risikovurdering.",
			)
	url_risikovurdering = models.URLField(
			verbose_name="Risikovurdering (URL)",
			blank=True,
			null=True,
			help_text=u"URL-referanse dersom det finnes. Om ikke kan fritekstfeltet benyttes.",
			)
	risikovurdering_tekst = models.TextField(
			verbose_name="Risikovurdering fritekst",
			blank=True,
			null=True,
			help_text=u"Ytterligere detaljer knyttet til gjennomføringen av risikovurdering for systemet.",
			)
	dato_sist_ros = models.DateTimeField(
			verbose_name="Dato sist gjennomførte risikovurdering",
			blank=True,
			null=True,
			help_text=u"YYYY-MM-DD eksempel 2019-05-05 (tidspunkt er påkrevet - sett 'Nå')",
			)
	systemtekniske_sikkerhetstiltak = models.TextField(
			verbose_name="Systemtekniske sikkerhetstiltak (oppsummering)",
			blank=True,
			null=True,
			help_text=u"fases ut til fordel for mer detaljerte spørsmål under.",
			)
	autentiseringsalternativer = models.ManyToManyField(
			to=Autentiseringsmetode,
			related_name='system_autentiseringsalternativer',
			verbose_name="Identifiseringsnivå",
			blank=True,
			help_text=u"Sikkerhetsnivå på innloggingen?",
			)
	autentiseringsteknologi = models.ManyToManyField(
			to=Autentiseringsteknologi,
			related_name='system_autentiseringsalternativer',
			verbose_name="Påloggingstjeneste",
			blank=True,
			help_text=u"Hvordan logger bruker på? Husk også å legge til systemavhengighet dersom AD/LDAP/SAML/OIDC. (Henger sammen med hvordan brukere opprettes)",
			)
	loggingalternativer = models.ManyToManyField(
			to=Loggkategori,
			related_name='system_loggingalternativer',
			verbose_name="Etablerte logger i systemet",
			blank=True,
			help_text=u"Nivå av logging etablert i systemet",
			)
	autorisasjon_differensiering_beskrivelse = models.TextField(
			verbose_name="Differensiering av tilganger med bakgrunn i roller/identitet",
			blank=True,
			null=True,
			help_text=u"Beskriv mulighetene for å differensiere tilganger med bakgrunn i roller/identitet.",
			)
	autorisasjon_differensiering_saksalder = models.TextField(
			verbose_name="Differensiering av tilganger med bakgrunn i sakenes alder",
			blank=True,
			null=True,
			help_text=u"Beskriv mulighetene for å differensiere tilganger med bakgrunn i sakenes alder ",
			)
	dataminimalisering = models.TextField(
			verbose_name="Dataminimalisering",
			blank=True,
			null=True,
			help_text=u"Beskriv systemets funksjonalitet for å sikre dataminimalisering",
			)
	sletting_av_personopplysninger = models.TextField(
			verbose_name="Sletting av personopplysninger",
			blank=True,
			null=True,
			help_text=u"(Redundant med felt på behandling) Beskriv systemets funksjonalitet for sletting av personopplysninger",
			)
	funksjonalitet_kryptering = models.TextField(
			verbose_name="Funksjonalitet for kryptering",
			blank=True,
			null=True,
			help_text=u"Beskriv funksjonalitet for kryptering (hva krypteres og hvordan, både for transport/overføring og ved lagring)",
			)
	anonymisering_pseudonymisering = models.TextField(
			verbose_name="Anonymisering og pseudonymisering",
			blank=True,
			null=True,
			help_text=u"(Redundant med felt på behandling) Beskriv funksjonalitet for anonymisering / pseudonymisering ved bruk av personopplysninger til andre formål ",
			)
	sikkerhetsmessig_overvaaking = models.TextField(
			verbose_name="Sikkerhetsovervåking",
			blank=True,
			null=True,
			help_text=u"Beskriv hva slags aktiv overvåking av logger og hendelser som gjelder for systemet. Hvem utfører dette og hvor ofte?",
			)
	kontaktperson_innsyn = models.ManyToManyField(
			to=Ansvarlig,
			related_name='system_kontaktperson_innsyn',
			verbose_name="Kontaktperson innsyn",
			blank=True,
			help_text=u"Person som kan kontaktes for å undersøke om det er personopplysninger i systemet knyttet til en innsynsbegjæring. Dersom du ikke finner personen du leter etter kan du legge til ny med +-tegnet.",
			)
	innsyn_innbygger = models.BooleanField(
			verbose_name="Innsyn relevant for innbyggere?",
			default=True,
			help_text=u"Er det aktuelt å søke igjennom dette systemet etter personopplysninger ved innsynsbegjæring fra en innbygger.",
			)
	innsyn_ansatt = models.BooleanField(
			verbose_name="Innsyn relevant for ansatte?",
			default=True,
			help_text=u"Er det aktuelt å søke igjennom dette systemet etter personopplysninger ved innsynsbegjæring fra en ansatt",
			)
	kjente_mangler = models.TextField(
			verbose_name="Kjente mangler i systemet",
			blank=True,
			null=True,
			help_text=u"Felt forvalter kan benytte for å notere ned kjente mangler.",
			)
	informasjonsklassifisering = models.ManyToManyField(
			to=InformasjonsKlasse,
			related_name='system_informasjonsklassifisering',
			verbose_name="Informasjonsklassifisering",
			blank=True,
			help_text=u"Velg de kategorier som er aktuelle.",
			)
	isolert_drift = models.BooleanField(
			verbose_name="På Tilpasset drift (felles IKT-plattform)",
			default=False,
			help_text=u"Krysses av dersom systemet ikke kan oppgraderes og derfor er spesielt adskilt fra andre systemer på plattformen.",
			)
	database_supported = models.ManyToManyField(
			to='Database',
			related_name='system_database_supported',
			verbose_name="Støttede databaser",
			blank=True,
			help_text=u"Legg til alle typer databaser som støttes av systemet.",
			)
	database_in_use = models.ManyToManyField(
			to='Database',
			related_name='system_database_in_use',
			verbose_name="Databasetype i bruk",
			blank=True,
			help_text=u"Legg til alle typer databaser er i bruk for dette systemet.",
			)
	godkjente_bestillere = models.ManyToManyField(
			to=Ansvarlig,
			related_name='system_godkjente_bestillere',
			verbose_name="Godkjente Kompass-bestillere",
			blank=True,
			help_text=u"Forvaltere er autorisert til å bestille endringer på systemet i Kompass. Her kan du gjerne legge inn hele forvalterteamet rundt systemet. Hvis du ikke finner personen du leter etter, kan du legge til med +-tegnet.",
			)
	er_arkiv = models.BooleanField(
			verbose_name="Er systemet et arkiv?",
			default=False,
			help_text=u"Krysses av dersom systemet er et arkivsystem i henhold til arkivlovverk.",
			)
	antall_brukere = models.BigIntegerField(
			verbose_name="Antall brukere",
			blank=True,
			null=True,
			help_text=u"Hvor mange bruker systemet totalt? (Manuell angivelse. Mulig vi i fremtiden vil kalkulere denne automatisk dersom AD-grupper er angitt)",
			)
	tilgangsgrupper_ad = models.ManyToManyField(
			to=ADgroup,
			related_name='system_referanse',
			verbose_name="Tilhørende tilgangsgrupper (AD)",
			blank=True,
			help_text=u"Her velger du hvilke AD-grupper som hører til systemet, slik at vi kan holde oversikt over tilganger og hvem som ligger i gruppene. "
			u"Som regel én gang i døgnet oppdateres automatisk hvilke virksomheter som står registrert som brukere av systemet — ut fra medlemmene i gruppene og opplysningene som finnes i Kartoteket. "
			u"Nye virksomheter kan da komme med på lista. Har en virksomhet vært markert som «ikke i bruk», men har fortsatt folk i gruppene, vil den bli satt i bruk igjen automatisk.",
			)
	legacy_klient_krever_smb = models.BooleanField(
			verbose_name="Direkte kommunikasjon med filområder?",
			blank=True,
			null=True,
			help_text=u"Settes dersom systemets klient må kommunisere direkte med on-prem filområder. OneDrive er ikke on-prem og er derfor ikke en grunnlag for å sette 'ja' på denne. Settes til 'ja' dersom minst ét av grensesnittene krever on-prem filområdetilgang.",
			)
	legacy_klient_krever_direkte_db = models.BooleanField(
			verbose_name="Direkte kommunikasjon med databaseserver fra klient?",
			blank=True,
			null=True,
			help_text=u"Settes dersom systemets klient må kommunisere direkte med databaser. Settes til 'ja' dersom minst ét av grensesnittene krever dette.",
			)
	legacy_klient_krever_onprem_lisensserver = models.BooleanField(
			verbose_name="Legacy: Krever on-prem lisensserver?",
			blank=True,
			null=True,
			help_text=u"Settes dersom systemet krever at klient har direktekontakt med on-prem lisensserver.",
			)
	legacy_klient_autentisering = models.BooleanField(
			verbose_name="Legacy klientautentisering?",
			blank=True,
			null=True,
			help_text=u"Settes dersom systemet ikke støtter moderne autentisering (SAML/OIDC)",
			)
	enterprise_applicatons = models.ManyToManyField(
			to="AzureApplication",
			related_name='systemreferanse',
			verbose_name="Tilhørende Microsoft service principals",
			help_text=u"Brukes for å koble systemet til enterprise applications for single sign-on eller for graph-tilganger.",
			blank=True,
			)
	LOSref = models.ManyToManyField(
			to="LOS",
			related_name='systemer',
			verbose_name="Begrepstagging (LOS)",
			blank=True,
			help_text=u"Her kan du tagge systemet med informasjonsområder (kommunale områder) standardiserte LOS-begreper forvaltet av DigDir. Du finner både tema og ord i listen. Anbefaler at du primært velger tema fra listen og sekundært andre ord som supplerer. Ord kan være knyttet til flere tema, så det er ikke mulig å entydig automatisk velge riktig tema basert på ord. Oversikten over behandlinger hensyntar bare på koblinger mot tema.",
			)
	klargjort_ny_sikkerhetsmodell = models.BigIntegerField(
			choices=VALG_KLARGJORT_SIKKERHETSMODELL,
			verbose_name="Status klargjort for ny sikkerhetsmodell",
			blank=True, null=True,
			help_text=u"Benyttes av DIG for å kartlegge hvilke virksomheter som er klare for ny klientmodell uten permanent VPN.",
			)
	kritisk_kapabilitet = models.ManyToManyField(
			to=KritiskKapabilitet,
			related_name="systemer",
			verbose_name="Kritisk kapabilitet",
			blank=True,
			help_text=u"Understøtter systemet en kritisk funksjon? Kategorier basert på rammeverket fra DSB."
			)
	inv_konklusjon = models.CharField(
			verbose_name="Konklusjon modernisering",
			max_length=250,
			blank=True,
			null=True,
			)
	inv_konklusjon_beskrivelse = models.TextField(
			verbose_name="Detaljert konklusjon modernisering",
			blank=True,
			null=True,
			)
	dato_etablert = models.DateField(
			verbose_name="Dato systemet ble tatt i bruk",
			null=True,
			blank=True,
			)
	dato_end_of_life = models.DateField(
			verbose_name="Dato systemet skal fases ut eller ble faset ut",
			null=True,
			blank=True,
			)
	arkivkommentar = models.TextField(
			verbose_name="Arkivars kommentarer til systemet",
			blank=True,
			null=True,
			)
	citrix_publications = models.ManyToManyField(
			to="CitrixPublication",
			related_name="systemer",
			verbose_name="Tilhørende citrix-publiseringer",
			blank=True,
			help_text=u"Her velger du citrix-publiseringer som brukes i forbindelse med systemet."
		)
	history = HistoricalRecords()

	unique_together = ('systemnavn', 'systemforvalter')

	def __str__(self):
		try:
			return f'{self.systemnavn} ({self.systemforvalter.virksomhetsforkortelse})'
		except:
			return f'{self.systemnavn}'

	def los_ord(self):
		words = list()
		for word in self.LOSref.all():
			if not word.er_tema():
				words.append(word)
		return words

	def alias_oppdelt(self):
		if self.alias == None:
			return []
		return self.alias.split()

	def unike_server_os(self):
		server_os = []
		try:
			for bss in self.service_offerings.all():
				for server in bss.servers.all():
						server_os.append("%s %s" % (server.comp_os, server.comp_os_version))
		except:
			pass
		return list(set(server_os))

	def save(self, *args, **kwargs):
		self.ibruk = self.er_ibruk()
		super(System, self).save(*args, **kwargs)

	def felles_sektorsystem(self):
		if self.systemeierskapsmodell in ("FELLESSYSTEM", "SEKTORSYSTEM", "TVERRSEKTORIELT"):
			return True
		else:
			return False

	def databaseplattform(self):
		databaser = []
		alle_bss = self.service_offerings.all()
		for bss in alle_bss:
			alle_db = CMDBdatabase.objects.filter(sub_name=bss)
			for db in alle_db:
				databaser.append("%s" % (db.db_version))
		if len(databaser) > 0:
			return ', '.join([db for db in set(databaser)])
		#fallback to manual field
		return ', '.join([db.navn for db in self.database_in_use.all()])

	def serverplattform(self):
		serveros = []
		alle_bss = self.service_offerings.all()
		for bss in alle_bss:
			servere = CMDBdevice.objects.filter(service_offerings=bss)
			for s in servere:
				serveros.append("%s %s" % (s.comp_os, s.comp_os_version))
		return ', '.join([os for os in set(serveros)])

	def er_infrastruktur(self):
		for stype in self.systemtyper.all():
			if stype.er_infrastruktur:
				return True
		else:
			return False

	def er_integrasjon(self):
		for stype in self.systemtyper.all():
			if stype.er_integrasjon:
				return True
		else:
			return False

	def er_selvutviklet(self):
		return self.er_egenutviklet

	def er_samarbeidspartner(self):
		try:
			if self.driftsmodell_foreignkey.samarbeidspartner:
				return True
		except:
			pass

		return False

	def er_privat_sky(self):
		try:
			if self.driftsmodell_foreignkey.type_plattform == 1:
				return True
		except:
			return False

	def mangler_driftsmodell(self):
		if self.driftsmodell_foreignkey == None:
			return True

	def driftes_av_dig(self):
		try:
			virksomhet = self.driftsmodell_foreignkey.ansvarlig_virksomhet
			if virksomhet and virksomhet.virksomhetsforkortelse == "DIG":
				return True
		except:
			pass
		return False

	def drift_dimensjoner(self):
		dm = self.driftsmodell_foreignkey
		if dm is None:
			return {
				"ukjent": True,
				"saas": False,
				"samarbeidspartner": False,
				"egenutviklet": self.er_egenutviklet,
				"privat_datasenter": False,
				"offentlig_datasenter": False,
				"driftes_av_dig": False,
			}
		return {
			"ukjent": False,
			"saas": bool(dm.er_saas),
			"samarbeidspartner": bool(dm.samarbeidspartner),
			"egenutviklet": self.er_egenutviklet,
			"privat_datasenter": dm.type_plattform == 1,
			"offentlig_datasenter": dm.type_plattform == 2,
			"driftes_av_dig": self.driftes_av_dig(),
		}

	def drift_color_segment(self):
		d = self.drift_dimensjoner()
		if d["ukjent"]:
			return "ukjent"
		if d["samarbeidspartner"]:
			return "samarbeidspartner"
		if d["saas"]:
			return "saas"
		if d["privat_datasenter"]:
			if d["driftes_av_dig"]:
				return "drift_uke_privat"
			return "drift_virksomhet_privat"
		if d["driftes_av_dig"]:
			return "drift_uke_sky"
		return "drift_virksomhet_sky"

	def er_saas(self):
		try:
			if self.driftsmodell_foreignkey.er_saas:
				return True
		except:
			pass
		return False

	def forventet_url(self):
		for systemtype in self.systemtyper.all():
			if systemtype.har_url:
				return True
		return False

	def antall_avhengigheter(self): # SER IKKE UT TIL Å VÆRE I BRUK
		return len(self.system_integration_source.all()) + len(self.system_integration_destination.all())

	def antall_bruk(self):
		bruk = SystemBruk.objects.filter(system=self.pk)
		return bruk.count()

	def er_ibruk(self):
		if self.livslop_status in [1,6,7]:
			return False
		return True

	def color(self):
		return SYSTEM_COLORS[self.drift_color_segment()]


	# brukes bare av dashboard, flyttes dit? ("def statusTjenestenivaa(systemer)")
	def fip_kritikalitet(self):
		if hasattr(self, 'bs_system_referanse'):
			kritikalitet = []
			for ref in self.service_offerings.all():
				if ref.environment == 1: # 1 er produksjon
					kritikalitet.append(ref.kritikalitet)

			if len(kritikalitet) == 1:
				return kritikalitet[0] # alt OK, bare én prod valgt
			else:
				return None
		else:
			return None

	def fip_kritikalitet_text(self):
		if hasattr(self, 'bs_system_referanse'):
			prod_referanser = []
			for ref in self.system.all():
				if ref.environment == 1: # 1 er produksjon
					prod_referanser.append(ref)
			if len(prod_referanser) == 1:
				return prod_referanser[0].get_kritikalitet_display()
			else:
				return("Uklart, flere PROD-koblinger")
		else:
			return None

	def sist_endret_av(self):
		from django.contrib.contenttypes.models import ContentType
		from django.contrib.admin.models import LogEntry
		system_content_type = ContentType.objects.get_for_model(self)
		try:
			return LogEntry.objects.filter(content_type=system_content_type).filter(object_id=self.pk).order_by('-action_time')[0]
		except:
			return None

	def databehandleravtaler_system(self):
		from systemoversikt.models import Avtale
		try:
			return Avtale.objects.filter(for_system=self.pk).filter(avtaletype=1) #1=databehandleravtale
		except:
			return None

	def databehandleravtaler_drift(self):
		try:
			avtaler = self.driftsmodell_foreignkey.avtaler.all()
		except:
			return None
		databehandleravtaler = []
		for avtale in avtaler:
			if avtale.avtaletype == 1: #1=databehandleravtale
				databehandleravtaler.append(avtale)
		return databehandleravtaler

	def _beregn_systemprioritet(self):
		import re
		tilgjengelighet = self.tilgjengelighetsvurdering
		if tilgjengelighet is None:
			tilgjengelighet = 5

		# 2026-06-23: M2M manager is never None – exists() distinguishes linked vs unlinked offerings.
		if self.service_offerings.exists():
			tjenestenivaa = 4
			for bss in self.service_offerings.all():
				if bss.operational_status == 1:# and bss.er_produksjon:
					try:
						bss_tjenestenivaa = int(re.findall(r'T(\d+)', bss.u_service_availability)[0])
						if bss_tjenestenivaa < tjenestenivaa:
							tjenestenivaa = bss_tjenestenivaa
					except:
						pass

			kritikalitet = 5
			for bss in self.service_offerings.all():
				if bss.operational_status == 1:# and bss.er_produksjon:
					try:
						bss_kritikalitet = int(re.findall(r'\d+', bss.u_service_operation_factor)[0])
						if bss_kritikalitet < kritikalitet:
							kritikalitet = bss_kritikalitet
					except:
						pass
		else: # ingen CMDB-kobling finnes
			tjenestenivaa = 2
			kritikalitet = 2 # balanse mellom å la ikke-kritiske systemer havne for høyt på prioritet og at kritiske systemer havner for langt ned på listen dersom ikke koblet til tjeneste

		sammfunnskritisk = 2
		if len(self.kritisk_kapabilitet.all()) > 0:
			sammfunnskritisk = 1

		score = tilgjengelighet * tjenestenivaa * kritikalitet * sammfunnskritisk
		return tilgjengelighet, tjenestenivaa, kritikalitet, sammfunnskritisk, score

	def systemprioritet_poeng(self):
		*_, score = self._beregn_systemprioritet()
		return score

	def systemprioritet(self):
		tilgjengelighet, tjenestenivaa, kritikalitet, sammfunnskritisk, score = self._beregn_systemprioritet()
		return f"{tilgjengelighet}*{tjenestenivaa}*{kritikalitet}*{sammfunnskritisk}={score}"

	def citrix_publiseringer_pk(self):
		navn = self.systemnavn.split()
		#print(navn)
		alias = self.alias_oppdelt()
		#print(alias)
		words = navn + alias
		#print(words)
		hits = []
		for w in words:
			if len(w) > 2:
				hits.extend((list(CitrixPublication.objects.filter(publikasjon_json__icontains=w))))
		return hits

	def citrix_publiseringer(self):
		hits = self.citrix_publiseringer_pk()

		if hits:
			for t in hits:
				t.publikasjon_json = json.loads(t.publikasjon_json)
			return hits
		else:
			return None

	def vis_autentisering(self):
		relevante_integrasjoner = SystemIntegration.objects.filter(source_system=self).filter(integration_type="AUTHENTICATION")
		if len(relevante_integrasjoner) > 0:
			return [i.destination_system for i in relevante_integrasjoner]
		else:
			return self.autentiseringsteknologi.all()

	def eiere(self):
		brukernavn = set()
		forvaltere = [ansvarlig.brukernavn.username for ansvarlig in self.systemforvalter_kontaktpersoner_referanse.all()]
		eiere = [ansvarlig.brukernavn.username for ansvarlig in self.systemeier_kontaktpersoner_referanse.all()]
		brukernavn.update(forvaltere)
		brukernavn.update(eiere)
		#print(f"{forvaltere} og {eiere} og unike brukernavn {brukernavn}")
		return brukernavn

	def vulnerabilities(self):
		connected_vulns = set()
		for service_offering in self.service_offerings.all():
			#print(service_offering)
			for server in service_offering.servers.all():
				#print(server)
				for vuln in server.qualys_vulnerabilities.all():
					if vuln.severity in [4,5]:
						vuln.tmp_offering = service_offering # brukes kun i template
						connected_vulns.add(vuln)
		#print(connected_vulns)
		return list(connected_vulns)

	def vulnerabilities_old(self):
		num_days_old = 45
		connected_vulns = set()
		datetime_limit = timezone.now() - timedelta(days=num_days_old)
		for service_offering in self.service_offerings.all():
			#print(service_offering)
			for server in service_offering.servers.all():
				#print(server)
				for vuln in server.qualys_vulnerabilities.filter(first_seen__lt=datetime_limit, severity__in=[4,5], akseptert=False):
					#if vuln.severity in [4,5]:
					vuln.tmp_offering = service_offering # brukes kun i template
					connected_vulns.add(vuln)
		#print(connected_vulns)
		return connected_vulns

	def kontakt_forvalter(self):
		if len(self.systemforvalter_kontaktpersoner_referanse.all()) > 0:
			return self.systemforvalter_kontaktpersoner_referanse.all()[0].brukernavn.email
		else:
			return "ukjent"

	def kontakt_ikthoved(self):
		if len(self.systemforvalter.ikt_kontakt.all()) > 0:
			return self.systemforvalter.ikt_kontakt.all()[0].brukernavn.email
		else:
			return "ukjent"


	def antall_oppdateringer(self):
		system_content_type = ContentType.objects.get_for_model(self)
		return len(LogEntry.objects.filter(content_type=system_content_type).filter(object_id=self.pk))

	def vis_konfidensialitet(self):
		VALG = {
			4: '5 🔴 Gradert',
			3: '4 🔴 Strengt beskyttet',
			5: '3 🔴 Beskyttet',
			2: '2 🟡 Intern',
			1: '1 🟢 Åpen',
		}
		try:
			return VALG[self.sikkerhetsnivaa]
		except:
			return "0 ?"

	def vis_tilgjengelighet(self):
		VALG = {
			1: '5 🔴 Svært alvorlig',
			2: '4 🔴 Alvorlig',
			3: '3 🟡 Moderat',
			4: '2 🟢 Lav',
			5: '1 🟢 Ubetydelig',
			6: '0 ?',
		}
		try:
			return VALG[self.tilgjengelighetsvurdering]
		except:
			return "0 ?"

	def vis_integritetsvurdering(self):
		VALG = {
			1: '5 🔴 Svært alvorlig',
			2: '4 🔴 Alvorlig',
			3: '3 🟡 Moderat',
			4: '2 🟢 Lav',
			5: '1 🟢 Ubetydelig',
			6: '0 ?',
		}
		try:
			return VALG[self.integritetsvurdering]
		except:
			return "0 ?"


	class Meta:
		verbose_name_plural = "Systemoversikt: Systemer"
		default_permissions = ('add', 'change', 'delete', 'view')



TYPE_SIKKERHETSTEST = (
	(1, 'Intern infrastrukturtesting'),
	(2, 'Ekstern infrastrukturtesting'),
	(3, 'Web-applikasjonstesting'),
	(4, 'Kildekodegjennomgang'),
	(5, 'Mobile applikasjoner'),
	(6, 'Konfigurasjonsgjennomgang'),
	(7, 'Sosial manipulering'),
)

class Sikkerhetstester(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	systemer = models.ManyToManyField(
			to=System,
			related_name='sikkerhetstest_systemer',
			verbose_name="Systemer testet",
			blank=False,
			)
	type_test = models.BigIntegerField(
			choices=TYPE_SIKKERHETSTEST,
			verbose_name="Type sikkerhetstest",
			blank=False, null=True,
			help_text=u"Velg mest aktuelle som definert på <a href='https://confluence.oslo.kommune.no/x/eww4B'>Confluence</a> (trenger ny link)",
			)
	rapport = models.URLField(
			verbose_name="Link til rapport",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Ikke i bruk. Linker brekker..",
			)
	dato_rapport = models.DateTimeField(
			verbose_name="Dato for sluttføring av rapport",
			blank=False,
			null=True,
			help_text=u"(tidspunkt er påkrevet - sett 'Nå')"
			)
	testet_av = models.ForeignKey(
			to=Leverandor,
			related_name='sikkerhetstest_testet_av',
			on_delete=models.PROTECT,
			verbose_name="Testet av (leverandør)",
			null=True,
			blank=True,
			help_text=u'Den som har utført testen, enten en leverandør eller en etat',
			)
	notater = models.TextField(
			verbose_name="Omfang av test og andre notater",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s: %s' % (self.testet_av, self.dato_rapport)

	class Meta:
		verbose_name_plural = "Systemoversikt: Sikkerhetstester"
		verbose_name = "sikkerhetstest"
		default_permissions = ('add', 'change', 'delete', 'view')


VURDERING_AVTALESTATUS_VALG = (
	(1, "1 Dårlig"),
	(2, "2 Store mangler"),
	(3, "3 Akseptbel"),
	(4, "4 God"),
	(5, "5 Meget god"),
)

IBRUK_VALG = (
	(1, "Ja"),
	(2, "Nei"),
	(3, "Kanskje"),
	(4, "Planlagt"),
)



class ProgramvareBruk(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	brukergruppe = models.ForeignKey(
			to=Virksomhet,
			on_delete=models.PROTECT,
			blank=False, null=False,
			related_name='programvarebruk_brukergruppe',
			)
	programvare = models.ForeignKey(
			to=Programvare,
			on_delete=models.PROTECT,  # slett ProgramvareBruken når Programvaren slettes
			related_name='programvarebruk_programvare',
			blank=False, null=False,
			)
	ibruk = models.BooleanField(
			verbose_name="Er programvaren i bruk?",
			blank=False,
			null=False,
			default=True,
			help_text=u"Er i bruk ved kryss, og 'ikke i bruk' når kryss fjernes. Kan fjernes i stedet for å slette koblingen og lokale vurderinger.",
			)
	livslop_status = models.BigIntegerField(
			choices=LIVSLOEP_VALG,
			verbose_name="Livsløpstatus",
			blank=True,
			null=True,
			help_text=u"",
			)
	kommentar = models.TextField(
			verbose_name="Kommentarer til denne bruken",
			blank=True,
			null=True,
			help_text=u"Utdyp hva programvaren brukes til hos din virksomhet.",
			)
	programvareeierskap = models.TextField(
			verbose_name="Programvareeierskap (fritekst)",
			blank=True,
			null=True,
			help_text=u"",
			)
	antall_brukere = models.BigIntegerField(
			verbose_name="Antall brukere",
			blank=True,
			null=True,
			help_text=u"Hvor mange bruker programvaren hos dere? (fylles ut dersom relevant)",
			)
	avtaletype = models.CharField(
			verbose_name="Avtaletype",
			max_length=250,
			blank=True,
			null=True,
			help_text=u"",
			)
	avtalestatus = models.BigIntegerField(
			choices=VURDERING_AVTALESTATUS_VALG,
			verbose_name="Avtalestatus",
			blank=True,
			null=True,
			help_text=u"",
			)
	avtale_kan_avropes = models.BooleanField(
			verbose_name="Avtale kan avropes av andre virksomheter",
			blank=True,
			null=True,
			help_text=u"",
			)
	borger = models.BigIntegerField(
			choices=IBRUK_VALG,
			verbose_name="For borger?",
			blank=True,
			null=True,
			help_text=u"",
			)
	kostnader = models.BigIntegerField(
			verbose_name="Kostnader for programvaren",
			blank=True,
			null=True,
			help_text=u"",
			)
	strategisk_egnethet = models.BigIntegerField(
			choices=VURDERINGER_STRATEGISK_VALG,
			verbose_name="Strategisk egnethet",
			blank=True, null=True,
			help_text=u"",
			)
	funksjonell_egnethet = models.BigIntegerField(
			choices=VURDERINGER_FUNKSJONELL_VALG,
			verbose_name="Funksjonell egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	teknisk_egnethet = models.BigIntegerField(
			choices=VURDERINGER_TEKNISK_VALG,
			verbose_name="Teknisk egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	lokal_kontakt = models.ManyToManyField(
			to=Ansvarlig,
			related_name='programvarebruk_lokal_kontakt',
			verbose_name="Lokal kontakt",
			blank=True,
			help_text=u"Kontaktperson for virksomhetens bruk av programvaren",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s - %s' % (self.programvare, self.brukergruppe)

	class Meta:
		verbose_name_plural = "Organisasjon: Programvarebruk"
		unique_together = ('programvare', 'brukergruppe')
		default_permissions = ('add', 'change', 'delete', 'view')



# 2026-06-23: Exposed via /api/systembruk/ – update api_tjeneste_systemoversikt_docs.py when changing relevant API output (url name: api_tjeneste_systemoversikt_docs).
class SystemBruk(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	brukergruppe = models.ForeignKey(
			to=Virksomhet,
			related_name='systembruk_brukergruppe',
			verbose_name="Brukergruppe",
			on_delete=models.PROTECT,
			blank=False,
			null=False,
			)
	system = models.ForeignKey(
			to=System,
			related_name='systembruk_system',
			verbose_name="System som brukes",
			blank=False,
			null=False,
			on_delete=models.PROTECT,  # slett SystemBruken når Systemet slettes
			)
	ibruk = models.BooleanField(
			verbose_name="Er systemet i bruk?",
			blank=False,
			null=False,
			default=True,
			help_text=u"Er i bruk ved kryss, og 'ikke i bruk' når kryss fjernes. Kan fjernes i stedet for å slette koblingen og lokale vurderinger.",
			)
	systemforvalter = models.ForeignKey(
			to=Virksomhet,
			related_name='systembruk_systemforvalter',
			on_delete=models.SET_NULL,
			verbose_name="Lokal kontaktperson",
			blank=True,
			null=True,
			help_text=u"Lokal kontaktperson for virksomhets bruk av systemet",
			)
	systemforvalter_kontaktpersoner_referanse = models.ManyToManyField(
			to=Ansvarlig,
			related_name='systembruk_forvalter_for',
			verbose_name="Lokal forvalter (person)",
			blank=True,
			help_text=u"Dersom fellesløsning på applikasjonshotell, hvilke roller/personer fyller rollen som lokal forvalter?",
			)
	systemeier_kontaktpersoner_referanse = models.ManyToManyField(
			to=Ansvarlig,
			related_name='systembruk_systemeier_kontaktpersoner',
			verbose_name="Lokal eier (person)",
			blank=True,
			help_text=u"Dersom fellesløsning på applikasjonshotell, hvilke roller/personer fyller rollen som lokal eier?",
			)
	livslop_status = models.BigIntegerField(			##SLETT##
			choices=LIVSLOEP_VALG,
			verbose_name="Livsløpstatus",
			blank=True,
			null=True,
			help_text=u"",
			)
	avhengigheter_referanser = models.ManyToManyField(			##SLETT##
			to="System",
			related_name='systembruk_avhengigheter_referanser',
			verbose_name="Systemtekniske avhengigheter til andre systemer",
			blank=True,
			help_text=u"Avvikles: Andre systemer dette systemet har systemtekniske avhengigheter til.",
			)
	avhengigheter = models.TextField(			##SLETT##
			verbose_name="Avhengigheter (fritekst)",
			blank=True,
			null=True,
			help_text=u"Avvikles: Moduler og eksterne/interne integrasjoner som er i bruk",
			)
	kommentar = models.TextField(
			verbose_name="Kommentarer til denne bruken",
			blank=True,
			null=True,
			help_text=u"Utdyp hva systemet brukes til hos din virksomhet.",
			)
	systemeierskap = models.TextField(
			verbose_name="Systemeierskap (fritekst)",
			blank=True,
			null=True,
			help_text=u"Hvis det er behov for å presisere eierskapet utover det som står på systemsiden.")
	driftsmodell_foreignkey = models.ForeignKey(			##SLETT##
			to=Driftsmodell,
			related_name='systembruk_driftsmodell',
			on_delete=models.SET_NULL,
			verbose_name="Driftsmodell / plattform (for denne bruken)",
			blank=True,
			null=True,
			help_text=u"Dette feltet blir faset ut. Dette er spesifisert på systemet.",
			)
	antall_brukere = models.BigIntegerField(  #reintrodusert 31.08.2020
			verbose_name="Antall brukere?",
			blank=True,
			null=True,
			help_text=u"Ca hvor mange bruker systemet hos dere? (fylles ut dersom relevant)",
			)
	konfidensialitetsvurdering = models.BigIntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Konfidensialitetsvurdering",
			blank=True,
			null=True,
			help_text=u"Hvor sensitive er opplysningene?",
			)
	integritetsvurdering = models.BigIntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Integritetsvurdering",
			blank=True,
			null=True,
			help_text=u"Hvor kritisk er det at opplysningene stemmer?",
			)
	tilgjengelighetsvurdering = models.BigIntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Tilgjengelighetsvurdering",
			blank=True,
			null=True,
			help_text=u"Hvor kritisk er det om systemet ikke virker?",
			)
	avtaletype = models.CharField(			##SLETT##
			verbose_name="Avtaletype (fritekst)",
			max_length=250,
			blank=True,
			null=True,
			help_text=u"",
			)
	avtalestatus = models.BigIntegerField(			##SLETT##
			choices=VURDERING_AVTALESTATUS_VALG,
			verbose_name="Avtalestatus",
			blank=True,
			null=True,
			help_text=u"",
			)
	avtale_kan_avropes = models.BooleanField(			##SLETT##
			verbose_name="Avtale kan avropes av andre virksomheter",
			blank=True,
			null=True,
			help_text=u"",
			)
	#borger = models.BigIntegerField(blank=True, null=True, choices=IBRUK_VALG,
	#		verbose_name="For borger?",
	#		help_text=u"",
	#		)
	kostnadersystem = models.BigIntegerField(			##SLETT##
			verbose_name="Kostnader for system",
			blank=True,
			null=True, help_text=u"",
			)
	systemeierskapsmodell = models.CharField(			##SLETT##
			choices=SYSTEMEIERSKAPSMODELL_VALG,
			verbose_name="Systemeierskapsmodell",
			max_length=30,
			blank=True,
			null=True,
			help_text=u"Feltet skal avvikles da dette settes på systemet, ikke bruken",
			)
	programvarekategori = models.BigIntegerField(			##SLETT##
			choices=PROGRAMVAREKATEGORI_VALG,
			verbose_name="Programvarekategori",
			blank=True,
			null=True,
			help_text=u"Feltet skal avvikles. Har ikke noe her å gjøre.",
			)
	strategisk_egnethet = models.BigIntegerField(			##SKAL VI BEHOLDE DISSE?
			choices=VURDERINGER_STRATEGISK_VALG,
			verbose_name="Strategisk egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	funksjonell_egnethet = models.BigIntegerField(			##SKAL VI BEHOLDE DISSE?
			choices=VURDERINGER_FUNKSJONELL_VALG,
			verbose_name="Funksjonell egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	teknisk_egnethet = models.BigIntegerField(			##SKAL VI BEHOLDE DISSE?
			choices=VURDERINGER_TEKNISK_VALG,
			verbose_name="Teknisk egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	url_risikovurdering = models.URLField(
			verbose_name="Risikovurdering (URL)",
			blank=True,
			null=True,
			help_text=u"URL-referanse dersom det finnes. Om ikke kan fritekstfeltet under benyttes.",
			)
	risikovurdering_tekst = models.TextField(
			verbose_name="Risikovurdering fritekst",
			blank=True,
			null=True,
			help_text=u"Ytterligere detaljer knyttet til gjennomføringen av risikovurdering for systemet.",
			)
	dato_sist_ros = models.DateTimeField(
			verbose_name="Dato sist gjennomførte risikovurdering",
			blank=True,
			null=True,
			help_text=u"(tidspunkt er påkrevet - sett 'Nå')",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s - %s' % (self.system, self.brukergruppe)

	class Meta:
		verbose_name_plural = "Organisasjon: Systembruk"
		unique_together = ('system', 'brukergruppe')
		default_permissions = ('add', 'change', 'delete', 'view')


class WANLokasjon(models.Model):
	lokasjons_id = models.CharField(
			unique=True,
			verbose_name="Lokasjons ID",
			blank=False,
			null=False,
			max_length=15,
			)
	virksomhet = models.ForeignKey(
			to=Virksomhet,
			on_delete=models.SET_NULL,
			verbose_name="Virksomhetstilhørighet",
			blank=True,
			null=True,
			)
	aksess_type = models.TextField(
			verbose_name="Aksesstype",
			blank=True,
			null=True,
			)
	adresse = models.TextField(
			verbose_name="Lokasjonsadresse",
			blank=True,
			null=True,
		)
	beskrivelse = models.TextField(
			verbose_name="Beskrivelse",
			blank=False,
			null=False,
			)

	def __str__(self):
		return u'%s' % (self.lokasjons_id)

	class Meta:
		verbose_name_plural = "CMDB: WAN Lokasjoner"
		default_permissions = ('add', 'change', 'delete', 'view')


class AzureUser(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	guid = models.TextField(
			verbose_name="guid",
			unique=True,
		)
	userPrincipalName = models.TextField(
			verbose_name="userPrincipalName",
			blank=True, null=True,
		)
	displayName = models.TextField(
			verbose_name="displayName",
			blank=True, null=True,
		)
	mail = models.TextField(
			verbose_name="mail",
			blank=True, null=True
		)
	def __str__(self):
		if self.displayName != "":
			return u'%s' % (self.displayName)
		else:
			return self.guid


class AzureDirectoryRole(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	guid = models.TextField(
			verbose_name="guid",
			unique=True,
		)
	def __str__(self):
		return u'%s' % (self.guid)


class AzureGroup(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	guid = models.TextField(
			verbose_name="guid",
			unique=True,
		)
	description = models.TextField(
			verbose_name="description",
			blank=True, null=True
		)
	displayName = models.TextField(
			verbose_name="displayName",
			blank=True, null=True
		)
	onPremisesSamAccountName = models.TextField(
			verbose_name="onPremisesSamAccountName",
			blank=True, null=True
		)
	def __str__(self):
		if self.displayName != "":
			return u'%s' % (self.displayName)
		else:
			return self.guid


class AzureNamedLocations(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	active = models.BooleanField(
			verbose_name="Aktiv",
			default=True,
			)
	ipNamedLocation_id = models.CharField(
			unique=True,
			verbose_name="Named Location ID",
			blank=False,
			null=False,
			max_length=256,
			)
	displayName = models.CharField(
			unique=True,
			verbose_name="Display Name",
			blank=True,
			null=True,
			max_length=512,
			)
	sist_endret = models.DateTimeField(
			verbose_name="Sist endret",
			blank=True,
			null=True,
			)
	isTrusted = models.BooleanField(
			verbose_name="Trygg gruppe (Is trusted)",
			default=False,
			)
	ipRanges = models.TextField(
			verbose_name="IP-ranges (subnet)",
			blank=True,
			null=True,
		)
	countriesAndRegions = models.TextField(
			verbose_name="Land og regioner",
			blank=True,
			null=True,
			)

	def __str__(self):
		return u'%s' % (self.displayName)

	class Meta:
		verbose_name_plural = "Azure: Named locations"
		default_permissions = ('add', 'change', 'delete', 'view')


class HRorg(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	active = models.BooleanField(
			verbose_name="Aktiv",
			default=True, # per definisjon
			help_text=u"Settes automatisk",
			)
	ouid = models.BigIntegerField(
			unique=True,
			verbose_name="organisasjonId",
			null=False,
			help_text=u"Importert",
			db_index=True,
			)
	level = models.BigIntegerField(
			verbose_name="nivaa",
			null=True,
			help_text=u"Importert",
			)
	leder = models.ForeignKey(
			to=User,
			on_delete=models.PROTECT,
			related_name='hrorg_leder',
			verbose_name="Leder",
			null=True,
			help_text=u"Importert",
			)
	ou = models.CharField(
			verbose_name="navn",
			max_length=200,
			null=True,
			help_text=u"Importert",
			)
	virksomhet_mor = models.ForeignKey(
			to="Virksomhet",
			on_delete=models.SET_NULL,
			related_name='hrorg_virksomhet_mor',
			verbose_name="Overordnet virksomhet",
			null=True,
			help_text=u"Importert",
			)
	direkte_mor = models.ForeignKey(
			to="HRorg",
			on_delete=models.CASCADE,
			related_name='hrorg_direkte_mor',
			verbose_name="Overordnet enhet",
			null=True,
			help_text=u"Importert",
			)
	hrouid = models.BigIntegerField(
			unique=True,
			verbose_name="hrOrganisasjonId",
			null=True,
			help_text=u"Importert",
			db_index=True,
			)
	hr_status = models.CharField(
			verbose_name="hr_status",
			max_length=1,
			null=True,
			help_text=u"Importert",
			)
	virksomhetId = models.BigIntegerField(
			verbose_name="virksomhetId",
			null=True,
			help_text=u"Importert",
			)
	gateNavn = models.TextField(null=True)
	postnr = models.TextField(null=True)
	#ikke behov for historikk

	def __str__(self):
		if self.virksomhet_mor:
			return f"{self.ou} ({self.virksomhet_mor.virksomhetsforkortelse})"
		else:
			return f"{self.ou}"

	class Meta:
		verbose_name_plural = "Organisasjon: Organisasjonsledd"
		verbose_name  = "HR-organisasjonsledd"
		default_permissions = ('add', 'change', 'delete', 'view')


RISIKO_VALG = (
	(0, '0 Ikke vurdert'),
	(1, '1 Lav'),
	(2, '2 Middels'),
	(3, '3 Høy'),
)


class AzureUserConsents(models.Model):
	userId = models.TextField(null=False)
	appId = models.TextField()
	scopes = models.TextField(null=False)
	userDisplayName = models.TextField()
	appDisplayName = models.TextField(null=False)

	def __str__(self):
		return f"{self.userId} {self.appDisplayName} {self.scopes}"
	class Meta:
		verbose_name_plural = "Azure: User Consents"


class AzureApplicationKeys(models.Model):
	application_ref = models.ForeignKey(
			to="AzureApplication",
			related_name='keys',
			on_delete=models.CASCADE,
			null=False, blank=False,
			)
	key_id = models.CharField(
			max_length=200,
			null=False,
			blank=False,
			)
	display_name = models.CharField(
			max_length=400,
			null=True,
			blank=True,
			)
	key_type = models.CharField(
			max_length=200,
			null=True,
			blank=True,
			)
	key_usage = models.CharField(
			max_length=200,
			null=True,
			blank=True,
			)
	end_date_time = models.DateTimeField(
			null=False,
			blank=True,
			)
	hint = models.CharField(
			max_length=30,
			null=True,
			blank=True,
			)
	unique_together = ('application_ref', 'key_id')

	def __str__(self):
		return u'%s' % (self.display_name)

	class Meta:
		verbose_name_plural = "Azure: Application keys"
		default_permissions = ('add', 'change', 'delete', 'view')

	def expire(self):
		#from django.utils import timezone
		return timezone.now() > self.end_date_time

	def color(self):
		if self.expire():
			return "red"
		if self.expire_soon():
			return "orange"
		return "green"

	def expire_soon(self):
		if self.expire():
			return False
		#from django.utils import timezone
		#from datetime import timedelta
		return (timezone.now() + timedelta(30)) > self.end_date_time


class AzureApplication(models.Model):
	opprettet = models.DateTimeField(
		verbose_name="Opprettet",
		auto_now_add=True,
		null=True,
		)
	active = models.BooleanField(
		default=True,
		)
	sist_oppdatert = models.DateTimeField(
		verbose_name="Sist oppdatert",
		auto_now=True,
		)
	appId = models.CharField(
		verbose_name="app id",
		max_length=40,
		null=False,
		unique=True,
		)
	objectId = models.CharField(
		verbose_name="object id",
		max_length=40,
		null=True,
		blank=True,
		)
	createdDateTime = models.DateTimeField(
		null=True,
		blank=True,
		)
	displayName = models.CharField(
		# Delegated or Application permission
		max_length=200,
		null=True,
		blank=True,
		)
	requiredResourceAccess = models.ManyToManyField(
		to="AzurePublishedPermissionScopes",
		related_name='azure_applications',
		verbose_name="Rettigheter",
		blank=True,
		)
	vurdering = models.TextField(
		verbose_name="Tekstlig vurdering",
		null=True,
		blank=True,
		help_text=u"Beholdes ved synkronisering mot Azure som skjer hver natt",
		)
	risikonivaa = models.BigIntegerField(choices=RISIKO_VALG,
		verbose_name="UTFASET Vurdering av risiko",
		default=0,
		blank=False,
		null=False,
		help_text=u"Beholdes ved synkronisering mot Azure som skjer hver natt",
		)
	json_response = models.TextField(
		verbose_name="JSON-respons fra API",
		null=True,
		blank=True,
		help_text=u"Rådata for SP",
		)
	homepageUrl = models.TextField(null=True)
	servicePrincipalType = models.CharField(max_length=100,null=True, blank=True)
	tags = models.TextField(null=True)
	#applicationVisibility = models.CharField(max_length=25, null=True, blank=True)
	#isAppProxy = models.BooleanField(null=True)
	notes = models.TextField(null=True)
	from_applications = models.BooleanField(default=False)
	publisherName = models.CharField(max_length=300, null=True, blank=True)
	antall_graph_rettigheter = models.BigIntegerField(
		verbose_name="Kalkulert: Antall Graph-tilganger",
		null=True,
		)
	owner = models.TextField(
		verbose_name="Eier",
		null=True,
		blank=True,
		help_text=u"Eier",
		)
	assigned_to = models.TextField(
		verbose_name="Tildelt",
		null=True,
		blank=True,
		help_text=u"Tildelt",
		)


	def __str__(self):
		return u'%s' % (self.displayName)

	def antall_application_permissions(self):
		return AzurePublishedPermissionScopes.objects.filter(azure_applications=self.id).filter(permission_type="Application").count()

	def antall_permissions(self):
		return AzurePublishedPermissionScopes.objects.filter(azure_applications=self.id).count()

	def risikonivaa_autofill(self):
		risk_level = 0
		for perm in self.requiredResourceAccess.all():
			this_risk_level = perm.risk_level()
			if this_risk_level > risk_level:
				risk_level = this_risk_level
		if risk_level == 3:
			return "3 Høy (auto)"
		if risk_level == 2:
			return "2 Middels (auto)"
		return "1 Lav (auto)"

	def er_enterprise_app(self):
		if self.tags != None:
			if "WindowsAzureActiveDirectoryIntegratedApp" in self.tags:
				return True
		return False

	def owner_json(self):
		try:
			return json.loads(self.owner)
		except:
			return "-"

	def assigned_to_json(self):
		try:
			return json.loads(self.assigned_to)
		except:
			return "-"

	class Meta:
		verbose_name_plural = "Azure: Service Principals"
		default_permissions = ('add', 'change', 'delete', 'view')


class AzurePublishedPermissionScopes(models.Model):
	opprettet = models.DateTimeField(
		verbose_name="Opprettet",
		auto_now_add=True,
		null=True,
		)
	sist_oppdatert = models.DateTimeField(
		verbose_name="Sist oppdatert",
		auto_now=True,
		)
	permission_type = models.CharField(
		# Delegated or Application permission
		max_length=20,
		null=True,
		)
	scope_id = models.CharField(
		max_length=40,
		null=False,
		unique=True,
		)
	isEnabled = models.BooleanField(
		null=True,
		)
	value = models.CharField(
		max_length=200,
		null=True,
		)
	grant_type = models.TextField(
		# ment å holde en liste (array)
		# for å oppbevare permissionScope["type"] eller role["allowedMemberTypes"]
		null=True, # resourceSpecificApplicationPermissions har ikke denne
		)
	adminConsentDescription = models.TextField(
		null=True,
		)
	adminConsentDisplayName = models.TextField(
		null=True,
		)
	userConsentDescription = models.TextField(
		null=True,
		)
	userConsentDisplayName = models.TextField(
		null=True,
		)
	resourceAppId = models.CharField(
		max_length=40,
		null=True,
		)
	resourceAppStr = models.CharField(
		max_length=200,
		null=True,
		)

	def __str__(self):
		return u'%s' % (self.value)

	def application_rights(self):
		if self.permission_type == "Application":
			return True
		return False


	def warning_permission(self):
		# moderate risk return False
		if "User.Read.All" in self.value:
			return False
		if "Sites.Selected" in self.value:
			return False
		if "Score.Read.All" in self.value:
			return False
		if "Place.Read.All" in self.value:
			return False
		if "AdministrativeUnit.Read.All" in self.value:
			return False
		if "Policy.Read.All" in self.value:
			return False
		if "Group.Read.All" in self.value:
			return False

		if self.permission_type == "Application":
			return True
		#if "full access" in self.adminConsentDisplayName:
		#	return True
		#if "ReadWrite.All" in self.value:
		#	return True
		#if "Mail.ReadWrite" in self.value:
		#	return True
		return False # default

	def safe_permission(self):
		if "Sign in" in self.adminConsentDisplayName:
			return True
		if "View users' email" in self.adminConsentDisplayName:
			return True
		if "basic profiles" in self.adminConsentDisplayName:
			return True
		if "openid" in self.value:
			return True
		if "profile" in self.value:
			return True
		if "GroupMember.Read.All" in self.value:
			return True
		if "MailboxSettings.Read" in self.value:
			return True
		return False
		# "Access selected site collections"

	def risk_level(self):
		if self.safe_permission():
			return 1 # low
		if self.warning_permission():
			return 3 # high
		return 2 # medium

	def risk_color(self):
		if self.safe_permission():
			return "#00b92a" # low
		if self.warning_permission():
			return "#dc3545" # high
		return "#bd8e00" # medium


	class Meta:
		verbose_name_plural = "Azure: Permission scopes"
		default_permissions = ('add', 'change', 'delete', 'view')





# 2026-06-23: Exposed via /api/los/ – update api_tjeneste_systemoversikt_docs.py when changing relevant API output (url name: api_tjeneste_systemoversikt_docs).
class LOS(models.Model):
	sist_oppdatert = models.DateTimeField(
		verbose_name="Sist oppdatert",
		auto_now=True,
		)
	unik_id = models.URLField(
		verbose_name="Unik URL",
		max_length=300,
		blank=False,
		null=False,
		)
	verdi = models.CharField(
		verbose_name="Verdi",
		null=False,
		blank=False,
		max_length=300,
		)
	kategori_ref = models.ForeignKey(
		to="LOS",
		related_name='kategori',
		verbose_name="ConceptScheme",
		blank=True,
		null=True,
		on_delete=models.SET_NULL,
		)
	parent_id = models.ManyToManyField(
		to="LOS",
		related_name='children',
		verbose_name="Overordnet ord/tema",
		)
	active = models.BooleanField(
		verbose_name="I LOS?",
		default=True,
		)
	buffer_alle_tema = models.ManyToManyField(
		to="LOS",
		related_name='alle_tema_buffer',
		verbose_name="Alle tema (buffer)",
		)

	def __str__(self):
		if self.active:
			return u'%s (%s)' % (self.verdi, self.kategori_tekst())
		else:
			return u'%s (utfaset)' % (self.verdi)


	def er_tema(self):
		if self.kategori_ref:
			if self.kategori_ref.verdi == "Tema":
				return True
		return False


	def er_hovedtema(self):
		if self.kategori_ref.verdi == "Tema" and len(self.parent_id.all()) == 0:
			return True
		return False

	def kategori_tekst(self):
		if not self.er_tema(): # Ord
			return "Ord"
		if self.er_hovedtema():
			return "Hovedtema" # hovedtema
		return "Undertema" # undertema


	def color(self):
		if not self.er_tema(): # Ord
			return "#d9d7d7"
		if self.er_hovedtema():
			return "#343a40" # hovedtema
		return "#007bff" # undertema



	def badge(self):
		if not self.er_tema(): # Ord
			return "badge-light"
		if self.er_hovedtema():
			return "badge-dark" # hovedtema
		return "badge-primary" # undertema


	def alle_tema(self):
		if len(self.buffer_alle_tema.all()) > 0:
			return self.buffer_alle_tema.all()

		alle_tema = set()
		stack = []
		stack.extend(self.parent_id.all())
		while len(stack) > 0:
			item = stack.pop()
			#print(item)
			stack.extend(item.parent_id.all())
			if item.er_tema():
				alle_tema.add(item)

		for tema in alle_tema:
			self.buffer_alle_tema.add(tema)

		return self.buffer_alle_tema.all()


	def hovedtema(self):
		hovedtema = set()
		alle_tema = self.alle_tema()
		for tema in alle_tema:
			if tema.er_hovedtema():
				hovedtema.add(tema)
		return hovedtema

	def undertema(self):
		undertema = set()
		alle_tema = self.alle_tema()
		#print(alle_tema)
		for tema in alle_tema:
			if not tema.er_hovedtema():
				undertema.add(tema)
		return undertema


	class Meta:
		verbose_name_plural = "Systemkategori: LOS fellesbegreper"
		verbose_name = "LOS-begrep"
		default_permissions = ('add', 'change', 'delete', 'view')


# 2026-06-23: Exposed via /api/vulnapp/known_exploited/ – update api_vulnapp_docs.py when changing relevant API output (url name: api_vulnapp_docs).
class ExploitedVulnerability(models.Model):
	# Model to keep track of exploited vulnerabilities (CISA)
	cve_id = models.CharField(max_length=20, primary_key=True)
	vendor_project = models.CharField(max_length=255)
	product = models.CharField(max_length=255)
	vulnerability_name = models.CharField(max_length=255)
	date_added = models.DateField()
	short_description = models.TextField()
	required_action = models.TextField()
	due_date = models.DateField()
	known_ransomware_campaign_use = models.CharField(max_length=255)

	def __str__(self):
		return self.cve_id



class Nettverksgruppe(models.Model):
	name =models.CharField(
		verbose_name="Navn",
		null=False,
		blank=False,
		max_length=250,
		)
	members = models.TextField(
		verbose_name="Medlemmer (JSON)",
		blank=False,
		null=False,
		)

	def __str__(self):
		return u'%s' % (self.name)

	class Meta:
		verbose_name_plural = "CMDB: Navngitte nettverksalias"
		default_permissions = ('add', 'change', 'delete', 'view')

class Brannmurregel(models.Model):
	regel_id = models.CharField(
		verbose_name="Regel ID",
		null=False,
		blank=False,
		max_length=50,
		)
	brannmur = models.CharField(
		verbose_name="Virtuell brannmur",
		null=False,
		blank=False,
		max_length=50,
		)
	active = models.BooleanField(
		verbose_name="Regel aktiv?",
		blank=False,
		null=False,
		default=False,
		)
	permit = models.BooleanField(
		verbose_name="Tillat trafikk?",
		blank=False,
		null=False,
		default=False,
		)
	source = models.TextField(
		verbose_name="Kilde (JSON)",
		blank=False,
		null=False,
		)
	destination = models.TextField(
		verbose_name="Destinasjon (JSON)",
		blank=False,
		null=False,
		)
	protocol =  models.TextField(
		verbose_name="Port/protokoll (JSON)",
		blank=False,
		null=False,
		)
	comment =  models.TextField(
		verbose_name="Kommentar",
		blank=True,
		null=True,
		)
	ref_vip = models.ManyToManyField(
		to="virtualIP",
		related_name='firewall_rules',
		verbose_name="Tilknyttede VIP-er",
		)
	ref_server = models.ManyToManyField(
		to="CMDBdevice",
		related_name='firewall_rules',
		verbose_name="Tilknyttede servere",
		)
	ref_vlan = models.ManyToManyField(
		to="NetworkContainer",
		related_name='firewall_rules',
		verbose_name="Tilknyttede VLAN",
		)

	def __str__(self):
		return u'%s' % (self.regel_id)

	class Meta:
		verbose_name_plural = "CMDB: Brannmurregler"
		default_permissions = ('add', 'change', 'delete', 'view')

	def source_items(self):
		return json.loads(self.source)

	def destination_items(self):
		return json.loads(self.destination)

	def protocol_items(self):
		return json.loads(self.protocol)


class GraphLayout(models.Model):
	virksomhet = models.ForeignKey(Virksomhet, on_delete=models.CASCADE)
	positions_json = models.JSONField(null=True)
	zoom = models.FloatField(default=1)
	pan_x = models.FloatField(default=0)
	pan_y = models.FloatField(default=0)
	updated_at = models.DateTimeField(auto_now=True)
	locked = models.BooleanField(default=False)

	def __str__(self):
		return f"Layout for {self.virksomhet.virksomhetsforkortelse}"

	class Meta:
		verbose_name_plural = "Visualisering: Graphlayouts"
		default_permissions = ('add', 'change', 'delete', 'view')


class SystemGraphLayout(models.Model):
	system = models.OneToOneField(
			System,
			on_delete=models.CASCADE,
			related_name='graph_layout',
			)
	positions_json = models.JSONField(null=True, blank=True)
	zoom = models.FloatField(default=1)
	pan_x = models.FloatField(default=0)
	pan_y = models.FloatField(default=0)
	updated_at = models.DateTimeField(auto_now=True)
	locked = models.BooleanField(default=False)

	def __str__(self):
		return f"Layout for system {self.system_id}"

	class Meta:
		verbose_name_plural = "Visualisering: System graph layouts"
		default_permissions = ('add', 'change', 'delete', 'view')



class AzureDevice(models.Model):
	device_id = models.CharField(max_length=64, primary_key=True)
	aad_device_id = models.UUIDField(null=True, blank=True)
	hostname = models.CharField(max_length=255)
	os_platform = models.CharField(max_length=64)
	exposure_level = models.CharField(max_length=32, null=True, blank=True)
	risk_score = models.CharField(max_length=32, null=True, blank=True)

	last_seen = models.DateTimeField(null=True, blank=True)
	first_seen = models.DateTimeField(null=True, blank=True)

	last_metadata_sync = models.DateTimeField(auto_now=True)

	def __str__(self):
		return self.hostname

	class Meta:
		verbose_name_plural = "Azure: Devices"
		indexes = [
			models.Index(fields=["os_platform"]),
		]


class CVE(models.Model):
	cve_id = models.CharField(max_length=32, primary_key=True)
	severity = models.CharField(max_length=16)
	cvss_score = models.FloatField(null=True, blank=True)

	description = models.TextField(null=True, blank=True)
	published_at = models.DateTimeField(null=True, blank=True)

	def __str__(self):
		return self.cve_id

	class Meta:
		verbose_name_plural = "Azure: CVEs"


class AzureDeviceVulnerability(models.Model):
	device = models.ForeignKey(AzureDevice, on_delete=models.CASCADE)
	cve = models.ForeignKey(CVE, on_delete=models.CASCADE)

	product_name = models.CharField(max_length=128)
	product_vendor = models.CharField(max_length=64)
	product_version = models.CharField(max_length=64)

	fixing_kb = models.CharField(max_length=32, null=True, blank=True)
	severity = models.CharField(max_length=16)

	first_seen = models.DateTimeField()
	last_seen = models.DateTimeField()

	class Meta:
		verbose_name_plural = "Azure: Device vulnerabilities"
		unique_together = ("device", "cve")
		indexes = [
			models.Index(fields=["severity"]),
			models.Index(fields=["product_vendor"]),
			models.Index(fields=["device"]),
		]


class DeviceCodeSignInCombo(models.Model):
	# 2026-06-19: Unique user+IP+app device code combos for nightly sync and 3-month history.
	# 2026-06-29: sign_in_count – total observed sign-ins for this combo (incremented by nightly sync).
	user_principal_name = models.CharField(max_length=255, db_index=True)
	ip_address = models.CharField(max_length=45, db_index=True)
	app_display_name = models.CharField(max_length=255, db_index=True)
	is_noteworthy = models.BooleanField(default=False)
	first_seen = models.DateTimeField()
	last_seen = models.DateTimeField()
	sign_in_count = models.PositiveIntegerField(default=1)

	def __str__(self):
		return f"{self.user_principal_name} / {self.ip_address} / {self.app_display_name}"

	class Meta:
		verbose_name_plural = "Device code: kombinasjoner"
		unique_together = ("user_principal_name", "ip_address", "app_display_name")
		indexes = [
			models.Index(fields=["last_seen"]),
			models.Index(fields=["is_noteworthy", "last_seen"]),
		]


class BloodHoundSnapshot(models.Model):
	# 2026-06-23: One row per bloodhound-python collection upload (object counts from meta, not full graph).
	snapshot_id = models.CharField(max_length=14, unique=True, db_index=True)
	received_at = models.DateTimeField(auto_now_add=True)
	storage_path = models.CharField(max_length=512)
	status = models.CharField(max_length=32, default='indexed')
	error_message = models.TextField(blank=True)
	count_users = models.BigIntegerField(default=0)
	count_computers = models.BigIntegerField(default=0)
	count_groups = models.BigIntegerField(default=0)
	count_gpos = models.BigIntegerField(default=0)
	count_ous = models.BigIntegerField(default=0)
	count_domains = models.BigIntegerField(default=0)
	count_containers = models.BigIntegerField(default=0)
	shard_counts = models.JSONField(default=dict, blank=True)
	file_count = models.IntegerField(default=0)
	total_bytes = models.BigIntegerField(default=0)
	collection_methods = models.BigIntegerField(null=True, blank=True)
	meta_version = models.IntegerField(null=True, blank=True)
	source_ip = models.GenericIPAddressField(null=True, blank=True)
	analysis_status = models.CharField(max_length=16, default='pending', db_index=True)
	analysis_completed_at = models.DateTimeField(null=True, blank=True)
	finding_count = models.IntegerField(default=0)
	analysis_error = models.TextField(blank=True)

	def snapshot_id_readable(self):
		from systemoversikt.bloodhound.ingest import snapshot_id_readable
		return snapshot_id_readable(self.snapshot_id)

	def counts_table(self):
		return [
			('users', self.count_users, self.shard_counts.get('users', 0)),
			('computers', self.count_computers, self.shard_counts.get('computers', 0)),
			('groups', self.count_groups, self.shard_counts.get('groups', 0)),
			('gpos', self.count_gpos, self.shard_counts.get('gpos', 0)),
			('ous', self.count_ous, self.shard_counts.get('ous', 0)),
			('domains', self.count_domains, self.shard_counts.get('domains', 0)),
			('containers', self.count_containers, self.shard_counts.get('containers', 0)),
		]

	def __str__(self):
		return f'BloodHound {self.snapshot_id}'

	class Meta:
		verbose_name_plural = "BloodHound: snapshots"
		ordering = ['-snapshot_id']
		default_permissions = ('add', 'change', 'delete', 'view')


class BloodHoundFinding(models.Model):
	# 2026-06-23: One preventive finding from bloodhound_analyze (BH-01–BH-07).
	snapshot = models.ForeignKey(
		BloodHoundSnapshot,
		on_delete=models.CASCADE,
		related_name='findings',
	)
	check_id = models.CharField(max_length=8, db_index=True)
	severity = models.CharField(max_length=16, db_index=True)
	title = models.CharField(max_length=256)
	principal_sid = models.CharField(max_length=128, blank=True, db_index=True)
	principal_name = models.CharField(max_length=512)
	target_sid = models.CharField(max_length=128, blank=True, db_index=True)
	target_name = models.CharField(max_length=512, blank=True)
	right_name = models.CharField(max_length=64, blank=True)
	detail = models.JSONField(default=dict, blank=True)
	user = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='bloodhound_findings',
	)

	def __str__(self):
		return f'{self.check_id} {self.principal_name}'

	class Meta:
		verbose_name_plural = "BloodHound: funn"
		ordering = ['check_id', 'principal_name']
		default_permissions = ('add', 'change', 'delete', 'view')
		indexes = [
			models.Index(fields=['snapshot', 'check_id']),
		]


RISIKOBEHANDLING_VALG = (
	('godta', 'Godta/Akseptere'),
	('redusere', 'Redusere'),
	('dele', 'Dele/Overføre'),
	('unnga', 'Unngå'),
)

RISK_ACTION_STATUS_VALG = (
	('forslag', 'Forslag'),
	('besluttet', 'Besluttet'),
	('under_arbeid', 'Under arbeid'),
	('utfort', 'Utført'),
)

RISK_ACTION_KILDE_VALG = (
	('parsed', 'Parsed fra foreslåtte tiltak'),
	('tiltak_sheet', 'Tiltak-ark'),
	('manual', 'Manuell'),
)

RISK_SCOPE_MEMBER_ROLE_VALG = (
	('owner', 'Eier'),
	('participant', 'Deltaker'),
)
RISK_SCOPE_MEMBER_ROLE_OWNER = 'owner'
RISK_SCOPE_MEMBER_ROLE_PARTICIPANT = 'participant'


class RiskScope(models.Model):
	opprettet = models.DateTimeField(
		verbose_name="Opprettet",
		auto_now_add=True,
		null=True,
	)
	sist_oppdatert = models.DateTimeField(
		verbose_name="Sist oppdatert",
		auto_now=True,
	)
	title = models.CharField(
		verbose_name="Tittel",
		max_length=300,
	)
	beskrivelse = models.TextField(
		verbose_name="Beskrivelse",
		blank=True,
		default='',
		help_text="Kort beskrivelse av hva risikovurderingen dekker.",
	)
	virksomhet = models.ForeignKey(
		to='Virksomhet',
		on_delete=models.PROTECT,
		related_name='risk_scopes',
		verbose_name="Virksomhet",
		blank=True,
		null=True,
	)
	sist_revidert = models.DateField(
		verbose_name="Sist revidert",
	)
	source_filename = models.CharField(
		verbose_name="Kildefil",
		max_length=300,
		blank=True,
		default='',
	)
	history = HistoricalRecords()

	def membership_for(self, user):
		if user is None or not getattr(user, 'is_authenticated', False):
			return None
		return self.memberships.filter(user_id=user.pk).first()

	def is_owner(self, user):
		membership = self.membership_for(user)
		return membership is not None and membership.role == RISK_SCOPE_MEMBER_ROLE_OWNER

	def is_participant(self, user):
		membership = self.membership_for(user)
		return membership is not None and membership.role == RISK_SCOPE_MEMBER_ROLE_PARTICIPANT

	def is_member(self, user):
		return self.membership_for(user) is not None

	def owner_memberships(self):
		return self.memberships.filter(role=RISK_SCOPE_MEMBER_ROLE_OWNER).select_related('user')

	def participant_memberships(self):
		return self.memberships.filter(role=RISK_SCOPE_MEMBER_ROLE_PARTICIPANT).select_related('user')

	def __str__(self):
		return self.title

	class Meta:
		verbose_name = "risikoomfang"
		verbose_name_plural = "Risiko: omfang"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['-sist_revidert', '-opprettet']


class RiskScopeMember(models.Model):
	opprettet = models.DateTimeField(
		verbose_name="Opprettet",
		auto_now_add=True,
		null=True,
	)
	scope = models.ForeignKey(
		to=RiskScope,
		on_delete=models.CASCADE,
		related_name='memberships',
		verbose_name="Risikoomfang",
	)
	user = models.ForeignKey(
		to=User,
		on_delete=models.CASCADE,
		related_name='risk_scope_memberships',
		verbose_name="Bruker",
	)
	role = models.CharField(
		verbose_name="Rolle",
		max_length=20,
		choices=RISK_SCOPE_MEMBER_ROLE_VALG,
	)
	added_by = models.ForeignKey(
		to=User,
		on_delete=models.SET_NULL,
		related_name='risk_scope_memberships_added',
		verbose_name="Lagt til av",
		blank=True,
		null=True,
	)
	history = HistoricalRecords()

	def __str__(self):
		return '%s – %s (%s)' % (self.scope, self.user, self.role)

	class Meta:
		verbose_name = "risikoomfang-medlem"
		verbose_name_plural = "Risiko: omfang-medlemmer"
		default_permissions = ('add', 'change', 'delete', 'view')
		constraints = [
			models.UniqueConstraint(
				fields=['scope', 'user'],
				name='risk_scope_member_unique_scope_user',
			),
		]


class RiskScenario(models.Model):
	opprettet = models.DateTimeField(
		verbose_name="Opprettet",
		auto_now_add=True,
		null=True,
	)
	sist_oppdatert = models.DateTimeField(
		verbose_name="Sist oppdatert",
		auto_now=True,
	)
	scope = models.ForeignKey(
		to=RiskScope,
		on_delete=models.CASCADE,
		related_name='scenarios',
		verbose_name="Risikoomfang",
	)
	risk_id = models.CharField(
		verbose_name="RiskID",
		max_length=20,
	)
	uonsket_hendelse = models.TextField(
		verbose_name="Uønsket hendelse",
		blank=True,
		default='',
	)
	kit_dimensjoner = models.CharField(
		verbose_name="K, I, T",
		max_length=50,
		blank=True,
		default='',
	)
	konsekvenstyper = models.CharField(
		verbose_name="Konsekvenstyper",
		max_length=120,
		blank=True,
		default='',
	)
	arsaker_svakheter = models.TextField(
		verbose_name="Årsaker/svakheter",
		blank=True,
		default='',
	)
	konsekvens_nivaa = models.PositiveSmallIntegerField(
		verbose_name="Konsekvens (nivå)",
		null=True,
		blank=True,
	)
	sannsynlighet_nivaa = models.PositiveSmallIntegerField(
		verbose_name="Sannsynlighet (nivå)",
		null=True,
		blank=True,
	)
	konsekvens_begrunnelse = models.TextField(
		verbose_name="Konsekvensbegrunnelse",
		blank=True,
		default='',
	)
	sannsynlighetsbegrunnelse = models.TextField(
		verbose_name="Sannsynlighetsbegrunnelse",
		blank=True,
		default='',
	)
	risikobehandling = models.CharField(
		verbose_name="Risikobehandling",
		max_length=20,
		choices=RISIKOBEHANDLING_VALG,
		blank=True,
		default='',
	)
	konsekvens_etter = models.PositiveSmallIntegerField(
		verbose_name="Konsekvens etter tiltak (nivå)",
		null=True,
		blank=True,
	)
	sannsynlighet_etter = models.PositiveSmallIntegerField(
		verbose_name="Sannsynlighet etter tiltak (nivå)",
		null=True,
		blank=True,
	)
	rekkefolge = models.PositiveIntegerField(
		verbose_name="Rekkefølge",
		default=0,
	)
	systemer = models.ManyToManyField(
		to='System',
		related_name='risk_scenarios',
		verbose_name="Systemer",
		blank=True,
	)
	history = HistoricalRecords()

	@property
	def risiko_etikett(self):
		from systemoversikt.risk_criteria import risk_label
		return risk_label(self.sannsynlighet_nivaa, self.konsekvens_nivaa)

	@property
	def restrisiko_etikett(self):
		# 2026-06-29: Empty etter fields inherit current risk via effective_residual_levels().
		from systemoversikt.risk_criteria import effective_residual_levels, risk_label
		s, k = effective_residual_levels(self)
		return risk_label(s, k)

	def scenario_nummer(self):
		"""Excel Tiltak-ark refererer ofte til tall uten R-prefiks (R1 -> 1)."""
		digits = ''.join(c for c in self.risk_id if c.isdigit())
		return int(digits) if digits else self.rekkefolge

	def __str__(self):
		return '%s: %s' % (self.risk_id, self.uonsket_hendelse[:60])

	class Meta:
		verbose_name = "risikoscenario"
		verbose_name_plural = "Risiko: scenarioer"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['rekkefolge', 'risk_id']
		unique_together = ('scope', 'risk_id')


class RiskAction(models.Model):
	opprettet = models.DateTimeField(
		verbose_name="Opprettet",
		auto_now_add=True,
		null=True,
	)
	sist_oppdatert = models.DateTimeField(
		verbose_name="Sist oppdatert",
		auto_now=True,
	)
	scope = models.ForeignKey(
		to=RiskScope,
		on_delete=models.CASCADE,
		related_name='actions',
		verbose_name="Risikoomfang",
	)
	scenarios = models.ManyToManyField(
		to=RiskScenario,
		related_name='actions',
		verbose_name="Risikoscenarioer",
		blank=True,
	)
	beskrivelse = models.TextField(
		verbose_name="Tiltak",
	)
	ansvarlig = models.CharField(
		verbose_name="Ansvarlig",
		max_length=200,
		blank=True,
		default='',
	)
	frist = models.DateField(
		verbose_name="Frist",
		null=True,
		blank=True,
	)
	status = models.CharField(
		verbose_name="Status",
		max_length=20,
		choices=RISK_ACTION_STATUS_VALG,
		default='forslag',
	)
	kilde = models.CharField(
		verbose_name="Kilde",
		max_length=20,
		choices=RISK_ACTION_KILDE_VALG,
		default='parsed',
	)
	history = HistoricalRecords()

	def __str__(self):
		return self.beskrivelse[:60]

	class Meta:
		verbose_name = "risikotiltak"
		verbose_name_plural = "Risiko: tiltak"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['pk']
