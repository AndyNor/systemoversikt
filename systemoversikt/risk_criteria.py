# -*- coding: utf-8 -*-
# Change log:
# 2026-06-30: Konsekvenstype slugs + parse helpers for scenario tagging.
# 2026-06-30: Tiltak status forslag + besluttet (replaces ikke_startet) for Excel import and editor.
# 2026-06-29: effective_residual_levels() – empty etter fields inherit current risk for matrix/label.
# 2026-06-25: parse_kit_dimensjoner() for K/I/T dimension tags in scenario table.
# 2026-06-25: lookup labels for konsekvens/sannsynlighet table cells; 1–5 color scale aligned to risk colors.
# 2026-06-25: level_cell_css_class() for konsekvens/sannsynlighet table cell backgrounds.
# 2026-06-24: meta_choices() for AJAX risk editor dropdowns and matrix preview.
# 2026-06-24: Reference data for security risk module – labels, matrix, akseptkriterier text.

import re
import unicodedata

# 5×5 matrix: RISK_MATRIX[sannsynlighet][konsekvens] -> Lav|Middels|Høy
# From Akseptkriterier sheet rows 33–37 (sannsynlighet 5..1, konsekvens 1..5).
RISK_MATRIX = {
	5: {1: 'Middels', 2: 'Middels', 3: 'Høy', 4: 'Høy', 5: 'Høy'},
	4: {1: 'Lav', 2: 'Middels', 3: 'Middels', 4: 'Høy', 5: 'Høy'},
	3: {1: 'Lav', 2: 'Middels', 3: 'Middels', 4: 'Høy', 5: 'Høy'},
	2: {1: 'Lav', 2: 'Lav', 3: 'Middels', 4: 'Middels', 5: 'Høy'},
	1: {1: 'Lav', 2: 'Lav', 3: 'Middels', 4: 'Middels', 5: 'Middels'},
}

KONSEKVENS_LABELS = {
	1: 'Ubetydelig',
	2: 'Lav',
	3: 'Moderat',
	4: 'Alvorlig',
	5: 'Svært alvorlig',
}

SANNSYNLIGHET_LABELS = {
	1: 'Meget liten',
	2: 'Liten',
	3: 'Moderat',
	4: 'Stor',
	5: 'Svært stor',
}

RISIKOBEHANDLING_MAP = {
	'godta': 'Godta/Akseptere',
	'redusere': 'Redusere',
	'dele': 'Dele/Overføre',
	'unnga': 'Unngå',
}

RISIKOBEHANDLING_FROM_TEXT = {
	'godta/akseptere': 'godta',
	'godta': 'godta',
	'akseptere': 'godta',
	'redusere': 'redusere',
	'dele/overføre': 'dele',
	'dele': 'dele',
	'overføre': 'dele',
	'unngå': 'unnga',
	'unnga': 'unnga',
}

TILTAK_STATUS_FROM_TEXT = {
	'forslag': 'forslag',
	'besluttet': 'besluttet',
	'ikke startet': 'besluttet',
	'under arbeid': 'under_arbeid',
	'utført': 'utfort',
	'utfort': 'utfort',
}

# Konsekvens dimension descriptions (Akseptkriterier konsekvensmatrise).
KONSEKVENS_DIMENSJONER = [
	'Liv og helse',
	'Økonomi',
	'Tillit',
	'Etterlevelse av lover og regler',
	'Måloppnåelse',
]

KONSEKVENSTYPE_VALG = (
	('liv_helse', 'Liv og helse'),
	('okonomi', 'Økonomi'),
	('tillit', 'Tillit'),
	('etterlevelse', 'Etterlevelse av lover og regler'),
	('maaloppnaelse', 'Måloppnåelse'),
)
KONSEKVENSTYPE_SLUGS = {slug for slug, _ in KONSEKVENSTYPE_VALG}
KONSEKVENSTYPE_LABELS = dict(KONSEKVENSTYPE_VALG)
KONSEKVENSTYPE_ORDER = [slug for slug, _ in KONSEKVENSTYPE_VALG]

