
# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
import os
import sys
import ldap
from pyasn1.type.univ import Integer
from pyasn1.codec.ber import encoder

# Optional: use impacket to decode the SD into DACL/ACEs
try:
    from impacket.nt_security import SECURITY_DESCRIPTOR
    HAVE_IMPACKET = True
except Exception:
    HAVE_IMPACKET = False


def build_sd_control(sdflags):
    """
    Build the LDAP server control for requesting nTSecurityDescriptor parts.
    OID: 1.2.840.113556.1.4.801 (LDAP_SERVER_SD_FLAGS_OID)
    Flags:
        0x01 = OWNER
        0x02 = GROUP
        0x04 = DACL
        0x08 = SACL (requires SeSecurityPrivilege; typically not available)
    """
    control_value = encoder.encode(Integer(sdflags))
    return ldap.controls.LDAPControl('1.2.840.113556.1.4.801', True, control_value)


def connect(server_url, user, password, insecure_tls=False):
    """
    Initialize and bind an LDAP connection.
    Use ldaps://host:636 for SSL. Set insecure_tls=True only for lab/testing.
    """
    if insecure_tls:
        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
    ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)

    conn = ldap.initialize(server_url)
    # Disable referrals to avoid chasing across partitions
    conn.set_option(ldap.OPT_REFERRALS, 0)
    conn.simple_bind_s(user, password)
    return conn


def parse_security_descriptor(sd_bytes):
    """
    Parse SECURITY_DESCRIPTOR bytes using impacket (if available) and return
    a list of simplified ACE records. If impacket is missing, return None.
    """
    if not HAVE_IMPACKET:
        return None

    sd = SECURITY_DESCRIPTOR(sd_bytes)
    dacl = sd['Dacl']
    if dacl is None:
        return []

    aces = []
    for ace in dacl.aces:
        ace_type = ace['AceType']            # e.g., ACCESS_ALLOWED_ACE_TYPE
        mask = ace['Ace']['Mask']['Mask']    # access mask
        sid = ace['Ace']['Sid'].formatCanonical()  # S-1-5-...
        flags = ace['Ace']['AceFlags']
        inherited = bool(flags & 0x10)       # INHERITED_ACE

        aces.append({
            'AceType': ace_type,
            'Mask': mask,
            'Sid': sid,
            'Inherited': inherited,
        })
    return aces


def sid_to_binary(sid_str):
    """
    Convert string SID (S-1-5-21-...) into binary for LDAP search on objectSid.
    """
    # Minimal parser; for robust conversion you can use impacket/pyad modules.
    try:
        parts = sid_str.split('-')
        if not parts[0] == 'S':
            raise ValueError('Not a SID')
        revision = int(parts[1])
        authority = int(parts[2])

        # SubAuthorities
        sub_auths = list(map(int, parts[3:]))

        # Build binary:
        # 1 byte revision, 1 byte subauth count, 6 bytes authority big endian,
        # then each subauth as 4 bytes little endian.
        import struct
        bin_sid = bytearray()
        bin_sid.append(revision & 0xFF)
        bin_sid.append(len(sub_auths) & 0xFF)
        # 6-byte big endian authority
        bin_sid += authority.to_bytes(6, 'big')
        # sub authorities 4-byte little endian
        for sa in sub_auths:
            bin_sid += struct.pack('<I', sa)
        return bytes(bin_sid)
    except Exception:
        return None


def resolve_sid_to_name(conn, base_dn, sid_str):
    """
    Resolve SID -> (distinguishedName, sAMAccountName or Name) via LDAP.
    Returns a friendly string like 'DOMAIN\\account' or DN as fallback.
    """
    bin_sid = sid_to_binary(sid_str)
    if not bin_sid:
        return sid_str

    # Build a binary filter for objectSid
    # python-ldap expects already-escaped filter; we need to hex-escape the bytes
    sid_hex = ''.join(['\\{:02X}'.format(b) for b in bin_sid])
    flt = f'(objectSid={sid_hex})'
    try:
        results = conn.search_s(
            base_dn,
            ldap.SCOPE_SUBTREE,
            flt,
            ['distinguishedName', 'sAMAccountName', 'cn', 'name', 'objectClass']
        )
        for dn, attrs in results or []:
            if not dn or not attrs:
                continue
            # Pick sAMAccountName, or name/cn
            sam = attrs.get('sAMAccountName', [b''])
            name = attrs.get('name', [b''])
            cn = attrs.get('cn', [b''])
            account = (sam[0] or name[0] or cn[0]).decode('utf-8', errors='ignore')
            return f'{account} ({dn})'
    except Exception:
        pass
    return sid_str


