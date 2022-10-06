# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å fikse tilknytning virksomhet for DRIFT-brukere
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import *
import ldap


class Command(BaseCommand):
	def handle(self, **options):

		l = ldap.initialize(os.environ["KARTOTEKET_LDAPSERVER"])
		l.bind_s(os.environ["KARTOTEKET_LDAPUSER"], os.environ["KARTOTEKET_LDAPPASSWORD"])

		ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
		ldap_filter = ('(&(objectCategory=Group)(cn=DS-SYE_APP_VIRK_GERICA))')
		ldap_properties = ['cn', 'displayName', 'description']

		query_result = l.search_s(
				ldap_path,
				ldap.SCOPE_BASE,
				ldap_filter,
				ldap_properties
			)
		print(query_result)
		#for key in query_result:
		#	virksomheter.append(key[1]["ou"][0].decode())
		l.unbind_s()

