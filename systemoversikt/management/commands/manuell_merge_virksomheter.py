# -*- coding: utf-8 -*-
# Flytte systemer og programvarer fra en virksomhet til en annen
# MÅ ALLTID VERIFISERES FØR DEN KJØRES!

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import *

class Command(BaseCommand):
	def handle(self, **options):

		gammel_virksomhet = Virksomhet.objects.get(pk=150) # KID
		ny_virksomhet = Virksomhet.objects.get(pk=174) # OBF


		for system in System.objects.filter(systemeier=gammel_virksomhet):
			print("Endrer systemeier for %s fra %s til %s" % (system.systemnavn, gammel_virksomhet, ny_virksomhet))
			system.systemeier = ny_virksomhet
			system.save()

		for system in System.objects.filter(systemforvalter=gammel_virksomhet):
			print("Endrer systemforvalter for %s fra %s til %s" % (system.systemnavn, gammel_virksomhet, ny_virksomhet))
			system.systemforvalter = ny_virksomhet
			system.save()


		for systembruk in SystemBruk.objects.filter(brukergruppe=gammel_virksomhet):
			try:
				print("Endrer systembruk for %s fra %s til %s" % (systembruk.system.systemnavn, gammel_virksomhet, ny_virksomhet))
				systembruk.brukergruppe = ny_virksomhet
				systembruk.save()
			except: # skjer dersom den allerede finnes. Det skjer alltid for fellesystemer.
				print("Overføring av systembruk feilet for %s" % systembruk.system.systemnavn)

			#skrive over kommentarer og andre relevante felt

		for programvarebruk in ProgramvareBruk.objects.filter(brukergruppe=gammel_virksomhet):
			try:
				print("Endrer programvarebruk for %s fra %s til %s" % (programvarebruk.programvare.programvarenavn, gammel_virksomhet, ny_virksomhet))
				programvarebruk.brukergruppe = ny_virksomhet
				programvarebruk.save()
			except: # skjer dersom den allerede finnes. Det skjer alltid for fellesystemer.
				print("Overføring av programvarebruk feilet for %s" % programvarebruk.programvare.programvarenavn)

			#skrive over kommentarer og andre relevante felt


		#for behandling in BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=gammel_virksomhet):
		#	print("Flytter behandlingen %s fra %s til %s" % (behandling.behandlingen, gammel_virksomhet, ny_virksomhet))
		#	behandling.behandlingsansvarlig = ny_virksomhet
		#	behandling.save()


		# samme for avtale

		# samme for plattformer

		# prøve å flytte over ansvarlige (dersom samme epostalias)



