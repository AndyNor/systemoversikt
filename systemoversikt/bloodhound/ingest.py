# -*- coding: utf-8 -*-
# Change log:
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


def bloodhound_import_root():
	"""Directory for extracted BloodHound snapshots."""
	override = os.environ.get('BLOODHOUND_IMPORT_DIR')
	if override:
		return override
	pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	return os.path.join(pkg_dir, 'import', 'bloodhound')


def bloodhound_upload_max_bytes():
	return int(os.environ.get('BLOODHOUND_UPLOAD_MAX_BYTES', 2 * 1024 * 1024 * 1024))


def bloodhound_snapshot_retention():
	return int(os.environ.get('BLOODHOUND_SNAPSHOT_RETENTION', 3))


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
			raise ValueError(f'Unsafe path in archive: {member.name}')
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
		raise ValueError('No domains.json found in archive – not a valid BloodHound export')

	return {
		'counts': counts,
		'shards': shards,
		'meta_version': meta_version,
		'collection_methods': collection_methods,
		'file_count': file_count,
		'total_bytes': total_bytes,
	}


def stage_snapshot_files(json_paths_by_basename, snapshot_id, import_root=None):
	"""Move JSON files into import_root/snapshot_id/."""
	root = import_root or bloodhound_import_root()
	dest_dir = os.path.join(root, snapshot_id)
	os.makedirs(dest_dir, exist_ok=True)
	for basename, src in json_paths_by_basename.items():
		if not snapshot_id_from_filename(basename) == snapshot_id:
			continue
		shutil.copy2(src, os.path.join(dest_dir, basename))
	return dest_dir


def apply_snapshot_retention(import_root=None, keep=None):
	"""Delete oldest snapshot directories beyond retention limit."""
	root = import_root or bloodhound_import_root()
	if not os.path.isdir(root):
		return []
	keep = keep if keep is not None else bloodhound_snapshot_retention()
	snapshot_dirs = []
	for name in os.listdir(root):
		path = os.path.join(root, name)
		if os.path.isdir(path) and len(name) == 14 and name.isdigit():
			snapshot_dirs.append(name)
	snapshot_dirs.sort(reverse=True)
	removed = []
	for old_id in snapshot_dirs[keep:]:
		shutil.rmtree(os.path.join(root, old_id), ignore_errors=True)
		removed.append(old_id)
	return removed


def ingest_tar_gz_archive(archive_path):
	"""
	Extract tar.gz, summarize counts, stage under import root.
	Returns dict suitable for API response and DB persist.
	"""
	work_dir = tempfile.mkdtemp(prefix='bloodhound_upload_')
	try:
		extract_archive(archive_path, work_dir)
		json_files = collect_bloodhound_json_files(work_dir)
		if not json_files:
			raise ValueError('No BloodHound JSON files found in archive')

		snapshot_id = detect_snapshot_id(json_files.keys())
		if not snapshot_id:
			raise ValueError('Could not determine snapshot id from filenames')

		summary = summarize_json_files(json_files)
		storage_path = stage_snapshot_files(json_files, snapshot_id)
		removed = apply_snapshot_retention()

		return {
			'snapshot_id': snapshot_id,
			'storage_path': storage_path,
			'removed_snapshots': removed,
			**summary,
		}
	finally:
		shutil.rmtree(work_dir, ignore_errors=True)
