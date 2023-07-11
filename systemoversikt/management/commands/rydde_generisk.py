# -*- coding: utf-8 -*-

"""
Hensikten med denne koden å
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from systemoversikt.models import *
from django.core.exceptions import ObjectDoesNotExist

class Command(BaseCommand):
	def handle(self, **options):
		"""
		Her sjekker vi først klassen "ansvarlige" for alle felter og avhengig av relasjonstype identifiserer vi om det er aktive relasjoner til dem. Normalt benyttes mangetilmange-relasjoner mot ansvarlige, men det er noen få unntak med OneToOneFields.
		"""
		LOG_EVENT_TYPE = 'Rydde generisk'
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

		teller_uten_eier = 0
		teller_rettet = 0
		for system in System.objects.all():

			# fikse manglende tilgjengelighetsvurdering
			if system.tilgjengelighetsvurdering == None:
				system.tilgjengelighetsvurdering = 6
				system.save()
				print(f"Endret tilgjengelighetsvurdering til ukjent for {system}.")


			# fikse manglende systemforvalter ved å sette systemeier dersom det eksisterer
			if system.systemforvalter:
				continue

			if system.systemeier:
				system.systemforvalter = system.systemeier
				system.save()
				teller_rettet += 1

			print(f"{system} har hverken forvalter eller eier")
			teller_uten_eier += 1



		logg_entry_message = f"Rettet {teller_rettet} systemer uten forvalter organisasjon satt. Fant også {teller_uten_eier} systemer uten eier."
		print(logg_entry_message)
		logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)
