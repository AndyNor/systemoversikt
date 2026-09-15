# -*- coding: utf-8 -*-
# Change log:
# 2026-09-15: OKA kode parse/normalize – parent is inferred from kode, not Excel Overliggende.

"""Parse Oslo kommune archive classification (OKA) codes.

Display form in the sheet is like ``A1 - 01``. Parent is not taken from the
Overliggende column (it is unreliable). Hierarchy:

* ``A`` → hovedfunksjon
* ``A1`` → funksjon, parent ``A``
* ``A1 - 01`` → underfunksjon, parent ``A1``
"""
import re

NIVAA_HOVED = 'hovedfunksjon'
NIVAA_FUNKSJON = 'funksjon'
NIVAA_UNDER = 'underfunksjon'

# Keep a single space around the hyphen in display/normalized form.
_HYPHEN_SPACES = re.compile(r'\s*-\s*')
_FUNKSJON = re.compile(r'^([A-ZÆØÅ])(\d+)$', re.IGNORECASE)
_UNDER = re.compile(r'^([A-ZÆØÅ]\d+)\s*-\s*(\d+)$', re.IGNORECASE)
_HOVED = re.compile(r'^([A-ZÆØÅ])$', re.IGNORECASE)


def normalize_kode(kode):
	if kode is None:
		return ''
	text = _HYPHEN_SPACES.sub(' - ', str(kode).strip())
	return re.sub(r'\s+', ' ', text)


def nivaa_from_kode(kode):
	normalized = normalize_kode(kode)
	if _UNDER.match(normalized):
		return NIVAA_UNDER
	if _FUNKSJON.match(normalized):
		return NIVAA_FUNKSJON
	if _HOVED.match(normalized):
		return NIVAA_HOVED
	return None


def parent_kode_from_kode(kode):
	normalized = normalize_kode(kode)
	under = _UNDER.match(normalized)
	if under:
		return normalize_kode(under.group(1))
	funksjon = _FUNKSJON.match(normalized)
	if funksjon:
		return normalize_kode(funksjon.group(1))
	return None
