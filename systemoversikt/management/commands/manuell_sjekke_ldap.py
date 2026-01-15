
# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import os
import ldap
import sys
from pyasn1.type.univ import Integer
from pyasn1.codec.ber import encoder  # BER encode ASN.1 INTEGER

class Command(BaseCommand):
	def handle(self, **options):


		VIP = 'ldaps://ldaps.oslofelles.oslo.kommune.no:636'
		DN  = "CN=SVC-P-KAR-WEBLDAP01,OU=DIG,OU=Servicekontoer,OU=OK,DC=oslofelles,DC=oslo,DC=kommune,DC=no"
		SDFLAGS = 0x04  # Owner|Group|DACL (0x04 is DACL only)

		def main():
			user = os.environ.get("KARTOTEKET_LDAPUSER")
			password = os.environ.get("KARTOTEKET_LDAPPASSWORD")
			if not user or not password:
				print("Missing creds: set KARTOTEKET_LDAPUSER and KARTOTEKET_LDAPPASSWORD.")
				sys.exit(2)

			ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # Use CA in prod
			ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)

			print(f"VIP: {VIP}")
			print(f"DN : {DN}")
			print(f"SD : 0x{SDFLAGS:02X} (non-critical)")

			try:
				conn = ldap.initialize(VIP)
				conn.set_option(ldap.OPT_REFERRALS, 0)
				conn.simple_bind_s(user, password)
			except Exception as e:
				print(f"[FAIL] Bind to VIP failed: {e}")
				sys.exit(3)

			# RootDSE sanity
			try:
				root = conn.search_s("", ldap.SCOPE_BASE, None, ['defaultNamingContext', 'isGlobalCatalogReady', 'dnsHostName'])
				attrs = root[0][1] if root else {}
				def g(n, d=""):
					v = attrs.get(n)
					return (v[0].decode(errors='ignore') if v and len(v) else d)
				default_nc = g('defaultNamingContext')
				is_gc = g('isGlobalCatalogReady', 'FALSE').upper()
				dns_host = g('dnsHostName')
				print(f"RootDSE dnsHostName          : {dns_host or '(empty)'}")
				print(f"RootDSE defaultNamingContext : {default_nc or '(empty)'}")
				print(f"RootDSE isGlobalCatalogReady : {is_gc}")
				if not default_nc:
					conn.unbind_s()
					print("[FAIL] defaultNamingContext empty. VIP may not point to AD domain LDAP.")
					sys.exit(4)
			except Exception as e:
				try: conn.unbind_s()
				except Exception: pass
				print(f"[FAIL] RootDSE check failed on VIP: {e}")
				sys.exit(5)

			# SD control (non-critical)
			ctrl = ldap.controls.LDAPControl('1.2.840.113556.1.4.801', False, encoder.encode(Integer(SDFLAGS)))

			try:
				res = conn.search_ext_s(DN, ldap.SCOPE_BASE, '(objectClass=*)', ['nTSecurityDescriptor'], serverctrls=[ctrl])
			except ldap.UNAVAILABLE_CRITICAL_EXTENSION as e:
				try: conn.unbind_s()
				except Exception: pass
				print(f"[FAIL] Server rejected SD control: {e}")
				sys.exit(6)
			except Exception as e:
				try: conn.unbind_s()
				except Exception: pass
				print(f"[FAIL] SD search failed: {e}")
				sys.exit(7)

			try: conn.unbind_s()
			except Exception: pass

			if not res:
				print("[FAIL] No entry returned for the DN from VIP.")
				sys.exit(8)

			rdn, a = res[0]
			sdvals = a.get('nTSecurityDescriptor') if a else None
			print(f"Entry DN returned             : {rdn or '(none)'}")
			print(f"Has nTSecurityDescriptor      : {bool(sdvals)}")
			if sdvals:
				print(f"nTSecurityDescriptor size     : {len(sdvals[0])} bytes")
				print("[OK] VIP returns SD correctly.")
				sys.exit(0)
			else:
				print("[WARN] No nTSecurityDescriptor returned.")
				print("      Likely cause: bind account lacks READ_CONTROL ('Read permissions') on this object/OU.")
				print("      Less likely : VIP pool member cannot serve SD; ask LB team to validate monitor/backends.")
				sys.exit(9)

		main()

