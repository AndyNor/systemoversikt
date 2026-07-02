# -*- coding: utf-8 -*-
# Change log:
# 2026-07-02: Merge status + findings into one Bloodhound page; legacy URLs redirect here.
# 2026-06-23: BloodHound views require systemoversikt.view_qualysvuln (same as vulnstats).
# 2026-06-23: Findings page – check catalog with looks_for/risk descriptions.
# 2026-06-23: BloodHound preventive findings page (BH-01–BH-07).
# 2026-06-23: BloodHound snapshot status page – object counts from latest upload.
import re

from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404
from django.shortcuts import redirect, render

from systemoversikt.bloodhound.constants import BH_CHECK_META, bh_check_catalog
from systemoversikt.models import BloodHoundFinding, BloodHoundSnapshot
from systemoversikt.views import _integrasjonsstatus, formater_permissions

SNAPSHOT_ID_RE = re.compile(r'^\d{14}$')
VALID_CHECKS = frozenset(BH_CHECK_META.keys())
VALID_SEVERITIES = frozenset({'critical', 'high', 'medium'})
FINDINGS_PAGE_SIZE = 100


def _bloodhound_required_permissions():
	return ['systemoversikt.view_qualysvuln']


def _bloodhound_permission_denied(request, required_permissions):
	return render(request, '403.html', {
		'required_permissions': required_permissions,
		'groups': request.user.groups,
	})


def _selected_bloodhound_snapshot(request, snapshots):
	selected_id = request.GET.get('snapshot', '').strip()
	if selected_id and not SNAPSHOT_ID_RE.match(selected_id):
		raise Http404

	if not snapshots:
		return None

	if selected_id:
		selected = BloodHoundSnapshot.objects.filter(snapshot_id=selected_id).first()
		if not selected:
			raise Http404
		return selected

	return snapshots[0]


def sikkerhet_bloodhound(request):
	# 2026-07-02: Combined snapshot status and preventive findings on one page.
	required_permissions = _bloodhound_required_permissions()
	if not any(map(request.user.has_perm, required_permissions)):
		return _bloodhound_permission_denied(request, required_permissions)

	check_filter = request.GET.get('check', '').strip().upper()
	if check_filter and check_filter not in VALID_CHECKS:
		raise Http404

	severity_filter = request.GET.get('severity', '').strip().lower()
	if severity_filter and severity_filter not in VALID_SEVERITIES:
		raise Http404

	snapshots = list(
		BloodHoundSnapshot.objects.filter(status='indexed').order_by('-snapshot_id')[:20]
	)
	selected = _selected_bloodhound_snapshot(request, snapshots)

	findings_qs = BloodHoundFinding.objects.none()
	summary_by_check = []
	summary_by_severity = []
	if selected:
		findings_qs = BloodHoundFinding.objects.filter(snapshot=selected).select_related('user')
		if check_filter:
			findings_qs = findings_qs.filter(check_id=check_filter)
		if severity_filter:
			findings_qs = findings_qs.filter(severity=severity_filter)

		raw_by_check = list(
			BloodHoundFinding.objects.filter(snapshot=selected)
			.values('check_id', 'severity')
			.annotate(count=Count('id'))
			.order_by('check_id')
		)
		for row in raw_by_check:
			meta = BH_CHECK_META.get(row['check_id'], {})
			summary_by_check.append({
				'check_id': row['check_id'],
				'severity': row['severity'],
				'count': row['count'],
				'title': meta.get('title', ''),
			})
		summary_by_severity = list(
			BloodHoundFinding.objects.filter(snapshot=selected)
			.values('severity')
			.annotate(count=Count('id'))
			.order_by('severity')
		)

	paginator = Paginator(findings_qs, FINDINGS_PAGE_SIZE)
	page_number = request.GET.get('page', '1')
	page_obj = paginator.get_page(page_number)

	query_parts = []
	if selected:
		query_parts.append(f'snapshot={selected.snapshot_id}')
	if check_filter:
		query_parts.append(f'check={check_filter}')
	if severity_filter:
		query_parts.append(f'severity={severity_filter}')
	filter_query = '&'.join(query_parts)

	active_check_meta = BH_CHECK_META.get(check_filter) if check_filter else None

	return render(request, 'sikkerhet_bloodhound.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'snapshots': snapshots,
		'selected': selected,
		'page_obj': page_obj,
		'summary_by_check': summary_by_check,
		'summary_by_severity': summary_by_severity,
		'check_filter': check_filter,
		'severity_filter': severity_filter,
		'filter_query': filter_query,
		'bh_check_catalog': bh_check_catalog(),
		'active_check_meta': active_check_meta,
		'integrasjonsstatus': _integrasjonsstatus('bloodhound_ad'),
	})


def sikkerhet_bloodhound_legacy_redirect(request):
	# 2026-07-02: Preserve bookmarks to old status/findings URLs.
	target = '/sikkerhet/bloodhound/'
	if request.GET:
		target = f'{target}?{request.GET.urlencode()}'
	return redirect(target, permanent=True)
