# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: BloodHound preventive check constants (BH-01–BH-07).
from systemoversikt.models import PRIVILEGERTE_GRUPPER_AD

DCSYNC_RIGHTS = frozenset({'GetChanges', 'GetChangesAll'})
DANGEROUS_DOMAIN_RIGHTS = frozenset({'GenericAll', 'WriteDacl', 'WriteOwner'})

DANGEROUS_ACL_RIGHTS = frozenset({
	'GenericAll',
	'WriteOwner',
	'WriteDacl',
	'AddMember',
	'ForceChangePassword',
	'AllExtendedRights',
})

GPO_WRITE_RIGHTS = frozenset({'GenericAll', 'WriteOwner', 'WriteDacl'})

EXTRA_PRIVILEGED_GROUPS = frozenset({
	'Domain Admins',
	'Enterprise Admins',
	'Schema Admins',
	'Administrators',
})

BH_CHECK_META = {
	'BH-01': {'title': 'DCSync-rettighet', 'severity': 'critical'},
	'BH-02': {'title': 'Farlig ACL på privilegert gruppe', 'severity': 'critical'},
	'BH-03': {'title': 'Unconstrained delegation', 'severity': 'high'},
	'BH-04': {'title': 'Resource-based constrained delegation (RBCD)', 'severity': 'high'},
	'BH-05': {'title': 'Kerberoastbar konto med privilegium', 'severity': 'high'},
	'BH-06': {'title': 'Skriverettighet på GPO', 'severity': 'medium'},
	'BH-07': {'title': 'SID history på konto', 'severity': 'medium'},
}


def privileged_group_name_set():
	names = set()
	for name in PRIVILEGERTE_GRUPPER_AD:
		names.add(name.lower())
	for name in EXTRA_PRIVILEGED_GROUPS:
		names.add(name.lower())
	return names


def severity_for_bh02(right_name):
	if right_name in ('GenericAll', 'WriteOwner', 'WriteDacl', 'AllExtendedRights'):
		return 'critical'
	return 'high'
