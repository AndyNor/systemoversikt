# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: Tests for SDDL parser used by tool_ntfs.
from django.test import SimpleTestCase

from systemoversikt.sddl_parser import SddlParseError, normalize_sddl_input, parse_sddl


SAMPLE_SDDL = (
	"D:AI(A;OICI;FA;;;S-1-5-21-1123878227-590538075-4181424053-65398)"
	"(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)"
	"(A;OICI;FA;;;S-1-5-21-1123878227-590538075-4181424053-48099)"
	"(A;OICI;0x1200a9;;;S-1-5-21-1123878227-590538075-4181424053-73462)"
	"(A;OICI;0x1301bf;;;S-1-5-21-1123878227-590538075-4181424053-73463)"
)


class SddlParserTests(SimpleTestCase):
	def test_normalize_extracts_dacl_from_noise(self):
		raw = "icacls output\n" + SAMPLE_SDDL
		self.assertTrue(normalize_sddl_input(raw).startswith("D:"))

	def test_parse_sample_dacl_ace_count(self):
		parsed = parse_sddl(SAMPLE_SDDL)
		self.assertEqual(len(parsed['dacl']['aces']), 6)

	def test_parse_well_known_trustee(self):
		parsed = parse_sddl(SAMPLE_SDDL)
		trustees = [ace['trustee']['name'] for ace in parsed['dacl']['aces']]
		self.assertIn('Built-in Administrators', trustees)
		self.assertIn('LOCAL SYSTEM', trustees)

	def test_parse_hex_rights_read_execute(self):
		parsed = parse_sddl(SAMPLE_SDDL)
		hex_ace = parsed['dacl']['aces'][4]
		self.assertIn('Read & execute', hex_ace['rights']['labels'])

	def test_parse_hex_rights_modify(self):
		parsed = parse_sddl(SAMPLE_SDDL)
		hex_ace = parsed['dacl']['aces'][5]
		self.assertIn('Modify', hex_ace['rights']['labels'])

	def test_empty_input_raises(self):
		with self.assertRaises(SddlParseError):
			parse_sddl('')
