# -*- coding: utf-8 -*-
from django.test import TestCase

from systemoversikt.models import (
	AzureGroup,
	AzureNamedLocations,
	azure_named_location_ca_label,
	azure_named_location_display_name_cache,
	conditional_access_enrich_policy_locations,
	conditional_access_guid_lookup_cache,
	conditional_access_guids_in_text,
	conditional_access_replace_guid,
)


class ConditionalAccessGuidLookupTests(TestCase):
	def test_guids_in_text_finds_uuid(self):
		text = '{"includeUsers": ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]}'
		self.assertEqual(
			conditional_access_guids_in_text(text),
			['aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'],
		)

	def test_guid_lookup_cache_resolves_known_group(self):
		guid = '11111111-2222-3333-4444-555555555555'
		AzureGroup.objects.create(guid=guid, displayName='Test group')
		cache = conditional_access_guid_lookup_cache([guid])
		self.assertEqual(cache[guid], 'Test group')

	def test_replace_guid_uses_lookup_without_db(self):
		guid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
		text = f'user {guid}'
		with self.assertNumQueries(0):
			result = conditional_access_replace_guid(text, guid_lookup={guid: 'Cached name'})
		self.assertIn('Cached name', result)
		self.assertNotIn(guid, result)

	def test_named_location_ca_label_includes_ip_ranges(self):
		nl = AzureNamedLocations.objects.create(
			ipNamedLocation_id='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
			displayName='Office VPN',
			ipRanges='["192.0.2.0/24", "203.0.113.0/24"]',
		)
		self.assertEqual(
			azure_named_location_ca_label(nl),
			'Office VPN (192.0.2.0/24, 203.0.113.0/24)',
		)

	def test_named_location_ca_label_skips_countries_only(self):
		nl = AzureNamedLocations.objects.create(
			ipNamedLocation_id='bbbbbbbb-cccc-dddd-eeee-ffffffffffff',
			displayName='Norge',
			countriesAndRegions='[{"code": "NO", "name": "Norway"}]',
		)
		self.assertEqual(azure_named_location_ca_label(nl), 'Norge')

	def test_guid_lookup_cache_named_location_includes_ip_ranges(self):
		guid = 'cccccccc-dddd-eeee-ffff-000000000000'
		AzureNamedLocations.objects.create(
			ipNamedLocation_id=guid,
			displayName='Trusted subnet',
			ipRanges='["192.0.2.0/24"]',
		)
		cache = conditional_access_guid_lookup_cache([guid])
		self.assertEqual(cache[guid], 'Trusted subnet (192.0.2.0/24)')

	def test_enrich_policy_locations_by_exact_display_name(self):
		AzureNamedLocations.objects.create(
			ipNamedLocation_id='dddddddd-eeee-ffff-0000-111111111111',
			displayName='Ekstern partner',
			ipRanges='["203.0.113.0/24"]',
		)
		policy_data = {
			'value': [{
				'conditions': {
					'locations': {
						'includeLocations': ['All', 'Ekstern partner'],
						'excludeLocations': ['Ekstern partner'],
					},
				},
			}],
		}
		cache = azure_named_location_display_name_cache()
		enriched = conditional_access_enrich_policy_locations(policy_data, display_name_cache=cache)
		locations = enriched['value'][0]['conditions']['locations']
		self.assertEqual(locations['includeLocations'][0], 'All')
		self.assertEqual(
			locations['includeLocations'][1],
			'Ekstern partner (203.0.113.0/24)',
		)
		self.assertEqual(
			locations['excludeLocations'][0],
			'Ekstern partner (203.0.113.0/24)',
		)
