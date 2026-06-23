# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: Preventive BloodHound checks BH-01 through BH-07.
from systemoversikt.bloodhound.constants import (
	BH_CHECK_META,
	DANGEROUS_ACL_RIGHTS,
	DANGEROUS_DOMAIN_RIGHTS,
	DCSYNC_RIGHTS,
	GPO_WRITE_RIGHTS,
	severity_for_bh02,
)
from systemoversikt.bloodhound.parser import (
	_display_name,
	_object_id,
	_properties,
	_relation_ids,
	iter_objects,
)


def _finding(check_id, principal_sid, principal_name, target_sid='', target_name='',
		right_name='', detail=None, severity=None):
	meta = BH_CHECK_META[check_id]
	return {
		'check_id': check_id,
		'severity': severity or meta['severity'],
		'title': meta['title'],
		'principal_sid': principal_sid or '',
		'principal_name': principal_name or principal_sid or '',
		'target_sid': target_sid or '',
		'target_name': target_name or target_sid or '',
		'right_name': right_name or '',
		'detail': detail or {},
	}


def _ace_findings_bh02(index, target_id, target_name, aces):
	for ace in aces or []:
		right = ace.get('RightName') or ''
		if right not in DANGEROUS_ACL_RIGHTS:
			continue
		principal_sid = ace.get('PrincipalSID') or ''
		yield _finding(
			'BH-02',
			principal_sid,
			index.resolve_name(principal_sid),
			target_id,
			target_name,
			right,
			{'is_inherited': ace.get('IsInherited', False)},
			severity=severity_for_bh02(right),
		)


def findings_for_object(index, meta_type, obj):
	"""Yield all findings for a single BloodHound object (single-pass analysis)."""
	oid = _object_id(obj)
	props = _properties(obj)
	target_name = _display_name(props, oid)

	if meta_type == 'domains':
		for ace in obj.get('Aces') or []:
			right = ace.get('RightName') or ''
			if right not in DCSYNC_RIGHTS and right not in DANGEROUS_DOMAIN_RIGHTS:
				continue
			principal_sid = ace.get('PrincipalSID') or ''
			yield _finding(
				'BH-01',
				principal_sid,
				index.resolve_name(principal_sid),
				oid,
				target_name,
				right,
				{'is_inherited': ace.get('IsInherited', False)},
			)

	if index.is_privileged_group(oid):
		yield from _ace_findings_bh02(index, oid, target_name, obj.get('Aces'))

	if meta_type in ('users', 'computers') and props.get('unconstraineddelegation'):
		yield _finding(
			'BH-03',
			oid,
			target_name,
			oid,
			target_name,
			'',
			{'object_type': meta_type},
		)

	if meta_type == 'computers':
		for principal_id in _relation_ids(obj.get('AllowedToAct')):
			yield _finding(
				'BH-04',
				principal_id,
				index.resolve_name(principal_id),
				oid,
				target_name,
				'AllowedToAct',
				{'computer': target_name},
			)

	if meta_type == 'users' and props.get('hasspn') and index.user_in_privileged_group(oid):
		spns = props.get('serviceprincipalnames') or props.get('spns') or []
		yield _finding(
			'BH-05',
			oid,
			target_name,
			oid,
			target_name,
			'',
			{'spn_count': len(spns) if isinstance(spns, list) else 0},
		)

	if meta_type == 'gpos':
		for ace in obj.get('Aces') or []:
			right = ace.get('RightName') or ''
			if right not in GPO_WRITE_RIGHTS:
				continue
			principal_sid = ace.get('PrincipalSID') or ''
			yield _finding(
				'BH-06',
				principal_sid,
				index.resolve_name(principal_sid),
				oid,
				target_name,
				right,
				{'is_inherited': ace.get('IsInherited', False)},
			)

	if meta_type == 'users':
		history = props.get('sidhistory') or []
		if history:
			yield _finding(
				'BH-07',
				oid,
				target_name,
				oid,
				target_name,
				'',
				{'sidhistory_count': len(history) if isinstance(history, list) else 1},
			)


def run_all_checks(index, import_directory):
	"""One pass over all JSON shards; yield finding dicts."""
	for meta_type, obj in iter_objects(import_directory):
		yield from findings_for_object(index, meta_type, obj)
