# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: Tests for flat import dir and replace-on-upload.
# 2026-06-23: Tests for BloodHound ingest (shard meta.count summation, tar.gz extract).
import json
import os
import shutil
import tarfile
import tempfile

from django.test import SimpleTestCase

from systemoversikt.bloodhound.ingest import (
	BH_FILE_RE,
	BloodHoundIngestError,
	bloodhound_import_root,
	detect_snapshot_id,
	ingest_tar_gz_archive,
	snapshot_id_readable,
	summarize_json_files,
)


def _write_bh_json(directory, basename, obj_type, count):
	path = os.path.join(directory, basename)
	payload = {
		'data': [],
		'meta': {'type': obj_type, 'count': count, 'version': 5, 'methods': 127999},
	}
	with open(path, 'w', encoding='utf-8') as handle:
		json.dump(payload, handle)
	return path


def _make_fixture_tar(work_dir, import_root):
	snapshot_id = '20260622193924'
	_write_bh_json(work_dir, f'{snapshot_id}_domains.json', 'domains', 1)
	_write_bh_json(work_dir, f'{snapshot_id}_users.json', 'users', 100)
	_write_bh_json(work_dir, f'{snapshot_id}_users_01.json', 'users', 50)
	_write_bh_json(work_dir, f'{snapshot_id}_computers.json', 'computers', 40)
	_write_bh_json(work_dir, 'output.log', 'users', 999)  # ignored

	tar_path = os.path.join(work_dir, 'bundle.tar.gz')
	with tarfile.open(tar_path, 'w:gz') as tar:
		for name in os.listdir(work_dir):
			if name.endswith('.tar.gz'):
				continue
			tar.add(os.path.join(work_dir, name), arcname=name)

	return tar_path, snapshot_id


class BloodHoundIngestTests(SimpleTestCase):
	def test_import_root_default_under_package_import(self):
		old_dir = os.environ.pop('BLOODHOUND_IMPORT_DIR', None)
		try:
			root = bloodhound_import_root()
			self.assertTrue(root.endswith(os.path.join('import', 'bloodhound')))
		finally:
			if old_dir is not None:
				os.environ['BLOODHOUND_IMPORT_DIR'] = old_dir

	def test_filename_regex(self):
		self.assertTrue(BH_FILE_RE.match('20260622193924_users.json'))
		self.assertTrue(BH_FILE_RE.match('20260622193924_users_01.json'))
		self.assertFalse(BH_FILE_RE.match('output.log'))

	def test_detect_snapshot_id(self):
		names = ['20260622193924_users.json', '20260622193924_users_01.json']
		self.assertEqual(detect_snapshot_id(names), '20260622193924')

	def test_snapshot_id_readable(self):
		self.assertEqual(snapshot_id_readable('20260622193924'), '2026-06-22 19:39:24')

	def test_summarize_json_shards(self):
		work = tempfile.mkdtemp()
		try:
			files = {
				'20260622193924_domains.json': _write_bh_json(work, '20260622193924_domains.json', 'domains', 1),
				'20260622193924_users.json': _write_bh_json(work, '20260622193924_users.json', 'users', 100),
				'20260622193924_users_01.json': _write_bh_json(work, '20260622193924_users_01.json', 'users', 50),
			}
			summary = summarize_json_files(files)
			self.assertEqual(summary['counts']['users'], 150)
			self.assertEqual(summary['counts']['domains'], 1)
			self.assertEqual(summary['shards']['users'], 2)
		finally:
			shutil.rmtree(work, ignore_errors=True)

	def test_ingest_empty_tar_reports_debug(self):
		work = tempfile.mkdtemp()
		tar_path = os.path.join(work, 'empty.tar.gz')
		try:
			with tarfile.open(tar_path, 'w:gz'):
				pass
			with self.assertRaises(BloodHoundIngestError) as ctx:
				ingest_tar_gz_archive(tar_path)
			self.assertEqual(ctx.exception.phase, 'collect')
			self.assertIn('tar_members', ctx.exception.debug)
		finally:
			shutil.rmtree(work, ignore_errors=True)

	def test_ingest_tar_gz_archive_flat_storage(self):
		work = tempfile.mkdtemp()
		import_root = os.path.join(work, 'import')
		os.makedirs(import_root, exist_ok=True)
		try:
			tar_path, snapshot_id = _make_fixture_tar(work, import_root)
			os.environ['BLOODHOUND_IMPORT_DIR'] = import_root
			result = ingest_tar_gz_archive(tar_path)

			self.assertEqual(result['snapshot_id'], snapshot_id)
			self.assertEqual(result['counts']['users'], 150)
			self.assertEqual(result['counts']['computers'], 40)
			self.assertEqual(result['storage_path'], import_root)
			self.assertTrue(os.path.isfile(os.path.join(import_root, f'{snapshot_id}_domains.json')))
			self.assertFalse(os.path.isdir(os.path.join(import_root, snapshot_id)))
		finally:
			shutil.rmtree(work, ignore_errors=True)
			os.environ.pop('BLOODHOUND_IMPORT_DIR', None)

	def test_ingest_replaces_previous_files(self):
		work = tempfile.mkdtemp()
		import_root = os.path.join(work, 'import')
		os.makedirs(import_root, exist_ok=True)
		try:
			os.environ['BLOODHOUND_IMPORT_DIR'] = import_root
			old_id = '20260101000000'
			_write_bh_json(import_root, f'{old_id}_domains.json', 'domains', 1)
			_write_bh_json(import_root, f'{old_id}_users.json', 'users', 1)

			tar_path, new_id = _make_fixture_tar(work, import_root)
			result = ingest_tar_gz_archive(tar_path)

			self.assertEqual(result['snapshot_id'], new_id)
			self.assertFalse(os.path.exists(os.path.join(import_root, f'{old_id}_users.json')))
			self.assertTrue(os.path.exists(os.path.join(import_root, f'{new_id}_users.json')))
			self.assertIn(f'{old_id}_users.json', result['removed_files'])
		finally:
			shutil.rmtree(work, ignore_errors=True)
			os.environ.pop('BLOODHOUND_IMPORT_DIR', None)
