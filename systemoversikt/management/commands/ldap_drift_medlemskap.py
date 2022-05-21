# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å oppdatere en lokal oversikt over alle AD-grupper, både for å kunne analysere medlemskap, f.eks. tomme grupper, kunne finne grupper som ikke stammer fra AD, kunne følge med på opprettelse av nye grupper.
"""

# TODO slette grupper som ikke ble funnet

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.models import *
from django.contrib.auth.models import User

class Command(BaseCommand):
	def handle(self, **options):

		from systemoversikt.views import ldap_users_securitygroups

		driftbrukere = User.objects.filter(username__istartswith="DRIFT").filter(profile__accountdisable=False)
		for bruker in driftbrukere:
			if bruker.profile.adgrupper_antall == None:
				print("slår opp %s" % (bruker))
				grupper = ldap_users_securitygroups(bruker.username)
				for g in grupper:
					try:
						adg = ADgroup.objects.get(distinguishedname=g)
						bruker.profile.adgrupper.add(adg)
						bruker.profile.adgrupper_antall = len(grupper)
						bruker.save()
					except:
						print("Error, fant ikke %s" % (g))


