# -*- coding: utf-8 -*-
# Change log:
# 2026-06-21: Tests for decoupled Qualys basisdrift vs risk-acceptance title rules.
from django.test import SimpleTestCase

from systemoversikt.qualys_vuln_rules import qualys_vuln_flags, title_matches


class _RuleStub:
	def __init__(self, title):
		self.title = title


class QualysVulnRulesTests(SimpleTestCase):
	def test_title_matches_case_insensitive_substring(self):
		self.assertTrue(title_matches("openssl", "OpenSSL Multiple Vulnerabilities"))
		self.assertFalse(title_matches("apache", "OpenSSL Multiple Vulnerabilities"))

	def test_qualys_vuln_flags_neither(self):
		flags = qualys_vuln_flags(
			"Some Other Vulnerability",
			basis_rules=[_RuleStub("openssl")],
			acceptance_rules=[_RuleStub("apache")],
		)
		self.assertEqual(flags, (False, False))

	def test_qualys_vuln_flags_basisdrift_only(self):
		flags = qualys_vuln_flags(
			"OpenSSL Multiple Vulnerabilities",
			basis_rules=[_RuleStub("openssl")],
			acceptance_rules=[_RuleStub("apache")],
		)
		self.assertEqual(flags, (True, False))

	def test_qualys_vuln_flags_accepted_only(self):
		flags = qualys_vuln_flags(
			"Apache HTTP Server Vulnerability",
			basis_rules=[_RuleStub("openssl")],
			acceptance_rules=[_RuleStub("apache")],
		)
		self.assertEqual(flags, (False, True))

	def test_qualys_vuln_flags_both(self):
		flags = qualys_vuln_flags(
			"OpenSSL and Apache combined issue",
			basis_rules=[_RuleStub("openssl")],
			acceptance_rules=[_RuleStub("apache")],
		)
		self.assertEqual(flags, (True, True))
