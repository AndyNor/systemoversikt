# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: SDDL parser for tool_ntfs – decode NTFS ACL strings without external deps.
"""Parse Windows SDDL strings into human-readable NTFS ACL summaries."""

import re

ACE_TYPES = {
	'A': 'Allow',
	'D': 'Deny',
	'AU': 'Audit',
	'AL': 'Alarm',
	'OA': 'Allow (object)',
	'OD': 'Deny (object)',
	'OU': 'Audit (object)',
	'OL': 'Alarm (object)',
	'ML': 'Mandatory label',
	'XA': 'Allow (callback)',
	'XD': 'Deny (callback)',
	'RA': 'Resource attribute',
	'SP': 'Scoped policy ID',
}

ACL_FLAGS = {
	'P': 'Protected',
	'AR': 'Auto inherit required',
	'AI': 'Auto inherited',
}

# Longest match first when splitting combined ACE flag strings (e.g. OICIID).
ACE_FLAG_TOKENS = sorted(
	[
		('OICIIO', ('Object inherit', 'Container inherit', 'Inherit only')),
		('OICIID', ('Object inherit', 'Container inherit', 'Inherit only', 'Inherited')),
		('CIIO', ('Container inherit', 'Inherit only')),
		('CIID', ('Container inherit', 'Inherit only', 'Inherited')),
		('OIIO', ('Object inherit', 'Inherit only')),
		('OICI', ('Object inherit', 'Container inherit')),
		('NR', ('Do not require integrity check',)),
		('NX', ('Do not allow cross-integrity writes',)),
		('CI', ('Container inherit',)),
		('OI', ('Object inherit',)),
		('IO', ('Inherit only',)),
		('NP', ('Do not propagate inherit',)),
		('ID', ('Inherited',)),
		('SA', ('Audit success',)),
		('FA', ('Audit failure',)),
	],
	key=lambda item: len(item[0]),
	reverse=True,
)

WELL_KNOWN_SIDS = {
	'AO': 'Account operators',
	'AN': 'Anonymous logon',
	'AU': 'Authenticated Users',
	'BA': 'Built-in Administrators',
	'BG': 'Built-in Guests',
	'BO': 'Built-in Backup Operators',
	'BU': 'Built-in Users',
	'CA': 'Certificate authority administrators',
	'CD': 'Certificate services DCOM access',
	'CG': 'Creator Group',
	'CO': 'Creator Owner',
	'DA': 'Domain administrators',
	'DC': 'Domain computers',
	'DD': 'Domain controllers',
	'DG': 'Domain guests',
	'DU': 'Domain users',
	'EA': 'Enterprise administrators',
	'ED': 'Enterprise domain controllers',
	'HI': 'High integrity',
	'IU': 'Interactive',
	'LA': 'Local administrator',
	'LG': 'Local guest',
	'LS': 'Local service',
	'LW': 'Low integrity',
	'ME': 'Medium integrity',
	'MU': 'Performance monitor users',
	'NO': 'Network configuration operators',
	'NS': 'Network service',
	'NU': 'Network',
	'OW': 'Owner rights',
	'PA': 'Group Policy administrators',
	'PO': 'Printer operators',
	'PS': 'Personal self',
	'PU': 'Power users',
	'RC': 'Restricted code',
	'RD': 'Terminal server users',
	'RE': 'Replicator',
	'RO': 'Enterprise RO DCs',
	'RS': 'RAS servers',
	'RU': 'Alias to allow previous Windows 2000',
	'SA': 'Schema administrators',
	'SI': 'Server operators',
	'SO': 'Server operators',
	'SU': 'Service',
	'SY': 'LOCAL SYSTEM',
	'UD': 'User-mode drivers',
	'WD': 'Everyone',
	'WR': 'Write restricted code',
}

