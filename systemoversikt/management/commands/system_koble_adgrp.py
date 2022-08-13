# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å fikse tilknytning virksomhet for DRIFT-brukere
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import *
from django.db.models import Q

class Command(BaseCommand):
	def handle(self, **options):

		for s in System.objects.filter(ibruk=True).all():
			if hasattr(s, "bs_system_referanse"):
				if s.bs_system_referanse != None:
					lookup_words = []
					if len(s.systemnavn.split("(")[0].strip()) > 3:
						lookup_words.append(s.systemnavn.split("(")[0].strip())
					if s.alias != None:
						for a in s.alias.split():
							if len(a.split("(")[0].strip()) > 3:
								lookup_words.append(a.split("(")[0].strip())
					print(lookup_words)
					for word in lookup_words:
						adgrp = ADgroup.objects.filter(Q(common_name__icontains=word) | Q(display_name__icontains=word))
						for grp in adgrp:
							# Aktive PRK-valg
							if len(grp.prkvalg.all()) > 0:
								for prkvalg in grp.prkvalg.all():
									print("   PRK:%s: %s - %s" % (grp.common_name, prkvalg.skjemanavn, prkvalg))
									if s not in prkvalg.systemer.all():
										prkvalg.systemer.add(s)
										prkvalg.save()
							print("   ADgruppe:%s (%s)" % (grp.common_name, grp.display_name))
							if s not in grp.systemer.all():
								grp.systemer.add(s)
								grp.save()
					print("------")