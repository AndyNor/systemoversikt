# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: Flat storage in import/bloodhound – wipe previous JSON before each upload.
# 2026-06-23: Writable-check helpers; import stays under systemoversikt/import/bloodhound.
# 2026-06-23: Richer ingest errors (phase + debug) for upload API troubleshooting.
# 2026-06-23: BloodHound tar.gz ingest – extract, shard-aware meta.count summary, snapshot retention.
import gc
import json
import os
import re
import shutil
import tarfile
import tempfile
from pathlib import Path

BH_FILE_RE = re.compile(r'^(\d{14})_([a-z]+)(?:_\d+)?\.json$')
OBJECT_TYPES = (
	'users',
	'computers',
	'groups',
	'gpos',
	'ous',
	'domains',
	'containers',
)

_DEBUG_LIST_LIMIT = 40


class BloodHoundIngestError(Exception):
	"""Ingest failure with structured detail for API logging and responses."""

	def __init__(self, message, phase='ingest', debug=None):
		self.phase = phase
		self.debug = debug or {}
		super().__init__(message)


def _truncate_list(items, limit=_DEBUG_LIST_LIMIT):
	items = list(items)
	if len(items) <= limit:
		return items
	return items[:limit] + [f'… and {len(items) - limit} more']


def list_tar_member_names(archive_path, limit=_DEBUG_LIST_LIMIT):
	"""List member paths inside a tar.gz without extracting (for error diagnostics)."""
	try:
		with tarfile.open(str(archive_path), 'r:gz') as tar:
			return _truncate_list(m.name for m in tar.getmembers() if m.isfile())
	except Exception as exc:
		return [f'(could not read tar: {exc})']


def bloodhound_import_root():
	"""Directory for extracted BloodHound snapshots."""
	override = os.environ.get('BLOODHOUND_IMPORT_DIR')
	if override:
		return override
	pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	return os.path.join(pkg_dir, 'import', 'bloodhound')


def _storage_permission_hint(import_root=None):
	root = import_root or bloodhound_import_root()
	return (
		f'Ensure {root} is owned by apache and writable (gunicorn user). '
		f'Example: sudo chown -R apache:apache {root} && sudo chmod 775 {root}'
	)


def ensure_writable_import_root(import_root=None):
	"""Create import root if missing; raise BloodHoundIngestError when not writable."""
	root = import_root or bloodhound_import_root()
	try:
		os.makedirs(root, mode=0o775, exist_ok=True)
	except PermissionError as exc:
		raise BloodHoundIngestError(
			f'Cannot create BloodHound import directory: {root}',
			phase='storage',
			debug={
				'import_root': root,
				'hint': _storage_permission_hint(root),
				'errno': exc.errno,
			},
		) from exc
	if not os.access(root, os.W_OK):
		raise BloodHoundIngestError(
			f'BloodHound import directory is not writable: {root}',
			phase='storage',
			debug={
				'import_root': root,
				'hint': _storage_permission_hint(root),
			},
		)
	return root


def bloodhound_upload_max_bytes():
	return int(os.environ.get('BLOODHOUND_UPLOAD_MAX_BYTES', 2 * 1024 * 1024 * 1024))


def snapshot_id_from_filename(filename):
	match = BH_FILE_RE.match(filename)
	if not match:
		return None
	return match.group(1)


def detect_snapshot_id(filenames):
	"""Pick the snapshot prefix shared by BloodHound JSON files."""
	ids = set()
	for name in filenames:
		sid = snapshot_id_from_filename(name)
		if sid:
			ids.add(sid)
	if len(ids) == 1:
		return next(iter(ids))
	if ids:
		return sorted(ids)[-1]
	return None


def snapshot_id_readable(snapshot_id):
	"""YYYYMMDDHHMMSS -> YYYY-MM-DD HH:MM:SS."""
	if not snapshot_id or len(snapshot_id) != 14 or not snapshot_id.isdigit():
		return snapshot_id or ''
	return (
		f'{snapshot_id[0:4]}-{snapshot_id[4:6]}-{snapshot_id[6:8]} '
		f'{snapshot_id[8:10]}:{snapshot_id[10:12]}:{snapshot_id[12:14]}'
	)


def _safe_extract_tar(tar, dest_dir):
	"""Extract tar members only under dest_dir (path traversal guard)."""
	dest = Path(dest_dir).resolve()
	for member in tar.getmembers():
		target = (dest / member.name).resolve()
		if not str(target).startswith(str(dest)):
			raise BloodHoundIngestError(
				f'Unsafe path in archive: {member.name}',
				phase='extract',
				debug={'member': member.name},
			)
		tar.extract(member, path=dest_dir)


def extract_archive(archive_path, work_dir):
	"""Extract .tar.gz or .tgz to work_dir. Returns list of extracted file paths."""
	archive_path = str(archive_path)
	with tarfile.open(archive_path, 'r:gz') as tar:
		_safe_extract_tar(tar, work_dir)
	paths = []
	for root, _dirs, files in os.walk(work_dir):
		for name in files:
			paths.append(os.path.join(root, name))
	return paths


def collect_bloodhound_json_files(directory):
	"""Return BloodHound JSON paths keyed by basename."""
	result = {}
	for root, _dirs, files in os.walk(directory):
		for name in files:
			if not BH_FILE_RE.match(name):
				continue
			result[name] = os.path.join(root, name)
	return result


