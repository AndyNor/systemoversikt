# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
import ldap, os
from systemoversikt.views import ldap_query

class Command(BaseCommand):
	def handle(self, **options):
		
		#server = 'ldaps://ldaps.oslofelles.oslo.kommune.no:636'
		#user = os.environ["KARTOTEKET_LDAPUSER"]
		#password = os.environ["KARTOTEKET_LDAPPASSWORD"]

		#ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
		#ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
		#ldapClient = ldap.initialize(server)
		#ldapClient.set_option(ldap.OPT_REFERRALS, 0)
		#ldapClient.bind_s(user, password)


		def ldap_query(ldap_path, ldap_filter, ldap_properties, timeout): # støttefunksjon for LDAP
			import ldap, os
			server = 'ldaps://ldaps.oslofelles.oslo.kommune.no:636'
			user = os.environ["KARTOTEKET_LDAPUSER"]
			password = os.environ["KARTOTEKET_LDAPPASSWORD"]
			ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # have to deactivate sertificate check
			ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
			ldapClient = ldap.initialize(server)
			ldapClient.timeout = timeout
			ldapClient.set_option(ldap.OPT_REFERRALS, 0)  # tells the server not to chase referrals
			ldapClient.bind_s(user, password)  # synchronious

			result = ldapClient.search_s(
					ldap_path,
					ldap.SCOPE_SUBTREE,
					ldap_filter,
					ldap_properties
			)

			ldapClient.unbind_s()
			return result

		ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
		#ldap_filter = ('(&(objectCategory=person)(objectClass=user)(memberOf:1.2.840.113556.1.4.1941:=%s))' % group)
		ldap_filter = ('(distinguishedName=%s)' % "CN=S-BRE-MSCRM-ADMIN,OU=ServiceAccounts,OU=AD,OU=Administrasjon,DC=oslofelles,DC=oslo,DC=kommune,DC=no")
		ldap_properties = ['cn', 'displayName', 'description']


		result = ldap_query(ldap_path=ldap_path, ldap_filter=ldap_filter, ldap_properties=ldap_properties, timeout=10)

		print(result)


