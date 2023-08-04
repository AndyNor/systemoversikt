# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å fikse tilknytning virksomhet for DRIFT-brukere
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import *

class Command(BaseCommand):
	def handle(self, **options):

		tom_virksomhet = Virksomhet.objects.get(virksomhetsnavn='Ukjent virksomhet')

		for s in System.objects.all():
			if s.systemforvalter == None:
				print(s)
				s.systemforvalter = tom_virksomhet
				s.save()
				print(f'Endret forvalter fra None til ukjent virksomhet for {s}')
