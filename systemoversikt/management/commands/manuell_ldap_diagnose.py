# -*- coding: utf-8 -*-
# Change log:
# 2026-10-21: Diagnostic LDAP connect – verbose env, options, bind, and rootDSE identity.
from django.core.management.base import BaseCommand
import ldap
import os
import socket
from urllib.parse import urlparse


# Friendly names for common python-ldap option values we set/read.
_TLS_REQUIRE_CERT_NAMES = {
	ldap.OPT_X_TLS_NEVER: 'OPT_X_TLS_NEVER',
	ldap.OPT_X_TLS_HARD: 'OPT_X_TLS_HARD',
	ldap.OPT_X_TLS_DEMAND: 'OPT_X_TLS_DEMAND',
	ldap.OPT_X_TLS_ALLOW: 'OPT_X_TLS_ALLOW',
	ldap.OPT_X_TLS_TRY: 'OPT_X_TLS_TRY',
}


class Command(BaseCommand):
	help = 'Establish an LDAP connection to AD and print verbose connection details (no password).'

	def handle(self, **options):
		def section(title):
			self.stdout.write('')
			self.stdout.write('=== %s ===' % title)

		def line(label, value):
			self.stdout.write('  %-32s %s' % (label + ':', value))

		section('Environment')
		server = os.environ.get('KARTOTEKET_LDAPSERVER')
		user = os.environ.get('KARTOTEKET_LDAPUSER')
		password = os.environ.get('KARTOTEKET_LDAPPASSWORD')
		ldap_root = os.environ.get('KARTOTEKET_LDAPROOT')

		line('KARTOTEKET_LDAPSERVER', server or '(missing)')
		line('KARTOTEKET_LDAPUSER', user or '(missing)')
		line('KARTOTEKET_LDAPPASSWORD', '(set, %d chars)' % len(password) if password else '(missing)')
		line('KARTOTEKET_LDAPROOT', ldap_root or '(missing)')

		missing = [n for n, v in [
			('KARTOTEKET_LDAPSERVER', server),
			('KARTOTEKET_LDAPUSER', user),
			('KARTOTEKET_LDAPPASSWORD', password),
		] if not v]
		if missing:
			raise SystemExit('Missing required env: %s' % ', '.join(missing))

		section('python-ldap')
		line('ldap.__version__', ldap.__version__)
		line('ldap.__file__', getattr(ldap, '__file__', '(unknown)'))

		section('URL / DNS')
		parsed = urlparse(server)
		hostname = parsed.hostname or server
		port = parsed.port
		if port is None:
			port = 636 if (parsed.scheme or '').lower() == 'ldaps' else 389
		line('scheme', parsed.scheme or '(none – bare host?)')
		line('hostname', hostname)
		line('port', port)
		try:
			addrs = sorted({ai[4][0] for ai in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)})
			line('resolved addresses', ', '.join(addrs) if addrs else '(none)')
		except socket.gaierror as e:
			line('resolved addresses', 'DNS failed: %s' % e)

		section('Options set (same pattern as imports)')
		line('OPT_X_TLS_REQUIRE_CERT', 'OPT_X_TLS_NEVER (%s)' % ldap.OPT_X_TLS_NEVER)
		line('OPT_PROTOCOL_VERSION', '3')
		line('OPT_REFERRALS', '0 (do not chase)')
		line('bind method', 'simple_bind_s (simple bind)')

		ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
		ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)

		section('Connect + bind')
		ldap_client = None
		try:
			line('initialize()', server)
			ldap_client = ldap.initialize(server)
			ldap_client.set_option(ldap.OPT_REFERRALS, 0)

			# Reflect options back after set (where readable).
			try:
				req = ldap_client.get_option(ldap.OPT_X_TLS_REQUIRE_CERT)
				line('get OPT_X_TLS_REQUIRE_CERT', '%s (%s)' % (
					_TLS_REQUIRE_CERT_NAMES.get(req, 'unknown'), req))
			except ldap.LDAPError as e:
				line('get OPT_X_TLS_REQUIRE_CERT', 'unavailable: %s' % e)
			try:
				line('get OPT_PROTOCOL_VERSION', ldap_client.get_option(ldap.OPT_PROTOCOL_VERSION))
			except ldap.LDAPError as e:
				line('get OPT_PROTOCOL_VERSION', 'unavailable: %s' % e)
			try:
				line('get OPT_REFERRALS', ldap_client.get_option(ldap.OPT_REFERRALS))
			except ldap.LDAPError as e:
				line('get OPT_REFERRALS', 'unavailable: %s' % e)

			line('simple_bind_s()', user)
			ldap_client.simple_bind_s(user, password)
			line('bind', 'OK')

			section('rootDSE (who answered – useful behind VIP/BigIP)')
			# Empty DN + BASE scope = rootDSE
			result = ldap_client.search_s(
				'',
				ldap.SCOPE_BASE,
				'(objectClass=*)',
				[
					'dnsHostName',
					'serverName',
					'defaultNamingContext',
					'rootDomainNamingContext',
					'ldapServiceName',
					'supportedLDAPVersion',
					'supportedSASLMechanisms',
					'highestCommittedUSN',
					'isGlobalCatalogReady',
					'forestFunctionality',
					'domainFunctionality',
					'domainControllerFunctionality',
				],
			)
			for dn, attrs in result:
				line('rootDSE DN', repr(dn))
				for key in sorted(attrs.keys()):
					vals = attrs[key]
					decoded = []
					for v in vals:
						if isinstance(v, bytes):
							try:
								decoded.append(v.decode('utf-8'))
							except UnicodeDecodeError:
								decoded.append(repr(v))
						else:
							decoded.append(str(v))
					line(key, ', '.join(decoded))

			if ldap_root:
				section('Base DN check (KARTOTEKET_LDAPROOT)')
				try:
					base_result = ldap_client.search_s(
						ldap_root,
						ldap.SCOPE_BASE,
						'(objectClass=*)',
						['distinguishedName', 'objectClass'],
					)
					for dn, attrs in base_result:
						line('base search DN', dn)
						ocs = attrs.get('objectClass', [])
						line('objectClass', ', '.join(
							v.decode('utf-8') if isinstance(v, bytes) else str(v) for v in ocs
						))
					line('base DN', 'reachable')
				except ldap.LDAPError as e:
					line('base DN', 'failed: %s' % e)

		except ldap.LDAPError as e:
			line('error', e)
			raise SystemExit(1)
		finally:
			if ldap_client is not None:
				try:
					ldap_client.unbind_s()
					section('Cleanup')
					line('unbind_s()', 'OK')
				except ldap.LDAPError as e:
					section('Cleanup')
					line('unbind_s()', 'failed: %s' % e)

		self.stdout.write('')
		self.stdout.write('Done.')
