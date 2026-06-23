# -*- coding: utf-8 -*-
from django.test import TestCase
from django.urls import reverse

from systemoversikt.models import (
	AzureGroup,
	conditional_access_build_overview_tiles,
	conditional_access_collect_overview_filters,
	conditional_access_tile_conditions,
)


class ConditionalAccessOverviewTileTests(TestCase):
	def _sample_policies(self):
		group_guid = '11111111-2222-3333-4444-555555555555'
		app_id = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
		role_guid = 'bbbbbbbb-cccc-dddd-eeee-ffffffffffff'
		return [
			{
				'id': 'policy-active-1',
				'displayName': 'MFA - Require MFA',
				'state': 'enabled',
				'conditions': {
					'users': {
						'includeUsers': ['All'],
						'includeGroups': [group_guid],
						'includeRoles': [role_guid],
						'excludeUsers': ['excluded-user-guid'],
						'excludeGroups': [group_guid],
						'excludeRoles': [role_guid],
					},
					'applications': {
						'includeApplications': [app_id, 'Office365'],
						'excludeApplications': [app_id],
					},
					'locations': {'includeLocations': ['All']},
					'platforms': {
						'includePlatforms': ['windows'],
						'excludePlatforms': ['android'],
					},
					'clientAppTypes': ['browser'],
				},
				'grantControls': {'builtInControls': ['mfa']},
			},
		]

	def _enriched_sample(self, group_name='Security team', app_name='Office App'):
		policy = self._sample_policies()[0]
		enriched = dict(policy)
		enriched['conditions'] = {
			'users': {
				'includeUsers': ['All'],
				'includeGroups': [group_name],
				'includeRoles': ['Global Administrator'],
				'excludeUsers': ['Guest User'],
				'excludeGroups': [group_name],
			},
			'applications': {
				'includeApplications': [app_name, 'Office 365'],
				'excludeApplications': [app_name],
			},
			'locations': {'includeLocations': ['All']},
			'platforms': {
				'includePlatforms': ['windows'],
				'excludePlatforms': ['android'],
			},
			'clientAppTypes': ['browser'],
		}
		return policy, enriched

	def test_tile_conditions_uses_enriched_group_names(self):
		raw, enriched = self._enriched_sample(group_name='DIG Security')
		conditions = conditional_access_tile_conditions(
			enriched['conditions'],
			raw_conditions=raw['conditions'],
		)
		included_texts = [label['text'] for label in conditions['included_labels']]
		excluded_texts = [label['text'] for label in conditions['excluded_labels']]
		self.assertIn('DIG Security', included_texts)
		self.assertIn('All users', included_texts)
		self.assertIn('1 role', included_texts)
		self.assertIn('Office App', included_texts)
		self.assertIn('Guest User', excluded_texts)
		self.assertIn('DIG Security', excluded_texts)
		self.assertIn('1 role', excluded_texts)
		self.assertIn('group:11111111-2222-3333-4444-555555555555', conditions['filter_tags'])

	def test_build_overview_tiles_resolves_groups_from_lookup(self):
		group_guid = '11111111-2222-3333-4444-555555555555'
		AzureGroup.objects.create(guid=group_guid, displayName='Security team')
		raw, enriched = self._enriched_sample()
		guid_lookup = {group_guid: 'Security team'}
		tiles = conditional_access_build_overview_tiles(
			[enriched],
			'/rules/',
			guid_lookup=guid_lookup,
			raw_policies_by_id={raw['id']: raw},
		)
		included_texts = [label['text'] for label in tiles[0]['conditions_included']]
		self.assertIn('Security team', included_texts)

	def test_collect_overview_filters_groups(self):
		raw, enriched = self._enriched_sample(group_name='Ops team')
		tiles = conditional_access_build_overview_tiles(
			[enriched],
			'/rules/',
			raw_policies_by_id={raw['id']: raw},
		)
		groups = {group['id']: group for group in conditional_access_collect_overview_filters(tiles)}
		self.assertIn('groups', groups)
		group_tags = {opt['tag']: opt['label'] for opt in groups['groups']['options']}
		self.assertEqual(
			group_tags['group:11111111-2222-3333-4444-555555555555'],
			'Ops team',
		)


class ConditionalAccessOverviewViewTests(TestCase):
	def test_overview_url_resolves(self):
		url = reverse('rapport_conditional_access_overview')
		self.assertEqual(url, '/rapport/azure/conditional_access/overview/')