def summarize_json_files(json_paths_by_basename):
	"""
	Sum meta.count per object type across shard files.
	json_paths_by_basename: {basename: absolute_path}
	"""
	counts = {t: 0 for t in OBJECT_TYPES}
	shards = {t: 0 for t in OBJECT_TYPES}
	meta_version = None
	collection_methods = None
	total_bytes = 0
	file_count = 0

	for basename in sorted(json_paths_by_basename):
		match = BH_FILE_RE.match(basename)
		if not match:
			continue
		obj_type = match.group(2)
		if obj_type not in counts:
			continue
		filepath = json_paths_by_basename[basename]
		file_count += 1
		total_bytes += os.path.getsize(filepath)
		shards[obj_type] += 1

		with open(filepath, 'r', encoding='utf-8') as handle:
			payload = json.load(handle)
		meta = payload.get('meta') or {}
		counts[obj_type] += int(meta.get('count', 0))
		if obj_type == 'domains':
			if meta.get('version') is not None:
				meta_version = meta.get('version')
			if meta.get('methods') is not None:
				collection_methods = meta.get('methods')
		del payload
		gc.collect()

	if counts.get('domains', 0) == 0 and file_count > 0:
		raise BloodHoundIngestError(
			'No domains.json found in archive – not a valid BloodHound export',
			phase='summarize',
			debug={
				'file_count': file_count,
				'object_types_seen': sorted(t for t, n in counts.items() if n > 0),
				'domain_shard_files': [
					name for name in json_paths_by_basename
					if BH_FILE_RE.match(name) and BH_FILE_RE.match(name).group(2) == 'domains'
				],
			},
		)

	return {
		'counts': counts,
		'shards': shards,
		'meta_version': meta_version,
		'collection_methods': collection_methods,
		'file_count': file_count,
		'total_bytes': total_bytes,
	}


def clear_bloodhound_import_dir(import_root=None):
	"""Remove previous BloodHound JSON, logs, and legacy snapshot subdirs."""
	root = ensure_writable_import_root(import_root)
	removed = []
	if not os.path.isdir(root):
		return removed
	for name in os.listdir(root):
		path = os.path.join(root, name)
		try:
			if os.path.isdir(path):
				shutil.rmtree(path)
				removed.append(name + '/')
			elif BH_FILE_RE.match(name) or name == 'output.log':
				os.remove(path)
				removed.append(name)
		except OSError as exc:
			raise BloodHoundIngestError(
				f'Cannot remove old BloodHound file: {path}',
				phase='storage',
				debug={
					'path': path,
					'import_root': root,
					'hint': _storage_permission_hint(root),
					'errno': getattr(exc, 'errno', None),
				},
			) from exc
	return removed


def stage_snapshot_files(json_paths_by_basename, snapshot_id, import_root=None):
	"""Replace import dir contents with the new snapshot JSON files (flat layout)."""
	root = ensure_writable_import_root(import_root)
	removed = clear_bloodhound_import_dir(import_root=root)
	for basename, src in json_paths_by_basename.items():
		if snapshot_id_from_filename(basename) != snapshot_id:
			continue
		dest = os.path.join(root, basename)
		try:
			shutil.copy2(src, dest)
		except OSError as exc:
			raise BloodHoundIngestError(
				f'Cannot write BloodHound file: {dest}',
				phase='storage',
				debug={
					'path': dest,
					'import_root': root,
					'hint': _storage_permission_hint(root),
					'errno': getattr(exc, 'errno', None),
				},
			) from exc
	return root, removed


def ingest_tar_gz_archive(archive_path):
	"""
	Extract tar.gz, summarize counts, stage under import root.
	Returns dict suitable for API response and DB persist.
	"""
	work_dir = tempfile.mkdtemp(prefix='bloodhound_upload_')
	tar_members = []
	try:
		tar_members = list_tar_member_names(archive_path)
		extract_archive(archive_path, work_dir)
		json_files = collect_bloodhound_json_files(work_dir)
		all_extracted = []
		for root, _dirs, files in os.walk(work_dir):
			for name in files:
				all_extracted.append(name)

		if not json_files:
			raise BloodHoundIngestError(
				'No BloodHound JSON files found in archive',
				phase='collect',
				debug={
					'tar_members': tar_members,
					'extracted_files': _truncate_list(sorted(all_extracted)),
					'expected_filename_pattern': r'^\d{14}_[a-z]+(_\d+)?\.json$',
				},
			)

		snapshot_id = detect_snapshot_id(json_files.keys())
		if not snapshot_id:
			raise BloodHoundIngestError(
				'Could not determine snapshot id from filenames',
				phase='snapshot_id',
				debug={
					'bloodhound_json_files': _truncate_list(sorted(json_files.keys())),
				},
			)

		summary = summarize_json_files(json_files)
		storage_path, removed_files = stage_snapshot_files(json_files, snapshot_id)

		return {
			'snapshot_id': snapshot_id,
			'storage_path': storage_path,
			'removed_files': removed_files,
			**summary,
		}
	except BloodHoundIngestError:
		raise
	except Exception as exc:
		raise BloodHoundIngestError(
			str(exc),
			phase='ingest',
			debug={'tar_members': tar_members},
		) from exc
	finally:
		shutil.rmtree(work_dir, ignore_errors=True)
