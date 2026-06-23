# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: Tests for BloodHound preventive checks BH-01–BH-07.
import json
import os
import shutil
import tempfile

from django.test import SimpleTestCase

from systemoversikt.bloodhound.checks import findings_for_object, run_all_checks
from systemoversikt.bloodhound.parser import build_index


SNAPSHOT_ID = '20260101000000'
DOMAIN_SID = 'S-1-5-21-1000-1'
DA_GROUP_SID = 'S-1-5-21-1000-512'
USER_SID = 'S-1-5-21-1000-1001'
ATTACKER_SID = 'S-1-5-21-1000-2001'
COMPUTER_SID = 'S-1-5-21-1000-3001'
GPO_SID = 'S-1-5-21-1000-4001'


def _write_shard(directory, obj_type, objects):
	basename = f'{SNAPSHOT_ID}_{obj_type}.json'
	path = os.path.join(directory, basename)
	payload = {
		'data': objects,
		'meta': {'type': obj_type, 'count': len(objects), 'version': 5},
	}
	with open(path, 'w', encoding='utf-8') as handle:
		json.dump(payload, handle)


def _mini_fixture_dir():
	work = tempfile.mkdtemp()
	_write_shard(work, 'domains', [{
		'ObjectIdentifier': DOMAIN_SID,
		'ObjectType': 'Domain',
		'Properties': {'name': 'TEST.LOCAL'},
		'Aces': [{
			'PrincipalSID': ATTACKER_SID,
			'PrincipalType': 'User',
			'RightName': 'GetChangesAll',
			'IsInherited': False,
		}],
	}])
	_write_shard(work, 'groups', [{
		'ObjectIdentifier': DA_GROUP_SID,
		'ObjectType': 'Group',
		'Properties': {'name': 'DOMAIN ADMINS@TEST.LOCAL', 'samaccountname': 'Domain Admins'},
		'Aces': [{
			'PrincipalSID': ATTACKER_SID,
			'PrincipalType': 'User',
			'RightName': 'GenericAll',
			'IsInherited': False,
		}],
	}])
	_write_shard(work, 'users', [
		{
			'ObjectIdentifier': USER_SID,
			'ObjectType': 'User',
			'Properties': {
				'name': 'SVC@TEST.LOCAL',
				'samaccountname': 'svc',
				'hasspn': True,
				'serviceprincipalnames': ['HTTP/svc.test.local'],
			},
			'MemberOf': [{'ObjectIdentifier': DA_GROUP_SID, 'ObjectType': 'Group'}],
		},
		{
			'ObjectIdentifier': 'S-1-5-21-1000-1002',
			'ObjectType': 'User',
			'Properties': {
				'name': 'OLD@TEST.LOCAL',
				'sidhistory': ['S-1-5-21-999-1'],
			},
		},
		{
			'ObjectIdentifier': ATTACKER_SID,
			'ObjectType': 'User',
			'Properties': {'name': 'ATTACKER@TEST.LOCAL', 'unconstraineddelegation': True},
		},
	])
	_write_shard(work, 'computers', [{
		'ObjectIdentifier': COMPUTER_SID,
		'ObjectType': 'Computer',
		'Properties': {'name': 'SRV01.TEST.LOCAL'},
		'AllowedToAct': [{'ObjectIdentifier': ATTACKER_SID, 'ObjectType': 'User'}],
	}])
	_write_shard(work, 'gpos', [{
		'ObjectIdentifier': GPO_SID,
		'ObjectType': 'GPO',
		'Properties': {'name': 'Default GPO'},
		'Aces': [{
			'PrincipalSID': ATTACKER_SID,
			'PrincipalType': 'User',
			'RightName': 'WriteDacl',
			'IsInherited': False,
		}],
	}])
	return work


class BloodHoundChecksTests(SimpleTestCase):
	def test_bh01_dcsync(self):
		work = _mini_fixture_dir()
		try:
			index = build_index(work)
			findings = list(run_all_checks(index, work))
			bh01 = [f for f in findings if f['check_id'] == 'BH-01']
			self.assertEqual(len(bh01), 1)
			self.assertEqual(bh01[0]['right_name'], 'GetChangesAll')
		finally:
			shutil.rmtree(work, ignore_errors=True)

	def test_bh02_privileged_acl(self):
		work = _mini_fixture_dir()
		try:
			index = build_index(work)
			findings = [f for f in run_all_checks(index, work) if f['check_id'] == 'BH-02']
			self.assertTrue(any(f['right_name'] == 'GenericAll' for f in findings))
		finally:
			shutil.rmtree(work, ignore_errors=True)

	def test_bh03_bh07_flags(self):
		work = _mini_fixture_dir()
		try:
			index = build_index(work)
			ids = {f['check_id'] for f in run_all_checks(index, work)}
			self.assertIn('BH-03', ids)
			self.assertIn('BH-07', ids)
		finally:
			shutil.rmtree(work, ignore_errors=True)

	def test_bh04_rbcd(self):
		work = _mini_fixture_dir()
		try:
			index = build_index(work)
			bh04 = [f for f in run_all_checks(index, work) if f['check_id'] == 'BH-04']
			self.assertEqual(len(bh04), 1)
		finally:
			shutil.rmtree(work, ignore_errors=True)

	def test_bh05_kerberoast_privileged(self):
		work = _mini_fixture_dir()
		try:
			index = build_index(work)
			bh05 = [f for f in run_all_checks(index, work) if f['check_id'] == 'BH-05']
			self.assertEqual(len(bh05), 1)
			self.assertEqual(bh05[0]['principal_sid'], USER_SID)
		finally:
			shutil.rmtree(work, ignore_errors=True)

	def test_bh06_gpo_write(self):
		work = _mini_fixture_dir()
		try:
			index = build_index(work)
			bh06 = [f for f in run_all_checks(index, work) if f['check_id'] == 'BH-06']
			self.assertEqual(len(bh06), 1)
			self.assertEqual(bh06[0]['right_name'], 'WriteDacl')
		finally:
			shutil.rmtree(work, ignore_errors=True)

	def test_findings_for_object_isolated(self):
		obj = {
			'ObjectIdentifier': DOMAIN_SID,
			'Properties': {'name': 'TEST.LOCAL'},
			'Aces': [{'PrincipalSID': ATTACKER_SID, 'RightName': 'GetChanges', 'IsInherited': False}],
		}
		index = BloodHoundIndexStub()
		findings = list(findings_for_object(index, 'domains', obj))
		self.assertEqual(findings[0]['check_id'], 'BH-01')


class BloodHoundIndexStub:
	def resolve_name(self, sid):
		return f'name:{sid}'

	def is_privileged_group(self, oid):
		return False

	def user_in_privileged_group(self, user_id):
		return False
