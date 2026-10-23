# -*- coding: utf-8 -*-
# Change log:
# 2026-10-21: Free-text device lookup tokens + FQDN/IP paste matching for massesøk.
"""Shared hostname ↔ CMDB comp_name matching and display."""
import ipaddress
import os
import re

from django.conf import settings
from django.db.models import Q
from django.db.models.functions import Lower


# Hostname / FQDN-ish tokens (letters required so pure numbers are not hostnames).
_HOSTNAME_TOKEN_RE = re.compile(
	r'\b(?:[a-z0-9](?:[a-z0-9_-]*[a-z0-9])?)(?:\.[a-z0-9](?:[a-z0-9_-]*[a-z0-9])?)+\b'
	r'|\b[a-z][a-z0-9_-]{1,62}\b',
	re.I,
)
_IPV4_TOKEN_RE = re.compile(r'(?<![0-9.])(?:\d{1,3}\.){3}\d{1,3}(?![0-9.])')
_IPV6_TOKEN_RE = re.compile(
	r'(?<![0-9a-f:])(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}(?![0-9a-f:])',
	re.I,
)


def hostname_domain_suffixes():
	# Prefer env (comma-separated) so deploy can add suffixes without code changes.
	env_raw = os.environ.get("CMDB_HOSTNAME_DOMAIN_SUFFIXES", "").strip()
	if env_raw:
		return [p.strip() for p in env_raw.split(",") if p.strip()]
	suffixes = getattr(settings, "CMDB_HOSTNAME_DOMAIN_SUFFIXES", None)
	if not suffixes:
		return []
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
	# IPs are matched separately; do not derive label candidates from them.
	try:
		ipaddress.ip_address(name)
		return [name]
	except ValueError:
		pass
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


def _normalize_paste_token(raw):
	"""Strip wrappers / junk; keep DOMAIN\\host as host only."""
	token = str(raw).strip().strip('\'"<>[](){},;')
	if not token:
		return ""
	if "\\" in token:
		token = token.rsplit("\\", 1)[-1].strip()
	return token.strip().strip(".")


def _parse_ip_token(token):
	try:
		return str(ipaddress.ip_address(token))
	except ValueError:
		return None


def is_probable_device_token(token):
	"""True when a token looks intentional (hostname/IP), not prose noise."""
	if not token or len(token) < 2:
		return False
	if _parse_ip_token(token):
		return True
	lowered = token.lower()
	if "." in token:
		# FQDN / multi-label — domain-agnostic (no hardcoded suffix required)
		labels = [p for p in lowered.split(".") if p]
		if len(labels) >= 2 and any(any(c.isalpha() for c in p) for p in labels):
			return True
	# Server-ish short names usually include a digit or hyphen
	if any(c.isdigit() for c in token) or "-" in token or "_" in token:
		return True
	return False


def extract_device_lookup_tokens(text):
	"""
	Pull hostname/IP-like tokens from free-form pasted text.

	Returns a list of (token, explicit) in first-seen order.
	explicit=True means the token was a solitary list segment (own line / CSV
	cell), so unmatched values should be reported as misses even if they look
	like ordinary words.
	"""
	if not text or not str(text).strip():
		return []

	raw = str(text)
	ordered = []
	seen = set()

	def _add(token, explicit=False):
		token = _normalize_paste_token(token)
		if not token:
			return
		ip_str = _parse_ip_token(token)
		key = ("ip", ip_str) if ip_str else ("host", token.lower())
		if key in seen:
			# Upgrade to explicit if seen again as a clean list item
			if explicit:
				for i, (existing, was_explicit) in enumerate(ordered):
					existing_ip = _parse_ip_token(existing)
					existing_key = ("ip", existing_ip) if existing_ip else ("host", existing.lower())
					if existing_key == key and not was_explicit:
						ordered[i] = (existing, True)
						break
			return
		seen.add(key)
		ordered.append((ip_str or token, explicit))

	for line in raw.splitlines():
		line_stripped = line.strip()
		if not line_stripped:
			continue
		parts = re.split(r'[,;\t|]+', line_stripped)
		for part in parts:
			part = part.strip()
			if not part:
				continue
			# Solitary segment (no whitespace) → intentional list item
			if re.fullmatch(r'\S+', part):
				_add(part, explicit=True)
				continue
			# Keep document order: gather all match spans, then sort by start.
			spans = []
			for m in _IPV4_TOKEN_RE.finditer(part):
				spans.append((m.start(), m.end(), m.group(0), "ip"))
			for m in _IPV6_TOKEN_RE.finditer(part):
				cand = m.group(0)
				if _parse_ip_token(cand):
					spans.append((m.start(), m.end(), cand, "ip"))
			for m in _HOSTNAME_TOKEN_RE.finditer(part):
				spans.append((m.start(), m.end(), m.group(0), "host"))
			spans.sort(key=lambda s: (s[0], s[1]))
			last_end = -1
			for start, end, value, kind in spans:
				if start < last_end:
					continue  # overlapped by an earlier (usually longer) match
				if kind == "host" and _parse_ip_token(value):
					continue  # IPv4 already captured as ip
				_add(value, explicit=False)
				last_end = end

	return ordered


