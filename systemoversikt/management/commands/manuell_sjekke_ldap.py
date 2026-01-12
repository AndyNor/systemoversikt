
# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
import os

class Command(BaseCommand):
	def handle(self, **options):

		import ldap
		from ldap.controls import LDAPControl
		from pyasn1.type.univ import Integer
		from pyasn1.codec.ber import encoder

		server = 'ldaps://ldaps.oslofelles.oslo.kommune.no:636'
		user = os.environ["KARTOTEKET_LDAPUSER"]
		password = os.environ["KARTOTEKET_LDAPPASSWORD"]

		ldap_client = ldap.initialize(server)
		ldap_client.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
		ldap_client.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
		ldap_client.set_option(ldap.OPT_REFERRALS, 0)
		ldap_client.simple_bind_s(user, password)

		dn = "CN=S-BRE-MSCRM-ADMIN,OU=ServiceAccounts,OU=AD,OU=Administrasjon,DC=oslofelles,DC=oslo,DC=kommune,DC=no"

		# SDFlags control: ASN.1 encoded integer
		sdflags = 0x04  # DACL only
		control_value = encoder.encode(Integer(sdflags))
		sd_control = LDAPControl('1.2.840.113556.1.4.801', True, control_value)

		result = ldap_client.search_ext_s(
			dn,
			ldap.SCOPE_BASE,
			'(objectClass=*)',
			['nTSecurityDescriptor'],
			serverctrls=[sd_control]
		)

		print(result)
		ldap_client.unbind_s()
