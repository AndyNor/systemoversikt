# -*- coding: utf-8 -*-
# Change log:
# 2026-06-22: One-off script – set systemeier to systemforvalter when owner is INE/Origo/UKE.
"""
Engangsscript: finn systemer der organisatorisk systemeier er INE, Origo (OOO) eller UKE,
og sett systemeier til samme virksomhet som systemforvalter.

Bruk:
  python manage.py manuell_systemeier_til_forvalter --dry-run
  python manage.py manuell_systemeier_til_forvalter
"""
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from systemoversikt.models import System, Virksomhet

# Origo er registrert med forkortelse OOO i kartoteket.
SOURCE_OWNER_ABBREVIATIONS = ("INE", "OOO", "UKE")


class Command(BaseCommand):
	help = (
		"Sett organisatorisk systemeier til systemforvalter for systemer "
		"der systemeier er INE, Origo (OOO) eller UKE."
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
			help="Sti til loggfil (standard: systemeier_til_forvalter_<tidsstempel>.log i cwd)",
		)

	def handle(self, *args, **options):
		dry_run = options["dry_run"]
		log_path = options["log_file"] or self._default_log_path()
		log_lines = []

		def log(line=""):
			self.stdout.write(line)
			log_lines.append(line)

		source_virksomheter = list(
			Virksomhet.objects.filter(virksomhetsforkortelse__in=SOURCE_OWNER_ABBREVIATIONS)
		)
		found_abbreviations = {v.virksomhetsforkortelse for v in source_virksomheter}
		missing_abbreviations = set(SOURCE_OWNER_ABBREVIATIONS) - found_abbreviations

		log(f"=== manuell_systemeier_til_forvalter {datetime.now().isoformat(timespec='seconds')} ===")
		log(f"Modus: {'DRY RUN (ingen endringer lagres)' if dry_run else 'LIVE (endringer lagres)'}")
		log(f"Loggfil: {log_path}")
		log(f"Søker etter systemeier med forkortelse: {', '.join(SOURCE_OWNER_ABBREVIATIONS)}")
		if source_virksomheter:
			log(
				"Fant virksomheter: "
				+ ", ".join(f"{v.virksomhetsnavn} ({v.virksomhetsforkortelse}, pk={v.pk})" for v in source_virksomheter)
			)
		else:
			log("Fant ingen virksomheter med angitte forkortelser – avslutter.")
			self._write_log_file(log_path, log_lines)
			return

		if missing_abbreviations:
			log(
				"Advarsel: fant ikke virksomhet for forkortelse(r): "
				+ ", ".join(sorted(missing_abbreviations))
			)

		systems = (
			System.objects.filter(systemeier__in=source_virksomheter)
			.select_related("systemeier", "systemforvalter")
			.order_by("systemnavn")
		)

		changed = 0
		skipped_same = 0
		warnings = 0

		log(f"\nFant {systems.count()} system(er) med systemeier INE/Origo/UKE.\n")

		with transaction.atomic():
			for system in systems:
				old_eier = system.systemeier
				new_eier = system.systemforvalter

				if old_eier == new_eier:
					skipped_same += 1
					log(
						f"SKIP pk={system.pk} {system.systemnavn}: "
						f"systemeier er allerede lik systemforvalter ({new_eier})"
					)
					continue

				if new_eier.virksomhetsforkortelse in SOURCE_OWNER_ABBREVIATIONS:
					warnings += 1
					log(
						f"ADVARSEL pk={system.pk} {system.systemnavn}: "
						f"systemforvalter er også {new_eier.virksomhetsforkortelse} "
						f"({new_eier}) – endringen vil ikke flytte eierskap bort fra kilden"
					)

				log(
					f"ENDRE pk={system.pk} {system.systemnavn}: "
					f"systemeier {old_eier.virksomhetsforkortelse} ({old_eier.pk}) "
					f"-> {new_eier.virksomhetsforkortelse} ({new_eier.pk}) "
					f"[forvalter: {new_eier}]"
				)

				if not dry_run:
					system.systemeier = new_eier
					system.save(update_fields=["systemeier", "sist_oppdatert"])
				changed += 1

			if dry_run:
				transaction.set_rollback(True)

		log("\n--- Oppsummering ---")
		log(f"Treff totalt:     {systems.count()}")
		log(f"Endret/planlagt:  {changed}")
		log(f"Hoppet over:      {skipped_same} (systemeier = systemforvalter)")
		log(f"Advarsler:        {warnings}")
		if dry_run:
			log("\n*** DRY RUN – ingen endringer ble lagret. Kjør uten --dry-run for å utføre. ***")

		self._write_log_file(log_path, log_lines)
		log(f"\nLogg skrevet til {log_path}")

	def _default_log_path(self):
		stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		return f"systemeier_til_forvalter_{stamp}.log"

	def _write_log_file(self, log_path, log_lines):
		with open(log_path, "w", encoding="utf-8") as log_file:
			log_file.write("\n".join(log_lines))
			log_file.write("\n")
