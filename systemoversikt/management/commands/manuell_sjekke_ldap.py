
# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
import os

class Command(BaseCommand):
	def handle(self, **options):

		from ldap3 import Server, Connection, ALL, SUBTREE, NTLM
		from impacket.dcerpc.v5 import samr
		from impacket.dcerpc.v5.dtypes import RPC_SID
		import struct
		import os

		# --- CONFIG ---
		ldap_host = 'ldaps.oslofelles.oslo.kommune.no'
		username = os.environ["KARTOTEKET_LDAPUSER"]
		password = os.environ["KARTOTEKET_LDAPPASSWORD"]
		dn = 'CN=S-BRE-MSCRM-ADMIN,OU=ServiceAccounts,OU=AD,OU=Administrasjon'
		base_dn = 'DC=oslofelles,DC=oslo,DC=kommune,DC=no'

		# --- CONNECT ---
		server = Server(ldap_host, port=636, use_ssl=True, get_info=ALL)
		conn = Connection(server, user=username, password=password, authentication=NTLM)
		if not conn.bind():
			raise Exception("LDAP bind failed: " + str(conn.result))

		# --- Request DACL only ---
		SDFLAGS_OID = '1.2.840.113556.1.4.801'
		DACL_ONLY = (SDFLAGS_OID, True, b'\x04\x00\x00\x00')

		conn.search(dn, '(objectClass=*)', search_scope='BASE',
					attributes=['nTSecurityDescriptor'], controls=[DACL_ONLY])

		if not conn.entries:
			raise SystemExit("No entries returned. Check DN or permissions.")

		sd_data = conn.entries[0]['nTSecurityDescriptor'].raw_values[0]

		# --- Parse DACL manually ---
		# Security Descriptor header is 20 bytes: <BBHLLLL
		rev, sbz1, control, owner_ofs, group_ofs, sacl_ofs, dacl_ofs = struct.unpack('<BBHLLLL', sd_data[:20])
		if dacl_ofs == 0:
			print("No DACL present.")
			conn.unbind()
			exit()

		dacl = samr.DACL(sd_data[dacl_ofs:])

		# SID -> name helper
		def sid_to_name(sid_str):
			try:
				sid_obj = RPC_SID(); sid_obj.fromString(sid_str)
				sid_bytes = sid_obj.getData()
				esc = ''.join('\\{:02x}'.format(b) for b in sid_bytes)
				flt = f'(objectSid={esc})'
				if conn.search(base_dn, flt, SUBTREE, attributes=['sAMAccountName']):
					if conn.entries:
						return str(conn.entries[0]['sAMAccountName'].value)
			except:
				pass
			return sid_str

		RIGHTS_MAP = {
			0x10000000: 'GenericAll',
			0x40000000: 'GenericWrite',
			0x80000000: 'GenericRead',
			0x20000000: 'GenericExecute',
			0x00000008: 'WriteDacl',
			0x00000002: 'WriteOwner',
		}

		print(f"{'Identity':<35} {'RightsMask':<12} {'Rights':<40} {'ACEType':<10} {'Inherited'}")
		print('-' * 100)
		for ace in dacl.aces:
			mask = ace['Ace']['Mask']
			rights = [name for bit, name in RIGHTS_MAP.items() if mask & bit]
			identity = sid_to_name(str(ace['Ace']['Sid']))
			ace_type = ace['AceType']
			inherited = bool(ace['AceFlags'] & 0x10)
			print(f"{identity:<35} {hex(mask):<12} {','.join(rights):<40} {hex(ace_type):<10} {inherited}")

		conn.unbind()



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
