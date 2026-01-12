# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
import ldap, os
from systemoversikt.views import ldap_query

class Command(BaseCommand):
	def handle(self, **options):


		from ldap3 import Server, Connection, ALL, NTLM
		from impacket.dcerpc.v5.dtypes import RPC_SID
		from impacket.dcerpc.v5 import samr
		import struct

		# --- CONFIG ---
		ldap_server = 'ldaps://ldaps.oslofelles.oslo.kommune.no:636'
		username = os.environ["KARTOTEKET_LDAPUSER"]
		password = os.environ["KARTOTEKET_LDAPPASSWORD"]

		dn = 'CN=S-BRE-MSCRM-ADMIN,OU=ServiceAccounts,OU=AD,OU=Administrasjon,DC=oslofelles,DC=oslo,DC=kommune,DC=no'  # Target object's DN

		# --- CONNECT TO LDAP ---
		server = Server(ldap_server, get_info=ALL)
		conn = Connection(server, user=username, password=password, authentication=NTLM)
		if not conn.bind():
		    raise Exception("LDAP bind failed: " + str(conn.result))

		# --- FETCH SECURITY DESCRIPTOR ---
		conn.search(dn, '(objectClass=*)', attributes=['nTSecurityDescriptor'])
		sd_data = conn.entries[0]['nTSecurityDescriptor'].raw_values[0]

		# --- PARSE SECURITY DESCRIPTOR ---
		# The binary SD contains Owner, Group, DACL, SACL
		# We'll parse the DACL using Impacket's samr.DACL
		dacl = samr.DACL(sd_data)

		print(f"Permissions on object: {dn}")
		print("-" * 80)
		print(f"{'SID':<50} {'Rights':<20} {'Type':<10} {'Inherited'}")
		print("-" * 80)

		for ace in dacl.aces:
		    sid = str(ace['Ace']['Sid'])
		    mask = ace['Ace']['Mask']
		    ace_type = ace['AceType']
		    inherited = ace['AceFlags'] & 0x10 != 0  # INHERITED_ACE flag

		    # Decode rights (basic mapping)
		    rights_map = {
		        0x10000000: 'GenericAll',
		        0x40000000: 'GenericWrite',
		        0x80000000: 'GenericRead',
		        0x20000000: 'GenericExecute',
		        0x00000008: 'WriteDACL',
		        0x00000002: 'WriteOwner'
		    }
		    rights = [name for bit, name in rights_map.items() if mask & bit]

		    print(f"{sid:<50} {','.join(rights):<20} {ace_type:<10} {inherited}")


		"""
		BRUKERE = [
			"CN=DRIFT429712,OU=ServiceAccounts,OU=AD,OU=Administrasjon,DC=oslofelles,DC=oslo,DC=kommune,DC=no",
			"CN=DRIFT429712,OU=DRIFT,OU=Servicekontoer,OU=OK,DC=oslofelles,DC=oslo,DC=kommune,DC=no"
		]

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


		for bruker in BRUKERE:

			ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
			ldap_filter = ('(distinguishedName=%s)' % bruker)
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
		"""