class Command(BaseCommand):
    help = "Fetch and parse nTSecurityDescriptor for a single DN (DACL), optionally resolve SIDs."

    def add_arguments(self, parser):
        parser.add_argument('--dn', required=True, help='Distinguished Name of the target object')
        parser.add_argument('--server', required=True, help='LDAP URL, e.g., ldaps://dc01.example.com:636')
        parser.add_argument('--user', default=os.environ.get('KARTOTEKET_LDAPUSER'),
                            help='Bind DN/User. Defaults to $KARTOTEKET_LDAPUSER.')
        parser.add_argument('--password', default=os.environ.get('KARTOTEKET_LDAPPASSWORD'),
                            help='Bind password. Defaults to $KARTOTEKET_LDAPPASSWORD.')
        parser.add_argument('--base-dn', required=False,
                            help='Base DN for SID resolution searches (e.g., DC=example,DC=com)')
        parser.add_argument('--sdflags', default='0x07',
                            help='SD flags hex (default 0x07 = OWNER|GROUP|DACL).')
        parser.add_argument('--resolve-sids', action='store_true',
                            help='Resolve ACE SIDs to names via LDAP.')
        parser.add_argument('--insecure-tls', action='store_true',
                            help='Disable TLS cert validation (testing only).')

    def handle(self, *args, **options):
        dn = options['dn']
        server = options['server']
        user = options['user']
        password = options['password']
        base_dn = options.get('base_dn') or ','.join(dn.split(',')[-2:])  # crude fallback to last 2 RDNs
        insecure_tls = options['insecure_tls']

        if not user or not password:
            raise CommandError("Bind user/password not provided (use --user/--password or env vars).")

        # Parse sdflags (allow 0x.. or decimal)
        sdflags_str = options['sdflags'].lower().strip()
        sdflags = int(sdflags_str, 16) if sdflags_str.startswith('0x') else int(sdflags_str)

        # Connect
        try:
            conn = connect(server, user, password, insecure_tls=insecure_tls)
        except ldap.INVALID_CREDENTIALS:
            raise CommandError("Invalid LDAP credentials.")
        except Exception as e:
            raise CommandError(f"LDAP connect/bind failed: {e}")

        # Build SD control
        sd_control = build_sd_control(sdflags)

        # Perform BASE search for nTSecurityDescriptor
        try:
            results = conn.search_ext_s(
                dn,
                ldap.SCOPE_BASE,
                '(objectClass=*)',
                ['nTSecurityDescriptor'],
                serverctrls=[sd_control]
            )
        except ldap.NO_SUCH_OBJECT:
            conn.unbind_s()
            raise CommandError(f"DN not found: {dn}")
        except Exception as e:
            conn.unbind_s()
            raise CommandError(f"LDAP search failed: {e}")

        conn.unbind_s()

        # Parse result
        sd_bytes = None
        for rdn, attrs in results or []:
            if not rdn or not attrs:
                continue
            values = attrs.get('nTSecurityDescriptor')
            if values:
                sd_bytes = values[0]
                break

        self.stdout.write(f"DN: {dn}")
        if not sd_bytes:
            self.stdout.write(self.style.WARNING(
                "No nTSecurityDescriptor returned. "
                "Likely causes: insufficient permissions (needs READ_CONTROL), wrong DC/port, "
                "or using Global Catalog. Try sdflags=0x07 and ensure the account can read permissions."
            ))
            return

        self.stdout.write(f"SecurityDescriptor bytes: {len(sd_bytes)}")

        # If Impacket is available, decode DACL and print ACEs
        aces = parse_security_descriptor(sd_bytes)
        if aces is None:
            self.stdout.write(self.style.WARNING(
                "Impacket not available – skipping ACE decoding. "
                "Install with: pip install impacket"
            ))
            return

        if not aces:
            self.stdout.write("No DACL or zero ACEs found.")
            return

        self.stdout.write("\nACEs:")
        # Optional: resolve SIDs
        resolve_sids = options['resolve_sids']
        # If we need to resolve SIDs, make a fresh read-only connection
        res_conn = None
        if resolve_sids:
            try:
                res_conn = connect(server, user, password, insecure_tls=insecure_tls)
            except Exception:
                self.stdout.write(self.style.WARNING("Could not open connection for SID resolution."))

        for ace in aces:
            sid = ace['Sid']
            friendly = sid
            if resolve_sids and res_conn:
                try:
                    friendly = resolve_sid_to_name(res_conn, base_dn, sid)
                except Exception:
                    pass
            self.stdout.write(
                f"- AceType={ace['AceType']} "
                f"Mask=0x{ace['Mask']:08X} "
                f"SID={sid} "
                f"Name={friendly if friendly != sid else ''} "
                f"Inherited={ace['Inherited']}"
            )

        if res_conn:
            try:
                res_conn.unbind_s()
            except Exception:
                pass
