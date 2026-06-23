# -*- coding: utf-8 -*-
from django.test import TestCase

from systemoversikt.models import (
	AzureGroup,
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
