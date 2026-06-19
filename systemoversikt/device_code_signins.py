# -*- coding: utf-8 -*-
# Change log:
# 2026-06-19: Shared Graph fetch and combo sync for device code sign-in page and nightly job.
import datetime
import os
import time
from collections import defaultdict
from urllib.parse import quote

from django.utils import timezone
from django.utils.dateparse import parse_datetime

DEVICE_CODE_EXCLUDED_APPS = frozenset({
	"Microsoft Graph Command Line Tools",
	"Microsoft Exchange REST API Based Powershell",
	"Microsoft Azure CLI",
	"MS Teams Powershell Cmdlets",
})
DEVICE_CODE_SIGNIN_SELECT = (
	"createdDateTime,userPrincipalName,ipAddress,location,appDisplayName,"
	"resourceDisplayName,clientAppUsed,correlationId,riskLevelDuringSignIn,"
	"riskLevelAggregated,deviceDetail"
)
DEVICE_CODE_HISTORY_DAYS = 90


def device_code_internal_ip_prefixes():
	# 2026-06-19: IP prefixes from env – do not hardcode tenant network ranges in code.
	raw = os.environ.get('DEVICE_CODE_INTERNAL_IP_PREFIXES', '')
	return [prefix.strip() for prefix in raw.split(',') if prefix.strip()]


def signin_is_noteworthy(sign_in):
	"""True for sign-ins outside routine tooling, DIG apps and internal IP range."""
	ip_address = sign_in.get("ipAddress") or ""
	for prefix in device_code_internal_ip_prefixes():
		if ip_address.startswith(prefix):
			return False
	app_display_name = sign_in.get("appDisplayName") or ""
	if app_display_name.startswith("DIG"):
		return False
	if app_display_name in DEVICE_CODE_EXCLUDED_APPS:
		return False
	return True


def _parse_signin_datetime(created):
	if not created:
		return None
	if isinstance(created, datetime.datetime):
		dt = created
	else:
		dt = parse_datetime(str(created).replace("Z", "+00:00"))
		if dt is None:
			try:
				dt = datetime.datetime.fromisoformat(str(created).replace("Z", "+00:00"))
			except (ValueError, AttributeError):
				return None
	if timezone.is_naive(dt):
		dt = timezone.make_aware(dt, datetime.timezone.utc)
	return dt


def signin_to_combo_fields(sign_in):
	sign_in_time = _parse_signin_datetime(sign_in.get("createdDateTime"))
	return {
		"user_principal_name": sign_in.get("userPrincipalName") or "",
		"ip_address": sign_in.get("ipAddress") or "",
		"app_display_name": sign_in.get("appDisplayName") or "",
		"is_noteworthy": signin_is_noteworthy(sign_in),
		"sign_in_time": sign_in_time,
	}


def signin_to_display_row(sign_in):
	device = sign_in.get("deviceDetail") or {}
	location = sign_in.get("location") or {}
	created = sign_in.get("createdDateTime")
	row = {
		"TimeGenerated": created,
		"UserPrincipalName": sign_in.get("userPrincipalName"),
		"IPAddress": sign_in.get("ipAddress"),
		"CountryCode": location.get("countryOrRegion"),
		"AppDisplayName": sign_in.get("appDisplayName"),
		"Resource": sign_in.get("resourceDisplayName"),
		"ClientAppUsed": sign_in.get("clientAppUsed"),
		"CorrelationId": sign_in.get("correlationId"),
		"SignInRisk": sign_in.get("riskLevelDuringSignIn"),
		"UserRisk": sign_in.get("riskLevelAggregated"),
		"DeviceName": device.get("displayName"),
		"DeviceId": device.get("deviceId"),
		"IsCompliant": device.get("isCompliant"),
		"IsManaged": device.get("isManaged"),
		"merk_interessant": signin_is_noteworthy(sign_in),
	}
	if created:
		try:
			dt = datetime.datetime.fromisoformat(str(created).replace("Z", "+00:00"))
			row["TimeGeneratedDisplay"] = dt.strftime("%d.%m.%Y %H:%M")
			row["TimeGeneratedSort"] = dt.strftime("%Y-%m-%d %H:%M")
		except (ValueError, AttributeError):
			row["TimeGeneratedDisplay"] = created
			row["TimeGeneratedSort"] = created
	return row


