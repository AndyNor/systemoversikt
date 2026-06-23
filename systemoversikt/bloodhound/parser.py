# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: Build BloodHound indexes from flat JSON shards for preventive checks.
import gc
import json
import os
from dataclasses import dataclass, field

from systemoversikt.bloodhound.constants import privileged_group_name_set
from systemoversikt.bloodhound.ingest import BH_FILE_RE, collect_bloodhound_json_files


def _object_id(obj):
	return obj.get('ObjectIdentifier') or ''


def _properties(obj):
	return obj.get('Properties') or {}


def _display_name(props, fallback=''):
	name = props.get('name') or props.get('samaccountname') or fallback
	return str(name)


def _sam_account_name(props):
	sam = props.get('samaccountname') or ''
	if sam:
		return str(sam)
	name = props.get('name') or ''
	if '@' in name:
		return name.split('@', 1)[0]
	return name


def _relation_ids(relations):
	ids = []
	for rel in relations or []:
		if isinstance(rel, dict):
			oid = rel.get('ObjectIdentifier')
			if oid:
				ids.append(oid)
	return ids


@dataclass
class BloodHoundIndex:
	sid_index: dict = field(default_factory=dict)
	privileged_group_ids: set = field(default_factory=set)
	user_member_of: dict = field(default_factory=dict)
	group_members: dict = field(default_factory=dict)
	object_member_of: dict = field(default_factory=dict)
	domain_object_ids: list = field(default_factory=list)
	privileged_names: set = field(default_factory=privileged_group_name_set)

	def resolve_name(self, object_id):
		entry = self.sid_index.get(object_id)
		if entry:
			return entry.get('name') or object_id
		return object_id

	def resolve_type(self, object_id):
		entry = self.sid_index.get(object_id)
		if entry:
			return entry.get('object_type') or ''
		return ''

	def is_privileged_group(self, object_id):
		return object_id in self.privileged_group_ids

	def user_in_privileged_group(self, user_id, depth=2):
		"""Membership in a privileged group, including nested MemberOf up to depth."""
		current = {user_id}
		for _ in range(depth):
			next_level = set()
			for oid in current:
				for group_id in self.object_member_of.get(oid, ()):
					if group_id in self.privileged_group_ids:
						return True
					next_level.add(group_id)
			current = next_level
		return False


def _is_privileged_group_props(props, privileged_names):
	for candidate in (_sam_account_name(props),):
		if candidate and candidate.lower() in privileged_names:
			return True
	name = props.get('name') or ''
	if '@' in name:
		prefix = name.split('@', 1)[0]
		if prefix.lower() in privileged_names:
			return True
	return False


def _index_object(index, obj, meta_type):
	oid = _object_id(obj)
	if not oid:
		return
	props = _properties(obj)
	object_type = obj.get('ObjectType') or meta_type.rstrip('s').capitalize()
	index.sid_index[oid] = {
		'name': _display_name(props, oid),
		'samaccountname': _sam_account_name(props),
		'object_type': object_type,
		'meta_type': meta_type,
	}

	if meta_type == 'groups':
		if _is_privileged_group_props(props, index.privileged_names):
			index.privileged_group_ids.add(oid)
		members = _relation_ids(obj.get('Members'))
		if members:
			index.group_members[oid] = set(members)

	member_of = _relation_ids(obj.get('MemberOf'))
	if member_of:
		index.object_member_of[oid] = set(member_of)
	if meta_type == 'users' and member_of:
		index.user_member_of[oid] = set(member_of)

	if meta_type == 'domains':
		index.domain_object_ids.append(oid)


def build_index(import_directory):
	"""Read all BloodHound JSON shards and build lookup indexes."""
	index = BloodHoundIndex()
	json_files = collect_bloodhound_json_files(import_directory)
	for basename in sorted(json_files):
		match = BH_FILE_RE.match(basename)
		if not match:
			continue
		meta_type = match.group(2)
		with open(json_files[basename], 'r', encoding='utf-8') as handle:
			payload = json.load(handle)
		for obj in payload.get('data') or []:
			_index_object(index, obj, meta_type)
		del payload
		gc.collect()

	return index


def iter_objects(import_directory):
	"""Yield (meta_type, obj) from all JSON shards."""
	json_files = collect_bloodhound_json_files(import_directory)
	for basename in sorted(json_files):
		match = BH_FILE_RE.match(basename)
		if not match:
			continue
		meta_type = match.group(2)
		with open(json_files[basename], 'r', encoding='utf-8') as handle:
			payload = json.load(handle)
		for obj in payload.get('data') or []:
			yield meta_type, obj
		del payload
		gc.collect()


def iter_objects_by_type(import_directory, meta_type):
	for obj_type, obj in iter_objects(import_directory):
		if obj_type == meta_type:
			yield obj
