# -*- coding: utf-8 -*-
# 2026-06-22: Migrate er_egenutviklet from legacy Driftsmodell.utviklingsplattform flag.

from django.core.management.base import BaseCommand

from systemoversikt.models import Driftsmodell, System


class Command(BaseCommand):
	help = (
		"Set System.er_egenutviklet=True for all systems on a Driftsmodell "
		"marked utviklingsplattform=True (legacy data migration)."
	)

	def handle(self, *args, **options):
		plattformer = Driftsmodell.objects.filter(utviklingsplattform=True).order_by('navn')
		plattform_count = plattformer.count()
		self.stdout.write(f"Driftsmodeller with utviklingsplattform=True: {plattform_count}")
		for plattform in plattformer:
			self.stdout.write(f"  - [{plattform.pk}] {plattform}")

		systems = (
			System.objects.filter(driftsmodell_foreignkey__utviklingsplattform=True)
			.select_related('driftsmodell_foreignkey')
			.order_by('systemnavn')
		)
		total = systems.count()
		self.stdout.write(f"\nSystems linked to those platforms: {total}")

		updated = 0
		skipped = 0
		for system in systems:
			plattform = system.driftsmodell_foreignkey
			if system.er_egenutviklet:
				skipped += 1
				self.stdout.write(
					f"SKIP [{system.pk}] {system} "
					f"(already er_egenutviklet, plattform: {plattform})"
				)
				continue
			system.er_egenutviklet = True
			system.save(update_fields=['er_egenutviklet'])
			updated += 1
			self.stdout.write(
				f"SET  [{system.pk}] {system} "
				f"-> er_egenutviklet=True (plattform: {plattform})"
			)

		self.stdout.write(
			f"\nDone. Updated {updated}, skipped {skipped} (already set), total matched {total}."
		)
