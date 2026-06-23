# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: BloodHound preventive findings page (BH-01–BH-07).
# 2026-06-23: BloodHound snapshot status page – object counts from latest upload.
import re

from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404
from django.shortcuts import render

from systemoversikt.bloodhound.constants import BH_CHECK_META
from systemoversikt.models import BloodHoundFinding, BloodHoundSnapshot
from systemoversikt.views import _integrasjonsstatus, formater_permissions

SNAPSHOT_ID_RE = re.compile(r'^\d{14}$')
VALID_CHECKS = frozenset(BH_CHECK_META.keys())
VALID_SEVERITIES = frozenset({'critical', 'high', 'medium'})
FINDINGS_PAGE_SIZE = 100


def sikkerhet_bloodhound_status(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {
			'required_permissions': required_permissions,
			'groups': request.user.groups,
		})

	selected_id = request.GET.get('snapshot', '').strip()
	if selected_id and not SNAPSHOT_ID_RE.match(selected_id):
		raise Http404

	snapshots = list(
		BloodHoundSnapshot.objects.filter(status='indexed').order_by('-snapshot_id')[:20]
	)
	if not snapshots:
		selected = None
	else:
		if selected_id:
			selected = BloodHoundSnapshot.objects.filter(snapshot_id=selected_id).first()
			if not selected:
				raise Http404
		else:
			selected = snapshots[0]

	return render(request, 'sikkerhet_bloodhound_status.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'snapshots': snapshots,
		'selected': selected,
		'integrasjonsstatus': _integrasjonsstatus('bloodhound_ad'),
	})


def sikkerhet_bloodhound_findings(request):
	# 2026-06-23: Preventive findings from bloodhound_analyze batch job.
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {
			'required_permissions': required_permissions,
			'groups': request.user.groups,
		})

	selected_id = request.GET.get('snapshot', '').strip()
	if selected_id and not SNAPSHOT_ID_RE.match(selected_id):
		raise Http404

	check_filter = request.GET.get('check', '').strip().upper()
	if check_filter and check_filter not in VALID_CHECKS:
		raise Http404

	severity_filter = request.GET.get('severity', '').strip().lower()
	if severity_filter and severity_filter not in VALID_SEVERITIES:
		raise Http404

	snapshots = list(
		BloodHoundSnapshot.objects.filter(status='indexed').order_by('-snapshot_id')[:20]
	)
	if not snapshots:
		selected = None
		findings_qs = BloodHoundFinding.objects.none()
	else:
		if selected_id:
			selected = BloodHoundSnapshot.objects.filter(snapshot_id=selected_id).first()
			if not selected:
				raise Http404
		else:
			selected = snapshots[0]

		findings_qs = BloodHoundFinding.objects.filter(snapshot=selected).select_related('user')
		if check_filter:
			findings_qs = findings_qs.filter(check_id=check_filter)
		if severity_filter:
			findings_qs = findings_qs.filter(severity=severity_filter)

	summary_by_check = []
	summary_by_severity = []
	if selected:
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

	return render(request, 'sikkerhet_bloodhound_findings.html', {
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
		'integrasjonsstatus': _integrasjonsstatus('bloodhound_ad'),
	})