SDDL_FILE_RIGHTS = {
	'FA': 'Full control',
	'FR': 'Generic read',
	'FW': 'Generic write',
	'FX': 'Generic execute',
	'GA': 'Generic all',
	'GR': 'Generic read',
	'GW': 'Generic write',
	'GX': 'Generic execute',
	'SD': 'Delete',
	'RC': 'Read control',
	'WD': 'Write DAC',
	'WO': 'Write owner',
	'RP': 'Read property',
	'WP': 'Write property',
	'CC': 'Create child',
	'DC': 'Delete child',
	'LC': 'List contents',
	'SW': 'Self',
	'LO': 'List object',
	'DT': 'Delete tree',
	'CR': 'Control access',
	'RD': 'Read data',
	'AD': 'Append data',
	'REA': 'Read extended attributes',
	'WEA': 'Write extended attributes',
	'X': 'Execute / traverse',
	'RA': 'Read attributes',
	'WA': 'Write attributes',
}

FILE_ACCESS_BITS = [
	(0x00010000, 'Delete'),
	(0x00020000, 'Read control'),
	(0x00040000, 'Write DAC'),
	(0x00080000, 'Write owner'),
	(0x00100000, 'Synchronize'),
	(0x00000001, 'Read data / List directory'),
	(0x00000002, 'Write data / Create file'),
	(0x00000004, 'Append data / Create subdirectory'),
	(0x00000008, 'Read extended attributes'),
	(0x00000010, 'Write extended attributes'),
	(0x00000020, 'Execute / Traverse'),
	(0x00000040, 'Delete child'),
	(0x00000080, 'Read attributes'),
	(0x00000100, 'Write attributes'),
]

FILE_ACCESS_PRESETS = {
	0x001F01FF: 'Full control',
	0x001301BF: 'Modify',
	0x001200A9: 'Read & execute',
	0x00120089: 'Read',
	0x00120116: 'Write',
	0x001200A0: 'Execute',
	0x120089: 'Generic read',
	0x120116: 'Generic write',
	0x1200A0: 'Generic execute',
	0x1200A9: 'Read & execute',
	0x1301BF: 'Modify',
	0x1F01FF: 'Full control',
}

PERMISSION_TYPES = ('file', 'directory', 'registry', 'service')


class SddlParseError(ValueError):
	pass


def normalize_sddl_input(text):
	"""Extract an SDDL string from pasted text (raw SDDL or icacls-style blobs)."""
	text = (text or '').strip()
	if not text:
		return ''

	for line in text.splitlines():
		candidate = line.strip()
		if re.search(r'^[OGDS]:', candidate) or re.search(r'\([AD][^;]*;', candidate):
			text = candidate
			break

	for prefix in ('O:', 'D:'):
		idx = text.find(prefix)
		if idx > 0:
			text = text[idx:]
			break

	return text.strip()


def _split_sections(sddl):
	sections = {}
	current_key = None
	current_val = []
	i = 0
	while i < len(sddl):
		ch = sddl[i]
		if ch in 'OGDS' and i + 1 < len(sddl) and sddl[i + 1] == ':':
			if current_key is not None:
				sections[current_key] = ''.join(current_val)
			current_key = ch
			current_val = []
			i += 2
			continue
		if current_key is not None:
			current_val.append(ch)
		i += 1
	if current_key is not None:
		sections[current_key] = ''.join(current_val)
	return sections


def _parse_acl_flags(flag_text):
	flags = []
	remaining = flag_text or ''
	while remaining:
		matched = False
		for code, label in ACL_FLAGS.items():
			if remaining.startswith(code):
				flags.append({'code': code, 'label': label})
				remaining = remaining[len(code):]
				matched = True
				break
		if not matched:
			flags.append({'code': remaining, 'label': remaining})
			break
	return flags