KONSEKVENS_BESKRIVELSER = {
	5: [
		'Dødsfall eller flere personer rammes av alvorlig varig funksjons-nedsettelse eller skade.',
		'Tap/skade på over 5 mill kroner for virksomheten',
		'Langvarige og svært negative oppslag i riksdekkende media.',
		'Kan medføre eller bidra til alvorlig brudd på lov, forskrift eller annet regelverk.',
		'Manglende oppnåelse av kritiske mål i virksomheten.',
	],
	4: [
		'Alvorlig personskade eller varig funksjons-nedsettelse.',
		'Tap/skade mellom kr 1 og 5 mill for virksomheten',
		'Negative oppslag i riksdekkende media over flere dager.',
		'Kan medføre eller bidra til brudd på lov, forskrift eller annet regelverk.',
		'Manglende oppnåelse av mindre kritiske mål i virksomheten.',
	],
	3: [
		'Mindre alvorlig personskade',
		'Tap/skade mellom kr 250.000 til 1 mill for virksomheten',
		'Mindre eller kortvarige oppslag i media.',
		'Kan medføre eller bidra til mindre alvorlige brudd på lov, forskrift eller annet regelverk.',
		'Moderat innvirkning på oppnåelse av virksomhetens mål.',
	],
	2: [
		'Småskader',
		'Tap/skade mellom kr 50.000 og 250.000 for virksomheten',
		'Henvendelse fra media uten negative oppslag.',
		'Kan medføre brudd på intern instruks eller reglement.',
		'Liten innvirkning på oppnåelse av virksomhetens mål.',
	],
	1: [
		'Ingen skade',
		'Tap/skade på mindre enn 50.000 kroner for virksomheten',
		'Ubetydelig påvirkning fra media.',
		'Påvirker ikke etterlevelse',
		'Ubetydelig innvirkning på oppnåelse av virksomhetens mål.',
	],
}

SANNSYNLIGHET_BESKRIVELSER = {
	5: {
		'forventning': 'Forventes å inntreffe tilnærmet ukentlig.',
		'estimert': 'Hendelsen vil oppstå under de fleste omstendigheter (inntreffer med over 70 % sannsynlighet)',
		'sarbarhet': 'Sikkerhetstiltak er ikke etablert eller fungerer ikke etter hensikten',
		'kapasitet': 'Sikkerhetstiltak kan omgås eller brytes med små til normale ressurser uten kjennskap til tiltakene',
		'intensjon': 'Ubetenksomhet eller uhell',
	},
	4: {
		'forventning': 'Forventes å inntreffe tilnærmet månedlig.',
		'estimert': 'Hendelsen kan oppstå under flere omstendigheter (30–70 % sannsynlighet)',
		'sarbarhet': 'Sikkerhetstiltak er i noen grad etablert eller usikkert om de fungerer',
		'kapasitet': 'Kan brytes med små til normale ressurser',
		'intensjon': 'Ubetenksomhet eller bevisst brudd (eksterne)',
	},
	3: {
		'forventning': 'Forventes å inntreffe minst kvartalsvis.',
		'estimert': 'Hendelsen kan oppstå under noen omstendigheter (10–30 % sannsynlighet)',
		'sarbarhet': 'Sikkerhetstiltak er delvis etablert og fungerer delvis',
		'kapasitet': 'Kan brytes med normal til gode ressurser og noe kjennskap',
		'intensjon': 'Bevisst brudd av egne medarbeidere eller planlagt brudd eksternt',
	},
	2: {
		'forventning': 'Forventes å inntreffe årlig.',
		'estimert': 'Sjeldne omstendigheter (5–10 % sannsynlighet)',
		'sarbarhet': 'Sikkerhetstiltak er etablert etter sikkerhetsbehovet og fungerer',
		'kapasitet': 'Kan brytes med gode ressurser og kjennskap til tiltakene',
		'intensjon': 'Bevisst brudd, planlegging over lengre tid (eksterne)',
	},
	1: {
		'forventning': 'Forventes å finne sted sjeldnere enn en gang pr år.',
		'estimert': 'Kun under helt spesielle omstendigheter (under 5 % sannsynlighet)',
		'sarbarhet': 'Sikkerhetstiltak etablert og kontrolleres',
		'kapasitet': 'Kan kun brytes med gode ressurser og fullstendig kjennskap',
		'intensjon': 'Planlagt og bevisst brudd av egne medarbeidere',
	},
}

