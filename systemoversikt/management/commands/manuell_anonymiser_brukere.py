# -*- coding: utf-8 -*-
# Change log:
# 2026-07-02: One-off script – anonymize remaining AD user PII without LDAP access.
"""
Engangsscript: anonymiser bruker-PII i databasen (samme felt som ldap_users_paged_v2),
uten LDAP-tilgang. Bruker 12-tegns SHA-256-hex (kortere enn LDAP-importens 24).

Bruk (krever THIS_ENV=TEST):
  python manage.py manuell_anonymiser_brukere --dry-run
  python manage.py manuell_anonymiser_brukere
"""
import hashlib
import os
import re
from collections import Counter
from datetime import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from systemoversikt.models import Profile

_HASH_LEN = 12
_HEX12 = re.compile(r'^[0-9a-f]{12}$')
_HEX24 = re.compile(r'^[0-9a-f]{24}$')


def _anonymize_text(value):
	if value is None or not value:
		return value
	if _HEX12.match(value):
		return value
	if _HEX24.match(value):
		return value[0:_HASH_LEN]
	return hashlib.sha256(value.encode('utf-8')).hexdigest()[0:_HASH_LEN]


def _anonymize_email(email):
	if not email or '@' not in email:
		return email
	local, domain = email.split('@', 1)
	if _HEX12.match(local):
		return email
	if _HEX24.match(local):
		return f"{local[0:_HASH_LEN]}@{domain}"
	local_hash = hashlib.sha256(local.encode('utf-8')).hexdigest()[0:_HASH_LEN]
	return f"{local_hash}@{domain}"


class Command(BaseCommand):
	help = (
		"Anonymiser bruker-PII (fornavn, etternavn, e-post, beskrivelse, visningsnavn) "
		"med 12-tegns SHA-256-hex. Krever THIS_ENV=TEST."
	)

	def add_arguments(self, parser):
		parser.add_argument(
			"--dry-run",
			action="store_true",
			help="Vis planlagte endringer uten å lagre",
		)
		parser.add_argument(
			"--log-file",
			default=None,
			help="Sti til loggfil (standard: anonymiser_brukere_<tidsstempel>.log i cwd)",
		)

	def handle(self, *args, **options):
		if os.environ.get('THIS_ENV') != 'TEST':
			self.stderr.write(
				self.style.ERROR(
					"Avbrutt: kommandoen kan bare kjøres når THIS_ENV=TEST."
				)
			)
			return

		dry_run = options["dry_run"]
		log_path = options["log_file"] or self._default_log_path()
		log_lines = []
		field_changes = Counter()

		def log(line=""):
			self.stdout.write(line)
			log_lines.append(line)

		log(f"=== manuell_anonymiser_brukere {datetime.now().isoformat(timespec='seconds')} ===")
		log(f"Modus: {'DRY RUN (ingen endringer lagres)' if dry_run else 'LIVE (endringer lagres)'}")
		log(f"Loggfil: {log_path}")
		log(f"Hash-lengde: {_HASH_LEN} tegn\n")

		users = list(User.objects.select_related('profile').all())
		users_to_update = []
		profiles_to_update = []
		users_changed = 0

		with transaction.atomic():
			for user in users:
				user_changed = False
				profile = user.profile

				new_first_name = _anonymize_text(user.first_name)
				if new_first_name != user.first_name:
					field_changes['first_name'] += 1
					user.first_name = new_first_name
					user_changed = True

				new_last_name = _anonymize_text(user.last_name)
				if new_last_name != user.last_name:
					field_changes['last_name'] += 1
					user.last_name = new_last_name
					user_changed = True

				new_email = _anonymize_email(user.email)
				if new_email != user.email:
					field_changes['email'] += 1
					user.email = new_email
					user_changed = True

				new_description = _anonymize_text(profile.description)
				if new_description != profile.description:
					field_changes['description'] += 1
					profile.description = new_description
					user_changed = True

				new_display_name = _anonymize_text(profile.displayName)
				if new_display_name != profile.displayName:
					field_changes['displayName'] += 1
					profile.displayName = new_display_name
					user_changed = True

				if user_changed:
					users_changed += 1
					users_to_update.append(user)
					profiles_to_update.append(profile)

			if users_to_update and not dry_run:
				User.objects.bulk_update(users_to_update, ['first_name', 'last_name', 'email'])
				Profile.objects.bulk_update(profiles_to_update, ['description', 'displayName'])

			if dry_run:
				transaction.set_rollback(True)

		log("--- Oppsummering ---")
		log(f"Brukere skannet:  {len(users)}")
		log(f"Brukere endret:   {users_changed}")
		for field_name in ('first_name', 'last_name', 'email', 'description', 'displayName'):
			log(f"  {field_name}: {field_changes[field_name]} feltendringer")
		if dry_run:
			log("\n*** DRY RUN – ingen endringer ble lagret. Kjør uten --dry-run for å utføre. ***")

		self._write_log_file(log_path, log_lines)
		log(f"\nLogg skrevet til {log_path}")

	def _default_log_path(self):
		stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		return f"anonymiser_brukere_{stamp}.log"

	def _write_log_file(self, log_path, log_lines):
		with open(log_path, "w", encoding="utf-8") as log_file:
			log_file.write("\n".join(log_lines))
			log_file.write("\n")