def fetch_device_code_signins_from_graph(dager=30, page_size=100, max_results=200):
	# 2026-06-19: Minimal OData filter + $select; deviceCode filtered server-side on Graph beta.
	import requests as api_requests
	from azure.identity import ClientSecretCredential

	sign_ins = []
	truncated = False
	error_message = None

	credential = ClientSecretCredential(
		tenant_id=os.environ['AZURE_TENANT_ID'],
		client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
		client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
	)
	token = credential.get_token("https://graph.microsoft.com/.default").token
	headers = {"Authorization": f"Bearer {token}"}

	since = (datetime.datetime.utcnow() - datetime.timedelta(days=dager)).strftime("%Y-%m-%dT%H:%M:%SZ")
	filter_expr = (
		f"authenticationProtocol eq 'deviceCode' and createdDateTime ge {since} "
		f"and status/errorCode eq 0"
	)
	url = (
		"https://graph.microsoft.com/beta/auditLogs/signIns"
		f"?$filter={quote(filter_expr)}"
		f"&$select={quote(DEVICE_CODE_SIGNIN_SELECT)}"
		f"&$top={page_size}"
	)

	while url and len(sign_ins) < max_results:
		response = api_requests.get(url, headers=headers, timeout=120)
		if response.status_code == 429:
			retry_after = int(response.headers.get("Retry-After", 30))
			time.sleep(retry_after)
			continue
		if response.status_code != 200:
			error_message = f"Microsoft Graph-kall feilet med HTTP {response.status_code}: {response.text[:500]}"
			break

		data = response.json()
		for sign_in in data.get("value", []):
			sign_ins.append(sign_in)
			if len(sign_ins) >= max_results:
				break

		next_link = data.get("@odata.nextLink")
		if len(sign_ins) >= max_results and next_link:
			truncated = True
		url = next_link if len(sign_ins) < max_results else None

	return sign_ins, truncated, error_message


def upsert_device_code_combos(sign_ins):
	"""Persist unique user+IP+app combos; return count of newly created noteworthy combos."""
	from systemoversikt.models import DeviceCodeSignInCombo

	new_noteworthy_count = 0
	combos_by_key = {}

	for sign_in in sign_ins:
		fields = signin_to_combo_fields(sign_in)
		if not fields["user_principal_name"] or not fields["sign_in_time"]:
			continue
		key = (
			fields["user_principal_name"],
			fields["ip_address"],
			fields["app_display_name"],
		)
		existing = combos_by_key.get(key)
		if existing is None or fields["sign_in_time"] > existing["sign_in_time"]:
			combos_by_key[key] = fields

	for fields in combos_by_key.values():
		obj, created = DeviceCodeSignInCombo.objects.get_or_create(
			user_principal_name=fields["user_principal_name"],
			ip_address=fields["ip_address"],
			app_display_name=fields["app_display_name"],
			defaults={
				"first_seen": fields["sign_in_time"],
				"last_seen": fields["sign_in_time"],
				"is_noteworthy": fields["is_noteworthy"],
			},
		)
		if created:
			if fields["is_noteworthy"]:
				new_noteworthy_count += 1
			continue

		updated_fields = []
		if fields["sign_in_time"] and fields["sign_in_time"] > obj.last_seen:
			obj.last_seen = fields["sign_in_time"]
			updated_fields.append("last_seen")
		if fields["sign_in_time"] and fields["sign_in_time"] < obj.first_seen:
			obj.first_seen = fields["sign_in_time"]
			updated_fields.append("first_seen")
		if fields["is_noteworthy"] and not obj.is_noteworthy:
			obj.is_noteworthy = True
			updated_fields.append("is_noteworthy")
		if updated_fields:
			obj.save(update_fields=updated_fields)

	return new_noteworthy_count


def prune_device_code_combos(retention_days=DEVICE_CODE_HISTORY_DAYS):
	from systemoversikt.models import DeviceCodeSignInCombo

	cutoff = timezone.now() - datetime.timedelta(days=retention_days)
	deleted, _ = DeviceCodeSignInCombo.objects.filter(last_seen__lt=cutoff).delete()
	return deleted


def build_device_code_history_summary(combos_queryset):
	"""Per-user aggregates for the last DEVICE_CODE_HISTORY_DAYS window."""
	by_user = defaultdict(lambda: {
		"ip_addresses": set(),
		"apps": set(),
		"first_seen": None,
		"last_seen": None,
		"merk_interessant": False,
	})

	for combo in combos_queryset:
		user = combo.user_principal_name
		entry = by_user[user]
		if combo.ip_address:
			entry["ip_addresses"].add(combo.ip_address)
		if combo.app_display_name:
			entry["apps"].add(combo.app_display_name)
		if entry["first_seen"] is None or combo.first_seen < entry["first_seen"]:
			entry["first_seen"] = combo.first_seen
		if entry["last_seen"] is None or combo.last_seen > entry["last_seen"]:
			entry["last_seen"] = combo.last_seen
		if combo.is_noteworthy:
			entry["merk_interessant"] = True

	rows = []
	for user_principal_name, entry in by_user.items():
		first_seen = entry["first_seen"]
		last_seen = entry["last_seen"]
		rows.append({
			"user_principal_name": user_principal_name,
			"ip_addresses": ", ".join(sorted(entry["ip_addresses"])),
			"apps": ", ".join(sorted(entry["apps"])),
			"first_seen_display": first_seen.strftime("%d.%m.%Y %H:%M") if first_seen else "",
			"first_seen_sort": first_seen.strftime("%Y-%m-%d %H:%M") if first_seen else "",
			"last_seen_display": last_seen.strftime("%d.%m.%Y %H:%M") if last_seen else "",
			"last_seen_sort": last_seen.strftime("%Y-%m-%d %H:%M") if last_seen else "",
			"merk_interessant": entry["merk_interessant"],
		})

	rows.sort(key=lambda row: row.get("last_seen_sort") or "", reverse=True)
	return rows
