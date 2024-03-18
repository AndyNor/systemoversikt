# -*- coding: utf-8 -*-

# Midlertidig kode for å endre ukjent driftsmodell None til valg 9 (som er "ukjent")

from django.core.management.base import BaseCommand
from systemoversikt.models import *
from django.db import transaction

class Command(BaseCommand):
	def handle(self, **options):

		@transaction.atomic
		def execute_atomic():
			for s in System.objects.all():
				for system in s.datautveksling_mottar_fra.all():
					i, created = SystemIntegration.objects.get_or_create(
							source_system=system,
							destination_system=s,
							integration_type="INTEGRATION",
						)
					if created:
						print(f"{i}")
				for system in s.datautveksling_avleverer_til.all():
					i, created = SystemIntegration.objects.get_or_create(
							source_system=s,
							destination_system=system,
							integration_type="INTEGRATION",
						)
					if created:
						print(f"{i}")
				for system in s.avhengigheter_referanser.all():
					i, created = SystemIntegration.objects.get_or_create(
							source_system=s,
							destination_system=system,
							integration_type="COMPONENT",
						)
					if created:
						print(f"{i}")

		#SystemIntegration.objects.all().delete()
		execute_atomic()
		print("Ferdig")