# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: Tests for navigation page search registry and matching.
from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase
from django.urls import reverse

from systemoversikt.search_nav_pages import (
	NAV_PAGES,
	match_nav_pages,
	reverse_kwargs_for_test,
)


class _PermUser:
	def __init__(self, permissions):
		self._permissions = set(permissions)

	def has_perm(self, permission):
		return permission in self._permissions


class _ProfileStub:
	def __init__(self, virksomhet_pk):
		self.virksomhet = _VirksomhetStub(virksomhet_pk) if virksomhet_pk is not None else None


class _VirksomhetStub:
	def __init__(self, pk):
		self.pk = pk


class _UserWithProfile:
	def __init__(self, permissions, virksomhet_pk):
		self.profile = _ProfileStub(virksomhet_pk)
		self._permissions = set(permissions)

	def has_perm(self, permission):
		return permission in self._permissions


class SearchNavPagesTests(SimpleTestCase):
	def test_all_registered_url_names_resolve(self):
		for entry in NAV_PAGES:
			kwargs = reverse_kwargs_for_test(entry)
			with self.subTest(url_name=entry['url_name'], label=entry['label']):
				reverse(entry['url_name'], kwargs=kwargs)

	def test_prioriteringer_matches_rapport_prioriteringer(self):
		user = _PermUser(['systemoversikt.view_system'])
		results = match_nav_pages('prioriteringer', user)
		self.assertTrue(results)
		self.assertEqual(results[0]['label'], 'Systemprioriteringer')
		self.assertEqual(results[0]['url'], reverse('rapport_prioriteringer'))

	def test_short_search_term_returns_empty(self):
		user = _PermUser(['systemoversikt.view_system'])
		self.assertEqual(match_nav_pages('p', user), [])

	def test_qualys_page_requires_permission(self):
		user_without = _PermUser(['systemoversikt.view_system'])
		user_with = _PermUser(['systemoversikt.view_qualysvuln'])
		self.assertEqual(match_nav_pages('qualys', user_without), [])
		self.assertTrue(match_nav_pages('qualys', user_with))

	def test_var_systembruk_hidden_without_virksomhet(self):
		user = _UserWithProfile(['systemoversikt.view_system'], virksomhet_pk=None)
		self.assertEqual(match_nav_pages('systembruk', user), [])

	def test_var_systembruk_shown_with_virksomhet(self):
		user = _UserWithProfile(['systemoversikt.view_system'], virksomhet_pk=42)
		results = match_nav_pages('systembruk', user)
		labels = [item['label'] for item in results]
		self.assertIn('Vår systembruk', labels)
		self.assertEqual(
			next(item for item in results if item['label'] == 'Vår systembruk')['url'],
			reverse('all_bruk_for_virksomhet', kwargs={'pk': 42}),
		)

	def test_anonymous_user_without_open_permissions(self):
		results = match_nav_pages('prioriteringer', AnonymousUser())
		self.assertEqual(results, [])

	def test_open_page_visible_without_special_permissions(self):
		user = _PermUser([])
		results = match_nav_pages('alle virksomheter', user)
		self.assertTrue(results)
		self.assertEqual(results[0]['label'], 'Alle virksomheter')
