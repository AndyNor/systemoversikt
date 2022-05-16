# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å oppdatere en lokal oversikt over alle AD-grupper, både for å kunne analysere medlemskap, f.eks. tomme grupper, kunne finne grupper som ikke stammer fra AD, kunne følge med på opprettelse av nye grupper.
"""

# TODO slette grupper som ikke ble funnet

from django.core.management.base import BaseCommand
from systemoversikt.models import ApplicationLog, ADOrgUnit, ADgroup, CMDBbs, System

class Command(BaseCommand):
	def handle(self, **options):


		for s in System.objects.all():
			if s.driftsmodell_foreignkey != None:
				if s.driftsmodell_foreignkey.pk == 9:
					s.driftsmodell_foreignkey.pk = 3
					print("endrer modell for %s" % (s))
					s.save()