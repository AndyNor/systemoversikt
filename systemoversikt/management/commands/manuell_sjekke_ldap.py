
# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import os
import ldap
from pyasn1.type.univ import Integer
from pyasn1.codec.ber import encoder  # BER encode ASN.1 INTEGER

class Command(BaseCommand):
    def handle(self, **options):

        cn = "CN=UKE232914,OU=UKE,OU=Brukere,OU=OK,DC=oslofelles,DC=oslo,DC=kommune,DC=no"
        server = 'ldaps://ldaps.oslofelles.oslo.kommune.no:636'
        user = os.environ["KARTOTEKET_LDAPUSER"]
        password = os.environ["KARTOTEKET_LDAPPASSWORD"]

        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
        ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)

        ldap_client = ldap.initialize(server)
        ldap_client.set_option(ldap.OPT_REFERRALS, 0)
        ldap_client.bind_s(user, password)

        # --- FIX 1: use 0x07 instead of 0x04 ---
        sdflags = 0x07    # Owner + Group + DACL (recommended)

        control_value = encoder.encode(Integer(sdflags))
        sd_control = ldap.controls.LDAPControl(
            '1.2.840.113556.1.4.801',
            True,
            control_value
        )

        # --- FIX 2: use cn instead of undefined dn ---
        result = ldap_client.search_ext_s(
            cn,
            ldap.SCOPE_BASE,
            '(objectClass=*)',
            ['nTSecurityDescriptor'],
            serverctrls=[sd_control]
        )

        ldap_client.unbind_s()

        for dn, attrs in result:
            if not dn:
                continue
            has_sd = 'nTSecurityDescriptor' in attrs and attrs['nTSecurityDescriptor']
            print("DN:", dn)
            print("Has nTSecurityDescriptor:", bool(has_sd))
            if has_sd:
                print("SD bytes:", len(attrs['nTSecurityDescriptor'][0]))
