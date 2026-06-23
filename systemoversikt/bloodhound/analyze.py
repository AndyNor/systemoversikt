# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: Run preventive checks and persist BloodHoundFinding rows (idempotent).
import os

from django.db import transaction
from django.utils import timezone

from systemoversikt.bloodhound.checks import run_all_checks
from systemoversikt.bloodhound.parser import build_index
from systemoversikt.models import BloodHoundFinding, BloodHoundSnapshot, Profile

_BULK_BATCH = 1000


def _resolve_users_by_sid(principal_sids):
	sids = [s for s in principal_sids if s]
	if not sids:
		return {}
	profiles = Profile.objects.filter(object_sid__in=sids).select_related('user')
	return {p.object_sid: p.user for p in profiles if p.user_id}


def analyze_snapshot(snapshot):
	"""
	Build index, run all checks, replace findings for snapshot.
	Returns finding count.
	"""
	import_directory = snapshot.storage_path
	if not import_directory or not os.path.isdir(import_directory):
		raise FileNotFoundError(f'BloodHound import directory not found: {import_directory}')

	snapshot.analysis_status = 'running'
	snapshot.analysis_error = ''
	snapshot.save(update_fields=['analysis_status', 'analysis_error'])

	try:
		index = build_index(import_directory)
		raw_findings = list(run_all_checks(index, import_directory))
		principal_sids = {f['principal_sid'] for f in raw_findings if f.get('principal_sid')}
		user_by_sid = _resolve_users_by_sid(principal_sids)

		with transaction.atomic():
			BloodHoundFinding.objects.filter(snapshot=snapshot).delete()
			batch = []
			for row in raw_findings:
				batch.append(BloodHoundFinding(
					snapshot=snapshot,
					check_id=row['check_id'],
					severity=row['severity'],
					title=row['title'],
					principal_sid=row.get('principal_sid') or '',
					principal_name=row.get('principal_name') or '',
					target_sid=row.get('target_sid') or '',
					target_name=row.get('target_name') or '',
					right_name=row.get('right_name') or '',
					detail=row.get('detail') or {},
					user=user_by_sid.get(row.get('principal_sid')),
				))
				if len(batch) >= _BULK_BATCH:
					BloodHoundFinding.objects.bulk_create(batch)
					batch = []
			if batch:
				BloodHoundFinding.objects.bulk_create(batch)

		snapshot.analysis_status = 'completed'
		snapshot.analysis_completed_at = timezone.now()
		snapshot.finding_count = len(raw_findings)
		snapshot.analysis_error = ''
		snapshot.save(update_fields=[
			'analysis_status', 'analysis_completed_at', 'finding_count', 'analysis_error',
		])
		return len(raw_findings)

	except Exception as exc:
		snapshot.analysis_status = 'failed'
		snapshot.analysis_error = str(exc)[:2000]
		snapshot.save(update_fields=['analysis_status', 'analysis_error'])
		raise
