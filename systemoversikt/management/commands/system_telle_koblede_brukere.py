# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å fikse tilknytning virksomhet for DRIFT-brukere
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import *
from django.db.models import Q
from django.db import transaction

class Command(BaseCommand):
	def handle(self, **options):

		@transaction.atomic
		def opptelling():
			idx = 1
			for profile in Profile.objects.all():
				if idx % 1000 == 0:
					print("%s" % idx)
				idx += 1
				if profile.ansattnr_ref != None:
					antall = len(profile.ansattnr_ref.userprofile.all())
					if profile.ansattnr_antall != antall:
						profile.ansattnr_antall = antall
						profile.save()

		opptelling()

