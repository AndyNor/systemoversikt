# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
import ldap, os
from systemoversikt.views import ldap_query

class Command(BaseCommand):
	def handle(self, **options):


		import ssl
		from ldap3 import Server, Connection, ALL, SUBTREE
		from ldap3.core.tls import TLS
		from impacket.dcerpc.v5 import samr
		from impacket.dcerpc.v5.dtypes import RPC_SID

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
		SDFLAGS_OID = '1.2.840.113556.1.4.801'
		DACL_ONLY   = (SDFLAGS_OID, True, b'\x04\x00\x00\x00')

		conn.search(
			search_base=dn,
			search_filter='(objectClass=*)',
			search_scope='BASE',
			attributes=['nTSecurityDescriptor'],
			controls=[DACL_ONLY]
		)

		if not conn.entries:
			raise SystemExit("No entries returned. Check DN, permissions, or controls.")

		sd_attr = conn.entries[0]['nTSecurityDescriptor']
		if not sd_attr or not sd_attr.raw_values:
			raise SystemExit("Entry returned but nTSecurityDescriptor missing. Check SDFlags or rights.")

		sd_data = sd_attr.raw_values[0]

		# Parse DACL
		dacl = samr.DACL(sd_data)

		# Helper: SID -> sAMAccountName (or CN) via LDAP search on objectSid
		def sid_to_name(conn: Connection, base_dn: str, sid_str: str) -> str:
			try:
				sid_obj = RPC_SID(); sid_obj.fromString(sid_str)
				sid_bytes = sid_obj.getData()  # raw SID bytes for filter equality

				# AD supports binary match on objectSid via '=' with raw bytes in ldap3 filter_extensible
				# Simpler approach: use an equality filter with escaped bytes
				# ldap3 can accept filters using escaped hex; build it:
				esc = ''.join('\\{:02x}'.format(b) for b in sid_bytes)
				flt = f'(objectSid={esc})'

				if conn.search(base_dn, flt, SUBTREE, attributes=['sAMAccountName', 'cn', 'distinguishedName']):
					if conn.entries:
						e = conn.entries[0]
						if 'sAMAccountName' in e and e['sAMAccountName'].value:
							return str(e['sAMAccountName'].value)
						if 'cn' in e and e['cn'].value:
							return str(e['cn'].value)
						if 'distinguishedName' in e and e['distinguishedName'].value:
							return str(e['distinguishedName'].value)
			except Exception:
				pass
			return sid_str  # fallback to SID string

		# Basic rights decode (add more as needed)
		RIGHTS_MAP = {
			0x10000000: 'GenericAll',
			0x40000000: 'GenericWrite',
			0x80000000: 'GenericRead',
			0x20000000: 'GenericExecute',
			0x00000008: 'WriteDacl',
			0x00000002: 'WriteOwner',
		}

		# Print header
		print(f"Permissions on object: {TARGET_DN}")
		print("-" * 100)
		print(f"{'Identity':<35} {'RightsMask(hex)':<14} {'Rights(decoded)':<35} {'ACEType':<8} {'Inherited':<9} {'ObjectType'}")
		print("-" * 100)

		for ace in dacl.aces:
			# Type 0x00 = ACCESS_ALLOWED_ACE, 0x01 = ACCESS_DENIED_ACE, 0x05/0x06 = object-specific allowed/denied, etc.
			ace_type   = ace['AceType']
			ace_flags  = ace['AceFlags']
			inherited  = bool(ace_flags & 0x10)  # INHERITED_ACE
			mask       = ace['Ace']['Mask']
			sid_str    = str(ace['Ace']['Sid'])
			identity   = sid_to_name(conn, BASE_DN, sid_str)

			# ObjectType GUID (for property/extended-right-specific ACEs)
			obj_type_guid = ''
			try:
				# Not all ACEs have ObjectType; object-specific ACEs do
				if 'ObjectType' in ace['Ace'] and ace['Ace']['ObjectType'] is not None:
					obj_type_guid = str(ace['Ace']['ObjectType'])
			except Exception:
				obj_type_guid = ''

			rights_decoded = [name for bit, name in RIGHTS_MAP.items() if (mask & bit) == bit]
			print(f"{identity:<35} {hex(mask):<14} {','.join(rights_decoded):<35} {hex(ace_type):<8} {str(inherited):<9} {obj_type_guid}")

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
