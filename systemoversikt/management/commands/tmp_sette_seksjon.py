# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å fikse tilknytning virksomhet for DRIFT-brukere
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import System, Database

class Command(BaseCommand):
	def handle(self, **options):

		for s in System.objects.all():
			if s.systemforvalter_avdeling_referanse != None:
				continue # vi overskriver ikke

			aktuelle_seksjoner = []
			for ansvarlig in s.systemforvalter_kontaktpersoner_referanse.all():
				try:
					org_enhet = ansvarlig.brukernavn.profile.org_unit
					if org_enhet != None:
						aktuelle_seksjoner.append(org_enhet)
				except:
					pass

			if len(aktuelle_seksjoner) == 0:
				continue

			if len(aktuelle_seksjoner) == 1:
				s.systemforvalter_avdeling_referanse = aktuelle_seksjoner[0]
				print(f"Setter seksjon direkte for {s} til {aktuelle_seksjoner[0]}")
				s.save()
				continue

			# det var flere enn 1 seksjon, vi velger den mest frekvente
			import collections
			mest_frekvente_seksjon = collections.Counter(aktuelle_seksjoner).most_common(1)[0][0]
			s.systemforvalter_avdeling_referanse = mest_frekvente_seksjon
			print(f"Setter mest frekvente seksjon for {s} til {mest_frekvente_seksjon}")
			s.save()
