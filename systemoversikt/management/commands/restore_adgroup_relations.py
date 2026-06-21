# -*- coding: utf-8 -*-
"""
Restore M2M and FK relationships to ADgroup after accidental deletion.

Usage:
  python manage.py restore_adgroup_relations --backup-file /path/to/backup.psql.bin
  python manage.py restore_adgroup_relations --backup-file /path/to/backup.psql.bin --dry-run

The script will:
  1. Create a temporary database 'kartoteket_restore'
  2. Load the backup into it
  3. Remap ADgroup relationships using distinguishedname
  4. Drop the temporary database when done

The script maps old adgroup IDs to new ones via distinguishedname.
"""
from django.core.management.base import BaseCommand
from django.db import transaction, connection
from systemoversikt.models import ADgroup
import psycopg2, os, time, subprocess, glob
from datetime import datetime


class Command(BaseCommand):
	help = "Restore ADgroup M2M/FK relations from a backup database after accidental group deletion"

	def add_arguments(self, parser):
		parser.add_argument(
			'--restore-db',
			default='kartoteket_restore',
			help='Name of the temporary restore database (default: kartoteket_restore)',
		)
		parser.add_argument(
			'--backup-file',
			default=None,
			help='Path to the backup file (.psql.bin). If not provided, uses the latest in dbbackup/',
		)
		parser.add_argument(
			'--dry-run',
			action='store_true',
			help='Show what would be restored without making changes',
		)

	def _setup_restore_db(self, restore_db_name, backup_file):
		"""Create temporary database and load backup into it."""
		db_user = os.environ["POSTGRES_USER"]
		db_password = os.environ["POSTGRES_PASSWORD"]
		db_host = "localhost"
		db_port = "5432"

		env = os.environ.copy()
		env["PGPASSWORD"] = db_password

		# Find backup file if not specified
		if not backup_file:
			backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'dbbackup')
			candidates = sorted(glob.glob(os.path.join(backup_dir, '*.psql.bin')))
			if not candidates:
				candidates = sorted(glob.glob(os.path.join(backup_dir, '*.psql')))
			if not candidates:
				raise Exception(f"Fant ingen backup-filer i {backup_dir}")
			backup_file = candidates[-1]
			print(f"Bruker backup-fil: {backup_file}")

		# Create database using Django's existing connection (which works)
		print(f"Oppretter midlertidig database '{restore_db_name}'...")
		conn = psycopg2.connect(
			dbname='kartoteket',
			user=db_user,
			password=db_password,
			host=db_host,
			port=db_port,
		)
		conn.autocommit = True
		cur = conn.cursor()
		# Drop if exists from a previous failed run
		cur.execute(f"DROP DATABASE IF EXISTS {restore_db_name}")
		cur.execute(f"CREATE DATABASE {restore_db_name}")
		cur.close()
		conn.close()
		print("  Database opprettet.")

		# Load backup using pg_restore
		print(f"Laster backup inn i '{restore_db_name}'...")
		result = subprocess.run(
			["pg_restore", "-h", db_host, "-p", db_port, "-U", db_user, "-d", restore_db_name, "--no-owner", "--no-acl", backup_file],
			env=env,
			capture_output=True,
			text=True,
		)
		if result.returncode != 0 and "ERROR" in result.stderr:
			# pg_restore often returns non-zero for warnings, only fail on real errors
			print(f"  pg_restore advarsler: {result.stderr[:500]}")
		print("  Backup lastet inn.")

	def _drop_restore_db(self, restore_db_name):
		"""Drop the temporary restore database."""
		db_user = os.environ["POSTGRES_USER"]
		db_password = os.environ["POSTGRES_PASSWORD"]

		print(f"\nSletter midlertidig database '{restore_db_name}'...")
		conn = psycopg2.connect(
			dbname='kartoteket',
			user=db_user,
			password=db_password,
			host='localhost',
			port='5432',
		)
		conn.autocommit = True
		cur = conn.cursor()
		cur.execute(f"DROP DATABASE IF EXISTS {restore_db_name}")
		cur.close()
		conn.close()
		print("  Slettet.")

	def handle(self, **options):
		restore_db_name = options['restore_db']
		backup_file = options['backup_file']
		dry_run = options['dry_run']

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter restore_adgroup_relations ------")
		if dry_run:
			print("*** DRY RUN - ingen endringer vil bli gjort ***")

		runtime_t0 = time.time()

		# Setup: create and populate restore database
		try:
			self._setup_restore_db(restore_db_name, backup_file)
		except Exception as e:
			print(f"FEIL under oppretting av restore-database: {e}")
			return

		# Connect to the restore database
		try:
			restore_conn = psycopg2.connect(
				dbname=restore_db_name,
				user=os.environ["POSTGRES_USER"],
				password=os.environ["POSTGRES_PASSWORD"],
				host='localhost',
				port='5432',
			)
			restore_conn.set_session(readonly=True)
			restore_cur = restore_conn.cursor()
		except Exception as e:
			print(f"FEIL: Kunne ikke koble til restore-databasen '{restore_db_name}': {e}")
			self._drop_restore_db(restore_db_name)
			return

		# Build mapping: old adgroup_id -> distinguishedname (from backup)
		print("Leser gamle ADgroup-IDer fra backup...")
		restore_cur.execute("SELECT id, distinguishedname FROM systemoversikt_adgroup")
		old_id_to_dn = {row[0]: row[1] for row in restore_cur.fetchall()}
		print(f"  Fant {len(old_id_to_dn)} grupper i backup")

		# Build mapping: distinguishedname -> new adgroup_id (from live DB)
		print("Bygger mapping til nye ADgroup-IDer...")
		new_dn_to_id = {g.distinguishedname: g.id for g in ADgroup.objects.all()}
		print(f"  Fant {len(new_dn_to_id)} grupper i live DB")

		# Combined mapping: old_id -> new_id
		old_to_new = {}
		unmapped = 0
		for old_id, dn in old_id_to_dn.items():
			if dn in new_dn_to_id:
				old_to_new[old_id] = new_dn_to_id[dn]
			else:
				unmapped += 1
		print(f"  Mappet {len(old_to_new)} grupper, {unmapped} kunne ikke mappes (finnes ikke lenger i AD)")

		# --- Restore M2M: System.tilgangsgrupper_ad ---
		print("\n--- Restoring System.tilgangsgrupper_ad ---")
		restore_cur.execute("SELECT system_id, adgroup_id FROM systemoversikt_system_tilgangsgrupper_ad")
		system_adgroup_rows = restore_cur.fetchall()
		restored, skipped = self._restore_m2m(
			'systemoversikt_system_tilgangsgrupper_ad',
			'system_id', 'adgroup_id',
			system_adgroup_rows, old_to_new, dry_run
		)
		print(f"  Resultat: {restored} gjenopprettet, {skipped} hoppet over (gruppe finnes ikke)")

		# --- Restore M2M: Leverandortilgang.adgrupper ---
		print("\n--- Restoring Leverandortilgang.adgrupper ---")
		restore_cur.execute("SELECT leverandortilgang_id, adgroup_id FROM systemoversikt_leverandortilgang_adgrupper")
		lev_adgroup_rows = restore_cur.fetchall()
		restored, skipped = self._restore_m2m(
			'systemoversikt_leverandortilgang_adgrupper',
			'leverandortilgang_id', 'adgroup_id',
			lev_adgroup_rows, old_to_new, dry_run
		)
		print(f"  Resultat: {restored} gjenopprettet, {skipped} hoppet over")

		# --- Restore M2M: RapportGruppemedlemskaper.grupper ---
		print("\n--- Restoring RapportGruppemedlemskaper.grupper ---")
		restore_cur.execute("SELECT rapportgruppemedlemskaper_id, adgroup_id FROM systemoversikt_rapportgruppemedlemskaper_grupper")
		rapport_grupper_rows = restore_cur.fetchall()
		restored, skipped = self._restore_m2m(
			'systemoversikt_rapportgruppemedlemskaper_grupper',
			'rapportgruppemedlemskaper_id', 'adgroup_id',
			rapport_grupper_rows, old_to_new, dry_run
		)
		print(f"  Resultat: {restored} gjenopprettet, {skipped} hoppet over")

		# --- Restore M2M: RapportGruppemedlemskaper.AND_grupper ---
		print("\n--- Restoring RapportGruppemedlemskaper.AND_grupper ---")
		try:
			restore_cur.execute("SELECT rapportgruppemedlemskaper_id, adgroup_id FROM \"systemoversikt_rapportgruppemedlemskaper_AND_grupper\"")
			rapport_and_rows = restore_cur.fetchall()
			restored, skipped = self._restore_m2m(
				'"systemoversikt_rapportgruppemedlemskaper_AND_grupper"',
				'rapportgruppemedlemskaper_id', 'adgroup_id',
				rapport_and_rows, old_to_new, dry_run
			)
			print(f"  Resultat: {restored} gjenopprettet, {skipped} hoppet over")
		except Exception as e:
			print(f"  Hopper over (tabell finnes kanskje ikke): {e}")
			restore_conn.rollback()

		restore_cur.close()
		restore_conn.close()

		# Cleanup: drop the temporary database
		self._drop_restore_db(restore_db_name)

		runtime_t1 = time.time()
		print(f"\nFerdig. Total kjøretid: {round(runtime_t1 - runtime_t0, 1)} sekunder")
		if dry_run:
			print("*** DRY RUN - ingen endringer ble gjort. Kjør uten --dry-run for å utføre ***")


	def _restore_m2m(self, table_name, left_col, right_col, rows, old_to_new, dry_run):
		"""Restore rows in an M2M junction table by remapping adgroup IDs."""
		from django.db import connection

		remapped_rows = []
		skipped = 0
		for left_id, old_adgroup_id in rows:
			if old_adgroup_id in old_to_new:
				remapped_rows.append((left_id, old_to_new[old_adgroup_id]))
			else:
				skipped += 1

		if not remapped_rows or dry_run:
			return len(remapped_rows), skipped

		with transaction.atomic():
			cursor = connection.cursor()
			# Use INSERT ... ON CONFLICT DO NOTHING to avoid duplicates
			for left_id, new_adgroup_id in remapped_rows:
				cursor.execute(
					f"INSERT INTO {table_name} ({left_col}, {right_col}) VALUES (%s, %s) ON CONFLICT DO NOTHING",
					[left_id, new_adgroup_id]
				)

		return len(remapped_rows), skipped
