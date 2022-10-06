# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å fikse tilknytning virksomhet for DRIFT-brukere
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import *
import ldap
import os


class Command(BaseCommand):
	def handle(self, **options):

		ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # have to deactivate sertificate check
		ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
		l = ldap.initialize(os.environ["KARTOTEKET_LDAPSERVER"])
		l.set_option(ldap.OPT_REFERRALS, 0)
		l.bind_s(os.environ["KARTOTEKET_LDAPUSER"], os.environ["KARTOTEKET_LDAPPASSWORD"])

		ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
		ldap_filter = '(&(objectCategory=Group)(cn=DS-SYE_APP_VIRK_GERICA))'
		ldap_properties = ['member;range=5000-5020']

		query_result = l.search_s(
				ldap_path,
				ldap.SCOPE_SUBTREE,
				ldap_filter,
				ldap_properties
			)
		print(query_result)
		#for key in query_result:
		#	virksomheter.append(key[1]["ou"][0].decode())
		l.unbind_s()

