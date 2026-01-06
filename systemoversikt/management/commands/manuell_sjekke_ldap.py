# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
import ldap, os
from systemoversikt.views import ldap_query

class Command(BaseCommand):
	def handle(self, **options):

		def ldap_query_with_sd(ldap_path, ldap_filter, ldap_properties, timeout, sdflags=0x07):
			import ldap, os
			from ldap.controls import LDAPControl
			import struct

			server = 'ldaps://ldaps.oslofelles.oslo.kommune.no:636'
			user = os.environ["KARTOTEKET_LDAPUSER"]         # e.g., 'user@domain' or full DN
			password = os.environ["KARTOTEKET_LDAPPASSWORD"]

			# TLS settings (note: disabling cert check has security implications)
			ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
			ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)

			ldap_client = ldap.initialize(server)
			ldap_client.timeout = timeout
			ldap_client.set_option(ldap.OPT_REFERRALS, 0)
			ldap_client.bind_s(user, password)

			# SD Flags control value must be BER-encoded unsigned int; python-ldap accepts raw 4-byte little-endian
			# Equivalent to the Microsoft SD Flags control (OID 1.2.840.113556.1.4.801)
			sd_flags_oid = '1.2.840.113556.1.4.801'
			control_value = struct.pack('<I', sdflags)
			sd_control = LDAPControl(sd_flags_oid, True, control_value)

			# Use search_ext_s to send server controls
			result = ldap_client.search_ext_s(
			    ldap_path,
			    ldap.SCOPE_SUBTREE,
			    ldap_filter,
			    ldap_properties,
			    serverctrls=[sd_control]
			)

			ldap_client.unbind_s()
			return result

		ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
		ldap_filter = ('(distinguishedName=%s)' %
		               "CN=user,OU=ServiceAccounts,OU=AD,OU=Administrasjon,DC=oslofelles,DC=oslo,DC=kommune,DC=no")
		ldap_properties = ['cn', 'mail', 'givenName', 'displayName', 'sn', 'userAccountControl', 'nTSecurityDescriptor']

		result = ldap_query_with_sd(ldap_path, ldap_filter, ldap_properties, timeout=10, sdflags=0x07)

		for dn, attrs in result:
		    if dn:
		        for key, value in attrs.items():
		            if key == 'nTSecurityDescriptor':
		                # AD returns raw bytes in a single-element list
		                raw_sd = value[0]
		                print(f'{key}: {len(raw_sd)} bytes')
		            else:
		                print(f'{key}: {value}\n')



