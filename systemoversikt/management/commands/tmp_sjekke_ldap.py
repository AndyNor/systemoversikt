# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å oppdatere en lokal oversikt over alle AD-grupper, både for å kunne analysere medlemskap, f.eks. tomme grupper, kunne finne grupper som ikke stammer fra AD, kunne følge med på opprettelse av nye grupper.
"""

# TODO slette grupper som ikke ble funnet

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
import ldap, os

class Command(BaseCommand):
	def handle(self, **options):
		
		server = 'ldaps://ldaps.oslofelles.oslo.kommune.no:636'
		user = os.environ["KARTOTEKET_LDAPUSER"]
		password = os.environ["KARTOTEKET_LDAPPASSWORD"]

		ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
		ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
		ldapClient = ldap.initialize(server)
		ldapClient.set_option(ldap.OPT_REFERRALS, 0)
		ldapClient.bind_s(user, password)
