# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
import ldap, os
from systemoversikt.views import ldap_query

class Command(BaseCommand):
	def handle(self, **options):

		BRUKER = "CN=DRIFT429712,OU=DRIFT,OU=Servicekontoer,OU=OK,DC=oslofelles,DC=oslo,DC=kommune,DC=no"
		#BRUKER = "CN=DRIFT429712,OU=ServiceAccounts,OU=AD,OU=Administrasjon,DC=oslofelles,DC=oslo,DC=kommune,DC=no"

		def ldap_query_with_sd(ldap_path, ldap_filter, ldap_properties, timeout, sdflags=0x07):
			import ldap, os
			from ldap.controls import LDAPControl
			from pyasn1.type.univ import Integer
			from pyasn1.codec.ber import encoder  # <- BER-encode ASN.1 INTEGER

			server = 'ldaps://ldaps.oslofelles.oslo.kommune.no:636'
			user = os.environ["KARTOTEKET_LDAPUSER"]
			password = os.environ["KARTOTEKET_LDAPPASSWORD"]

			ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
			ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)

			ldap_client = ldap.initialize(server)
			ldap_client.timeout = timeout
			ldap_client.set_option(ldap.OPT_REFERRALS, 0)
			ldap_client.bind_s(user, password)

			sd_flags_oid = '1.2.840.113556.1.4.801'
			# BER-encode the integer value per ASN.1
			control_value = encoder.encode(Integer(sdflags))
			# criticality can be False; True is also fine
			sd_control = LDAPControl(sd_flags_oid, False, control_value)

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
		ldap_filter = ('(distinguishedName=%s)' % BRUKER)
		ldap_properties = ['cn', 'mail', 'givenName', 'displayName', 'sn',
				'userAccountControl', 'nTSecurityDescriptor']

		result = ldap_query_with_sd(ldap_path, ldap_filter, ldap_properties, timeout=10, sdflags=0x07)


		for dn, attrs in result:
			if not dn:
				continue
			has_sd = 'nTSecurityDescriptor' in attrs and attrs['nTSecurityDescriptor']
			print("DN:", dn)
			print("Has nTSecurityDescriptor:", bool(has_sd))
				if has_sd:
			print("SD bytes:", len(attrs['nTSecurityDescriptor'][0]))
