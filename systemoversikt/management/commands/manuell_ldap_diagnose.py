# -*- coding: utf-8 -*-
# Change log:
# 2026-10-21: Probe TLS modes, sample multiple binds for DC mix, print summary only.
# 2026-10-21: Diagnostic LDAP connect – verbose env, options, bind, and rootDSE identity.
from django.core.management.base import BaseCommand
import ldap
import os
import socket
from collections import Counter
from urllib.parse import urlparse


# Strictest first – used both for probing and for picking the sample mode.
_TLS_MODES = [
	('OPT_X_TLS_HARD', ldap.OPT_X_TLS_HARD),
	('OPT_X_TLS_DEMAND', ldap.OPT_X_TLS_DEMAND),
	('OPT_X_TLS_TRY', ldap.OPT_X_TLS_TRY),
	('OPT_X_TLS_ALLOW', ldap.OPT_X_TLS_ALLOW),
	('OPT_X_TLS_NEVER', ldap.OPT_X_TLS_NEVER),
]


def _decode_attr(attrs, name):
	vals = attrs.get(name) or []
	out = []
	for v in vals:
		if isinstance(v, bytes):
			try:
				out.append(v.decode('utf-8'))
			except UnicodeDecodeError:
				out.append(repr(v))
		else:
			out.append(str(v))
	return ', '.join(out) if out else None


def _short_ldap_error(exc):
	text = str(exc).replace('\n', ' ').strip()
	if len(text) > 160:
		text = text[:157] + '...'
	return text


