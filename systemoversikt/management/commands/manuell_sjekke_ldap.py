
# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import os
import ldap
from pyasn1.type.univ import Integer
from pyasn1.codec.ber import encoder  # BER encode ASN.1 INTEGER

class Command(BaseCommand):
	def handle(self, **options):


		VIP = 'ldaps://ldaps.oslofelles.oslo.kommune.no:636'
		DN  = "CN=DIG232914,OU=DIG,OU=Brukere,OU=OK,DC=oslofelles,DC=oslo,DC=kommune,DC=no"

		def main():
			user = os.environ.get("KARTOTEKET_LDAPUSER")
			pwd  = os.environ.get("KARTOTEKET_LDAPPASSWORD")
			if not user or not pwd:
				print("Set KARTOTEKET_LDAPUSER and KARTOTEKET_LDAPPASSWORD")
				sys.exit(2)

			ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
			ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)

			print("VIP:", VIP)
			print("DN :", DN)

			try:
				conn = ldap.initialize(VIP)
				conn.set_option(ldap.OPT_REFERRALS, 0)
				conn.simple_bind_s(user, pwd)
			except Exception as e:
				print("[FAIL] Bind failed:", e); sys.exit(3)

			try:
				root = conn.search_s("", ldap.SCOPE_BASE, None,
									 ['defaultNamingContext','isGlobalCatalogReady',
									  'dnsHostName','supportedCapabilities'])
				a = root[0][1] if root else {}
				def get(k, d=""):
					v=a.get(k); return (v[0].decode(errors='ignore') if v else d)
				caps = [c.decode(errors='ignore') for c in a.get('supportedCapabilities',[])]
				print("dnsHostName             :", get('dnsHostName') or "(empty)")
				print("defaultNamingContext    :", get('defaultNamingContext') or "(empty)")
				print("isGlobalCatalogReady    :", (get('isGlobalCatalogReady','FALSE') or 'FALSE'))
				print("supportedCapabilities   :", caps)
			except Exception as e:
				print("[FAIL] RootDSE failed:", e); sys.exit(4)

			# SD control (non-critical), try 0x04 first
			ctrl = ldap.controls.LDAPControl('1.2.840.113556.1.4.801', False, encoder.encode(Integer(0x04)))
			try:
				res = conn.search_ext_s(DN, ldap.SCOPE_BASE, '(objectClass=*)',
										['nTSecurityDescriptor'], serverctrls=[ctrl])
			except Exception as e:
				print("[FAIL] SD search failed:", e); sys.exit(5)
			finally:
				try: conn.unbind_s()
				except: pass

			if not res:
				print("[FAIL] No entry returned."); sys.exit(6)
			sdvals = res[0][1].get('nTSecurityDescriptor') if res[0][1] else None
			print("Has nTSecurityDescriptor:", bool(sdvals))
			if sdvals:
				print("SD bytes                 :", len(sdvals[0]))
				print("[OK] VIP serves SD correctly.")
				sys.exit(0)

			# Guidance
			print("[WARN] SD missing. Likely causes:")
			print("  1) VIP routes to GC partition (common) -> ask F5 to ensure 636->636 to DC LDAP only, not 3269.")
			print("  2) Bind account lacks READ_CONTROL -> grant 'Read permissions' at the OU with inheritance.")
			sys.exit(9)

		main()

