# -*- coding: utf-8 -*-
# Change log:
# 2026-07-08: System details risk overview – scenarios linked via M2M, exclude archived collections.
# 2026-07-07: alle_nettverk – only parse / as CIDR when term is valid IPv4/prefix (not text like DMZ Ekstern/Internett).
# 2026-07-07: alle_nettverk – top_by_ip_devices stats use .values() so dict access works.
# 2026-07-07: alle_nettverk – pagination, stats (lokasjon, IP-enheter, sone) and exclude filter.
# 2026-07-07: alle_dns – exclude box for IP addresses and alias mot (CNAME targets).
# 2026-07-07: alle_dns – top 20 alias mot only; IP and TTL remain top 10.
# 2026-07-07: alle_dns – alias stats from dns_target column, not only dns_type=CNAME.
# 2026-07-07: alle_dns – top 10 CNAME alias targets in overview stats.
# 2026-07-07: alle_dns – stat badges trigger search_term instead of facet filters.
# 2026-07-07: alle_dns – overview stats without cache (fast enough at ~46k rows).
# 2026-07-07: alle_dns – overview stats modules with IP/TTL/type/source filters.
# 2026-07-07: alle_dns – fix search (FQDN/IP) and explicit template context.
# 2026-07-07: alle_dns – search and pagination for 46k+ DNS records.
# 2026-07-07: Global /sok/ redirects IPv4/CIDR terms to alle_ip when user has CMDB access.
# 2026-07-02: Qualys landing chart – CMDB server count line from audit log on dual y-axis.
# 2026-07-02: Qualys import chart – stacked severity bars plus total line from audit log.
# 2026-07-02: sikkerhet_sarbarheter – landing page with links; Qualys import chart from audit log.
# 2026-06-30: tool_service_announcements – latest MS Graph service announcement messages (no permission gate).
# 2026-06-24: rapport_conditional_access_rules – single rule at /rules/<pk>/; list at /rules/.
# 2026-06-23: rapport_conditional_access_overview – tile view of active CA rules (replaces graph prototype).
# 2026-06-23: rapport_conditional_access_rules – batch GUID lookup and named-location IP ranges in conditions.
# 2026-06-23: rapport_conditional_access_changes – batch GUID lookups for CA changes report performance.
# 2026-06-23: drift_beredskap – sort by computed priority score; attach prioritet_poeng for template sort key.
# 2026-06-23: rapport_prioriteringer – quick links from intern_tjenesteleverandor flag, not hardcoded DIG id.
# 2026-06-23: drift_beredskap – bar chart data for priority score distribution per virksomhet.
# 2026-06-23: Developer docs page for Sårbarhetsoversikten (vulnapp) API (login_required).
# 2026-06-23: Fix api_virksomheter overordnede_virksomheter – use parent.pk not shadowed loop variable.
# 2026-06-23: Developer docs page for Tjeneste- og systemoversikt API (login_required).
# 2026-06-23: tool_ntfs – SDDL/NTFS ACL decoder (no permission gate).
# 2026-06-23: Home page – fifth chart for egenutviklet vs generisk (replaces text under drift chart).
# 2026-06-22: Home page drift chart – Driftsplattform segment counts via drift_color_segment().
# 2026-06-22: Tjenestekatalog API – bool_er_saas, bool_egenutviklet, bool_saas; removed dead non-optimized API blocks.
# 2026-06-21: Dead code cleanup – removed unreachable views, prk_api, SharePoint legacy block, csrf403 stub.
# 2026-06-21: decode_ad_timestamp helper – consolidates AD FILETIME decoding in LDAP lookups.
# 2026-06-21: Tjeneste detail page with separate ecosystem graph – not shared with systemdetaljer.
# 2026-06-21: Page perf – prefetch/select_related on forvalteroversikt, servicebrukere, Citrix app pages.
# 2026-06-21: CSIRT immediate virksomhet security alert page for sikkerhetsanalytikere.
# 2026-06-21: Removed Definisjon views – feature retired, URLs already disabled.
# 2026-06-21: Removed UBW module views – feature retired, URLs already disabled.
# 2026-06-21: Nightly rydde_leverandorer job – shared reference logic in leverandor_referanser.py.
# 2026-06-21: Fast leverandør stats via through/FK tables – avoids slow reverse JOINs on Leverandor.
# 2026-06-21: Removed BehandlingerPersonopplysninger and DPIA views/URLs – functionality moved to Behandlingsoversikten.
# 2026-06-21: Pass system_colors to systemdetaljer – legend matches dependency chart palette.
# 2026-06-21: System dependency chart – layout save/lock endpoints and generer_graf_ny extraction.
# 2026-06-21: System dependency graph – URL, CMDB BSS and parent BS nodes on system detail.
# 2026-06-21: Removed phased-out virksomhet dashboard (template, view, URLs).
# 2026-06-21: _integrasjonsstatus helpers – shared lookup for import freshness on source pages.
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core import serializers
from systemoversikt.models import *
from systemoversikt.hostname_utils import (
	azure_device_q_for_comp_name,
	cmdb_pk_lookup_for_hostnames,
	device_name_rows_for_hostnames,
)
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models.functions import Concat, Cast
from django.db.models import CharField, Count, Q, Sum, F, Avg, Max, FloatField, ExpressionWrapper, Case, When, Value
from django.db.models import Prefetch
from django.template.loader import render_to_string
from django.db.models.functions import Lower, TruncMonth, TruncYear, TruncDay, TruncDate, Substr
from django.http import HttpResponseBadRequest, JsonResponse, Http404, HttpResponseRedirect, HttpResponse, HttpRequest, HttpResponseForbidden
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.urls import reverse
from django.utils.http import urlencode
from django.db import transaction
import ipaddress
import os, datetime, json, re, time, struct, hashlib
from collections import Counter, defaultdict
from django.utils import timezone
from django.core.cache import cache
from systemoversikt.leverandor_referanser import leverandor_referanse_statistikk


##########################
# Fellesvariabler #
##########################


def _integrasjonsstatus(kodeord):
	try:
		return IntegrasjonKonfigurasjon.objects.get(kodeord=kodeord)
	except IntegrasjonKonfigurasjon.DoesNotExist:
		return None


def _integrasjonsstatus_flere(*kodeord):
	return [s for k in kodeord if (s := _integrasjonsstatus(k))]


def _integrasjonsstatus_auth_methods():
	return _integrasjonsstatus("azure_ad_auth_methods_v2") or _integrasjonsstatus("azure_ad_auth_methods")


def _azure_vulnstats_cache_ts_token(integrasjonsstatus):
	dt = getattr(integrasjonsstatus, "dato_sist_oppdatert", None)
	if not dt:
		return "ukjent"
	# Memcached keys must avoid spaces/colons/etc in values we embed in keys.
	return hashlib.md5(str(dt).encode("utf-8")).hexdigest()


def _azure_vulnstats_cache_slug(value):
	if value is None:
		return "none"
	return hashlib.md5(str(value).encode("utf-8")).hexdigest()


# Overview-only: Defender client osPlatform values (WindowsServer* kept for server reporting).
_AZURE_VULNSTATS_OVERVIEW_EXCLUDED_OS = ("Windows10", "Windows11")


def _azure_vulnstats_overview_active():
	qs = AzureDeviceVulnerability.objects.all()
	for os_platform in _AZURE_VULNSTATS_OVERVIEW_EXCLUDED_OS:
		qs = qs.exclude(device__os_platform__iexact=os_platform)
	return qs


def _azure_vulnstats_qualys_defender_comparison():
	# 2026-06-07: Fleet-wide unique CVE union/agreement plus per-machine breakdown for qualys_compare.
	"""Unique CVE sets per CMDB machine plus fleet-wide unique CVE aggregates."""
	empty_fleet = {
		"qualys_total": 0,
		"defender_total": 0,
		"qualys_only": 0,
		"overlap": 0,
		"defender_only": 0,
		"union": 0,
		"agreement_pct": None,
		"machine_count": 0,
		"machines_both_sources": 0,
		"machines_qualys_only": 0,
		"machines_defender_only": 0,
	}
	qualys_by_pk = defaultdict(set)
	for server_id, cve_info in QualysVuln.objects.filter(
		server_id__isnull=False,
	).values_list("server_id", "cve_info"):
		qualys_by_pk[server_id].update(_cves_from_qualys_cve_info(cve_info))

	azure_by_pk = defaultdict(set)
	azure_rows = list(
		_azure_vulnstats_overview_active().values_list("device__hostname", "cve__cve_id")
	)
	hostnames = {hostname for hostname, cve_id in azure_rows if hostname and cve_id}
	pk_by_hostname = cmdb_pk_lookup_for_hostnames(hostnames)
	for hostname, cve_id in azure_rows:
		if not cve_id:
			continue
		pk = pk_by_hostname.get(hostname)
		if pk:
			azure_by_pk[pk].add(cve_id.upper())

	all_pks = set(qualys_by_pk.keys()) | set(azure_by_pk.keys())
	if not all_pks:
		return {
			"rows": [],
			"summary": {
				"machine_count": 0,
				"qualys_only": 0,
				"overlap": 0,
				"defender_only": 0,
			},
			"fleet": empty_fleet,
		}

	comp_names = dict(
		CMDBdevice.objects.filter(pk__in=all_pks).values_list("pk", "comp_name")
	)

	rows = []
	summary = {
		"machine_count": 0,
		"qualys_only": 0,
		"overlap": 0,
		"defender_only": 0,
	}
	fleet_qualys = set()
	fleet_azure = set()
	machines_both_sources = 0
	machines_qualys_only = 0
	machines_defender_only = 0
	for pk in all_pks:
		qualys = qualys_by_pk.get(pk, set())
		azure = azure_by_pk.get(pk, set())
		if not qualys and not azure:
			continue
		fleet_qualys |= qualys
		fleet_azure |= azure
		if qualys and azure:
			machines_both_sources += 1
		elif qualys:
			machines_qualys_only += 1
		else:
			machines_defender_only += 1
		overlap = qualys & azure
		qualys_only = qualys - azure
		defender_only = azure - qualys
		union = qualys | azure
		rows.append({
			"cmdb_pk": pk,
			"comp_name": (comp_names.get(pk) or "").strip() or f"(pk {pk})",
			"qualys_only": len(qualys_only),
			"overlap": len(overlap),
			"defender_only": len(defender_only),
			"qualys_total": len(qualys),
			"defender_total": len(azure),
			"union": len(union),
			"agreement_pct": (
				round(100 * len(overlap) / len(union), 1) if union else None
			),
		})

	rows.sort(
		key=lambda row: (
			-(row["qualys_only"] + row["defender_only"]),
			row["comp_name"].lower(),
		)
	)
	summary["machine_count"] = len(rows)
	for row in rows:
		summary["qualys_only"] += row["qualys_only"]
		summary["overlap"] += row["overlap"]
		summary["defender_only"] += row["defender_only"]

	fleet_overlap = fleet_qualys & fleet_azure
	fleet_qualys_only = fleet_qualys - fleet_azure
	fleet_defender_only = fleet_azure - fleet_qualys
	fleet_union = fleet_qualys | fleet_azure
	fleet = {
		"qualys_total": len(fleet_qualys),
		"defender_total": len(fleet_azure),
		"qualys_only": len(fleet_qualys_only),
		"overlap": len(fleet_overlap),
		"defender_only": len(fleet_defender_only),
		"union": len(fleet_union),
		"agreement_pct": (
			round(100 * len(fleet_overlap) / len(fleet_union), 1)
			if fleet_union
			else None
		),
		"machine_count": len(rows),
		"machines_both_sources": machines_both_sources,
		"machines_qualys_only": machines_qualys_only,
		"machines_defender_only": machines_defender_only,
	}

	return {"rows": rows, "summary": summary, "fleet": fleet}


def _cves_from_qualys_cve_info(cve_info):
	"""Unique CVE IDs from Qualys cve_info (comma-separated and/or embedded in text)."""
	if not cve_info:
		return []
	found = re.findall(r"CVE-\d{4}-\d+", str(cve_info), flags=re.IGNORECASE)
	return {m.upper() for m in found}


_CVE_YEAR_NUM = re.compile(r"^CVE-(\d{4})-(\d+)$", re.IGNORECASE)


def _cve_sort_key_newest_first(cve_id):
	m = _CVE_YEAR_NUM.match((cve_id or "").strip())
	if m:
		return (int(m.group(1)), int(m.group(2)))
	return (0, 0)


def _sort_cve_ids_newest_first(cve_ids):
	return sorted(cve_ids, key=_cve_sort_key_newest_first, reverse=True)


def recent_errors(request):
	required_permissions = ['systemoversikt.view_qualysvuln'] # en rettighet veldig få har
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	# Query params
	try:
		days = int(request.GET.get("days", 7))  # Default: last 7 days
	except ValueError:
		days = 7

	status_filter = request.GET.get("status")  # e.g., "500" or "4xx"
	limit = int(request.GET.get("limit", 100))  # Default: 100 rows

	start_date = timezone.now() - timezone.timedelta(days=days)

	# Base queryset
	qs = RequestLogs.objects.filter(timestamp__gte=start_date).exclude(status_code=200)

	# Apply status filter
	if status_filter:
		if status_filter.endswith("xx") and len(status_filter) == 3:
			# e.g., "4xx" → filter 400-499
			prefix = int(status_filter[0])
			qs = qs.filter(status_code__gte=prefix * 100, status_code__lt=(prefix + 1) * 100)
		else:
			try:
				code = int(status_filter)
				qs = qs.filter(status_code=code)
			except ValueError:
				pass  # Ignore invalid status filter

	errors = qs.order_by('-timestamp')[:limit]

	return render(request, 'recent_errors.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'errors': errors,
		'summary': {
			'days': days,
			'status_filter': status_filter,
			'limit': limit,
			'count': qs.count(),
			'from': start_date,
			'to': timezone.now(),
		}
	})





def top_slow_pages(request: HttpRequest):
	required_permissions = ['systemoversikt.view_qualysvuln'] # en rettighet veldig få har
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })
	"""
	Prioritize endpoints that consume the most total time in the last 7 days.
	Supports:
	  - ?min_requests=50   (only include endpoints with at least N requests)
	  - ?include_errors=0  (exclude status_code >= 400 by default)
	  - ?limit=50          (limit number of rows; default 50)
	"""
	one_week_ago = timezone.now() - timezone.timedelta(days=7)

	# Query params with defaults
	try:
		min_requests = int(request.GET.get("min_requests", 5))
	except ValueError:
		min_requests = 5

	try:
		limit = int(request.GET.get("limit", 50))
	except ValueError:
		limit = 50

	include_errors = request.GET.get("include_errors", "0")  # "0" (default) or "1"

	base_qs = RequestLogs.objects.filter(timestamp__gte=one_week_ago)

	if include_errors != "1":
		# Exclude 4xx and 5xx to focus on normal page performance
		base_qs = base_qs.filter(status_code__lt=400)

	# Aggregate by (path, method)
	aggregated = (
		base_qs
		.values("path", "method")
		.annotate(
			requests=Count("id"),
			avg_duration=Avg("duration_ms"),
			max_duration=Max("duration_ms"),
			total_duration=Sum("duration_ms"),
			avg_sql_queries=Avg("sql_queries"),
			total_sql_time=Sum("sql_time_ms"),
		)
		.filter(requests__gte=min_requests)
		.order_by("-total_duration")  # Primary prioritization: total time consumed
	)

	# Limit rows for display
	aggregated = list(aggregated[:limit])

	# Summary (for header)
	summary = {
		"from": one_week_ago,
		"to": timezone.now(),
		"min_requests": min_requests,
		"include_errors": include_errors == "1",
		"limit": limit,
		"endpoints": len(aggregated),
		"total_requests": base_qs.count(),
		"total_duration_ms": base_qs.aggregate(Sum("duration_ms"))["duration_ms__sum"] or 0,
		"total_sql_time_ms": base_qs.aggregate(Sum("sql_time_ms"))["sql_time_ms__sum"] or 0,
	}

	return render(request, "top_slow_pages.html", {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"rows": aggregated,
		"summary": summary,
	})




##########################
# Støttefunksjoner start #
##########################

def auth_er_ansvarlig(user):
	return True if len(Ansvarlig.objects.filter(brukernavn=user)) > 0 else False

def auth_er_systemforvalter(user):
	if auth_er_ansvarlig(user):
		# nå vet vi at vedkommende er registrert som ansvarlig
		ansvarlig = user.ansvarlig_brukernavn

		if SystemBruk.objects.filter(
			Q(systemeier_kontaktpersoner_referanse=ansvarlig) |
			Q(systemforvalter_kontaktpersoner_referanse=ansvarlig)
		).exists():
			return True

		if System.objects.filter(
			Q(systemeier_kontaktpersoner_referanse=ansvarlig) |
			Q(systemforvalter_kontaktpersoner_referanse=ansvarlig)
		).exists():
			return True

		return False

	else:
		return False

def auth_er_virksomhetsrolle(user):
	if auth_er_ansvarlig(user):
		ansvarlig = user.ansvarlig_brukernavn
		return True if Virksomhet.objects.filter(Q(ikt_kontakt=ansvarlig) | Q(personvernkoordinator=ansvarlig) | Q(informasjonssikkerhetskoordinator=ansvarlig)) else False
	else:
		return False


def user_can_change_virksomhet(user, virksomhet):
	# 2026-06-08: Mirror VirksomhetAdmin.has_change_permission for front-end virksomhet edits.
	if not user.is_authenticated:
		return False
	if user.is_superuser:
		return True
	if user.groups.filter(name="/DS-SYSTEMOVERSIKT_ADMINISTRATOR_ADMINISTRATOR").exists():
		return True
	if user.has_perm('systemoversikt.change_virksomhet'):
		try:
			return user.profile.virksomhet_id == virksomhet.pk
		except AttributeError:
			return False
	return False

def sharepoint_get_file(filename):
	from azure.identity import ClientSecretCredential
	from msgraph.core import GraphClient
	from django.utils.timezone import make_aware, is_aware
	import os
	import requests

	print(f'Starter nedlasting av "{filename}"...')

	client_credential = ClientSecretCredential(
			tenant_id=os.environ['AZURE_TENANT_ID'],
			client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
			client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
	)
	site_id = os.environ['SHAREPOINT_SITE_ID']
	library_id = os.environ['SHAREPOINT_LIBRARY_ID']

	client = GraphClient(credential=client_credential, api_version='beta')
	#query = f"/sites/{site_id}/drives/{library_id}/root/children" # liste alle elementer
	query = f"/sites/{site_id}/drives/{library_id}/items/root:/{filename}"
	#print(f"Spørring: {query}")
	resp = client.get(query)
	try:
		file_metadata = json.loads(resp.text)
	except json.JSONDecodeError as e:
		raise RuntimeError(
			f'Ugyldig JSON fra Microsoft Graph for "{filename}": {e}. '
			f'Svar (start): {resp.text[:800]!r}'
		) from e

	if not isinstance(file_metadata, dict):
		raise RuntimeError(
			f'Uventet Graph-svar for "{filename}": forventet objekt, fikk {type(file_metadata).__name__}'
		)

	if 'error' in file_metadata:
		err = file_metadata['error']
		code = err.get('code', '') if isinstance(err, dict) else ''
		msg = err.get('message', json.dumps(err)) if isinstance(err, dict) else repr(err)
		raise RuntimeError(
			f'Microsoft Graph feilet for "{filename}" (kode {code!r}): {msg}. '
			f'Sjekk filsti, SHAREPOINT_SITE_ID / SHAREPOINT_LIBRARY_ID og tilganger.'
		)

	last_modified_raw = file_metadata.get('lastModifiedDateTime')
	if not last_modified_raw:
		raise RuntimeError(
			f'Mangler lastModifiedDateTime i Graph-svar for "{filename}". '
			f'Toppnøkler i svaret: {list(file_metadata.keys())}. '
			f'Dette skjer ofte ved fil ikke funnet eller feil i stedet for drive-item.'
		)

	# ISO 8601 fra Graph (ev. med brøkdeler): 2024-01-15T12:00:00Z eller ...00.1234567Z
	ts = last_modified_raw.replace('Z', '+00:00') if last_modified_raw.endswith('Z') else last_modified_raw
	try:
		modified_dt = datetime.datetime.fromisoformat(ts)
	except ValueError:
		modified_dt = datetime.datetime.strptime(last_modified_raw, '%Y-%m-%dT%H:%M:%SZ')
	if not is_aware(modified_dt):
		modified_date = make_aware(modified_dt)
	else:
		modified_date = modified_dt

	download_url = file_metadata.get('@microsoft.graph.downloadUrl')
	if not download_url:
		raise RuntimeError(
			f'Mangler @microsoft.graph.downloadUrl for "{filename}". Toppnøkler: {list(file_metadata.keys())}'
		)

	destination_file = f'systemoversikt/import/{filename}'

	response = requests.get(download_url)
	with open(destination_file, "wb") as f:
		f.write(response.content)
	#print(f"Lastet ned fil til {destination_file} ")

	return {"destination_file": destination_file, "modified_date": modified_date}


def decode_ad_timestamp(raw_value):
	"""Convert AD FILETIME attribute bytes to datetime (100 ns since 1601-01-01)."""
	ms_timestamp = int(raw_value[:-1].decode())
	return datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=ms_timestamp)


def decode_useraccountcontrol(code):
	#https://support.microsoft.com/nb-no/help/305144/how-to-use-useraccountcontrol-to-manipulate-user-account-properties
	active_codes = []
	status_codes = {
			"SCRIPT": 0,
			"ACCOUNTDISABLE": 1,
			"HOMEDIR_REQUIRED": 2,
			"LOCKOUT": 4,
			"PASSWD_NOTREQD": 5,
			"PASSWD_CANT_CHANGE": 6,
			"ENCRYPTED_TEXT_PWD_ALLOWED": 7,
			"TEMP_DUPLICATE_ACCOUNT": 8,
			"NORMAL_ACCOUNT": 9,
			"INTERDOMAIN_TRUST_ACCOUNT": 11,
			"WORKSTATION_TRUST_ACCOUNT": 12,
			"SERVER_TRUST_ACCOUNT": 13,
			"DONT_EXPIRE_PASSWORD": 16,
			"PASSWORD_EXPIRED": 23,
			"MNS_LOGON_ACCOUNT": 17,
			"SMARTCARD_REQUIRED": 18,
			"TRUSTED_FOR_DELEGATION": 19,
			"NOT_DELEGATED": 20,
			"USE_DES_KEY_ONLY": 21,
			"DONT_REQ_PREAUTH": 22,
			"TRUSTED_TO_AUTH_FOR_DELEGATION": 24,
			"PARTIAL_SECRETS_ACCOUNT": 26,
		}
	for key in status_codes:
		if int(code) >> status_codes[key] & 1:
			active_codes.append(key)
	return active_codes


def push_pushover(message):
	import os, requests
	import http.client
	USER_KEY = os.environ['PUSHOVER_USER_KEY']
	APP_TOKEN = os.environ['PUSHOVER_APP_TOKEN']
	if USER_KEY != "" and APP_TOKEN != "":
		try:
			payload = {"message": message, "user": USER_KEY, "token": APP_TOKEN}
			r = requests.post('https://api.pushover.net/1/messages.json', data=payload, headers={'User-Agent': 'Python'})
			conn = http.client.HTTPSConnection("api.pushover.net:443")
		except Exception as e:
			print(f"Error: Kan ikke sende til pushover grunnet {e}")
		return
	print(f"Pushover er ikke konfigurert")


def get_client_ip(request): # støttefunksjon
	try:
		x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
		if x_forwarded_for:
			ip = x_forwarded_for.split(',')[0]
		else:
			ip = request.META.get('REMOTE_ADDR')
		return ip
	except:
		return "get_client_ip() feilet"


def ldap_query(ldap_path, ldap_filter, ldap_properties, timeout): # støttefunksjon for LDAP
	import ldap, os
	server = 'ldaps://ldaps.oslofelles.oslo.kommune.no:636'
	user = os.environ["KARTOTEKET_LDAPUSER"]
	password = os.environ["KARTOTEKET_LDAPPASSWORD"]
	ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # have to deactivate sertificate check
	ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
	ldapClient = ldap.initialize(server)
	ldapClient.timeout = timeout
	ldapClient.set_option(ldap.OPT_REFERRALS, 0)  # tells the server not to chase referrals
	ldapClient.bind_s(user, password)  # synchronious

	result = ldapClient.search_s(
			ldap_path,
			ldap.SCOPE_SUBTREE,
			ldap_filter,
			ldap_properties
	)

	ldapClient.unbind_s()
	return result

"""
def ldap_get_user_details(username): # støttefunksjon for LDAP

	ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
	ldap_filter = ('(&(objectClass=user)(cn=%s))' % username)
	ldap_properties = ['cn', 'mail', 'givenName', 'displayName', 'sn', 'userAccountControl', 'logonCount', 'memberOf', 'lastLogonTimestamp', 'title', 'description', 'otherMobile', 'mobile', 'objectClass']

	result = ldap_query(ldap_path=ldap_path, ldap_filter=ldap_filter, ldap_properties=ldap_properties, timeout=10)
	users = []
	for cn,attrs in result:
		if cn:
			attrs_decoded = {}
			for key in attrs:
				attrs_decoded[key] = []
				if key == "lastLogonTimestamp":
					# always just one timestamp, hence item 0 hardcoded
					ms_timestamp = int(attrs[key][0][:-1].decode())  # removing one trailing digit converting 100ns to microsec.
					converted_date = datetime.datetime(1601,1,1) + datetime.timedelta(microseconds=ms_timestamp)
					attrs_decoded[key].append(converted_date)
				elif key == "userAccountControl":
					accountControl = decode_useraccountcontrol(int(attrs[key][0].decode()))
					attrs_decoded[key].append(accountControl)
				elif key == "memberOf":
					for element in attrs[key]:
						e = element.decode()
						regex_find_group = re.search(r'cn=([^\,]*)', e, re.I).groups()[0]

						attrs_decoded[key].append({
								"group": regex_find_group,
								"cn": e,
						})
					continue  # skip the next for..
				else:
					for element in attrs[key]:
						attrs_decoded[key].append(element.decode())

			users.append({
					"cn": cn,
					"attrs": attrs_decoded,
			})
	return users


def ldap_get_group_details(group): # støttefunksjon for LDAP

	ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
	ldap_filter = ('(&(cn=%s)(objectclass=group))' % group)
	ldap_properties = ['description', 'cn', 'member', 'objectClass']

	result = ldap_query(ldap_path=ldap_path, ldap_filter=ldap_filter, ldap_properties=ldap_properties, timeout=10)

	groups = []
	for cn,attrs in result:
		if cn:
			attrs_decoded = {}
			for key in attrs:
				attrs_decoded[key] = []
				if key == "member":
					for element in attrs[key]:
						e = element.decode()
						regex_find_username = re.search(r'cn=([^\,]*)', e, re.I).groups()[0]

						try:
							user = User.objects.get(username__iexact=regex_find_username)
						except:
							user = None

						attrs_decoded[key].append({
								"username": regex_find_username,
								"user": user,
								"cn": e,
						})
					continue  # skip the next for..
				for element in attrs[key]:
					attrs_decoded[key].append(element.decode())

			groups.append({
					"cn": cn,
					"attrs": attrs_decoded,
			})
	return groups
"""


def ldap_get_recursive_group_members(group): # støttefunksjon for LDAP
	ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
	ldap_filter = ('(&(objectCategory=person)(objectClass=user)(memberOf:1.2.840.113556.1.4.1941:=%s))' % group)
	ldap_properties = ['cn', 'displayName', 'description']

	result = ldap_query(ldap_path=ldap_path, ldap_filter=ldap_filter, ldap_properties=ldap_properties, timeout=100)
	users = []

	for cn,attrs in result:
		if cn:
			attrs_decoded = {}
			for key in attrs:
				attrs_decoded[key] = []
				for element in attrs[key]:
					attrs_decoded[key].append(element.decode())

			users.append({
					"cn": cn,
					"attrs": attrs_decoded,
			})

	return users


def ldap_users_securitygroups(user): # støttefunksjon for LDAP
	ldap_filter = ('(cn=%s)' % user)
	result = ldap_query(ldap_path="DC=oslofelles,DC=oslo,DC=kommune,DC=no", ldap_filter=ldap_filter, ldap_properties=[], timeout=5)
	try:
		memberof = result[0][1]['memberOf']
		return([g.decode() for g in memberof])
	except:
		#print(f"Finner ikke 'memberof' attributtet for {user}.")
		#print("error ldap_users_securitygroups(): %s" %(result))
		return []


def convert_distinguishedname_cn(liste): # støttefunksjon
	return [re.search(r'cn=([^\,]*)', g, re.I).groups()[0] for g in liste]


def decode_sid(sid):
	revision, sub_authority_count = struct.unpack('BB', sid[:2])
	identifier_authority = struct.unpack('>Q', b'\x00\x00' + sid[2:8])[0]
	sub_authorities = struct.unpack('<' + 'I' * sub_authority_count, sid[8:])
	return 'S-{}-{}-{}'.format(revision, identifier_authority, '-'.join(map(str, sub_authorities)))


def ldap_get_details(name, ldap_filter, request): # støttefunksjon
	ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
	ldap_properties = []
	result = ldap_query(ldap_path=ldap_path, ldap_filter=ldap_filter, ldap_properties=ldap_properties, timeout=10)
	groups = []
	users = []
	computers = []

	for cn,attrs in result:
		if cn:

			if b'computer' in attrs["objectClass"]:
				attrs_decoded = {}
				for key in attrs:
					if key in ['description', 'cn', 'objectClass', 'operatingSystem', 'operatingSystemVersion', 'dNSHostName',]:
						attrs_decoded[key] = []
						for element in attrs[key]:
							attrs_decoded[key].append(element.decode())
					else:
						continue

				computers.append({
						"cn": cn,
						"attrs": attrs_decoded,
				})

				return ({
						"computers": computers,
						"raw": result,
					})


			if b'user' in attrs["objectClass"]:
				import codecs
				attrs_decoded = {}
				for key in attrs:
					try:
						if key in ['objectGUID', 'objectSid', 'cn', 'sAMAccountName', 'mail', 'givenName', 'displayName', 'whenCreated', 'sn', 'userAccountControl', 'logonCount', 'memberOf', 'lastLogonTimestamp', 'title', 'description', 'otherMobile', 'mobile', 'objectClass', 'thumbnailPhoto']:
							# if not, then we don't bother decoding the value for now
							attrs_decoded[key] = []
							if key == "lastLogonTimestamp":
								# always just one timestamp, hence item 0 hardcoded
								attrs_decoded[key].append(decode_ad_timestamp(attrs[key][0]))

							elif key == "objectGUID":
								import uuid
								for element in attrs[key]:
									attrs_decoded[key].append(uuid.UUID(bytes_le=element))

							elif key == "objectSid":
								for element in attrs[key]:
									attrs_decoded[key].append(decode_sid(element))

							elif key == "whenCreated":
								value = attrs[key][0].decode().split('.')[0]
								converted_date = datetime.datetime.strptime(value, "%Y%m%d%H%M%S")
								attrs_decoded[key].append(converted_date)
							elif key == "userAccountControl":
								accountControl = decode_useraccountcontrol(int(attrs[key][0].decode()))
								attrs_decoded[key].append(accountControl)
							elif key == "thumbnailPhoto":
								attrs_decoded[key].append(codecs.encode(attrs[key][0], 'base64').decode('utf-8'))
							elif key == "memberOf":
								for element in attrs[key]:
									e = element.decode()
									regex_find_group = re.search(r'cn=([^\,]*)', e, re.I).groups()[0]

									attrs_decoded[key].append({
											"group": regex_find_group,
											"cn": e,
									})
								continue  # skip the next for..
							else:
								for element in attrs[key]:
									attrs_decoded[key].append(element.decode())
						else:
							continue
					except Exception as e:
						messages.warning(request, e)

				users.append({
						"cn": cn,
						"attrs": attrs_decoded,
				})
				return ({
						"users": users,
						"raw": result,
					})


			if b'group' in attrs["objectClass"]:
				attrs_decoded = {}
				for key in attrs:
					if key in ['description', 'cn', 'member', 'objectClass', 'memberOf']:
						attrs_decoded[key] = []
						if key == "member":
							for element in attrs[key]:
								e = element.decode()
								regex_find_username = re.search(r'cn=([^\,]*)', e, re.I).groups()[0]

								try:
									user = User.objects.get(username__iexact=regex_find_username)
								except:
									user = None

								attrs_decoded[key].append({
										"username": regex_find_username,
										"user": user,
										"cn": e,
								})
							continue  # skip the next for..
						for element in attrs[key]:
							attrs_decoded[key].append(element.decode())
					else:
						continue

				groups.append({
						"cn": cn,
						"attrs": attrs_decoded,
				})
				return ({
						"groups": groups,
						"raw": result,
					})
	return None

"""
def ldap_exact(name): # støttefunksjon for LDAP
	ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
	ldap_filter = ('(distinguishedName=%s)' % name)
	ldap_properties = []

	result = ldap_query(ldap_path=ldap_path, ldap_filter=ldap_filter, ldap_properties=ldap_properties, timeout=100)
	prepare = []

	for cn,attrs in result:
		if cn:
			attrs_decoded = {}
			for key in attrs:
				attrs_decoded[key] = []
				for element in attrs[key]:
					try:
						attrs_decoded[key].append(element.decode())
					except:
						attrs_decoded[key].append(element)

			prepare.append({
					"cn": cn,
					"attrs": attrs_decoded,
			})

	return {"raw": prepare}
"""


def get_ipaddr_instance(address):

	if address == "" or address == None or address == "0.0.0.0":
		return None
	try:
		return NetworkIPAddress.objects.get(ip_address=address)
	except:
		n = NetworkIPAddress.objects.create(ip_address=address)
		n.ip_address_integer = int(ipaddress.ip_address(n.ip_address))
		n.save()
		return n

def login(request):
	"""
	støttefunksjon for å logge inn
	"""
	if settings.THIS_ENVIRONMENT == "PROD":
		return redirect(reverse('oidc_authentication_init'))
	else:
		return redirect("/admin/")

def unique_splitted_items(text):
	text = text.strip() # leading and trailing spaces
	filtered = text.replace('\"','').replace('\'','').replace(',',' ').replace(';',' ').replace(':',' ').replace('|',' ').lower()
	splitted = filtered.split()
	unike = set(splitted)
	return unike


def formater_permissions(permissions):
	if permissions == None:
		return []
	return [tag.replace(".", ": ").replace("_", " ") for tag in permissions]


def adgruppe_utnosting(gr): # støttefunksjon
	hierarki = []
	hierarki.append(gr)

	def identifiser_underliggende_grupper(gr):
		child_groups = []
		for element in json.loads(gr.member):
			try: # fra LDAP-svaret vet vi ikke om en member er en gruppe eller en brukerident. Vi må derfor slå opp.
				g = ADgroup.objects.get(distinguishedname=element)
				child_groups.append(g)
			except:
				pass # må være noe annet enn en gruppe, gitt at kartotekets database er synkronisert med AD
		return child_groups

	stack = []
	stack += identifiser_underliggende_grupper(gr)

	while stack:
		denne_gruppen = stack.pop()
		#print(denne_gruppen)
		hierarki.append(denne_gruppen)
		nye_undergrupper = identifiser_underliggende_grupper(denne_gruppen)
		for ug in nye_undergrupper:
			if ug not in hierarki:
				stack.append(ug)

	return hierarki


""" without caching
def human_readable_members(items, onlygroups=False): # støttefunksjon
	groups = []
	users = []
	notfound = []

	for item in items:
		print(item)
		match = False
		if onlygroups == False:
			regex_username = re.search(r'cn=([^\,]*)', item, re.I).groups()[0]
			try:
				u = User.objects.get(username__iexact=regex_username)
				users.append(u)
				match = True
				continue
			except:
				pass
		try:
			g = ADgroup.objects.get(distinguishedname=item)
			groups.append(g)
		except:
			notfound.append(item)  # vi fant ikke noe, returner det vi fikk

	return {"groups": groups, "users": users, "notfound": notfound}
"""

def human_readable_members(items, onlygroups=False): # støttefunksjon, with caching
	groups = []
	users = []
	notfound = []

	# Pre-fetch all users and groups
	all_users = {user.username.lower(): user for user in User.objects.all()}
	all_groups = {group.distinguishedname: group for group in ADgroup.objects.all()}

	for item in items:
		match = False
		if not onlygroups:
			regex_username = re.search(r'cn=([^\,]*)', item, re.I).groups()[0].lower()
			if regex_username in all_users:
				users.append(all_users[regex_username])
				match = True
				continue

		if item in all_groups:
			groups.append(all_groups[item])
		else:
			notfound.append(item)  # vi fant ikke noe, returner det vi fikk

	return {"groups": groups, "users": users, "notfound": notfound}




def human_readable_members_optimized(items, onlygroups=False):
	"""
	Convert AD member DNs to human-readable objects.
	Optimized: bulk query only needed users/groups.
	"""
	groups = []
	users = []
	notfound = []

	if not items:
		return {"groups": [], "users": [], "notfound": []}

	# Extract usernames and group DNs
	usernames = []
	group_dns = []

	for item in items:
		if not onlygroups:
			match = re.search(r'cn=([^,]*)', item, re.I)
			if match:
				usernames.append(match.group(1).lower())
		group_dns.append(item)

	# Bulk fetch users and groups
	user_map = {}
	if not onlygroups and usernames:
		user_qs = User.objects.filter(username__in=usernames).only('username')
		user_map = {u.username.lower(): u for u in user_qs}

	group_qs = ADgroup.objects.filter(distinguishedname__in=group_dns).only('distinguishedname', 'common_name')
	group_map = {g.distinguishedname: g for g in group_qs}

	# Build result lists
	for item in items:
		added = False
		if not onlygroups:
			match = re.search(r'cn=([^,]*)', item, re.I)
			if match:
				uname = match.group(1).lower()
				if uname in user_map:
					users.append(user_map[uname])
					added = True
		if item in group_map:
			groups.append(group_map[item])
			added = True
		if not added:
			notfound.append(item)

	return {"groups": groups, "users": users, "notfound": notfound}



##########################
# Støttefunksjoner slutt #
##########################



##################
# Ordinære views #
##################

def mal(request):
	required_permissions = ['systemoversikt.XYZ']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	return render(request, 'mal.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})


def tools_index(request):
	required_permissions = None
	return render(request, 'tools_index.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})


def debug_info(request):
	"""
	Denne funksjonen viser debug-informasjon ifm. feilsøking av bibliotek og moduler
	Tilgjengelig for personer som kan se logger
	"""
	required_permissions = ['auth.view_logentry']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(
			request,
			'403.html',
			{
				'required_permissions': required_permissions,
				'groups': request.user.groups
			}
		)


	# --- PostgreSQL / database info ---
	from django.db import connection
	try:
		with connection.cursor() as cursor:
			cursor.execute("SELECT version()")
			pg_version = cursor.fetchone()[0]

		db_settings = connection.settings_dict
		db_info = {
			"engine": db_settings.get("ENGINE"),
			"name": db_settings.get("NAME"),
			"user": db_settings.get("USER"),
			"host": db_settings.get("HOST"),
			"port": db_settings.get("PORT"),
			"server_version": pg_version,
		}
	except Exception as e:
		db_info = {"error": str(e)}


	#import sqlite3
	#sqlite_info = "SQLite: %s %s" % (sqlite3.version, sqlite3.__path__)

	import sys
	python_info = "Python: %s %s" % (sys.version, sys.executable)

	import django
	django_info = "Django: %s %s" % (django.VERSION, django.__path__)

	# --- NEW: pip modules ---
	import subprocess

	try:
		pip_output = subprocess.check_output(
			[sys.executable, "-m", "pip", "freeze"],
			text=True
		)
		pip_modules = pip_output.splitlines()
	except Exception as e:
		pip_modules = ["Could not list pip packages: %s" % e]

	return render(request, 'system_debug_info.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		#'sqlite_info': sqlite_info,
		'db_info': db_info,
		'python_info': python_info,
		'django_info': django_info,
		'pip_modules': pip_modules,
	})


def tool_ntfs(request):
	from systemoversikt.sddl_parser import SddlParseError, parse_sddl

	required_permissions = None
	sddl_input = request.POST.get('sddl_input', '')
	permission_type = request.POST.get('permission_type', 'file')
	parsed = None
	error = None

	if request.method == 'POST' and sddl_input.strip():
		try:
			parsed = parse_sddl(sddl_input, permission_type=permission_type)
		except SddlParseError as exc:
			error = str(exc)

	return render(request, 'tool_ntfs.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'sddl_input': sddl_input,
		'permission_type': permission_type,
		'parsed': parsed,
		'error': error,
	})


def tool_service_announcements(request):
	import json
	from systemoversikt.graph_service_announcements import fetch_latest_service_announcement_messages

	required_permissions = None
	messages, error = fetch_latest_service_announcement_messages(limit=10)

	return render(request, 'tool_service_announcements.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'messages': messages,
		'messages_json': json.dumps(messages, indent=2, ensure_ascii=False),
		'error': error,
	})


def tool_word_count(request):
	required_permissions = None
	import collections
	inndata = request.POST.get('inndata', '')
	filtered = inndata.replace(',',' ').replace(';',' ').replace(':',' ').replace('|',' ').replace('.','').lower()
	words = filtered.split()
	stripped_words = []
	for w in words:
		stripped_words.append(w.strip())

	counter = collections.Counter(stripped_words)
	alle_ord = [{"ord": word, "frekvens": frequency} for word, frequency in dict(counter).items()]

	return render(request, 'tool_word_count.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"alle_ord": alle_ord,
		"inndata": inndata,
	})


def vulnstats_nettverk(request):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	data = {}
	data["nettverksenheter"] = CMDBdevice.objects.filter(device_type="NETWORK")

	return render(request, 'rapport_vulnstats_nettverk.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'integrasjonsstatus': integrasjonsstatus,
		'data': data,
	})



def vulnstats_datakvalitet(request):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	data = {}
	data["count_uten_server"] = QualysVuln.objects.filter(server=None).count()
	data["count_uten_server_antall_servere"] = QualysVuln.objects.filter(server=None).values("source").distinct().count()

	data["count_servere_aktive"] = CMDBdevice.objects.filter(device_type="SERVER").count()
	data["count_servere_uten_vuln"] = CMDBdevice.objects.filter(device_type="SERVER").filter(qualys_vulnerabilities=None).count()

	# servere uten offering-kobling
	data["servere_uten_offering"] = CMDBdevice.objects.filter(service_offerings=None, device_type__in=["SERVER", "NETTWORK"])

	# eksponert internett kartoteket vs qualys
	dager_gamle = 30
	tidsgrense = datetime.date.today() - datetime.timedelta(days=dager_gamle)
	kartoteket_internett_eksponert = set(CMDBdevice.objects.filter(eksternt_eksponert_dato__gte=tidsgrense))
	qualys_internett_eksponert = set(CMDBdevice.objects.filter(qualys_vulnerabilities__public_facing=True))
	data["eksponert_kun_kartoteket"] = kartoteket_internett_eksponert - qualys_internett_eksponert
	data["eksponert_kun_qualys"] = qualys_internett_eksponert - kartoteket_internett_eksponert
	data["eksponert_dager_gamle"] = dager_gamle

	return render(request, 'rapport_vulnstats_datakvalitet.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'integrasjonsstatus': integrasjonsstatus,
		'data': data,
	})


def _qualys_import_chart_from_audit_log():
	# 2026-07-02: Qualys import + CMDB server import timeline from ApplicationLog.
	qualys_import_total_pattern = re.compile(
		r'importing\s+(\d+)\s+vulnerabilities,\s+where\s+(\d+)\s+of them failed server lookup',
		re.I,
	)
	qualys_severity_pattern = re.compile(r'Alvorlighet\s+([1-5]):\s*(\d+)', re.I)
	cmdb_server_import_pattern = re.compile(r'Importen inneholder\s+(\d+)\s+servere', re.I)
	points = []

	for log in ApplicationLog.objects.filter(
		event_type="Qualys import",
		message__icontains="Done importing",
	).order_by('opprettet'):
		match = qualys_import_total_pattern.search(log.message)
		if not match:
			continue
		severities = {severity: 0 for severity in range(1, 6)}
		for severity_match in qualys_severity_pattern.finditer(log.message):
			severities[int(severity_match.group(1))] = int(severity_match.group(2))
		points.append({
			"dt": log.opprettet,
			"qualys_total": int(match.group(1)),
			"severities": severities,
			"servers": None,
		})

	for log in ApplicationLog.objects.filter(
		event_type="CMDB server import",
		message__icontains="Importen inneholder",
	).order_by('opprettet'):
		match = cmdb_server_import_pattern.search(log.message)
		if not match:
			continue
		points.append({
			"dt": log.opprettet,
			"qualys_total": None,
			"severities": None,
			"servers": int(match.group(1)),
		})

	if not points:
		return None

	points.sort(key=lambda point: point["dt"])
	labels = []
	total = []
	servers = []
	severity_series = {severity: [] for severity in range(1, 6)}
	for point in points:
		labels.append(point["dt"].strftime("%d %b %y"))
		total.append(point["qualys_total"])
		servers.append(point["servers"])
		if point["severities"]:
			for severity in range(1, 6):
				severity_series[severity].append(point["severities"][severity])
		else:
			for severity in range(1, 6):
				severity_series[severity].append(None)

	return {
		"labels": labels,
		"total": total,
		"servers": servers,
		"severities": severity_series,
	}


def sikkerhet_sarbarheter(request):
	# 2026-07-02: Landing page for Qualys, Defender and compare reports; Qualys import chart from audit log.
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	return render(request, 'sikkerhet_sarbarheter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'qualys_import_chart': _qualys_import_chart_from_audit_log(),
		'integrasjonsstatus_qualys': _integrasjonsstatus("sp_qualys"),
	})


def vulnstats(request):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	data = {}

	data["count_all"] = QualysVuln.objects.all().count()

	#data["count_unike_alvorligheter"] = QualysVuln.objects.values('severity').annotate(count=Count('severity'))
	#if len(data["count_unike_alvorligheter"]) > 0:
	#   severities = {item['severity'] for item in data["count_unike_alvorligheter"]}
	#   [data["count_unike_alvorligheter"].append({"severity": severity, "count": 0}) for severity in range(1, 6) if severity not in severities]
	#   data["count_unike_alvorligheter"] = sorted(data["count_unike_alvorligheter"], key=lambda x: x['severity'], reverse=False)

	data["count_unike_alvorligheter_eol"] = list(QualysVuln.objects.filter(server__derived_os_endoflife=True).values('severity').annotate(count=Count('severity')))
	if len(data["count_unike_alvorligheter_eol"]) > 0:
		severities = {item['severity'] for item in data["count_unike_alvorligheter_eol"]}
		[data["count_unike_alvorligheter_eol"].append({"severity": severity, "count": 0}) for severity in range(1, 6) if severity not in severities]
		data["count_unike_alvorligheter_eol"] = sorted(data["count_unike_alvorligheter_eol"], key=lambda x: x['severity'], reverse=False)

	data["count_unike_vulns"] = list(QualysVuln.objects.values('severity').annotate(unique_titles=Count('severity')))
	if len(data["count_unike_vulns"]) > 0:
		severities = {item['severity'] for item in data["count_unike_vulns"]}
		[data["count_unike_vulns"].append({"severity": severity, "unique_titles": 0}) for severity in range(1, 6) if severity not in severities]
		data["count_unike_vulns"] = sorted(data["count_unike_vulns"], key=lambda x: x['severity'], reverse=False)

	data["count_unike_known_exploited_vulns"] = list(QualysVuln.objects.filter(known_exploited=True).values('severity').annotate(unique_titles=Count('severity')))
	if len(data["count_unike_known_exploited_vulns"]) > 0:
		severities = {item['severity'] for item in data["count_unike_known_exploited_vulns"]}
		[data["count_unike_known_exploited_vulns"].append({"severity": severity, "unique_titles": 0}) for severity in range(1, 6) if severity not in severities]
		data["count_unike_known_exploited_vulns"] = sorted(data["count_unike_known_exploited_vulns"], key=lambda x: x['severity'], reverse=False)

	data["count_unike_known_exploited_public_face"] = list(QualysVuln.objects.filter(known_exploited=True, public_facing=True).values('severity').annotate(unique_titles=Count('severity')))
	if len(data["count_unike_known_exploited_public_face"]) > 0:
		severities = {item['severity'] for item in data["count_unike_known_exploited_public_face"]}
		[data["count_unike_known_exploited_public_face"].append({"severity": severity, "unique_titles": 0}) for severity in range(1, 6) if severity not in severities]
		data["count_unike_known_exploited_public_face"] = sorted(data["count_unike_known_exploited_public_face"], key=lambda x: x['severity'], reverse=False)


	# samme, men filtrert bort siste måneden
	for_nytt_dager = 30
	for_nytt = timezone.now() - datetime.timedelta(days=for_nytt_dager)

	data["count_unike_vulns_not_current"] = QualysVuln.objects.filter(first_seen__lte=for_nytt).values('severity').annotate(unique_titles=Count('severity'))
	if len(data["count_unike_vulns_not_current"]) > 0:
		severities = {item['severity'] for item in data["count_unike_vulns_not_current"]}
		[data["count_unike_vulns_not_current"].append({"severity": severity, "unique_titles": 0}) for severity in range(1, 6) if severity not in severities]
		data["count_unike_vulns_not_current"] = sorted(data["count_unike_vulns_not_current"], key=lambda x: x['severity'], reverse=False)

	data["count_unike_known_exploited_vulns_not_current"] = list(QualysVuln.objects.filter(first_seen__lte=for_nytt).filter(known_exploited=True).values('severity').annotate(unique_titles=Count('severity')))
	if len(data["count_unike_known_exploited_vulns_not_current"]) > 0:
		severities = {item['severity'] for item in data["count_unike_known_exploited_vulns_not_current"]}
		[data["count_unike_known_exploited_vulns_not_current"].append({"severity": severity, "unique_titles": 0}) for severity in range(1, 6) if severity not in severities]
		data["count_unike_known_exploited_vulns_not_current"] = sorted(data["count_unike_known_exploited_vulns_not_current"], key=lambda x: x['severity'], reverse=False)

	data["count_unike_known_exploited_public_face_not_current"] = list(QualysVuln.objects.filter(first_seen__lte=for_nytt).filter(known_exploited=True, public_facing=True).values('severity').annotate(unique_titles=Count('severity')))
	if len(data["count_unike_known_exploited_public_face_not_current"]) > 0:
		severities = {item['severity'] for item in data["count_unike_known_exploited_public_face_not_current"]}
		[data["count_unike_known_exploited_public_face_not_current"].append({"severity": severity, "unique_titles": 0}) for severity in range(1, 6) if severity not in severities]
		data["count_unike_known_exploited_public_face_not_current"] = sorted(data["count_unike_known_exploited_public_face_not_current"], key=lambda x: x['severity'], reverse=False)

	#Sårbarheter fordelt på "først sett" dato
	data["count_first_seen_monthly"] = list(QualysVuln.objects.annotate(
				year=TruncYear('first_seen'),
				month=TruncMonth('first_seen')
				).values('year', 'month').annotate(count=Count('id')).order_by('year', 'month'))

	data["count_last_seen_monthly"] = list(QualysVuln.objects.annotate(
				year=TruncYear('last_seen'),
				day=TruncDay('last_seen')
				).values('year', 'day').annotate(count=Count('id')).order_by('year', 'day'))

	data["count_first_seen_monthly_public_facing_5"] = QualysVuln.objects.filter(known_exploited=True, severity__in=[5]).annotate(
				year=TruncYear('first_seen'),
				month=TruncMonth('first_seen')
				).values('year', 'month').annotate(count=Count('id')).order_by('year', 'month')

	data["count_first_seen_monthly_public_facing_4"] = QualysVuln.objects.filter(known_exploited=True, severity__in=[4]).annotate(
				year=TruncYear('first_seen'),
				month=TruncMonth('first_seen')
				).values('year', 'month').annotate(count=Count('id')).order_by('year', 'month')

	data["vulns_first_seen_monthly_public_facing_5"] = QualysVuln.objects.filter(known_exploited=True, severity__in=[5]).values('title', 'akseptert').annotate(count=Count('title')).order_by('-count')
	data["vulns_first_seen_monthly_public_facing_4"] = QualysVuln.objects.filter(known_exploited=True, severity__in=[4]).values('title', 'akseptert').annotate(count=Count('title')).order_by('-count')


	data["antall_servere_per_datasenter"] = (
		CMDBdevice.objects
		.filter(device_type__in=["SERVER", "NETWORK"])
		.values("comp_location")
		.annotate(
			antall_servere=Count("id", distinct=True),

			antall_servere_med_saarbarheter=Count(
				"id",
				filter=Q(qualys_vulnerabilities__isnull=False),
				distinct=True
			),

			antall_saarbarheter=Count("qualys_vulnerabilities"),
		)
		.annotate(
			snitt_saarbarheter_per_server=Case(
				When(
					antall_servere_med_saarbarheter__gt=0,
					then=ExpressionWrapper(
						F("antall_saarbarheter") * 1.0
						/ F("antall_servere_med_saarbarheter"),
						output_field=FloatField()
					)
				),
				default=Value(None),
				output_field=FloatField(),
			)
		)
	)

	# 2026-06-22: Bar widths for per-environment tiles – relative to max servere / snitt / server share.
	loc_stats = list(data["antall_servere_per_datasenter"])
	max_servere = max(
		(row.get("antall_servere") or 0) for row in loc_stats
	) if loc_stats else 0
	max_snitt = max(
		(row.get("snitt_saarbarheter_per_server") or 0) for row in loc_stats
	) if loc_stats else 0
	for row in loc_stats:
		servers = row.get("antall_servere") or 0
		if servers and max_servere:
			row["servere_bar_pct"] = round(100 * servers / max_servere)
		else:
			row["servere_bar_pct"] = 0
		snitt = row.get("snitt_saarbarheter_per_server")
		if snitt and max_snitt:
			row["snitt_bar_pct"] = round(100 * snitt / max_snitt)
		else:
			row["snitt_bar_pct"] = 0
		affected = row.get("antall_servere_med_saarbarheter") or 0
		row["servere_med_vuln_pct"] = round(100 * affected / servers) if servers else 0
	data["antall_servere_per_datasenter"] = loc_stats

	return render(request, 'rapport_vulnstats.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'for_nytt_dager': for_nytt_dager,
		'integrasjonsstatus': integrasjonsstatus,
	})


def azure_vulnstats_qualys_compare(request):
	# 2026-06-07: Qualys vs Defender CVE comparison on dedicated URL (moved off overview).
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("azure_vulnerabilities")

	integrasjonsstatus_qualys = _integrasjonsstatus("sp_qualys")

	cache_version = "v2"
	azure_ts = _azure_vulnstats_cache_ts_token(integrasjonsstatus)
	qualys_ts = _azure_vulnstats_cache_ts_token(integrasjonsstatus_qualys)
	cache_key = f"azure_vulnstats:qualys_compare:{cache_version}:{azure_ts}:{qualys_ts}"
	data = cache.get(cache_key)

	if data is None:
		data = _azure_vulnstats_qualys_defender_comparison()
		cache.set(cache_key, data, timeout=60 * 60 * 24)

	return render(request, 'rapport_azure_vulnstats_qualys_compare.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'integrasjonsstatus': integrasjonsstatus,
		'integrasjonsstatus_qualys': integrasjonsstatus_qualys,
		'data': data,
	})


def azure_vulnstats(request):
	# 2026-06-07: Exclude Windows 11 client OS from overview aggregates – faster page, easy to revert.
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("azure_vulnerabilities")

	cache_version = "v16"
	cache_ts = _azure_vulnstats_cache_ts_token(integrasjonsstatus)
	cache_key = f"azure_vulnstats:overview:{cache_version}:{cache_ts}"
	data = cache.get(cache_key)

	if data is None:
		active = _azure_vulnstats_overview_active()

		severity_order = ["Critical", "High"]
		severity_colors = {
			"Critical": "rgb(220, 53, 69)",   # bootstrap danger-ish
			"High": "rgb(255, 193, 7)",       # warning-ish
		}

		year_severity_rows = list(
			active.annotate(cve_year=Substr("cve__cve_id", 5, 4))
			.values("cve_year", "severity")
			.annotate(count=Count("id"))
			.order_by("cve_year", "severity")
		)

		years = sorted({r["cve_year"] for r in year_severity_rows if r.get("cve_year")})
		year_index = {y: i for i, y in enumerate(years)}

		# Build datasets for chart.js (stacked bars).
		counts = {sev: [0] * len(years) for sev in severity_order}
		for r in year_severity_rows:
			y = r.get("cve_year")
			if not y or y not in year_index:
				continue
			sev = r.get("severity")
			if sev not in counts:
				continue
			counts[sev][year_index[y]] = r.get("count") or 0

		severities_present = [s for s in severity_order if any(counts[s])]

		cve_year_chart = {
			"labels": years,
			"datasets": [
				{
					"label": sev,
					"data": counts[sev],
					"backgroundColor": severity_colors.get(sev, "rgb(0, 123, 255)"),
				}
				for sev in severities_present
			],
		}

		os_device_summary = list(
			active.values("device__os_platform")
			.annotate(
				device_count=Count("device", distinct=True),
				vuln_count=Count("id"),
			)
			.order_by("-vuln_count", "device__os_platform")
		)
		for row in os_device_summary:
			devices = row.get("device_count") or 0
			vulns = row.get("vuln_count") or 0
			row["avg_vulns_per_device"] = (vulns / devices) if devices else None

		distinct_counts = active.aggregate(
			devices_with_vuln=Count("device", distinct=True),
			distinct_cves=Count("cve", distinct=True),
		)

		data = {
			"count_active": active.count(),
			"count_devices_with_vuln": distinct_counts["devices_with_vuln"] or 0,
			"count_distinct_cves": distinct_counts["distinct_cves"] or 0,
			"vendor_summary": list(
				active.values("product_vendor", "product_name")
				.annotate(
					critical=Count(Case(When(severity="Critical", then=1))),
					high=Count(Case(When(severity="High", then=1))),
					medium=Count(Case(When(severity="Medium", then=1))),
					low=Count(Case(When(severity="Low", then=1))),
				)
				.order_by("-critical", "-high", "-medium", "-low", "product_vendor", "product_name")
			),
			"os_device_summary": os_device_summary,
			"cve_year_chart": cve_year_chart,
		}

		# Aggregeringene over stor tabell er dyre – cache for å avlaste.
		cache.set(cache_key, data, timeout=60 * 60 * 24)

	return render(request, 'rapport_azure_vulnstats.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'integrasjonsstatus': integrasjonsstatus,
		'data': data,
	})


def azure_vulnstats_product(request, vendor, product):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("azure_vulnerabilities")

	# Device list pagination (AJAX-friendly; no new library needed)
	try:
		devices_chunk = int(request.GET.get("devices_chunk", 200))
	except ValueError:
		devices_chunk = 200
	devices_chunk = max(1, min(devices_chunk, 500))

	try:
		devices_offset = int(request.GET.get("devices_offset", 0))
	except ValueError:
		devices_offset = 0
	devices_offset = max(0, devices_offset)

	cache_version = "v8"
	cache_ts = _azure_vulnstats_cache_ts_token(integrasjonsstatus)
	cache_key = (
		f"azure_vulnstats:product:{cache_version}:{cache_ts}:"
		f"{_azure_vulnstats_cache_slug(vendor)}:{_azure_vulnstats_cache_slug(product)}"
	)
	data = cache.get(cache_key)

	if data is None:
		active = _azure_vulnstats_overview_active().filter(
			product_vendor=vendor,
			product_name=product,
		)

		severity_order = ["Critical", "High"]
		severity_colors = {
			"Critical": "rgb(220, 53, 69)",
			"High": "rgb(255, 193, 7)",
		}

		year_severity_rows = list(
			active.annotate(cve_year=Substr("cve__cve_id", 5, 4))
			.values("cve_year", "severity")
			.annotate(count=Count("id"))
			.order_by("cve_year", "severity")
		)

		years = sorted({r["cve_year"] for r in year_severity_rows if r.get("cve_year")})
		year_index = {y: i for i, y in enumerate(years)}

		counts = {sev: [0] * len(years) for sev in severity_order}
		for r in year_severity_rows:
			y = r.get("cve_year")
			if not y or y not in year_index:
				continue
			sev = r.get("severity")
			if sev not in counts:
				continue
			counts[sev][year_index[y]] = r.get("count") or 0

		severities_present = [s for s in severity_order if any(counts[s])]
		cve_year_chart = {
			"labels": years,
			"datasets": [
				{
					"label": sev,
					"data": counts[sev],
					"backgroundColor": severity_colors.get(sev, "rgb(0, 123, 255)"),
				}
				for sev in severities_present
			],
		}

		os_device_summary = list(
			active.values("device__os_platform")
			.annotate(
				device_count=Count("device", distinct=True),
				vuln_count=Count("id"),
			)
			.order_by("-vuln_count", "device__os_platform")
		)
		for row in os_device_summary:
			devices = row.get("device_count") or 0
			vulns = row.get("vuln_count") or 0
			row["avg_vulns_per_device"] = (vulns / devices) if devices else None

		data = {
			"count_active": active.count(),
			"os_device_summary": os_device_summary,
			"cve_year_chart": cve_year_chart,
			"unique_cves": list(
				active.values("cve__cve_id", "severity")
				.annotate(instance_count=Count("id"))
				.order_by("-instance_count", "cve__cve_id")
			),
		}

		cache.set(cache_key, data, timeout=60 * 60 * 24)

	# Unique device names for this product (active vulns). Not cached since it is UI-paged.
	active_devices_qs = (
		AzureDeviceVulnerability.objects.filter(
			product_vendor=vendor,
			product_name=product,
		)
		.exclude(device__hostname__isnull=True)
		.exclude(device__hostname__exact="")
		.values_list("device__hostname", flat=True)
		.distinct()
		.order_by("device__hostname")
	)
	device_hostnames = list(active_devices_qs[devices_offset : devices_offset + devices_chunk + 1])
	device_names_more_available = len(device_hostnames) > devices_chunk
	if device_names_more_available:
		device_hostnames = device_hostnames[:devices_chunk]

	devices_next_offset = devices_offset + len(device_hostnames)
	device_names = device_name_rows_for_hostnames(device_hostnames)

	# AJAX endpoint (returns next chunk as JSON; used by product template)
	if request.GET.get("devices_ajax") == "1":
		return JsonResponse({
			"device_names": device_names,
			"next_offset": devices_next_offset,
			"has_more": device_names_more_available,
		})

	return render(request, 'rapport_azure_vulnstats_product.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'integrasjonsstatus': integrasjonsstatus,
		'vendor': vendor,
		'product': product,
		'data': data,
		'device_names': device_names,
		'device_names_more_available': device_names_more_available,
		'devices_offset': devices_offset,
		'devices_chunk': devices_chunk,
		'devices_next_offset': devices_next_offset,
	})


def azure_vulnstats_os(request, os):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("azure_vulnerabilities")

	cache_version = "v6"
	cache_ts = _azure_vulnstats_cache_ts_token(integrasjonsstatus)
	cache_key = f"azure_vulnstats:os:{cache_version}:{cache_ts}:{_azure_vulnstats_cache_slug(os)}"
	data = cache.get(cache_key)

	if data is None:
		active = AzureDeviceVulnerability.objects.filter(
			device__os_platform=os,
		)

		severity_order = ["Critical", "High"]
		severity_colors = {
			"Critical": "rgb(220, 53, 69)",
			"High": "rgb(255, 193, 7)",
		}

		year_severity_rows = list(
			active.annotate(cve_year=Substr("cve__cve_id", 5, 4))
			.values("cve_year", "severity")
			.annotate(count=Count("id"))
			.order_by("cve_year", "severity")
		)

		years = sorted({r["cve_year"] for r in year_severity_rows if r.get("cve_year")})
		year_index = {y: i for i, y in enumerate(years)}

		counts = {sev: [0] * len(years) for sev in severity_order}
		for r in year_severity_rows:
			y = r.get("cve_year")
			if not y or y not in year_index:
				continue
			sev = r.get("severity")
			if sev not in counts:
				continue
			counts[sev][year_index[y]] = r.get("count") or 0

		severities_present = [s for s in severity_order if any(counts[s])]
		cve_year_chart = {
			"labels": years,
			"datasets": [
				{
					"label": sev,
					"data": counts[sev],
					"backgroundColor": severity_colors.get(sev, "rgb(0, 123, 255)"),
				}
				for sev in severities_present
			],
		}

		vendor_summary = list(
			active.values("product_vendor", "product_name")
			.annotate(
				critical=Count(Case(When(severity="Critical", then=1))),
				high=Count(Case(When(severity="High", then=1))),
				medium=Count(Case(When(severity="Medium", then=1))),
				low=Count(Case(When(severity="Low", then=1))),
			)
			.order_by("-critical", "-high", "-medium", "-low", "product_vendor", "product_name")
		)

		data = {
			"count_active": active.count(),
			"cve_year_chart": cve_year_chart,
			"vendor_summary": vendor_summary,
			"unique_cves": list(
				active.values("cve__cve_id", "severity")
				.annotate(instance_count=Count("id"))
				.order_by("-instance_count", "cve__cve_id")
			),
		}

		cache.set(cache_key, data, timeout=60 * 60 * 24)

	return render(request, 'rapport_azure_vulnstats_os.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'integrasjonsstatus': integrasjonsstatus,
		'os': os,
		'data': data,
	})


def vulnstats_servere_uten_vuln(request):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	data = {}
	data["servere_uten_vuln"] = CMDBdevice.objects.filter(device_type="SERVER").filter(qualys_vulnerabilities=None)

	return render(request, 'rapport_vulnstats_servere_uten_vuln.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'integrasjonsstatus': integrasjonsstatus,
		'data': data,
	})



def vulnstats_all(request):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	data = {}
	data["vulns"] = QualysVuln.objects.values('title', 'severity', 'ansvar_basisdrift').annotate(num_vulns=Count('title')).order_by('-num_vulns')

	return render(request, 'rapport_vulnstats_all.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'integrasjonsstatus': integrasjonsstatus,
		'data': data,
	})


def vulnstats_search(request):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	search_term = request.GET.get("query", None)
	vulns = QualysVuln.objects.filter(
				Q(source__icontains=search_term) | 
				Q(title__icontains=search_term) | 
				Q(cve_info__icontains=search_term) | 
				Q(result__icontains=search_term)
			)#.values('title', 'severity')#.annotate(count=Count('title')).order_by('-count')


	return render(request, 'rapport_vulnstats_search.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'search_term': search_term,
		'vulns': vulns,
		'integrasjonsstatus': integrasjonsstatus,
	})


def vulnstats_offerings(request):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	from collections import defaultdict
	data = {}
	queryset = QualysVuln.objects.values('server__service_offerings__navn', 'server__service_offerings__pk', 'severity').annotate(count=Count('id'))
	results = defaultdict(lambda: ([0] * 5, None))  # 5 plasser for antall sårbarheter per kritikalitet + en plass for offering ID
	for entry in queryset:
		offering = entry['server__service_offerings__navn']
		offering_pk = entry['server__service_offerings__pk']
		severity = entry['severity']
		count = entry['count']
		counts, _ = results[offering]
		counts[severity - 1] = count
		results[offering] = (counts, offering_pk)

	data["offerings"] = [{'offering': offering, 'offering_pk': offering_pk, 'counts': counts} for offering, (counts, offering_pk) in results.items()]

	return render(request, 'rapport_vulnstats_offerings.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'offering': offering,
		'integrasjonsstatus': integrasjonsstatus,
	})




def vulnstats_virksomhet(request, pk=None):
	required_permissions = ['systemoversikt.change_virksomhet', 'systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")


	pk = int(pk)
	data = None
	virksomhet = Virksomhet.objects.get(pk=pk)
	if pk:

		representerer = request.user.profile.virksomhet
		if (representerer.pk == pk) or request.user.has_perm("systemoversikt.view_qualysvuln"):
			# 1. Fast DB query for base fields
			base_values = list(
				QualysVuln.objects.filter(
					server__service_offerings__system__systemforvalter=pk
				).values(
					"id",
					"title",
					"severity",
					"server__comp_name",
					"server__service_offerings__system__systemnavn",
					#"server__service_offerings__system__systemforvalter",
				).order_by("-severity")
			)
			# 2. Load objects once (only IDs from result set)
			objs = {
				obj.id: obj
				for obj in QualysVuln.objects.filter(id__in=[v["id"] for v in base_values])
			}
			# 3. Inject class method result
			for row in base_values:
				obj = objs[row["id"]]
				row["csv_readable"] = obj.csv_readable()
			data = base_values  # your final enriched result
		else:
			messages.info(
				request,
				f"Du prøver å se sårbarheter for en virksomhet du ikke representerer."
				f"Du er logget inn som {representerer}"
			)	



		"""
		representerer = request.user.profile.virksomhet
		if ((representerer.pk == pk) or (request.user.has_perm("systemoversikt.view_qualysvuln"))):
			data = QualysVuln.objects.filter(server__service_offerings__system__systemforvalter=pk).values(
					'title', 
					'severity', 
					'server__comp_name', 
					'server__service_offerings__system__systemnavn', 
					'server__service_offerings__system__systemforvalter'
					'item.csv_readable()'
				).order_by('server__comp_name')
			for item in data:
				item["cvss"] = 
		else:
			messages.info(request, f"Du prøver å se sårbarheter for en virksomhet du ikke representerer. Du er logget inn som {representerer}")
		"""


	return render(request, 'rapport_vulnstats_virksomhet.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'integrasjonsstatus': integrasjonsstatus,
		'data': data,
		'virksomhet': virksomhet,
	})




def vulnstats_offering(request, pk=None):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if pk == "None":
		pk = None

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	data = {}
	if pk != None:
		offering = CMDBRef.objects.get(pk=pk)
	else:
		offering = None

	data["vulns"] = QualysVuln.objects.filter(server__service_offerings=offering).values('title', 'severity').annotate(num_vulns=Count('title')).order_by('-severity', '-num_vulns')

	return render(request, 'rapport_vulnstats_offering.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'integrasjonsstatus': integrasjonsstatus,
		'data': data,
		'offering': offering,
	})


def vulnstats_severity_eol(request, severity):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	data = {}

	data["top_unike_vulns"] = QualysVuln.objects.filter(server__derived_os_endoflife=True).filter(severity=severity)

	return render(request, 'rapport_vulnstats_eol.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'severity': severity,
		'integrasjonsstatus': integrasjonsstatus,
	})


def vulnstats_ukjente_servere(request):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	data = {}
	data["unique_source_no_server"] = QualysVuln.objects.filter(server=None).values('source').annotate(count=Count('source')).order_by("source")

	data["vulnerabilies_high_severity"] = QualysVuln.objects.filter(server=None, severity__in=[4,5]).order_by("-severity")

	return render(request, 'rapport_vulnstats_ukjente_servere.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'integrasjonsstatus': integrasjonsstatus,
	})


def vulnstats_severity_known_exploited_public(request, severity):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	antall = len(QualysVuln.objects.filter(known_exploited=True, public_facing=True, severity=severity))

	data = {}
	data["top_unike_vulns"] = QualysVuln.objects.filter(known_exploited=True, public_facing=True, severity=severity).values('title', 'akseptert').annotate(count=Count('title')).order_by('-count')

	return render(request, 'rapport_vulnstats_severity_known_exp_public.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'severity': severity,
		'integrasjonsstatus': integrasjonsstatus,
		'antall': antall,
	})

def vulnstats_severity_known_exploited_public_not_current(request, severity):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	for_nytt = timezone.now() - datetime.timedelta(days=30)
	antall = len(QualysVuln.objects.filter(known_exploited=True, public_facing=True, severity=severity, first_seen__lte=for_nytt))

	data = {}
	data["top_unike_vulns"] = QualysVuln.objects.filter(known_exploited=True, public_facing=True, severity=severity, first_seen__lte=for_nytt).values('title', 'akseptert').annotate(count=Count('title')).order_by('-count')

	return render(request, 'rapport_vulnstats_severity_known_exp_public.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'severity': severity,
		'integrasjonsstatus': integrasjonsstatus,
		'antall': antall,
	})


def vulnstats_severity_known_exploited(request, severity):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	antall = len(QualysVuln.objects.filter(known_exploited=True, severity=severity))

	data = {}
	data["top_unike_vulns"] = QualysVuln.objects.filter(known_exploited=True, severity=severity).values('title').annotate(count=Count('title')).order_by('-count')

	return render(request, 'rapport_vulnstats_severity_known_exp.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'severity': severity,
		'integrasjonsstatus': integrasjonsstatus,
		'antall': antall,
	})

def vulnstats_severity_known_exploited_not_current(request, severity):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")


	for_nytt = timezone.now() - datetime.timedelta(days=30)
	antall = len(QualysVuln.objects.filter(known_exploited=True, severity=severity, first_seen__lte=for_nytt))


	data = {}
	data["top_unike_vulns"] = QualysVuln.objects.filter(known_exploited=True, severity=severity, first_seen__lte=for_nytt).values('title', 'akseptert').annotate(count=Count('title')).order_by('-count')

	return render(request, 'rapport_vulnstats_severity_known_exp.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'severity': severity,
		'integrasjonsstatus': integrasjonsstatus,
		'antall': antall,
	})


def vulnstats_severity(request, severity):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")


	antall = len(QualysVuln.objects.filter(severity=severity))

	data = {}
	top_unike_vulns = QualysVuln.objects.filter(severity=severity).values('title', 'akseptert').annotate(count=Count('title')).order_by('-count')
	data["top_unike_vulns"] = top_unike_vulns

	return render(request, 'rapport_vulnstats_severity.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'severity': severity,
		'integrasjonsstatus': integrasjonsstatus,
		'antall': antall,
	})


def vulnstats_severity_not_current(request, severity):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	for_nytt = timezone.now() - datetime.timedelta(days=30)
	antall = len(QualysVuln.objects.filter(severity=severity, first_seen__lte=for_nytt))

	data = {}
	top_unike_vulns = QualysVuln.objects.filter(severity=severity, first_seen__lte=for_nytt).values('title', 'akseptert').annotate(count=Count('title')).order_by('-count')
	data["top_unike_vulns"] = top_unike_vulns

	return render(request, 'rapport_vulnstats_severity.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'severity': severity,
		'integrasjonsstatus': integrasjonsstatus,
		'antall': antall,
	})



def vulnstats_whereis(request, vuln):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	data = {}

	vulnerabilities = QualysVuln.objects.filter(title=vuln)
	data["vulnerabilities"] = vulnerabilities

	return render(request, 'rapport_vulnstats_whereis.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'integrasjonsstatus': integrasjonsstatus,
		'vuln': vuln,
	})


def tool_systemimport(request):
	required_permissions = ['systemoversikt.change_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import json
	innlogget_som = request.user.profile.virksomhet_innlogget_som

	if request.GET.get('upload') == "true":
		# Det er lastet opp nye data
		user_input_new_data = request.POST.get('user_input_new_data', '')
		try:
			user_input_json = json.loads(user_input_new_data)
			import_data_result = ""
			validated = True
		except:
			import_data_result = "Det du limte inn er ikke gyldig JSON"
			validated = False

		if validated:
			oppdatert = 0
			totalt = len(user_input_json['systemer'])
			for system_new in user_input_json['systemer']:
				if not 'id' in system_new:
					import_data_result += f"feltet id er obligatorisk.\n"
					continue
				system_new_id = system_new['id']
				try:
					system_old = System.objects.get(pk=system_new_id)
					import_data_result += f"Starter på {system_old}\n"
				except:
					import_data_result += f"Feilet å finne system med ID: {system_new_id}.\n"
					continue

				if system_old.systemforvalter == innlogget_som or system_old.systemeier == innlogget_som:

					try:
						if 'systemnavn' in system_new:
							system_old.systemnavn = system_new['systemnavn']
							import_data_result += f"- oppdaterte systemnavn\n"

						if 'alias' in system_new:
							system_old.alias = system_new['alias']
							import_data_result += f"- oppdaterte alias\n"

						if 'er_arkiv' in system_new:
							system_old.er_arkiv = system_new['er_arkiv']
							import_data_result += f"- oppdaterte er_arkiv\n"

						if 'antall_brukere' in system_new:
							system_old.antall_brukere = system_new['antall_brukere']
							import_data_result += f"- oppdaterte antall_brukere\n"

						if 'livslop_status' in system_new:
							system_old.livslop_status = system_new['livslop_status']
							import_data_result += f"- oppdaterte livslop_status\n"

						if 'url_risikovurdering' in system_new:
							system_old.url_risikovurdering = system_new['url_risikovurdering']
							import_data_result += f"- oppdaterte url_risikovurdering\n"

						if 'systembeskrivelse' in system_new:
							system_old.systembeskrivelse = system_new['systembeskrivelse']
							import_data_result += f"- oppdaterte systembeskrivelse\n"

						if 'konfidensialitetsvurdering' in system_new:
							system_old.konfidensialitetsvurdering = system_new['konfidensialitetsvurdering']
							import_data_result += f"- oppdaterte konfidensialitetsvurdering\n"

						if 'tilgjengelighetsvurdering' in system_new:
							system_old.tilgjengelighetsvurdering = system_new['tilgjengelighetsvurdering']
							import_data_result += f"- oppdaterte tilgjengelighetsvurdering\n"

						if 'driftsmodell_foreignkey' in system_new:
							system_old.driftsmodell_foreignkey.pk = system_new['driftsmodell_foreignkey']
							import_data_result += f"- oppdaterte driftsmodell_foreignkey\n"

						if 'forvaltning_epost' in system_new:
							system_old.forvaltning_epost = system_new['forvaltning_epost']
							import_data_result += f"- oppdaterte forvaltning_epost\n"

						if 'kritisk_kapabilitet' in system_new:
							system_old.kritisk_kapabilitet.clear()
							for kapabilitet in system_new['kritisk_kapabilitet']:
								system_old.kritisk_kapabilitet.add(kapabilitet)
							import_data_result += f"- oppdaterte kritisk_kapabilitet\n"

						"""
						if 'avhengigheter_referanser' in system_new:
							system_old.avhengigheter_referanser.clear()
							for avhengighet in system_new['avhengigheter_referanser']:
								system_old.avhengigheter_referanser.add(avhengighet)
							import_data_result += f"- oppdaterte avhengigheter_referanser\n"
						"""

						if 'dato_sist_ros' in system_new:
							system_old.dato_sist_ros = datetime.datetime.strptime(system_new['dato_sist_ros'], '%Y-%m-%d')
							import_data_result += f"- oppdaterte dato_sist_ros\n"

						if 'systemforvalter_kontaktpersoner_referanse' in system_new:
							system_old.systemforvalter_kontaktpersoner_referanse.clear()
							for email in system_new['systemforvalter_kontaktpersoner_referanse']:
								try:
									user = User.objects.get(email=email)
								except:
									import_data_result += f"Person med e-postadresse {email} finnes ikke.\n"
									continue

								try:
									ansvarlig = Ansvarlig.objects.get(brukernavn=user)
								except:
									ansvarlig = Ansvarlig.objects.create(brukernavn=user)
									import_data_result += f"{user} opprettet som ansvarlig.\n"

								system_old.systemforvalter_kontaktpersoner_referanse.add(ansvarlig)
							import_data_result += f"- oppdaterte systemforvalter_kontaktpersoner_referanse\n"

						system_old.save()
						import_data_result += f"Ferdig med {system_old}\n"
						oppdatert += 1

					except Exception as e:
						import_data_result += f"Feilet for {system_old} med: {e}\n"

				else:
					import_data_result += f"Du har ikke rettigheter til å endre {system_old}.\n"

			import_data_result += f"Importerte {oppdatert} av {totalt}."

	valgte_systemer_eksport = request.POST.getlist('eksport_systemer', None)
	if valgte_systemer_eksport:
		valgte_systemer_eksport = list(map(int, valgte_systemer_eksport))
		eksport_systemdata = []
		for system in valgte_systemer_eksport:
			try:
				system = System.objects.get(pk=system)
			except:
				continue

			eksport_systemdata.append({
					"id": system.pk,
					"systemnavn": system.systemnavn,
					"alias": system.alias,
					"er_arkiv": system.er_arkiv,
					"antall_brukere": system.antall_brukere,
					"livslop_status": system.livslop_status,
					"kritisk_kapabilitet": [k.pk for k in system.kritisk_kapabilitet.all()],
					"url_risikovurdering": system.url_risikovurdering,
					"dato_sist_ros": system.dato_sist_ros.strftime('%Y-%m-%d') if system.dato_sist_ros else None,
					"systembeskrivelse": system.systembeskrivelse,
					"konfidensialitetsvurdering": system.konfidensialitetsvurdering,
					"tilgjengelighetsvurdering": system.tilgjengelighetsvurdering,
					"systemforvalter_kontaktpersoner_referanse": [ansvarlig.brukernavn.email for ansvarlig in system.systemforvalter_kontaktpersoner_referanse.all()],
					"driftsmodell_foreignkey": system.driftsmodell_foreignkey.pk if system.driftsmodell_foreignkey else None,
					"forvaltning_epost": system.forvaltning_epost,
					#"avhengigheter_referanser": [referanse.pk for referanse in system.avhengigheter_referanser.all()]
				})

		oppslagstabeller = {
			"driftsmodell_foreignkey": {driftsmodell.pk: driftsmodell.__str__() for driftsmodell in Driftsmodell.objects.all()},
			"livslop_status": {livslop[0]: livslop[1] for livslop in LIVSLOEP_VALG},
			"konfidensialitetsvurdering": {valg[0]: valg[1] for valg in VURDERINGER_SIKKERHET_VALG},
			"tilgjengelighetsvurdering": {valg[0]: valg[1] for valg in VURDERINGER_SIKKERHET_VALG},
			"kritisk_kapabilitet": {kapabilitet.pk: kapabilitet.__str__() for kapabilitet in KritiskKapabilitet.objects.all()},
			#"avhengigheter_referanser": {system.pk: system.__str__() for system in System.objects.all()},
		}

		eksport_json = {
			"systemer": eksport_systemdata,
			"oppslagstabeller": oppslagstabeller,
		}


	mine_systemer = System.objects.filter(Q(systemeier=innlogget_som)|Q(systemforvalter=innlogget_som))
	for system in mine_systemer:
		if system.pk in valgte_systemer_eksport:
			system.valgt = True

	return render(request, 'tool_systemimport.html', {
		'request': request,
		'innlogget_som': innlogget_som,
		'mine_systemer': mine_systemer,
		'import_data_result': import_data_result if 'import_data_result' in locals() else None,
		'eksport_json': json.dumps(eksport_json, indent=4) if 'eksport_json' in locals() else None,
		'valgte_systemer_eksport': valgte_systemer_eksport,
		'user_input_new_data': user_input_new_data if 'user_input_new_data' in locals() else ''
	})



def tool_docx2html(request):
	required_permissions = None
	html = None
	messages = None
	if request.method == "POST":
		#print(request.POST)
		import mammoth
		from bs4 import BeautifulSoup
		try:
			docx_file = request.FILES['fileupload']
			filename = docx_file.name + ".html"
		except:
			html = "Ingen fil valgt"
			filename = "error.html"

		result = mammoth.convert_to_html(docx_file)
		html = BeautifulSoup(result.value).prettify()
		messages = result.messages

		if "download" in request.POST:
			response = HttpResponse(html, content_type='text/plain')
			response['Content-Disposition'] = 'attachment; filename={0}'.format(filename)
			return response

		# ellers så var det "preview" in request.POST. Da returnerer vi HTML direkte

	return render(request, 'tool_docx2html.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"html": html,
		"messages": messages,
	})


def tool_csv_converter(request):
	antall_vist = 5000
	if request.method == "POST":
		import csv
		from io import StringIO
		file_content = request.FILES['fileupload'].read().decode('utf-8')
		rows = list(csv.DictReader(StringIO(file_content), delimiter=","))
		header = list(rows[0].keys())

		#print(header)
		#print(len(rows))

	return render(request, 'tool_csv_converter.html', {
		'request': request,
		'rows': rows[0:antall_vist] if 'rows' in locals() else None,
		'header': header if 'header' in locals() else None,
		'antall_vist': antall_vist,
	})


def tool_compare_items(request):
	required_permissions = []

	boks_a_raw = request.POST.get('boks_a', '')
	boks_b_raw = request.POST.get('boks_b', '')

	boks_a = unique_splitted_items(boks_a_raw)
	boks_b = unique_splitted_items(boks_b_raw)

	bare_i_a = boks_a.difference(boks_b)
	bare_i_b = boks_b.difference(boks_a)
	begge_a_og_b = boks_a.intersection(boks_b)
	a_og_b = boks_a.union(boks_b)

	return render(request, 'tool_compare_items.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"boks_a_raw": boks_a_raw,
		"boks_b_raw": boks_b_raw,
		"bare_i_a": bare_i_a,
		"bare_i_b": bare_i_b,
		"begge_a_og_b": begge_a_og_b,
		"a_og_b": a_og_b,
	})



def tool_unique_items(request):
	required_permissions = []

	raw = request.POST.get('data', '').strip()  # strip removes trailing and leading space
	filtered = raw.replace('\"','').replace('\'','').replace(',',' ').replace(';',' ').replace(':',' ').replace('|',' ').lower()
	splitted = filtered.split()
	unike = sorted(set(splitted))

	return render(request, 'tool_unique_items.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"result": unike,
		"query": raw,
	})


# def tool_longest_substring
# def tool_item_count


def cmdb_adcs_index(request):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from os import path, listdir
	from os.path import isfile, join

	path = path.dirname(path.abspath(__file__)) + "/pki/"
	limit = 60
	summary = []

	selected_file_str = request.GET.get("file", None)
	if selected_file_str:
		if re.match(r"^\d{14}_Certipy.json$", selected_file_str):
			# only if valid open the file
			with open(f"{path}/{selected_file_str}") as f:
				selected_file = list(json.load(f).items())

			for k, v in selected_file[1][1].items():
				summary.append({
						"template": v["Template Name"],
						"ca": v["Certificate Authorities"],
						"key_usage": v["Extended Key Usage"],
						"validity_period": v["Validity Period"],
						"vulnerabilities": v["[!] Vulnerabilities"]
					})
		else:
			raise Http404
	else:
		selected_file = None

	# always show file list
	filelist = [f for f in listdir(path) if isfile(join(path, f))]
	filelist = sorted(filelist, reverse=True)
	if len(filelist) > limit:
		filelist = filelist[:limit]

	filelist_readable = []
	for item in filelist:
		tekst = f"{item[0:4]}-{item[4:6]}-{item[6:8]} {item[8:10]}:{item[10:12]}.{item[12:14]}"
		filelist_readable.append({
				"filename": item,
				"tekst": tekst,
			})

	return render(request, 'cmdb_adcs_index.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"filelist": filelist_readable,
		"selected_file": json.dumps(selected_file, indent=4),
		"summary": summary,
		'integrasjonsstatus': _integrasjonsstatus("ad_certificate_templates"),
	})



def cmdb_per_virksomhet(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	template_data = list()
	bs_alle = list(CMDBbs.objects.filter(operational_status=True, eksponert_for_bruker=True))
	for virksomhet in Virksomhet.objects.all():
		bs_eier = []
		for system in virksomhet.systemer_eier.all():
			offerings = system.service_offerings.all()
			for offering in offerings:
				bs_eier.append(offering)
				try:
					bs_alle.remove(offering)
				except:
					pass

		bs_forvalter = []
		for system in virksomhet.systemer_systemforvalter.all():
			offerings = system.service_offerings.all()
			for offering in offerings:
				bs_forvalter.append(offering)
				try:
					bs_alle.remove(offering)
				except:
					pass

		template_data.append({"virksomhet": virksomhet, "bs_eier": bs_eier, "bs_forvalter": bs_forvalter,})

	return render(request, 'cmdb_per_virksomhet.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'template_data': template_data,
		"resterende_bs": bs_alle,
	})



def o365_avvik(request):
	# 2026-05-27: Count unique transitive Kartoteket users (same as system detail page).
	# 2026-05-27: Include rapportgruppemedlemskaper pk – admin links per table row.
	# 2026-05-27: Pass ADgroup objects to template – detail links use pk, not search.
	#Viser alle avvik per virksomhet (cisco, bigip..)
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	innhentingsbehov = []
	for i in RapportGruppemedlemskaper.objects.all().order_by('kategori'):
		try:
			innhentingsbehov.append({
					"pk": i.pk,
					"kategori": i.kategori,
					"beskrivelse": i.beskrivelse,
					"kommentar": i.kommentar,
					"grupper": list(i.grupper.all()),
					"AND_grupper": list(i.AND_grupper.all()),
					"tidslinjedata": json.loads(i.tidslinjedata),
				})
		except:
			messages.error(request, f"Konfigurasjon for {i.beskrivelse} er enten feil eller har ikke kjørt første gang enda.")

	def rapport_hent_statistikk(i):
		antall, usernames = rapport_gruppemedlemskaper_antall_brukere(i["grupper"], i["AND_grupper"] or None)
		i["medlemmer"] = antall
		if i["AND_grupper"]:
			i["konkrete_medlemmer"] = usernames
		return i

	statistikk = []
	for i in innhentingsbehov:
		statistikk.append(rapport_hent_statistikk(i))

	alle_virskomhet = Virksomhet.objects.filter(ordinar_virksomhet=True)

	return render(request, 'rapport_sikkerhetsavvik.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'statistikk': statistikk,
		'virksomheter': alle_virskomhet,
		'integrasjonsstatus': _integrasjonsstatus("ad_graph_sikkerhetsavvik"),
	})



def azure_user_consents(request):
	#Vise liste over alle Azure enterprise applications med rettigheter de har fått tildelt
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	userconsents = AzureUserConsents.objects.all()
	integrasjonsstatus = _integrasjonsstatus("azure_enterprise_applications")

	return render(request, 'rapport_azure_user_consents.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'userconsents': userconsents,
		'integrasjonsstatus': integrasjonsstatus,
	})



def rapport_conditional_access_rules(request, pk=None):
	required_permissions = ['systemoversikt.view_entraidconditionalaccesspolicies']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	# 2026-06-23: Batch GUID/displayName lookups – show IP ranges for named locations in conditions.
	ca_regler_nyeste = EntraIDConditionalAccessPolicies.objects.latest()
	guids = set(conditional_access_guids_in_text(ca_regler_nyeste.json_policy))
	guid_lookup = conditional_access_guid_lookup_cache(guids)
	display_name_cache = azure_named_location_display_name_cache()
	ca_policy = ca_regler_nyeste.json_policy_as_json(
		guid_lookup=guid_lookup,
		display_name_cache=display_name_cache,
	)
	if pk:
		matched = [
			regel for regel in (ca_policy.get('value') or [])
			if regel.get('id') == pk
		]
		if not matched:
			raise Http404
		ca_policy = dict(ca_policy)
		ca_policy['value'] = matched
	integrasjonsstatus = _integrasjonsstatus("azure_ad_conditional_access")

	return render(request, 'rapport_conditional_access_rules.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ca_regler_nyeste': ca_regler_nyeste,
		'ca_policy': ca_policy,
		'pk': pk,
		'integrasjonsstatus': integrasjonsstatus,
	})


def rapport_conditional_access_overview(request):
	required_permissions = ['systemoversikt.view_entraidconditionalaccesspolicies']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	ca_regler_nyeste = EntraIDConditionalAccessPolicies.objects.latest()
	guids = set(conditional_access_guids_in_text(ca_regler_nyeste.json_policy))
	guid_lookup = conditional_access_guid_lookup_cache(guids)
	display_name_cache = azure_named_location_display_name_cache()
	ca_policy = ca_regler_nyeste.json_policy_as_json(
		guid_lookup=guid_lookup,
		display_name_cache=display_name_cache,
	)
	raw_policies_by_id = {
		policy['id']: policy
		for policy in json.loads(ca_regler_nyeste.json_policy).get('value') or []
		if policy.get('id')
	}
	rules_detail_url = reverse('rapport_conditional_access_rules')
	ca_tiles = conditional_access_build_overview_tiles(
		ca_policy.get('value') or [],
		guid_lookup=guid_lookup,
		raw_policies_by_id=raw_policies_by_id,
	)
	ca_filters = conditional_access_collect_overview_filters(ca_tiles)
	integrasjonsstatus = _integrasjonsstatus("azure_ad_conditional_access")

	return render(request, 'rapport_conditional_access_overview.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ca_tiles': ca_tiles,
		'ca_filters': ca_filters,
		'rules_detail_url': rules_detail_url,
		'integrasjonsstatus': integrasjonsstatus,
	})



def rapport_conditional_access_changes(request):
	required_permissions = ['systemoversikt.view_entraidconditionalaccesspolicies']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	antall_siste_endringer = 15
	ca_regler_endringer = list(
		EntraIDConditionalAccessPolicies.objects.filter(modification=True).order_by('-timestamp')[:antall_siste_endringer]
	)
	guids = set()
	for ca in ca_regler_endringer:
		guids.update(conditional_access_guids_in_text(ca.json_policy))
		guids.update(conditional_access_guids_in_text(ca.changes))
	guid_lookup = conditional_access_guid_lookup_cache(guids)
	ca_endringer = [
		{'timestamp': ca.timestamp, 'changes': ca.changes_to_json(guid_lookup=guid_lookup)}
		for ca in ca_regler_endringer
	]
	integrasjonsstatus = _integrasjonsstatus("azure_ad_conditional_access")

	return render(request, 'rapport_conditional_access_changes.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ca_endringer': ca_endringer,
		'antall_siste_endringer': antall_siste_endringer,
		'integrasjonsstatus': integrasjonsstatus,
	})


def admin_visitors(request): # brukerstatisikk
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


	from collections import Counter
	logged_in_events = ApplicationLog.objects.filter(event_type__icontains="Brukerpålogging", message__icontains="logget inn")

	# hente informasjon om antall pålogginger siste x dager
	period = 90 # days
	period_timestamp = timezone.now() - datetime.timedelta(period)
	auth_this_period = logged_in_events.filter(opprettet__gte=period_timestamp).values_list('message', flat=True).distinct().count()


	# hente informasjon om antall pålogginger fordelt per måned tilbake i tid
	from django.db.models.functions import TruncMonth
	auth_over_time = logged_in_events.annotate(year_month=TruncMonth('opprettet')).values('year_month').annotate(count=Count('message', distinct=True)).values('year_month', 'count')


	# hente data om pålogginger fordelt på virksomhet for de siste x dager
	quarterly_usernames = logged_in_events.filter(opprettet__gte=period_timestamp).values('message').distinct()
	quarterly_usernames_processed = []
	for element in quarterly_usernames:
		username = element["message"].split("logget inn.")[0]
		etat = ""
		if "@" in username: # e-mail / upn
			match = re.search(r"@([a-zA-Z0-9-]+)\.", username)
			if match:
				etat = match.group(1)
		else:
			match = re.match(r"(\D*?)\d", username)
			if match:
				etat = match.group(1)
		quarterly_usernames_processed.append(etat)

	quarterly_usernames_processed = {item: quarterly_usernames_processed.count(item) for item in set(quarterly_usernames_processed)}

	counts = Counter(quarterly_usernames_processed)
	result = [{"word": word, "count": count} for word, count in counts.items()]
	quarterly_usernames_processed = result


	# hente data om endringer fordelt på virksomhet for de siste x dager
	editing_users = LogEntry.objects.filter(action_time__gte=period_timestamp).values('user_id')
	editing_users_processed = []
	for user in editing_users:
		virksomhet = User.objects.get(id=user["user_id"]).profile.virksomhet.virksomhetsforkortelse
		editing_users_processed.append(virksomhet)

	counts = Counter(editing_users_processed)
	result = [{"word": word, "count": count} for word, count in counts.items()]
	editing_users_processed = result


	return render(request, 'admin_visitors.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'auth_this_period': auth_this_period,
		'period': period,
		'auth_over_time': auth_over_time,
		'quarterly_usernames': quarterly_usernames_processed,
		'editing_users_processed': editing_users_processed,
	})


def _azure_applications_queryset(term, search_term):
	"""Build queryset for azure_applications based on GET params."""
	if term:
		vise_managed_identity = True
		antall_dager = None
		applikasjoner = AzureApplication.objects.filter(appId=term)
	elif search_term:
		antall_dager = None
		vise_managed_identity = True
		if search_term == "__all__":
			applikasjoner = AzureApplication.objects.all().order_by('-createdDateTime')
		else:
			# 2026-06-08: Also match permission scope value/display name (e.g. User.Read → User.Read.All).
			applikasjoner = AzureApplication.objects.filter(
				Q(appId=search_term) | Q(objectId=search_term) | Q(displayName__icontains=search_term) | Q(notes__icontains=search_term)
				| Q(requiredResourceAccess__value__icontains=search_term)
				| Q(requiredResourceAccess__adminConsentDisplayName__icontains=search_term)
			).distinct().order_by('-createdDateTime')
	else:
		vise_managed_identity = False
		antall_dager = 28
		days_ago = timezone.now() - datetime.timedelta(days=antall_dager)
		applikasjoner = AzureApplication.objects.filter(
			createdDateTime__gte=days_ago
		).filter(~Q(servicePrincipalType="ManagedIdentity")).order_by('-createdDateTime')
	return applikasjoner, vise_managed_identity, antall_dager


def _azure_applications_optimize_queryset(qs):
	# 2026-06-08: Prefetch/defer for chunked async load – avoids N+1 and large json_response reads.
	return qs.prefetch_related(
		'requiredResourceAccess',
		'systemreferanse',
	).defer('json_response')


def azure_applications(request):
	#Vise liste over alle Azure enterprise applications med rettigheter de har fått tildelt
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	term = request.GET.get("term", None)
	search_term = request.GET.get("search_term", None)
	applikasjoner, vise_managed_identity, ANTALL_DAGER = _azure_applications_queryset(term, search_term)
	load_applications_async = bool(search_term)

	# 2026-06-08: Chunked AJAX for search results – prevents gunicorn worker timeout on __all__.
	if request.GET.get("applications_ajax") == "1":
		if not load_applications_async:
			return JsonResponse({"html": "", "next_offset": 0, "has_more": False})
		try:
			offset = max(0, int(request.GET.get("offset", 0)))
			chunk = min(max(1, int(request.GET.get("chunk", 200))), 500)
		except (TypeError, ValueError):
			return HttpResponseBadRequest("Invalid offset or chunk")
		qs = _azure_applications_optimize_queryset(applikasjoner)
		rows = list(qs[offset:offset + chunk + 1])
		has_more = len(rows) > chunk
		if has_more:
			rows = rows[:chunk]
		html = render_to_string('cmdb_azure_applications_rows.html', {'applikasjoner': rows})
		return JsonResponse({
			"html": html,
			"next_offset": offset + len(rows),
			"has_more": has_more,
		})

	integrasjonsstatus = _integrasjonsstatus("azure_enterprise_applications")

	if not load_applications_async:
		applikasjoner = _azure_applications_optimize_queryset(applikasjoner)

	return render(request, 'cmdb_azure_applications.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'applikasjoner': applikasjoner,
		'integrasjonsstatus': integrasjonsstatus,
		'dager_gammelt': ANTALL_DAGER,
		'vise_managed_identity': vise_managed_identity,
		'search_term': search_term,
		'load_applications_async': load_applications_async,
		'applications_chunk': 200,
	})


def rapport_sikkerhetstester(request):
	#Vise liste over alle Azure enterprise application keys etter utløpsdato
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	sikkerhetstester = Sikkerhetstester.objects.all().order_by("-dato_rapport")

	return render(request, 'rapport_sikkerhetstester.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'sikkerhetstester': sikkerhetstester,
	})


AZURE_KEYS_HIDE_LIST = [
	"CN=MS-Organization-P2P-Access",
	"CN=Microsoft Azure Federated SSO Certificate",
	"CWAP_AuthSecret",
]

AZUREAPP_KEY_EXPIRE_WARNING_EXCLUDE_PREFIXES = Q()
for prefix in AZURE_KEYS_HIDE_LIST:
	AZUREAPP_KEY_EXPIRE_WARNING_EXCLUDE_PREFIXES |= Q(display_name__startswith=prefix)


def azure_application_keys_expired(request):
	#Vise liste over alle Azure enterprise application keys etter utløpsdato
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	keys = AzureApplicationKeys.objects.filter(end_date_time__lt=timezone.now()).filter(~Q(key_type="AsymmetricX509Cert", key_usage="Verify")).exclude(AZUREAPP_KEY_EXPIRE_WARNING_EXCLUDE_PREFIXES).order_by('-end_date_time')
	#denne brukes også for utsending av e-post. Husk å bytte begge!!

	messages.info(request, 'Det sendes en e-post hver onsdag til forvaltningen i DIG med varsel om utgåtte og snart utgåtte nøkler.')

	return render(request, 'cmdb_azure_application_keys.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'keys': keys,
		'text_header': 'utgått',
		'integrasjonsstatus': _integrasjonsstatus("azure_enterprise_applications"),
	})


AZUREAPP_KEY_EXPIRE_WARNING = 14
def azure_application_keys_soon(request):
	#Vise liste over alle Azure enterprise application keys etter utløpsdato
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	warning = (timezone.now() + datetime.timedelta(AZUREAPP_KEY_EXPIRE_WARNING))
	keys = AzureApplicationKeys.objects.filter(end_date_time__gte=timezone.now()).filter(end_date_time__lte=warning).filter(~Q(key_type="AsymmetricX509Cert",key_usage="Verify")).exclude(AZUREAPP_KEY_EXPIRE_WARNING_EXCLUDE_PREFIXES).order_by('end_date_time')

	return render(request, 'cmdb_azure_application_keys.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'keys': keys,
		'text_header': 'utløper snart',
		'integrasjonsstatus': _integrasjonsstatus("azure_enterprise_applications"),
	})


def azure_application_keys_active(request):
	#Vise liste over alle Azure enterprise application keys etter utløpsdato
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	warning = (timezone.now() + datetime.timedelta(AZUREAPP_KEY_EXPIRE_WARNING))
	keys = AzureApplicationKeys.objects.filter(end_date_time__gte=warning).filter(~Q(key_type="AsymmetricX509Cert",key_usage="Verify")).exclude(AZUREAPP_KEY_EXPIRE_WARNING_EXCLUDE_PREFIXES).order_by('end_date_time')

	return render(request, 'cmdb_azure_application_keys.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'keys': keys,
		'text_header': 'aktive',
		'integrasjonsstatus': _integrasjonsstatus("azure_enterprise_applications"),
	})

def rapport_startside(request):
	required_permissions = None
	return render(request, 'rapport_startside.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})



def _systemer_forsomt_queryset(oppdatert_siden=730):
	# 2026-06-21: Forsømt = not updated in 2 years OR missing livsløp/forvalter (within exclusions).
	tidsgrense = timezone.now() - datetime.timedelta(days=oppdatert_siden)
	base = (
		System.objects.filter(~Q(driftsmodell_foreignkey__id=11))
		.filter(~Q(livslop_status__in=[1, 6, 7]))
	)
	stale = base.filter(sist_oppdatert__lte=tidsgrense)
	mangler_livslop = base.filter(Q(livslop_status=None) | Q(livslop_status=0))
	mangler_forvalter = base.filter(
		Q(systemforvalter=None) | Q(systemforvalter__ordinar_virksomhet=False)
	)
	return (stale | mangler_livslop | mangler_forvalter).distinct()


def rapport_systemer_forsomt(request):
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


	oppdatert_siden = 730 # dager (2 år)
	combined_queryset = _systemer_forsomt_queryset(oppdatert_siden)


	return render(request, 'rapport_systemer_forsomt.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'oppdatert_siden': oppdatert_siden,
		'systemer': combined_queryset,
	})


"""
def systemer_vis_alle(request):
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	systemer = System.objects.all()

	return render(request, 'systemer_vis_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'aktuelle_systemer': systemer,
	})
"""



def systemer_vis_alle_optimized(request):
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {
			'required_permissions': required_permissions,
			'groups': request.user.groups
		})

	systemer = (
		System.objects.all()
		.select_related(
			"systemforvalter",
			"driftsmodell_foreignkey__ansvarlig_virksomhet"
		)
		.prefetch_related(
			"systembruk_system",
			"basisdriftleverandor",
			"applikasjonsdriftleverandor",
			"systemleverandor",
			"service_offerings"
		)
	)

	return render(request, 'systemer_vis_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'aktuelle_systemer': systemer,
	})





def isk_ansvarlig_for_system(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	aktuelle_systemer = list()
	systemer = System.objects.all()
	for s in systemer:
		if s.er_infrastruktur():
			continue # skip

		if s.driftsmodell_foreignkey != None:
			if s.driftsmodell_foreignkey.type_plattform != 1: # 1 er private cloud
				continue # skip

			if s.driftsmodell_foreignkey.ansvarlig_virksomhet != None: # hvis noen eier denne plattformen
				if s.driftsmodell_foreignkey.ansvarlig_virksomhet.virksomhetsforkortelse == "UKE": # og dersom denne eier er UKE
					aktuelle_systemer.append(s)

	return render(request, 'rapport_systemer_per_isk.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'aktuelle_systemer': aktuelle_systemer,
	})


def rapport_kit_vurderinger_samlet(request):
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	aktuelle_systemer = System.objects.filter(ibruk=True)

	return render(request, 'rapport_kit_vurderinger_samlet.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'aktuelle_systemer': aktuelle_systemer,
	})



def rapport_entra_id_auth(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


	antall_med_lisens = len(User.objects.filter(profile__accountdisable=False).filter(~Q(profile__ny365lisens=None)))
	antall_med_mfa = len(User.objects.filter(profile__accountdisable=False).filter(
						Q(profile__auth_methods__icontains="phoneAuthenticationMethod") |
						Q(profile__auth_methods__icontains="fido2AuthenticationMethod") |
						Q(profile__auth_methods__icontains="microsoftAuthenticatorAuthenticationMethod")
					))

	data = []
	data.append({"tekst": "Aktive brukere med lisens", "antall": antall_med_lisens})
	data.append({"tekst": "Telefonoppringing", "antall": len(User.objects.filter(profile__accountdisable=False).filter(profile__auth_methods__icontains="voiceAuthenticationMethod"))})
	data.append({"tekst": "SMS", "antall": len(User.objects.filter(profile__accountdisable=False).filter(profile__auth_methods__icontains="phoneAuthenticationMethod"))})
	data.append({"tekst": "Sertifikat", "antall": len(User.objects.filter(profile__accountdisable=False).filter(profile__auth_methods__icontains="certificateBasedAuthentication"))})
	data.append({"tekst": "Temporary Access Pass", "antall": len(User.objects.filter(profile__accountdisable=False).filter(profile__auth_methods__icontains="temporaryAccessPassAuthenticationMethod"))})
	data.append({"tekst": "FIDO2", "antall": len(User.objects.filter(profile__accountdisable=False).filter(profile__auth_methods__icontains="fido2AuthenticationMethod"))})
	data.append({"tekst": "Authenticator", "antall": len(User.objects.filter(profile__accountdisable=False).filter(profile__auth_methods__icontains="microsoftAuthenticatorAuthenticationMethod"))})
	data.append({"tekst": "Oauth Software", "antall": len(User.objects.filter(profile__accountdisable=False).filter(profile__auth_methods__icontains="oathSoftwareTokenAuthenticationMethod"))})
	data.append({"tekst": "Oauth Hardware", "antall": len(User.objects.filter(profile__accountdisable=False).filter(profile__auth_methods__icontains="oathHardwareTokenAuthenticationMethod"))})
	data.append({"tekst": "SMS, FIDO2 eller Authenticator", "antall": antall_med_mfa})
	data.append({"tekst": "Uten MFA", "antall": antall_med_lisens - antall_med_mfa})


	full_table = User.objects.filter(profile__accountdisable=False).values('profile__virksomhet__virksomhetsnavn', 'profile__virksomhet__id').annotate(
		total_count_lisence=Count('id', filter=Q(
			Q(profile__ny365lisens__icontains="G1") |
			Q(profile__ny365lisens__icontains="G2") |
			Q(profile__ny365lisens__icontains="G3") |
			Q(profile__ny365lisens__icontains="G4") |
			Q(profile__ny365lisens__icontains="G5")
		)),
		total_count_no_auth=Count('id', filter=~Q(
			Q(profile__auth_methods__icontains="voiceAuthenticationMethod") |
			Q(profile__auth_methods__icontains="phoneAuthenticationMethod") |
			#Q(profile__auth_methods__icontains="certificateBasedAuthentication") | # ikke relevant
			#Q(profile__auth_methods__icontains="temporaryAccessPassAuthenticationMethod") | # ikke relevant
			Q(profile__auth_methods__icontains="fido2AuthenticationMethod") |
			Q(profile__auth_methods__icontains="microsoftAuthenticatorAuthenticationMethod") |
			Q(profile__auth_methods__icontains="oathSoftwareTokenAuthenticationMethod") |
			Q(profile__auth_methods__icontains="oathHardwareTokenAuthenticationMethod")
		) & Q(
			Q(profile__ny365lisens__icontains="G1") |
			Q(profile__ny365lisens__icontains="G2") |
			Q(profile__ny365lisens__icontains="G3") |
			Q(profile__ny365lisens__icontains="G4") |
			Q(profile__ny365lisens__icontains="G5")
		)),
		voiceAuthenticationMethod=Count('id', filter=Q(profile__auth_methods__icontains="voiceAuthenticationMethod")),
		phoneAuthenticationMethod=Count('id', filter=Q(profile__auth_methods__icontains="phoneAuthenticationMethod")),
		certificateBasedAuthentication=Count('id', filter=Q(profile__auth_methods__icontains="certificateBasedAuthentication")),
		temporaryAccessPassAuthenticationMethod=Count('id', filter=Q(profile__auth_methods__icontains="temporaryAccessPassAuthenticationMethod")),
		fido2AuthenticationMethod=Count('id', filter=Q(profile__auth_methods__icontains="fido2AuthenticationMethod")),
		microsoftAuthenticatorAuthenticationMethod=Count('id', filter=Q(profile__auth_methods__icontains="microsoftAuthenticatorAuthenticationMethod")),
		oathSoftwareTokenAuthenticationMethod=Count('id', filter=Q(profile__auth_methods__icontains="oathSoftwareTokenAuthenticationMethod")),
		oathHardwareTokenAuthenticationMethod=Count('id', filter=Q(profile__auth_methods__icontains="oathHardwareTokenAuthenticationMethod")),
	)

	update_stats = Profile.objects.filter(~Q(ny365lisens=None)).filter(accountdisable=False).annotate(day=TruncDate('auth_methods_last_update')).values('day').annotate(count=Count('user')).order_by('day')



	import json
	import re
	from collections import Counter
	from django.db.models import F

	PAREN_RE = re.compile(r"\((.*?)\)")   # extract inside parentheses

	AAGUID_LOOKUP = {
		"e77e3c64-05e3-428b-8824-0cbeb04b829d": "YubiKey Security Key NFC (Black) (USB-A, USB-C) (e77e3c64-05e3-428b-8824-0cbeb04b829d)",
		"a4e9fc6d-4cbe-4758-b8ba-37598bb5bbaa": "YubiKey Security Key NFC (Black) (USB-A, USB-C) (a4e9fc6d-4cbe-4758-b8ba-37598bb5bbaa)",
		"b7d3f68e-88a6-471e-9ecf-2df26d041ede": "YubiKey Security Key NFC (Black) (USB-A, USB-C) (b7d3f68e-88a6-471e-9ecf-2df26d041ede)",
		"90a3ccdf-635c-4729-a248-9b709135078f": "Microsoft Authenticator for iOS",
		"de1e552d-db1d-4423-a619-566b625cdc84": "Microsoft Authenticator for Android",
		"2fc0579f-8113-47ea-b116-bb5a8db9202a": "YubiKey 5/5C NFC (2fc0579f-8113-47ea-b116-bb5a8db9202a)",
		"d8522d9f-575b-4866-88a9-ba99fa02f35b": "YubiKey Bio - FIDO Edition",
		"ee882879-721c-4913-9775-3dfcce97072a": "YubiKey 5/5C/Nano CSPN",
		"fa2b99dc-9e39-4257-8f92-4a30d23c4118": "YubiKey 5 NFC (fa2b99dc-9e39-4257-8f92-4a30d23c4118)",
		"a25342c0-3cdc-4414-8e46-f4807fca511c": "YubiKey 5/5C NFC (a25342c0-3cdc-4414-8e46-f4807fca511c)",
		"149a2021-8ef6-4133-96b8-81f8d5b7f1f5": "YubiKey Security Key NFC (USB-A, USB-C) (Blue) (149a2021-8ef6-4133-96b8-81f8d5b7f1f5)",
		"73402251-f2a8-4f03-873e-3cb6db604b03": "uTrust FIDO2 Security Key",
		"42b4fb4a-2866-43b2-9bf7-6c6669c2e5d3": "Google Titan Security Key v2",
	}

	def get_top_fido2_devices():
		qs = Profile.objects.only("auth_methods").values_list("auth_methods", flat=True)
		counter = Counter()

		for raw in qs:
			try:
				items = json.loads(raw)   # list of auth method objects
			except Exception:
				continue  # skip invalid JSON

			for item in items:
				try:
					if item.get("@odata.type") == "#microsoft.graph.fido2AuthenticationMethod":
						#beskrivelse = item.get("beskrivelse", "").strip()
						aaguid = item.get("aaGuid")
						if not aaguid:
							continue

						# Look up description, fall back to AAGUID if unknown
						device = AAGUID_LOOKUP.get(aaguid, aaguid) # returnerer seg selv om ingen treff
						# Extract only the text inside parentheses
						#match = PAREN_RE.search(beskrivelse)
						#if match:
						#	device_type = match.group(1).strip()
						counter[device] += 1

				except Exception:
					pass

		return [(k, v) for k, v in counter.most_common() if v > 1]
		#return counter.most_common(n)

	top_devices = get_top_fido2_devices()
	#print(top_devices)




	return render(request, 'rapport_entra_id_auth.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'full_table': full_table,
		'update_stats': update_stats,
		'top_devices': top_devices,
		'integrasjonsstatus': _integrasjonsstatus_auth_methods(),
	})



def o365_lisenser(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	data = []
	data.append({"tekst": "Totalt med lisens", "antall": len(User.objects.filter(profile__ny365lisens__icontains="G", profile__accountdisable=False))})
	data.append({"tekst": "Brukere i gruppe 1 - Tykk klient", "antall": len(User.objects.filter(profile__ny365lisens__icontains="G1", profile__accountdisable=False))})
	data.append({"tekst": "Brukere i gruppe 2 - Flerbruker", "antall": len(User.objects.filter(profile__ny365lisens__icontains="G2", profile__accountdisable=False))})
	data.append({"tekst": "Brukere i gruppe 3 - Mangler epost", "antall": len(User.objects.filter(profile__ny365lisens__icontains="G3, profile__accountdisable=False"))})
	data.append({"tekst": "Brukere i gruppe 4 - Educaton", "antall": len(User.objects.filter(profile__ny365lisens__icontains="G4", profile__accountdisable=False))})
	data.append({"tekst": "Brukere i gruppe 5 - IDA basis (F1)", "antall": len(User.objects.filter(profile__ny365lisens__icontains="G5", profile__accountdisable=False))})


	full_table = User.objects.values('profile__virksomhet__virksomhetsnavn', 'profile__virksomhet__id').filter(profile__accountdisable=False).annotate(
		total_count=Count('id', filter=Q(
			Q(profile__ny365lisens__icontains="G1") |
			Q(profile__ny365lisens__icontains="G2") |
			Q(profile__ny365lisens__icontains="G3") |
			Q(profile__ny365lisens__icontains="G4") |
			Q(profile__ny365lisens__icontains="G5")
		)),
		G1_count=Count('id', filter=Q(profile__ny365lisens__icontains="G1")),
		G2_count=Count('id', filter=Q(profile__ny365lisens__icontains="G2")),
		G3_count=Count('id', filter=Q(profile__ny365lisens__icontains="G3")),
		G4_count=Count('id', filter=Q(profile__ny365lisens__icontains="G4")),
		G5_count=Count('id', filter=Q(profile__ny365lisens__icontains="G5"))
	)

	return render(request, 'rapport_o365_lisenser.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'full_table': full_table,
	})



def systemer_citrix(request):
	#Viser alle systemer som er knyttet til Citrix med metadata
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	systemer_på_citrix = System.objects.filter(~Q(citrix_publications=None))

	for s in systemer_på_citrix:

		citrix_apps = s.citrix_publications.filter(publikasjon_active=True)

		s.tmp_antall_publiseringer = len(citrix_apps)
		s.tmp_intern = True if any(app.sone == "Intern" for app in citrix_apps) else False
		s.tmp_sikker = True if any(app.sone == "Sikker" for app in citrix_apps) else False


		s.tmp_vApp = True if any(app.type_vApp for app in citrix_apps) else False
		s.tmp_nettleser = True if any(app.type_nettleser for app in citrix_apps) else False
		s.tmp_remotedesktop = True if any(app.type_remotedesktop for app in citrix_apps) else False

		s.tmp_nhn = True if any(app.type_nhn for app in citrix_apps) else False
		s.tmp_antall_brukere = max((app.cache_antall_publisert_til for app in citrix_apps), default=0)

		s.tmp_executable = True if any(app.type_executable for app in citrix_apps) else False
		s.tmp_vbs = True if any(app.type_vbs for app in citrix_apps) else False
		s.tmp_ps1 = True if any(app.type_ps1 for app in citrix_apps) else False
		s.tmp_bat = True if any(app.type_bat for app in citrix_apps) else False
		s.tmp_cmd = True if any(app.type_cmd for app in citrix_apps) else False

		unike_desktop_groups = []
		for app in citrix_apps:
			decoded_json = json.loads(app.publikasjon_json)
			#print(decoded_json)
			unike_desktop_groups.extend(decoded_json["AllAssociatedDesktopGroupUids_Name"])

		s.tmp_desktop_groups = set(unike_desktop_groups)


	integrasjonsstatus = _integrasjonsstatus("sp_citrix")

	return render(request, 'systemer_citrix.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer_på_citrix,
		'integrasjonsstatus': integrasjonsstatus,
	})




def system_kritisk_funksjon(request):
	#Viser alle kritiske funksjoner og hvilke systemer som understøtter dem
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	kritiske_funksjoner = KritiskFunksjon.objects.all()
	kritiske_kapabiliteter = KritiskKapabilitet.objects.all()
	systemer = System.objects.filter(~Q(kritisk_kapabilitet=None))

	return render(request, 'system_kritisk_funksjon.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'kritiske_funksjoner': kritiske_funksjoner,
		'systemer': systemer,
		'kritiske_kapabiliteter': kritiske_kapabiliteter,
	})



def system_informasjonsbehandling(request):
	#Vise alle LOS-begreper og systemer som er knyttet til
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	los_hovedtema = LOS.objects.filter(kategori_ref__verdi="Tema", active=True, parent_id=None)

	return render(request, 'system_los_oversikt.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'los_hovedtema': los_hovedtema,
	})



def system_los_struktur(request, pk=None):
	#Vise alle LOS-begreper grafisk
	required_permissions = None
	los_graf = {"nodes": [], "edges": []}

	nodes = LOS.objects.filter(active=True).filter(~Q(kategori_ref=None))

	if pk:
		nodes = nodes.filter(buffer_alle_tema=pk)
		nodes = list(nodes)
		nodes.append(LOS.objects.get(pk=pk))

	for node in nodes:

		if not pk:
			if node.kategori_ref.verdi != "Tema":
				continue

		los_graf["nodes"].append(
				{"data": {
					"id": node.pk,
					#"parent": node.hovedtema(),
					"name": node.verdi,
					"shape": "ellipse",
					"color": node.color(),
					#"size": node.size(),
					"href": reverse('system_los_struktur', args=[node.pk])
					}
				})

		for parent in node.parent_id.all():
			if parent in nodes:
				los_graf["edges"].append(
						{"data": {
							"source": node.pk,
							"target": parent.pk,
							"linestyle": "solid"
							}
						})

	return render(request, 'system_los_struktur.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'los_graf': los_graf,
		'nodes': nodes,
		'integrasjonsstatus': _integrasjonsstatus("los_begreper"),
	})

def citrix_desktop_group(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	group_name = request.GET.get("gruppe", "")
	citrix_desktop_group_members = CMDBdevice.objects.filter(citrix_desktop_group=group_name)

	return render(request, 'cmdb_citrix_desktop_group.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'citrix_desktop_group_members': citrix_desktop_group_members,
		'group_name': group_name,
		'integrasjonsstatus': _integrasjonsstatus("sp_citrix"),
	})


def citrix_mappings(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	citrix_mappings = (System.objects.filter(~Q(citrix_publications=None))
			.values('systemnavn', 'pk', 'citrix_publications__publikasjon_UUID')
			.annotate(publication_UUID=F('citrix_publications__publikasjon_UUID'))
			.values('systemnavn', 'pk', 'publication_UUID')
		)
	citrix_mappings = json.dumps(list(citrix_mappings))

	return render(request, 'cmdb_citrix_mappings.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'citrix_mappings': citrix_mappings,
		'integrasjonsstatus': _integrasjonsstatus("sp_citrix"),
	})


def _citrixpub_queryset(pk=None, order_by_bruk=False):
	# 2026-06-21: Prefetch linked systems – avoids N+1 on Citrix app list pages.
	system_qs = System.objects.select_related("systemforvalter").prefetch_related(
		"systemforvalter_kontaktpersoner_referanse__brukernavn",
		"systemforvalter__ikt_kontakt__brukernavn",
	)
	citrixapps = CitrixPublication.objects.filter(publikasjon_active=True).prefetch_related(
		Prefetch("systemer", queryset=system_qs),
	)
	if pk:
		citrixapps = citrixapps.filter(systemer=pk)
	if order_by_bruk:
		citrixapps = citrixapps.order_by("-bruk_unique_users")
	citrixapps = list(citrixapps)
	for app in citrixapps:
		app.publikasjon_json = json.loads(app.publikasjon_json)
	return citrixapps


def _citrixpub_stats(citrixapps):
	antall_apper_totalt = CitrixPublication.objects.all().count()
	antall_apper_koblet = CitrixPublication.objects.filter(publikasjon_active=True, systemer=None).count()
	try:
		antall_apper_koblet_pct = antall_apper_koblet / len(citrixapps)
	except ZeroDivisionError:
		antall_apper_koblet_pct = "?"
	return {
		"antall_apper_totalt": antall_apper_totalt,
		"antall_apper_koblet": antall_apper_koblet,
		"antall_apper_koblet_pct": (
			f"{round(antall_apper_koblet_pct * 100, 1)}%" if antall_apper_koblet_pct != "?" else None
		),
	}


def alle_citrixpub_bruk(request, pk=None):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	citrixapps = _citrixpub_queryset(pk=pk, order_by_bruk=True)

	return render(request, 'cmdb_citrix_apps_bruk.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'citrixapps': citrixapps,
		'filter': True if pk else False,
		'integrasjonsstatus': _integrasjonsstatus("sp_citrix"),
		**_citrixpub_stats(citrixapps),
	})


def alle_citrixpub(request, pk=None):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	citrixapps = _citrixpub_queryset(pk=pk)
	unike_siloer = CMDBdevice.objects.order_by().values('citrix_desktop_group').distinct()

	return render(request, 'cmdb_citrix_apps.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'citrixapps': citrixapps,
		'filter': True if pk else False,
		'unike_siloer': unike_siloer,
		'integrasjonsstatus': _integrasjonsstatus("sp_citrix"),
		**_citrixpub_stats(citrixapps),
	})

def alle_nettverksenheter(request):
	#Viser alle nettverksenheter (cisco, bigip..)
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	nettverksenehter = CMDBdevice.objects.filter(device_type="NETWORK")

	return render(request, 'cmdb_nettverksenehter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'nettverksenehter': nettverksenehter,
		'integrasjonsstatus': _integrasjonsstatus("sp_network_eq"),
	})


def rapport_cmdb_status(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjoner = IntegrasjonKonfigurasjon.objects.all()

	return render(request, 'rapport_cmdb_status.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'integrasjoner': integrasjoner,
	})


def rapport_ad_identer(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	ad_brukere_per_virksomhet = []
	for virksomhet in Virksomhet.objects.all():
		interne = Profile.objects.filter(accountdisable=False, virksomhet=virksomhet, account_type="Intern").count()
		eksterne = Profile.objects.filter(accountdisable=False, virksomhet=virksomhet, account_type="Ekstern").count()
		servicekontoer = Profile.objects.filter(accountdisable=False, virksomhet=virksomhet, account_type="Servicekonto").count()
		ressurser = Profile.objects.filter(accountdisable=False, virksomhet=virksomhet, account_type="Ressurs").count()
		kontakter = Profile.objects.filter(accountdisable=False, virksomhet=virksomhet, account_type="Kontakt").count()

		ad_brukere_per_virksomhet.append({
			'virksomhet': virksomhet,
			'interne': interne,
			'eksterne': eksterne,
			'servicekontoer': servicekontoer,
			'ressurser': ressurser,
			'kontakter': kontakter,
			})

	return render(request, 'rapport_ad_identer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ad_brukere_per_virksomhet': ad_brukere_per_virksomhet,
		'integrasjonsstatus': _integrasjonsstatus("ad_users"),
	})



def cmdb_statistikk(request):
	#Vise alle statistikk over alt i CMDB
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	count_office_ea = AzureApplication.objects.all().count()
	count_office_ea_keys = AzureApplicationKeys.objects.all().count()
	count_ad_users = User.objects.all().count()
	count_prk_users = User.objects.filter(profile__from_prk=True).count()
	count_ad_grupper = ADgroup.objects.all().count()
	count_bs = CMDBbs.objects.filter(operational_status=True).count()
	count_bss = CMDBRef.objects.filter(operational_status=1).count()
	count_klienter = CMDBdevice.objects.filter(device_type="KLIENT").all().count()
	count_server = CMDBdevice.objects.filter(device_type="SERVER").all().count()
	count_vlan = NetworkContainer.objects.all().count()
	count_vip = virtualIP.objects.all().count()
	count_vip_pool = VirtualIPPool.objects.all().count()
	count_oracle = CMDBdatabase.objects.filter(db_version__icontains="oracle", db_operational_status=True).all().count()
	count_mssql = CMDBdatabase.objects.filter(db_version__icontains="mssql", db_operational_status=True).all().count()
	count_mem = CMDBdevice.objects.filter(device_type="SERVER").aggregate(Sum('comp_ram'))["comp_ram__sum"]
	if count_mem:
		count_mem = count_mem * 1000*1000 # summen er MB --> bytes
	count_disk = CMDBdevice.objects.filter(device_type="SERVER").aggregate(Sum('comp_disk_space'))["comp_disk_space__sum"] #summen er i bytes
	count_oracle_disk = CMDBdatabase.objects.filter(db_version__icontains="oracle", db_operational_status=True).aggregate(Sum('db_u_datafilessizekb'))["db_u_datafilessizekb__sum"] # summen er i bytes
	count_mssql_disk = CMDBdatabase.objects.filter(db_version__icontains="mssql", db_operational_status=True).aggregate(Sum('db_u_datafilessizekb'))["db_u_datafilessizekb__sum"] # summen er i bytes
	count_dns_arecords = DNSrecord.objects.filter(dns_type="A record").count()
	count_dns_cnames = DNSrecord.objects.filter(dns_type="CNAME").count()
	count_cisco = CMDBdevice.objects.filter(device_type="NETWORK").filter(comp_os__icontains="cisco").count()
	count_bigip = CMDBdevice.objects.filter(device_type="NETWORK").filter(comp_os__icontains="f5").count()
	count_backup = CMDBbackup.objects.all().aggregate(Sum('backup_size_bytes'))["backup_size_bytes__sum"]
	count_service_accounts = User.objects.filter(profile__distinguishedname__icontains="OU=Servicekontoer").filter(profile__accountdisable=False).count()
	count_drift_accounts = User.objects.filter(Q(profile__distinguishedname__icontains="OU=DRIFT,OU=Eksterne brukere") | Q(profile__distinguishedname__icontains="OU=DRIFT,OU=Brukere")).filter(profile__accountdisable=False).count()
	count_ressurs_accounts = User.objects.filter(profile__distinguishedname__icontains="OU=Ressurser").filter(profile__accountdisable=False).count()
	count_inactive_accounts = User.objects.filter(profile__accountdisable=True).count()
	count_utenfor_OK_accounts = User.objects.filter(~Q(profile__distinguishedname__icontains="OU=OK")).filter(profile__accountdisable=False).count()

	return render(request, 'cmdb_statistikk.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'count_office_ea': count_office_ea,
		'count_office_ea_keys': count_office_ea_keys,
		'count_ad_users': count_ad_users,
		'count_prk_users': count_prk_users,
		'count_ad_grupper': count_ad_grupper,
		'count_bs': count_bs,
		'count_bss': count_bss,
		'count_server': count_server,
		'count_klienter': count_klienter,
		'count_vlan': count_vlan,
		'count_vip': count_vip,
		'count_vip_pool': count_vip_pool,
		'count_oracle': count_oracle,
		'count_mssql': count_mssql,
		'count_mem': count_mem,
		'count_disk': count_disk,
		'count_oracle_disk': count_oracle_disk,
		'count_mssql_disk': count_mssql_disk,
		'count_dns_arecords': count_dns_arecords,
		'count_dns_cnames': count_dns_cnames,
		'count_cisco': count_cisco,
		'count_bigip': count_bigip,
		'count_backup': count_backup,
		'count_service_accounts': count_service_accounts,
		'count_drift_accounts': count_drift_accounts,
		'count_ressurs_accounts': count_ressurs_accounts,
		'count_inactive_accounts': count_inactive_accounts,
		'count_utenfor_OK_accounts': count_utenfor_OK_accounts,
	})



def detaljer_vip(request, pk):
	#Vise detaljer for lastbalanserte URL-er med deres pool-medlemmer
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	vip = virtualIP.objects.get(pk=pk)

	return render(request, 'cmdb_alle_vip.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'alle_viper': [vip],
		'integrasjonsstatus': _integrasjonsstatus("sp_lastbalansering"),
	})



def cmdb_devicedetails(request, pk):
	#Vise detaljer for server/klient (ting med IP)
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	device = get_object_or_404(CMDBdevice, pk=pk)

	may_view_vulnerabilities = request.user.groups.filter(
		name="/DS-SYSTEMOVERSIKT_SAARBARHETSOVERSIKT_SIKKERHETSANALYTIKER"
	).exists()

	integrasjonsstatus_qualys = None
	integrasjonsstatus_azure = None
	qualys_cve_ids = []
	qualys_funn_total = 0
	azure_cve_ids = []
	azure_device_vulns_total = 0
	cve_both_sources = frozenset()
	if may_view_vulnerabilities:
		integrasjonsstatus_qualys = _integrasjonsstatus("sp_qualys")
		integrasjonsstatus_azure = _integrasjonsstatus("azure_vulnerabilities")
		qualys_funn_total = device.qualys_vulnerabilities.count()
		qualys_unique = set()
		for cve_info in device.qualys_vulnerabilities.values_list("cve_info", flat=True):
			qualys_unique.update(_cves_from_qualys_cve_info(cve_info))
		comp = (device.comp_name or "").strip()
		azure_base = AzureDeviceVulnerability.objects.filter(azure_device_q_for_comp_name(comp))
		azure_device_vulns_total = azure_base.count()
		azure_unique = {x.upper() for x in azure_base.values_list("cve__cve_id", flat=True) if x}
		cve_both_sources = frozenset(qualys_unique & azure_unique)
		qualys_cve_ids = _sort_cve_ids_newest_first(qualys_unique)
		azure_cve_ids = _sort_cve_ids_newest_first(azure_unique)

	return render(request, 'cmdb_devicedetails.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'device': device,
		'may_view_vulnerabilities': may_view_vulnerabilities,
		'integrasjonsstatus_qualys': integrasjonsstatus_qualys,
		'integrasjonsstatus_azure': integrasjonsstatus_azure,
		'qualys_cve_ids': qualys_cve_ids,
		'qualys_funn_total': qualys_funn_total,
		'azure_cve_ids': azure_cve_ids,
		'azure_device_vulns_total': azure_device_vulns_total,
		'cve_both_sources': cve_both_sources,
	})



def _dns_source_label(source):
	if not source:
		return '–'
	if source.endswith('_intern'):
		return 'Intern'
	if source.endswith('_ekstern'):
		return 'Ekstern'
	return source.rsplit('/', 1)[-1]


def _dns_normalize_alias_target(value):
	return (value or '').strip().rstrip('.')


def _dns_alias_target_variants(value):
	normalized = _dns_normalize_alias_target(value)
	if not normalized:
		return []
	variants = {value.strip(), normalized, normalized + '.'}
	return [variant for variant in variants if variant]


def _dns_filter_by_alias_target(qs, alias_target):
	variants = _dns_alias_target_variants(alias_target)
	if not variants:
		return qs
	return qs.filter(dns_target__in=variants)


DNS_EXCLUDE_MAX_TERMS = 100


def _dns_parse_exclude_terms(exclude_raw):
	"""Split exclude box input into unique IP or hostname/CNAME terms."""
	if not exclude_raw or not exclude_raw.strip():
		return []
	terms = []
	seen = set()
	for part in re.findall(r'([^,;\t\s\n\r]+)', exclude_raw.strip()):
		term = part.strip()
		if not term:
			continue
		key = term.lower().rstrip('.')
		if key in seen:
			continue
		seen.add(key)
		terms.append(term)
		if len(terms) >= DNS_EXCLUDE_MAX_TERMS:
			break
	return terms


def _dns_exclude_q_for_term(term):
	"""Build OR-filters for one excluded IP or alias/CNAME value."""
	try:
		ip = ipaddress.ip_address(term)
		return Q(ip_address=str(ip))
	except ValueError:
		pass

	normalized = _dns_normalize_alias_target(term)
	term_q = Q()
	variants = _dns_alias_target_variants(term)
	if variants:
		term_q |= Q(dns_target__in=variants)
	if normalized:
		term_q |= Q(dns_name__iexact=normalized)
		if '.' in normalized:
			name, domain = normalized.split('.', 1)
			term_q |= Q(dns_name__iexact=name, dns_domain__iexact=domain)
	return term_q


def _dns_apply_excludes(qs, exclude_terms):
	if not exclude_terms:
		return qs
	exclude_q = Q()
	for term in exclude_terms:
		term_q = _dns_exclude_q_for_term(term)
		if term_q:
			exclude_q |= term_q
	if exclude_q:
		qs = qs.exclude(exclude_q)
	return qs


def _dns_page_query_parts(search_term_raw='', alias_mot_raw='', exclude_raw=''):
	query_parts = {}
	if search_term_raw:
		query_parts['search_term'] = search_term_raw
	if alias_mot_raw:
		query_parts['alias_mot'] = alias_mot_raw
	if exclude_raw:
		query_parts['exclude'] = exclude_raw
	return query_parts


def _dns_build_filter_query(search_term_raw='', alias_mot_raw='', exclude_raw=''):
	return urlencode(_dns_page_query_parts(search_term_raw, alias_mot_raw, exclude_raw))


def _dns_search_href(search_term, current_search_term='', alias_mot_raw='', exclude_raw=''):
	"""Link that sets search_term; clicking the active term again clears the search."""
	term = (search_term or '').strip()
	current = (current_search_term or '').strip()
	if term and term == current:
		query_parts = _dns_page_query_parts(alias_mot_raw=alias_mot_raw, exclude_raw=exclude_raw)
		return '?' + urlencode(query_parts) if query_parts else '?'
	if not term:
		query_parts = _dns_page_query_parts(alias_mot_raw=alias_mot_raw, exclude_raw=exclude_raw)
		return '?' + urlencode(query_parts) if query_parts else '?'
	query_parts = _dns_page_query_parts(search_term_raw=term, alias_mot_raw=alias_mot_raw, exclude_raw=exclude_raw)
	return '?' + urlencode(query_parts)


def _dns_alias_mot_href(alias_target, current_alias_mot='', search_term_raw='', exclude_raw=''):
	"""Link that filters the table on alias mot (dns_target); click again to clear."""
	target = (alias_target or '').strip()
	current = (current_alias_mot or '').strip()
	if target and _dns_normalize_alias_target(target) == _dns_normalize_alias_target(current):
		query_parts = _dns_page_query_parts(search_term_raw=search_term_raw, exclude_raw=exclude_raw)
		return '?' + urlencode(query_parts) if query_parts else '?'
	if not target:
		query_parts = _dns_page_query_parts(search_term_raw=search_term_raw, exclude_raw=exclude_raw)
		return '?' + urlencode(query_parts) if query_parts else '?'
	query_parts = _dns_page_query_parts(
		search_term_raw=search_term_raw,
		alias_mot_raw=target,
		exclude_raw=exclude_raw,
	)
	return '?' + urlencode(query_parts)


def _dns_overview_stats(exclude_terms=None):
	base = _dns_apply_excludes(DNSrecord.objects.all(), exclude_terms or [])
	return {
		'top_ips': list(
			base.exclude(ip_address__isnull=True)
			.values('ip_address')
			.annotate(count=Count('id'))
			.order_by('-count')[:10]
		),
		'top_alias_targets': list(
			base.filter(dns_type__icontains='CNAME')
			.exclude(dns_target__isnull=True)
			.exclude(dns_target='')
			.values('dns_target')
			.annotate(count=Count('id'))
			.order_by('-count')[:20]
		),
		'top_ttls': list(
			base.exclude(ttl__isnull=True)
			.values('ttl')
			.annotate(count=Count('id'))
			.order_by('-count')[:10]
		),
		'dns_types': list(
			base.exclude(dns_type__isnull=True)
			.exclude(dns_type='')
			.values('dns_type')
			.annotate(count=Count('id'))
			.order_by('-count')
		),
		'sources': list(
			base.exclude(source__isnull=True)
			.exclude(source='')
			.values('source')
			.annotate(count=Count('id'))
			.order_by('-count')
		),
	}


def _dns_record_search_queryset(search_term):
	"""Filter DNS records by hostname, alias, type, source, domain, FQDN or IP."""
	term = (search_term or '').strip()
	if not term or term == '__ALL__':
		return DNSrecord.objects.all()

	text_filters = (
		Q(dns_name__icontains=term) |
		Q(dns_target__icontains=term) |
		Q(dns_type__icontains=term) |
		Q(source__icontains=term) |
		Q(dns_domain__icontains=term)
	)
	if term.isdigit():
		text_filters |= Q(ttl=int(term))
	qs = DNSrecord.objects.annotate(
		dns_full=Concat('dns_name', Value('.'), 'dns_domain', output_field=CharField()),
		ip_text=Cast('ip_address', CharField()),
	).filter(text_filters | Q(dns_full__icontains=term) | Q(ip_text__icontains=term))
	return qs


def alle_dns(request):
	# 2026-07-07: Search, exclude list, alias filter and pagination for large DNS tables.
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	DNS_PAGE_SIZE = 100

	search_term_raw = request.GET.get('search_term', '')
	search_term = search_term_raw.strip()
	alias_mot_raw = request.GET.get('alias_mot', '')
	alias_mot = alias_mot_raw.strip()
	exclude_raw = request.GET.get('exclude', '')
	exclude_terms = _dns_parse_exclude_terms(exclude_raw)
	has_filters = bool(search_term or alias_mot or exclude_terms)

	qs = _dns_record_search_queryset(search_term)
	if alias_mot:
		qs = _dns_filter_by_alias_target(qs, alias_mot)
	qs = _dns_apply_excludes(qs, exclude_terms)
	qs = qs.order_by('dns_name', 'dns_type', 'pk')

	paginator = Paginator(qs, DNS_PAGE_SIZE)
	page_number = request.GET.get('page', '1')
	page_obj = paginator.get_page(page_number)
	total_count = paginator.count
	filter_query = _dns_build_filter_query(search_term_raw, alias_mot_raw, exclude_raw)

	raw_stats = _dns_overview_stats(exclude_terms)
	dns_stats = {
		'top_ips': [
			{
				'ip_address': row['ip_address'],
				'count': row['count'],
				'search_href': _dns_search_href(row['ip_address'], search_term_raw, alias_mot_raw, exclude_raw),
				'active': search_term == row['ip_address'],
			}
			for row in raw_stats['top_ips']
		],
		'top_alias_targets': [
			{
				'dns_target': row['dns_target'],
				'dns_target_display': _dns_normalize_alias_target(row['dns_target']),
				'count': row['count'],
				'search_href': _dns_alias_mot_href(row['dns_target'], alias_mot_raw, search_term_raw, exclude_raw),
				'active': _dns_normalize_alias_target(alias_mot) == _dns_normalize_alias_target(row['dns_target']),
			}
			for row in raw_stats['top_alias_targets']
		],
		'top_ttls': [
			{
				'ttl': row['ttl'],
				'count': row['count'],
				'search_href': _dns_search_href(str(row['ttl']), search_term_raw, alias_mot_raw, exclude_raw),
				'active': search_term == str(row['ttl']),
			}
			for row in raw_stats['top_ttls']
		],
		'dns_types': [
			{
				'dns_type': row['dns_type'],
				'count': row['count'],
				'search_href': _dns_search_href(row['dns_type'], search_term_raw, alias_mot_raw, exclude_raw),
				'active': search_term == row['dns_type'],
			}
			for row in raw_stats['dns_types']
		],
		'sources': [
			{
				'source': row['source'],
				'label': _dns_source_label(row['source']),
				'count': row['count'],
				'search_href': _dns_search_href(row['source'], search_term_raw, alias_mot_raw, exclude_raw),
				'active': search_term == row['source'],
			}
			for row in raw_stats['sources']
		],
	}

	return render(request, 'cmdb_alle_dns.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'page_obj': page_obj,
		'dns_records': page_obj.object_list,
		'total_count': total_count,
		'dns_search_term': search_term_raw,
		'alias_mot': alias_mot_raw,
		'alias_mot_display': _dns_normalize_alias_target(alias_mot_raw),
		'exclude': exclude_raw,
		'exclude_term_count': len(exclude_terms),
		'has_filters': has_filters,
		'filter_query': filter_query,
		'dns_stats': dns_stats,
		'integrasjonsstatus': _integrasjonsstatus("sp_dns"),
	})



def dns_txt(request):
	#Vise alle DNS navn og alias
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	txt_records = DNSrecord.objects.filter(dns_type="TXT")

	return render(request, 'cmdb_dns_txt.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'txt_records': txt_records,
		'integrasjonsstatus': _integrasjonsstatus("sp_dns"),
	})



def alle_vip(request):
	#Vise alle lastbalanserte URL-er med deres pool-medlemmer
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	def vip_loopup(term):
		return virtualIP.objects.filter(
				Q(vip_name__icontains=search_term) |
				Q(pool_name__icontains=search_term) |
				Q(ip_address__icontains=search_term)
			)

	search_term_raw = request.GET.get('search_term', '')
	search_term = search_term_raw.strip()

	if search_term == "__ALL__":
		alle_viper = virtualIP.objects.all()

	elif len(search_term) > 1:
		alle_viper = vip_loopup(search_term)

	else:
		alle_viper = []

	return render(request, 'cmdb_alle_vip.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'alle_viper': alle_viper,
		'vip_search_term': search_term_raw,
		'integrasjonsstatus': _integrasjonsstatus("sp_lastbalansering"),
	})



def nettverk_detaljer(request, pk):
	#Vise brannmuråpninger koblet til et nettverk
	required_permissions = ['systemoversikt.view_brannmurregel']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	nettverk = NetworkContainer.objects.get(pk=pk)
	network_ip_addresses = nettverk.network_ip_address.all().order_by('ip_address_integer')
	firewall_openings = nettverk.firewall_rules.filter(active=True)

	return render(request, 'cmdb_nettverk_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'nettverk': nettverk,
		'network_ip_addresses': network_ip_addresses,
		'firewall_openings': firewall_openings,
		'config_maximum_mark_server': 100,
		'integrasjonsstatus': _integrasjonsstatus("sp_network_eq"),
	})



NETTVERK_EXCLUDE_MAX_TERMS = 100


def _network_try_parse_cidr(term):
	"""Return (ip_address, prefix_len) when term is IPv4/CIDR, else None."""
	term = (term or '').strip()
	if not term or '/' not in term:
		return None
	ip_part, mask_part = term.split('/', 1)
	ip_part = ip_part.strip()
	mask_part = mask_part.strip()
	if not ip_part or not mask_part:
		return None
	try:
		ip = ipaddress.ip_address(ip_part)
		if not isinstance(ip, ipaddress.IPv4Address):
			return None
	except ValueError:
		return None
	try:
		prefix = int(mask_part)
	except ValueError:
		return None
	if not (0 <= prefix <= 32):
		return None
	return str(ip), prefix


def _network_parse_exclude_terms(exclude_raw):
	"""Split exclude box input into unique network search terms."""
	if not exclude_raw or not exclude_raw.strip():
		return []
	terms = []
	seen = set()
	for part in re.findall(r'([^,;\t\s\n\r]+)', exclude_raw.strip()):
		term = part.strip()
		if not term:
			continue
		key = term.lower()
		if key in seen:
			continue
		seen.add(key)
		terms.append(term)
		if len(terms) >= NETTVERK_EXCLUDE_MAX_TERMS:
			break
	return terms


def _network_exclude_q_for_term(term):
	"""Build OR-filters for one excluded network value (IP, CIDR, lokasjon, sone, etc.)."""
	term_q = (
		Q(ip_address__icontains=term) |
		Q(comment__icontains=term) |
		Q(locationid__icontains=term) |
		Q(network_zone__icontains=term) |
		Q(orgname__icontains=term) |
		Q(vlan_name__icontains=term) |
		Q(vlanid__icontains=term) |
		Q(vrfname__icontains=term) |
		Q(location_name__icontains=term) |
		Q(netcategory__icontains=term)
	)
	parsed_cidr = _network_try_parse_cidr(term)
	if parsed_cidr:
		ip_str, prefix = parsed_cidr
		term_q |= Q(ip_address=ip_str, subnet_mask=prefix)
	try:
		search_ip = ipaddress.ip_address(parsed_cidr[0] if parsed_cidr else term)
		term_q |= Q(ip_address=str(search_ip))
	except ValueError:
		pass
	return term_q


def _network_apply_excludes(qs, exclude_terms):
	if not exclude_terms:
		return qs
	exclude_q = Q()
	for term in exclude_terms:
		term_q = _network_exclude_q_for_term(term)
		if term_q:
			exclude_q |= term_q
	if exclude_q:
		qs = qs.exclude(exclude_q)
	return qs


def _network_page_query_parts(search_term_raw='', exclude_raw=''):
	query_parts = {}
	if search_term_raw:
		query_parts['search_term'] = search_term_raw
	if exclude_raw:
		query_parts['exclude'] = exclude_raw
	return query_parts


def _network_build_filter_query(search_term_raw='', exclude_raw=''):
	return urlencode(_network_page_query_parts(search_term_raw, exclude_raw))


def _network_search_href(search_term, current_search_term='', exclude_raw=''):
	"""Link that sets search_term; clicking the active term again clears the search."""
	term = (search_term or '').strip()
	current = (current_search_term or '').strip()
	if term and term == current:
		query_parts = _network_page_query_parts(exclude_raw=exclude_raw)
		return '?' + urlencode(query_parts) if query_parts else '?'
	if not term:
		query_parts = _network_page_query_parts(exclude_raw=exclude_raw)
		return '?' + urlencode(query_parts) if query_parts else '?'
	query_parts = _network_page_query_parts(search_term_raw=term, exclude_raw=exclude_raw)
	return '?' + urlencode(query_parts)


def _network_display_cidr(ip_address, subnet_mask):
	return f'{ip_address}/{subnet_mask}'


def _network_overview_stats(exclude_terms=None):
	base = _network_apply_excludes(NetworkContainer.objects.all(), exclude_terms or [])
	return {
		'top_locationids': list(
			base.exclude(locationid__isnull=True)
			.exclude(locationid='')
			.values('locationid')
			.annotate(count=Count('id'))
			.order_by('-count')[:20]
		),
		'top_by_ip_devices': list(
			base.annotate(ip_device_count=Count('network_ip_address'))
			.values('ip_address', 'subnet_mask', 'ip_device_count')
			.order_by('-ip_device_count', 'ip_address')[:10]
		),
		'zones': list(
			base.exclude(network_zone__isnull=True)
			.exclude(network_zone='')
			.values('network_zone')
			.annotate(count=Count('id'))
			.order_by('-count')
		),
	}


def _network_search_queryset(search_term):
	"""Filter network containers by IP, CIDR, description, lokasjon, sone or org fields."""
	term = (search_term or '').strip()
	if not term or term == '__ALL__':
		return NetworkContainer.objects.all()

	parsed_cidr = _network_try_parse_cidr(term)
	term_ip = parsed_cidr[0] if parsed_cidr else term
	text_filters = (
		Q(ip_address__icontains=term_ip) |
		Q(orgname__icontains=term) |
		Q(comment__icontains=term) |
		Q(vrfname__icontains=term) |
		Q(locationid__icontains=term) |
		Q(vlan_name__icontains=term) |
		Q(location_name__icontains=term) |
		Q(netcategory__icontains=term) |
		Q(network_zone__icontains=term) |
		Q(vlanid__icontains=term)
	)
	if parsed_cidr:
		ip_str, prefix = parsed_cidr
		text_filters |= Q(ip_address=ip_str, subnet_mask=prefix)

	qs = NetworkContainer.objects.filter(text_filters)
	if qs.exists() or len(term) <= 1:
		return qs

	try:
		search_ip = ipaddress.ip_address(term_ip)
	except ValueError:
		return qs

	matching_pks = []
	for vlan in NetworkContainer.objects.all():
		try:
			vlan_network = ipaddress.ip_network(f'{vlan.ip_address}/{vlan.subnet_mask}', strict=False)
		except ValueError:
			continue
		if search_ip in vlan_network:
			matching_pks.append(vlan.pk)
	if matching_pks:
		return NetworkContainer.objects.filter(pk__in=matching_pks)
	return qs


def alle_nettverk(request):
	# 2026-07-07: Pagination, stats, exclude filter and default list (like alle_dns).
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	NETTVERK_PAGE_SIZE = 100

	search_term_raw = request.GET.get('search_term', '')
	search_term = search_term_raw.strip()
	exclude_raw = request.GET.get('exclude', '')
	exclude_terms = _network_parse_exclude_terms(exclude_raw)
	has_filters = bool(search_term and search_term != '__ALL__' or exclude_terms)

	qs = _network_search_queryset(search_term)
	qs = _network_apply_excludes(qs, exclude_terms)
	qs = qs.annotate(ip_device_count=Count('network_ip_address')).order_by('ip_address', 'subnet_mask', 'pk')

	paginator = Paginator(qs, NETTVERK_PAGE_SIZE)
	page_number = request.GET.get('page', '1')
	page_obj = paginator.get_page(page_number)
	total_count = paginator.count
	filter_query = _network_build_filter_query(search_term_raw, exclude_raw)

	raw_stats = _network_overview_stats(exclude_terms)
	network_stats = {
		'top_locationids': [
			{
				'locationid': row['locationid'],
				'count': row['count'],
				'search_href': _network_search_href(row['locationid'], search_term_raw, exclude_raw),
				'active': search_term == row['locationid'],
			}
			for row in raw_stats['top_locationids']
		],
		'top_by_ip_devices': [
			{
				'cidr': _network_display_cidr(row['ip_address'], row['subnet_mask']),
				'ip_device_count': row['ip_device_count'],
				'search_href': _network_search_href(
					_network_display_cidr(row['ip_address'], row['subnet_mask']),
					search_term_raw,
					exclude_raw,
				),
				'active': search_term == _network_display_cidr(row['ip_address'], row['subnet_mask']),
			}
			for row in raw_stats['top_by_ip_devices']
		],
		'zones': [
			{
				'network_zone': row['network_zone'],
				'count': row['count'],
				'search_href': _network_search_href(row['network_zone'], search_term_raw, exclude_raw),
				'active': search_term == row['network_zone'],
			}
			for row in raw_stats['zones']
		],
	}

	return render(request, 'cmdb_alle_nettverk.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'page_obj': page_obj,
		'alle_nettverk': page_obj.object_list,
		'total_count': total_count,
		'vlan_search_term': search_term_raw,
		'exclude': exclude_raw,
		'exclude_term_count': len(exclude_terms),
		'has_filters': has_filters,
		'filter_query': filter_query,
		'network_stats': network_stats,
		'integrasjonsstatus': _integrasjonsstatus("sp_network_eq"),
	})



def cmdb_uten_backup(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	uten_backup = CMDBdevice.objects.filter(backup=None, device_type="SERVER").order_by('service_offerings__parent_ref')

	return render(request, 'cmdb_uten_backup.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'uten_backup': uten_backup,
		'integrasjonsstatus': _integrasjonsstatus("sp_backup"),
	})



def cmdb_backup_index(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	count_backup = CMDBbackup.objects.all().aggregate(Sum('backup_size_bytes'))["backup_size_bytes__sum"]
	count_backup_ukjent = CMDBbackup.objects.filter(source_type="OTHER").aggregate(Sum('backup_size_bytes'))["backup_size_bytes__sum"]

	offering_all = CMDBRef.objects.all()

	sum_offering_all = 0
	for offering in offering_all:
		offering.size = offering.backup_size()
		sum_offering_all += offering.backup_size()

	num_offerings_show = 30
	offerings_sorted = sorted(offering_all, key=lambda item: item.size, reverse=True)[0:num_offerings_show]

	volum_servere_d30 = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D30").filter(~Q(environment__in=[2,3,4,5,6,7,8])):
		volum_servere_d30 += backup_data.backup_size_bytes

	volum_oracle_d40 = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D40").filter(~Q(environment__in=[2,3,4,5,6,7,8])):
		volum_oracle_d40 += backup_data.backup_size_bytes

	volum_file_exch_DWMY = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D30-W13-M12-Y10").filter(~Q(device_str__icontains="SQL")).filter(~Q(environment__in=[2,3,4,5,6,7,8])):
		volum_file_exch_DWMY += backup_data.backup_size_bytes

	volum_mssql_DWMY = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D30-W13-M12-Y10", device_str__icontains="SQL").filter(~Q(environment__in=[2,3,4,5,6,7,8])):
		volum_mssql_DWMY += backup_data.backup_size_bytes

	volum_ukjent = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="").filter(~Q(environment__in=[2,3,4,5,6,7,8])):
		volum_ukjent += backup_data.backup_size_bytes

	volum_d60_dmm = 0
	for backup_data in CMDBbackup.objects.filter(Q(backup_frequency="D60") | Q(backup_frequency="D30-M13-M12")).filter(~Q(environment__in=[2,3,4,5,6,7,8])):
		volum_d60_dmm += backup_data.backup_size_bytes



	volum_servere_d30_test = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D30", environment__in=[2,3,4,5,6,7,8]):
		volum_servere_d30_test += backup_data.backup_size_bytes

	volum_oracle_d40_test = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D40", environment__in=[2,3,4,5,6,7,8]):
		volum_oracle_d40_test += backup_data.backup_size_bytes

	volum_file_exch_DWMY_test = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D30-W13-M12-Y10", environment__in=[2,3,4,5,6,7,8]).filter(~Q(device_str__icontains="SQL")):
		volum_file_exch_DWMY_test += backup_data.backup_size_bytes

	volum_mssql_DWMY_test = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D30-W13-M12-Y10", device_str__icontains="SQL", environment__in=[2,3,4,5,6,7,8]):
		volum_mssql_DWMY_test += backup_data.backup_size_bytes

	volum_ukjent_test = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="", environment__in=[2,3,4,5,6,7,8]):
		volum_ukjent_test += backup_data.backup_size_bytes

	volum_d60_dmm_test = 0
	for backup_data in CMDBbackup.objects.filter(Q(backup_frequency="D60") | Q(backup_frequency="D30-M13-M12")).filter(Q(environment__in=[2,3,4,5,6,7,8])):
		volum_d60_dmm_test += backup_data.backup_size_bytes

	pct_servere_d30_prod = round(100 * volum_servere_d30 / count_backup, 2)
	pct_oracle_d40_prod = round(100 * volum_oracle_d40 / count_backup, 2)
	pct_file_exch_DWMY_prod = round(100 * volum_file_exch_DWMY / count_backup, 2)
	pct_mssql_DWMY_prod = round(100 * volum_mssql_DWMY / count_backup, 2)
	pct_ukjent_prod = round(100 * volum_ukjent / count_backup, 2)
	pct_ud60_dmm = round(100 * volum_d60_dmm / count_backup, 2)

	pct_servere_d30 = round(100 * volum_servere_d30_test / count_backup, 2)
	pct_oracle_d40 = round(100 * volum_oracle_d40_test / count_backup, 2)
	pct_file_exch_DWMY = round(100 * volum_file_exch_DWMY_test / count_backup, 2)
	pct_mssql_DWMY = round(100 * volum_mssql_DWMY_test / count_backup, 2)
	pct_ukjent = round(100 * volum_ukjent_test / count_backup, 2)
	pct_ud60_dmm_test = round(100 * volum_d60_dmm_test / count_backup, 2)

	pct_kontroll = round(pct_servere_d30_prod + pct_oracle_d40_prod + pct_file_exch_DWMY_prod + pct_mssql_DWMY_prod + pct_ukjent_prod + pct_ud60_dmm + pct_servere_d30 + pct_oracle_d40 + pct_file_exch_DWMY + pct_mssql_DWMY + pct_ukjent + pct_ud60_dmm_test, 2)

	backup_uten_kobling = CMDBbackup.objects.filter(source_type="OTHER").order_by('-backup_size_bytes')[0:num_offerings_show]
	for b in backup_uten_kobling:
		b.pct = round(100* b.backup_size_bytes / count_backup, 2)

	return render(request, 'cmdb_backup_index.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'count_backup': count_backup,
		'count_backup_ukjent': count_backup_ukjent,
		'offering_all': offerings_sorted,
		'sum_offering_all': sum_offering_all,
		'volum_servere_d30': volum_servere_d30,
		'volum_oracle_d40': volum_oracle_d40,
		'volum_file_exch_DWMY': volum_file_exch_DWMY,
		'volum_mssql_DWMY': volum_mssql_DWMY,
		'volum_ukjent': volum_ukjent,
		'volum_servere_d30_test': volum_servere_d30_test,
		'volum_oracle_d40_test': volum_oracle_d40_test,
		'volum_file_exch_DWMY_test': volum_file_exch_DWMY_test,
		'volum_mssql_DWMY_test': volum_mssql_DWMY_test,
		'volum_ukjent_test': volum_ukjent_test,
		'pct_servere_d30': pct_servere_d30,
		'pct_oracle_d40': pct_oracle_d40,
		'pct_file_exch_DWMY': pct_file_exch_DWMY,
		'pct_mssql_DWMY': pct_mssql_DWMY,
		'pct_ukjent': pct_ukjent,
		'pct_servere_d30_prod': pct_servere_d30_prod,
		'pct_oracle_d40_prod': pct_oracle_d40_prod,
		'pct_file_exch_DWMY_prod': pct_file_exch_DWMY_prod,
		'pct_mssql_DWMY_prod': pct_mssql_DWMY_prod,
		'pct_ukjent_prod': pct_ukjent_prod,
		'volum_d60_dmm': volum_d60_dmm,
		'volum_d60_dmm_test': volum_d60_dmm_test,
		'pct_ud60_dmm': pct_ud60_dmm,
		'pct_ud60_dmm_test': pct_ud60_dmm_test,
		'pct_kontroll': pct_kontroll,
		'num_offerings_show': num_offerings_show,
		'backup_uten_kobling': backup_uten_kobling,
		'integrasjonsstatus': _integrasjonsstatus("sp_backup"),
	})



def cmdb_lagring_index(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	count_san_allocated = CMDBdevice.objects.filter(device_type="SERVER").aggregate(Sum('vm_disk_allocation'))["vm_disk_allocation__sum"]
	count_san_used = CMDBdevice.objects.filter(device_type="SERVER").aggregate(Sum('vm_disk_usage'))["vm_disk_usage__sum"]
	pct_used = int(count_san_used / count_san_allocated * 100)
	count_san_missing_bs = CMDBdevice.objects.filter(device_type="SERVER").filter(service_offerings=None).aggregate(Sum('vm_disk_allocation'))["vm_disk_allocation__sum"]
	count_not_active = CMDBdevice.objects.filter(device_type="SERVER").aggregate(Sum('vm_disk_allocation'))["vm_disk_allocation__sum"]

	bs_all = CMDBbs.objects.all()

	return render(request, 'cmdb_lagring_index.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'count_san_allocated': count_san_allocated,
		'count_san_used': count_san_used,
		'pct_used': pct_used,
		'count_san_missing_bs': count_san_missing_bs,
		'count_not_active': count_not_active,
		'bs_all': bs_all,
		'integrasjonsstatus': _integrasjonsstatus("sp_server_disk"),

	})



def cmdb_minne_index(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	try:
		count_ram_allocated = CMDBdevice.objects.filter(device_type="SERVER").aggregate(Sum('comp_ram'))["comp_ram__sum"] * 1000**2 #MB->bytes
	except:
		count_ram_allocated = 0
	try:
		count_ram_missing_bs = CMDBdevice.objects.filter(device_type="SERVER").filter(sub_name=None).aggregate(Sum('comp_ram'))["comp_ram__sum"] * 1000**2 #MB->bytes
	except:
		count_ram_missing_bs = 0

	bs_all = CMDBbs.objects.all()

	return render(request, 'cmdb_minne_index.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'count_ram_allocated': count_ram_allocated,
		'count_ram_missing_bs': count_ram_missing_bs,
		'bs_all': bs_all,
		'integrasjonsstatus': _integrasjonsstatus("sp_server_disk"),

	})



def cmdb_ad_flere_brukeridenter(request):
	#Viser informasjon om personer med mer enn 1 brukerident
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import collections
	ansattnr = []
	relevante_brukere = User.objects.filter(profile__accountdisable=False).filter(Q(profile__distinguishedname__icontains="OU=Eksterne brukere,OU=OK")|Q(profile__distinguishedname__icontains="OU=Brukere,OU=OK"))#.values_list("username", flat=True)
	for anr in relevante_brukere:
		match = re.search(r'(\d{4,})', anr.username, re.I)
		if match:
			ansattnr.append(match[0])

	counter = collections.Counter(ansattnr)
	ansattnr_flere = sorted([{"anr": anr, "count": count} for anr, count in counter.items() if count>1], key=lambda x: x['count'], reverse=True)
	ant_ansattnr_flere = len(ansattnr_flere)

	relevante_brukere = Profile.objects.filter(accountdisable=False).filter(ansattnr_antall__gt=1)

	stat_brukertype = relevante_brukere.values('usertype').annotate(count=Count('usertype')).order_by('-count')

	stat_virksomhet = relevante_brukere.values('virksomhet').annotate(count=Count('virksomhet')).order_by('-count')
	for s in stat_virksomhet:
		if s["count"] > 0:
			s["virksomhet"] = Virksomhet.objects.get(pk=s["virksomhet"])

	stat_ou = relevante_brukere.values('ou').annotate(count=Count('ou')).order_by('-count')
	for s in stat_ou:
		if s["count"] > 0:
			try:
				s["ou"] = HRorg.objects.get(pk=s["ou"])
			except:
				s["ou"] = None

	return render(request, 'cmdb_ad_flere_brukeridenter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ant_ansattnr_unike': ant_ansattnr_flere,
		'ant_ansattnr_totalt': len(relevante_brukere),
		'stat_brukertype': stat_brukertype,
		'stat_virksomhet': stat_virksomhet,
		'stat_ou': stat_ou,
		'raw': ansattnr_flere,
	})


def ad_brukerlistesok(request):
	#Denne funksjonen er for å søke opp mange brukernavn og se informasjon om de det er treff på
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_raw = request.POST.get('user_search_term', '').strip()  # strip removes trailing and leading space
	search_term = search_raw
	users = []
	not_users = []

	search_term = search_term.replace('\"','').replace('\'','').replace(',',' ').replace(';',' ').replace('(',' ').replace(')',' ')
	search_term = search_term.split()

	for term in search_term:
		term_lower = term.lower()
		try:
			user = User.objects.get(Q(username=term_lower) | Q(email__contains=term_lower) | Q(profile__object_sid__iexact=term_lower))
			users.append(user)
		except:
			not_users.append(term_lower)
			continue

	return render(request, 'ad_brukerlistesok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'user_search_term': search_raw,
		'users': users,
		'not_users': not_users,
		'integrasjonsstatus': _integrasjonsstatus("ad_users"),
	})


def get_client_for_graph():
	import os
	from msgraph.core import GraphClient
	from azure.identity import ClientSecretCredential
	client_credential = ClientSecretCredential(
			tenant_id=os.environ['AZURE_TENANT_ID'],
			client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
			client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
	)
	api_version = "beta"
	client = GraphClient(credential=client_credential, api_version=api_version)
	return client


def fetch_groups_for_user_id(user_id):
	client = get_client_for_graph()
	query = f"/users/{user_id}/memberOf"
	groups = []
	response = client.get(query)
	data = response.json()
	groups.extend(data.get('value', []))
	next_link = data.get('@odata.nextLink')
	while next_link:
		response = client.get(next_link)
		data = response.json()
		groups.extend(data.get('value', []))
		next_link = data.get('@odata.nextLink')
	return groups


def get_usermetadata_from_spn_or_email(spn_or_email):
	client = get_client_for_graph()
	query = f"/users?$count=true&$filter=startsWith(userPrincipalName, '{spn_or_email}') or onPremisesExtensionAttributes/extensionAttribute2 eq '{spn_or_email.upper()}'"
	resp = client.get(query, headers={'ConsistencyLevel': 'eventual'})
	if resp.status_code == 200:
		return resp.json()
	return False


def auth_kartoteket_group_lookup(username):
	user = get_usermetadata_from_spn_or_email(username)
	if not user:
		print("Auth: fant ingen bruker")
		return False

	if not user["@odata.count"] == 1:
		print("Auth: fant flere brukere")
		return False

	# bare ét treff
	metadata = user["value"][0] # det er bare ét treff, så vi kan ta det første
	#print(metadata)
	groups = fetch_groups_for_user_id(metadata["id"])
	#print(groups)

	relevant_groups = []
	for g in groups:
		if "onPremisesSyncEnabled" in g:
			if g["onPremisesSyncEnabled"]:
				relevant_groups.append(g["mailNickname"])

	#print(relevant_groups)
	return relevant_groups



	client = get_client_for_graph()
	query = f"/users?$count=true$onPremisesExtensionAttributes/extensionAttribute2 eq '{username.upper()}'"
	resp = client.get(query, headers={'ConsistencyLevel': 'eventual'})
	if resp.status_code == 200:
		metadata = json.loads(resp.text)
		if metadata["@odata.count"] == 1:
			metadata = metadata["value"][0] # det er bare ét treff, så vi kan ta det første
			groups = fetch_groups_for_user_id(metadata["id"])
			relevant_groups = []



def entra_id_oppslag(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import re
	inndata = request.POST.get('search_term_user_entraId', '')
	#message = f"{request.user} søkte på: {inndata}."
	inndata = re.sub(r'[^A-Za-z0-9\.\@]', '', inndata) # sørge for at det kun er lovlige tegn

	if inndata != '':
		#ApplicationLog.objects.create(event_type="Azure AD brukersøk", message=message)

		client = get_client_for_graph()
		metadata = get_usermetadata_from_spn_or_email(inndata)

		if metadata:
			if metadata["@odata.count"] == 1:
				metadata = metadata["value"][0] # det er bare ét treff, så vi kan ta det første
				groups = fetch_groups_for_user_id(metadata["id"])
			else:
				messages.info(request, f'Flere treff på: "{inndata}" i Entra ID. Sørg for at søket er unikt.')
				metadata = None
				groups = None

		else: # returned False meaning not a 200 OK from server
			messages.info(request, f'Ingen treff på: "{inndata}" i Entra ID.')
			metadata = None
			groups = None

	if inndata == '':
		inndata = request.GET.get('search_term_user_entraId', '')
	metadata = metadata if 'metadata' in locals() else None
	groups = groups if 'groups' in locals() else None

	return render(request, 'brukere_brukersok_entraid.html', {
		'request': request,
		'metadata': metadata,
		'groups': groups,
		'search_term_user_entraId': inndata,
		'raw_groups': json.dumps(groups, sort_keys=True, indent=4),
		'raw_metadata': json.dumps(metadata, sort_keys=True, indent=4),
	})



def bruker_sok(request):
	#Denne funksjonen utfører søk etter brukere basert på e-post, brukernavn og displayname
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from functools import reduce
	from operator import or_, and_
	#from unidecode import unidecode
	search_term = request.GET.get('search_term_user', '').replace(","," ").strip().lower()
	# vi ønsker her å søke med AND-operatør mellom alle ord mot displayname, men OR-et med første ordet mot username.
	fields = (
		'profile__displayName__icontains',
	)
	parts = []
	terms = search_term.split(" ")
	for term in terms:
		for field in fields:
			parts.append(Q(**{field: term}))

	query_display = reduce(and_, parts)
	username_query = Q(**{'username__contains': terms[0]})
	email_query = Q(**{'email': terms[0]})
	sid_query = Q(**{'profile__object_sid__iexact': terms[0]})
	desc_quert = Q(**{'profile__description': terms[0]})
	query = reduce(or_, [query_display, username_query, email_query, sid_query, desc_quert])

	if len(search_term) > 2:
		users = User.objects.filter(query).distinct()

	else:
		users = User.objects.none()

	return render(request, 'brukere_brukersok_ad.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'search_term_user': search_term,
		'users': users,
	})



def passwdneverexpire(request, pk):
	#Denne funksjonen viser alle personer som har satt passord utløper aldri
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	users = User.objects.filter(profile__virksomhet=virksomhet.pk).filter(profile__usertype__in=["Ansatt", "Ekstern"]).filter(profile__dont_expire_password=True).order_by('profile__displayName')

	return render(request, 'virksomhet_passwordneverexpire.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'users': users,
	})



def ansatte_virksomhet(request, pk):
	#Denne funksjonen viser alle personer i en virksomhet
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from datetime import datetime
	dato = datetime.today().strftime('%Y-%m-%d')

	virksomhet = Virksomhet.objects.get(pk=pk)
	brukere = User.objects.filter(profile__virksomhet=virksomhet, profile__accountdisable=False)

	return render(request, 'virksomhet_ansatte_virksomhet.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'brukere': brukere,
		'dato': dato,
	})



def tom_epost(request, pk):
	#Denne funksjonen viser alle personer som har passordutløp kommende periode
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	count_brukere_i_virksomhet = User.objects.filter(profile__virksomhet=virksomhet, profile__accountdisable=False, profile__account_type__in=['Ekstern', 'Intern']).count()
	brukere_uten_epost = User.objects.filter(email="", profile__virksomhet=virksomhet, profile__accountdisable=False, profile__account_type__in=['Ekstern', 'Intern'])

	return render(request, 'virksomhet_tom_epost.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'count_brukere_i_virksomhet': count_brukere_i_virksomhet,
		'brukere_uten_epost': brukere_uten_epost,
	})


def cmdb_uten_epost_stat(request):
	#Denne funksjonen viser alle personer som har passordutløp kommende periode
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	stats = []
	totalt_uten_epost = 0
	totalt_antall_brukere = 0

	for virksomhet in Virksomhet.objects.all():

		if virksomhet.virksomhetsforkortelse == "DRIFT":
			continue # hopp over

		brukere_i_virksomhet = User.objects.filter(profile__virksomhet=virksomhet, profile__accountdisable=False, profile__account_type__in=['Ekstern', 'Intern']).count()
		brukere_uten_epost = User.objects.filter(email="", profile__virksomhet=virksomhet, profile__accountdisable=False, profile__account_type__in=['Ekstern', 'Intern']).count()

		totalt_uten_epost += brukere_uten_epost
		totalt_antall_brukere += brukere_i_virksomhet

		try:
			andel_brukere_i_virksomhet = round(100*brukere_uten_epost / brukere_i_virksomhet)
		except:
			andel_brukere_i_virksomhet = None

		stats.append(
				{
					"virksomhet": virksomhet,
					"brukere_i_virksomhet": brukere_i_virksomhet,
					"brukere_uten_epost": brukere_uten_epost,
					"andel_brukere_i_virksomhet": andel_brukere_i_virksomhet,
				}
			)

	return render(request, 'cmdb_uten_epost_stat.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'stats': stats,
		'totalt_uten_epost': totalt_uten_epost,
		'totalt_antall_brukere': totalt_antall_brukere,
	})


def bruker_detaljer(request, pk):
	#Denne funksjonen viser detaljer om en bruker lastet inn i kartoteket
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	user = User.objects.get(pk=pk)
	if not user.is_active:
		messages.warning(request, 'Denne brukeren er deaktivert!')


	return render(request, 'brukere_brukerprofil.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'user': user,
	})



def lokasjoner_hos_virksomhet(request, pk):
	required_permissions = ['systemoversikt.view_virksomhet']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	lokasjoner = WANLokasjon.objects.filter(virksomhet=virksomhet)
	return render(request, 'virksomhet_lokasjoner.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'lokasjoner': lokasjoner,
	})



def klienter_hos_virksomhet(request, pk):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	alle_klienter_hos_virksomhet = CMDBdevice.objects.filter(client_virksomhet=virksomhet).filter(~Q(client_last_loggedin_user=None))

	return render(request, 'virksomhet_klientoversikt.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'alle_klienter_hos_virksomhet': alle_klienter_hos_virksomhet,
	})



def virksomhet_leverandortilgang(request, pk=None):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if pk == None:
		raise Http404

	virksomhet = Virksomhet.objects.get(pk=pk)
	relevante_grupper = list()

	levprofiler = Leverandortilgang.objects.all()
	for profile in levprofiler:
		for system in profile.systemer.all():
			if system.systemforvalter == virksomhet:
				relevante_grupper.extend(profile.adgrupper.all())

	users = list()
	for gruppe in relevante_grupper:
		users.extend(json.loads(gruppe.member))

	users = list(set(users)) # sørger for unike personer
	member = human_readable_members(users)

	return render(request, 'virksomhet_leverandortilgang.html', {
		'show_access_groups': False,
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'member': member,
	})



def virksomhet_sikkerhetsavvik(request, pk=None):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if pk == None:
		try:
			pk = request.user.profile.virksomhet.pk
		except:
			pass

	virksomhet = Virksomhet.objects.get(pk=pk)
	logg = ""

	def hent_brukere(grupper, logg):
		brukerliste = set()
		for g in grupper:
			try:
				gruppe = ADgroup.objects.get(common_name=g)
				members = json.loads(gruppe.member)
				for m in members:
					username = m.split(",")[0].split("=")[1]
					if virksomhet.virksomhetsforkortelse in username:
						logg += "la til %s " % (username)
						brukerliste.add(username)
				if len(brukerliste) > 500:
					#print("For mange brukere")
					return (["Over 500 personer"], "")
			except:
				logg = "" # deaktivert # += "feilet for %s " % (g)
				#print("fant ikke gruppen %s" % g)

		brukerliste = [b.lower() for b in brukerliste]
		brukerobjekter = User.objects.filter(username__in=brukerliste)
		return (brukerobjekter, logg)

	#Grupper for å unnta fra krav om kjent enhet
	grupper_ikke_administrert = [
		"DS-OFFICE365_OPSJON_IKKEADMINISTRERT",
		"DS-OFFICE365E5S_OPSJON_IKKEADMINISTRERT",
		"DS-OFFICE365SVC_UNNTAK_KJENTENHET"
	]
	brukere_ikke_administrert, logg = hent_brukere(grupper_ikke_administrert, logg)

	#unntak MFA
	grupper_unntak_mfa = [
		"DS-OFFICE365SVC_UNNTAK_MFA",
	]
	brukere_unntak_mfa, logg = hent_brukere(grupper_unntak_mfa, logg)

	#unntak innenfor EU
	grupper_utenfor_eu = [
		"DS-OFFICE365SVC_UNNTAK_EUROPEISKIP",
		"DS-OFFICE365SPES_UNNTAK_EUROPEISKIP",
	]
	brukere_utenfor_eu, logg = hent_brukere(grupper_utenfor_eu, logg)

	grupper_hoyrisikoland = [
		"DS-OFFICE365SPES_UNNTAK_HOYRISIKO",
	]
	brukere_hoyrisikoland, logg = hent_brukere(grupper_hoyrisikoland, logg)

	#opptak
	grupper_med_opptak = [
		"DS-OFFICE365SPES_OPPTAK_OPPTAK",
	]
	brukere_med_opptak, logg = hent_brukere(grupper_med_opptak, logg)

	grupper_med_liveevent = [
		"DS-OFFICE365SPES_LIVEEVENT_LIVEEVENT",
	]
	brukere_med_liveevent, logg = hent_brukere(grupper_med_liveevent, logg)

	#spesialroller
	grupper_omraadeadm = [
		"DS-OFFICE365SPES_OMRAADEADM_OMRAADEADM",
	]
	brukere_omraadeadm, logg = hent_brukere(grupper_omraadeadm, logg)
	for user in brukere_omraadeadm:
		if user in brukere_ikke_administrert:
			user.avvik_kjent_enhet = True
		else:
			user.avvik_kjent_enhet = False

	grupper_gjestegodk = [
		"DS-OFFICE365SPES_OMRAADEADM_GJESTEGODK",
	]
	brukere_gjestegodk, logg = hent_brukere(grupper_gjestegodk, logg)

	grupper_gruppeadm = [
		"DS-OFFICE365SPES_OMRAADEADM_GRUPPEOPPRETTER",
	]
	brukere_gruppeadm, logg = hent_brukere(grupper_gruppeadm, logg)

	grupper_byod_vpn = [
		"DS-FJARB_OF20_SA_LISENS",
	]
	brukere_byod_vpn, logg = hent_brukere(grupper_byod_vpn, logg)

	grupper_filefullcontrol_applomr = [
		"DS-File-FullControl-Alle-%s-ApplOmr" % (virksomhet.virksomhetsforkortelse),
	]
	brukere_filefullcontrol_applomr, logg = hent_brukere(grupper_filefullcontrol_applomr, logg)

	grupper_filefullcontrol_fellesomr = [
		"DS-File-FullControl-Alle-%s-FellesOmr" % (virksomhet.virksomhetsforkortelse),
	]
	brukere_filefullcontrol_fellesomr, logg = hent_brukere(grupper_filefullcontrol_fellesomr, logg)

	grupper_filefullcontrol_hjemmeomr = [
		"DS-File-FullControl-Alle-%s-HomeFolders" % (virksomhet.virksomhetsforkortelse),
	]
	brukere_filefullcontrol_hjemmeomr, logg = hent_brukere(grupper_filefullcontrol_hjemmeomr, logg)

	grupper_lokalskriver_is = [
		"DS-%s_APP_KLIENT_LOCALPRINT" % (virksomhet.virksomhetsforkortelse),
	]
	brukere_lokalskriver_is, logg = hent_brukere(grupper_lokalskriver_is, logg)

	grupper_lokalskriver_ss = [
		"DS-%s_APP_KLIENT_LOCALPRINTSS" % (virksomhet.virksomhetsforkortelse),
	]
	brukere_lokalskriver_ss, logg = hent_brukere(grupper_lokalskriver_ss, logg)

	grupper_usb_tykklient = [
		"DS-%s_APP_KLIENT_USBAKSESSTYKK" % (virksomhet.virksomhetsforkortelse),
		"DS-%s_APP_KLIENT_USBACCESSTYKK" % (virksomhet.virksomhetsforkortelse),

	]
	brukere_usb_tykklient, logg = hent_brukere(grupper_usb_tykklient, logg)

	grupper_usb_tynnklient = [
		"DS-%s_APP_KLIENT_USBAKSESSTYNN" % (virksomhet.virksomhetsforkortelse),
		"DS-%s_APP_KLIENT_USBACCESSTYNN" % (virksomhet.virksomhetsforkortelse),
	]
	brukere_usb_tynnklient, logg = hent_brukere(grupper_usb_tynnklient, logg)

	grupper_lokal_administrator = [
		"DS-%s_APP_SUPPORT_LOKAL_ADMINISTRATOR" % (virksomhet.virksomhetsforkortelse),
		"DS-SIKKERHETKLIENT_LOKALADMIN_ADMINKLIENT",
	]
	brukere_lokal_administrator, logg = hent_brukere(grupper_lokal_administrator, logg)

	grupper_nettleserutvidelser = [
		"DS-SIKKERHETKLIENT_NETTLESERUTVIDELSER_INSTALLNETTLE",
	]
	brukere_nettleserutvidelser, logg = hent_brukere(grupper_nettleserutvidelser, logg)

	return render(request, 'virksomhet_sikkerhetsavvik.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'grupper_uten_administrert_klient': grupper_ikke_administrert,
		'brukere_uten_administrert_klient': brukere_ikke_administrert,
		'grupper_unntak_mfa': grupper_unntak_mfa,
		'brukere_unntak_mfa': brukere_unntak_mfa,
		'grupper_utenfor_eu': grupper_utenfor_eu,
		'brukere_utenfor_eu': brukere_utenfor_eu,
		'grupper_hoyrisikoland': grupper_hoyrisikoland,
		'brukere_hoyrisikoland': brukere_hoyrisikoland,
		'grupper_med_opptak': grupper_med_opptak,
		'brukere_med_opptak': brukere_med_opptak,
		'grupper_med_liveevent': grupper_med_liveevent,
		'brukere_med_liveevent': brukere_med_liveevent,
		'grupper_omraadeadm': grupper_omraadeadm,
		'brukere_omraadeadm': brukere_omraadeadm,
		'grupper_gjestegodk': grupper_gjestegodk,
		'brukere_gjestegodk': brukere_gjestegodk,
		'grupper_gruppeadm': grupper_gruppeadm,
		'brukere_gruppeadm': brukere_gruppeadm,
		'grupper_byod_vpn': grupper_byod_vpn,
		'brukere_byod_vpn': brukere_byod_vpn,
		'grupper_filefullcontrol_applomr': grupper_filefullcontrol_applomr,
		'brukere_filefullcontrol_applomr': brukere_filefullcontrol_applomr,
		'grupper_filefullcontrol_fellesomr': grupper_filefullcontrol_fellesomr,
		'brukere_filefullcontrol_fellesomr': brukere_filefullcontrol_fellesomr,
		'grupper_filefullcontrol_hjemmeomr': grupper_filefullcontrol_hjemmeomr,
		'brukere_filefullcontrol_hjemmeomr': brukere_filefullcontrol_hjemmeomr,
		'grupper_lokalskriver_is': grupper_lokalskriver_is,
		'brukere_lokalskriver_is': brukere_lokalskriver_is,
		'grupper_lokalskriver_ss': grupper_lokalskriver_ss,
		'brukere_lokalskriver_ss': brukere_lokalskriver_ss,
		'grupper_usb_tykklient': grupper_usb_tykklient,
		'brukere_usb_tykklient': brukere_usb_tykklient,
		'grupper_usb_tynnklient': grupper_usb_tynnklient,
		'brukere_usb_tynnklient': brukere_usb_tynnklient,
		'grupper_lokal_administrator': grupper_lokal_administrator,
		'brukere_lokal_administrator': brukere_lokal_administrator,
		'grupper_nettleserutvidelser': grupper_nettleserutvidelser,
		'brukere_nettleserutvidelser': brukere_nettleserutvidelser,
		'logging': logg,
		'integrasjonsstatus': _integrasjonsstatus("ad_sye_tilganger"),
	})



def minside(request):
	# 2026-06-21: Removed oidc-token session lookup – profile page uses request.user only.
	#Når innlogget, vise informasjon om innlogget bruker
	required_permissions = None

	if request.user.is_authenticated:
		return render(request, 'site_minside.html', {
			'request': request,
			'required_permissions': formater_permissions(required_permissions),
		})
	else:
		return redirect("/")



def ansvarlig_bytte(request):
	required_permissions = ['systemoversikt.change_ansvarlig']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	str_ansvarlig_fra = request.POST.get('ansvarlig_fra', '')
	str_ansvarlig_til = request.POST.get('ansvarlig_til', '')

	try:
		bruker_fra = User.objects.get(username=str_ansvarlig_fra)
		ansvarlig_fra = Ansvarlig.objects.get(brukernavn=bruker_fra)
	except:
		ansvarlig_fra = None

	try:
		bruker_til = User.objects.get(username=str_ansvarlig_til)
		try:
			ansvarlig_til = Ansvarlig.objects.get(brukernavn=bruker_til)
		except:
			# det kan hende personen ikke allerede er opprettet som ansvarlig, så da gjør vi det her
			ansvarlig_til = Ansvarlig.objects.create(brukernavn=bruker_til)
	except:
		ansvarlig_til = None

	if ansvarlig_fra == None or ansvarlig_til == None:
		feilmelding = "Et eller begge feltene inneholder et ugyldig brukernavn"
	else:
		feilmelding = ""

	resultat = []

	if ansvarlig_fra != None and ansvarlig_til != None and ansvarlig_fra != ansvarlig_til:

		# her lister vi først ut alle felter på Ansvarlig-klassen som er av typen mange-til-mange eller fremmednøkkel.
		m2m_relations = []
		fk_relations = []
		detaljert_logg = ""

		for f in Ansvarlig._meta.get_fields(include_hidden=False):
			if f.get_internal_type() in ["ManyToManyField"]:
				m2m_relations.append(f)
			if f.get_internal_type() in ["ForeignKey"]:
				fk_relations.append(f)

		#field
		#model
		#related_name
		#related_model

		for m2mr in m2m_relations:
			for obj in getattr(ansvarlig_fra, m2mr.name).all():
				object_field = getattr(obj, m2mr.field.name)
				object_field.remove(ansvarlig_fra)
				object_field.add(ansvarlig_til)
				melding = ("Fjernet %s og la til %s på %s %s" % (ansvarlig_fra, ansvarlig_til, obj.__class__.__name__, obj))
				detaljert_logg += ("%s %s, " % (obj.__class__.__name__, obj))
				resultat.append(melding)

		for fkr in fk_relations:
			for obj in getattr(ansvarlig_fra, fkr.name).all():
				setattr(obj, fkr.field.name, ansvarlig_til)
				obj.save()
				melding = ("Fjernet %s og la til %s på %s %s" % (ansvarlig_fra, ansvarlig_til, obj.__class__.__name__, obj))
				detaljert_logg += ("%s %s, " % (obj.__class__.__name__, obj))
				resultat.append(melding)

		logg_entry_message = "%s har overført alt ansvar fra %s til %s for %s" % (request.user, ansvarlig_fra, ansvarlig_til, detaljert_logg)

		ApplicationLog.objects.create(
				event_type='Overføring av ansvar',
				message=logg_entry_message,
			)
	else:
		resultat = None

	return render(request, "ansvarlig_bytte.html", {
		'request': request,
		'required_permissions': required_permissions,
		'str_ansvarlig_fra': str_ansvarlig_fra,
		'str_ansvarlig_til': str_ansvarlig_til,
		'ansvarlig_fra': ansvarlig_fra,
		'ansvarlig_til': ansvarlig_til,
		'resultat': resultat,
	})


"""
def user_clean_up(request):
	#Denne funksjonen er laget for å slette/anonymisere data i testmiljøet.
	required_permissions = ['auth.change_permission']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if settings.DEBUG == True:  # Testmiljø
		from django.contrib.auth.models import User
		for user in User.objects.all():
			try:
				user.delete()
			except:
				print("Kan ikke slette bruker %s. Forsøker å anonymisere" % user)

			anonymous_firstname = ("First-" + user.username[:3])
			user.first_name = anonymous_firstname
			anonymous_lastname = ("Last-" + user.username[3:])
			user.last_name = anonymous_lastname
			user.save()
	else:
		print("Du får ikke kjøre denne kommandoen i produksjon!")

	return render(request, "site_home.html", {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})
"""



def permissions(request):
	#viser informasjon om alle ansvarliges aktive rettigheter
	required_permissions = ['systemoversikt.change_ansvarlig']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	ansvarlige = Ansvarlig.objects.all()
	return render(request, 'site_permissions.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ansvarlige': ansvarlige,
	})



def roller(request):
	required_permissions = None
	from django.core import serializers
	from django.contrib.auth.models import Group
	groups = Group.objects.all()
	if request.GET.get('export') == "json":
		export = []
		for g in groups:
			unique_permissions = []
			for p in g.permissions.all():
				unique_permissions.append({"content_type__app_label": p.content_type.app_label, "codename": p.codename})
			export.append({"group": g.name, "permissions": unique_permissions})

		return JsonResponse(export, safe=False, status=200)
	else:
		header = []
		grupper_med_rettigheter = {}
		for g in groups:
			header.append(g.name.split("/DS-SYSTEMOVERSIKT_")[1].replace("_", " "))
			grupper_med_rettigheter[g.name] = [p.codename for p in g.permissions.all()]

		unique_permissions = list(set([ x for y in grupper_med_rettigheter.values() for x in y]))
		unique_permissions = sorted(unique_permissions)

		matrise = {}
		for key in unique_permissions:
			matrise[key] = [ True if key in rettigheter else False for gruppe, rettigheter in grupper_med_rettigheter.items() ]

		return render(request, 'site_roller.html', {
			'request': request,
			'required_permissions': formater_permissions(required_permissions),
			'header': header,
			'matrise': matrise,
	})



def logger(request):
	#viser alle endringer på objekter i løsningen
	required_permissions = ['admin.view_logentry']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	aktive_antall_uker = 4
	aktive_antall_personer = 10
	period = datetime.datetime.now() - datetime.timedelta(weeks=aktive_antall_uker)
	top_users = LogEntry.objects.filter(action_time__gte=period).values('user_id').annotate(count=Count('user_id')).order_by('-count')[:aktive_antall_personer]
	#print(top_users)
	for user in top_users:
		user["user"] = User.objects.get(pk=user["user_id"])

	antall_vist = 500
	recent_admin_loggs = LogEntry.objects.order_by('-action_time')[:antall_vist]

	return render(request, 'site_audit_logger.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'recent_admin_loggs': recent_admin_loggs,
		'antall_vist': antall_vist,
		#'top_endringer': top_endringer,
		'aktive_antall_uker': aktive_antall_uker,
		'aktive_antall_personer': aktive_antall_personer,
		'top_users': top_users,
		#'users': users,


	})



def logger_audit(request):
	#viser alle endringer på objekter i løsningen
	required_permissions = ['systemoversikt.view_applicationlog']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	recent_loggs = ApplicationLog.objects.filter(~Q(event_type__icontains="api")).filter(~Q(event_type__icontains="Brukerpålogging")).order_by('-opprettet')[:1500]
	return render(request, 'site_logger_audit.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'recent_loggs': recent_loggs,
	})



def databasestatistikk(request):
	#viser størrelse på alle tabeller i databasefilen

	required_permissions = ['systemoversikt.view_applicationlog']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


	from django.db import connection
	import os
	import sqlite3

	engine = connection.vendor  # returns 'sqlite', 'postgresql', 'mysql', etc.

	if engine == 'sqlite':
		messages.info(request, 'Det benyttes SQLite som databasemotor')
		# Hvis det brukes SQLite

		database_file = settings.DATABASES['default']['NAME']
		file_size = os.stat(database_file).st_size

		conn = sqlite3.connect(database_file)
		cursor = conn.cursor()

		cursor.execute("""
			SELECT name FROM sqlite_master
			WHERE type='table' AND name NOT LIKE 'sqlite_%';
		""")
		tables = cursor.fetchall()

		stats = []
		sum_size = 0

		for (table_name,) in tables:
			try:
				cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
				row_count = cursor.fetchone()[0]
				stats.append({"name": table_name, "row_count": row_count})
				sum_size += row_count
			except Exception as e:
				# Skip tables that can't be queried (e.g., views or locked tables)
				stats.append({"name": table_name, "row_count": "error"})
				continue

		conn.close()

		return render(request, 'site_databasestatistikk.html', {
			'request': request,
			'required_permissions': formater_permissions(required_permissions),
			'stats': stats,
			'file_size': file_size,  # total DB size
			'sum_size': sum_size,
		})




	elif engine == 'postgresql':
		# Hvis det brukes postgres
		messages.info(request, 'Det benyttes PostgreSQL som databasemotor')

		with connection.cursor() as cursor:
			cursor.execute("""
				SELECT SUM(pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname))) AS total_size_bytes
				FROM pg_stat_user_tables;
			""")
			result = cursor.fetchone()
			file_size = result[0] if result and result[0] is not None else 0


		with connection.cursor() as cursor:
			cursor.execute("""
				SELECT
					c.relname AS table_name,
					c.reltuples AS estimated_row_count
				FROM pg_class c
				JOIN pg_namespace n ON n.oid = c.relnamespace
				WHERE c.relkind = 'r'
				ORDER BY table_name;
			""")
			rows = cursor.fetchall()

		stats = []
		sum_size = 0
		for name, row_count in rows:
			stats.append({"name": name, "row_count": int(row_count)})
			sum_size += int(row_count)



		return render(request, 'site_databasestatistikk.html', {
			'request': request,
			'required_permissions': formater_permissions(required_permissions),
			'stats': stats,
			'file_size': file_size,
			'sum_size': sum_size,
		})



def logger_api(request):
	#viser alle endringer på objekter i løsningen
	required_permissions = ['systemoversikt.view_applicationlog']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	recent_loggs = ApplicationLog.objects.filter(event_type__icontains="api").order_by('-opprettet')[:5000]
	return render(request, 'site_logger_audit.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'recent_loggs': recent_loggs,
	})



def logger_autentisering(request):
	#viser alle endringer på objekter i løsningen
	required_permissions = ['systemoversikt.view_applicationlog']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	recent_loggs = ApplicationLog.objects.filter(event_type__icontains="Brukerpålogging").order_by('-opprettet')[:1500]
	return render(request, 'site_logger_audit.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'recent_loggs': recent_loggs,
	})



def logger_users(request):
	#viser selektive endringer på brukere/ansvarlige i løsningen
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	recent_loggs = UserChangeLog.objects.order_by('-opprettet')[:800]
	return render(request, 'site_logger_users.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'recent_loggs': recent_loggs,
	})



def alle_nyheter(request):
	required_permissions = None
	nyheter = NyeFunksjoner.objects.all().order_by('-tidspunkt')
	return render(request, 'system_nyheter_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'nyheter': nyheter,
	})



def home(request):
	#Startsiden med oversikt over systemer per kategori
	required_permissions = None
	antall_systemer = System.objects.filter(~Q(ibruk=False)).count()
	nyeste_systemer = System.objects.filter(~Q(ibruk=False)).order_by('-pk')[:10]
	antall_programvarer = Programvare.objects.count()
	nyeste_programvarer = Programvare.objects.order_by('-pk')[:10]
	kategorier = SystemKategori.objects.all()
	nyheter = NyeFunksjoner.objects.all().order_by('-tidspunkt')[:3]

	# 2026-06-21: Home page charts – all systems (incl. disabled), grouped by livsløp and systemklassifisering.
	# 2026-06-21: Short livsløp labels for chart legend; vedlikehold chart reuses forsømt-report logic.
	# 2026-06-21: Custom light palette for livsløp chart segments.
	# 2026-06-21: Clickable chart segments link to detail pages (forsømt, systemklassifisering).
	HOME_LIVSLOEP_CHART_LABELS = {
		None: 'Ikke vurdert',
		1: 'Under anskaffelse/utvikling',
		2: 'Nytt og umodent',
		3: 'Moderne og modent',
		4: 'Modent, ikke moderne',
		5: 'Bør/skal byttes ut',
		6: 'Ute av bruk',
		7: 'Fullstendig avviklet',
		8: 'Ukjent',
	}
	HOME_LIVSLOEP_CHART_COLORS = {
		None: 'rgb(103, 103, 103)',
		1: 'rgb(225, 225, 225)',
		2: 'rgb(215, 235, 175)',
		3: 'rgb(140, 210, 140)',
		4: 'rgb(165, 208, 135)',
		5: 'rgb(255, 159, 64)',
		6: 'rgb(200, 200, 200)',
		7: 'rgb(175, 175, 175)',
		8: 'rgb(200, 175, 255)',
	}
	alle_systemer = System.objects.all()
	# 2026-06-21: Klassifisering/vedlikehold charts exclude systems no longer in use (livsløp 6–7).
	systemer_for_status_charts = alle_systemer.exclude(livslop_status__in=[6, 7])
	livslop_count_by_status = {}
	for row in alle_systemer.values('livslop_status').annotate(count=Count('pk')):
		status = None if row['livslop_status'] in (None, 0) else row['livslop_status']
		livslop_count_by_status[status] = livslop_count_by_status.get(status, 0) + row['count']
	chart_livslop = {
		'labels': [HOME_LIVSLOEP_CHART_LABELS[value] for value, _label in LIVSLOEP_VALG],
		'data': [livslop_count_by_status.get(value, 0) for value, _label in LIVSLOEP_VALG],
		'colors': [HOME_LIVSLOEP_CHART_COLORS[value] for value, _label in LIVSLOEP_VALG],
	}
	klassifisering_count_by_value = {}
	for row in systemer_for_status_charts.values('systemeierskapsmodell').annotate(count=Count('pk')):
		klassifisering = row['systemeierskapsmodell'] or None
		klassifisering_count_by_value[klassifisering] = (
			klassifisering_count_by_value.get(klassifisering, 0) + row['count']
		)
	chart_systemklassifisering = {
		'labels': [label for _value, label in SYSTEMEIERSKAPSMODELL_VALG] + ['Mangler'],
		'data': (
			[klassifisering_count_by_value.get(value, 0) for value, _label in SYSTEMEIERSKAPSMODELL_VALG]
			+ [klassifisering_count_by_value.get(None, 0)]
		),
		'urls': [
			reverse('systemklassifisering_detaljer', kwargs={'kriterie': value})
			for value, _label in SYSTEMEIERSKAPSMODELL_VALG
		] + [reverse('systemklassifisering_detaljer', kwargs={'kriterie': '__NONE__'})],
	}
	antall_forsomt = _systemer_forsomt_queryset().filter(pk__in=systemer_for_status_charts).count()
	antall_vedlikehold_grunnlag = systemer_for_status_charts.count()
	chart_vedlikehold = {
		'labels': ['Forsømt', 'Vedlikeholdt'],
		'data': [antall_forsomt, antall_vedlikehold_grunnlag - antall_forsomt],
		'urls': [reverse('rapport_systemer_forsomt'), None],
		'colors': ['rgb(248, 165, 165)', 'rgb(140, 210, 140)'],
	}

	HOME_DRIFT_CHART_SEGMENTS = (
		("saas", "SaaS"),
		("samarbeidspartner", "Samarbeidspartner"),
		("drift_uke_privat", "DIG privat datasenter"),
		("drift_uke_sky", "DIG offentlig sky"),
		("drift_virksomhet_privat", "Virksomhet privat datasenter"),
		("drift_virksomhet_sky", "Virksomhet offentlig sky"),
		("ukjent", "Ukjent drift"),
	)
	drift_segment_counts = {key: 0 for key, _label in HOME_DRIFT_CHART_SEGMENTS}
	for system in systemer_for_status_charts.select_related(
		"driftsmodell_foreignkey__ansvarlig_virksomhet"
	):
		drift_segment_counts[system.drift_color_segment()] += 1
	chart_driftsplattform = {
		"labels": [label for _key, label in HOME_DRIFT_CHART_SEGMENTS],
		"data": [drift_segment_counts[key] for key, _label in HOME_DRIFT_CHART_SEGMENTS],
		"colors": [SYSTEM_COLORS[key] for key, _label in HOME_DRIFT_CHART_SEGMENTS],
	}
	antall_egenutviklet = systemer_for_status_charts.filter(er_egenutviklet=True).count()
	antall_generisk = systemer_for_status_charts.filter(er_egenutviklet=False).count()
	chart_egenutviklet = {
		"labels": ["Egenutviklet", "Generisk"],
		"data": [antall_egenutviklet, antall_generisk],
		"urls": [
			"/admin/systemoversikt/system/?er_egenutviklet__exact=1",
			"/admin/systemoversikt/system/?er_egenutviklet__exact=0",
		],
		"colors": [SYSTEM_COLORS["egenutviklet"], "rgb(201, 203, 207)"],
	}

	return render(request, 'site_home.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'kategorier': kategorier,
		'antall_systemer': antall_systemer,
		'nyeste_systemer': nyeste_systemer,
		'antall_programvarer': antall_programvarer,
		'nyeste_programvarer': nyeste_programvarer,
		'nyheter': nyheter,
		'chart_livslop': chart_livslop,
		'chart_systemklassifisering': chart_systemklassifisering,
		'chart_vedlikehold': chart_vedlikehold,
		'chart_driftsplattform': chart_driftsplattform,
		'chart_egenutviklet': chart_egenutviklet,
	})



def home_chart(request):
	#Startsiden med oversikt over systemer per kategori
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	nodes = []
	parents = []

	def systemnavn_forkortet(system):
		maximum = 20
		if len(system.systemnavn) > maximum:
			return system.systemnavn[:maximum]
		return system.systemnavn

	def system_virksomhet(system, parents):
		if system.systemforvalter:
			parents.append(system.systemforvalter.virksomhetsnavn)
			return system.systemforvalter.virksomhetsnavn

		parents.append('Ingen')
		return 'Ingen'

	antall_graph_noder = 0
	for system in System.objects.all().order_by('systemnavn'):
		if not system.er_ibruk():
			continue

		if system.er_integrasjon():
			continue

		if system.er_infrastruktur():
			continue

		antall_graph_noder += 1
		nodes.append({
			'data': {
				'id': system.pk,
				'name': systemnavn_forkortet(system),
				'parent': system_virksomhet(system, parents),
				'shape': 'rectangle',
				'color': system.color(),
				'href': f'/systemer/detaljer/{system.pk}/',
			}
		})

	for p in set(parents):
		nodes.append(
			{'data':
				{'id': p,
				#'parent': virksomhet.virksomhetsforkortelse,
				'color': 'white'
				}
			},
		)

	node_size = 350 + 8*antall_graph_noder
	if node_size > 1920:
		node_size = 1920

	virksomheter = Virksomhet.objects.filter(ordinar_virksomhet=True)

	return render(request, 'site_home_chart.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'nodes': nodes,
		'node_size': node_size,
		'system_colors': SYSTEM_COLORS,
		'virksomheter': virksomheter,
	})


def tjenestekatalogen_forvalter_api(request):
	#Dette er et API for å hente ut alle systemforvaltere.
	#Brukere: Tjenestekatalogen til UKE
	if request.method == "GET":

		key = request.headers.get("key", None)
		allowed_keys = APIKeys.objects.filter(navn="itas_tjenestekatalog").values_list("key", flat=True)
		if key in list(allowed_keys):

			owner = APIKeys.objects.get(key=key).navn
			ApplicationLog.objects.create(event_type="Forvalter-API", message="Brukt av %s" %(owner))

			forvaltere_eksport = []
			for ansvarlig in Ansvarlig.objects.all():

				forvalter_for = []
				for system in ansvarlig.system_forvalter_for.all():
					if system.ibruk:
						forvalter_for.append({
								"system_id": system.pk,
								"system_navn": system.systemnavn,
								"system_alias": system.alias,
								"system_eier_virksomhet_kort": system.systemeier.virksomhetsforkortelse if system.systemeier else None,
								"system_eier_virksomhet": system.systemeier.virksomhetsnavn if system.systemeier else None,
								"system_forvalter_virksomhet_kort": system.systemforvalter.virksomhetsforkortelse if system.systemforvalter else None,
								"system_forvalter_virksomhet": system.systemforvalter.virksomhetsnavn if system.systemforvalter else None,
							})

				eier_av = []
				for system in ansvarlig.system_eier_for.all():
					if system.ibruk:
						eier_av.append({
								"system_id": system.pk,
								"system_navn": system.systemnavn,
								"system_alias": system.alias,
								"system_eier_virksomhet_kort": system.systemeier.virksomhetsforkortelse if system.systemeier else None,
								"system_eier_virksomhet": system.systemeier.virksomhetsnavn if system.systemeier else None,
								"system_forvalter_virksomhet_kort": system.systemforvalter.virksomhetsforkortelse if system.systemforvalter else None,
								"system_forvalter_virksomhet": system.systemforvalter.virksomhetsnavn if system.systemforvalter else None,
							})

				if len(forvalter_for) < 1 and len(eier_av) < 1:  # begge er tomme
					continue  # hopp til neste person

				forvaltere_eksport.append({
					"brukernavn": ansvarlig.brukernavn.username,
					"fornavn": ansvarlig.brukernavn.first_name,
					"etternavn": ansvarlig.brukernavn.last_name,
					"epost": ansvarlig.brukernavn.email,
					#profil opprettes automatisk, så dette er trygt
					"visningsnavn": ansvarlig.brukernavn.profile.displayName,
					"prkid": ansvarlig.brukernavn.profile.ansattnr,
					"virksomhet_kort": ansvarlig.brukernavn.profile.virksomhet.virksomhetsforkortelse if ansvarlig.brukernavn.profile.virksomhet else None,
					"virksomhet": ansvarlig.brukernavn.profile.virksomhet.virksomhetsnavn if ansvarlig.brukernavn.profile.virksomhet else None,
					"orgenhet": ansvarlig.brukernavn.profile.org_unit.ou if ansvarlig.brukernavn.profile.org_unit else None,
					"forvalter_for": forvalter_for,
					"eier_av": eier_av,
					})

			data = {"message": "OK", "data": forvaltere_eksport}
			return JsonResponse(data, safe=False, status=200)

		else:
			return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)
	else:
		raise Http404



def tjenestekatalogen_systemer_api(request):
	#Dette er et API for å hente ut alle systemforvaltere.
	#Brukere: Tjenestekatalogen til UKE
	if request.method == "GET":

		key = request.headers.get("key", None)
		allowed_keys = APIKeys.objects.filter(navn="itas_tjenestekatalog").values_list("key", flat=True)
		if key in list(allowed_keys):

			owner = APIKeys.objects.get(key=key).navn
			ApplicationLog.objects.create(event_type="Forvalter-API", message="Brukt av %s" %(owner))

			systemer_eksport = []
			for system in System.objects.all():

				systemeiere = []
				for eier in system.systemeier_kontaktpersoner_referanse.all():
					systemeiere.append({
							"pk": eier.pk,
							"full_name": eier.brukernavn.profile.displayName if eier.brukernavn.profile else None,
							"email": eier.brukernavn.email,
							"virksomhet": eier.brukernavn.profile.virksomhet.virksomhetsnavn if eier.brukernavn.profile.virksomhet else None,
						})
				systemer_eksport.append({
						"pk": system.pk,
						"systemnavn": system.systemnavn,
						"ibruk": system.ibruk,
						"systembeskrivelse": system.systembeskrivelse,
						"systemeier_kontaktpersoner_referanse": systemeiere,
					})

			data = {"message": "OK", "data": systemer_eksport}
			return JsonResponse(data, safe=False, status=200)

		else:
			return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)
	else:
		raise Http404


def alle_ansvarlige(request):
	#Viser informasjon om alle ansvarlige
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	ansvarlige = Ansvarlig.objects.all().order_by('brukernavn__first_name')

	return render(request, 'ansvarlig_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ansvarlige': ansvarlige,
		'suboverskrift': "Hele kommunen",
	})



def alle_ansvarlige_eksport(request):
	#Viser informasjon om alle ansvarlige
	required_permissions = ['systemoversikt.change_ansvarlig']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	ansvarlige = Ansvarlig.objects.filter(brukernavn__is_active=True)

	return render(request, 'ansvarlig_eksport.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ansvarlige': ansvarlige,
	})



def systemkvalitet_virksomhet(request, pk):
	#Viser informasjon om datakvalitet per system
	required_permissions = ['systemoversikt.view_virksomhet']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	systemer_ansvarlig_for = System.objects.filter(Q(systemeier=pk) | Q(systemforvalter=pk)).order_by(Lower('systemnavn'))

	return render(request, 'virksomhet_hvamangler.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'systemer': systemer_ansvarlig_for,
	})



def systemer_vurderinger(request):
	#Vise alle systemvurderinger
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	systemer = System.objects.all()

	return render(request, 'systemer_vurderinger.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
	})


def systemer_EOL(request):
	#EOS-visning for felles IKT-plattform
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=163)
	driftsmodeller = Driftsmodell.objects.filter(ansvarlig_virksomhet=virksomhet)
	alle_systemer = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet).filter(livslop_status__in=[5,6])

	systemer = []
	infrastruktur = []

	for s in alle_systemer:
		if s.er_infrastruktur() == True:
			infrastruktur.append(s)
		else:
			systemer.append(s)

	return render(request, 'systemer_EOL_vurderinger_FIP.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
		'infrastruktur': infrastruktur,
	})


def tjenester_oversikt(request):
	# 2026-06-21: Tile overview – prefetch and counts for tjeneste cards without N+1 queries.
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	tjenester = (
		Tjeneste.objects
		.prefetch_related(
			'systemer',
			'systemer__systemeier',
			'systemer__systemforvalter',
		)
		.annotate(system_count=Count('systemer', distinct=True))
		.order_by('navn')
	)

	return render(request, 'tjenester_oversikt.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'tjenester': tjenester,
	})


def tjeneste_detaljer(request, pk):
	# 2026-06-21: Tjeneste detail with ecosystem chart – separate code path from systemdetaljer.
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	tjeneste = get_object_or_404(
		Tjeneste.objects.prefetch_related(
			'systemer',
			'systemer__systemeier',
			'systemer__systemforvalter',
			'systemer__systemforvalter_kontaktpersoner_referanse',
			'systemer__systemeier_kontaktpersoner_referanse',
			'systemer__kritisk_kapabilitet',
			'systemer__LOSref',
			'systemer__system_integration_source',
			'systemer__system_integration_source__destination_system',
			'systemer__system_integration_destination',
			'systemer__system_integration_destination__source_system',
		),
		pk=pk,
	)

	from systemoversikt.tjeneste_okosystem_graf import generer_tjeneste_okosystem_graf
	okosystem_graf = generer_tjeneste_okosystem_graf(tjeneste)

	integrasjoner = []
	seen_integration_ids = set()
	for system in tjeneste.systemer.all():
		for integrasjon in system.system_integration_source.all():
			if integrasjon.pk not in seen_integration_ids:
				seen_integration_ids.add(integrasjon.pk)
				integrasjoner.append(integrasjon)
		for integrasjon in system.system_integration_destination.all():
			if integrasjon.pk not in seen_integration_ids:
				seen_integration_ids.add(integrasjon.pk)
				integrasjoner.append(integrasjon)
	integrasjoner.sort(key=lambda i: (i.source_system.systemnavn.lower(), i.destination_system.systemnavn.lower()))

	return render(request, 'tjeneste_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'tjeneste': tjeneste,
		'okosystem_graf': okosystem_graf,
		'integrasjoner': integrasjoner,
		'system_colors': SYSTEM_COLORS,
		'okosystem_chart_size': 320 + len(okosystem_graf["nodes"]) * 22,
	})


def generer_graf_ny(system, follow_count):
	# 2026-06-21: Integration edges carry admin edit href – clickable in dependency chart.
	avhengigheter_graf = {"nodes": [], "edges": []}
	observerte_driftsmodeller = set()
	first_round = True
	observerte_systemer = set()
	behandlede_systemer = set()
	aktivt_nivaa_systemer = set()
	neste_nivaa = set()

	def parent(system):
		if system.driftsmodell_foreignkey is not None:
			return f"drift_{system.driftsmodell_foreignkey.pk}"
		return "Ukjent"

	aktivt_nivaa_systemer.add(system)
	observerte_systemer.add(system)

	def avhengighetsrunde(aktivt_nivaa_systemer, neste_nivaa):
		for aktuelt_system in aktivt_nivaa_systemer:
			avhengigheter_graf["nodes"].append({"data": {
				"id": aktuelt_system.pk,
				"parent": parent(aktuelt_system),
				"name": aktuelt_system.systemnavn,
				"shape": "ellipse",
				"color": SYSTEM_COLORS["chart_current_system"]
			}})
			observerte_driftsmodeller.add(aktuelt_system.driftsmodell_foreignkey)

			for s in aktuelt_system.system_integration_source.all():
				integrasjon = s
				s = s.destination_system
				if s not in observerte_systemer:
					neste_nivaa.add(s)
					observerte_systemer.add(s)
				if s not in behandlede_systemer:
					avhengigheter_graf["nodes"].append({"data": {
						"id": s.pk,
						"parent": parent(s),
						"name": s.systemnavn,
						"shape": "ellipse",
						"color": integrasjon.color(),
						"href": reverse('systemdetaljer', args=[s.pk])
					}})
					observerte_driftsmodeller.add(s.driftsmodell_foreignkey)
				avhengigheter_graf["edges"].append({"data": {
					"id": f"integration_{integrasjon.pk}",
					"source": aktuelt_system.pk,
					"target": s.pk,
					'linewidth': 2,
					'curve-style': 'bezier',
					"linecolor": integrasjon.color(),
					"linestyle": "solid",
					"href": reverse('admin:systemoversikt_systemintegration_change', args=[integrasjon.pk]),
				}})

			if first_round:
				for s in aktuelt_system.system_integration_destination.all():
					integrasjon = s
					s = s.source_system
					if s not in observerte_systemer:
						neste_nivaa.add(s)
						observerte_systemer.add(s)
					if s not in behandlede_systemer:
						avhengigheter_graf["nodes"].append({"data": {
							"id": s.pk,
							"parent": parent(s),
							"name": s.systemnavn,
							"shape": "ellipse",
							"color": integrasjon.color(),
							"href": reverse('systemdetaljer', args=[s.pk])
						}})
						observerte_driftsmodeller.add(s.driftsmodell_foreignkey)
					avhengigheter_graf["edges"].append({"data": {
						"id": f"integration_{integrasjon.pk}",
						"source": s.pk,
						"target": aktuelt_system.pk,
						'linewidth': 1,
						'curve-style': 'bezier',
						"linecolor": integrasjon.color(),
						"linestyle": "dashed",
						"href": reverse('admin:systemoversikt_systemintegration_change', args=[integrasjon.pk]),
					}})

			behandlede_systemer.add(aktuelt_system)

		aktivt_nivaa_systemer = neste_nivaa
		neste_nivaa = set()
		return aktivt_nivaa_systemer, neste_nivaa

	aktivt_nivaa_systemer, neste_nivaa = avhengighetsrunde(aktivt_nivaa_systemer, neste_nivaa)
	first_round = False
	remaining_follow = follow_count
	while remaining_follow > 0 and aktivt_nivaa_systemer:
		aktivt_nivaa_systemer, neste_nivaa = avhengighetsrunde(aktivt_nivaa_systemer, neste_nivaa)
		remaining_follow -= 1

	drift_gruppe_shape = "roundrectangle"
	drift_gruppe_color = "#F1F9FF"
	for driftsmodell in observerte_driftsmodeller:
		if driftsmodell is not None:
			if driftsmodell.overordnet_plattform:
				avhengigheter_graf["nodes"].append({"data": {
					"id": f"drift_{driftsmodell.pk}",
					"name": driftsmodell.navn,
					"parent": f"drift_{driftsmodell.overordnet_plattform.pk}",
					"shape": drift_gruppe_shape,
					"color": drift_gruppe_color,
				}})
				avhengigheter_graf["nodes"].append({"data": {
					"id": f"drift_{driftsmodell.overordnet_plattform.pk}",
					"name": driftsmodell.overordnet_plattform.navn,
					"shape": drift_gruppe_shape,
					"color": drift_gruppe_color,
				}})
			else:
				avhengigheter_graf["nodes"].append({"data": {
					"id": f"drift_{driftsmodell.pk}",
					"name": driftsmodell.navn,
					"shape": drift_gruppe_shape,
					"color": drift_gruppe_color,
				}})

	url_color = SYSTEM_COLORS["chart_url"]
	bss_color = SYSTEM_COLORS["chart_cmdb_bss"]
	bs_color = SYSTEM_COLORS["chart_cmdb_bs"]
	observerte_cmdb_bs = set()

	def graf_node_navn(tekst, maximum=40):
		if len(tekst) > maximum:
			return tekst[:maximum] + "…"
		return tekst

	def graf_kant(kilde, mal, farge):
		avhengigheter_graf["edges"].append({"data": {
			"source": kilde,
			"target": mal,
			"linewidth": 1,
			"curve-style": "bezier",
			"linecolor": farge,
			"linestyle": "dotted",
		}})

	for url in system.systemurl.all():
		node_id = f"url_{url.pk}"
		avhengigheter_graf["nodes"].append({"data": {
			"id": node_id,
			"name": graf_node_navn(url.domene),
			"shape": "round-rectangle",
			"color": url_color,
			"href": url.domene,
		}})
		graf_kant(system.pk, node_id, url_color)

	for bss in system.service_offerings.select_related("parent_ref").all():
		bss_node_id = f"bss_{bss.pk}"
		avhengigheter_graf["nodes"].append({"data": {
			"id": bss_node_id,
			"name": graf_node_navn(bss.navn),
			"shape": "diamond",
			"color": bss_color,
			"href": reverse("cmdb_bss", args=[bss.pk]),
		}})
		graf_kant(system.pk, bss_node_id, bss_color)

		bs = bss.parent_ref
		if bs is not None and bs.pk not in observerte_cmdb_bs:
			observerte_cmdb_bs.add(bs.pk)
			bs_node_id = f"bs_{bs.pk}"
			avhengigheter_graf["nodes"].append({"data": {
				"id": bs_node_id,
				"name": graf_node_navn(bs.navn),
				"shape": "hexagon",
				"color": bs_color,
				"href": f"{reverse('cmdb_bs_detaljer')}?{urlencode({'search_term': bs.navn})}",
			}})
		if bs is not None:
			graf_kant(bss_node_id, f"bs_{bs.pk}", bs_color)

	# 2026-06-22: Programvare leaf nodes on focal system – same pattern as URL/BSS/BS.
	programvare_color = SYSTEM_COLORS["chart_programvare"]
	for pv in system.programvarer.all():
		node_id = f"programvare_{pv.pk}"
		avhengigheter_graf["nodes"].append({"data": {
			"id": node_id,
			"name": graf_node_navn(pv.programvarenavn),
			"shape": "ellipse",
			"color": programvare_color,
			"href": reverse("programvaredetaljer", args=[pv.pk]),
		}})
		graf_kant(system.pk, node_id, programvare_color)

	return avhengigheter_graf


def systemdetaljer(request, pk):
	#Viser detaljer om et system
	#Tilgangsstyring: Merk at noen informasjonselementer er begrenset i template
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	system = System.objects.get(pk=pk)

	follow_count = int(request.GET.get("follow_count", 0))

	siste_endringer_antall = 10
	system_content_type = ContentType.objects.get_for_model(system)
	siste_endringer = LogEntry.objects.filter(content_type=system_content_type).filter(object_id=pk).order_by('-action_time')[:siste_endringer_antall]

	systembruk = SystemBruk.objects.filter(system=pk).filter(ibruk=True).order_by("brukergruppe")

	# "avleverer til" fra et annet system tilsvarer "mottar fra" dette systemet
	datautveksling_mottar_fra = [i.source_system for i in SystemIntegration.objects.filter(personopplysninger=True,destination_system=system.pk).all()]
	datautveksling_avleverer_til = [i.destination_system for i in SystemIntegration.objects.filter(personopplysninger=True,source_system=system.pk).all()]
	avhengigheter_reverse_systemer = System.objects.filter(avhengigheter_referanser=pk)

	avhengigheter_graf_ny = generer_graf_ny(system, follow_count)

	from django.middleware.csrf import get_token
	saved_layout_json = _system_graph_layout_context(system)
	csrf_js_token = get_token(request)
	save_rettigheter = _user_can_save_system_graph_layout(request.user, system)

	citrix_apps = system.citrix_publications.all()
	for app in citrix_apps:
		app.publikasjon_json = json.loads(app.publikasjon_json)

	tilgangs_ad_grupper = list(system.tilgangsgrupper_ad.all())
	vir_telling_ad_brukere = None
	if tilgangs_ad_grupper:
		ad_brukere_set = adgruppe_transitive_users_db_only(tilgangs_ad_grupper)
		automatisk_brukere_antall_fra_ad = len(ad_brukere_set)
		if ad_brukere_set:
			vir_telling_ad_brukere = Counter(
				User.objects.filter(pk__in=[u.pk for u in ad_brukere_set]).values_list(
					"profile__virksomhet_id", flat=True
				)
			)
		else:
			vir_telling_ad_brukere = Counter()
	else:
		automatisk_brukere_antall_fra_ad = None

	current_user_is_owner = True if request.user.username in system.eiere() else False
	if request.user.groups.filter(name='/DS-SYSTEMOVERSIKT_SAARBARHETSOVERSIKT_SIKKERHETSANALYTIKER').exists():
		current_user_is_owner = True

	# 2026-07-08: Read-only risk overview for system-linked scenarios (non-archived collections).
	from systemoversikt.risk_system import (
		build_system_risk_context,
		user_can_view_system_restricted_security,
	)
	can_view_system_risk = user_can_view_system_restricted_security(request.user, system)
	system_risk_context = build_system_risk_context(system) if can_view_system_risk else {}

	integrasjonsstatus = _integrasjonsstatus("sp_qualys")

	vulnerabilities = list(system.vulnerabilities_old())
	total_number_vulns = len(vulnerabilities)
	unique_vulns = {}
	for v in vulnerabilities:
		if v.title not in unique_vulns:
			unique_vulns[v.title] = {
				"title": v.title,
				"severity": v.severity,
				"known_exploited": v.known_exploited,
				"ansvar_basisdrift": v.ansvar_basisdrift,
				"vulnerabilities": []
			}
		unique_vulns[v.title]["vulnerabilities"].append(v)

	unique_vulns_list = list(unique_vulns.values())
	sorted_unique_vulns = sorted(unique_vulns_list, key=lambda x: (not x["known_exploited"], -x["severity"]))

	systembruk = list(systembruk)
	for bruk in systembruk:
		if vir_telling_ad_brukere is not None:
			bruk.automatisk_ad_antall_for_virksomhet = vir_telling_ad_brukere.get(bruk.brukergruppe_id, 0)
		else:
			bruk.automatisk_ad_antall_for_virksomhet = None

	return render(request, 'system_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemdetaljer': system,
		'systembruk': systembruk,
		'datautveksling_mottar_fra': datautveksling_mottar_fra,
		'datautveksling_avleverer_til': datautveksling_avleverer_til,
		'avhengigheter_reverse_systemer': avhengigheter_reverse_systemer,
		'siste_endringer': siste_endringer,
		'siste_endringer_antall': siste_endringer_antall,
		'avhengigheter_graf_ny': avhengigheter_graf_ny,
		'system_colors': SYSTEM_COLORS,
		'follow_count': follow_count,
		'avhengigheter_chart_size_ny': 300 + len(avhengigheter_graf_ny["nodes"])*20,
		'saved_layout_json': saved_layout_json,
		'csrf_js_token': csrf_js_token,
		'save_rettigheter': save_rettigheter,
		'citrix_apps': citrix_apps,
		'current_user_is_owner': current_user_is_owner,
		'can_view_system_risk': can_view_system_risk,
		'integrasjonsstatus': integrasjonsstatus,
		'vulnerabilities': sorted_unique_vulns,
		'total_number_vulns': total_number_vulns,
		'automatisk_brukere_antall_fra_ad': automatisk_brukere_antall_fra_ad,
		**system_risk_context,
	})



def systemer_pakket(request):
	#Uferdig: vising av hvordan applikasjoner er pakket
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	systemer = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=163)  # 163=UKE
	programvarer = Programvare.objects.all()
	return render(request, 'system_hvordan_pakket.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
		'programvarer': programvarer,
	})



def systemklassifisering_detaljer(request, kriterie=None):
	#Vise systemer filtrert basert på systemeierskapsmodell (felles, sektor, virksomhet)
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if kriterie == None:
		kriterie = "FELLESSYSTEM_OBLIGATORISK"

	if kriterie == "__NONE__":
		utvalg_systemer = System.objects.filter(~Q(ibruk=False)).filter(systemeierskapsmodell=None)
		kriterie = "uten verdi"
	else:
		utvalg_systemer = System.objects.filter(~Q(ibruk=False)).filter(systemeierskapsmodell=kriterie)

	from systemoversikt.models import SYSTEMEIERSKAPSMODELL_VALG
	systemtyper = Systemtype.objects.all()

	return render(request, 'system_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'overskrift': ("Systemer der systemklassifisering er %s" % kriterie.lower()),
		'systemer': utvalg_systemer,
		'kommuneklassifisering': SYSTEMEIERSKAPSMODELL_VALG,
		'systemtyper': systemtyper,
	})



def systemtype_detaljer(request, pk=None):
	#Vise systemer filtrert basert på systemtype (web/app/infrastruktur osv.)
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if pk:
		utvalg_systemer = System.objects.filter(systemtyper=pk)
		systemtype_navn = Systemtype.objects.get(pk=pk).kategorinavn
		overskrift = ("Systemer av typen %s" % systemtype_navn.lower())
	else:
		utvalg_systemer = System.objects.filter(systemtyper=None)
		overskrift = "Systemer som mangler systemtype"

	from systemoversikt.models import SYSTEMEIERSKAPSMODELL_VALG
	systemtyper = Systemtype.objects.all()

	utvalg_systemer = utvalg_systemer.filter(livslop_status__in=[1,2,3,4,5]).order_by('ibruk', Lower('systemnavn'))
	return render(request, 'system_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'overskrift': overskrift,
		'systemer': utvalg_systemer,
		'kommuneklassifisering': SYSTEMEIERSKAPSMODELL_VALG,
		'systemtyper': systemtyper,
	})



def alle_systemer_forvaltere(request):
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	# 2026-06-21: Prefetch contact persons – avoids N+1 on forvalteroversikt table.
	def _ansvarlig_prefetch_qs():
		return Ansvarlig.objects.select_related(
			"brukernavn", "brukernavn__profile", "brukernavn__profile__virksomhet"
		)

	systemer = (
		System.objects.all()
		.select_related("systemeier", "systemforvalter", "driftsmodell_foreignkey")
		.prefetch_related(
			Prefetch("systemeier_kontaktpersoner_referanse", queryset=_ansvarlig_prefetch_qs()),
			Prefetch("systemforvalter_kontaktpersoner_referanse", queryset=_ansvarlig_prefetch_qs()),
		)
	)

	return render(request, 'system_forvalteroversikt.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
	})



def alle_systemer(request):
	#Vise alle systemer
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('vis', 'fellessystem').strip()  # strip removes trailing and leading space
	aktuelle_systemer = System.objects.filter()
	aktuelle_systemer = aktuelle_systemer.order_by('-ibruk', Lower('systemnavn'))

	from systemoversikt.models import SYSTEMEIERSKAPSMODELL_VALG
	systemtyper = Systemtype.objects.all()

	return render(request, 'system_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': aktuelle_systemer,
		'kommuneklassifisering': SYSTEMEIERSKAPSMODELL_VALG,
		'systemtyper': systemtyper,
		'overskrift': ("Systemer"),
	})



def search(request):
	#Vise alle systemer
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space
	navigasjonstreff = []

	# 2026-07-07: Route pure IPv4/CIDR lookups to IP search instead of generic entity search.
	if (
		search_term
		and request.user.has_perm('systemoversikt.view_cmdbdevice')
		and _search_term_is_ip_lookup(search_term)
	):
		return redirect(f"{reverse('alle_ip')}?{urlencode({'search_term': search_term})}")

	try:
		v = Virksomhet.objects.get(virksomhetsforkortelse__iexact=search_term)
		return redirect('virksomhet', v.pk)
	except:
		pass

	aktuelle_personer = None
	if len(search_term) > 4: # det er noen få brukernavn som er identiske med systemnavn..
		try:
			u = User.objects.get(username__iexact=search_term)
			return redirect('bruker_detaljer', u.pk)
		except:
			aktuelle_personer = User.objects.filter(username__icontains=search_term)

	if search_term != '' and len(search_term) > 1:
		# 2026-06-23: Navigation/theme pages before entity hits in search results.
		from systemoversikt.search_nav_pages import match_nav_pages
		navigasjonstreff = match_nav_pages(search_term, request.user)
		aktuelle_systemer = System.objects.filter(~Q(livslop_status=7)).filter(Q(systemnavn__icontains=search_term)|Q(alias__icontains=search_term))
		#Her ønsker vi å vise treff i beskrivelsesfeltet, men samtidig ikke vise systemer på nytt
		potensielle_systemer = System.objects.filter(~Q(livslop_status=7)).filter(Q(systembeskrivelse__icontains=search_term) & ~Q(pk__in=aktuelle_systemer))
		aktuelle_programvarer = Programvare.objects.filter(Q(programvarenavn__icontains=search_term)|Q(alias__icontains=search_term))
		domenetreff = SystemUrl.objects.filter(domene__icontains=search_term)
		aktuelle_leverandorer = Leverandor.objects.filter(leverandor_navn__icontains=search_term)
		business_services = CMDBRef.objects.filter(navn__icontains=search_term)
		aktuelle_adgrupper = ADgroup.objects.filter(common_name__icontains=search_term)
		aktuelle_servere = CMDBdevice.objects.filter(comp_name__icontains=search_term)
		aktuelle_databaser = CMDBdatabase.objects.filter(db_database__icontains=search_term)
		enterpriseapps = AzureApplication.objects.filter(displayName__icontains=search_term, active=True)
		aktuelle_orgledd = HRorg.objects.filter(ou__icontains=search_term)
		systemer_avviklet = System.objects.filter(Q(livslop_status=7)).filter(Q(systemnavn__icontains=search_term)|Q(alias__icontains=search_term))
		aktuelle_citrixapper = CitrixPublication.objects.filter(application_name__icontains=search_term)
	else:
		messages.info(request, 'Lengden på det du søker på må minimum være 2 tegn')
		navigasjonstreff = []
		aktuelle_systemer = System.objects.none()
		potensielle_systemer = System.objects.none()
		aktuelle_programvarer = Programvare.objects.none()
		domenetreff = SystemUrl.objects.none()
		aktuelle_leverandorer = Leverandor.objects.none()
		aktuelle_personer = User.objects.none()
		business_services = CMDBRef.objects.none()
		aktuelle_adgrupper = ADgroup.objects.none()
		aktuelle_servere = CMDBdevice.objects.none()
		aktuelle_databaser = CMDBdatabase.objects.none()
		enterpriseapps = AzureApplication.objects.none()
		aktuelle_orgledd = HRorg.objects.none()
		systemer_avviklet = System.objects.none()
		aktuelle_citrixapper = CitrixPublication.objects.none()

	#if (len(aktuelle_systemer) == 1) and (len(aktuelle_programvarer) == 0) and (len(domenetreff) == 0):  # bare ét systemtreff og ingen programvaretreff.
	#   return redirect('systemdetaljer', aktuelle_systemer[0].pk)

	aktuelle_systemer = aktuelle_systemer.order_by('-ibruk', Lower('systemnavn'))
	potensielle_systemer = potensielle_systemer.order_by('ibruk', Lower('systemnavn'))
	aktuelle_programvarer.order_by(Lower('programvarenavn'))
	domenetreff.order_by(Lower('domene'))
	aktuelle_adgrupper.order_by(Lower('common_name'))

	#from systemoversikt.models import SYSTEMEIERSKAPSMODELL_VALG
	#systemtyper = Systemtype.objects.all()

	return render(request, 'site_search.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': aktuelle_systemer,
		'potensielle_systemer': potensielle_systemer,
		'search_term': search_term,
		'domenetreff': domenetreff,
		'aktuelle_programvarer': aktuelle_programvarer,
		'aktuelle_leverandorer': aktuelle_leverandorer,
		'business_services': business_services,
		'aktuelle_adgrupper': aktuelle_adgrupper,
		'aktuelle_servere': aktuelle_servere,
		'enterpriseapps': enterpriseapps,
		'aktuelle_personer': aktuelle_personer,
		'aktuelle_databaser': aktuelle_databaser,
		'aktuelle_orgledd': aktuelle_orgledd,
		'systemer_avviklet': systemer_avviklet,
		'aktuelle_citrixapper': aktuelle_citrixapper,
		'navigasjonstreff': navigasjonstreff,
	})



def bruksdetaljer(request, pk):
	#Vise detaljer om systembruk
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	bruk = SystemBruk.objects.get(pk=pk)

	return render(request, 'systembruk_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'bruk': bruk,
	})



def mine_systembruk(request):
	#Redirect for å sende bruker til detaljer om innlogget brukers virksomhets systembruk
	required_permissions = None

	try:
		brukers_virksomhet = request.user.profile.virksomhet_forkortelse
		pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
		return redirect('all_bruk_for_virksomhet', pk)
	except:
		messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
		return redirect('alle_virksomheter')



def all_bruk_for_virksomhet(request, pk):
	#Vise detaljer om en valgt virksomhets systembruk
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet_pk = pk
	all_systembruk = SystemBruk.objects.filter(brukergruppe=virksomhet_pk, ibruk=True).exclude(system__livslop_status__in=[6,7]).order_by(Lower('system__systemnavn'))  # sortering er ellers case-sensitiv
	ikke_i_bruk = SystemBruk.objects.filter(brukergruppe=virksomhet_pk).filter(system__livslop_status__in=[6,7]).order_by(Lower('system__systemnavn'))  # sortering er ellers case-sensitiv

	try:
		virksomhet = Virksomhet.objects.get(pk=pk)
	except:
		messages.warning(request, 'Fant ingen virksomhet med denne ID-en.')
		virksomhet = Virksomhet.objects.none()

	all_programvarebruk = ProgramvareBruk.objects.filter(brukergruppe=virksomhet_pk).order_by(Lower('programvare__programvarenavn'))

	eier_eller_forvalter = set(System.objects.filter(~Q(livslop_status=7)).filter(Q(systemeier=virksomhet_pk) or Q(systemforvalter=virksomhet_pk)))  #{1, 2, 3, 4} #systemer virksomhet eier liste
	systembruk = set(SystemBruk.objects.filter(brukergruppe=virksomhet_pk)) # {3, 4} #systemer virksomhet bruker liste
	systemer_ibruk = []
	for b in systembruk:
		systemer_ibruk.append(b.system)
	systemer_ibruk = set(systemer_ibruk)

	#print([s.id for s in systemer_ibruk])
	#print([s.id for s in eier_eller_forvalter])
	mangler_bruk = eier_eller_forvalter - systemer_ibruk
	#print([s.id for s in mangler_bruk])

	return render(request, 'systembruk_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'all_systembruk': all_systembruk,
		'all_programvarebruk': all_programvarebruk,
		'ikke_i_bruk': ikke_i_bruk,
		'virksomhet': virksomhet,
		'mangler_bruk': mangler_bruk,
	})



def registrer_bruk(request, system):
	#Forenklet metode for å legge til bruk av system ved avkryssing
	required_permissions = ['systemoversikt.add_systembruk']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from django.core.exceptions import ObjectDoesNotExist
	system_instans = System.objects.get(pk=system)
	alle_virksomheter = list(Virksomhet.objects.all())

	if request.POST:
		virksomheter = request.POST.getlist("virksomheter", "")
		for str_virksomhet in virksomheter:
			virksomhet = Virksomhet.objects.get(pk=int(str_virksomhet))
			alle_virksomheter.remove(virksomhet)
			try:
				bruk = SystemBruk.objects.get(brukergruppe=virksomhet, system=system_instans)
				if bruk.ibruk == False:
					bruk.ibruk = True
					bruk.save()
					#print("Satt %s aktiv" % bruk)
			except ObjectDoesNotExist:
				bruk = SystemBruk.objects.create(
					brukergruppe=virksomhet,
					system=system_instans,
					ibruk=True,
				)
				#print("Opprettet %s" % bruk)
		for virk in alle_virksomheter: # alle som er igjen, ble ikke merket, merk som ikke i bruk
			try:
				bruk = SystemBruk.objects.get(system=system_instans, brukergruppe=virk)
				if bruk.ibruk == True:
					bruk.ibruk = False
					bruk.save()
					#print("Satt %s deaktiv" % bruk)
			except ObjectDoesNotExist:
				pass # trenger ikke sette et ikke-eksisterende objekt
		return redirect('systemdetaljer', system_instans.pk)

	virksomheter_template = list()
	for virk in Virksomhet.objects.filter(ordinar_virksomhet=True):
		try:
			bruk = SystemBruk.objects.get(system=system_instans, brukergruppe=virk, ibruk=True)
			virksomheter_template.append({"virksomhet": virk, "bruk": bruk})
		except:
			virksomheter_template.append({"virksomhet": virk, "bruk": None})

	return render(request, 'system_registrer_bruk.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'target': system_instans,
		'target_name': system_instans.systemnavn,
		'back_link': reverse('systemdetaljer', args=[system_instans.pk]),
		'virksomheter_template': virksomheter_template,
	})


def bydel_virksomheter():
	# 2026-06-19: Shared bydel filter – virksomhetsnavn starting with "bydel", ordinær only.
	return Virksomhet.objects.filter(
		virksomhetsnavn__istartswith="bydel",
		ordinar_virksomhet=True,
	).order_by("virksomhetsforkortelse")


def _systembruk_bydeler_cell_symbol(bruk_set, forvalt_set, system_id, virksomhet_id):
	has_bruk = (system_id, virksomhet_id) in bruk_set
	has_forvalt = (system_id, virksomhet_id) in forvalt_set
	if has_bruk and has_forvalt:
		return "BF"
	if has_bruk:
		return "B"
	if has_forvalt:
		return "F"
	return ""


def _systembruk_bydeler_cell(bruk_set, forvalt_set, system_id, virksomhet_id):
	# 2026-06-19: Cell dict for template – inline background beats tablesorter zebra striping.
	symbol = _systembruk_bydeler_cell_symbol(bruk_set, forvalt_set, system_id, virksomhet_id)
	if symbol == "B":
		cell_style = "background-color: #d4edda;"
	elif symbol in ("F", "BF"):
		cell_style = "background-color: #f8d7da;"
	else:
		cell_style = ""
	return {"symbol": symbol, "cell_style": cell_style}


def _programvare_bydeler_cell(bruk_set, programvare_id, virksomhet_id):
	# 2026-06-19: Programvare has no organisatorisk forvaltning – only active use (B).
	if (programvare_id, virksomhet_id) in bruk_set:
		return {"symbol": "B", "cell_style": "background-color: #d1ecf1;"}
	return {"symbol": "", "cell_style": ""}


def systembruk_bydeler_oversikt(request):
	# 2026-06-19: Cross-bydel matrix – same report for all users; no logged-in virksomhet column.
	# 2026-06-19: Added programvare section – bruk only, separate table, shared vis filter.
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	bydeler = list(bydel_virksomheter())
	bydel_ids = {b.pk for b in bydeler}

	klassifisering = request.GET.get('klassifisering', '').strip()
	vis = request.GET.get('vis', 'alle').strip()
	if vis not in ('alle', 'systemer', 'programvare'):
		vis = 'alle'
	vis_systemer = vis in ('alle', 'systemer')
	vis_programvare = vis in ('alle', 'programvare')

	brukt_ids = set(SystemBruk.objects.filter(
		brukergruppe__in=bydeler,
		ibruk=True,
	).exclude(system__livslop_status__in=[6, 7]).values_list('system_id', flat=True))

	forvalt_ids = set(System.objects.filter(
		Q(systemeier__in=bydeler) | Q(systemforvalter__in=bydeler),
	).exclude(livslop_status__in=[6, 7]).values_list('pk', flat=True))

	all_system_ids = brukt_ids | forvalt_ids

	systemer_qs = System.objects.filter(pk__in=all_system_ids).select_related(
		'systemforvalter',
	).order_by(Lower('systemnavn'))

	if klassifisering:
		systemer_qs = systemer_qs.filter(systemeierskapsmodell=klassifisering)

	systemer = list(systemer_qs)
	system_ids = [s.pk for s in systemer]

	bruk_set = set(SystemBruk.objects.filter(
		system_id__in=system_ids,
		brukergruppe_id__in=bydel_ids,
		ibruk=True,
	).values_list('system_id', 'brukergruppe_id'))

	forvalt_set = set()
	for system in systemer:
		if system.systemeier_id and system.systemeier_id in bydel_ids:
			forvalt_set.add((system.pk, system.systemeier_id))
		if system.systemforvalter_id and system.systemforvalter_id in bydel_ids:
			forvalt_set.add((system.pk, system.systemforvalter_id))

	columns = [{'virksomhet': b} for b in bydeler]

	system_rows = []
	for system in systemer:
		cells = []
		for col in columns:
			cells.append(_systembruk_bydeler_cell(
				bruk_set, forvalt_set, system.pk, col['virksomhet'].pk,
			))
		system_rows.append({
			'system': system,
			'cells': cells,
		})

	prog_brukt_ids = set(ProgramvareBruk.objects.filter(
		brukergruppe__in=bydeler,
		ibruk=True,
	).exclude(programvare__livslop_status__in=[6, 7]).values_list('programvare_id', flat=True))

	programvarer = list(Programvare.objects.filter(
		pk__in=prog_brukt_ids,
	).prefetch_related('programvareleverandor').order_by(Lower('programvarenavn')))

	prog_bruk_set = set(ProgramvareBruk.objects.filter(
		programvare_id__in=prog_brukt_ids,
		brukergruppe_id__in=bydel_ids,
		ibruk=True,
	).values_list('programvare_id', 'brukergruppe_id'))

	programvare_rows = []
	for programvare in programvarer:
		cells = []
		for col in columns:
			cells.append(_programvare_bydeler_cell(
				prog_bruk_set, programvare.pk, col['virksomhet'].pk,
			))
		programvare_rows.append({
			'programvare': programvare,
			'cells': cells,
		})

	from systemoversikt.models import SYSTEMEIERSKAPSMODELL_VALG

	return render(request, 'systembruk_bydeler_oversikt.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'system_rows': system_rows,
		'programvare_rows': programvare_rows,
		'columns': columns,
		'klassifisering': klassifisering,
		'vis': vis,
		'vis_systemer': vis_systemer,
		'vis_programvare': vis_programvare,
		'systemklassifisering_valg': SYSTEMEIERSKAPSMODELL_VALG,
		'antall_systemer': len(system_rows),
		'antall_programvare': len(programvare_rows),
	})


def systembruk_bydeler_ekskludert(request):
	# 2026-06-19: Moved from /systemer/bydelsbruk/ – gap report for systems bydeler use that we do not.
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	din_virksomhet = request.user.profile.virksomhet

	bydelssystemer = System.objects.filter(~Q(livslop_status=7)).filter(
			systembruk_system__brukergruppe__in=bydel_virksomheter()).filter(~Q(
			systembruk_system__brukergruppe=din_virksomhet)).distinct()

	return render(request, 'systembruk_bydeler.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': bydelssystemer,
		'din_virksomhet': din_virksomhet,
	})


def registrer_bruk_programvare(request, programvare):
	#Forenklet metode for å legge til bruk av programvare ved avkryssing
	required_permissions = ['systemoversikt.add_programvarebruk']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from django.core.exceptions import ObjectDoesNotExist
	programvare_instans = Programvare.objects.get(pk=programvare)
	alle_virksomheter = list(Virksomhet.objects.all())

	if request.POST:
		virksomheter = request.POST.getlist("virksomheter", "")
		for str_virksomhet in virksomheter:
			virksomhet = Virksomhet.objects.get(pk=int(str_virksomhet))
			alle_virksomheter.remove(virksomhet)
			try:
				bruk = ProgramvareBruk.objects.get(brukergruppe=virksomhet, programvare=programvare_instans)
				if bruk.ibruk == False:
					bruk.ibruk = True
					bruk.save()
					#print("Satt %s aktiv" % bruk)
			except ObjectDoesNotExist:
				bruk = ProgramvareBruk.objects.create(
					brukergruppe=virksomhet,
					programvare=programvare_instans,
					ibruk=True,
				)
				#print("Opprettet %s" % bruk)
		for virk in alle_virksomheter: # alle som er igjen, ble ikke merket, merk som ikke i bruk
			try:
				bruk = ProgramvareBruk.objects.get(programvare=programvare_instans, brukergruppe=virk)
				if bruk.ibruk == True:
					bruk.ibruk = False
					bruk.save()
					#print("Satt %s deaktiv" % bruk)
			except ObjectDoesNotExist:
				pass # trenger ikke sette et ikke-eksisterende objekt
		return redirect('programvaredetaljer', programvare_instans.pk)

	virksomheter_template = list()
	for virk in Virksomhet.objects.filter(ordinar_virksomhet=True):
		try:
			bruk = ProgramvareBruk.objects.get(programvare=programvare_instans, brukergruppe=virk, ibruk=True)
			virksomheter_template.append({"virksomhet": virk, "bruk": bruk})
		except:
			virksomheter_template.append({"virksomhet": virk, "bruk": None})

	return render(request, 'system_registrer_bruk.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'target': programvare_instans,
		'target_name': programvare_instans.programvarenavn,
		'back_link': reverse('programvaredetaljer', args=[programvare_instans.pk]),
		'virksomheter_template': virksomheter_template,
	})



def rapport_named_locations(request):

	required_permissions = None
	color_table = []
	color_table_display = []
	color_table.append(['Land', 'Fargekode'])

	def populate(named_location_id, color_code, color_name): # 1 is green, 2 is yellow, 3 is red and 4 is black
		named_location = AzureNamedLocations.objects.get(ipNamedLocation_id=named_location_id)
		for country in json.loads(named_location.countriesAndRegions):
			#print(country)
			color_table.append([{"v": country["code"], "f": country["name"]}, color_code])
			color_table_display.append({"land": country["name"], "farge": color_name})

	data = [
		{"named_location_id": '141f4101-6ea0-4cd0-9c6e-2b57e868876f', "color_code": 1, "color_name": "grønn"}, # grønn
		{"named_location_id": '1b0ee1ab-e197-45bf-b48c-c05999613ea8', "color_code": 2, "color_name": "gul"}, # gul
		{"named_location_id": '1c5daa1a-f370-4512-9078-bf81159ee7b2', "color_code": 3, "color_name": "rød"}, # rød
		{"named_location_id": '801537bb-85ee-4b84-8202-1e69779a54c3', "color_code": 4, "color_name": "sort"}, # sort
	]

	for item in data:
		populate(item["named_location_id"], item["color_code"], item["color_name"])

	return render(request, "rapport_named_locations.html", {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'color_table': color_table,
		'color_table_display': color_table_display,
		'integrasjonsstatus': _integrasjonsstatus("azure_named_locations"),
	})



def programvaredetaljer(request, pk):
	#Vise detaljer for programvare
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	siste_endringer_antall = 10
	content_type = ContentType.objects.get_for_model(Programvare)
	siste_endringer = LogEntry.objects.filter(content_type=content_type).filter(object_id=pk).order_by('-action_time')[:siste_endringer_antall]
	programvare = Programvare.objects.get(pk=pk)
	programvarebruk = ProgramvareBruk.objects.filter(programvare=pk, ibruk=True).order_by("brukergruppe")

	return render(request, "programvare_detaljer.html", {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'programvare': programvare,
		'programvarebruk': programvarebruk,
		'siste_endringer': siste_endringer,
		'siste_endringer_antall': siste_endringer_antall,
	})



def alle_programvarer(request):
	#Vise alle programvarer
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space

	if search_term == "":
		aktuelle_programvarer = Programvare.objects.all()
	elif len(search_term) < 2: # if one or less, return nothing
		aktuelle_programvarer = Programvare.objects.none()
	else:
		aktuelle_programvarer = Programvare.objects.filter(programvarenavn__icontains=search_term)

	aktuelle_programvarer = aktuelle_programvarer.order_by(Lower('programvarenavn'))

	programvare = Programvare.objects.values_list('programvarenavn', flat=True).distinct()
	leverandorer = Leverandor.objects.values_list('leverandor_navn', flat=True).distinct()
	systemer = System.objects.values_list('systemnavn', flat=True).distinct()
	programvare_json = json.dumps(list(programvare) + list(leverandorer) + list(systemer))

	return render(request, 'programvare_alle.html', {
		'overskrift': "Programvarer og applikasjoner",
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'programvarer': aktuelle_programvarer,
		'programvare_json': programvare_json,
	})




def alle_programvarer_optimized(request):
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {
			'required_permissions': required_permissions,
			'groups': request.user.groups
		})

	search_term = request.GET.get('search_term', '').strip()

	if search_term in ["", "__all__"]:
		aktuelle_programvarer = Programvare.objects.all()
	elif len(search_term) < 2:
		aktuelle_programvarer = Programvare.objects.none()
	else:
		aktuelle_programvarer = Programvare.objects.filter(programvarenavn__icontains=search_term)

	# ---- KEY OPTIMIZATIONS ----
	aktuelle_programvarer = (
		aktuelle_programvarer
		.only('pk', 'programvarenavn', 'programvarebeskrivelse', 'til_cveoversikt_og_nyheter')
		.order_by(Lower('programvarenavn'))
		.prefetch_related(
			'programvareleverandor',
			'kategorier',
			Prefetch('systemer', queryset=System.objects.select_related('systemforvalter')),
			'programvarebruk_programvare__brukergruppe'
		)
	)

	# Cache count to avoid second query in template
	programvarer_count = aktuelle_programvarer.count()

	# Autocomplete raw list (unchanged)
	programvare = Programvare.objects.values_list('programvarenavn', flat=True).distinct()
	leverandorer = Leverandor.objects.values_list('leverandor_navn', flat=True).distinct()
	systemer = System.objects.values_list('systemnavn', flat=True).distinct()
	programvare_json = json.dumps(list(programvare) + list(leverandorer) + list(systemer))

	return render(request, 'programvare_alle.html', {
		'overskrift': "Programvarer og applikasjoner",
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'programvarer': aktuelle_programvarer,
		'programvare_json': programvare_json,
		'programvarer_count': programvarer_count,  # use this in template
		'search_term': search_term,
	})





def programvarebruksdetaljer(request, pk):
	#Vise detaljer for bruk av programvare
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	bruksdetaljer = ProgramvareBruk.objects.get(pk=pk)

	return render(request, "programvarebruk_detaljer.html", {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'bruksdetaljer': bruksdetaljer,
	})


"""
def alle_tjenester(request):
	tjenester = Tjeneste.objects.all().order_by(Lower('tjenestenavn'))
	template = 'alle_tjenester.html'

	return render(request, template, {
		'overskrift': "Tjenester",
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'tjenester': tjenester,
	})

def tjenestedetaljer(request, pk):
	tjeneste = Tjeneste.objects.get(pk=pk)

	return render(request, 'detaljer_tjeneste.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'tjeneste': tjeneste,
	})
"""


def virksomhet_ansvarlige(request, pk=None):

	if pk == None:
		try:
			brukers_virksomhet = request.user.profile.virksomhet_forkortelse
			pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
			return redirect('virksomhet_ansvarlige', pk)
		except:
			messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
			return redirect('alle_virksomheter')

	#Vise alle ansvarlige knyttet til valgt virksomhet
	required_permissions = ['systemoversikt.view_ansvarlig']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	ansvarlige = Ansvarlig.objects.filter(brukernavn__profile__virksomhet=pk).order_by('brukernavn__first_name')
	return render(request, 'ansvarlig_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ansvarlige': ansvarlige,
		'virksomhet': virksomhet,
	})


def brukere_startside(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	antall_aktive_brukere = User.objects.filter(profile__accountdisable=False).count()
	antall_deaktive_brukere = User.objects.filter(profile__accountdisable=True).count()


	return render(request, 'brukere_startside.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'antall_aktive_brukere': antall_aktive_brukere,
		'antall_deaktive_brukere': antall_deaktive_brukere,
	})


OU_STR_VANLIGE_VIRKSOMHETER = [
		"OU=BAL,OU=Brukere,OU=OK",
		"OU=BAR,OU=Brukere,OU=OK",
		"OU=BBJ,OU=Brukere,OU=OK",
		"OU=BBY,OU=Brukere,OU=OK",
		"OU=BER,OU=Brukere,OU=OK",
		"OU=BFE,OU=Brukere,OU=OK",
		"OU=BFR,OU=Brukere,OU=OK",
		"OU=BGA,OU=Brukere,OU=OK",
		"OU=BGO,OU=Brukere,OU=OK",
		"OU=BGR,OU=Brukere,OU=OK",
		"OU=BNA,OU=Brukere,OU=OK",
		"OU=BNS,OU=Brukere,OU=OK",
		"OU=BOS,OU=Brukere,OU=OK",
		"OU=BRE,OU=Brukere,OU=OK",
		"OU=BSA,OU=Brukere,OU=OK",
		"OU=BSH,OU=Brukere,OU=OK",
		"OU=BSL,OU=Brukere,OU=OK",
		"OU=BSN,OU=Brukere,OU=OK",
		"OU=BSR,OU=Brukere,OU=OK",
		"OU=BUN,OU=Brukere,OU=OK",
		"OU=BVA,OU=Brukere,OU=OK",
		"OU=BYA,OU=Brukere,OU=OK",
		"OU=BYM,OU=Brukere,OU=OK",
		"OU=BYR,OU=Brukere,OU=OK",
		"OU=BYS,OU=Brukere,OU=OK",
		"OU=BYU,OU=Brukere,OU=OK",
		"OU=DEB,OU=Brukere,OU=OK",
		"OU=DIG,OU=Brukere,OU=OK",
		"OU=EBY,OU=Brukere,OU=OK",
		"OU=EGE,OU=Brukere,OU=OK",
		"OU=FIL,OU=Brukere,OU=OK",
		"OU=FOB,OU=Brukere,OU=OK",
		"OU=GFE,OU=Brukere,OU=OK",
		"OU=GPE,OU=Brukere,OU=OK",
		"OU=HAV,OU=Brukere,OU=OK",
		"OU=HEL,OU=Brukere,OU=OK",
		"OU=HME,OU=Brukere,OU=OK",
		"OU=HSO,OU=Brukere,OU=OK",
		"OU=INE,OU=Brukere,OU=OK",
		"OU=KAO,OU=Brukere,OU=OK",
		"OU=KEM,OU=Brukere,OU=OK",
		"OU=KID,OU=Brukere,OU=OK",
		"OU=KLI,OU=Brukere,OU=OK",
		"OU=KRV,OU=Brukere,OU=OK",
		"OU=KUL,OU=Brukere,OU=OK",
		"OU=LVA,OU=Brukere,OU=OK",
		"OU=MAL,OU=Brukere,OU=OK",
		"OU=MUM,OU=Brukere,OU=OK",
		"OU=NAE,OU=Brukere,OU=OK",
		"OU=NAV,OU=Brukere,OU=OK",
		"OU=OBF,OU=Brukere,OU=OK",
		"OU=OBY,OU=Brukere,OU=OK",
		"OU=ODE,OU=Brukere,OU=OK",
		"OU=OKF,OU=Brukere,OU=OK",
		"OU=OOO,OU=Brukere,OU=OK",
		"OU=PBE,OU=Brukere,OU=OK",
		"OU=REG,OU=Brukere,OU=OK",
		"OU=REN,OU=Brukere,OU=OK",
		"OU=RFT,OU=Brukere,OU=OK",
		"OU=SYE,OU=Brukere,OU=OK",
		"OU=UBF,OU=Brukere,OU=OK",
		"OU=UDE,OU=Brukere,OU=OK",
		"OU=UKE,OU=Brukere,OU=OK",
		"OU=VAV2,OU=Brukere,OU=OK",
		"OU=VAV,OU=Brukere,OU=OK",
		"OU=VEL,OU=Brukere,OU=OK",
		"OU=BAL,OU=Eksterne brukere,OU=OK",
		"OU=BAR,OU=Eksterne brukere,OU=OK",
		"OU=BBJ,OU=Eksterne brukere,OU=OK",
		"OU=BBY,OU=Eksterne brukere,OU=OK",
		"OU=BER,OU=Eksterne brukere,OU=OK",
		"OU=BFE,OU=Eksterne brukere,OU=OK",
		"OU=BFR,OU=Eksterne brukere,OU=OK",
		"OU=BGA,OU=Eksterne brukere,OU=OK",
		"OU=BGO,OU=Eksterne brukere,OU=OK",
		"OU=BGR,OU=Eksterne brukere,OU=OK",
		"OU=BNA,OU=Eksterne brukere,OU=OK",
		"OU=BNS,OU=Eksterne brukere,OU=OK",
		"OU=BOS,OU=Eksterne brukere,OU=OK",
		"OU=BRE,OU=Eksterne brukere,OU=OK",
		"OU=BSA,OU=Eksterne brukere,OU=OK",
		"OU=BSH,OU=Eksterne brukere,OU=OK",
		"OU=BSL,OU=Eksterne brukere,OU=OK",
		"OU=BSN,OU=Eksterne brukere,OU=OK",
		"OU=BSR,OU=Eksterne brukere,OU=OK",
		"OU=BUN,OU=Eksterne brukere,OU=OK",
		"OU=BVA,OU=Eksterne brukere,OU=OK",
		"OU=BYA,OU=Eksterne brukere,OU=OK",
		"OU=BYM,OU=Eksterne brukere,OU=OK",
		"OU=BYR,OU=Eksterne brukere,OU=OK",
		"OU=BYS,OU=Eksterne brukere,OU=OK",
		"OU=BYU,OU=Eksterne brukere,OU=OK",
		"OU=DEB,OU=Eksterne brukere,OU=OK",
		"OU=DIG,OU=Eksterne brukere,OU=OK",
		"OU=EBY,OU=Eksterne brukere,OU=OK",
		"OU=EGE,OU=Eksterne brukere,OU=OK",
		"OU=FIL,OU=Eksterne brukere,OU=OK",
		"OU=FOB,OU=Eksterne brukere,OU=OK",
		"OU=GFE,OU=Eksterne brukere,OU=OK",
		"OU=GPE,OU=Eksterne brukere,OU=OK",
		"OU=HAV,OU=Eksterne brukere,OU=OK",
		"OU=HEL,OU=Eksterne brukere,OU=OK",
		"OU=HME,OU=Eksterne brukere,OU=OK",
		"OU=HSO,OU=Eksterne brukere,OU=OK",
		"OU=INE,OU=Eksterne brukere,OU=OK",
		"OU=KAO,OU=Eksterne brukere,OU=OK",
		"OU=KEM,OU=Eksterne brukere,OU=OK",
		"OU=KID,OU=Eksterne brukere,OU=OK",
		"OU=KLI,OU=Eksterne brukere,OU=OK",
		"OU=KRV,OU=Eksterne brukere,OU=OK",
		"OU=KUL,OU=Eksterne brukere,OU=OK",
		"OU=MUM,OU=Eksterne brukere,OU=OK",
		"OU=NAE,OU=Eksterne brukere,OU=OK",
		"OU=NAV,OU=Eksterne brukere,OU=OK",
		"OU=OBF,OU=Eksterne brukere,OU=OK",
		"OU=OBY,OU=Eksterne brukere,OU=OK",
		"OU=ODE,OU=Eksterne brukere,OU=OK",
		"OU=OKF,OU=Eksterne brukere,OU=OK",
		"OU=OOO,OU=Eksterne brukere,OU=OK",
		"OU=PBE,OU=Eksterne brukere,OU=OK",
		"OU=REG,OU=Eksterne brukere,OU=OK",
		"OU=REN,OU=Eksterne brukere,OU=OK",
		"OU=RFT,OU=Eksterne brukere,OU=OK",
		"OU=SYE,OU=Eksterne brukere,OU=OK",
		"OU=UBF,OU=Eksterne brukere,OU=OK",
		"OU=UDE,OU=Eksterne brukere,OU=OK",
		"OU=UKE,OU=Eksterne brukere,OU=OK",
		"OU=VAV,OU=Eksterne brukere,OU=OK",
		"OU=VEL,OU=Eksterne brukere,OU=OK",
		"OU=Kontakt",
		"OU=Ressurser"
	]


def ikke_byttet_passord_normal_users(request):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from functools import reduce
	from operator import or_

	ou_navnliste = OU_STR_VANLIGE_VIRKSOMHETER
	cutoff = timezone.make_aware(datetime.datetime(2023, 11, 23))

	exclude_q = reduce(
		or_,
		(Q(profile__distinguishedname__icontains=ou) for ou in ou_navnliste)
	)

	ikke_byttet = (
		User.objects
		#.filter(profile__accountdisable=False)
		.filter(
			Q(profile__pwdLastSet__isnull=True) |
			Q(profile__pwdLastSet__lt=cutoff)
		)
		.filter(exclude_q)
	)


	return render(request, 'ikke_byttet_passord.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ikke_byttet': ikke_byttet,
		'dato': cutoff,
	})



def ikke_byttet_passord_annet(request):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from functools import reduce
	from operator import or_

	ou_navnliste = OU_STR_VANLIGE_VIRKSOMHETER
	cutoff = timezone.make_aware(datetime.datetime(2023, 11, 23))

	exclude_q = reduce(
		or_,
		(Q(profile__distinguishedname__icontains=ou) for ou in ou_navnliste)
	)

	ikke_byttet = (
		User.objects
		#.filter(profile__accountdisable=False)
		.filter(
			Q(profile__pwdLastSet__isnull=True) |
			Q(profile__pwdLastSet__lt=cutoff)
		)
		.exclude(exclude_q)
	)


	return render(request, 'ikke_byttet_passord.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ikke_byttet': ikke_byttet,
		'dato': cutoff,
	})


def enhet_detaljer(request, pk):
	#Vise informasjon om en konkret organisatorisk enhet
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	unit = HRorg.objects.get(pk=pk)
	sideenheter = HRorg.objects.filter(direkte_mor=unit).order_by('ou')
	personer = User.objects.filter(profile__org_unit=pk).order_by('profile__displayName')
	systemer_ansvarfor = System.objects.filter(systemforvalter_avdeling_referanse=unit).filter(~Q(livslop_status__in=[7]))

	return render(request, 'virksomhet_enhet_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'unit': unit,
		'sideenheter': sideenheter,
		'brukere': personer,
		'systemer_ansvarfor': systemer_ansvarfor,
	})




def virksomhet_enhetsok(request):
	#Vise informasjon om organisatorisk struktur
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term_org', "").strip()
	if len(search_term) > 1:
		units = HRorg.objects.filter(ou__icontains=search_term).filter(active=True).order_by('virksomhet_mor')
	else:
		units = HRorg.objects.none()


	antall_aktive_brukere = User.objects.filter(profile__accountdisable=False).count()
	antall_deaktive_brukere = User.objects.filter(profile__accountdisable=True).count()
	antall_organisasjonsledd = HRorg.objects.all().count()
	antall_adgrupper = ADgroup.objects.all().count()


	return render(request, 'virksomhet_enhetsok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'units': units,
		'search_term_org': search_term,
		'antall_aktive_brukere': antall_aktive_brukere,
		'antall_deaktive_brukere': antall_deaktive_brukere,
		'antall_organisasjonsledd': antall_organisasjonsledd,
		'antall_adgrupper': antall_adgrupper,
		'integrasjonsstatus_list': _integrasjonsstatus_flere("grunndatabase_org", "ad_users"),
	})



def virksomhet_enheter(request, pk):
	#Vise informasjon om organisatorisk struktur
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import math
	virksomhet = Virksomhet.objects.get(pk=pk)

	avhengigheter_graf = {"nodes": [], "edges": []}

	def color(unit):
		palett = {
			1: "black",
			2: "#ff0000",
			3: "#cc0033",
			4: "#990066",
			5: "#660099",
			6: "#3300cc",
			7: "#0000ff",
		}
		try:
			return palett[unit.level]
		except:
			return "black"

	"""
	def size(unit):
		minimum = 25
		if unit.num_members > 0:
			adjusted_member_count = minimum + (20 * math.log(unit.num_members, 10))
			return ("%spx" % adjusted_member_count)
		else:
			return ("%spx" % minimum)
	"""

	nodes = []
	units = HRorg.objects.filter(virksomhet_mor=pk).filter(active=True).filter(level__gt=2)
	for u in units:
		members = User.objects.filter(profile__org_unit=u.pk)
		if len(members) > 0:
			u.num_members = len(members)
			nodes.append(u)
			nodes.append(u.direkte_mor)
			avhengigheter_graf["edges"].append(
				{"data": {
					"source": u.direkte_mor.pk,
					"target": u.pk,
					"linestyle": "solid"
					}
				})
	for u in nodes:
		avhengigheter_graf["nodes"].append(
			{"data": {
				"id": u.pk,
				"name": u.ou,
				"parent": u.direkte_mor.ou,
				"shape": "ellipse",
				"color": color(u),
				#"size": size(u)
				#"href": reverse('adgruppe_detaljer', args=[m.pk])
				}
			})

	return render(request, 'virksomhet_enheter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'units': units,
		'virksomhet': virksomhet,
		'avhengigheter_graf': avhengigheter_graf,
	})


def api_overview(request):
	#Vise informasjon brukere som har leverandørtilgang
	required_permissions = ['auth.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


	return render(request, 'rapport_api_overview.html', {
		"request": request,
		"required_permissions": required_permissions,
	})


@login_required
def api_tjeneste_systemoversikt_docs(request):
	from systemoversikt.api_tjeneste_systemoversikt_docs import (
		AUTH_INFO,
		BASE_URL,
		ENDPOINTS,
		LIMITATIONS,
		RESPONSE_WRAPPER,
		REFERENCE_PATTERN,
		SYNC_GUIDE,
		SYNC_NOTES_NO,
		build_entity_graph,
	)
	return render(request, 'rapport_api_tjeneste_systemoversikt_docs.html', {
		'request': request,
		'auth_info': AUTH_INFO,
		'base_url': BASE_URL,
		'endpoints': ENDPOINTS,
		'entity_graph': build_entity_graph(),
		'sync_guide': SYNC_GUIDE,
		'sync_notes_no': SYNC_NOTES_NO,
		'limitations': LIMITATIONS,
		'response_wrapper': RESPONSE_WRAPPER,
		'reference_pattern': REFERENCE_PATTERN,
	})


@login_required
def api_vulnapp_docs(request):
	from systemoversikt.api_vulnapp_docs import (
		AUTH_INFO,
		BASE_URL,
		ENDPOINTS,
		FLOW_NOTES_NO,
		LIMITATIONS,
		build_entity_graph,
	)
	return render(request, 'rapport_api_vulnapp_docs.html', {
		'request': request,
		'auth_info': AUTH_INFO,
		'base_url': BASE_URL,
		'endpoints': ENDPOINTS,
		'entity_graph': build_entity_graph(),
		'flow_notes_no': FLOW_NOTES_NO,
		'limitations': LIMITATIONS,
	})


LEVERANDORTILGANG_KJENTE_GRUPPER = [
		'DS-UVALEVTILGANG', 
		'DS-DRIFT_DML_', 
		'DS-DRIFT_SC2_',
		'DS-DRIFT_TREDJE'
		'DS-KEM_RPA', 
		'DS-LEV_TREDJEPARTSDRIFT', 
		'DS-DIG_FELL_DELT_TASK',
		'DS-DIG_APP_OS_',
		'TASK-OF2-Levtilgang', 
		'TASK-OF2-DRIFT',
		'TASK-OF2-GEN',
		'DS-HAVLEV',
	]

def leverandortilgang(request, valgt_gruppe=None):
	#Vise informasjon brukere som har leverandørtilgang
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if valgt_gruppe == None:

		leverandortilganger = Leverandortilgang.objects.all()
		connected_groups = []
		for lt in leverandortilganger:
			connected_groups.extend([getattr(adgruppe, 'distinguishedname') if adgruppe else "" for adgruppe in lt.adgrupper.all()])

		manglende_grupper = []

		for levtilganggruppe in LEVERANDORTILGANG_KJENTE_GRUPPER:
			dml_grupper = ADgroup.objects.filter(distinguishedname__icontains=levtilganggruppe).exclude(distinguishedname__in=[o for o in connected_groups])
			for g in dml_grupper:
				if g.common_name != None:
					if all(substring not in g.common_name for substring in ["_L0", "_L4", "_L1"]):
						manglende_grupper.append(g)

		manglende_grupper.sort(key=lambda g : g.common_name)

		virksomheter = virksomheter = Virksomhet.objects.filter(ordinar_virksomhet=True)

		return render(request, 'ad_leverandortilgang.html', {
			"request": request,
			"virksomheter": virksomheter,
			"required_permissions": required_permissions,
			"manglende_grupper": manglende_grupper,
			"leverandortilganger": leverandortilganger,
		})

	# må sjekkes, hva om ikke None?


def rapport_trusted_delegation(request):
	# 2026-07-07: Restrict to view_qualysvuln – same audience as other sikkerhetsanalytiker AD reports.
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	brukere = User.objects.filter(profile__trusted_for_delegation=True).order_by("username")

	for b in brukere:
		try:
			b.spns = json.loads(b.profile.service_principal_name)
			if not isinstance(b.spns, list):  # Ensure it's a list
				b.spns = [str(b.spns)]
		except Exception:
			b.spns = []


	return render(request, 'rapport_trusted_delegation.html', {
		"request": request,
		"required_permissions": required_permissions,
		"brukere": brukere,
		'integrasjonsstatus': _integrasjonsstatus("ad_users"),
	})

def alle_spn(request):
	#Vise informasjon brukere som er opprettet for å teste noe (og ikke har blitt slettet i etterkant)
	# 2026-07-07: Restrict to view_qualysvuln – same audience as other sikkerhetsanalytiker AD reports.
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	brukere = User.objects.filter(~Q(profile__service_principal_name=None)).order_by("username")

	for b in brukere:
		try:
			b.spns = json.loads(b.profile.service_principal_name)
			if not isinstance(b.spns, list):  # Ensure it's a list
				b.spns = [str(b.spns)]
		except Exception:
			b.spns = []

	return render(request, 'ad_alle_spn.html', {
		"request": request,
		"required_permissions": required_permissions,
		"brukere": brukere,
		'integrasjonsstatus': _integrasjonsstatus("ad_users"),
	})

def tbrukere(request):
	#Vise informasjon brukere som er opprettet for å teste noe (og ikke har blitt slettet i etterkant)
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	brukere = User.objects.filter(
			Q(username__istartswith="t-") |
			Q(username__istartswith="t_") |
			Q(username__icontains="_t2") |
			Q(username__icontains="aks20") |
			Q(username__icontains="-t20") |
			Q(username__icontains="copy") |
			Q(username__icontains="kopi") |
			Q(username__iendswith="-t") |
			Q(username__iendswith="_t")
		).exclude(
			Q(username="t-ok-wlan") |
			Q(username__istartswith="s-bfe-birk") |
			Q(username__istartswith="s-drift-euc") |
			Q(username__istartswith="svc-bfe") |
			Q(username="http-sektor-sikker-t") |
			Q(username__istartswith="bfe-birk")
		).order_by("username")

	return render(request, 'ad_tbrukere.html', {
		"request": request,
		"required_permissions": required_permissions,
		"brukere": brukere,
	})

def rapport_servicekontoer(request):
	#Vise informasjon om brukere som har drifttilgang
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	# 2026-06-21: select_related on profile relations – avoids N+1 on servicebrukere table.
	brukere = (
		User.objects.filter(profile__distinguishedname__icontains="OU=Servicekontoer,OU=OK")
		.filter(profile__accountdisable=False)
		.select_related("profile", "profile__org_unit", "profile__min_leder")
		.order_by("-profile__whenCreated")
	)
	brukere_count = brukere.count()

	return render(request, 'rapport_ad_servicekontoer.html', {
		"request": request,
		"required_permissions": required_permissions,
		"brukere": brukere,
		"brukere_count": brukere_count,
		'integrasjonsstatus': _integrasjonsstatus("ad_users"),
	})


def rapport_ad_testbrukere(request):
	#Vise informasjon testkontoer IDA oppretter
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	brukere = User.objects.filter(Q(profile__distinguishedname__icontains="OU=Testkontoer,OU=OK")).filter(profile__accountdisable=False)

	return render(request, 'rapport_ad_testbrukere.html', {
		"request": request,
		"required_permissions": required_permissions,
		"brukere": brukere,
		'integrasjonsstatus': _integrasjonsstatus("ad_users"),
	})




def rapport_ad_driftbrukere(request):
	#Vise informasjon brukere som har drifttilgang
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	brukere = User.objects.filter(Q(profile__distinguishedname__icontains="OU=DRIFT,OU=Eksterne brukere") | Q(profile__distinguishedname__icontains="OU=DRIFT,OU=Brukere")).filter(profile__accountdisable=False)

	return render(request, 'rapport_ad_drifttilgang.html', {
		"request": request,
		"required_permissions": required_permissions,
		"brukere": brukere,
		'integrasjonsstatus': _integrasjonsstatus("ad_drift_tilganger"),
	})


def rapport_ad_ukjente_brukere(request):
	# 2026-07-07: Restrict to view_qualysvuln – same audience as other sikkerhetsanalytiker AD reports.
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	brukere = excluded_users = User.objects.exclude(
			Q(profile__distinguishedname__icontains="OU=Brukere,OU=OK") |
			Q(profile__distinguishedname__icontains="OU=Eksterne brukere,OU=OK") |
			Q(profile__distinguishedname__icontains="OU=Ressurser,OU=OK") |
			Q(profile__distinguishedname__icontains="OU=Kontakt,OU=OK") |
			Q(profile__distinguishedname__icontains="CN=Monitoring Mailboxes") |
			Q(profile__distinguishedname__icontains="OU=Servicekontoer,OU=OK") |
			Q(profile__distinguishedname__icontains="OU=Testkontoer,OU=OK")
		).filter(is_active=True,profile__accountdisable=False)


	return render(request, 'rapport_ad_ukjente_brukere.html', {
		"request": request,
		"required_permissions": required_permissions,
		"brukere": brukere,
		'integrasjonsstatus': _integrasjonsstatus("ad_users"),
	})



def finn_roller():
	def adgruppe_oppslag(liste):
		oppslag = []
		for cn in liste:
			try:
				oppslag.append(ADgroup.objects.get(common_name=cn))
			except:
				#print("error adgruppe_oppslag() %s" % (cn))
				pass
		return oppslag

	serveradmins = [
		"GS-OpsRole-ErgoGroup-AdminAlleMemberServere",
		"GS-OpsRole-Ergogroup-ServerAdmins",
		"Task-OF2-ServerAdmin-AllMemberServers",
		"Role-OF2-Admin-Citrix Services",
		"DS-MemberServer-Admin-AlleManagementServere",
		"DS-MemberServer-Admin-AlleManagementServere",
		"DS-DRIFT_DRIFTSPERSONELL_SERVERMGMT_SERVERADMIN",
		"Role-OF2-AdminAlleMemberServere",
	]
	serveradmins = adgruppe_oppslag(serveradmins)

	domainadmins = [
		"Domain Admins",
		"Enterprise Admins",
		"Role-Domain-Admins-UVA",
		"On-Prem Domain Admins (009378fe-ecdf-4f49-bd65-d82411703915)",
	]
	domainadmins = adgruppe_oppslag(domainadmins)

	prkadmin = [
		"DS-GKAT_BRGR_SYSADM",
		"DS-GKAT_ADMSENTRALESKJEMA_ALLE",
		"DS-GKAT_ADMSENTRALESKJEMA_KOKS",
		"DS-GKAT_IMPSKJEMA_TIGIMP",
		"DS-GKAT_IMPSKJEMA_TSIMP",
		"DS-GKAT_MODULER_GLOBAL_ADMINISTRASJON",
		"DS-GKAT_DSGLOKALESKJEMA_ALLE",
		"DS-GKAT_DSGLOKALESKJEMA_INFOCARE",
		"DS-GKAT_DSGLOKALESKJEMA_OPPRETTE",
		"DS-GKAT_DSGSENTRALESKJEMA_ALLE",
		"DS-GKAT_DSGSENTRALESKJEMA_OPPRETTE",
		"DS-GKAT_ADMLOKALESKJEMA_ALLE",
		"DS-GKAT_ADMLOKALESKJEMA_APPLIKASJON",
	]
	prkadmin = adgruppe_oppslag(prkadmin)

	sqladmins = [
		"GS-UKE-MSSQL-DBA",
		"DS-OF2-SQL-SYSADMIN",
		"DS-DRIFT_DRIFTSPERSONELL_DATABASE_SQL",
		"GS-Role-MSSQL-DBA",
		"GS-UKE-MSSQL-DBA",
		"DS-Role-MSSQL-DBA",
		"DS-DRIFT_DRIFTSPERSONELL_DATABASE_ORACLE",
		"DS-OF2-TASK-SQLCluster",
	]
	sqladmins = adgruppe_oppslag(sqladmins)

	citrixadmin = [
		"Task-OF2-Admin-Citrix XenApp",
		"DS-DRIFT_DRIFTSPERSONELL_REMOTE_CITRIXDIRECTOR",
		"DS-DRIFT_DRIFTSPERSONELL_CITRIX_APPV_ADMIN",
		"DS-DRIFT_DRIFTSPERSONELL_CITRIX_CITRIX_NETSCALER_ADM",
		"DS-DRIFT_DRIFTSPERSONELL_CITRIX_ADMINISTRATOR",
		"DS-DRIFT_DRIFTSPERSONELL_CITRIX_DRIFT",
	]
	citrixadmin = adgruppe_oppslag(citrixadmin)

	sccmadmin = [
		"Task-SCCM-Application-Administrator",
		"Task-SCCM-Application-Author",
		"Task-SCCM-Application-Deployment-Manager",
		"Task-SCCM-Asset-Manager",
		"Task-SCCM-Compliance-Settings-Manager",
		"Task-SCCM-Endpoint-Protection-Manager",
		"Task-SCCM-Operations-Administrator",
		"Task-SCCM-OSD-Manager",
		"Task-SCCM-Infrastructure-Administrator",
		"Task-SCCM-Remote-Tools-Operator",
		"Task-SCCM-Security-Administrator",
		"Task-SCCM-Software-Update-Manager",
		"Task-SCCM-Full-Administrator",
		"Task-SCCM-SRV-Admin",
		"Task-SCCM-ClientInstall_SikkerSone_MP",
		"Task-SCCM-ClientInstall_InternSone_MP",
		"Task-SCCM-ClientInstall",
		"TASK-SCCM-CLIENT-INSTALL-EXCLUDE",
		"Task-SCCM-RemoteDesktop",
		"Task-SCCM-SQL-Admin",
		"DS-DRIFT_DRIFTSPERSONELL_SCCM_SCCMFULLADM",
		"DA-SCCM-SQL-SysAdmin-F",
	]
	sccmadmin = adgruppe_oppslag(sccmadmin)

	levtilgang = [
		"DS-DRIFT_DML_LEVTILGANG_LEVTILGANGSS",
		"DS-DRIFT_DML_LEVTILGANG_LEVTILGANG",
		"DS-DRIFT_DML_DRIFTTILGANG_DRIFTTILGANGIS",
		"DS-DRIFT_DML_DRIFTTILGANG_DRIFTTILGANGSS",
	]
	levtilgang = adgruppe_oppslag(levtilgang)

	dcadmin = [
		"DS-DRIFT_DRIFTSPERSONELL_SERVERMGMT_ADMINDC",
	]
	dcadmin = adgruppe_oppslag(dcadmin)

	exchangeadmin = [
		"DS-DRIFT_DRIFTSPERSONELL_MAIL_EXH_FULL_ADMINISTRATOR",
	]
	exchangeadmin = adgruppe_oppslag(exchangeadmin)

	filsensitivt = [
		"DS-DRIFT_DRIFTSPERSONELL_ACCESSMGMT_OVERGREPSMOTTAKET",
	]
	filsensitivt = adgruppe_oppslag(filsensitivt)

	"""
	for b in brukere:
		b.serveradmin = set(serveradmins).intersection(set(b.profile.adgrupper.all()))
		b.domainadmin = set(domainadmins).intersection(set(b.profile.adgrupper.all()))
		b.prkadmin = set(prkadmin).intersection(set(b.profile.adgrupper.all()))
		b.sqladmin = set(sqladmins).intersection(set(b.profile.adgrupper.all()))
		b.citrixadmin = set(citrixadmin).intersection(set(b.profile.adgrupper.all()))
		b.sccmadmin = set(sccmadmin).intersection(set(b.profile.adgrupper.all()))
		b.levtilgang = set(levtilgang).intersection(set(b.profile.adgrupper.all()))
		b.dcadmin = set(dcadmin).intersection(set(b.profile.adgrupper.all()))
		b.exchangeadmin = set(exchangeadmin).intersection(set(b.profile.adgrupper.all()))
		b.filsensitivt = set(filsensitivt).intersection(set(b.profile.adgrupper.all()))
	"""



def prk_userlookup(request):
	#Vise informasjon om vilkårlige brukere
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if request.POST:
		query = request.POST.get('query', '').strip()
		users = re.findall(r"([^,;\t\s\n\r]+)", query)
		users_result = []
		for item in users:
			try:
				u = User.objects.get(username__iexact=item)
				users_result.append({
					"username": u.username,
					"organization": u.profile.org_tilhorighet,
					"accountdisable": u.profile.accountdisable,
					"name": u.profile.displayName,
					})
			except:
				messages.warning(request, 'Fant ikke info på "%s"' % (item))
				continue

	else:
		users_result = []
		query = ""

	return render(request, 'prk_userlookup.html', {
		"request": request,
		"required_permissions": required_permissions,
		"query": query,
		"users": users_result,
	})



def systemer_virksomhet_ansvarlig_for(request, pk=None):

	if pk == None:
		try:
			brukers_virksomhet = request.user.profile.virksomhet_forkortelse
			pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
			return redirect('systemer_virksomhet_ansvarlig_for', pk)
		except:
			messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
			return redirect('alle_virksomheter')

	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	systemer_ansvarlig_for = System.objects.filter(~Q(ibruk=False)).filter(Q(systemeier=pk) | Q(systemforvalter=pk)).order_by(Lower('systemnavn'))

	unike_ansvarlige_eiere = set()
	unike_ansvarlige_forvaltere = set()
	for system in systemer_ansvarlig_for:
		for ansvarlig in system.systemforvalter_kontaktpersoner_referanse.all():
			unike_ansvarlige_forvaltere.add(ansvarlig)
		for ansvarlig in system.systemeier_kontaktpersoner_referanse.all():
			unike_ansvarlige_eiere.add(ansvarlig)

	return render(request, 'virksomhet_systemer_ansvarfor.html', {
		"request": request,
		"required_permissions": required_permissions,
		'virksomhet': virksomhet,
		'systemer_ansvarlig_for': systemer_ansvarlig_for,
		'unike_ansvarlige_eiere': list(unike_ansvarlige_eiere),
		'unike_ansvarlige_forvaltere': list(unike_ansvarlige_forvaltere),
	})



def virksomhet_forvalter_isk(request, pk=None):

	if pk == None:
		try:
			brukers_virksomhet = request.user.profile.virksomhet_forkortelse
			pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
			return redirect('virksomhet_forvalter_isk', pk)
		except:
			messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
			return redirect('alle_virksomheter')


	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	systemer_ansvarlig_for = System.objects.filter(~Q(ibruk=False)).filter(Q(systemeier=pk) | Q(systemforvalter=pk)).order_by(Lower('systemnavn'))

	return render(request, 'virksomhet_forvalter_isk.html', {
		"request": request,
		"required_permissions": required_permissions,
		'virksomhet': virksomhet,
		'systemer_ansvarlig_for': systemer_ansvarlig_for,
	})



def systemer_virksomhet_ansvarlig_for_fip(request, pk):
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	uke = Virksomhet.objects.get(virksomhetsforkortelse="UKE")
	systemer_ansvarlig_for = System.objects.filter(~Q(ibruk=False)).filter(Q(systemeier=pk) | Q(systemforvalter=pk)).filter(driftsmodell_foreignkey__ansvarlig_virksomhet=uke).order_by(Lower('systemnavn'))

	unike_ansvarlige_eiere = set()
	unike_ansvarlige_forvaltere = set()
	for system in systemer_ansvarlig_for:
		for ansvarlig in system.systemforvalter_kontaktpersoner_referanse.all():
			unike_ansvarlige_forvaltere.add(ansvarlig)
		for ansvarlig in system.systemeier_kontaktpersoner_referanse.all():
			unike_ansvarlige_eiere.add(ansvarlig)

	return render(request, 'virksomhet_systemer_ansvarfor.html', {
		"request": request,
		"required_permissions": required_permissions,
		'virksomhet': virksomhet,
		'systemer_ansvarlig_for': systemer_ansvarlig_for,
		'unike_ansvarlige_eiere': list(unike_ansvarlige_eiere),
		'unike_ansvarlige_forvaltere': list(unike_ansvarlige_forvaltere),
	})


def _forvalter_systemer_queryset(pk, kilde="alle"):
	# 2026-06-21: Shared queryset for virksomhet forvalter-system figur charts (seksjon + plattform).
	base_qs = (System.objects.filter(systemforvalter=pk)
					.filter(~Q(livslop_status__in=[6,7]))
					.order_by('systemnavn'))

	if kilde == "tjenester":
		return base_qs.exclude(
			Q(systemtyper__er_infrastruktur=True) | Q(systemtyper__er_integrasjon=True)
		)
	if kilde == "infrastruktur":
		return base_qs.filter(
			Q(systemtyper__er_infrastruktur=True) | Q(systemtyper__er_integrasjon=True)
		)
	return base_qs


def _collect_system_graph_data(pk, kilde="alle"):
	# 2026-06-08: Combined tjenester+infrastruktur chart; 🛠️ prefix + light red marks infrastructure on kilde=alle.
	infra_chart_color = SYSTEM_COLORS['infrastruktur_chart']
	nodes = []
	parents = []

	def systemnavn_forkortet(system, mark_infrastruktur=False):
		prefix = '🛠️ ' if mark_infrastruktur else ''
		maximum = 20
		navn = system.systemnavn
		if len(navn) > maximum:
			navn = navn[:maximum]
		return prefix + navn

	def system_seksjon(system):
		if system.systemforvalter_avdeling_referanse:
			parents.append(system.systemforvalter_avdeling_referanse)
			return f"org_{system.systemforvalter_avdeling_referanse.pk}"

		try:
			forste_forvalters_ou = system.systemforvalter_kontaktpersoner_referanse.all()[0].brukernavn.profile.org_unit
			parents.append(forste_forvalters_ou)
			return forste_forvalters_ou.ou
		except:
			pass

		parents.append('Ukjent')
		return 'Ukjent'

	relevante_systemer = _forvalter_systemer_queryset(pk, kilde)

	for system in relevante_systemer:
		if system.er_ibruk():
			mark_infrastruktur = kilde == "alle" and (system.er_infrastruktur() or system.er_integrasjon())
			nodes.append({
				'data': {
					'id': system.pk,
					'name': systemnavn_forkortet(system, mark_infrastruktur=mark_infrastruktur),
					'parent': system_seksjon(system),
					'shape': 'rectangle',
					'color': infra_chart_color if mark_infrastruktur else system.color(),
					'href': f'/systemer/detaljer/{system.pk}/',
				}
			})

	all_parents = list(set(parents))
	work_queue = list(set(parents))
	while work_queue:
		item = work_queue.pop()
		if item == 'Ukjent' or item == None:
			continue
		if item.direkte_mor != None:
			if item.direkte_mor not in all_parents:
				#print(f"La til {item.direkte_mor}")
				work_queue.append(item.direkte_mor)
				all_parents.append(item.direkte_mor)
			else:
				#print(f"{item.direkte_mor} var allerede lagt til")
				pass

	for p in all_parents:
		if p == 'Ukjent':
			nodes.append({'data': {'id': p, 'name': p, 'color': 'white', 'shape': 'rectangle',}},)
			continue
		if p == None:
			continue
		if p.direkte_mor != None:
			nodes.append({'data': {'id': f"org_{p.pk}", 'name': p.ou, 'color': 'white', 'shape': 'rectangle', 'parent': f"org_{p.direkte_mor.pk}"}},)
			#nodes.append({'data': {'id': f"org_{p.direkte_mor.pk}", 'name': p.direkte_mor.ou, 'color': 'white',}},)
		else:
			nodes.append({'data': {'id': f"org_{p.pk}", 'name': p.ou, 'color': 'white', 'shape': 'rectangle',}},)

	return nodes


def _collect_system_graph_data_by_plattform(pk, kilde="alle"):
	# 2026-06-21: Forvalter-systemer grouped by driftsplattform – no dependency edges.
	infra_chart_color = SYSTEM_COLORS['infrastruktur_chart']
	nodes = []
	observerte_driftsmodeller = set()
	har_ukjent_plattform = False
	drift_gruppe_color = "#F1F9FF"

	def systemnavn_forkortet(system, mark_infrastruktur=False):
		prefix = '🛠️ ' if mark_infrastruktur else ''
		maximum = 20
		navn = system.systemnavn
		if len(navn) > maximum:
			navn = navn[:maximum]
		return prefix + navn

	def system_plattform_parent(system):
		nonlocal har_ukjent_plattform
		if system.driftsmodell_foreignkey is not None:
			observerte_driftsmodeller.add(system.driftsmodell_foreignkey)
			return f"drift_{system.driftsmodell_foreignkey.pk}"
		har_ukjent_plattform = True
		return "Ukjent"

	relevante_systemer = _forvalter_systemer_queryset(pk, kilde)

	for system in relevante_systemer:
		if system.er_ibruk():
			mark_infrastruktur = kilde == "alle" and (system.er_infrastruktur() or system.er_integrasjon())
			nodes.append({
				'data': {
					'id': system.pk,
					'name': systemnavn_forkortet(system, mark_infrastruktur=mark_infrastruktur),
					'parent': system_plattform_parent(system),
					'shape': 'rectangle',
					'color': infra_chart_color if mark_infrastruktur else system.color(),
					'href': f'/systemer/detaljer/{system.pk}/',
				}
			})

	for driftsmodell in observerte_driftsmodeller:
		if driftsmodell is not None:
			if driftsmodell.overordnet_plattform:
				nodes.append({'data': {
					'id': f"drift_{driftsmodell.pk}",
					'name': driftsmodell.navn,
					'parent': f"drift_{driftsmodell.overordnet_plattform.pk}",
					'shape': 'rectangle',
					'color': drift_gruppe_color,
				}})
				nodes.append({'data': {
					'id': f"drift_{driftsmodell.overordnet_plattform.pk}",
					'name': driftsmodell.overordnet_plattform.navn,
					'shape': 'rectangle',
					'color': drift_gruppe_color,
				}})
			else:
				nodes.append({'data': {
					'id': f"drift_{driftsmodell.pk}",
					'name': driftsmodell.navn,
					'shape': 'rectangle',
					'color': drift_gruppe_color,
				}})

	if har_ukjent_plattform:
		nodes.append({'data': {'id': 'Ukjent', 'name': 'Ukjent', 'color': 'white', 'shape': 'rectangle'}})

	return nodes


def _collect_systembruk_graph_data_by_forvalter(pk):
	# 2026-06-21: Active systembruk grouped flat by organisatorisk systemforvalter.
	nodes = []
	forvaltere = set()

	def systemnavn_forkortet(system):
		maximum = 20
		navn = system.systemnavn
		if len(navn) > maximum:
			navn = navn[:maximum]
		return navn

	all_systembruk = (SystemBruk.objects.filter(brukergruppe=pk, ibruk=True)
		.exclude(system__livslop_status__in=[6, 7])
		.select_related('system', 'system__systemforvalter', 'system__driftsmodell_foreignkey')
		.order_by(Lower('system__systemnavn')))

	for bruk in all_systembruk:
		system = bruk.system
		forvalter = system.systemforvalter
		forvaltere.add(forvalter)
		nodes.append({
			'data': {
				'id': system.pk,
				'name': systemnavn_forkortet(system),
				'parent': f"vir_{forvalter.pk}",
				'shape': 'rectangle',
				'color': system.color(),
				'href': f'/systemer/detaljer/{system.pk}/',
			}
		})

	for forvalter in forvaltere:
		nodes.append({
			'data': {
				'id': f"vir_{forvalter.pk}",
				'name': forvalter.virksomhetsnavn,
				'color': 'white',
				'shape': 'rectangle',
			}
		})

	return nodes


def virksomhet_figur_system_seksjon(request, pk):
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	kilde = request.GET.get('kilde', 'alle')
	from systemoversikt.models import SYSTEM_COLORS

	return render(request, 'virksomhet_figur_system_seksjon.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'nodes': _collect_system_graph_data(pk, kilde=kilde),
		'system_colors': SYSTEM_COLORS,
		'kilde': kilde,
	})


def virksomhet_figur_system_plattform(request, pk):
	# 2026-06-21: Dedicated plattform grouping chart for forvalter-systemer.
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	kilde = request.GET.get('kilde', 'alle')
	from systemoversikt.models import SYSTEM_COLORS

	return render(request, 'virksomhet_figur_system_plattform.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'nodes': _collect_system_graph_data_by_plattform(pk, kilde=kilde),
		'system_colors': SYSTEM_COLORS,
		'kilde': kilde,
	})


def virksomhet_figur_systembruk_forvalter(request, pk):
	# 2026-06-21: Active systembruk grouped by organisatorisk systemforvalter.
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	from systemoversikt.models import SYSTEM_COLORS

	return render(request, 'virksomhet_figur_systembruk_forvalter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'nodes': _collect_systembruk_graph_data_by_forvalter(pk),
		'system_colors': SYSTEM_COLORS,
	})


def _virksomhet_graph_layout_context(virksomhet):
	try:
		layout = GraphLayout.objects.get(virksomhet=virksomhet)
		return {
			"positions": layout.positions_json,
			"zoom": layout.zoom,
			"pan": {"x": layout.pan_x, "y": layout.pan_y},
			"locked": layout.locked,
		}
	except GraphLayout.DoesNotExist:
		return None


def virksomhet_figur_system_avhengigheter(request, pk):
	# 2026-06-08: Dedicated dependency graph page – keeps /virksomhet/<pk>/ fast to load.
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	avhengigheter_graf_ny = generer_graf_virksomhet(pk)
	saved_layout = _virksomhet_graph_layout_context(virksomhet)

	from django.middleware.csrf import get_token
	csrf = get_token(request)

	save_rettigheter = True if any(map(request.user.has_perm, REQUIRED_PERMISSIONS_SAVE_GRAPH_VIRKSOMHET)) else False

	return render(request, 'virksomhet_figur_system_avhengigheter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'avhengigheter_graf_ny': avhengigheter_graf_ny,
		'saved_layout_json': saved_layout,
		'csrf_js_token': csrf,
		'save_rettigheter': save_rettigheter,
	})



def generer_graf_virksomhet(virksomhet_pk):
	avhengigheter_graf = {"nodes": [], "edges": []}
	observerte_driftsmodeller = set()
	first_round = True
	follow_count = 0
	observerte_systemer = set()
	behandlede_systemer = set()
	aktivt_nivaa_systemer = set()  # aktiv runde
	neste_nivaa = set() # neste runde (nye ting vi ser i aktiv runde)

	def parent(system):
		if system.driftsmodell_foreignkey is not None:
			return f"drift_{system.driftsmodell_foreignkey.pk}"
		else:
			return "Ukjent"

	def systemfarge(self):
		if self.er_infrastruktur():
			return "gray"
		else:
			return "#dca85a"

	virksomhetens_systemer = (System.objects.filter(systemforvalter=virksomhet_pk)
									.filter(~Q(livslop_status__in=[6,7]))
								)

	#print(virksomhetens_systemer)
	for s in virksomhetens_systemer:
		aktivt_nivaa_systemer.add(s)
		observerte_systemer.add(s)

	def avhengighetsrunde(aktivt_nivaa_systemer, neste_nivaa):
		for aktuelt_system in aktivt_nivaa_systemer:

			avhengigheter_graf["nodes"].append({"data": {
						"id": aktuelt_system.pk,
						"parent": parent(aktuelt_system),
						"name": aktuelt_system.systemnavn,
						"shape": "ellipse",
						"color": "#C63D3D",
						"href": reverse('systemdetaljer', args=[aktuelt_system.pk]) 
					}},)
			observerte_driftsmodeller.add(aktuelt_system.driftsmodell_foreignkey)

			for s in aktuelt_system.system_integration_source.all():
				integrasjon = s
				s = s.destination_system
				if s not in observerte_systemer:
					neste_nivaa.add(s)
					observerte_systemer.add(s)
				if s not in behandlede_systemer:
					avhengigheter_graf["nodes"].append({"data": { 
							"id": s.pk, 
							"parent": parent(s), 
							"name": s.systemnavn, 
							"shape": "ellipse", 
							"color": integrasjon.color(), 
							"href": reverse('systemdetaljer', args=[s.pk]) 
						}},)
					avhengigheter_graf["edges"].append({"data": { 
							"source": aktuelt_system.pk, 
							"target": s.pk, 
							"linewidth": 2,
							"shape": "ellipse", 
							"curve-style": 'bezier', 
							"linecolor": integrasjon.color(), 
							"linestyle": "solid"
						}},)
					observerte_driftsmodeller.add(s.driftsmodell_foreignkey)

			if first_round:
				for s in aktuelt_system.system_integration_destination.all():
					integrasjon = s
					s = s.source_system
					if s not in observerte_systemer:
						neste_nivaa.add(s)
						observerte_systemer.add(s)
					if s not in behandlede_systemer:
						avhengigheter_graf["nodes"].append({"data": { 
								"id": s.pk, 
								"parent": parent(s), 
								"name": s.systemnavn, 
								"shape": "ellipse", 
								"color": integrasjon.color(), 
								"href": reverse('systemdetaljer', args=[s.pk]) 
							}},)
						avhengigheter_graf["edges"].append({"data": { 
								"source": s.pk, 
								"target": aktuelt_system.pk, 
								"linewidth": 1, 
								"curve-style": 'bezier', 
								"linecolor": integrasjon.color(), 
								"linestyle": "dashed",
								"shape": "ellipse", 
							}},)
						observerte_driftsmodeller.add(s.driftsmodell_foreignkey)

			behandlede_systemer.add(aktuelt_system)

		# legger neste nivås systemer inn i gjendende nivå, klar for neste runde
		aktivt_nivaa_systemer = neste_nivaa
		neste_nivaa = set()

		return aktivt_nivaa_systemer, neste_nivaa

	aktivt_nivaa_systemer, neste_nivaa = avhengighetsrunde(aktivt_nivaa_systemer, neste_nivaa)
	first_round = False
	while follow_count > 0 and aktivt_nivaa_systemer: # det må være noen systemer å gå igjennom..
		aktivt_nivaa_systemer, neste_nivaa = avhengighetsrunde(aktivt_nivaa_systemer, neste_nivaa)
		follow_count-=1

	# legge til alle driftsmodeller som ble funnet (color kreves av cytoscape data()-mapping på alle noder)
	drift_gruppe_color = "#F1F9FF"
	for driftsmodell in observerte_driftsmodeller:
		if driftsmodell is not None:
			if driftsmodell.overordnet_plattform:
				avhengigheter_graf["nodes"].append({"data": { 
						"id": f"drift_{driftsmodell.pk}", 
						"name": driftsmodell.navn, 
						"parent": f"drift_{driftsmodell.overordnet_plattform.pk}",
						"shape": "ellipse", 
						"color": drift_gruppe_color,
					}},)
				avhengigheter_graf["nodes"].append({"data": { 
						"id": f"drift_{driftsmodell.overordnet_plattform.pk}", 
						"name": driftsmodell.overordnet_plattform.navn,
						"shape": "ellipse", 
						"color": drift_gruppe_color,
					}},)
			else:
				avhengigheter_graf["nodes"].append({"data": { 
						"id": f"drift_{driftsmodell.pk}", 
						"name": driftsmodell.navn,
						"shape": "ellipse", 
						"color": drift_gruppe_color,
					}},)

	return avhengigheter_graf


REQUIRED_PERMISSIONS_SAVE_GRAPH_VIRKSOMHET = ['systemoversikt.change_virksomhet']

# 2026-06-08: Editable sentrale roller on virksomhet detail page (field name, display label).
SENTRALE_ROLLER_EDITABLE = (
	('arkitekturkontakter', 'Aktitekturkontakter'),
	('ikt_kontakt', 'IKT-kontakter'),
	('personvernkoordinator', 'Personvernkoordinator'),
	('informasjonssikkerhetskoordinator', 'Informasjonvernkoordinator'),
	('varslingsmottak_sikkerhet_ref', 'Sikkerhetsrelaterte varsler sendes til'),
	('uke_kam_referanse', 'Kundekontakt i DIG'),
	('autoriserte_bestillere_tjenester', 'Infotorg autorisert bestiller'),
	('ks_fiks_admin_ref', 'Folkeregisteradministrator i KS Fiks'),
	('autoriserte_bestillere_tjenester_uke', 'Autorisert for bestilling av tjenester fra DIG'),
)
SENTRALE_ROLLER_FIELD_NAMES = frozenset(field for field, _label in SENTRALE_ROLLER_EDITABLE)


def _ansvarlig_display_list(ansvarlig):
	return {
		'id': ansvarlig.pk,
		'label': str(ansvarlig),
		'bruker_pk': ansvarlig.brukernavn_id,
		'url': reverse('bruker_detaljer', kwargs={'pk': ansvarlig.brukernavn_id}),
		'deaktivert': bool(getattr(ansvarlig.brukernavn.profile, 'accountdisable', False)),
	}


def _sentrale_roller_redigerbare(virksomhet):
	return [{
		'field': field,
		'label': label,
		'ansvarlige': [_ansvarlig_display_list(a) for a in getattr(virksomhet, field).all()],
	} for field, label in SENTRALE_ROLLER_EDITABLE]


SENTRALE_ROLLER_DIG_KAM_FIELD = 'uke_kam_referanse'
DIG_KUNDEKONTAKT_VIRKSOMHET_FORKORTELSE = 'DIG'


def _dig_kundekontakt_virksomhet():
	try:
		return Virksomhet.objects.get(virksomhetsforkortelse=DIG_KUNDEKONTAKT_VIRKSOMHET_FORKORTELSE)
	except Virksomhet.DoesNotExist:
		return None


def _sentrale_roller_ansvarlig_virksomhet(field, edited_virksomhet):
	# 2026-06-08: Kundekontakt i DIG uses DIG staff only; other roles use the edited virksomhet.
	if field == SENTRALE_ROLLER_DIG_KAM_FIELD:
		return _dig_kundekontakt_virksomhet()
	return edited_virksomhet


def _ansvarlig_q_for_virksomhet(virksomhet):
	if virksomhet is None:
		return Q(pk__in=[])
	return Q(brukernavn__profile__virksomhet=virksomhet)


def _virksomhet_ansvarlig_sok_queryset(q, scope_virksomhet):
	from functools import reduce
	from operator import or_
	if scope_virksomhet is None:
		return Ansvarlig.objects.none()
	terms = q.split()
	if not terms:
		return Ansvarlig.objects.none()
	field_queries = []
	for term in terms:
		field_queries.append(
			Q(brukernavn__username__icontains=term)
			| Q(brukernavn__first_name__icontains=term)
			| Q(brukernavn__last_name__icontains=term)
			| Q(brukernavn__email__icontains=term)
			| Q(brukernavn__profile__displayName__icontains=term)
		)
	query = reduce(or_, field_queries)
	return (
		Ansvarlig.objects.filter(query)
		.filter(_ansvarlig_q_for_virksomhet(scope_virksomhet))
		.select_related('brukernavn', 'brukernavn__profile')
		.distinct()
		.order_by('brukernavn__first_name', 'brukernavn__last_name')[:15]
	)


def _hrorg_enheter_tre(virksomhet_pk, max_child_depth=3):
	"""Nested tree of level-4 units (avdelinger) and child org units below."""
	alle_enheter = list(HRorg.objects.filter(virksomhet_mor=virksomhet_pk).order_by('ou'))
	children_by_parent = {}
	for enhet in alle_enheter:
		children_by_parent.setdefault(enhet.direkte_mor_id, []).append(enhet)

	def build_node(enhet, remaining_depth):
		return {
			'enhet': enhet,
			'children': [
				build_node(child, remaining_depth - 1)
				for child in children_by_parent.get(enhet.pk, [])
			] if remaining_depth > 0 else [],
		}

	return [build_node(enhet, max_child_depth) for enhet in alle_enheter if enhet.level == 4]


def virksomhet(request, pk):
	#Vise detaljer om en valgt virksomhet
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	ansvarlig_qs = Ansvarlig.objects.select_related('brukernavn', 'brukernavn__profile')
	virksomhet = Virksomhet.objects.prefetch_related(*[
		Prefetch(field, queryset=ansvarlig_qs)
		for field in SENTRALE_ROLLER_FIELD_NAMES
	]).get(pk=pk)
	#antall_brukere = User.objects.filter(profile__virksomhet=pk).filter(profile__ekstern_ressurs=False).filter(is_active=True).count()
	#antall_eksterne_brukere = User.objects.filter(profile__virksomhet=pk).filter(profile__ekstern_ressurs=True).filter(is_active=True).count()

	systemforvalter_ikke_kvalitetssikret = System.objects.filter(systemforvalter=pk).filter(informasjon_kvalitetssikret=False).count()
	systemeier_ikke_kvalitetssikret = System.objects.filter(systemeier=pk).filter(informasjon_kvalitetssikret=False).count()

	deaktiverte_brukere = Ansvarlig.objects.filter(brukernavn__profile__virksomhet=pk).filter(brukernavn__profile__accountdisable=True).count()

	ant_systemer_bruk = SystemBruk.objects.filter(brukergruppe=pk).count()
	ant_systemer_eier = System.objects.filter(systemeier=pk).count()
	ant_systemer_forvalter = System.objects.filter(systemforvalter=pk).count()
	# 2026-06-08: Avdelinger tree with three child levels for virksomhet_detaljer.
	enheter_tre = _hrorg_enheter_tre(virksomhet.pk)
	enheter_tre_mid = (len(enheter_tre) + 1) // 2
	enheter_tre_kol1 = enheter_tre[:enheter_tre_mid]
	enheter_tre_kol2 = enheter_tre[enheter_tre_mid:]

	# 2026-06-08: Group systems per kritisk funksjon for rowspan in virksomhet_detaljer table.
	kritiske_funksjoner = KritiskFunksjon.objects.filter(
		funksjoner__systemer__systemforvalter=pk,
	).distinct().prefetch_related('funksjoner__systemer__kritisk_kapabilitet')
	kritiske_funksjoner_rader = []
	for funksjon in kritiske_funksjoner:
		systemer = [
			system for system in funksjon.systemer()
			if system.systemforvalter_id == virksomhet.pk
		]
		if systemer:
			kritiske_funksjoner_rader.append({
				'funksjon': funksjon,
				'systemer': systemer,
			})

	systemer_drifter = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=pk).filter(~Q(ibruk=False)).count()

	sentrale_roller_redigerbare = _sentrale_roller_redigerbare(virksomhet)

	return render(request, 'virksomhet_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'can_change_virksomhet': user_can_change_virksomhet(request.user, virksomhet),
		'sentrale_roller_redigerbare': sentrale_roller_redigerbare,
		'sentrale_roller_redigerbare_json': json.dumps(sentrale_roller_redigerbare),
		'virksomhet': virksomhet,
		#'antall_brukere': antall_brukere,
		#'antall_eksterne_brukere': antall_eksterne_brukere,
		'systemforvalter_ikke_kvalitetssikret': systemforvalter_ikke_kvalitetssikret,
		'systemeier_ikke_kvalitetssikret': systemeier_ikke_kvalitetssikret,
		'deaktiverte_brukere': deaktiverte_brukere,
		'enheter_tre_kol1': enheter_tre_kol1,
		'enheter_tre_kol2': enheter_tre_kol2,
		'ant_systemer_bruk': ant_systemer_bruk,
		'ant_systemer_eier': ant_systemer_eier,
		'ant_systemer_forvalter': ant_systemer_forvalter,
		'systemer_drifter': systemer_drifter,
		'kritiske_funksjoner_rader': kritiske_funksjoner_rader,
		"virksomhet": virksomhet,
	})


def virksomhet_ansvarlig_sok(request, pk):
	# 2026-06-08: JSON search for ansvarlige when editing sentrale roller inline.
	virksomhet = get_object_or_404(Virksomhet, pk=pk)
	if not user_can_change_virksomhet(request.user, virksomhet):
		return JsonResponse({'error': 'forbidden'}, status=403)

	q = request.GET.get('q', '').strip()
	if len(q) < 2:
		return JsonResponse({'results': []})

	role_field = request.GET.get('exclude_field', '').strip()
	exclude_ids = set()
	if role_field in SENTRALE_ROLLER_FIELD_NAMES:
		exclude_ids.update(getattr(virksomhet, role_field).values_list('pk', flat=True))
		scope_virksomhet = _sentrale_roller_ansvarlig_virksomhet(role_field, virksomhet)
	else:
		scope_virksomhet = virksomhet
	for raw in request.GET.get('exclude_ids', '').split(','):
		raw = raw.strip()
		if raw.isdigit():
			exclude_ids.add(int(raw))

	results = []
	for ansvarlig in _virksomhet_ansvarlig_sok_queryset(q, scope_virksomhet):
		if ansvarlig.pk not in exclude_ids:
			results.append(_ansvarlig_display_list(ansvarlig))

	user_terms = q.split()
	if user_terms and scope_virksomhet is not None:
		from functools import reduce
		from operator import or_
		user_parts = []
		for term in user_terms:
			user_parts.append(
				Q(username__icontains=term)
				| Q(first_name__icontains=term)
				| Q(last_name__icontains=term)
				| Q(email__icontains=term)
				| Q(profile__displayName__icontains=term)
			)
		user_q = reduce(or_, user_parts)
		users = (
			User.objects.filter(user_q)
			.filter(profile__virksomhet=scope_virksomhet)
			.filter(ansvarlig_brukernavn__isnull=True)
			.select_related('profile')
			.distinct()
			.order_by('first_name', 'last_name')[:5]
		)
		for user in users:
			results.append({
				'id': None,
				'user_pk': user.pk,
				'label': str(user),
				'create': True,
			})

	return JsonResponse({'results': results})


@require_POST
def virksomhet_ansvarlig_opprett(request, pk):
	# 2026-06-08: Create Ansvarlig from User when adding via inline role search.
	virksomhet = get_object_or_404(Virksomhet, pk=pk)
	if not user_can_change_virksomhet(request.user, virksomhet):
		return JsonResponse({'error': 'forbidden'}, status=403)
	if not request.user.has_perm('systemoversikt.add_ansvarlig'):
		return JsonResponse({'error': 'forbidden'}, status=403)

	try:
		data = json.loads(request.body.decode('utf-8'))
	except json.JSONDecodeError:
		return JsonResponse({'error': 'invalid_json'}, status=400)

	user_pk = data.get('user_pk')
	field = data.get('field', '').strip()
	if not user_pk:
		return JsonResponse({'error': 'missing_user'}, status=400)
	if field not in SENTRALE_ROLLER_FIELD_NAMES:
		return JsonResponse({'error': 'invalid_field'}, status=400)

	scope_virksomhet = _sentrale_roller_ansvarlig_virksomhet(field, virksomhet)
	user = get_object_or_404(User, pk=user_pk)
	if scope_virksomhet is None or getattr(user.profile, 'virksomhet_id', None) != scope_virksomhet.pk:
		return JsonResponse({'error': 'wrong_virksomhet'}, status=400)
	ansvarlig, _created = Ansvarlig.objects.get_or_create(brukernavn=user)
	return JsonResponse(_ansvarlig_display_list(ansvarlig))


@require_POST
def virksomhet_lagre_roller(request, pk):
	# 2026-06-08: Save sentrale roller from inline editor on virksomhet detail page.
	virksomhet = get_object_or_404(Virksomhet, pk=pk)
	if not user_can_change_virksomhet(request.user, virksomhet):
		return JsonResponse({'error': 'forbidden'}, status=403)

	try:
		data = json.loads(request.body.decode('utf-8'))
	except json.JSONDecodeError:
		return JsonResponse({'error': 'invalid_json'}, status=400)

	roles = data.get('roles')
	if not isinstance(roles, dict):
		return JsonResponse({'error': 'invalid_roles'}, status=400)

	for field_name in roles:
		if field_name not in SENTRALE_ROLLER_FIELD_NAMES:
			return JsonResponse({'error': 'invalid_field', 'field': field_name}, status=400)

	for field_name, ids in roles.items():
		if not isinstance(ids, list):
			return JsonResponse({'error': 'invalid_ids', 'field': field_name}, status=400)
		try:
			field_ids = [int(i) for i in ids]
		except (TypeError, ValueError):
			return JsonResponse({'error': 'invalid_ids', 'field': field_name}, status=400)

		scope_virksomhet = _sentrale_roller_ansvarlig_virksomhet(field_name, virksomhet)
		valid_ids = set(
			Ansvarlig.objects.filter(pk__in=field_ids)
			.filter(_ansvarlig_q_for_virksomhet(scope_virksomhet))
			.values_list('pk', flat=True)
		)
		if set(field_ids) - valid_ids:
			return JsonResponse({'error': 'unknown_ansvarlig', 'field': field_name}, status=400)

	with transaction.atomic():
		for field_name, ids in roles.items():
			getattr(virksomhet, field_name).set([int(i) for i in ids])

	virksomhet = Virksomhet.objects.prefetch_related(*[
		Prefetch(field, queryset=Ansvarlig.objects.select_related('brukernavn', 'brukernavn__profile'))
		for field in SENTRALE_ROLLER_FIELD_NAMES
	]).get(pk=pk)

	return JsonResponse({
		'ok': True,
		'roller': _sentrale_roller_redigerbare(virksomhet),
	})


def virksomhet_rediger_roller(request, pk):
	# 2026-06-08: Legacy URL – redirect to virksomhet detail (inline editor).
	return redirect('virksomhet', pk=pk)


@require_POST
def virksomhet_toggle_graph_lock(request, pk):
	required_permissions = REQUIRED_PERMISSIONS_SAVE_GRAPH_VIRKSOMHET
	if not any(map(request.user.has_perm, required_permissions)):
		return HttpResponseForbidden(f'Manglende brukertilganger. Krever {required_permissions}.')
		
	layout = get_object_or_404(GraphLayout, virksomhet_id=pk)
	
	try:
		body = json.loads(request.body)
	except:
		return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

	lock = bool(body.get("locked"))
	layout.locked = lock
	layout.save()

	return JsonResponse({"ok": True, "locked": layout.locked})


@require_POST
def virksomhet_save_graph_layout(request, pk):
	required_permissions = REQUIRED_PERMISSIONS_SAVE_GRAPH_VIRKSOMHET
	if not any(map(request.user.has_perm, required_permissions)):
		return HttpResponseForbidden(f'Manglende brukertilganger. Krever {required_permissions}.')

	"""Persist node positions + viewport for a virksomhet. Returns diagnostics."""
	try:
		data = json.loads(request.body.decode('utf-8'))
	except json.JSONDecodeError:
		return HttpResponseBadRequest('Ugyldig JSON')

	positions = data.get('positions') or {}
	zoom = data.get('zoom', 1.0)
	pan = data.get('pan') or {}
	pan_x = float(pan.get('x', 0.0))
	pan_y = float(pan.get('y', 0.0))

	virksomhet = get_object_or_404(Virksomhet, pk=pk)

	layout, created = GraphLayout.objects.get_or_create(virksomhet=virksomhet)
	if layout.locked:
		return JsonResponse({"ok": False, "error": "Layout is locked"}, status=423)

	layout.positions_json = positions
	layout.zoom = float(zoom)
	layout.pan_x = pan_x
	layout.pan_y = pan_y
	layout.save()

	response = {
		'ok': True,
		'created': created, # om den ble opprettet nå, ikke tidspunkt opprettet
		'locked': layout.locked,
		'nodes': len(positions),
		'zoom': layout.zoom,
		'pan': {'x': layout.pan_x, 'y': layout.pan_y},
		'updated_at': layout.updated_at.isoformat(),
	}
	print(response)
	
	return JsonResponse(response, status=201 if created else 200)


REQUIRED_PERMISSIONS_SAVE_GRAPH_SYSTEM = ['systemoversikt.change_system']

GRAPH_LAYOUT_MAX_POSITIONS = 500
GRAPH_LAYOUT_COORD_BOUND = 50000
GRAPH_LAYOUT_PAN_BOUND = 100000
GRAPH_LAYOUT_ZOOM_MIN = 0.02
GRAPH_LAYOUT_ZOOM_MAX = 8
GRAPH_LAYOUT_MAX_FOLLOW_COUNT = 20


def _finite_float(value):
	try:
		number = float(value)
	except (TypeError, ValueError):
		return None
	if number != number or number in (float('inf'), float('-inf')):
		return None
	return number


def _user_can_save_system_graph_layout(user, system):
	if any(map(user.has_perm, REQUIRED_PERMISSIONS_SAVE_GRAPH_SYSTEM)):
		return True
	forvalter_usernames = {
		ansvarlig.brukernavn.username
		for ansvarlig in system.systemforvalter_kontaktpersoner_referanse.all()
	}
	return user.username in forvalter_usernames


def _system_graph_layout_context(system):
	try:
		layout = SystemGraphLayout.objects.get(system=system)
		return {
			"positions": layout.positions_json,
			"zoom": layout.zoom,
			"pan": {"x": layout.pan_x, "y": layout.pan_y},
			"locked": layout.locked,
		}
	except SystemGraphLayout.DoesNotExist:
		return None


def _system_graph_node_ids(graf):
	node_ids = set()
	for node in graf.get("nodes", []):
		data = node.get("data", {})
		node_id = data.get("id")
		if node_id is not None:
			node_ids.add(str(node_id))
	return node_ids


def _sanitize_system_graph_layout_payload(data, allowed_node_ids):
	if not isinstance(data, dict):
		return None, "Ugyldig JSON"

	extra_keys = set(data.keys()) - {"positions", "zoom", "pan"}
	if extra_keys:
		return None, "Ugyldige felt i forespørselen"

	positions = data.get("positions")
	if not isinstance(positions, dict):
		return None, "positions må være et objekt"
	if len(positions) > GRAPH_LAYOUT_MAX_POSITIONS:
		return None, "For mange noder i layout"

	clean_positions = {}
	for key, value in positions.items():
		key_str = str(key)
		if key_str not in allowed_node_ids:
			continue
		if not isinstance(value, dict):
			return None, "Ugyldig posisjon"
		x = _finite_float(value.get("x"))
		y = _finite_float(value.get("y"))
		if x is None or y is None:
			return None, "Ugyldige koordinater"
		if not (-GRAPH_LAYOUT_COORD_BOUND <= x <= GRAPH_LAYOUT_COORD_BOUND):
			return None, "Koordinat utenfor tillatt område"
		if not (-GRAPH_LAYOUT_COORD_BOUND <= y <= GRAPH_LAYOUT_COORD_BOUND):
			return None, "Koordinat utenfor tillatt område"
		clean_positions[key_str] = {"x": x, "y": y}

	zoom = _finite_float(data.get("zoom", 1.0))
	if zoom is None:
		return None, "Ugyldig zoom"
	zoom = min(GRAPH_LAYOUT_ZOOM_MAX, max(GRAPH_LAYOUT_ZOOM_MIN, zoom))

	pan = data.get("pan") or {}
	if not isinstance(pan, dict):
		return None, "Ugyldig pan"
	pan_x = _finite_float(pan.get("x", 0.0))
	pan_y = _finite_float(pan.get("y", 0.0))
	if pan_x is None or pan_y is None:
		return None, "Ugyldig pan"
	pan_x = min(GRAPH_LAYOUT_PAN_BOUND, max(-GRAPH_LAYOUT_PAN_BOUND, pan_x))
	pan_y = min(GRAPH_LAYOUT_PAN_BOUND, max(-GRAPH_LAYOUT_PAN_BOUND, pan_y))

	return {
		"positions": clean_positions,
		"zoom": zoom,
		"pan_x": pan_x,
		"pan_y": pan_y,
	}, None


@require_POST
def system_toggle_graph_lock(request, pk):
	system = get_object_or_404(System, pk=pk)
	if not _user_can_save_system_graph_layout(request.user, system):
		return HttpResponseForbidden(
			f'Manglende brukertilganger. Krever systemforvalter for dette systemet eller {REQUIRED_PERMISSIONS_SAVE_GRAPH_SYSTEM}.'
		)

	try:
		body = json.loads(request.body)
	except json.JSONDecodeError:
		return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

	if not isinstance(body, dict) or set(body.keys()) - {"locked"}:
		return JsonResponse({"ok": False, "error": "Ugyldig forespørsel"}, status=400)

	layout, _created = SystemGraphLayout.objects.get_or_create(system=system)
	layout.locked = bool(body.get("locked"))
	layout.save(update_fields=["locked", "updated_at"])

	return JsonResponse({"ok": True, "locked": layout.locked})


@require_POST
def system_save_graph_layout(request, pk):
	system = get_object_or_404(System, pk=pk)
	if not _user_can_save_system_graph_layout(request.user, system):
		return HttpResponseForbidden(
			f'Manglende brukertilganger. Krever systemforvalter for dette systemet eller {REQUIRED_PERMISSIONS_SAVE_GRAPH_SYSTEM}.'
		)

	try:
		data = json.loads(request.body.decode('utf-8'))
	except json.JSONDecodeError:
		return HttpResponseBadRequest('Ugyldig JSON')

	try:
		follow_count = int(request.GET.get("follow_count", 0))
	except (TypeError, ValueError):
		return HttpResponseBadRequest('Ugyldig follow_count')
	follow_count = max(0, min(follow_count, GRAPH_LAYOUT_MAX_FOLLOW_COUNT))

	graf = generer_graf_ny(system, follow_count)
	allowed_node_ids = _system_graph_node_ids(graf)
	sanitized, error = _sanitize_system_graph_layout_payload(data, allowed_node_ids)
	if sanitized is None:
		return HttpResponseBadRequest(error)

	layout, created = SystemGraphLayout.objects.get_or_create(system=system)
	if layout.locked:
		return JsonResponse({"ok": False, "error": "Layout is locked"}, status=423)

	layout.positions_json = sanitized["positions"]
	layout.zoom = sanitized["zoom"]
	layout.pan_x = sanitized["pan_x"]
	layout.pan_y = sanitized["pan_y"]
	layout.save()

	return JsonResponse({
		'ok': True,
		'created': created,
		'locked': layout.locked,
		'nodes': len(sanitized["positions"]),
		'zoom': layout.zoom,
		'pan': {'x': layout.pan_x, 'y': layout.pan_y},
		'updated_at': layout.updated_at.isoformat(),
	}, status=201 if created else 200)




def min_virksomhet(request):
	#Vise detaljer om en innlogget brukers virksomhet
	required_permissions = None # kun redirect

	try:
		brukers_virksomhet = request.user.profile.virksomhet_forkortelse
		pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
		return redirect('virksomhet', pk)

	except:
		messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
		return redirect('alle_virksomheter')


def bytt_virksomhet(request):
	#Tilgangsstyring: Innlogget og avhengig av virksomhet innlogget bruker er logget inn som
	#returnere en liste over virksomheter som gjeldende bruker kan representere
	required_permissions = None
	brukers_virksomhet_innlogget_som = request.user.profile.virksomhet_innlogget_som
	if brukers_virksomhet_innlogget_som != None:
		# Vi tar med virksomheten bruker er logget inn med samt alle virksomheter som har angitt gjeldende virksomhet som overordnet virksomhet.
		dine_virksomheter = Virksomhet.objects.filter(Q(pk=brukers_virksomhet_innlogget_som.pk) | Q(overordnede_virksomheter=brukers_virksomhet_innlogget_som))
	else:
		dine_virksomheter = None

	representasjonsvalg_str = request.POST.get("virksomhet", "")
	if representasjonsvalg_str != "":
		valgt_virksomhet = Virksomhet.objects.get(pk=int(representasjonsvalg_str))
		try:
			tillatte_bytter = dine_virksomheter
			if valgt_virksomhet in tillatte_bytter:
				request.user.profile.virksomhet = valgt_virksomhet
				request.user.save()
				messages.success(request, 'Du representerer nå %s' % valgt_virksomhet)
				return redirect(reverse('minside'))
			else:
				messages.warning(request, 'Forsøk på ulovlig bytte')
		except:
			messages.warning(request, 'Noe gikk galt ved endring av virksomhetstilhørighet')

	# denne må vi vente med i tilfelle den blir endret ved en POST-request
	aktiv_representasjon = request.user.profile.virksomhet

	return render(request, 'site_bytt_virksomhet.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'brukers_virksomhet': aktiv_representasjon,
		'dine_virksomheter': dine_virksomheter,
	})


def sertifikatmyndighet(request):
	#Vise informasjon om delegeringer knyttet til sertifikater
	required_permissions = ['systemoversikt.view_virksomhet']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomheter = Virksomhet.objects.all().order_by('-sertifikatfullmakt_avgitt_web')

	return render(request, 'virksomhet_sertifikatmyndigheter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomheter': virksomheter,
	})



def _group_count_by_fk(queryset, fk_field):
	# 2026-06-08: Simple GROUP BY counts – avoids multi-join annotate on virksomhet overview.
	return {
		fk_id: count
		for fk_id, count in queryset.values(fk_field).annotate(count=Count('pk')).values_list(fk_field, 'count')
		if fk_id is not None
	}


def _virksomhet_alle_row_counts(virksomhet_ids):
	"""Per-virksomhet counts for /virksomhet/alle/ – one indexed query per metric."""
	if not virksomhet_ids:
		return {}

	lokasjoner = _group_count_by_fk(
		WANLokasjon.objects.filter(virksomhet_id__in=virksomhet_ids),
		'virksomhet_id',
	)
	klienter = _group_count_by_fk(
		CMDBdevice.objects.filter(client_virksomhet_id__in=virksomhet_ids),
		'client_virksomhet_id',
	)
	systemforvalter = _group_count_by_fk(
		System.objects.filter(systemforvalter_id__in=virksomhet_ids),
		'systemforvalter_id',
	)
	profile_counts = {
		row['virksomhet_id']: row
		for row in (
			Profile.objects
			.filter(virksomhet_id__in=virksomhet_ids, accountdisable=False)
			.values('virksomhet_id')
			.annotate(
				interne=Count('pk', filter=Q(ekstern_ressurs=False)),
				eksterne=Count('pk', filter=Q(ekstern_ressurs=True)),
			)
		)
		if row['virksomhet_id'] is not None
	}

	return {
		pk: {
			'antall_lokasjoner': lokasjoner.get(pk, 0),
			'antall_klienter': klienter.get(pk, 0),
			'antall_systemforvalter': systemforvalter.get(pk, 0),
			'antall_interne_brukeridenter': profile_counts.get(pk, {}).get('interne', 0),
			'antall_eksterne_brukeridenter': profile_counts.get(pk, {}).get('eksterne', 0),
		}
		for pk in virksomhet_ids
	}


def alle_virksomheter(request):
	#Vise oversikt over alle virksomheter
	# 2026-06-08: Batch counts, prefetch M2M, batch leder_hr – avoids N+1 without join-heavy annotate.
	required_permissions = None

	search_term = request.GET.get('search_term', "").strip()

	if search_term in ("", "__all__"):
		virksomheter = Virksomhet.objects.all()
	else:
		virksomheter = Virksomhet.objects.filter(Q(virksomhetsnavn__icontains=search_term) | Q(virksomhetsforkortelse__iexact=search_term))

	ansvarlig_qs = Ansvarlig.objects.select_related('brukernavn')
	virksomheter = (
		virksomheter
		.prefetch_related(
			'overordnede_virksomheter',
			Prefetch('ikt_kontakt', queryset=ansvarlig_qs),
			Prefetch('arkitekturkontakter', queryset=ansvarlig_qs),
			Prefetch('uke_kam_referanse', queryset=ansvarlig_qs),
		)
		.only(
			'pk', 'virksomhetsnavn', 'virksomhetsforkortelse', 'ordinar_virksomhet',
			'resultatenhet', 'office365',
		)
		.order_by('-ordinar_virksomhet', 'virksomhetsnavn')
	)

	virksomheter_list = list(virksomheter)
	virksomheter_count = len(virksomheter_list)
	virksomhet_ids = [v.pk for v in virksomheter_list]
	row_counts = _virksomhet_alle_row_counts(virksomhet_ids)

	leder_hr_by_virksomhet = {}
	if virksomhet_ids:
		for hrorg in (
			HRorg.objects
			.filter(virksomhet_mor_id__in=virksomhet_ids, level__in=[2, 3])
			.select_related('leder', 'leder__profile')
			.order_by('virksomhet_mor_id', '-level')
		):
			if hrorg.virksomhet_mor_id not in leder_hr_by_virksomhet:
				leder_hr_by_virksomhet[hrorg.virksomhet_mor_id] = hrorg.leder

	for vir in virksomheter_list:
		counts = row_counts.get(vir.pk, {})
		vir.antall_lokasjoner = counts.get('antall_lokasjoner', 0)
		vir.antall_klienter = counts.get('antall_klienter', 0)
		vir.antall_systemforvalter = counts.get('antall_systemforvalter', 0)
		vir.antall_interne_brukeridenter = counts.get('antall_interne_brukeridenter', 0)
		vir.antall_eksterne_brukeridenter = counts.get('antall_eksterne_brukeridenter', 0)
		vir.leder_hr_cached = leder_hr_by_virksomhet.get(vir.pk)

	return render(request, 'virksomhet_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomheter': virksomheter_list,
		'virksomheter_count': virksomheter_count,
	})



def alle_virksomheter_kontaktinfo(request):
	#Vise oversikt over alle virksomheter
	required_permissions = []
	#if not any(map(request.user.has_perm, required_permissions)):
	#   return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomheter = Virksomhet.objects.all().order_by('-ordinar_virksomhet', 'virksomhetsnavn')

	return render(request, 'virksomhet_alle_kontaktinfo.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomheter': virksomheter,
	})


def virksomhet_arkivplan(request, pk):
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	systemer = System.objects.filter(Q(systemeier=virksomhet) | Q(systemforvalter=virksomhet))

	return render(request, 'virksomhet_arkivplan.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'systemer': systemer,
	})



def leverandor(request, pk):
	#Vise detaljer for en valgt leverandør
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	leverandor = Leverandor.objects.get(pk=pk)
	systemleverandor_for = System.objects.filter(systemleverandor=pk)
	programvareleverandor_for = Programvare.objects.filter(programvareleverandor=pk)
	basisdriftleverandor_for = System.objects.filter(basisdriftleverandor=pk)
	applikasjonsdriftleverandor_for = System.objects.filter(applikasjonsdriftleverandor=pk)
	registrar_for = SystemUrl.objects.filter(registrar=pk)
	sikkerhetstester = Sikkerhetstester.objects.filter(testet_av=pk)
	plattformer = Driftsmodell.objects.filter(leverandor=pk)
	plattformer_underleverandor = Driftsmodell.objects.filter(underleverandorer=pk)

	return render(request, 'leverandor_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'leverandor': leverandor,
		'systemleverandor_for': systemleverandor_for,
		'programvareleverandor_for': programvareleverandor_for,
		'basisdriftleverandor_for': basisdriftleverandor_for,
		'applikasjonsdriftleverandor_for': applikasjonsdriftleverandor_for,
		'registrar_for': registrar_for,
		'sikkerhetstester': sikkerhetstester,
		'plattformer': plattformer,
		'plattformer_underleverandor': plattformer_underleverandor,
	})



def alle_leverandorer(request):
	#Vise liste over alle leverandører
	# 2026-06-07: Annotate system counts per supplier role for overview table columns.
	# 2026-06-21: Leverandør reference statistics table at top of overview page.
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from django.db.models.functions import Lower
	search_term = request.GET.get('search_term', "").strip()

	if search_term == "":
		leverandorer = Leverandor.objects.all()
	else:
		leverandorer = Leverandor.objects.filter(leverandor_navn__icontains=search_term)

	leverandorer = leverandorer.annotate(
		antall_systemleverandor=Count('system_systemleverandor', distinct=True),
		antall_basisdriftleverandor=Count('system_driftsleverandor', distinct=True),
		antall_applikasjonsdriftleverandor=Count('system_applikasjonsdriftleverandor', distinct=True),
	).order_by(Lower('leverandor_navn'))

	return render(request, 'leverandor_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'leverandorer': leverandorer,
		'system_felt_referanse': System(),
		'search_term': search_term,
		'leverandor_statistikk': leverandor_referanse_statistikk(),
	})



def alle_driftsmodeller(request):
	#Vise liste over alle driftsmodeller
	# 2026-06-22: Prefetch related fields and annotate system count – full model data on alle-page.
	# 2026-06-22: Dropped lokasjon_lagring_valgmeny prefetch – field removed from model.
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	driftsmodeller = Driftsmodell.objects.annotate(
		antall_systemer=Count('systemer', filter=~Q(systemer__livslop_status=7)),
	).select_related(
		'ansvarlig_virksomhet',
		'overordnet_plattform',
		'applikasjonsdriftleverandor',
	).prefetch_related(
		'leverandor',
		'underleverandorer',
		'avtaler',
	).order_by('sort_order', 'navn')

	return render(request, 'driftsmodell_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'driftsmodeller': driftsmodeller,
		'driftsmodell_felt_referanse': Driftsmodell(),
	})



def driftsmodell_virksomhet_klassifisering(request, pk):
	#Vise informasjon om sikkerhethetsklassifisering for systemer driftet av en virksomhet (alle systemer koblet til driftsmodeller som forvaltes av valgt virksomhet)
	required_permissions = ['systemoversikt.change_systemkategori']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	driftsmodeller = Driftsmodell.objects.filter(ansvarlig_virksomhet=virksomhet)
	systemer_drifter = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet).filter(~Q(ibruk=False)).order_by('sikkerhetsnivaa')
	return render(request, 'alle_systemer_virksomhet_drifter_klassifisering.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'systemer': systemer_drifter,
		'driftsmodeller': driftsmodeller,
	})


def rapport_systemer_leverandor_land(request):
	# 2026-06-07: Report of systems with supplier country data – three supplier roles per system.
	# 2026-06-07: Country summary with system counts per observed country.
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	land_codes = [code for code, _ in LEVERANDOR_LAND_VALG]
	land_navn = dict(LEVERANDOR_LAND_VALG)
	har_leverandor_land = (
		Q(systemleverandor__land__in=land_codes) |
		Q(basisdriftleverandor__land__in=land_codes) |
		Q(applikasjonsdriftleverandor__land__in=land_codes)
	)
	systemer = System.objects.filter(har_leverandor_land).distinct().prefetch_related(
		'systemleverandor',
		'basisdriftleverandor',
		'applikasjonsdriftleverandor',
	).order_by(Lower('systemnavn'))

	land_til_systemer = defaultdict(set)
	for system in systemer:
		system_lands = set()
		for lev in system.systemleverandor.all():
			if lev.land:
				system_lands.add(lev.land)
		for lev in system.basisdriftleverandor.all():
			if lev.land:
				system_lands.add(lev.land)
		for lev in system.applikasjonsdriftleverandor.all():
			if lev.land:
				system_lands.add(lev.land)
		for land in system_lands:
			land_til_systemer[land].add(system.pk)

	land_oppsummering = sorted(
		[
			{
				'land_kode': land_kode,
				'land_navn': land_navn.get(land_kode, land_kode),
				'antall_systemer': len(system_ids),
			}
			for land_kode, system_ids in land_til_systemer.items()
		],
		key=lambda row: (-row['antall_systemer'], row['land_navn']),
	)

	return render(request, 'rapport_systemer_leverandor_land.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
		'land_oppsummering': land_oppsummering,
		'antall_unike_land': len(land_oppsummering),
		'antall_systemer': systemer.count(),
	})


def rapport_prioriteringer(request):
	#Vise indeks over systemprioritering
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomheter = Virksomhet.objects.filter(ordinar_virksomhet=True).filter(~Q(driftsmodell_ansvarlig_virksomhet=None))
	intern_tjenesteleverandorer = Virksomhet.objects.filter(
		intern_tjenesteleverandor=True,
	).order_by('virksomhetsforkortelse', 'virksomhetsnavn')

	return render(request, 'rapport_prioriteringer.html', {
		'request': request,
		'virksomheter': virksomheter,
		'intern_tjenesteleverandorer': intern_tjenesteleverandorer,
	})


def rapport_ukjente_identer(request):
	# 2026-07-07: Restrict to view_qualysvuln – same audience as other sikkerhetsanalytiker AD reports.
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	identer = User.objects.filter(profile__accountdisable=False, profile__virksomhet=None)

	return render(request, 'rapport_ukjente_identer.html', {
		'request': request,
		'identer': identer,
		'integrasjonsstatus': _integrasjonsstatus("ad_users"),
	})


def drift_beredskap_redirect(request):
	try:
		vir = request.user.profile.virksomhet
		return HttpResponseRedirect(reverse('drift_beredskap', kwargs={'pk': vir.pk}))
	except:
		messages.info("Du er ikke logget inn. Vennligst logg inn slik at du kan sendes til riktig beredskapsplan")
		return HttpResponseRedirect(reverse('home',))



def drift_beredskap(request, pk):
	#Vise systemer driftet av en virksomhet (alle systemer koblet til driftsmodeller som forvaltes av valgt virksomhet)
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	systemer_drifter = System.objects.filter(
		driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet,
	).filter(ibruk=True)

	# 2026-06-23: Exclude infra and sort by live score (lowest = highest recovery priority).
	systemer_med_poeng = [
		(s, s.systemprioritet_poeng())
		for s in systemer_drifter
		if not s.er_infrastruktur()
	]
	systemer_med_poeng.sort(key=lambda item: (item[1], item[0].systemnavn.lower()))
	for s, score in systemer_med_poeng:
		s.prioritet_poeng = score
	systemer_drifter = [s for s, _ in systemer_med_poeng]

	antall_top_x = 30
	systemer_drifter_top_x = systemer_drifter[:antall_top_x]

	# 2026-06-23: Bar chart – count per priority score so forvalter can see spread across poengsum.
	# 2026-06-23: Omit chart when all systems share one score – nothing to compare.
	priority_score_counts = Counter(score for _, score in systemer_med_poeng)
	sorted_scores = sorted(priority_score_counts.keys())
	chart_prioritet_fordeling = None
	if len(sorted_scores) > 1:
		chart_prioritet_fordeling = {
			'labels': [str(score) for score in sorted_scores],
			'data': [priority_score_counts[score] for score in sorted_scores],
		}

	return render(request, 'systemer_drifter_prioritering.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'systemer': systemer_drifter,
		'systemer_drifter_top_x': systemer_drifter_top_x,
		'antall_top_x': antall_top_x,
		'chart_prioritet_fordeling': chart_prioritet_fordeling,
	})



def driftsmodell_virksomhet(request, pk=None):

	if pk == None:
		try:
			brukers_virksomhet = request.user.profile.virksomhet_forkortelse
			pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
			return redirect('driftsmodell_virksomhet', pk)
		except:
			messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
			return redirect('alle_virksomheter')


	#Vise systemer driftet av en virksomhet (alle systemer koblet til driftsmodeller som forvaltes av valgt virksomhet)
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	driftsmodeller = Driftsmodell.objects.filter(ansvarlig_virksomhet=virksomhet).order_by("navn")
	systemer_drifter = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet).filter(~Q(ibruk=False)).order_by('systemnavn')

	return render(request, 'system_virksomhet_drifter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'systemer': systemer_drifter,
		'driftsmodeller': driftsmodeller,
	})



def detaljer_driftsmodell(request, pk):
	#Vise detaljer om en valgt driftsmodell (inkl. systemer tilknyttet)
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	driftsmodell = Driftsmodell.objects.get(pk=pk)
	systemer = System.objects.filter(driftsmodell_foreignkey=pk).filter(~Q(livslop_status=7))
	isolert_drift = systemer.filter(isolert_drift=True)

	return render(request, 'driftsmodell_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'driftsmodell': driftsmodell,
		'systemer': systemer,
		'isolert_drift': isolert_drift,
	})



def systemer_uten_driftsmodell(request):
	#Vise liste over systemer der driftsmodell mangler
	required_permissions = ['systemoversikt.view_system']

	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	mangler = System.objects.filter(Q(driftsmodell_foreignkey=None) & ~Q(systemtyper=1))

	return render(request, 'driftsmodell_mangler.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': mangler,
})


def systemer_utfaset(request):
	#Vise liste over systemer satt til "ikke i bruk"
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	systemer = System.objects.filter(livslop_status__in=[6,7]).order_by("-sist_oppdatert")

	return render(request, 'system_utfaset.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
})



def systemkategori(request, pk):
	#Vise detaljer om en kategori
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	kategori = SystemKategori.objects.get(pk=pk)
	systemer = System.objects.filter(~Q(livslop_status=7)).filter(systemkategorier=pk).order_by(Lower('systemnavn'))
	programvarer = Programvare.objects.filter(kategorier=pk).order_by(Lower('programvarenavn'))

	return render(request, 'kategori_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
		'kategori': kategori,
		'programvarer': programvarer,
	})



def alle_hovedkategorier(request):
	#Vise liste over alle hovedkategorier
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	hovedkategorier = SystemHovedKategori.objects.order_by('hovedkategorinavn')
	for kategori in hovedkategorier:
		systemteller = 0
		programteller = 0
		for subkategori in kategori.subkategorier.all():
			systemteller += len(subkategori.system_systemkategorier.all())
			programteller += len(subkategori.programvare_systemkategorier.all())
		kategori.systemteller = systemteller
		kategori.programteller = programteller

	subkategorier_uten_hovedkategori = []
	for subkategori in SystemKategori.objects.all():
		if len(subkategori.systemhovedkategori_systemkategorier.all()) == 0:
			subkategorier_uten_hovedkategori.append(subkategori)

	return render(request, 'kategori_hoved_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'hovedkategorier': hovedkategorier,
		'subkategorier_uten_hovedkategori': subkategorier_uten_hovedkategori,
	})



def alle_systemkategorier(request):
	#Vise liste over alle (under)kategorier
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	kategorier = SystemKategori.objects.order_by('kategorinavn')

	return render(request, 'kategori_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'kategorier': kategorier,
	})


def uten_systemkategori(request):
	#Vise liste over alle systemer uten (under)kategori
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	antall_systemer = System.objects.all().count()
	antall_programvarer = Programvare.objects.all().count()
	systemer = System.objects.annotate(num_categories=Count('systemkategorier')).filter(num_categories=0)
	programvarer = Programvare.objects.annotate(num_categories=Count('kategorier')).filter(num_categories=0)

	return render(request, 'kategori_system_uten.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
		'programvarer': programvarer,
		'antall_systemer': antall_systemer,
		'antall_programvarer': antall_programvarer,
	})



def alle_systemurler(request):
	#Vise liste over alle URLer
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	urler = SystemUrl.objects.order_by('domene')

	return render(request, 'urler_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'web_urler': urler,
	})



def virksomhet_urler(request, pk):
	#Vise liste over alle URLer
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	urler = SystemUrl.objects.filter(eier=virksomhet.pk).order_by('domene')

	return render(request, 'urler_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'web_urler': urler,
		'virksomhet': virksomhet,
	})



def bytt_kategori(request, fra, til):
	#Funksjon for å bytte all bruk av én kategori til en annen kategori
	required_permissions = ['systemoversikt.change_systemkategori']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	try:
		kategori_fra = SystemKategori.objects.get(pk=fra)
		kategori_til = SystemKategori.objects.get(pk=til)
	except:
		messages.warning(request, 'Erstatte kategori feilet. Enten "fra" eller "til" kategori finnes ikke.')
		return redirect('alle_virksomheter')

	kildesystemer = System.objects.filter(systemkategorier=fra)
	error = ok = 0
	for system in kildesystemer:
		try:
			system.systemkategorier.remove(kategori_fra)
			system.systemkategorier.add(kategori_til)
			ok += 1
		except:
			error += 1

	messages.success(request, 'Byttet fra %s til %s (ok: %s, error: %s)'% (
				kategori_fra.kategorinavn,
				kategori_til.kategorinavn,
				ok,
				error,
			))
	return redirect('alle_virksomheter')



def system_til_programvare(request, system_id=None):
	#Funksjon for å opprette en instans av programvare basert på system (systemet må slettes manuelt etterpå)
	required_permissions = ['systemoversikt.change_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if system_id:
		try:
			#finne systemet som skal konverteres
			kildesystem = System.objects.get(pk=system_id)

			try:
				Programvare.objects.get(programvarenavn=kildesystem.systemnavn)
				messages.warning(request, 'Programvare med navn %s finnes allerede' % kildesystem.systemnavn)
				resume = False
			except:
				resume = True

			if resume:
				#nytt programvareobjekt med kopierte verdier
				ny_programvare = Programvare.objects.create(
						programvarenavn=kildesystem.systemnavn,
						programvarekategori=kildesystem.programvarekategori,
						programvarebeskrivelse=kildesystem.systembeskrivelse,
						kommentar=kildesystem.kommentar,
						strategisk_egnethet=kildesystem.strategisk_egnethet,
						funksjonell_egnethet=kildesystem.funksjonell_egnethet,
						teknisk_egnethet=kildesystem.teknisk_egnethet,
						selvbetjening=kildesystem.selvbetjening,
						livslop_status=kildesystem.livslop_status,
					)
				for leverandor in kildesystem.systemleverandor.all():
					ny_programvare.programvareleverandor.add(leverandor)
				for kategori in kildesystem.systemkategorier.all():
					ny_programvare.kategorier.add(kategori)
				for programvaretype in kildesystem.systemtyper.all():
					ny_programvare.programvaretyper.add(programvaretype)
				ny_programvare.save()

				#nye programvarebruk per systembruk
				for systembruk in kildesystem.systembruk_system.all():
					ProgramvareBruk.objects.create(
							brukergruppe=systembruk.brukergruppe,
							programvare=ny_programvare,
							livslop_status=systembruk.livslop_status,
							kommentar=systembruk.kommentar,
							strategisk_egnethet=systembruk.strategisk_egnethet,
							funksjonell_egnethet=systembruk.funksjonell_egnethet,
							teknisk_egnethet=systembruk.teknisk_egnethet,
						)

				messages.success(request, 'Konvertere system til programvare. Ny programvare %s er opprettet' % ny_programvare.programvarenavn)

		except Exception as e:
			messages.warning(request, 'Konvertere system til programvare feilet med feilmelding %s' % e)

	utvalg_systemer = System.objects.filter(systemtyper=1)

	return render(request, 'system_tilprogramvare.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': utvalg_systemer,
	})



def adorgunit_detaljer(request, pk=None):
	#Vise informasjon om en konkret AD-OU
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import os

	if pk == None:
		root_str = os.environ["KARTOTEKET_LDAPROOT"]
		ou = ADOrgUnit.objects.get(distinguishedname=root_str)
		pk = ou.pk
	else:
		ou = ADOrgUnit.objects.get(pk=pk)

	groups = ADgroup.objects.filter(parent=pk).order_by(Lower('distinguishedname'))
	parent_str = ",".join(ou.distinguishedname.split(',')[1:])
	try:
		parent = ADOrgUnit.objects.get(distinguishedname=parent_str)
	except:
		parent = None
	children = ADOrgUnit.objects.filter(parent=pk).order_by(Lower('distinguishedname'))

	users = User.objects.filter(profile__ou=pk).order_by(Lower('first_name'))

	return render(request, 'ad_adorgunit_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"ou": ou,
		"groups": groups,
		"parent": parent,
		"children": children,
		"users": users,
	})



def ad_gruppeanalyse(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	brukernavn_str = request.POST.get('brukernavn', "").strip().lower()

	try:
		bruker = User.objects.get(username=brukernavn_str)
		brukers_grupper = ldap_users_securitygroups(bruker.username)
		brukers_unike_grupper = sorted(convert_distinguishedname_cn(brukers_grupper))
	except:
		#print("ad_gruppeanalyse: Brukernavn finnes ikke")
		brukers_unike_grupper = None


	sikkerhetsgrupper_str = request.POST.get('sikkerhetsgrupper', "")
	sikkerhetsgrupper = []
	feilede_oppslag = []
	sikkerhetsgrupper_oppsplittet = re.findall(r"([^,;\n\r]+)", sikkerhetsgrupper_str) # alt mellom tegn som typisk brukes for å splitte unike ting.

	for gr in sikkerhetsgrupper_oppsplittet:
		stripped_gr = gr.strip()
		if "\\" in stripped_gr:
			stripped_gr = stripped_gr.split("\\")[1]
		try:
			sikkerhetsgrupper.append(ADgroup.objects.get(common_name=stripped_gr))
		except:
			feilede_oppslag.append(stripped_gr)

	utnostede_grupper = []
	for gr in sikkerhetsgrupper:
		utnostede_grupper += adgruppe_utnosting(gr)

	utnostede_grupper_ant_medlemmer = 0
	for gr in utnostede_grupper:
		utnostede_grupper_ant_medlemmer += gr.membercount


	if brukers_unike_grupper and utnostede_grupper:
		set_brukers_grupper = set(brukers_unike_grupper)
		set_sikkerhetsgruppeutnosting = [g.common_name for g in utnostede_grupper]
		sammenfallende = set_brukers_grupper.intersection(set_sikkerhetsgruppeutnosting)
	else:
		sammenfallende = None

	context = {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'form_brukernavn': brukernavn_str,
		'form_sikkerhetsgrupper': sikkerhetsgrupper_str,
		'brukers_unike_grupper': brukers_unike_grupper,
		'feilede_oppslag': feilede_oppslag,
		'unike_utnostede_grupper': utnostede_grupper,
		'sammenfallende': sammenfallende,
		'utnostede_grupper_ant_medlemmer': utnostede_grupper_ant_medlemmer,
	}
	return render(request, 'ad_gruppeanalyse.html', context)



def adgruppe_graf(request, pk):
	#Vise en graf over hvordan grupper er nøstet nedover fra en gitt gruppe
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import math
	morgruppe = ADgroup.objects.get(pk=pk)

	avhengigheter_graf = {"nodes": [], "edges": []}
	nye_grupper = []
	ferdige = []

	maks_grense = int(request.GET.get('maks_grense', 50))  # strip removes trailing and leading space
	grense = 0

	def define_color(gruppe):
		if gruppe.from_prk:
			return "#3bc319"
		else:
			return "#da3747"

	def define_size(gruppe):
		minimum = 25
		if gruppe.membercount > 0:
			adjusted_member_count = minimum + (20 * math.log(gruppe.membercount, 10))
			return ("%spx" % adjusted_member_count)
		else:
			return ("%spx" % minimum)

	def registrere_gruppe(gruppe):
		if gruppe not in ferdige:
			size = define_size(gruppe)
			avhengigheter_graf["nodes"].append(
					{"data": {
							"parent": '',
							"id": gruppe.pk,
							"name": gruppe.short(),
							"shape": "triangle",
							"size": size,
							"color": "#202020"
						},
					})
			ferdige.append(gruppe.pk)

		members = human_readable_members(json.loads(gruppe.member), onlygroups=True)
		for m in members["groups"]:
			color = define_color(m)
			size = define_size(m)
			if m not in ferdige and m.parent != None:
				nonlocal grense
				if grense < maks_grense:
					nye_grupper.append(m)
					grense += 1
				#print("added %s" % m)

				avhengigheter_graf["nodes"].append(
						{"data": {
							"parent": m.parent.pk,
							"id": m.pk,
							"name": m.display_name,
							"shape": "ellipse",
							"color": color,
							"size": size,
							"href": reverse('adgruppe_detaljer', args=[m.pk])
							}
						})
				avhengigheter_graf["edges"].append(
						{"data": {
							"source": gruppe.pk,
							"target": m.pk,
							"linestyle": "solid"
							}
						})
				ferdige.append(m.pk)

	registrere_gruppe(morgruppe)

	while nye_grupper:
		g = nye_grupper.pop()
		#print("removed %s" % g)
		registrere_gruppe(g)

	return render(request, 'ad_graf.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'avhengigheter_graf': avhengigheter_graf,
		'morgruppe': morgruppe,
		'maks_grense': maks_grense,
		'grense': grense,
	})



def adgruppe_detaljer(request, pk):
	#Vise informasjon om en konkret AD-gruppe
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	render_anyway = True if (request.GET.get('alt') == "ja") else False
	render_limit = 300
	rendered = False
	gruppe = ADgroup.objects.get(pk=pk)

	member = {}
	memberof = {}

	print("laster medlemmer")
	member_decoded = json.loads(gruppe.member)
	if (len(member_decoded) <= render_limit) or render_anyway:
		member = human_readable_members_optimized(member_decoded)
		rendered = True
	print("laster memberof")
	memberof = human_readable_members_optimized(json.loads(gruppe.memberof))
	print("Sender til template")

	return render(request, 'ad_adgruppe_detaljer.html', {
		"gruppe": gruppe,
		"member": member,
		"memberof": memberof,
		"render_anyway": render_anyway,
		"render_limit": render_limit,
		"rendered": rendered,
	})




def adgruppe_detaljer_optimized(request, pk):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {
			'required_permissions': required_permissions,
			'groups': request.user.groups
		})

	render_anyway = (request.GET.get('alt') == "ja")
	render_limit = 600
	rendered = False

	# Load only necessary fields and optimize relations
	gruppe = (
		ADgroup.objects
		.only('pk', 'common_name', 'display_name', 'distinguishedname',
			  'description', 'from_prk', 'sist_oppdatert', 'member', 'memberof', 'parent')
		.select_related('parent')
		.get(pk=pk)
	)

	# Decode JSON safely
	member_items = json.loads(gruppe.member or "[]")
	memberof_items = json.loads(gruppe.memberof or "[]")

	# Cache keys based on last sync timestamp
	version = gruppe.sist_oppdatert.isoformat() if gruppe.sist_oppdatert else "0"
	member_cache_key = f"adgroup:{gruppe.pk}:member:{version}:{render_limit}:{int(render_anyway)}"
	memberof_cache_key = f"adgroup:{gruppe.pk}:memberof:{version}"

	# Resolve memberof (groups only)
	memberof = cache.get(memberof_cache_key)
	if memberof is None:
		memberof = human_readable_members(memberof_items, onlygroups=True)
		cache.set(memberof_cache_key, memberof, timeout=3600)

	# Resolve members if allowed
	member = {}
	if len(member_items) <= render_limit or render_anyway:
		member = cache.get(member_cache_key)
		if member is None:
			member = human_readable_members(member_items)
			cache.set(member_cache_key, member, timeout=3600)
		rendered = True

	return render(request, 'ad_adgruppe_detaljer.html', {
		"gruppe": gruppe,
		"member": member,
		"memberof": memberof,
		"render_anyway": render_anyway,
		"render_limit": render_limit,
		"rendered": rendered,
	})





def virksomhet_adgruppe_detaljer(request):
	#Vise informasjon om en konkret AD-gruppe for en enkelt virksomhet
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	try:
		virksomhetsforkotelse = request.user.profile.virksomhet_innlogget_som.virksomhetsforkortelse

	except:
		return render(request, 'ad_analyse.html', {
			'request': request,
			'required_permissions': formater_permissions(required_permissions),
		})

	valgt_gruppe = None
	valgt_gruppe_medlemmer = None
	valg_grupper = None
	search_term = ""

	search_term_raw = request.GET.get("search_term", False)
	if search_term_raw:
		valg_grupper = ADgroup.objects.filter(Q(distinguishedname__icontains=search_term_raw) | Q(display_name__icontains=search_term_raw))
		search_term = search_term_raw

	valgt_gruppe = request.GET.get("valgt_gruppe", False)
	if valgt_gruppe:

		gruppe = ADgroup.objects.get(pk=valgt_gruppe)
		members = json.loads(gruppe.member)
		filtrerte_medlemmer = set()
		for m in members:
			if virksomhetsforkotelse in m:
				filtrerte_medlemmer.add(m)

		members = human_readable_members(list(filtrerte_medlemmer))

		valgt_gruppe = gruppe
		valgt_gruppe_medlemmer = members
		search_term = gruppe

	return render(request, 'virksomhet_adgruppe_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"valg_grupper": valg_grupper,
		"valgt_gruppe": valgt_gruppe,
		"valgt_gruppe_medlemmer": valgt_gruppe_medlemmer,
		"search_term": search_term,
		"virksomhetsforkotelse": virksomhetsforkotelse,
	})



def ad_analyse(request):
	#Vise informasjon om tomme ADgrupper, AD-grupper ikke fra PRK osv.
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	antall_alle_grupper = ADgroup.objects.all().count()
	maks = int(request.GET.get('antall', 1))
	adgrupper_tomme = ADgroup.objects.filter(membercount__lte=maks)
	antall_tomme = len(adgrupper_tomme)

	return render(request, 'ad_analyse.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"adgrupper_tomme": adgrupper_tomme,
		"maks": maks,
		"antall_alle_grupper": antall_alle_grupper,
		"antall_tomme": antall_tomme,
	})


def rapport_ad_adgrupper(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	antall_adgr_tid = []
	logs = ApplicationLog.objects.filter(event_type="AD group-import", message__startswith="Det tok")
	for log in logs:
		antall_adgr_tid.append({"label": log.opprettet.strftime("%b %y"), "value": float(re.search(r'sekunder\. (\d+) treff', log.message, re.I).groups()[0])})


	return render(request, 'rapport_ad_adgrupper.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'antall_adgr_tid': antall_adgr_tid,
		'integrasjonsstatus': _integrasjonsstatus("ad_groups"),
	})



def alle_adgrupper(request):
	#Vise informasjon om AD-grupper
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term_adgrp', '').strip()  # strip removes trailing and leading space
	if len(search_term) > 1:
		if search_term[0:3] == "CN=":
			search_term = search_term[3:]
		search_term = search_term.split(",")[0]
		adgrupper = ADgroup.objects.filter(Q(common_name__icontains=search_term) | Q(display_name__icontains=search_term) | Q(description__icontains=search_term) | Q(distinguishedname__icontains=search_term))
		for g in adgrupper:
			members = json.loads(g.member)
			g.member_count = len(members)
			if g.member_count < 11:
				g.member_show = ", ".join(m.split(",")[0].split("CN=")[1] for m in members)
			else:
				g.member_show = ""
	else:
		adgrupper = ADgroup.objects.none()

	return render(request, 'ad_adgrupper_sok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"adgrupper": adgrupper,
		"search_term_adgrp": search_term,
	})



def maskin_sok(request):
	#Søke opp hostnavn
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	# 2026-06-21: Also match exact IP addresses (comp_ip_address and linked NetworkIPAddress).
	hits = []
	seen_hit_pks = set()
	misses = []
	query = request.POST.get('search_term', '').strip()
	if query != "":
		servers = query.split("\n")
		for server in servers:
			term = server.strip()
			if term == "":
				continue
			matched = False
			for m in CMDBdevice.objects.filter(comp_name__iexact=term):
				if m.pk not in seen_hit_pks:
					seen_hit_pks.add(m.pk)
					hits.append(m)
				matched = True
			try:
				ip_str = str(ipaddress.ip_address(term))
			except ValueError:
				ip_str = None
			if ip_str is not None:
				ip_matches = CMDBdevice.objects.filter(
					Q(comp_ip_address__iexact=ip_str)
					| Q(network_ip_address__ip_address=ip_str)
				).distinct()
				for m in ip_matches:
					if m.pk not in seen_hit_pks:
						seen_hit_pks.add(m.pk)
						hits.append(m)
					matched = True
			if not matched:
				misses.append(term)

	return render(request, 'cmdb_maskin_sok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'query': query,
		'hits': hits,
		'misses': misses,
	})



_IPV4_CIDR_TOKEN_RE = re.compile(
	r'(?<![0-9.])(?:\d{1,3}\.){3}\d{1,3}\s*/\s*(?:3[0-2]|[12]?\d)(?![0-9.])'
)


def _search_term_is_ip_lookup(search_term):
	"""True when the whole search string is only IPv4 address(es) and/or IPv4 CIDR."""
	term = search_term.strip()
	if len(term) <= 1:
		return False

	subnet_tokens, remainder = _extract_ipv4_cidr_tokens(term)
	remainder = remainder.replace('"', '').replace("'", '').replace(':', ' ')
	tokens = re.findall(r'([^,;\t\s\n\r]+)', remainder.strip())

	if not tokens:
		return bool(subnet_tokens)

	for token in tokens:
		try:
			ip = ipaddress.ip_address(token.strip())
			if not isinstance(ip, ipaddress.IPv4Address):
				return False
		except ValueError:
			return False

	return True


def _extract_ipv4_cidr_tokens(text):
	"""Plukk ut IPv4 CIDR (f.eks. 10.130.0.0/21) før øvrig splitting — må skje før '/' erstattes."""
	subnets = []
	parts = []
	pos = 0
	for m in _IPV4_CIDR_TOKEN_RE.finditer(text):
		parts.append(text[pos:m.start()])
		raw_display = m.group(0).strip()
		raw_parse = re.sub(r'\s*/\s*', '/', raw_display)
		try:
			net = ipaddress.ip_network(raw_parse, strict=False)
			if isinstance(net, ipaddress.IPv4Network):
				subnets.append((raw_parse, net))
			else:
				parts.append(raw_display)
		except ValueError:
			parts.append(raw_display)
		pos = m.end()
	parts.append(text[pos:])
	return subnets, ''.join(parts)


def alle_ip(request):
	# 2026-07-07: GET search_term – linked from global /sok/ redirect for IPv4/CIDR lookups.
	# 2026-07-07: Include /16 VLANs in host-IP containment lookup (threshold lowered from /17 to /16).
	# 2026-07-07: Prefetch infoblox_hosts for Infoblox host/fixed metadata on IP lookup.
	# Søke opp IPv4-adresser mot CMDB (host-IP, DNS-koblinger i CMDB) og VLAN-/nettverksdata.
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	MAX_IP_LOOKUPS = 1000

	if request.method == 'POST':
		show_hosts = request.POST.get('show_hosts') == 'on'
		show_networks = request.POST.get('show_networks') == 'on'
		show_unique_vlans = request.POST.get('show_unique_vlans') == 'on'
		search_term_display = request.POST.get('search_term', '').strip()
	elif request.GET.get('search_term', '').strip():
		show_hosts = True
		show_networks = True
		show_unique_vlans = False
		search_term_display = request.GET.get('search_term', '').strip()
	else:
		show_hosts = True
		show_networks = True
		show_unique_vlans = False
		search_term_display = ''

	host_matches = []
	network_matches = []
	unique_vlan_networks = []
	not_ip_addresses = []
	ipv6_terms = set()

	search_term = search_term_display
	# Skip summary nets broader than /16 when resolving a host IP or CIDR overlap (include /16 and smaller).
	MIN_VLAN_SUBNET_MASK_EXCLUSIVE = 15

	def find_matching_networks_ipv4(ip_string, networks_with_id):
		try:
			ip = ipaddress.ip_address(ip_string)
			if not isinstance(ip, ipaddress.IPv4Address):
				return None
			matching_ids = [nid for network, mask, nid in networks_with_id if ip in network]
			if not matching_ids:
				return None
			matching_objects = NetworkContainer.objects.filter(id__in=matching_ids)
			return [o for o in matching_objects if o.subnet_mask > MIN_VLAN_SUBNET_MASK_EXCLUSIVE]
		except ValueError:
			return None

	def find_overlapping_networks_ipv4(user_network, networks_with_id):
		matching_ids = [nid for network, mask, nid in networks_with_id if user_network.overlaps(network)]
		if not matching_ids:
			return None
		matching_objects = NetworkContainer.objects.filter(id__in=matching_ids)
		return [o for o in matching_objects if o.subnet_mask > MIN_VLAN_SUBNET_MASK_EXCLUSIVE]

	if search_term != '':
		if not show_hosts and not show_networks and not show_unique_vlans:
			messages.warning(
				request,
				'Velg minst én av «Vis host-treff», «Vis nettverkstreff» eller «Unike VLAN».',
			)
		else:
			subnet_tokens, search_term_no_cidr = _extract_ipv4_cidr_tokens(search_term)
			subnet_by_norm = {}
			for raw, net in subnet_tokens:
				key = str(net)
				if key not in subnet_by_norm:
					subnet_by_norm[key] = (raw, net)
			subnet_entries = list(subnet_by_norm.values())

			search_term = search_term_no_cidr
			search_term = search_term.replace('"', '').replace("'", '').replace(':', ' ')
			search_terms = re.findall(r'([^,;\t\s\n\r]+)', search_term)
			unique_terms = list(dict.fromkeys(search_terms))

			total_lookups = len(unique_terms) + len(subnet_entries)
			if total_lookups > MAX_IP_LOOKUPS:
				messages.error(
					request,
					f'For mange unike oppføringer ({total_lookups}). Maksimum er {MAX_IP_LOOKUPS} oppslag per søk.',
				)
			else:
				ipv4_by_term = {}
				for term in unique_terms:
					try:
						ip = ipaddress.ip_address(term.strip())
						if isinstance(ip, ipaddress.IPv6Address):
							ipv6_terms.add(term)
						else:
							ipv4_by_term[term] = str(ip)
					except ValueError:
						ipv4_by_term[term] = None

				ipv4_norm_set = {n for n in ipv4_by_term.values() if n is not None}

				matched_host_norms = set()
				if show_hosts and ipv4_norm_set:
					host_matches = list(
						NetworkIPAddress.objects.filter(ip_address__in=ipv4_norm_set).prefetch_related(
							'servere__service_offerings__system',
							'dns',
							'vlan',
							'viper',
							'vip_pools',
							'infoblox_hosts',
						)
					)
					matched_host_norms = {str(h.ip_address) for h in host_matches}

				network_hit_terms = set()
				vlan_objects_by_id = {}
				vlan_unique_ips = defaultdict(set)
				if show_networks or show_unique_vlans:
					exact_by_ip = defaultdict(list)
					if ipv4_norm_set:
						for row in NetworkContainer.objects.filter(ip_address__in=list(ipv4_norm_set)):
							exact_by_ip[str(row.ip_address)].append(row)

					networks_with_id = None
					for term in unique_terms:
						norm = ipv4_by_term.get(term)
						if not norm:
							continue
						if exact_by_ip[norm]:
							term_matches = exact_by_ip[norm]
						else:
							if networks_with_id is None:
								networks_with_id = []
								for nip, mask, nid in NetworkContainer.objects.values_list(
									'ip_address', 'subnet_mask', 'id'
								):
									try:
										if ':' in nip:
											continue
										networks_with_id.append(
											(ipaddress.IPv4Network(f'{nip}/{mask}', strict=False), mask, nid)
										)
									except ValueError:
										pass
							term_matches = find_matching_networks_ipv4(norm, networks_with_id) or []

						if term_matches:
							network_hit_terms.add(term)
							if show_unique_vlans:
								for n in term_matches:
									vlan_unique_ips[n.id].add(norm)
									if n.id not in vlan_objects_by_id:
										vlan_objects_by_id[n.id] = n
							if show_networks:
								network_matches.append({'term': term, 'matches': term_matches})

					for cidr_display, user_net in subnet_entries:
						if networks_with_id is None:
							networks_with_id = []
							for nip, mask, nid in NetworkContainer.objects.values_list(
								'ip_address', 'subnet_mask', 'id'
							):
								try:
									if ':' in nip:
										continue
									networks_with_id.append(
										(ipaddress.IPv4Network(f'{nip}/{mask}', strict=False), mask, nid)
									)
								except ValueError:
									pass
						term_matches = find_overlapping_networks_ipv4(user_net, networks_with_id) or []
						if term_matches:
							network_hit_terms.add(cidr_display)
							if show_unique_vlans:
								for n in term_matches:
									vlan_unique_ips[n.id].add(str(user_net))
									if n.id not in vlan_objects_by_id:
										vlan_objects_by_id[n.id] = n
							if show_networks:
								network_matches.append({'term': cidr_display, 'matches': term_matches})

					if show_unique_vlans and vlan_objects_by_id:
						unique_vlan_networks = sorted(
							(
								{
									'vlan': vlan_objects_by_id[vid],
									'unique_ip_count': len(vlan_unique_ips[vid]),
								}
								for vid in vlan_objects_by_id
							),
							key=lambda row: (
								(row['vlan'].comment or '').lower(),
								str(row['vlan'].ip_address),
								row['vlan'].subnet_mask,
							),
						)

				for term in unique_terms:
					if term in ipv6_terms:
						continue
					norm = ipv4_by_term.get(term)
					host_hit = bool(show_hosts and norm and norm in matched_host_norms)
					net_hit = bool((show_networks or show_unique_vlans) and term in network_hit_terms)
					if not host_hit and not net_hit:
						not_ip_addresses.append(term)

				for cidr_display, user_net in subnet_entries:
					net_hit = bool((show_networks or show_unique_vlans) and cidr_display in network_hit_terms)
					if not net_hit:
						not_ip_addresses.append(cidr_display)

	return render(request, 'cmdb_ip_sok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'host_matches': host_matches,
		'network_matches': network_matches,
		'search_term': search_term_display,
		'not_ip_addresses': not_ip_addresses,
		'show_hosts': show_hosts,
		'show_networks': show_networks,
		'show_unique_vlans': show_unique_vlans,
		'unique_vlan_networks': unique_vlan_networks,
		'ipv6_terms': sorted(ipv6_terms),
	})


def alle_klienter(request):
	#Søke og vise alle klienter
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('device_search_term', '').strip()  # strip removes trailing and leading space

	if search_term == '':
		maskiner = None
	elif search_term == '__all__':
		maskiner = CMDBdevice.objects.filter(device_type="KLIENT")
	else:
		# 2026-06-21: Search hostname, OS fields, and client model – matches visible columns and stats links.
		maskiner = CMDBdevice.objects.filter(device_type="KLIENT").filter(
			Q(comp_name__icontains=search_term)
			| Q(comp_os_readable__icontains=search_term)
			| Q(comp_os__icontains=search_term)
			| Q(comp_os_version__icontains=search_term)
			| Q(client_model_id__icontains=search_term)
		)

	alle_cmdb_klienter = CMDBdevice.objects.filter(device_type="KLIENT").count()


	# 2026-06-21: OS/model stats only when no search – avoids misleading aggregates on filtered results.
	maskiner_os_stats = []
	maskiner_model_stats = []
	if search_term == '':
		stat_maskiner = CMDBdevice.objects.filter(device_type="KLIENT")
		maskiner_os_stats = stat_maskiner.values('comp_os_readable').annotate(Count('comp_os_readable'))
		maskiner_os_stats = sorted(maskiner_os_stats, key=lambda os: os['comp_os_readable__count'], reverse=True)
		maskiner_model_stats = stat_maskiner.values('client_model_id').annotate(Count('client_model_id'))
		maskiner_model_stats = sorted(maskiner_model_stats, key=lambda os: os['client_model_id__count'], reverse=True)

	if maskiner != None:
		maskiner = maskiner.order_by('comp_name')

	return render(request, 'cmdb_maskiner_klienter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'maskiner': maskiner,
		'device_search_term': search_term,
		'alle_cmdb_klienter': alle_cmdb_klienter,
		'maskiner_os_stats': maskiner_os_stats,
		'maskiner_model_stats': maskiner_model_stats,
		'integrasjonsstatus': _integrasjonsstatus("sp_klienter"),
	})



def cmdb_installert_programvare(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import requests as api_requests
	from azure.identity import ClientSecretCredential

	results = []
	error_message = None
	columns = []

	try:
		credential = ClientSecretCredential(
			tenant_id=os.environ['AZURE_TENANT_ID'],
			client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
			client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
		)
		token = credential.get_token("https://api.securitycenter.microsoft.com/.default").token

		kql_query = (
			'let LatestDeviceInfo = DeviceInfo | summarize arg_max(Timestamp, *) by DeviceId;'
			'let OracleInventory = DeviceTvmSoftwareInventory'
			' | where SoftwareVendor =~ "oracle"'
			' | join kind=leftouter LatestDeviceInfo on DeviceId'
			' | project DeviceId, DeviceName, DeviceType, OSPlatform, SoftwareVendor, SoftwareName, SoftwareVersion, JoinType, OnboardingStatus, LastSeen=Timestamp;'
			'OracleInventory'
			' | join kind=leftouter DeviceTvmSoftwareEvidenceBeta on DeviceId, SoftwareVendor, SoftwareName'
			' | project DeviceName, OSPlatform, SoftwareVendor, SoftwareName, SoftwareVersion, DiskPaths, LastSeen'
		)

		response = api_requests.post(
			"https://api.security.microsoft.com/api/advancedqueries/run",
			headers={
				"Authorization": f"Bearer {token}",
				"Content-Type": "application/json",
			},
			json={"Query": kql_query},
			timeout=120,
		)

		if response.status_code == 200:
			data = response.json()
			columns = [col["Name"] for col in data.get("Schema", [])]
			results = data.get("Results", [])
			for row in results:
				if row.get("LastSeen"):
					try:
						dt = datetime.datetime.fromisoformat(row["LastSeen"].replace("Z", "+00:00"))
						row["LastSeenDisplay"] = dt.strftime("%d.%m.%Y %H:%M")
						row["LastSeenSort"] = dt.strftime("%Y-%m-%d %H:%M")
					except (ValueError, AttributeError):
						row["LastSeenDisplay"] = row["LastSeen"]
						row["LastSeenSort"] = row["LastSeen"]
		else:
			error_message = f"API-kall feilet med HTTP {response.status_code}: {response.text[:500]}"

	except Exception as e:
		error_message = f"Feil ved henting av data: {e}"

	return render(request, 'cmdb_installert_programvare.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'results': results,
		'columns': columns,
		'error_message': error_message,
		'antall_resultater': len(results),
	})


def sikkerhet_device_code_logins(request):
	# 2026-06-19: Device code sign-ins via Microsoft Graph auditLogs/signIns (AuditLog.Read.All).
	# 2026-06-19: History summary from DeviceCodeSignInCombo (hourly sync).
	# 2026-06-29: Overview only (hourly history); live Graph search moved to sikkerhet_device_code_logins_sanntid.
	from systemoversikt.device_code_signins import (
		DEVICE_CODE_HISTORY_DAYS,
		build_device_code_history_summary,
		device_code_internal_ip_prefixes,
	)

	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	internal_ip_prefixes = device_code_internal_ip_prefixes()

	since_history = timezone.now() - datetime.timedelta(days=DEVICE_CODE_HISTORY_DAYS)
	history_combos = DeviceCodeSignInCombo.objects.filter(last_seen__gte=since_history)
	history_rows = build_device_code_history_summary(history_combos)

	integrasjon = _integrasjonsstatus("device_code_signins")

	return render(request, 'rapport_device_code_logins.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'internal_ip_prefixes': internal_ip_prefixes,
		'history_rows': history_rows,
		'history_dager': DEVICE_CODE_HISTORY_DAYS,
		'integrasjon': integrasjon,
	})


def sikkerhet_device_code_logins_sanntid(request):
	# 2026-06-29: Live Graph search (slow); always 30 days – independent of hourly sync lookback.
	from systemoversikt.device_code_signins import (
		DEVICE_CODE_LIVE_SEARCH_DAYS,
		DEVICE_CODE_LIVE_SEARCH_MAX_RESULTS,
		device_code_internal_ip_prefixes,
		fetch_device_code_signins_from_graph,
		signin_to_display_row,
	)

	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	dager = DEVICE_CODE_LIVE_SEARCH_DAYS
	try:
		sign_ins, truncated, error_message = fetch_device_code_signins_from_graph(
			dager=dager,
			max_results=DEVICE_CODE_LIVE_SEARCH_MAX_RESULTS,
		)
		results = [signin_to_display_row(sign_in) for sign_in in sign_ins]
		results.sort(key=lambda row: row.get("TimeGeneratedSort") or "", reverse=True)
	except Exception as e:
		results = []
		truncated = False
		error_message = f"Feil ved henting av data: {e}"

	unike_brukere = len({row.get("UserPrincipalName") for row in results if row.get("UserPrincipalName")})
	app_counter = Counter(row.get("AppDisplayName") or "(ukjent)" for row in results)
	app_counts = app_counter.most_common(15)
	internal_ip_prefixes = device_code_internal_ip_prefixes()

	return render(request, 'rapport_device_code_logins_sanntid.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'results': results,
		'error_message': error_message,
		'antall_resultater': len(results),
		'unike_brukere': unike_brukere,
		'app_counts': app_counts,
		'dager': dager,
		'truncated': truncated,
		'max_results': DEVICE_CODE_LIVE_SEARCH_MAX_RESULTS,
		'internal_ip_prefixes': internal_ip_prefixes,
	})


def sikkerhet_varsling_virksomheter(request):
	# 2026-06-21: CSIRT alert to virksomhet security contacts (sikkerhetsanalytiker only).
	# 2026-06-21: Only log to ApplicationLog after successful live send (not on SMTP failure).
	from systemoversikt.csirt_varsling import (
		CSIRT_VARSLING_DRY_RUN,
		SIKKERHETSANALYTIKER_GROUP,
		csirt_email_address,
		append_varsling_footer,
		log_csirt_varsling_to_application_log,
		plan_security_alert_to_virksomheter,
		security_contact_emails_for_virksomhet,
		send_security_alert_to_virksomheter,
		user_is_sikkerhetsanalytiker,
	)

	if not user_is_sikkerhetsanalytiker(request.user):
		return render(request, '403.html', {
			'required_permissions': [SIKKERHETSANALYTIKER_GROUP],
			'groups': request.user.groups,
		})

	virksomheter = (
		Virksomhet.objects
		.filter(ordinar_virksomhet=True)
		.order_by('virksomhetsforkortelse')
		.prefetch_related(
			'varslingsmottak_sikkerhet_ref__brukernavn__profile',
			'informasjonssikkerhetskoordinator__brukernavn__profile',
			'ikt_kontakt__brukernavn__profile',
		)
	)

	virksomhet_rows = []
	for virksomhet in virksomheter:
		contact_emails, contact_source = security_contact_emails_for_virksomhet(virksomhet)
		virksomhet_rows.append({
			'virksomhet': virksomhet,
			'contact_count': len(contact_emails),
			'contact_emails': contact_emails,
			'contact_source': contact_source,
		})

	subject = ''
	body = ''
	# 2026-06-21: No virksomheter pre-selected – user must opt in (e.g. Velg alle).
	selected_pks = set()
	delivery_preview = None
	send_succeeded = False
	send_failed = False
	send_error = ''

	if request.method == 'POST':
		subject = request.POST.get('subject', '').strip()
		body = request.POST.get('body', '').strip()
		selected_pks = set(request.POST.getlist('virksomheter'))
		errors = []

		if not subject:
			errors.append('Tittel er påkrevd.')
		elif len(subject) > 200:
			errors.append('Tittel kan være maks 200 tegn.')
		if not body:
			errors.append('Meldingstekst er påkrevd.')
		if not selected_pks:
			errors.append('Velg minst én virksomhet.')

		if not CSIRT_VARSLING_DRY_RUN:
			try:
				csirt_email_address()
			except KeyError:
				errors.append('CSIRT-avsenderadresse er ikke konfigurert (CSIRT_EMAIL_ADDR).')

		if not errors:
			selected_virksomheter = [
				row['virksomhet']
				for row in virksomhet_rows
				if str(row['virksomhet'].pk) in selected_pks
			]
			try:
				sender = request.user.get_full_name() or request.user.username
				delivery_body = append_varsling_footer(body, sender)
				delivery_preview = plan_security_alert_to_virksomheter(
					selected_virksomheter,
					subject,
					delivery_body,
				)
				if CSIRT_VARSLING_DRY_RUN:
					log_csirt_varsling_to_application_log(
						request.user.username,
						subject,
						delivery_body,
						delivery_preview,
						dry_run=True,
					)
					messages.info(
						request,
						f'Tørrkjøring: Ville sendt 1 e-post til '
						f'{delivery_preview["recipient_total"]} mottaker(e). Ingen e-post ble sendt.',
					)
				else:
					send_security_alert_to_virksomheter(
						selected_virksomheter,
						subject,
						delivery_body,
					)
					log_csirt_varsling_to_application_log(
						request.user.username,
						subject,
						delivery_body,
						delivery_preview,
						dry_run=False,
					)
					send_succeeded = True
					messages.success(
						request,
						f'Sendte 1 e-post til {delivery_preview["recipient_total"]} mottaker(e). '
						f'{len(delivery_preview["skipped"])} virksomhet(er) hoppet over (ingen sikkerhetskontakter).',
					)
			except Exception as exc:
				delivery_preview = None
				send_failed = True
				send_error = str(exc)
		else:
			for error in errors:
				messages.error(request, error)

	csirt_configured = True
	try:
		csirt_email_address()
	except KeyError:
		csirt_configured = False

	return render(request, 'sikkerhet_varsling_virksomheter.html', {
		'request': request,
		'required_permissions': [SIKKERHETSANALYTIKER_GROUP],
		'virksomhet_rows': virksomhet_rows,
		'subject': subject,
		'body': body,
		'selected_pks': selected_pks,
		'delivery_preview': delivery_preview,
		'send_succeeded': send_succeeded,
		'send_failed': send_failed,
		'send_error': send_error,
		'csirt_configured': csirt_configured,
		'dry_run': CSIRT_VARSLING_DRY_RUN,
	})


def cmdb_internetteksponerte_servere(request):
	#Søke og vise alle maskiner
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	dager_gamle = 30
	tidsgrense = datetime.date.today() - datetime.timedelta(days=dager_gamle)
	servere = CMDBdevice.objects.filter(eksternt_eksponert_dato__gte=tidsgrense).order_by("-eksternt_eksponert_dato")

	return render(request, 'cmdb_internetteksponerte_servere.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'servere': servere,
		'integrasjonsstatus': _integrasjonsstatus("sp_network_eq"),
	})



def alle_servere(request):
	#Søke og vise alle maskiner
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('device_search_term', '').strip()  # strip removes trailing and leading space

	if search_term == '':
		maskiner = None
	elif search_term == '__all__':
		maskiner = CMDBdevice.objects.filter(device_type="SERVER")
	else:
		# 2026-06-21: Also match primary and linked CMDB IP addresses (partial, e.g. 10.20.).
		maskiner = CMDBdevice.objects.filter(device_type="SERVER").filter(
			Q(comp_name__icontains=search_term)
			| Q(comp_os_readable__iexact=search_term)
			| Q(service_offerings__navn__icontains=search_term)
			| Q(comp_ip_address__icontains=search_term)
			| Q(network_ip_address__ip_address__icontains=search_term)
		).distinct().order_by('comp_name')

	# 2026-06-21: OS/BSS stats only when no search – avoids full-fleet breakdown alongside filtered results.
	maskiner_stats = []
	bss_stats = []
	if search_term == '':
		maskiner_stats = CMDBdevice.objects.filter(device_type="SERVER").values('comp_os_readable').annotate(Count('comp_os_readable'))
		maskiner_stats = sorted(maskiner_stats, key=lambda os: os['comp_os_readable__count'], reverse=True)
		bss_stats = list(
			CMDBRef.objects.filter(servers__device_type="SERVER")
			.exclude(navn='')
			.values('navn')
			.annotate(server_count=Count('servers', filter=Q(servers__device_type="SERVER"), distinct=True))
		)
		bss_stats = sorted(bss_stats, key=lambda row: row['server_count'], reverse=True)

	vis_detaljer = True if request.GET.get('details') == "show" else False

	return render(request, 'cmdb_maskiner_servere.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'maskiner': maskiner,
		'device_search_term': search_term,
		'maskiner_stats': maskiner_stats,
		'bss_stats': bss_stats,
		'vis_detaljer': vis_detaljer,
		'integrasjonsstatus': _integrasjonsstatus("sp_virtual_machines"),
	})



def valgbarekategorier(request):
	#Vise noen linker knyttet til admin-panel. Valgfelt brukt i skjema.
	required_permissions = None

	return render(request, 'cmdb_valgbarekategorier.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})




def alle_databaser(request):
	#Søke og vise alle databaser
	required_permissions = ['systemoversikt.view_cmdbdatabase']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space

	if search_term == "__all__":
		databaser = CMDBdatabase.objects.filter(db_operational_status=1)
	elif len(search_term) < 2: # if one or less, return nothing
		databaser = CMDBdatabase.objects.none()
	else:
		databaser = CMDBdatabase.objects.filter(db_operational_status=1).filter(
				Q(db_database__icontains=search_term) |
				Q(sub_name__navn__icontains=search_term) |
				Q(db_version__icontains=search_term)
			)

	databaser = databaser.order_by('db_database')

	for d in databaser:
		try:
			server_str = d.db_comments.split("@")[1]
		except:
			server_str = None
		d.server_str = server_str # dette legger bare til et felt. Vi skriver ingen ting her.

	def cmdb_os_stats(maskiner):
		maskiner_stats = []
		for os in os_major:
			maskiner_stats.append({
				'major': os['db_version'],
				'count': os['db_version__count']
			})
		return sorted(maskiner_stats, key=lambda os: os['db_version'], reverse=True)

	databaseversjoner = CMDBdatabase.objects.filter(db_operational_status=True).values('db_version').distinct().annotate(Count('db_version'))
	databasestatistikk = []
	for versjon in databaseversjoner:
		if versjon["db_version"] == "":
			versjon["db_version"] = "ukjent"
		databasestatistikk.append({
				'versjon': versjon["db_version"],
				'antall': versjon["db_version__count"]
			})
	databasestatistikk = sorted(databasestatistikk, key=lambda v: v['antall'], reverse=True)

	return render(request, 'cmdb_databaser_sok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'databaser': databaser,
		'search_term': search_term,
		'databasestatistikk': databasestatistikk,
		'integrasjonsstatus_list': _integrasjonsstatus_flere("sp_database_mssql", "sp_database_oracle"),
	})



def alle_cmdbref(request):
	#Søke og vise alle business services (bs)
	required_permissions = ['systemoversikt.view_cmdbref', 'auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	cmdbref = CMDBRef.objects.filter(operational_status=True, parent_ref__eksponert_for_bruker=True).order_by("service_classification", "parent_ref__navn", Lower("navn"))

	return render(request, 'cmdb_bs_sok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'cmdbref': cmdbref,
		'integrasjonsstatus': _integrasjonsstatus("sp_business_services"),
	})


def cmdb_bs_detaljer(request):
	required_permissions = ['systemoversikt.view_cmdbref', 'auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term', "").strip()

	cmdbref_qs = CMDBRef.objects.select_related("parent_ref").prefetch_related(
		Prefetch(
			"system",
			queryset=System.objects.select_related(
				"systemforvalter",
				"systemforvalter_avdeling_referanse",
				"driftsmodell_foreignkey",
			).prefetch_related("systemtyper"),
		),
		Prefetch(
			"servers",
			queryset=CMDBdevice.objects.only("id", "comp_name").order_by("comp_name"),
		),
	).annotate(
		server_count=Count("servers", distinct=True),
		database_count=Count(
			"cmdbdatabase_sub_name",
			filter=Q(cmdbdatabase_sub_name__db_operational_status=True),
			distinct=True,
		),
	)

	if search_term == "__all__":
		cmdbref = cmdbref_qs.order_by("parent_ref__navn", Lower("navn"))
	elif len(search_term) < 1:
		cmdbref = cmdbref_qs.filter(
			operational_status=True,
			parent_ref__eksponert_for_bruker=True,
		).order_by("parent_ref__navn", Lower("navn"))
	else:
		cmdbref = cmdbref_qs.filter(
			Q(navn__icontains=search_term) | Q(parent_ref__navn__icontains=search_term)
		).order_by("parent_ref__navn", Lower("navn"))

	return render(request, 'cmdb_bs_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'cmdbref': cmdbref,
		'search_term': search_term,
		'integrasjonsstatus': _integrasjonsstatus("sp_business_services"),
	})

def cmdb_servere_flere_offerings(request):
	required_permissions = ['systemoversikt.view_cmdbref', 'auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	# telle servere med flere service offerings-koblinger
	from django.db.models import Count
	servere_flere_offerings = CMDBdevice.objects.annotate(num_offerings=Count('service_offerings')).filter(num_offerings__gt=1)
	servere_flereennto_offerings = CMDBdevice.objects.annotate(num_offerings=Count('service_offerings')).filter(num_offerings__gt=2)

	return render(request, 'cmdb_servere_flere_offerings.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'servere_flere_offerings': servere_flere_offerings,
		'servere_flereennto_offerings': servere_flereennto_offerings,
		'integrasjonsstatus': _integrasjonsstatus("sp_business_services"),
	})


def cmdb_bs_aktuelle_ikke_koblet(request):
	required_permissions = ['systemoversikt.view_cmdbref', 'auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet_uke = Virksomhet.objects.get(virksomhetsforkortelse="UKE")
	system_uten_bs = (System.objects
			.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet_uke)
			.filter(driftsmodell_foreignkey__overordnet_plattform=None)
			.filter(service_offerings=None) # skal ikke ha kobling
			.filter(systemtyper__er_infrastruktur=False)
			.filter(ibruk=True)
			.order_by('driftsmodell_foreignkey')
			.distinct()
	)

	return render(request, 'cmdb_bs_aktuelle_ikke_koblet.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'system_uten_bs': system_uten_bs,
		'integrasjonsstatus': _integrasjonsstatus("sp_business_services"),
	})

def cmdb_bs_skjult_relevant(request):
	required_permissions = ['systemoversikt.view_cmdbref', 'auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	skjult_server_db = []
	skjult_server_db_candidates = (CMDBbs.objects
			.filter(operational_status=True)
			.filter(eksponert_for_bruker=False)
			.distinct()
	)
	for bs in skjult_server_db_candidates:
		if bs.ant_devices() > 0 or bs.ant_databaser() > 0:
			skjult_server_db.append(bs)

	return render(request, 'cmdb_bs_skjult_relevant.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'skjult_server_db': skjult_server_db,
		'integrasjonsstatus': _integrasjonsstatus("sp_business_services"),
	})


def cmdb_bs_mangler_kobling(request):
	required_permissions = ['systemoversikt.view_cmdbref', 'auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	bs_uten_system = CMDBRef.objects.filter(operational_status=True).filter(Q(system=None)).order_by("-parent_ref__eksponert_for_bruker", "service_classification")

	return render(request, 'cmdb_bs_mangler_kobling.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'bs_uten_system': bs_uten_system,
		'integrasjonsstatus': _integrasjonsstatus("sp_business_services"),
	})



def cmdb_bs_koblet_ukjent_plattform(request):
	required_permissions = ['systemoversikt.view_cmdbref', 'auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet_uke = Virksomhet.objects.get(virksomhetsforkortelse="UKE")

	bs_utenfor_fip = (System.objects
			.filter(~Q(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet_uke))
			.filter(~Q(service_offerings=None)) # må ha kobling
			.filter(systemtyper__er_infrastruktur=False)
			.filter(ibruk=True)
			.order_by('driftsmodell_foreignkey')
			.distinct()
	)

	return render(request, 'cmdb_bs_koblet_ukjent_plattform.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'bs_utenfor_fip': bs_utenfor_fip,
		'integrasjonsstatus': _integrasjonsstatus("sp_business_services"),
	})

def cmdb_bskobling_utfaset(request):
	required_permissions = ['systemoversikt.view_cmdbref', 'auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	utfasede_bs = CMDBRef.objects.filter(operational_status=False).filter(~Q(system=None))

	return render(request, 'cmdb_bskobling_utfaset.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'utfasede_bs': utfasede_bs,
		'integrasjonsstatus': _integrasjonsstatus("sp_business_services"),
	})


def cmdb_bss(request, pk):
	#Søke og vise maskiner og databaser tilknyttet en business service for et system
	required_permissions = ['systemoversikt.view_cmdbref']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	cmdbref = CMDBRef.objects.get(pk=pk)
	cmdbdevices = CMDBdevice.objects.filter(service_offerings=cmdbref)
	databaser = CMDBdatabase.objects.filter(sub_name=cmdbref)

	vlan_lagt_til = []
	def identifiser_vlan(network_ip_addresses):
		if len(network_ip_addresses) > 0:
			if len(network_ip_addresses[0].vlan.all()) > 0:
				mest_presise_vlan = network_ip_addresses[0].vlan.all().order_by('-subnet_mask')[0]
				nonlocal graf_data
				nonlocal vlan_lagt_til

				if mest_presise_vlan.comment not in vlan_lagt_til:
					graf_data["nodes"].append({"data": { "id": mest_presise_vlan.comment }})
					vlan_lagt_til.append(mest_presise_vlan.comment)
				return mest_presise_vlan.comment
		return "Ukjent VLAN"

	graf_data = {"nodes": [], "edges": []}
	graf_data["nodes"].append({"data": { "id": "root_parent", "name": cmdbref.navn, "shape": "ellipse", "color": "black" }})

	for server in cmdbdevices:
		graf_data["nodes"].append(
						{"data": {
							"parent": identifiser_vlan(server.network_ip_address.all()),
							"id": "server"+str(server.pk),
							"name": server.comp_name,
							"shape": "ellipse",
							"color": "#1668c1"
							}
						})
		graf_data["edges"].append(
						{"data": {
							"source": "server"+str(server.pk),
							"target": "root_parent",
							"linestyle": "solid",
							"linecolor": "#1668c1",
							}
						})

	for db in databaser:
		#try:
		try:
			dbserver = CMDBdevice.objects.get(comp_name=db.db_server)
		except:
			messages.warning(request, f"Serveren {db.db_server} for databasen {db} finnes ikke.")
			continue
		network_ip_address = dbserver.network_ip_address.all()
		#except:
		#   network_ip_address = []
		graf_data["nodes"].append(
						{"data": {
							"parent": identifiser_vlan(network_ip_address),
							"id": "db"+str(db.pk),
							"name": db.db_database,
							"shape": "diamond",
							"color": "#d35215" }
						})
		graf_data["edges"].append(
						{"data": {
							"source": "db"+str(db.pk),
							"target": "root_parent",
							"linestyle": "solid",
							"linecolor": "#d35215",
							}
						})


	backup_inst = CMDBbackup.objects.filter(device__service_offerings=cmdbref)

	return render(request, 'cmdb_maskiner_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'cmdbref': [cmdbref],
		'cmdbdevices': cmdbdevices,
		'databaser': databaser,
		'graf_data': graf_data,
		'backup_inst': backup_inst,
		'integrasjonsstatus': _integrasjonsstatus("sp_business_services"),
	})


def cmdb_bs_disconnect(request):
	# frikoble alle system - business service-koblinger
	required_permissions = ['systemoversikt.delete_system'] # kun administrator-rollen
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	#for service in CMDBbs.objects.all():
	#   service.systemreferanse = None
	#   service.save()

	from django.http import HttpResponseRedirect
	return HttpResponseRedirect(reverse('alle_cmdbref_sok'))


def alle_avtaler(request, virksomhet=None):
	#Vise alle avtaler
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	avtaler = Avtale.objects.all()
	if virksomhet:
		virksomhet = Virksomhet.objects.get(pk=virksomhet)
		avtaler = avtaler.filter(Q(virksomhet=virksomhet) | Q(leverandor_intern=virksomhet))

	return render(request, 'avtale_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'avtaler': avtaler,
		'virksomhet': virksomhet,
	})



def avtaledetaljer(request, pk):
	#Vise detaljer for en avtale
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	avtale = Avtale.objects.get(pk=pk)

	return render(request, 'avtale_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'avtale': avtale,
	})



def databehandleravtaler_virksomhet(request, pk):
	#Vise alle databehandleravtaler for en valgt virksomhet
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomet = Virksomhet.objects.get(pk=pk)
	utdypende_beskrivelse = ("Viser databehandleravtaler for %s" % virksomet)
	avtaler = Avtale.objects.filter(virksomhet=pk).filter(avtaletype=1) # 1 er databehandleravtaler

	return render(request, 'avtale_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'avtaler': avtaler,
		'utdypende_beskrivelse': utdypende_beskrivelse,
	})



def ad(request):
	#Startside for LDAP/AD-spørringer
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	return render(request, 'ad_index.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})



def ad_details(request, name):
	#Søke opp en eksakt CN i AD
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	runtime_t0 = time.time()
	ldap_filter = ('(cn=%s)' % name)
	result = ldap_get_details(name, ldap_filter, request)
	runtime_t1 = time.time()
	logg_total_runtime = runtime_t1 - runtime_t0
	messages.success(request, 'Dette søket tok %s sekunder' % round(logg_total_runtime, 1))

	return render(request, 'ad_details.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'result': result,
	})



def ad_exact(request, name):
	#Søke opp et eksakt DN i AD
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	runtime_t0 = time.time()
	ldap_filter = ('(distinguishedName=%s)' % name)
	result = ldap_get_details(name, ldap_filter, request)
	runtime_t1 = time.time()
	logg_total_runtime = runtime_t1 - runtime_t0
	messages.success(request, 'Dette søket tok %s sekunder' % round(logg_total_runtime, 1))

	return render(request, 'ad_details.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'result': result,
	})



def recursive_group_members(request, group):
	#Søke opp alle brukere rekursivt med tilgang til et DN i AD
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	runtime_t0 = time.time()
	result = ldap_get_recursive_group_members(group)
	runtime_t1 = time.time()
	logg_total_runtime = runtime_t1 - runtime_t0
	messages.success(request, 'Dette søket tok %s sekunder' % round(logg_total_runtime, 1))

	return render(request, 'ad_recursive.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'result': result,
	})


"""
def tilgangsgrupper_api(request): #API
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="api_tilgangsgrupper").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
	try:
		owner = APIKeys.objects.get(key=key).navn
	except MultipleObjectsReturned:
		owner = "Flere treff på nøkkeleier"

	source_ip = get_client_ip(request)
	ApplicationLog.objects.create(event_type="API AD-grupper", message=f"Nøkkel tilhørende {owner} fra {source_ip}")

	if not "gruppenavn" in request.GET:
		return JsonResponse({"message": "Du må oppgi et gruppenavn som GET-variabel. ?gruppenavn=<navn>", "data": None}, safe=False, status=204)

	sporring = request.GET["gruppenavn"]
	try:
		adgruppe = ADgroup.objects.get(common_name__iexact=sporring)
	except MultipleObjectsReturned:
		return JsonResponse({"spørring": sporring, "status": "Spørringen gav flere treff. Dette burde ikke skje og bør undersøkes.", "data": []}, safe=False, status=204)
	except ObjectDoesNotExist:
		return JsonResponse({"spørring": sporring, "status": "Spørringen gav ingen treff. Vennligst oppgi et gyldig gruppenavn.", "data": []}, safe=False, status=204)
	except:
		return JsonResponse({"spørring": sporring, "status": "Ukjent feil", "data": []}, safe=False, status=500)
	data = {}

	def user_lookup(user):
		try:
			username = re.search(r'cn=([^\,]*)', user, re.I).groups()[0]
			user = User.objects.get(username__iexact=username)
			virksomhet = user.profile.virksomhet.virksomhetsforkortelse if user.profile.virksomhet else "Ukjent"
			return {
					"medlem": user.username,
					"status": "Treff på bruker i AD",
					"user_full_name": user.profile.displayName,
					"user_from_prk": user.profile.from_prk,
					"user_last_loggon": user.profile.lastLogonTimestamp,
					"user_passwd_expire": user.profile.userPasswordExpiry,
					"user_created": user.profile.whenCreated,
					"user_virksomhet": virksomhet,
					"user_description": user.profile.description,
					"user_disabled": user.profile.accountdisable,
					"user_passwd_never_expire": user.profile.dont_expire_password,
				}
		except ObjectDoesNotExist:
			return {
					"medlem": username,
					"status": "Ingen treff på bruker i AD. Kanskje objektet er en tilgangsgruppe?",
					"user_full_name": None,
					"user_from_prk": None,
					"user_last_loggon": None,
					"user_passwd_expire": None,
					"user_created": None,
					"user_virksomhet": None,
					"user_description": None,
					"user_disabled": None,
					"user_passwd_never_expire": None,
					}

	medlemmer = [user_lookup(user) for user in json.loads(adgruppe.member)]
	memberof = [user_lookup(mo) for mo in json.loads(adgruppe.memberof)]

	data['common_name'] = adgruppe.common_name
	data['distinguishedname'] = adgruppe.distinguishedname
	data['sist_oppdatert'] = adgruppe.sist_oppdatert
	data['description'] = adgruppe.description
	data['membercount'] = adgruppe.membercount
	data['from_prk'] = adgruppe.from_prk
	data['mail_enabled'] = adgruppe.mail
	data['medlemmer'] = medlemmer
	data['memberof'] = memberof

	resultat = {"spørring": sporring, "data": data}
	return JsonResponse(resultat, safe=False, status=200)
"""


def tilgangsgrupper_api_optimized(request):
	if request.method != "GET":
		raise Http404

	# --- API key logic unchanged ---
	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="api_tilgangsgrupper").values_list("key", flat=True)
	if key not in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
	try:
		owner = APIKeys.objects.get(key=key).navn
	except MultipleObjectsReturned:
		owner = "Flere treff på nøkkeleier"

	source_ip = get_client_ip(request)

	if "gruppenavn" not in request.GET:
		ApplicationLog.objects.create(event_type="API AD-grupper", message=f"Nøkkel tilhørende {owner} fra {source_ip}: status 400")
		return JsonResponse({"message": "Du må oppgi et gruppenavn som GET-variabel. ?gruppenavn=<navn>", "data": None}, safe=False, status=400)


	sporring = request.GET["gruppenavn"]
	try:
		adgruppe = ADgroup.objects.get(common_name__iexact=sporring)
	except MultipleObjectsReturned:
		ApplicationLog.objects.create(event_type="API AD-grupper", message=f"Nøkkel tilhørende {owner} fra {source_ip}: status 404 flere treff på {sporring}")
		return JsonResponse({"spørring": sporring, "status": "Spørringen gav flere treff. Dette burde ikke skje og bør undersøkes.", "data": []}, safe=False, status=404)
	except ObjectDoesNotExist:
		ApplicationLog.objects.create(event_type="API AD-grupper", message=f"Nøkkel tilhørende {owner} fra {source_ip}: status 404 ingen treff på {sporring}")
		return JsonResponse({"spørring": sporring, "status": "Spørringen gav ingen treff. Vennligst oppgi et gyldig gruppenavn.", "data": []}, safe=False, status=404)
	except:
		ApplicationLog.objects.create(event_type="API AD-grupper", message=f"Nøkkel tilhørende {owner} fra {source_ip}: status 500 ukjent feil på spørring {sporring}")
		return JsonResponse({"spørring": sporring, "status": "Ukjent feil", "data": []}, safe=False, status=500)

	# --- Extract members ---
	try:
		member_dns = json.loads(adgruppe.member) or []
	except json.JSONDecodeError:
		member_dns = []
	try:
		memberof_dns = json.loads(adgruppe.memberof) or []
	except json.JSONDecodeError:
		memberof_dns = []

	# Precompile regex
	dn_re = re.compile(r'cn=([^,]*)', re.I)

	def extract_username(dn):
		match = dn_re.search(dn)
		return match.group(1) if match else None

	member_usernames = [extract_username(dn) for dn in member_dns]
	memberof_usernames = [extract_username(dn) for dn in memberof_dns]
	all_usernames = {u.lower() for u in member_usernames + memberof_usernames if u}

	# --- Bulk query for all users ---
	users = (
		User.objects
		.annotate(username_l=Lower("username"))
		.filter(username_l__in=all_usernames)
		.select_related("profile__virksomhet")
	)
	user_map = {u.username.lower(): u for u in users}

	def build_user(username):
		if not username:
			return {"medlem": None, "status": "Ugyldig DN", **empty_user_fields()}
		user = user_map.get(username.lower())
		if user:
			p = user.profile
			virksomhet = p.virksomhet.virksomhetsforkortelse if p.virksomhet else "Ukjent"
			return {
				"medlem": user.username,
				"status": "Treff på bruker i AD",
				"user_full_name": p.displayName,
				"user_from_prk": p.from_prk,
				"user_last_loggon": p.lastLogonTimestamp,
				"user_passwd_expire": p.userPasswordExpiry,
				"user_created": p.whenCreated,
				"user_virksomhet": virksomhet,
				"user_description": p.description,
				"user_disabled": p.accountdisable,
				"user_passwd_never_expire": p.dont_expire_password,
			}
		return {"medlem": username, "status": "Ingen treff på bruker i AD. Kanskje objektet er en tilgangsgruppe?", **empty_user_fields()}

	def empty_user_fields():
		return {
			"user_full_name": None,
			"user_from_prk": None,
			"user_last_loggon": None,
			"user_passwd_expire": None,
			"user_created": None,
			"user_virksomhet": None,
			"user_description": None,
			"user_disabled": None,
			"user_passwd_never_expire": None,
		}

	medlemmer = [build_user(u) for u in member_usernames]
	memberof = [build_user(u) for u in memberof_usernames]

	data = {
		"common_name": adgruppe.common_name,
		"distinguishedname": adgruppe.distinguishedname,
		"sist_oppdatert": adgruppe.sist_oppdatert,
		"description": adgruppe.description,
		"membercount": adgruppe.membercount,
		"from_prk": adgruppe.from_prk,
		"mail_enabled": adgruppe.mail,
		"medlemmer": medlemmer,
		"memberof": memberof,
	}

	ApplicationLog.objects.create(event_type="API AD-grupper", message=f"Nøkkel tilhørende {owner} fra {source_ip}: status 200 OK for spørring {sporring}")
	return JsonResponse({"spørring": sporring, "data": data}, safe=False, status=200)




def systemer_api(request): #API

	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn="api_systemer").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False,status=403)

	data = []
	query = System.objects.filter(~Q(ibruk=False))
	for system in query:
		line = {}

		line["systemanvn"] = system.systemnavn
		line["alias"] = system.alias
		line["system_id"] = system.pk
		line["systemeierskapsmodell"] = system.get_systemeierskapsmodell_display()

		if system.systemeier:
			line["systemeier"] = system.systemeier.virksomhetsforkortelse
		if system.systemforvalter:
			line["systemforvalter"] = system.systemforvalter.virksomhetsforkortelse
		if system.driftsmodell_foreignkey:
			line["plattform"] = system.driftsmodell_foreignkey.navn

		kategoriliste = []
		for kategori in system.systemkategorier.all():
			kategoriliste.append(kategori.kategorinavn)
		line["systemkategorier"] = kategoriliste

		bruksliste = []
		for bruk in system.systembruk_system.all():
			bruksliste.append(bruk.brukergruppe.virksomhetsnavn)
		line["system_brukes_av"] = bruksliste

		data.append(line)

	resultat = {"antall systemer": len(query), "data": data}
	return JsonResponse(resultat, safe=False, status=200)




# Her kommer API-er benyttet av ny tjeneste og systemoversikt
# Developer docs: api_tjeneste_systemoversikt_docs.py (url name: api_tjeneste_systemoversikt_docs).
def api_systemer_optimized(request):  # tjeneste- og systemoversikt
	# 2026-06-23: Update api_tjeneste_systemoversikt_docs.py when changing /api/systemer/ or System JSON fields (url name: api_tjeneste_systemoversikt_docs).
	if request.method != "GET":
		raise Http404

	key = request.headers.get("key")
	allowed_keys = APIKeys.objects.filter(navn="tjenester_og_systemer").values_list("key", flat=True)
	if key not in allowed_keys:
		return JsonResponse(
			{"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None},
			safe=False, status=403
		)

	ApplicationLog.objects.create(
		event_type="api_systemer",
		message=f"Innkommende kall fra {get_client_ip(request)}"
	)
	runtime_t0 = time.time()

	query = (
		System.objects.all()
		.select_related(
			"systemeier",
			"systemforvalter",
			"driftsmodell_foreignkey",
			"systemforvalter_avdeling_referanse",
		)
		.prefetch_related(
			# collections
			"systemurl",
			"systemtyper",
			"programvarer",
			"LOSref",
			"kritisk_kapabilitet",
			"systemleverandor",
			"basisdriftleverandor",
			"applikasjonsdriftleverandor",
			"service_offerings",
			# contact persons + their user object to get email without extra hops
			"systemeier_kontaktpersoner_referanse__brukernavn",
			"systemforvalter_kontaktpersoner_referanse__brukernavn",
		)
	)

	data = []
	for system in query:
		# Read prefetched relations once (no extra queries)
		systemurls = [url.domene for url in system.systemurl.all()]
		systemtyper = [{"class": "Systemtype", "id": st.pk} for st in system.systemtyper.all()]
		programvarer = [{"class": "Programvare", "id": pv.pk} for pv in system.programvarer.all()]
		losref = [{"class": "LOS", "id": los.pk} for los in system.LOSref.all()]
		kapabilitet = [{"class": "KritiskKapabilitet", "id": k.pk} for k in system.kritisk_kapabilitet.all()]
		leverandor = [{"class": "Leverandor", "id": l.pk} for l in system.systemleverandor.all()]
		basisdrift = [{"class": "Leverandor", "id": l.pk} for l in system.basisdriftleverandor.all()]
		applikasjonsdrift = [{"class": "Leverandor", "id": l.pk} for l in system.applikasjonsdriftleverandor.all()]
		offerings_external = [off.bss_external_ref for off in system.service_offerings.all()]
		offerings_names = [off.navn for off in system.service_offerings.all()]

		systemeier_kontakter = [
			ansvarlig.brukernavn.email
			for ansvarlig in system.systemeier_kontaktpersoner_referanse.all()
		]
		systemforvalter_kontakter = [
			ansvarlig.brukernavn.email
			for ansvarlig in system.systemforvalter_kontaktpersoner_referanse.all()
		]

		line = {
			"class": "System",
			"id": system.pk,
			"kartotek_url": f"https://kartoteket.oslo.kommune.no/systemer/detaljer/{system.pk}/",
			"opprettet": system.opprettet,
			"sist_oppdatert": system.sist_oppdatert,
			"navn": system.systemnavn,
			"visningsnavn": str(system),
			"alias": system.alias,
			"beskrivelse": system.systembeskrivelse,

			"livslop_status": system.get_livslop_status_display(),
			"ibruk": system.er_ibruk(),
			"urler": systemurls,
			"systemtyper": systemtyper,
			"programvarer": programvarer,

			"eierskapsmodell": system.get_systemeierskapsmodell_display(),
			"systemeier_virksomhet": {"class": "Virksomhet", "id": system.systemeier.id} if system.systemeier else None,
			"systemeier_kontaktpersoner": systemeier_kontakter,
			"systemforvalter_virksomhet": {"class": "Virksomhet", "id": system.systemforvalter.id} if system.systemforvalter else None,
			"systemforvalter_kontaktpersoner": systemforvalter_kontakter,
			"systemforvalter_orgenhet_ouid": (
				{
					"prk_ouid": system.systemforvalter_avdeling_referanse.ouid,
					"hr_navn": system.systemforvalter_avdeling_referanse.ou,
					"hr_ouid": system.systemforvalter_avdeling_referanse.hrouid,
				}
				if system.systemforvalter_avdeling_referanse
				else None
			),
			"forvaltning_epost": system.forvaltning_epost,
			"superbrukere": system.superbrukere,
			"nokkelpersonell": system.nokkelpersonell,

			"driftsplattform": {
				"class": "Driftsplattform",
				"id": system.driftsmodell_foreignkey.pk if system.driftsmodell_foreignkey else None,
			},
			"bool_egenutviklet": system.er_egenutviklet,
			"bool_saas": system.driftsmodell_foreignkey.er_saas if system.driftsmodell_foreignkey else False,
			"plattformklassifisering": {
				"id": system.driftsmodell_foreignkey.type_plattform,
				"navn": system.driftsmodell_foreignkey.get_type_plattform_display(),
			} if system.driftsmodell_foreignkey else None,

			"konfidensialitet": system.vis_konfidensialitet(),
			"tilgjengelighet": system.vis_tilgjengelighet(),
			"integritetsvurdering": system.vis_integritetsvurdering(),

			"teknisk_egnethet": system.get_teknisk_egnethet_display(),
			"strategisk_egnethet": system.get_strategisk_egnethet_display(),
			"funksjonell_egnethet": system.get_funksjonell_egnethet_display(),

			"kommune_los": losref,
			"dsb_kapabilitet": kapabilitet,

			"systemleverandor": leverandor,
			"basisdriftleverandor": basisdrift,
			"applikasjonsdriftleverandor": applikasjonsdrift,

			"service_offerings_external_id": offerings_external,
			"service_offerings_navn": offerings_names,
		}

		data.append(line)

	delta = round(time.time() - runtime_t0, 3)

	resultat = {
		"beskrivelse": (
			"System-objekter fra Kartoteket. For oversikt over virksomheter som bruker systemet, "
			"se klassen SystemBruk. systemforvalter_orgenhet_ouid er ID fra HR. Ved integrasjon kan "
			"hr_navn ignoreres og erstattes med data rett fra HR."
		),
		"antall": len(query),
		"kjoretid": f"{delta}",
		"data": data,
	}

	ApplicationLog.objects.create(
		event_type="api_systemer",
		message=f"kallet fra {get_client_ip(request)} tok {delta} sekunder."
	)
	return JsonResponse(resultat, safe=False, status=200)




def api_systemtyper(request): #tjeneste- og systemoversikt
	# 2026-06-23: Update api_tjeneste_systemoversikt_docs.py when changing /api/systemtyper/ or Systemtype JSON fields (url name: api_tjeneste_systemoversikt_docs).
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn="tjenester_og_systemer").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	ApplicationLog.objects.create(event_type="api_systemtyper", message=f"Innkommende kall fra {get_client_ip(request)}")
	runtime_t0 = time.time()
	data = []
	query = Systemtype.objects.all()
	for systemtype in query:
		line = {}

		line["class"] = "Systemtype"
		line["id"] = systemtype.pk
		line["opprettet"] = None
		line["sist_oppdatert"] = systemtype.sist_oppdatert
		line["navn"] = systemtype.kategorinavn
		line["definisjon"] = systemtype.definisjon
		line["bool_har_url"] = systemtype.har_url
		line["bool_er_infrastruktur"] = systemtype.er_infrastruktur
		line["bool_er_integrasjon"] = systemtype.er_integrasjon

		data.append(line)


	runtime_t1 = time.time()
	delta = round(runtime_t1 - runtime_t0, 3)

	resultat = {"beskrivelse": "Systemtype-objekter fra Karoteket. Angir hva slags egenskaper systemer har. Kan være mange til mange mot system.", "antall": len(query), "kjoretid": f"{delta}", "data": data}

	ApplicationLog.objects.create(event_type="api_systemtyper", message=f"kallet fra {get_client_ip(request)} tok {delta} sekunder.")
	return JsonResponse(resultat, safe=False, status=200)



def api_programvarer(request): #tjeneste- og systemoversikt
	# 2026-06-23: Update api_tjeneste_systemoversikt_docs.py when changing /api/programvarer/ or Programvare JSON fields (url name: api_tjeneste_systemoversikt_docs).
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn="tjenester_og_systemer").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	ApplicationLog.objects.create(event_type="api_programvarer", message=f"Innkommende kall fra {get_client_ip(request)}")
	runtime_t0 = time.time()
	data = []
	query = Programvare.objects.all()
	for program in query:
		line = {}

		line["class"] = "Programvare"
		line["id"] = program.pk
		line["opprettet"] = None
		line["sist_oppdatert"] = program.sist_oppdatert
		line["navn"] = program.programvarenavn
		line["alias"] = program.alias
		line["beskrivelse"] = program.programvarebeskrivelse
		line["leverandor"] = [{"class": "Leverandor", "id": leverandor.pk} for leverandor in program.programvareleverandor.all()]

		data.append(line)


	runtime_t1 = time.time()
	delta = round(runtime_t1 - runtime_t0, 3)

	resultat = {"beskrivelse": "Programvare-objekter fra Karoteket. Et system kan bestå av flere programvarer.", "antall": len(query), "kjoretid": f"{delta}", "data": data}

	ApplicationLog.objects.create(event_type="api_programvarer", message=f"kallet fra {get_client_ip(request)} tok {delta} sekunder.")
	return JsonResponse(resultat, safe=False, status=200)



def api_driftsplattformer(request): #tjeneste- og systemoversikt
	# 2026-06-23: Update api_tjeneste_systemoversikt_docs.py when changing /api/driftsplattformer/ or Driftsmodell JSON fields (url name: api_tjeneste_systemoversikt_docs).
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn="tjenester_og_systemer").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	ApplicationLog.objects.create(event_type="api_driftsplattformer", message=f"Innkommende kall fra {get_client_ip(request)}")
	runtime_t0 = time.time()
	data = []
	query = Driftsmodell.objects.all()
	for plattform in query:
		line = {}

		line["class"] = "Driftsmodell"
		line["id"] = plattform.pk
		line["opprettet"] = None
		line["sist_oppdatert"] = plattform.sist_oppdatert
		line["navn"] = plattform.navn
		line["eier_virksomhet"] = {"class": "Virksomhet", "id": plattform.ansvarlig_virksomhet.id} if plattform.ansvarlig_virksomhet else None
		line["kommentar"] = plattform.kommentar
		line["plattformklassifisering"] = {"id": plattform.type_plattform, "navn": plattform.get_type_plattform_display()}
		line["overordnet_plattform"] = {"class": "Driftsmodell", "id": plattform.overordnet_plattform.id} if plattform.overordnet_plattform else None
		line["bool_utviklingsplattform"] = plattform.utviklingsplattform
		line["bool_samarbeidspartner"] = plattform.samarbeidspartner
		line["bool_er_saas"] = plattform.er_saas

		data.append(line)


	runtime_t1 = time.time()
	delta = round(runtime_t1 - runtime_t0, 3)

	resultat = {"beskrivelse": "Driftsplattform-objekter fra Karoteket. Systemer kan bare være koblet til én driftsplattform.", "antall": len(query), "kjoretid": f"{delta}", "data": data}

	ApplicationLog.objects.create(event_type="api_driftsplattformer", message=f"kallet fra {get_client_ip(request)} tok {delta} sekunder.")
	return JsonResponse(resultat, safe=False, status=200)



def api_leverandorer(request): #tjeneste- og systemoversikt
	# 2026-06-23: Update api_tjeneste_systemoversikt_docs.py when changing /api/leverandorer/ or Leverandor JSON fields (url name: api_tjeneste_systemoversikt_docs).
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn="tjenester_og_systemer").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	ApplicationLog.objects.create(event_type="api_leverandorer", message=f"Innkommende kall fra {get_client_ip(request)}")
	runtime_t0 = time.time()
	data = []
	query = Leverandor.objects.all()
	for lev in query:
		line = {}

		line["class"] = "Leverandor"
		line["id"] = lev.pk
		line["opprettet"] = None
		line["sist_oppdatert"] = lev.sist_oppdatert
		line["navn"] = lev.leverandor_navn
		line["kontaktinfo"] = lev.kontaktpersoner
		line["orgnummer"] = lev.orgnummer
		line["notater"] = lev.notater

		data.append(line)


	runtime_t1 = time.time()
	delta = round(runtime_t1 - runtime_t0, 3)

	resultat = {"beskrivelse": "Leverandør-objekter fra Karoteket.", "antall": len(query), "kjoretid": f"{delta}", "data": data}

	ApplicationLog.objects.create(event_type="api_leverandorer", message=f"kallet fra {get_client_ip(request)} tok {delta} sekunder.")
	return JsonResponse(resultat, safe=False, status=200)



def api_systemintegrasjoner_optimized(request):  # tjeneste- og systemoversikt
	# 2026-06-23: Update api_tjeneste_systemoversikt_docs.py when changing /api/systemintegrasjoner/ or SystemIntegration JSON fields (url name: api_tjeneste_systemoversikt_docs).
	if request.method != "GET":
		raise Http404

	key = request.headers.get("key")
	allowed_keys = APIKeys.objects.filter(navn="tjenester_og_systemer").values_list("key", flat=True)
	if key not in allowed_keys:
		return JsonResponse(
			{"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None},
			safe=False, status=403
		)

	ApplicationLog.objects.create(
		event_type="api_systemintegrasjoner",
		message=f"Innkommende kall fra {get_client_ip(request)}"
	)
	runtime_t0 = time.time()

	query = (
		SystemIntegration.objects.all()
		.select_related("source_system", "destination_system")
	)

	data = []
	for integrasjon in query:
		line = {
			"class": "SystemIntegration",
			"id": integrasjon.pk,
			"opprettet": integrasjon.opprettet,
			"sist_oppdatert": integrasjon.sist_oppdatert,
			"system_kilde": {"class": "System", "id": integrasjon.source_system.pk},
			"system_destinasjon": {"class": "System", "id": integrasjon.destination_system.pk},
			"integrasjonstype": {
				"id": integrasjon.integration_type,
				"navn": integrasjon.get_integration_type_display(),
			},
			"bool_personopplysninger": integrasjon.personopplysninger,
			"beskrivelse": integrasjon.description,
		}
		data.append(line)

	delta = round(time.time() - runtime_t0, 3)

	resultat = {
		"beskrivelse": "Systemintegrasjon-objekter fra Karoteket. Beskriver avhengigheter mellom to systemer.",
		"antall": len(query),
		"kjoretid": f"{delta}",
		"data": data,
	}

	ApplicationLog.objects.create(
		event_type="api_systemintegrasjoner",
		message=f"kallet fra {get_client_ip(request)} tok {delta} sekunder."
	)
	return JsonResponse(resultat, safe=False, status=200)




def api_los(request): #tjeneste- og systemoversikt
	# 2026-06-23: Update api_tjeneste_systemoversikt_docs.py when changing /api/los/ or LOS JSON fields (url name: api_tjeneste_systemoversikt_docs).
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn="tjenester_og_systemer").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	ApplicationLog.objects.create(event_type="api_los", message=f"Innkommende kall fra {get_client_ip(request)}")
	runtime_t0 = time.time()
	data = []
	query = LOS.objects.all()
	for term in query:
		line = {}

		line["class"] = "LOS"
		line["id"] = term.pk
		line["opprettet"] = None
		line["sist_oppdatert"] = term.sist_oppdatert
		line["los_external_id"] = term.unik_id
		line["begrep"] = term.verdi
		line["ontologi"] = {"class": "LOS", "id": term.kategori_ref.pk} if term.kategori_ref else None
		line["overordnede_begreper"] = [{"class": "LOS", "id": parent.pk} for parent in term.parent_id.all()]
		line["bool_active"] = term.active

		data.append(line)


	runtime_t1 = time.time()
	delta = round(runtime_t1 - runtime_t0, 3)

	resultat = {"beskrivelse": "LOS rammeverk-objekter fra Karoteket. Kategoribibliotek fra DigDir systemer kobles til. Se https://www.digdir.no/informasjonsforvaltning/los-felles-vokabular-klassifisering-av-offentlige-tjenester-og-ressurser/2434", "antall": len(query), "kjoretid": f"{delta}", "data": data}

	ApplicationLog.objects.create(event_type="api_los", message=f"kallet fra {get_client_ip(request)} tok {delta} sekunder.")
	return JsonResponse(resultat, safe=False, status=200)



def api_kritiske_funksjoner(request): #tjeneste- og systemoversikt
	# 2026-06-23: Update api_tjeneste_systemoversikt_docs.py when changing /api/kritiske_funksjoner/ or KritiskFunksjon JSON fields (url name: api_tjeneste_systemoversikt_docs).
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn="tjenester_og_systemer").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	ApplicationLog.objects.create(event_type="api_kritiske_funksjoner", message=f"Innkommende kall fra {get_client_ip(request)}")
	runtime_t0 = time.time()
	data = []
	query = KritiskFunksjon.objects.all()
	for funksjon in query:
		line = {}

		line["class"] = "KritiskFunksjon"
		line["id"] = funksjon.pk
		line["opprettet"] = None
		line["sist_oppdatert"] = None
		line["navn"] = funksjon.navn
		line["kategori"] = funksjon.get_kategori_display()

		data.append(line)


	runtime_t1 = time.time()
	delta = round(runtime_t1 - runtime_t0, 3)

	resultat = {"beskrivelse": "Kritisk funksjon-objekter fra Karoteket. Koblet til KritiskKapabilitet-objektet og kommer fra DSB-rammeverk manuelt skrevet inn.", "antall": len(query), "kjoretid": f"{delta}", "data": data}

	ApplicationLog.objects.create(event_type="api_kritiske_funksjoner", message=f"kallet fra {get_client_ip(request)} tok {delta} sekunder.")
	return JsonResponse(resultat, safe=False, status=200)


def api_kritiske_kapabiliteter(request): #tjeneste- og systemoversikt
	# 2026-06-23: Update api_tjeneste_systemoversikt_docs.py when changing /api/kritiske_kapabiliteter/ or KritiskKapabilitet JSON fields (url name: api_tjeneste_systemoversikt_docs).
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn="tjenester_og_systemer").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	ApplicationLog.objects.create(event_type="api_kritiske_kapabiliteter", message=f"Innkommende kall fra {get_client_ip(request)}")
	runtime_t0 = time.time()
	data = []
	query = KritiskKapabilitet.objects.all()
	for kapabilitet in query:
		line = {}

		line["class"] = "KritiskKapabilitet"
		line["id"] = kapabilitet.pk
		line["opprettet"] = None
		line["sist_oppdatert"] = None
		line["navn"] = kapabilitet.navn
		line["funksjon"] = {"class": "KritiskFunksjon", "id": kapabilitet.funksjon.pk} if kapabilitet.funksjon else None
		line["kategori"] = kapabilitet.beskrivelse

		data.append(line)


	runtime_t1 = time.time()
	delta = round(runtime_t1 - runtime_t0, 3)

	resultat = {"beskrivelse": "Kritisk kapabilitet-objekter. Koblet til Systemer, og kommer fra DSB-rammeverk manuelt skrevet inn.", "antall": len(query), "kjoretid": f"{delta}", "data": data}

	ApplicationLog.objects.create(event_type="api_kritiske_kapabiliteter", message=f"kallet fra {get_client_ip(request)} tok {delta} sekunder.")
	return JsonResponse(resultat, safe=False, status=200)



def api_virksomheter(request): #tjeneste- og systemoversikt
	# 2026-06-23: Update api_tjeneste_systemoversikt_docs.py when changing /api/virksomheter/ or Virksomhet JSON fields (url name: api_tjeneste_systemoversikt_docs).
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn="tjenester_og_systemer").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	ApplicationLog.objects.create(event_type="api_virksomheter", message=f"Innkommende kall fra {get_client_ip(request)}")
	runtime_t0 = time.time()
	data = []
	query = Virksomhet.objects.all()
	for virksomhet in query:
		line = {}

		line["class"] = "Virksomhet"
		line["id"] = virksomhet.pk
		line["opprettet"] = virksomhet.opprettet
		line["sist_oppdatert"] = virksomhet.sist_oppdatert
		line["virksomhetsnavn"] = virksomhet.virksomhetsnavn
		line["orgnummer"] = virksomhet.orgnummer
		line["virksomhetsforkortelse"] = virksomhet.virksomhetsforkortelse
		line["gamle_virksomhetsforkortelser"] = virksomhet.gamle_virksomhetsforkortelser
		line["klientplattform"] = virksomhet.get_resultatenhet_display()
		line["office365_tenant"] = virksomhet.get_office365_display()
		line["intranett_url"] = virksomhet.intranett_url
		line["www_url"] = virksomhet.www_url

		line["rolle_virksomhetsleder"] = virksomhet.leder_hr().email if virksomhet.leder_hr() else None
		line["rolle_uke_hovedkontakt"] = [ansvarlig.brukernavn.email for ansvarlig in virksomhet.uke_kam_referanse.all()]
		line["rolle_ikt_kontakt"] = [ansvarlig.brukernavn.email for ansvarlig in virksomhet.ikt_kontakt.all()]
		line["rolle_autoriserte_bestillere_infotorg"] = [ansvarlig.brukernavn.email for ansvarlig in virksomhet.autoriserte_bestillere_tjenester.all()]
		line["rolle_autoriserte_bestillere_uketjenester"] = [ansvarlig.brukernavn.email for ansvarlig in virksomhet.autoriserte_bestillere_tjenester_uke.all()]
		line["rolle_personvernkoordinator"] = [ansvarlig.brukernavn.email for ansvarlig in virksomhet.personvernkoordinator.all()]
		line["rolle_informasjonssikkerhetskoordinator"] = [ansvarlig.brukernavn.email for ansvarlig in virksomhet.informasjonssikkerhetskoordinator.all()]
		line["rolle_uke_kam"] = [ansvarlig.brukernavn.email for ansvarlig in virksomhet.uke_kam_referanse.all()]
		line["rolle_arkitekturkontakter"] = [ansvarlig.brukernavn.email for ansvarlig in virksomhet.arkitekturkontakter.all()]
		line["rolle_ks_fiks_admins"] = [ansvarlig.brukernavn.email for ansvarlig in virksomhet.ks_fiks_admin_ref.all()]

		line["overordnede_virksomheter"] = [{"class": "Virksomhet", "id": parent.pk} for parent in virksomhet.overordnede_virksomheter.all()]

		data.append(line)


	runtime_t1 = time.time()
	delta = round(runtime_t1 - runtime_t0, 3)

	resultat = {"beskrivelse": "Virksomhet-objekter fra Kartoteket. Sjekk klassen SystemBruk for oversikt over hvilke systemer en enkelt virksomhet bruker.", "antall": len(query), "kjoretid": f"{delta}", "data": data}

	ApplicationLog.objects.create(event_type="api_virksomheter", message=f"kallet fra {get_client_ip(request)} tok {delta} sekunder.")
	return JsonResponse(resultat, safe=False, status=200)


def api_systembruk_optimized(request):  # tjeneste- og systemoversikt
	# 2026-06-23: Update api_tjeneste_systemoversikt_docs.py when changing /api/systembruk/ or SystemBruk JSON fields (url name: api_tjeneste_systemoversikt_docs).
	if request.method != "GET":
		raise Http404

	key = request.headers.get("key")
	allowed_keys = APIKeys.objects.filter(navn="tjenester_og_systemer").values_list("key", flat=True)
	if key not in allowed_keys:
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	ApplicationLog.objects.create(event_type="api_systembruk", message=f"Innkommende kall fra {get_client_ip(request)}")
	runtime_t0 = time.time()

	query = (
		SystemBruk.objects.filter(ibruk=True)
		.select_related("system", "brukergruppe", "systemforvalter")
		.prefetch_related(
			"systemforvalter_kontaktpersoner_referanse__brukernavn",
			"systemeier_kontaktpersoner_referanse__brukernavn"
		)
	)

	data = []
	for systembruk in query:
		line = {
			"class": "SystemBruk",
			"id": systembruk.pk,
			"kommentar": systembruk.kommentar,
			"antall_brukere": systembruk.antall_brukere,
			"system": {"class": "System", "id": systembruk.system.pk},
			"virksomhet": {"class": "Virksomhet", "id": systembruk.brukergruppe.pk},
			"lokal_konfidensialitetsvurdering": systembruk.get_konfidensialitetsvurdering_display(),
			"lokal_integritetsvurdering": systembruk.get_integritetsvurdering_display(),
			"lokal_tilgjengelighetsvurdering": systembruk.get_tilgjengelighetsvurdering_display(),
			"lokal_systemforvalter_virksomhet": {"class": "Virksomhet", "id": systembruk.systemforvalter.pk} if systembruk.systemforvalter else None,
			"lokal_systemforvalter_kontaktpersoner": [ansvarlig.brukernavn.email for ansvarlig in systembruk.systemforvalter_kontaktpersoner_referanse.all()],
			"lokal_systemeier_kontaktpersoner": [ansvarlig.brukernavn.email for ansvarlig in systembruk.systemeier_kontaktpersoner_referanse.all()],
		}
		data.append(line)

	delta = round(time.time() - runtime_t0, 3)
	resultat = {"beskrivelse": "SystemBruk-objekter fra Kartoteket", "antall": len(query), "kjoretid": f"{delta}", "data": data}

	ApplicationLog.objects.create(event_type="api_systembruk", message=f"kallet fra {get_client_ip(request)} tok {delta} sekunder.")
	return JsonResponse(resultat, safe=False, status=200)





### FERDIG TJENESTE OG SYSTEMOVERSIKT-API-er ###

def system_excel_api(request, virksomhet_pk=None): #API

	if not request.method == "GET":
		raise Http404

	if not virksomhet_pk:
		return JsonResponse({"status": "Ingen virksomhet valgt", "data": None}, safe=False, status=200)

	virksomhet = Virksomhet.objects.get(pk=virksomhet_pk)

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="virksomhet_").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	relevante_systemer = []

	systemer_ansvarlig_for = System.objects.filter(~Q(ibruk=False)).filter(Q(systemeier=virksomhet_pk) | Q(systemforvalter=virksomhet_pk))
	for system in systemer_ansvarlig_for:
		system.__midlertidig_type = "Eier eller forvalter"
		relevante_systemer.append(system)

	virksomhets_bruk = SystemBruk.objects.filter(brukergruppe=virksomhet_pk)
	for bruk in virksomhets_bruk:
		system = bruk.system
		if system not in relevante_systemer:
			system.__midlertidig_type = "Kun bruk"
			relevante_systemer.append(system)

	data = []
	for system in relevante_systemer:
		line = {}
		line["systemnavn"] = system.systemnavn
		line["alias"] = system.alias
		line["systembeskrivelse"] = system.systembeskrivelse
		line["type"] = system.__midlertidig_type
		line["systemeier"] = system.systemeier.virksomhetsforkortelse  if system.systemeier else "Ukjent"
		line["systemforvalter"] = system.systemforvalter.virksomhetsforkortelse if system.systemforvalter else "Ukjent"
		line["livslop"] = system.get_livslop_status_display()
		line["driftsmodell"] = system.driftsmodell_foreignkey.navn if system.driftsmodell_foreignkey else "Ukjent"
		line["leverandor_system"] = [leverandor.leverandor_navn for leverandor in system.systemleverandor.all()]
		line["leverandor_appdrift"] = [leverandor.leverandor_navn for leverandor in system.applikasjonsdriftleverandor.all()]
		line["leverandor_basisdrift"] = [leverandor.leverandor_navn for leverandor in system.basisdriftleverandor.all()]
		line["teknisk_egnethet"] = system.get_teknisk_egnethet_display()
		line["strategisk_egnethet"] = system.get_strategisk_egnethet_display()
		line["funksjonell_egnethet"] = system.get_funksjonell_egnethet_display()
		data.append(line)

	status = "OK. Data for %s." % virksomhet.virksomhetsforkortelse
	resultat = {"status": status, "data": data}
	return JsonResponse(resultat, safe=False, status=200)



def iga_api(request): #API
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="iga").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	data = []
	for s in System.objects.all():
		systeminfo = {}
		systeminfo["navn"] = s.systemnavn
		systeminfo["pk"] = s.id
		systeminfo["ibruk"] = s.er_ibruk()
		systeminfo["status_id"] = s.livslop_status
		systeminfo["status_tekst"] = s.get_livslop_status_display()
		systeminfo["sist_oppdatert"] = s.sist_oppdatert
		systeminfo["beskrivelse"] = s.systembeskrivelse
		systeminfo["systemeier"] = s.systemeier.virksomhetsforkortelse if s.systemeier else None
		systeminfo["systemeier_personer"] = [ansvarlig.brukernavn.email for ansvarlig in s.systemeier_kontaktpersoner_referanse.all()]
		systeminfo["systemforvalter"] = s.systemforvalter.virksomhetsforkortelse if s.systemforvalter else None
		systeminfo["systemforvalter_personer"] = [ansvarlig.brukernavn.email for ansvarlig in s.systemforvalter_kontaktpersoner_referanse.all()]
		systeminfo["driftsmodell"] = s.driftsmodell_foreignkey.navn if s.driftsmodell_foreignkey else None
		systeminfo["service_offerings"] = [offering.navn for offering in s.service_offerings.all()]
		data.append(systeminfo)

	return JsonResponse(data, safe=False, status=200)



def get_api_tilganger(request): #API
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="get_api_tilganger").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	business_services = set()
	email = request.GET.get('email', '').strip()
	try:
		user = User.objects.get(email=email)
	except:
		return JsonResponse({"error": "No match for email address or no email address given. Please supply GET variable 'email' (?email=<>)."}, safe=False, content_type='application/json; charset=utf-8')

	for system in user.ansvarlig_brukernavn.system_eier_for.all():
		if hasattr(system, "bs_system_referanse"):
			business_services.add(system.bs_system_referanse.navn)

	for system in user.ansvarlig_brukernavn.system_forvalter_for.all():
		if hasattr(system, "bs_system_referanse"):
			business_services.add(system.bs_system_referanse.navn)

	result = {"email": email, "username": user.username, "business_services": list(business_services)}
	return JsonResponse(result, safe=False, status=200)


# denne er ikke lenger i bruk
"""
def csirt_maskinlookup_api(request): #API
	#ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message=f"Innkommende kall fra {get_client_ip(request)}")
	if not request.method == "GET":
		#ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message="Feil: HTTP metode var ikke GET")
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="csirt_ipsok").values_list("key", flat=True)
	if not key in list(allowed_keys):
		ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message="Feil eller tom API-nøkkel")
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False,status=403)

	from django.core.exceptions import ObjectDoesNotExist

	maskin_string = request.GET.get('server', '').strip()
	if maskin_string == '':
		ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message="Ingen treff på tomt servernavn")
		return JsonResponse({"error": "Servernavn er ikke oppgitt. Send som GET-variabel 'server'"}, safe=False)

	try:
		server_match = CMDBdevice.objects.get(comp_name=maskin_string)
	except ObjectDoesNotExist:
		try:
			alias_string = DNSrecord.objects.get(dns_name=maskin_string).dns_target
			server_match = CMDBdevice.objects.get(comp_name=alias_string)
			ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message=f"Ingen treff på {maskin_string}, men treff på {alias_string}")
		except:
			ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message=f"Ingen treff på {maskin_string}")
			return JsonResponse({"error": "Ingen treff på servernavn"}, safe=False)

	try:
		business_sub_service = server_match.sub_name.navn
	except:
		business_sub_service = ""
	try:
		business_service = server_match.sub_name.parent_ref.navn
	except:
		business_service = ""
	try:
		systemnavn = server_match.sub_name.system.systemnavn
	except:
		systemnavn = ""
	try:
		systemalias = server_match.sub_name.system.alias
	except:
		systemalias = ""
	try:
		systemeier = server_match.sub_name.system.systemeier.virksomhetsforkortelse
	except:
		systemeier = ""
	try:
		systemforvalter = server_match.sub_name.system.systemforvalter.virksomhetsforkortelse
	except:
		systemforvalter = ""
	try:
		systemforvaltere = [ansvarlig.brukernavn.email for ansvarlig in server_match.sub_name.system.systemforvalter_kontaktpersoner_referanse.all()]
	except:
		systemforvaltere = []

	data = {
		"query": maskin_string,
		"hostname": server_match.comp_name,
		"os": server_match.comp_os_readable,
		"ip_address": server_match.comp_ip_address,
		"business_sub_service": business_sub_service,
		"business_service": business_service,
		"system": {
			"systemnavn": systemnavn,
			"systemalias": systemalias,
			"systemeier": systemeier,
			"systemforvalter": systemforvalter,
			"systemforvaltere": systemforvaltere,
		}
	}

	ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message=f"Vellykket kall mot {maskin_string}")
	return JsonResponse(data, safe=False)
"""


def csirt_iplookup_api(request):
	# 2026-06-23: Update api_vulnapp_docs.py when changing /api/vulnapp/ipsok/ (url name: api_vulnapp_docs).
	#ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message=f"Innkommende kall fra {get_client_ip(request)}")
	if not request.method == "GET":
		ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message="Feil: HTTP metode var ikke GET")
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="vulnapp").values_list("key", flat=True)
	if not key in list(allowed_keys) and not os.environ['THIS_ENV'] == "TEST":
		ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message="Feil eller tom API-nøkkel")
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	from django.core.exceptions import ObjectDoesNotExist
	import ipaddress

	ip_string = request.GET.get('ip', '').strip()
	port_string = request.GET.get('port', '').strip()
	if ip_string == '':
		#ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message="Ingen treff på tom IP-adresse")
		return JsonResponse({"error": "Ingen IP-adresse oppgitt. Send som GET-variabel 'ip'"}, safe=False, status=200)
	try:
		ip = ipaddress.ip_address(ip_string)
	except ValueError:
		#ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message=f"Ingen treff på ugyldig IP-adresse {ip_string}")
		return JsonResponse({"error": "Ikke en gyldig IP-adresse"}, safe=False, status=200)


	if DNSrecord.objects.filter(ip_address=ip_string).count() <= 15:
		dns_match = [inst.dns_name for inst in DNSrecord.objects.filter(ip_address=ip_string).all()]
	else:
		dns_match = ["Flere enn 15"]

	try:
		ip_match = NetworkIPAddress.objects.get(ip_address=ip_string)

		vlan_match = ["%s subnet /%s: %s" % (inst.ip_address, inst.subnet_mask, inst.comment) for inst in ip_match.vlan.all()]
		vip_match = ["%s port %s" % (vip.vip_name, vip.port) for vip in ip_match.viper.all()]
		members = []

		for server in ip_match.servere.all():
			server.eksternt_eksponert_dato = timezone.now()
			server.save()

		for vip in ip_match.viper.all():
			if port_string != "":
				if vip.port != int(port_string):
					continue
			for pool in vip.nested_pool_members():

				for local_ip in pool.server.network_ip_address.all(): # Det er bare ét, men det er en mange-til-mangerelasjon
					#host_vlan.append(["%s (%s/%s)" % (v.comment, v.ip_address, v.subnet_mask) for v in local_ip.vlan.all()])
					domaint_vlan = local_ip.dominant_vlan()
					host_vlan = "%s (%s/%s)" % (domaint_vlan.comment, domaint_vlan.ip_address, domaint_vlan.subnet_mask)

				pool.server.eksternt_eksponert_dato = timezone.now()
				pool.server.save()

				members.append({
					"server": pool.server.comp_name,
					"host_ip": pool.ip_address,
					"external_vip": "%s port %s" % (vip.vip_name, vip.port),
					"server_vlan": host_vlan,
					"bss": [offering.navn for offering in pool.server.service_offerings.all()],
				})
		vip_pool_members = members

	except ObjectDoesNotExist:
		#ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message=f"Ingen treff på {ip_string}")
		return JsonResponse({"error": "Ingen treff på IP-adresse"}, safe=False, status=200)

	data = {
		"query_ip": ip_string,
		"query_port": port_string,
		"dns_matches": dns_match,
		"vip_matches": vip_match,
		"vip_pool_members": vip_pool_members,
		"matching_vlans": vlan_match,
	}

	source_ip = get_client_ip(request)
	ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message=f"Vellykket kall mot {ip_string} utført fra {source_ip}")
	return JsonResponse(data, safe=False, status=200)




def vav_akva_api(request): #API
	ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message=f"Innkommende kall fra {get_client_ip(request)}")
	if not request.method == "GET":
		ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message="Feil: HTTP metode var ikke GET")
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="akva_vav").values_list("key", flat=True)
	if not key in list(allowed_keys):
		ApplicationLog.objects.create(event_type="API Akva VAV", message="Feil eller tom API-nøkkel")
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	from systemoversikt.settings import SITE_SCHEME, SITE_DOMAIN

	data = []
	for b in SystemBruk.objects.filter(brukergruppe__virksomhetsforkortelse="VAV"):
		systeminfo = {}
		systeminfo["system_navn"] = b.system.systemnavn
		systeminfo["system_navn_visning"] = b.system.__str__()
		systeminfo["system_id"] = b.system.id
		systeminfo["ibruk"] = b.system.er_ibruk()
		systeminfo["livslop_status"] = b.system.livslop_status if b.system.livslop_status != None else 0
		systeminfo["livslop_status_visning"] = b.system.get_livslop_status_display()
		systeminfo["system_klassifisering"] = b.system.systemeierskapsmodell
		systeminfo["systemkategorier"] = [kategori.kategorinavn for kategori in b.system.systemkategorier.all()]
		systeminfo["sist_oppdatert"] = b.system.sist_oppdatert
		systeminfo["systemeier"] = b.system.systemeier.virksomhetsforkortelse if b.system.systemeier else None
		systeminfo["systemeier_personer"] = [ansvarlig.brukernavn.email for ansvarlig in b.system.systemeier_kontaktpersoner_referanse.all()]
		systeminfo["systemforvalter"] = b.system.systemforvalter.virksomhetsforkortelse if b.system.systemforvalter else None
		systeminfo["systemforvalter_seksjon"] = b.system.systemforvalter_avdeling_referanse.ou if b.system.systemforvalter_avdeling_referanse else None
		systeminfo["systemforvalter_personer"] = [ansvarlig.brukernavn.email for ansvarlig in b.system.systemforvalter_kontaktpersoner_referanse.all()]
		systeminfo["lokal_systemforvalter_personer"] = [ansvarlig.brukernavn.email for ansvarlig in b.systemforvalter_kontaktpersoner_referanse.all()]
		systeminfo["lokal_systemeier_personer"] = [ansvarlig.brukernavn.email for ansvarlig in b.systemeier_kontaktpersoner_referanse.all()]
		systeminfo["url_webportal"] = [url.domene for url in b.system.systemurl.all()]
		systeminfo["url_systemoversikt"] = SITE_SCHEME + "://" + SITE_DOMAIN + reverse('systemdetaljer', kwargs={'pk': b.system.pk})
		systeminfo["systembeskrivelse"] = b.system.systembeskrivelse if b.system.systembeskrivelse != None else ""
		systeminfo["lokal_systembeskrivelse"] = b.kommentar if b.kommentar != None else ""
		systeminfo["leverandor_applikasjon"] = [leverandor.leverandor_navn for leverandor in b.system.systemleverandor.all()]
		systeminfo["leverandor_applikasjonsdrift"] = [leverandor.leverandor_navn for leverandor in b.system.applikasjonsdriftleverandor.all()]
		systeminfo["leverandor_driftsmiljo"] = [leverandor.leverandor_navn for leverandor in b.system.basisdriftleverandor.all()]
		systeminfo["funksjonell_egnethet"] = b.system.funksjonell_egnethet
		systeminfo["funksjonell_egnethet_tekst"] = b.system.get_funksjonell_egnethet_display()
		systeminfo["teknisk_egnethet"] = b.system.teknisk_egnethet
		systeminfo["teknisk_egnethet_tekst"] = b.system.get_teknisk_egnethet_display()
		systeminfo["konfidensialitetsvurdering"] = b.system.sikkerhetsnivaa
		systeminfo["konfidensialitetsvurdering_tekst"] = b.system.get_sikkerhetsnivaa_display()
		systeminfo["superbrukere"] = b.system.superbrukere
		systeminfo["driftsplattform"] = b.system.driftsmodell_foreignkey.__str__() if b.system.driftsmodell_foreignkey else None
		data.append(systeminfo)

	source_ip = get_client_ip(request)
	ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message=f"Vellykket kall fra {source_ip}")
	return JsonResponse(data, safe=False, status=200)


@csrf_exempt
def api_known_exploited(request): #API
	# 2026-06-23: Update api_vulnapp_docs.py when changing /api/vulnapp/known_exploited/ (url name: api_vulnapp_docs).
	event_type = "API known exploited"
	ApplicationLog.objects.create(event_type=event_type, message=f"Innkommende kall fra {get_client_ip(request)}")

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="vulnapp_knownex").values_list("key", flat=True)
	if not key in list(allowed_keys) and not os.environ['THIS_ENV'] == "TEST":
		ApplicationLog.objects.create(event_type=event_type, message="Feil eller tom API-nøkkel")
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)


	if request.method == 'POST':
		try:
			data = json.loads(request.body)
			data = data.replace("vulnapp.exploitedvulnerability", "systemoversikt.exploitedvulnerability")

			count = 0
			for deserialized_object in serializers.deserialize('json', data):
				obj = deserialized_object.object
				obj.save()
				count += 1

			print(f"Updated {count} known exploited CVEs")

			ApplicationLog.objects.create(event_type=event_type, message=f"Vellykket oppdatering fra {get_client_ip(request)}")
			return JsonResponse({'message': 'Thanks for the update!'}, status=200)
		except json.JSONDecodeError:
			ApplicationLog.objects.create(event_type=event_type, message=f"Invalid JSON fra {get_client_ip(request)}")
			return JsonResponse({'error': 'Invalid JSON'}, status=400)

	ApplicationLog.objects.create(event_type=event_type, message=f"Invalid request method fra {get_client_ip(request)}")
	return JsonResponse({'error': 'Invalid request method'}, status=405)






def api_programvare_vulnapp(request): #API
	# 2026-06-23: Update api_vulnapp_docs.py when changing /api/vulnapp/programvare/ (url name: api_vulnapp_docs).
	ApplicationLog.objects.create(event_type="API programvare", message=f"Innkommende kall fra {get_client_ip(request)}")
	if not request.method == "GET":
		ApplicationLog.objects.create(event_type="API programvare", message="Feil: HTTP metode var ikke GET")
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="vulnapp").values_list("key", flat=True)
	if not key in list(allowed_keys) and not os.environ['THIS_ENV'] == "TEST":
		ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message="Feil eller tom API-nøkkel")
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	programvare = Programvare.objects.filter(til_cveoversikt_og_nyheter=True).values_list('programvarenavn', flat=True).distinct()
	programvarelev = Programvare.objects.filter(til_cveoversikt_og_nyheter=True).filter(~Q(programvareleverandor=None)).values_list('programvareleverandor__leverandor_navn', flat=True).distinct()

	data = {"programvare": list(programvare), "programvarelev": list(programvarelev)}
	#leverandorer = Leverandor.objects.values_list('leverandor_navn', flat=True).distinct()
	#systemer = System.objects.values_list('systemnavn', flat=True).distinct()
	ApplicationLog.objects.create(event_type="API programvare", message=f"Vellykket kall fra {get_client_ip(request)}")
	return JsonResponse(data, safe=False, status=200)



def behandlingsoversikt_api(request): #API
	ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message=f"Innkommende kall fra {get_client_ip(request)}")
	if not request.method == "GET":
		ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message="Feil: HTTP metode var ikke GET")
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="behandlingsoversikt").values_list("key", flat=True)
	if not key in list(allowed_keys):
		ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message="Feil eller tom API-nøkkel")
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	data = []
	for s in System.objects.all():
		systeminfo = {}
		systeminfo["system_navn"] = s.systemnavn
		systeminfo["system_navn_visning"] = s.__str__()
		systeminfo["system_id"] = s.id
		systeminfo["ibruk"] = s.er_ibruk()
		systeminfo["system_klassifisering"] = s.systemeierskapsmodell
		systeminfo["sist_oppdatert"] = s.sist_oppdatert
		systeminfo["systemeier"] = s.systemeier.virksomhetsforkortelse if s.systemeier else None
		systeminfo["systemeier_personer"] = [ansvarlig.brukernavn.email for ansvarlig in s.systemeier_kontaktpersoner_referanse.all()]
		systeminfo["systemforvalter"] = s.systemforvalter.virksomhetsforkortelse if s.systemforvalter else None
		systeminfo["systemforvalter_personer"] = [ansvarlig.brukernavn.email for ansvarlig in s.systemforvalter_kontaktpersoner_referanse.all()]
		data.append(systeminfo)

	source_ip = get_client_ip(request)
	ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message=f"Vellykket kall fra {source_ip}")
	return JsonResponse(data, safe=False, status=200)



def csirt_api(request): #API
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="csirt").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	data = []
	for s in System.objects.all():
		systeminfo = {}
		systeminfo["systemnavn"] = s.systemnavn
		systeminfo["systemalias"] = s.alias

		systeminfo["os"] = s.unike_server_os()

		systeminfo["applikasjoner"] = [a.programvarenavn for a in s.programvarer.all()]

		systeminfo["id"] = s.id
		systeminfo["systemeier"] = s.systemeier.virksomhetsforkortelse if s.systemeier else None
		systeminfo["systemforvalter"] = s.systemforvalter.virksomhetsforkortelse if s.systemforvalter else None
		data.append(systeminfo)

	return JsonResponse(data, safe=False, status=200)





def cmdb_api(request): #API
	# brukes for å samle inn faktureringsgrunnlag (koble servere til systemeier)
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="api_cmdb").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	data = []
	# tar ikke med tykke klienter da disse 11k per nå bare vil støye ned
	query = CMDBRef.objects.filter(operational_status=True).filter(~Q(navn="OK-Tykklient"))
	for bss in query:
		line = {}
		line["business_subservice_navn"] = bss.navn
		line["business_subservice_billable"] = bss.u_service_billable
		line["business_service"] = bss.parent_ref.navn
		line["sist_oppdatert"] = bss.sist_oppdatert
		line["opprettet"] = bss.opprettet
		line["environment"] = bss.get_environment_display()
		line["busines_criticality"] = bss.kritikalitet
		line["service_availability"] = bss.u_service_availability
		line["service_operation_factor"] = bss.u_service_operation_factor
		line["service_complexity"] = bss.u_service_complexity
		if bss.parent_ref:
			if bss.system:
				system = bss.system
				line["tilknyttet_system"] = system.systemnavn if system else "Ikke koblet"
				line["systemeier"] = system.systemeier.virksomhetsforkortelse if system.systemeier else "Ikke oppgitt"
				line["systemforvalter"] = system.systemforvalter.virksomhetsforkortelse if system.systemforvalter else "Ikke oppgitt"
				line["plattform"] = system.driftsmodell_foreignkey.navn if system.driftsmodell_foreignkey else "Ikke oppgitt"
				line["er_infrastruktur"] = system.er_infrastruktur()
			else:
				line["tilknyttet_system"] = "Ikke koblet"
				line["systemeier"] = "Ukjent grunnet manglende systemkobling"
				line["systemforvalter"] = "Ukjent grunnet manglende systemkobling"
				line["plattform"] = "Ukjent grunnet manglende systemkobling"
				line["er_infrastruktur"] = "Ukjent grunnet manglende systemkobling"
		else:
			return("error")

		line["antall_servere"] = bss.ant_devices()

		serverliste = []
		for server in bss.devices.all():
			s = dict()
			s["server_navn"] = server.comp_name
			s["billable"] = server.billable
			s["server_os"] = server.comp_os
			s["server_ram"] = server.comp_ram
			if server.comp_disk_space:
				s["server_disk"] = server.comp_disk_space * 1000 * 1000  # ønskes oppgitt i megabyte (fra bytes)
			else:
				s["server_disk"] = None
			s["server_cpu_core_count"] = server.comp_cpu_core_count
			serverliste.append(s)

		line["servere"] = serverliste
		line["antall_databaser"] = bss.ant_databaser()
		databaseliste = []
		for database in bss.cmdbdatabase_sub_name.filter(db_operational_status=True):
			s = dict()
			s["navn"] = database.db_database
			s["server"] = database.db_server
			s["version"] = database.db_version
			s["billable"] = database.billable
			s["status"] = database.db_status
			s["datafilessizekb"] = database.db_u_datafilessizekb # Merk at dette faktisk er bytes!
			s["db_comments"] = database.db_comments
			databaseliste.append(s)

		line["databaser"] = databaseliste
		data.append(line)
		resultat = {"antall bss": len(query), "data": data}

	return JsonResponse(resultat, safe=False, status=200)



def cmdb_api_kompass(request): #API
	# brukes for å oppdatere Kompass med informasjon om drift (bss, systemer, maskiner osv.)
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="api_cmdb_kompass").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	data = []
	query = CMDBbs.objects.filter(operational_status=True)#.filter(~Q(navn="OK-Tykklient"))
	for bs in query:
		line = {}
		line["business_service_operational_status"] = bool(bs.operational_status)
		line["business_service_name"] = bs.navn
		line["business_service_internal_ref"] = bs.pk
		line["business_service_external_ref"] = bs.bs_external_ref
		line["business_service_systemknytning_navn"] = bs.systemreferanse.systemnavn if bs.systemreferanse else None
		line["business_service_systemknytning_pk"] = bs.systemreferanse.pk if bs.systemreferanse else None

		bss_liste = []
		for bss in bs.cmdb_bss_to_bs.all():
			b = {}
			b["business_subservice_operational_status"] = bool(bss.operational_status)
			b["business_subservice_name"] = bss.navn
			b["business_subservice_environment"] = bss.get_environment_display()
			b["business_subservice_internal_ref"] = bss.pk
			b["business_subservice_external_ref"] = bss.bss_external_ref
			b["business_subservice_billable"] = bss.u_service_billable
			b["business_subservice_classification"] = bss.service_classification
			b["business_subservice_complexity"] = bss.u_service_complexity
			b["business_subservice_operation_factor"] = bss.u_service_operation_factor
			b["business_subservice_availability"] = bss.u_service_availability
			b["business_subservice_business_criticality"] = bss.kritikalitet
			b["business_subservice_business_criticality_str"] = bss.get_kritikalitet_display()
			b["business_subservice_comments"] = bss.comments
			bss_liste.append(b)

		line["Business_subservices"] = bss_liste
		data.append(line)

	resultat = {"antall business services": len(query), "data": data}
	return JsonResponse(resultat, safe=False, status=200)



def cmdb_firewall(request):
	required_permissions = ['systemoversikt.view_brannmurregel']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	def firewall_loopup(term):
		return Brannmurregel.objects.filter(
				Q(source__icontains=search_term) |
				Q(destination__icontains=search_term) |
				Q(protocol__icontains=search_term) |
				Q(comment__icontains=search_term)
			)

	search_term_raw = request.GET.get('search_term', '')
	search_term = search_term_raw.strip()

	if search_term == "__ALL__":
		firewall_openings = Brannmurregel.objects.all()

	elif len(search_term) > 1:
		firewall_openings = firewall_loopup(search_term)

	else:
		firewall_openings = []

	return render(request, 'cmdb_brannmur.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'all_openings': firewall_openings,
		'brannmur_search_term': search_term_raw,
		'integrasjonsstatus': _integrasjonsstatus("sp_firewall"),
	})



# 2026-06-21: Removed UBW module views – feature retired, URLs already disabled.


###############################################
# AD-gruppemedlemskap (kun lokale databaseverdier)
###############################################


def rapport_gruppemedlemskaper_antall_brukere(grupper, and_grupper=None):
	# 2026-05-27: Unique transitive Kartoteket users for sikkerhetsavvik / rapport_avvik counts.
	"""Return (count, sorted usernames) for RapportGruppemedlemskaper-style group rules."""
	users = adgruppe_transitive_users_db_only(grupper) if grupper else set()
	if and_grupper:
		users &= adgruppe_transitive_users_db_only(and_grupper)
	usernames = sorted(u.username for u in users)
	return len(users), usernames


def adgruppe_transitive_users_db_only(start_groups, collect_unresolved_dns=False, for_virksomhet=None):
	"""
	Finn unike brukerkontoer (User) som er medlem av minst én av de oppgitte AD-gruppene,
	inkludert medlemmer via nestede grupper, uten LDAP-kall.

	Basert utelukkende på feltet ADgroup.member (JSON med medlems-DN-er) og oppslag mot
	ADgroup (undergrupper) og User (samsvar med CN i DN og username, samme logikk som
	human_readable_members_optimized).

	Undergrupper som ikke finnes som ADgroup-rad (ikke synket inn) følges ikke.
	Medlemmer som verken matcher en kjent gruppe eller en User, hopper over (eller samles
	i unresolved-listen).

	Args:
		start_groups: iterable av ADgroup (f.eks. liste eller QuerySet).
		collect_unresolved_dns: hvis True, returner (users, unresolved) der unresolved
			er en liste av medlems-DN som ikke ble tolket som gruppe eller bruker.
		for_virksomhet: valgfritt Virksomhet-objekt eller primærnøkkel (int). Når satt,
			velges kun brukere der Profile.virksomhet matcher (representasjons-feltet).

	Returns:
		set[User] hvis collect_unresolved_dns er False.
		(set[User], list[str]) hvis collect_unresolved_dns er True.
	"""
	from collections import deque

	queue = deque()
	visited_group_dns = set()
	unresolved = []

	for g in start_groups:
		if g is None:
			continue
		queue.append(g)

	users_by_id = {}

	while queue:
		g = queue.popleft()
		gdn = g.distinguishedname
		if gdn in visited_group_dns:
			continue
		visited_group_dns.add(gdn)

		try:
			raw_members = json.loads(g.member or "[]")
		except (json.JSONDecodeError, TypeError):
			raw_members = []

		if not raw_members:
			continue

		resolved = human_readable_members_optimized(raw_members, onlygroups=False)

		for u in resolved["users"]:
			users_by_id[u.pk] = u

		for child in resolved["groups"]:
			if child.distinguishedname not in visited_group_dns:
				queue.append(child)

		if collect_unresolved_dns:
			unresolved.extend(resolved["notfound"])

	out_users = set(users_by_id.values())
	if for_virksomhet is not None and users_by_id:
		v_pk = for_virksomhet.pk if hasattr(for_virksomhet, "pk") else for_virksomhet
		allowed_pks = set(
			User.objects.filter(pk__in=users_by_id.keys(), profile__virksomhet_id=v_pk).values_list(
				"pk", flat=True
			)
		)
		out_users = {users_by_id[pk] for pk in allowed_pks}

	if collect_unresolved_dns:
		return out_users, unresolved
	return out_users
