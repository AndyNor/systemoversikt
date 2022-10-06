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


		def ldap_query_members(common_name, start, stop):
			ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # have to deactivate sertificate check
			ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
			l = ldap.initialize(os.environ["KARTOTEKET_LDAPSERVER"])
			l.set_option(ldap.OPT_REFERRALS, 0)
			l.bind_s(os.environ["KARTOTEKET_LDAPUSER"], os.environ["KARTOTEKET_LDAPPASSWORD"])

			ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
			ldap_filter = '(&(objectCategory=Group)(cn=%s))' % common_name
			ldap_properties = 'member;range=%s-%s' % (start, stop)

			#attrs["member"]

			query_result = l.search_s(
					ldap_path,
					ldap.SCOPE_SUBTREE,
					ldap_filter,
					[ldap_properties]
				)

			l.unbind_s()

			for cn, attrs in query_result:
				if common_name in cn:
					return attrs
				else:
					return None


		def all_members(common_name):
			all_members = []
			start = 0
			stop = '10000'
			next_members = ldap_query_members(common_name, start, stop)
			for key in next_members:
				if 'member;range' in key:
					print(len(next_members[key]))
					for m in next_members[key]:
						all_members.append(m.decode())
			return all_members



		all_members = all_members("DS-SYE_APP_VIRK_GERICA")
		print(len(all_members))

