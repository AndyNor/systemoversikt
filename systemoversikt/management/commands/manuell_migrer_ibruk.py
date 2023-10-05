# -*- coding: utf-8 -*-

# Midlertidig kode for å endre ukjent driftsmodell None til valg 9 (som er "ukjent")

from django.core.management.base import BaseCommand
from systemoversikt.models import ApplicationLog, ADOrgUnit, ADgroup, CMDBbs, System, Driftsmodell

class Command(BaseCommand):
	def handle(self, **options):


		for s in System.objects.all():
			if s.driftsmodell_foreignkey != None:
				if s.driftsmodell_foreignkey.pk == 9:
					target = Driftsmodell.objects.get(pk=3)
					s.driftsmodell_foreignkey = target
					print("endrer modell for %s" % (s))
					s.save()