def _parse_ace_flags(flag_text):
	if not flag_text:
		return []
	flags = []
	remaining = flag_text
	seen = set()
	while remaining:
		matched = False
		for code, labels in ACE_FLAG_TOKENS:
			if remaining.startswith(code):
				for label in labels:
					if label not in seen:
						flags.append({'code': code, 'label': label})
						seen.add(label)
				remaining = remaining[len(code):]
				matched = True
				break
		if not matched:
			flags.append({'code': remaining, 'label': remaining})
			break
	return flags


def _describe_sid(sid):
	sid = (sid or '').strip()
	if not sid:
		return {'sid': '', 'name': ''}
	name = WELL_KNOWN_SIDS.get(sid)
	if name:
		return {'sid': sid, 'name': name}
	if sid.startswith('S-1-5-21-'):
		return {'sid': sid, 'name': 'Domain principal'}
	return {'sid': sid, 'name': ''}


def _decode_access_mask(rights, permission_type):
	rights = (rights or '').strip()
	if not rights:
		return {'raw': '', 'labels': []}

	if rights in SDDL_FILE_RIGHTS:
		return {'raw': rights, 'labels': [SDDL_FILE_RIGHTS[rights]]}

	if rights.startswith('0x') or rights.startswith('0X'):
		try:
			mask = int(rights, 16)
		except ValueError as exc:
			raise SddlParseError('Invalid access mask: %s' % rights) from exc
	elif rights.isdigit():
		mask = int(rights, 10)
	else:
		return {'raw': rights, 'labels': ['Unknown rights code: %s' % rights]}

	preset = FILE_ACCESS_PRESETS.get(mask)
	if preset:
		return {'raw': rights, 'labels': [preset]}

	labels = []
	for bit, label in FILE_ACCESS_BITS:
		if mask & bit:
			labels.append(label)
	if not labels:
		labels.append('0x%X' % mask)
	return {'raw': rights, 'labels': labels, 'mask': mask}


def _parse_ace(ace_text, permission_type):
	parts = ace_text.split(';')
	while len(parts) < 6:
		parts.append('')
	type_code, flag_text, rights, object_guid, inherit_object_guid, account_sid = parts[:6]
	ace_type = ACE_TYPES.get(type_code, 'Unknown (%s)' % type_code)
	return {
		'raw': ace_text,
		'type_code': type_code,
		'type': ace_type,
		'flags': _parse_ace_flags(flag_text),
		'rights': _decode_access_mask(rights, permission_type),
		'object_guid': object_guid,
		'inherit_object_guid': inherit_object_guid,
		'trustee': _describe_sid(account_sid),
	}


def _parse_acl(acl_text, permission_type):
	acl_text = acl_text or ''
	prefix_end = acl_text.find('(')
	if prefix_end == -1:
		return {'flags': _parse_acl_flags(acl_text), 'aces': []}
	flag_text = acl_text[:prefix_end]
	ace_blob = acl_text[prefix_end:]
	aces = []
	for match in re.finditer(r'\(([^)]*)\)', ace_blob):
		aces.append(_parse_ace(match.group(1), permission_type))
	return {'flags': _parse_acl_flags(flag_text), 'aces': aces}


def parse_sddl(sddl_text, permission_type='file'):
	"""Parse an SDDL string into structured owner/group/DACL/SACL data."""
	sddl_text = normalize_sddl_input(sddl_text)
	if not sddl_text:
		raise SddlParseError('No SDDL string provided.')

	if permission_type not in PERMISSION_TYPES:
		raise SddlParseError('Unknown permission type: %s' % permission_type)

	sections = _split_sections(sddl_text)
	if not sections:
		raise SddlParseError('Could not find SDDL sections (expected O:, G:, D: or S:).')

	result = {
		'raw': sddl_text,
		'permission_type': permission_type,
		'owner': _describe_sid(sections.get('O', '')),
		'group': _describe_sid(sections.get('G', '')),
		'dacl': _parse_acl(sections.get('D', ''), permission_type),
		'sacl': _parse_acl(sections.get('S', ''), permission_type),
	}
	return result