_LABEL_ALIASES = {
	# Konsekvens
	'ubetydelig': (1, 'konsekvens'),
	'lav': (2, 'konsekvens'),
	'moderat': (3, 'konsekvens'),
	'alvorlig': (4, 'konsekvens'),
	'svært alvorlig': (5, 'konsekvens'),
	'svaert alvorlig': (5, 'konsekvens'),
	# Sannsynlighet
	'meget liten': (1, 'sannsynlighet'),
	'meget liten.': (1, 'sannsynlighet'),
	'liten': (2, 'sannsynlighet'),
	'stor': (4, 'sannsynlighet'),
	'svært stor': (5, 'sannsynlighet'),
	'svaert stor': (5, 'sannsynlighet'),
}


def _normalize_label(text):
	if text is None:
		return ''
	s = str(text).strip().lower()
	s = s.replace('\n', ' ')
	s = unicodedata.normalize('NFKD', s)
	s = ''.join(c for c in s if not unicodedata.combining(c))
	s = re.sub(r'\s+', ' ', s)
	return s


def label_to_level(text, kind=None):
	"""Map Excel label to 1–5. kind: 'konsekvens' or 'sannsynlighet' (optional disambiguator)."""
	norm = _normalize_label(text)
	if not norm:
		return None
	if norm in _LABEL_ALIASES:
		level, alias_kind = _LABEL_ALIASES[norm]
		if kind and alias_kind != kind:
			# 'lav' and 'liten' overlap – use kind hint
			if kind == 'konsekvens' and norm == 'lav':
				return 2
			if kind == 'sannsynlighet' and norm == 'liten':
				return 2
			if kind == 'konsekvens' and norm == 'moderat':
				return 3
			if kind == 'sannsynlighet' and norm == 'moderat':
				return 3
		return level
	# Fallback: partial match on longer phrases
	for alias, (level, alias_kind) in sorted(_LABEL_ALIASES.items(), key=lambda x: -len(x[0])):
		if alias in norm or norm in alias:
			if kind and alias_kind != kind:
				continue
			return level
	return None


def risikobehandling_from_text(text):
	if not text:
		return ''
	return RISIKOBEHANDLING_FROM_TEXT.get(_normalize_label(text), '')


def tiltak_status_from_text(text):
	if not text:
		return 'besluttet'
	return TILTAK_STATUS_FROM_TEXT.get(_normalize_label(text), 'besluttet')


def risk_label(sannsynlighet, konsekvens):
	if not sannsynlighet or not konsekvens:
		return ''
	try:
		s = int(sannsynlighet)
		k = int(konsekvens)
	except (TypeError, ValueError):
		return ''
	if s not in RISK_MATRIX or k not in RISK_MATRIX[s]:
		return ''
	return RISK_MATRIX[s][k]


def risk_cell_css_class(label):
	"""Bootstrap-friendly cell background class for matrix cells."""
	if label == 'Lav':
		return 'risk-cell-lav'
	if label == 'Middels':
		return 'risk-cell-middels'
	if label == 'Høy':
		return 'risk-cell-hoy'
	return 'risk-cell-empty'


# 2026-06-25: Level 1–5 and Lav/Middels/Høy background hex scale (scope detail CSS).
RISK_LEVEL_BACKGROUNDS = {
	1: '#c0eb96',
	2: '#e4f5ad',
	3: '#ffecb2',
	4: '#ffd997',
	5: '#ffc8cd',
}

RISK_LABEL_BACKGROUNDS = {
	'Lav': RISK_LEVEL_BACKGROUNDS[1],
	'Middels': RISK_LEVEL_BACKGROUNDS[3],
	'Høy': RISK_LEVEL_BACKGROUNDS[5],
}