class Command(BaseCommand):
	help = (
		'Probe LDAP/AD TLS modes and sample multiple connections to see which DCs '
		'answer behind the VIP. Prints a summary only (no password).'
	)

	def add_arguments(self, parser):
		parser.add_argument(
			'--samples',
			type=int,
			default=20,
			help='Number of reconnects when sampling DCs (default: 20).',
		)

	def handle(self, **options):
		samples = max(1, options['samples'])

		def section(title):
			self.stdout.write('')
			self.stdout.write('=== %s ===' % title)

		def line(label, value):
			self.stdout.write('  %-28s %s' % (label + ':', value))

		server = os.environ.get('KARTOTEKET_LDAPSERVER')
		user = os.environ.get('KARTOTEKET_LDAPUSER')
		password = os.environ.get('KARTOTEKET_LDAPPASSWORD')
		ldap_root = os.environ.get('KARTOTEKET_LDAPROOT')

		missing = [n for n, v in [
			('KARTOTEKET_LDAPSERVER', server),
			('KARTOTEKET_LDAPUSER', user),
			('KARTOTEKET_LDAPPASSWORD', password),
		] if not v]
		if missing:
			raise SystemExit('Missing required env: %s' % ', '.join(missing))

		parsed = urlparse(server)
		hostname = parsed.hostname or server
		port = parsed.port
		if port is None:
			port = 636 if (parsed.scheme or '').lower() == 'ldaps' else 389
		try:
			addrs = sorted({ai[4][0] for ai in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)})
			resolved = ', '.join(addrs) if addrs else '(none)'
		except socket.gaierror as e:
			resolved = 'DNS failed: %s' % e

		section('Target')
		line('server', server)
		line('VIP / DNS', '%s -> %s' % (hostname, resolved))
		line('user', user)
		line('password', '(set, %d chars)' % len(password))
		line('LDAP root', ldap_root or '(not set)')
		line('python-ldap', ldap.__version__)
		line('bind', 'simple_bind_s')
		line('referrals', 'off (OPT_REFERRALS=0)')

		def try_connect(tls_mode_value, fetch_identity=False):
			"""Bind with a given TLS require-cert mode. Returns (ok, detail_or_error)."""
			ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, tls_mode_value)
			# Force a new TLS context so the require-cert change takes effect.
			try:
				ldap.set_option(ldap.OPT_X_TLS_NEWCTX, 0)
			except ldap.LDAPError:
				pass
			ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)

			client = None
			try:
				client = ldap.initialize(server)
				client.set_option(ldap.OPT_REFERRALS, 0)
				client.simple_bind_s(user, password)

				identity = {}
				if fetch_identity:
					result = client.search_s(
						'',
						ldap.SCOPE_BASE,
						'(objectClass=*)',
						[
							'dnsHostName',
							'serverName',
							'defaultNamingContext',
							'supportedSASLMechanisms',
							'isGlobalCatalogReady',
						],
					)
					attrs = result[0][1] if result else {}
					identity = {
						'dnsHostName': _decode_attr(attrs, 'dnsHostName'),
						'serverName': _decode_attr(attrs, 'serverName'),
						'defaultNamingContext': _decode_attr(attrs, 'defaultNamingContext'),
						'supportedSASLMechanisms': _decode_attr(attrs, 'supportedSASLMechanisms'),
						'isGlobalCatalogReady': _decode_attr(attrs, 'isGlobalCatalogReady'),
					}
					if ldap_root:
						try:
							client.search_s(
								ldap_root,
								ldap.SCOPE_BASE,
								'(objectClass=*)',
								['distinguishedName'],
							)
							identity['base_dn'] = 'reachable'
						except ldap.LDAPError as e:
							identity['base_dn'] = 'failed: %s' % _short_ldap_error(e)

				return True, identity
			except ldap.LDAPError as e:
				return False, _short_ldap_error(e)
			finally:
				if client is not None:
					try:
						client.unbind_s()
					except ldap.LDAPError:
						pass

		section('TLS mode probe (strictest first)')
		working_modes = []
		first_identity = None
		for name, value in _TLS_MODES:
			ok, detail = try_connect(value, fetch_identity=False)
			if ok:
				working_modes.append((name, value))
				line(name, 'OK')
			else:
				line(name, 'FAIL – %s' % detail)

		if not working_modes:
			self.stdout.write('')
			self.stdout.write(self.style.ERROR('No TLS mode succeeded. Stopping.'))
			raise SystemExit(1)

		# Prefer the strictest mode that worked.
		best_name, best_value = working_modes[0]
		line('chosen for sampling', best_name)
		if best_name == 'OPT_X_TLS_NEVER':
			self.stdout.write(self.style.WARNING(
				'  Only OPT_X_TLS_NEVER works – cert verification is disabled (current import behaviour).'
			))
		elif best_name in ('OPT_X_TLS_HARD', 'OPT_X_TLS_DEMAND'):
			self.stdout.write(self.style.SUCCESS(
				'  Strict cert verification works – imports could move off OPT_X_TLS_NEVER.'
			))

		# One richer identity snapshot with the chosen mode.
		ok, first_identity = try_connect(best_value, fetch_identity=True)
		if ok and first_identity:
			section('Identity (one sample, %s)' % best_name)
			line('dnsHostName', first_identity.get('dnsHostName') or '(n/a)')
			line('serverName', first_identity.get('serverName') or '(n/a)')
			line('naming context', first_identity.get('defaultNamingContext') or '(n/a)')
			line('SASL mechanisms', first_identity.get('supportedSASLMechanisms') or '(n/a)')
			line('GC ready', first_identity.get('isGlobalCatalogReady') or '(n/a)')
			if 'base_dn' in first_identity:
				line('LDAP root', first_identity['base_dn'])

		section('DC sampling (%d reconnects, %s)' % (samples, best_name))
		dc_counts = Counter()
		failures = 0
		for _ in range(samples):
			ok, detail = try_connect(best_value, fetch_identity=True)
			if not ok:
				failures += 1
				continue
			dc = (detail or {}).get('dnsHostName') or '(unknown)'
			dc_counts[dc] += 1

		unique = len(dc_counts)
		line('success / fail', '%d / %d' % (samples - failures, failures))
		line('distinct DCs', unique)
		if dc_counts:
			self.stdout.write('  DCs hit:')
			for dc, count in dc_counts.most_common():
				pct = 100.0 * count / max(1, samples - failures)
				self.stdout.write('    %-48s %3d  (%.0f%%)' % (dc, count, pct))
		else:
			line('DCs hit', '(none)')

		section('Summary')
		tls_ok = ', '.join(n for n, _ in working_modes)
		tls_fail = ', '.join(n for n, v in _TLS_MODES if (n, v) not in working_modes)
		line('TLS OK', tls_ok or '(none)')
		line('TLS FAIL', tls_fail or '(none)')
		line('Recommended TLS', best_name)
		line('VIP', resolved)
		if unique <= 1:
			line('load balance', 'same DC every time (or single pool member)')
		else:
			line('load balance', '%d different DCs across %d connects' % (unique, samples - failures))

		self.stdout.write('')
		self.stdout.write('Done.')
