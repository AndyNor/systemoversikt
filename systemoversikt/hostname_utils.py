# -*- coding: utf-8 -*-
"""Shared hostname ↔ CMDB comp_name matching and display."""
from django.conf import settings
from django.db.models import Q


def hostname_domain_suffixes():
	suffixes = getattr(settings, "CMDB_HOSTNAME_DOMAIN_SUFFIXES", None)
	if suffixes is None:
		return [".oslofelles.oslo.kommune.no"]
	return list(suffixes)


def _normalize_domain_suffix(suffix):
	suffix = str(suffix).strip().lower()
	if not suffix:
		return None
	if not suffix.startswith("."):
		suffix = "." + suffix
	return suffix


def strip_configured_hostname_suffix(hostname):
	"""Remove the longest matching configured DNS suffix (case-insensitive)."""
	name = str(hostname).strip()
	if not name:
		return name
	lowered = name.lower()
	best_suffix = None
	best_len = 0
	for raw in hostname_domain_suffixes():
		suffix = _normalize_domain_suffix(raw)
		if not suffix:
			continue
		if lowered.endswith(suffix) and len(suffix) > best_len:
			best_len = len(suffix)
			best_suffix = suffix
	if best_suffix:
		short = name[:-best_len]
		if short:
			return short
	return name


def hostname_comp_name_candidates(hostname):
	"""Possible CMDB comp_name values for a Defender/Azure hostname."""
	if not hostname:
		return []
	name = str(hostname).strip()
	if not name:
		return []
	candidates = [name]
	stripped = strip_configured_hostname_suffix(name)
	if stripped and stripped.lower() != name.lower():
		candidates.append(stripped)
	if "." in name:
		first_label = name.split(".", 1)[0]
		if first_label:
			candidates.append(first_label)
	seen = set()
	out = []
	for candidate in candidates:
		key = candidate.lower()
		if key not in seen:
			seen.add(key)
			out.append(candidate)
	return out


def hostname_display_name(hostname, comp_name=None):
	"""Short label for UI; prefers CMDB comp_name when known."""
	if comp_name:
		comp = str(comp_name).strip()
		if comp:
			return comp
	name = str(hostname).strip()
	if not name:
		return name
	stripped = strip_configured_hostname_suffix(name)
	if stripped.lower() != name.lower():
		return stripped
	if "." in name:
		return name.split(".", 1)[0]
	return name


def azure_device_q_for_comp_name(comp):
	"""Q filter for AzureDeviceVulnerability rows tied to a CMDB comp_name."""
	comp = (comp or "").strip()
	if not comp:
		return Q(pk__in=[])
	azure_filter = Q(device__hostname__iexact=comp)
	azure_filter |= Q(device__hostname__istartswith=f"{comp}.")
	if "." in comp:
		azure_filter |= Q(device__hostname__iexact=comp.split(".", 1)[0])
	return azure_filter


def cmdb_pk_lookup_for_hostnames(hostnames):
	"""Map hostname -> CMDBdevice.pk (inverse of azure_device_q_for_comp_name)."""
	from systemoversikt.models import CMDBdevice

	if not hostnames:
		return {}
	all_candidates = []
	for hostname in hostnames:
		all_candidates.extend(hostname_comp_name_candidates(hostname))
	if not all_candidates:
		return {}
	unique_candidates = list({c.lower(): c for c in all_candidates}.values())
	lookup_q = Q()
	for candidate in unique_candidates:
		lookup_q |= Q(comp_name__iexact=candidate)
	by_comp_lower = {
		comp.lower(): pk
		for comp, pk in CMDBdevice.objects.filter(lookup_q).values_list("comp_name", "pk")
	}
	result = {}
	for hostname in hostnames:
		pk = None
		for candidate in hostname_comp_name_candidates(hostname):
			pk = by_comp_lower.get(candidate.lower())
			if pk:
				break
		result[hostname] = pk
	return result


def device_name_rows_for_hostnames(hostnames):
	"""Rows for vulnstats device list: hostname, cmdb_pk, display_name."""
	from systemoversikt.models import CMDBdevice

	pk_by_hostname = cmdb_pk_lookup_for_hostnames(hostnames)
	pks = [pk for pk in pk_by_hostname.values() if pk]
	comp_by_pk = {}
	if pks:
		comp_by_pk = dict(CMDBdevice.objects.filter(pk__in=pks).values_list("pk", "comp_name"))
	rows = []
	for hostname in hostnames:
		pk = pk_by_hostname.get(hostname)
		comp_name = comp_by_pk.get(pk) if pk else None
		rows.append({
			"hostname": hostname,
			"cmdb_pk": pk,
			"display_name": hostname_display_name(hostname, comp_name=comp_name),
		})
	return rows