def level_cell_css_class(level):
	"""Background class for konsekvens/sannsynlighet level cells (1–5)."""
	if level is None or level == '':
		return 'risk-cell-empty'
	try:
		n = int(level)
	except (TypeError, ValueError):
		return 'risk-cell-empty'
	if 1 <= n <= 5:
		return 'risk-level-%d' % n
	return 'risk-cell-empty'


def konsekvens_lookup_label(level):
	return _lookup_level_label(level, KONSEKVENS_LABELS)


def sannsynlighet_lookup_label(level):
	return _lookup_level_label(level, SANNSYNLIGHET_LABELS)


def _lookup_level_label(level, labels):
	if level is None or level == '':
		return ''
	try:
		n = int(level)
	except (TypeError, ValueError):
		return ''
	return labels.get(n, '')


def parse_kit_dimensjoner(text):
	"""Parse K/I/T text (e.g. 'K, T') into ordered dimension codes."""
	if not text or not str(text).strip():
		return []
	seen = set()
	result = []
	for code in re.findall(r'[KIT]', str(text).upper()):
		if code not in seen:
			seen.add(code)
			result.append(code)
	return result


def parse_konsekvenstyper(raw):
	"""Parse stored comma-string or API list into ordered konsekvenstype slugs."""
	if raw is None:
		return []
	if isinstance(raw, (list, tuple)):
		parts = [str(item).strip() for item in raw if str(item).strip()]
	elif isinstance(raw, str):
		parts = [part.strip() for part in raw.split(',') if part.strip()]
	else:
		parts = [str(raw).strip()] if str(raw).strip() else []
	seen = set()
	result = []
	for slug in parts:
		if slug in KONSEKVENSTYPE_SLUGS and slug not in seen:
			seen.add(slug)
			result.append(slug)
	# Stable display order regardless of input order
	order = {slug: index for index, slug in enumerate(KONSEKVENSTYPE_ORDER)}
	result.sort(key=lambda slug: order.get(slug, 99))
	return result


def konsekvenstype_to_storage(raw):
	"""Normalize API input to comma-separated slug string for DB."""
	return ','.join(parse_konsekvenstyper(raw))


def konsekvenstype_tag_dicts(raw):
	"""List of {slug, label} for API/template display."""
	return [
		{'slug': slug, 'label': KONSEKVENSTYPE_LABELS[slug]}
		for slug in parse_konsekvenstyper(raw)
	]


def effective_residual_levels(scenario):
	"""Residual konsekvens/sannsynlighet; unset etter fields inherit current risk."""
	k = scenario.konsekvens_etter or scenario.konsekvens_nivaa
	s = scenario.sannsynlighet_etter or scenario.sannsynlighet_nivaa
	return s, k


def matrix_placements(scenarios, use_residual=False):
	"""Group scenarios by (sannsynlighet, konsekvens) for matrix rendering."""
	cells = {}
	for scenario in scenarios:
		if use_residual:
			s, k = effective_residual_levels(scenario)
		else:
			s, k = scenario.sannsynlighet_nivaa, scenario.konsekvens_nivaa
		if not s or not k:
			continue
		key = (int(s), int(k))
		cells.setdefault(key, []).append(scenario)
	return cells


def meta_choices():
	"""Reference data for risk editor UI (dropdowns and live matrix lookup)."""
	from systemoversikt.models import RISIKOBEHANDLING_VALG, RISK_ACTION_STATUS_VALG
	return {
		'konsekvens_labels': KONSEKVENS_LABELS,
		'sannsynlighet_labels': SANNSYNLIGHET_LABELS,
		'risk_matrix': RISK_MATRIX,
		'risikobehandling': [{'value': v, 'label': l} for v, l in RISIKOBEHANDLING_VALG],
		'tiltak_status': [{'value': v, 'label': l} for v, l in RISK_ACTION_STATUS_VALG],
		'konsekvenstyper': [{'value': v, 'label': l} for v, l in KONSEKVENSTYPE_VALG],
	}