def lookup_cmdb_devices_from_paste(text, max_tokens=2000):
	"""
	Match pasted free text against CMDBdevice by hostname (incl. FQDN) and IP.

	FQDN handling uses configured DNS suffixes when present, and always tries
	the first DNS label so any domain works without hardcoding.

	Returns (hits, misses) where hits are CMDBdevice instances (stable order)
	and misses are unmatched tokens that look like devices (or were explicit
	list items).
	"""
	from systemoversikt.models import CMDBdevice

	token_rows = extract_device_lookup_tokens(text)[:max_tokens]
	if not token_rows:
		return [], []

	# Ignore prose noise from free text (avoid false hits on words like "test").
	lookup_rows = []
	explicit_keys = set()
	for token, explicit in token_rows:
		ip_str = _parse_ip_token(token)
		key = ("ip", ip_str) if ip_str else ("host", token.lower())
		if explicit:
			explicit_keys.add(key)
		if explicit or is_probable_device_token(token):
			lookup_rows.append((token, explicit))

	if not lookup_rows:
		return [], []

	tokens = [t for t, _explicit in lookup_rows]

	host_tokens = []
	ip_tokens = []
	for token in tokens:
		ip_str = _parse_ip_token(token)
		if ip_str:
			ip_tokens.append(ip_str)
		else:
			host_tokens.append(token)

	all_candidates_lower = set()
	for token in host_tokens:
		for candidate in hostname_comp_name_candidates(token):
			all_candidates_lower.add(candidate.lower())

	by_comp_lower = {}
	if all_candidates_lower:
		for comp_name, pk in (
			CMDBdevice.objects.annotate(cn_lower=Lower("comp_name"))
			.filter(cn_lower__in=all_candidates_lower)
			.values_list("comp_name", "pk")
		):
			by_comp_lower[comp_name.lower()] = pk

	ip_pks_by_ip = {ip: set() for ip in ip_tokens}
	if ip_tokens:
		for pk, ip_val in CMDBdevice.objects.filter(
			comp_ip_address__in=ip_tokens
		).values_list("pk", "comp_ip_address"):
			if ip_val in ip_pks_by_ip:
				ip_pks_by_ip[ip_val].add(pk)
		for pk, ip_val in CMDBdevice.objects.filter(
			network_ip_address__ip_address__in=ip_tokens
		).values_list("pk", "network_ip_address__ip_address"):
			if ip_val in ip_pks_by_ip:
				ip_pks_by_ip[ip_val].add(pk)

	matched_token_keys = set()
	hit_pks_ordered = []
	seen_pks = set()

	def _remember_pk(pk):
		if pk in seen_pks:
			return
		seen_pks.add(pk)
		hit_pks_ordered.append(pk)

	for token in tokens:
		ip_str = _parse_ip_token(token)
		if ip_str:
			pks = ip_pks_by_ip.get(ip_str) or set()
			if pks:
				matched_token_keys.add(("ip", ip_str))
				for pk in sorted(pks):
					_remember_pk(pk)
			continue
		matched = False
		for candidate in hostname_comp_name_candidates(token):
			pk = by_comp_lower.get(candidate.lower())
			if pk:
				matched = True
				_remember_pk(pk)
		if matched:
			matched_token_keys.add(("host", token.lower()))

	hits = []
	if hit_pks_ordered:
		by_pk = CMDBdevice.objects.in_bulk(hit_pks_ordered)
		hits = [by_pk[pk] for pk in hit_pks_ordered if pk in by_pk]

	misses = []
	for token in tokens:
		ip_str = _parse_ip_token(token)
		key = ("ip", ip_str) if ip_str else ("host", token.lower())
		if key in matched_token_keys:
			continue
		if key in explicit_keys or is_probable_device_token(token):
			misses.append(token)

	return hits, misses
