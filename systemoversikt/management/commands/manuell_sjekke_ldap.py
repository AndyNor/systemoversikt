
# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
import os

class Command(BaseCommand):
	def handle(self, **options):
		import ssl
		from ldap3 import Server, Connection, ALL, SUBTREE, NTLM
		#from ldap3.core.tls import TLS
		from impacket.nt_security import SECURITY_DESCRIPTOR
		from impacket.dcerpc.v5.dtypes import RPC_SID

		# --- CONFIG ---
		LDAP_HOST = 'ldaps.oslofelles.oslo.kommune.no'  # FQDN only (no scheme)
		LDAP_PORT = 636
		USERNAME = os.environ["KARTOTEKET_LDAPUSER"]     # 'DOMAIN\\user' or 'user@domain'
		PASSWORD = os.environ["KARTOTEKET_LDAPPASSWORD"]
		TARGET_DN = 'CN=S-BRE-MSCRM-ADMIN,OU=ServiceAccounts,OU=AD,OU=Administrasjon,DC=oslofelles,DC=oslo,DC=kommune,DC=no'
		BASE_DN   = 'DC=oslofelles,DC=oslo,DC=kommune,DC=no'  # used for SID->name lookups

		# --- LDAP / TLS ---
		# No CA available now -> disable validation temporarily. Re-enable when you can.
		#tls = TLS(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
		server = Server(LDAP_HOST, port=LDAP_PORT, use_ssl=True, get_info=ALL)

		conn = Connection(server, user=USERNAME, password=PASSWORD, authentication=NTLM, auto_bind=True)

		# --- Request DACL only via SDFlags control ---
		SDFLAGS_OID = '1.2.840.113556.1.4.801'
		DACL_ONLY   = (SDFLAGS_OID, True, b'\x04\x00\x00\x00')  # 0x04 = DACL

		conn.search(
			search_base=TARGET_DN,
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

		# --- Parse full Security Descriptor and extract DACL ---
		sd = SECURITY_DESCRIPTOR(sd_data)
		dacl = sd['Dacl']
		if dacl is None:
			print('No DACL present on this object.')
			conn.unbind()
			return

		# Map some well-known SIDs that won't resolve via LDAP search
		WELL_KNOWN = {
			'S-1-1-0':  'Everyone',
			'S-1-5-10': 'SELF',
			'S-1-5-11': 'Authenticated Users',
			'S-1-5-18': 'LOCAL SYSTEM',
		}

		# Helper: SID -> sAMAccountName (or CN / DN) via LDAP search on objectSid
		def sid_to_name(conn: Connection, base_dn: str, sid_str: str) -> str:
			if sid_str in WELL_KNOWN:
				return WELL_KNOWN[sid_str]
			try:
				sid_obj = RPC_SID(); sid_obj.fromString(sid_str)
				sid_bytes = sid_obj.getData()  # raw SID bytes
				# Build escaped-bytes filter for objectSid equality
				esc = ''.join('\\{:02x}'.format(b) for b in sid_bytes)
				flt = f'(objectSid={esc})'
				if conn.search(base_dn, flt, SUBTREE, attributes=['sAMAccountName', 'cn', 'distinguishedName']):
					if conn.entries:
						e = conn.entries[0]
						for attr in ('sAMAccountName', 'cn', 'distinguishedName'):
							if attr in e and e[attr].value:
								return str(e[attr].value)
			except Exception:
				pass
			return sid_str  # fallback to SID if not resolvable

		# Basic rights decode (extend as needed)
		RIGHTS_MAP = {
			0x10000000: 'GenericAll',
			0x40000000: 'GenericWrite',
			0x80000000: 'GenericRead',
			0x20000000: 'GenericExecute',
			0x00000008: 'WriteDacl',
			0x00000002: 'WriteOwner',
		}

		def ace_type_to_str(t: int) -> str:
			return {
				0x00: 'ALLOW',
				0x01: 'DENY',
				0x05: 'ALLOW_OBJECT',
				0x06: 'DENY_OBJECT',
			}.get(t, hex(t))

		# --- Output ---
		print(f"Permissions on object: {TARGET_DN}")
		print('-' * 120)
		print(f"{'Identity':<40} {'RightsMask':<12} {'Rights(decoded)':<45} {'ACEType':<14} {'Inherited':<9} {'ObjectType'}")
		print('-' * 120)

		for ace in dacl.aces:
			ace_type  = ace['AceType']              # allow/deny (+ object variants)
			ace_flags = ace['AceFlags']
			inherited = bool(ace_flags & 0x10)      # INHERITED_ACE
			mask      = ace['Ace']['Mask']
			sid_str   = str(ace['Ace']['Sid'])
			identity  = sid_to_name(conn, BASE_DN, sid_str)

			# ObjectType GUID is present for object-specific ACEs (0x05/0x06)
			obj_type_guid = ''
			try:
				if 'ObjectType' in ace['Ace'] and ace['Ace']['ObjectType'] is not None:
					obj_type_guid = str(ace['Ace']['ObjectType'])
			except Exception:
				pass

			rights_decoded = [name for bit, name in RIGHTS_MAP.items() if (mask & bit) == bit]
			print(f"{identity:<40} {hex(mask):<12} {','.join(rights_decoded):<45} {ace_type_to_str(ace_type):<14} {str(inherited):<9} {obj_type_guid}")




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
