# -*- coding: utf-8 -*-
# Change log:
# 2026-07-07: Sannsynlighetstyper in CriteriaBundle – editable scenario tags (parity with konsekvenstyper).
# 2026-06-30: Sannsynlighetstype slugs + parse helpers – fixed five probability dimensions per scenario.
# 2026-06-30: Global DB-backed CriteriaBundle + get_active_criteria() – editable akseptkriterier.
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

from django.core.cache import cache

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

SANNSYNLIGHET_KEYS = ('forventning', 'estimert', 'sarbarhet', 'kapasitet', 'intensjon')

SANNSYNLIGHETSTYPE_VALG = (
	('forventning', 'Forventning'),
	('estimert', 'Estimert sannsynlighet'),
	('sarbarhet', 'Sårbarhet'),
	('kapasitet', 'Kapasitet og evne'),
	('intensjon', 'Intensjon'),
)
SANNSYNLIGHETSTYPE_SLUGS = {slug for slug, _ in SANNSYNLIGHETSTYPE_VALG}
SANNSYNLIGHETSTYPE_LABELS = dict(SANNSYNLIGHETSTYPE_VALG)
SANNSYNLIGHETSTYPE_ORDER = [slug for slug, _ in SANNSYNLIGHETSTYPE_VALG]

RISK_LEVEL_VALUES = ('Lav', 'Middels', 'Høy')
LEVELS = (1, 2, 3, 4, 5)
CRITERIA_CACHE_KEY = 'risk_criteria_active_v1'


def _default_sannsynlighetstyper():
	return [{'slug': slug, 'label': label} for slug, label in SANNSYNLIGHETSTYPE_VALG]


def _sannsynlighetstype_slugs_from_data(data):
	st = data.get('sannsynlighetstyper') if isinstance(data, dict) else None
	if isinstance(st, list) and len(st) == 5:
		slugs = []
		for item in st:
			if isinstance(item, dict):
				slug = str(item.get('slug') or '').strip()
				if slug:
					slugs.append(slug)
		if len(slugs) == 5:
			return slugs
	return list(SANNSYNLIGHET_KEYS)


def normalize_criteria_dict(data):
	"""Fill missing keys for backward compatibility with older stored/imported criteria."""
	if not isinstance(data, dict):
		return data
	normalized = dict(data)
	if not normalized.get('sannsynlighetstyper'):
		normalized['sannsynlighetstyper'] = _default_sannsynlighetstyper()
	return normalized


def _int_key_dict(raw, label):
	if not isinstance(raw, dict):
		raise ValueError('%s må være et objekt.' % label)
	result = {}
	for key, value in raw.items():
		try:
			n = int(key)
		except (TypeError, ValueError):
			raise ValueError('%s: ugyldig nøkkel %r.' % (label, key))
		result[n] = value
	return result


def build_default_criteria_dict():
	"""Serialize module defaults to JSON-storable dict (string keys)."""
	return {
		'risk_matrix': {
			str(s): {str(k): v for k, v in row.items()}
			for s, row in RISK_MATRIX.items()
		},
		'konsekvens_labels': {str(k): v for k, v in KONSEKVENS_LABELS.items()},
		'sannsynlighet_labels': {str(k): v for k, v in SANNSYNLIGHET_LABELS.items()},
		'konsekvens_dimensjoner': list(KONSEKVENS_DIMENSJONER),
		'konsekvens_beskrivelser': {
			str(level): list(texts) for level, texts in KONSEKVENS_BESKRIVELSER.items()
		},
		'sannsynlighet_beskrivelser': {
			str(level): dict(desc) for level, desc in SANNSYNLIGHET_BESKRIVELSER.items()
		},
		'konsekvenstyper': [
			{'slug': slug, 'label': label} for slug, label in KONSEKVENSTYPE_VALG
		],
		'sannsynlighetstyper': [
			{'slug': slug, 'label': label} for slug, label in SANNSYNLIGHETSTYPE_VALG
		],
	}


def validate_criteria(data):
	"""Return list of human-readable validation errors (empty if valid)."""
	errors = []
	if not isinstance(data, dict):
		return ['Kriterier må være et objekt.']

	try:
		matrix_raw = data.get('risk_matrix')
		if not isinstance(matrix_raw, dict):
			errors.append('Risikomatrise mangler.')
		else:
			matrix = _int_key_dict(matrix_raw, 'Risikomatrise')
			for s in LEVELS:
				if s not in matrix:
					errors.append('Risikomatrise mangler sannsynlighet %d.' % s)
					continue
				row = matrix[s]
				if not isinstance(row, dict):
					errors.append('Risikomatrise rad %d er ugyldig.' % s)
					continue
				row_int = _int_key_dict(row, 'Risikomatrise rad %d' % s)
				for k in LEVELS:
					val = row_int.get(k)
					if val not in RISK_LEVEL_VALUES:
						errors.append('Risikomatrise [%d][%d] må være Lav, Middels eller Høy.' % (s, k))

		for field, label in (
			('konsekvens_labels', 'Konsekvensetiketter'),
			('sannsynlighet_labels', 'Sannsynlighetsetiketter'),
		):
			raw = data.get(field)
			if not isinstance(raw, dict):
				errors.append('%s mangler.' % label)
				continue
			labels = _int_key_dict(raw, label)
			for level in LEVELS:
				text = (labels.get(level) or '').strip()
				if not text:
					errors.append('%s nivå %d kan ikke være tom.' % (label, level))

		dims = data.get('konsekvens_dimensjoner')
		if not isinstance(dims, list) or len(dims) != 5:
			errors.append('Konsekvensdimensjoner må være en liste med 5 elementer.')
		else:
			for index, name in enumerate(dims):
				if not str(name).strip():
					errors.append('Konsekvensdimensjon %d kan ikke være tom.' % (index + 1))

		kb = data.get('konsekvens_beskrivelser')
		if not isinstance(kb, dict):
			errors.append('Konsekvensbeskrivelser mangler.')
		else:
			kb_int = _int_key_dict(kb, 'Konsekvensbeskrivelser')
			for level in LEVELS:
				texts = kb_int.get(level)
				if not isinstance(texts, list) or len(texts) != 5:
					errors.append('Konsekvensbeskrivelser nivå %d må ha 5 tekster.' % level)
				else:
					for index, text in enumerate(texts):
						if not str(text).strip():
							errors.append('Konsekvensbeskrivelse nivå %d dimensjon %d kan ikke være tom.' % (level, index + 1))

		sb = data.get('sannsynlighet_beskrivelser')
		if not isinstance(sb, dict):
			errors.append('Sannsynlighetsbeskrivelser mangler.')
		else:
			sb_int = _int_key_dict(sb, 'Sannsynlighetsbeskrivelser')
			sannsynlighet_keys = _sannsynlighetstype_slugs_from_data(data)
			for level in LEVELS:
				desc = sb_int.get(level)
				if not isinstance(desc, dict):
					errors.append('Sannsynlighetsbeskrivelser nivå %d mangler.' % level)
					continue
				for key in sannsynlighet_keys:
					if not str(desc.get(key) or '').strip():
						errors.append('Sannsynlighet nivå %d: %s kan ikke være tom.' % (level, key))

		kt = data.get('konsekvenstyper')
		if not isinstance(kt, list) or len(kt) != 5:
			errors.append('Konsekvenstyper må være en liste med 5 elementer.')
		else:
			slugs = []
			for index, item in enumerate(kt):
				if not isinstance(item, dict):
					errors.append('Konsekvenstype %d er ugyldig.' % (index + 1))
					continue
				slug = str(item.get('slug') or '').strip()
				label = str(item.get('label') or '').strip()
				if not slug or not re.match(r'^[a-z][a-z0-9_]*$', slug):
					errors.append('Konsekvenstype %d har ugyldig slug.' % (index + 1))
				if not label:
					errors.append('Konsekvenstype %d mangler etikett.' % (index + 1))
				slugs.append(slug)
			if len(set(slugs)) != len(slugs):
				errors.append('Konsekvenstype-slugs må være unike.')

		st = data.get('sannsynlighetstyper')
		if not isinstance(st, list) or len(st) != 5:
			errors.append('Sannsynlighetstyper må være en liste med 5 elementer.')
		else:
			slugs = []
			for index, item in enumerate(st):
				if not isinstance(item, dict):
					errors.append('Sannsynlighetstype %d er ugyldig.' % (index + 1))
					continue
				slug = str(item.get('slug') or '').strip()
				label = str(item.get('label') or '').strip()
				if not slug or not re.match(r'^[a-z][a-z0-9_]*$', slug):
					errors.append('Sannsynlighetstype %d har ugyldig slug.' % (index + 1))
				if not label:
					errors.append('Sannsynlighetstype %d mangler etikett.' % (index + 1))
				slugs.append(slug)
			if len(set(slugs)) != len(slugs):
				errors.append('Sannsynlighetstype-slugs må være unike.')
	except ValueError as exc:
		errors.append(str(exc))

	return errors


class CriteriaBundle:
	"""Runtime view of validated acceptance criteria."""

	def __init__(self, data):
		errors = validate_criteria(data)
		if errors:
			raise ValueError(errors[0])
		self._data = data
		self.risk_matrix = {}
		matrix_src = data['risk_matrix']
		for s in LEVELS:
			row_src = matrix_src.get(str(s), matrix_src.get(s))
			self.risk_matrix[s] = _int_key_dict(row_src, 'matrix')

		self.konsekvens_labels = _int_key_dict(data['konsekvens_labels'], 'konsekvens_labels')
		self.sannsynlighet_labels = _int_key_dict(data['sannsynlighet_labels'], 'sannsynlighet_labels')
		self.konsekvens_dimensjoner = list(data['konsekvens_dimensjoner'])
		kb = _int_key_dict(data['konsekvens_beskrivelser'], 'konsekvens_beskrivelser')
		self.konsekvens_beskrivelser = {level: list(kb[level]) for level in LEVELS}
		sb = _int_key_dict(data['sannsynlighet_beskrivelser'], 'sannsynlighet_beskrivelser')
		self.sannsynlighet_beskrivelser = {level: dict(sb[level]) for level in LEVELS}
		self.konsekvenstyper = list(data['konsekvenstyper'])
		self.konsekvenstype_slugs = {item['slug'] for item in self.konsekvenstyper}
		self.konsekvenstype_labels = {item['slug']: item['label'] for item in self.konsekvenstyper}
		self.konsekvenstype_order = [item['slug'] for item in self.konsekvenstyper]
		self.sannsynlighetstyper = list(data['sannsynlighetstyper'])
		self.sannsynlighetstype_slugs = {item['slug'] for item in self.sannsynlighetstyper}
		self.sannsynlighetstype_labels = {item['slug']: item['label'] for item in self.sannsynlighetstyper}
		self.sannsynlighetstype_order = [item['slug'] for item in self.sannsynlighetstyper]
		self._label_aliases = self._build_label_aliases()

	@classmethod
	def from_defaults(cls):
		return cls(build_default_criteria_dict())

	@classmethod
	def from_dict(cls, data):
		return cls(normalize_criteria_dict(data))

	def to_storage_dict(self):
		"""JSON-serializable dict with string keys."""
		return {
			'risk_matrix': {
				str(s): {str(k): self.risk_matrix[s][k] for k in LEVELS}
				for s in LEVELS
			},
			'konsekvens_labels': {str(k): v for k, v in self.konsekvens_labels.items()},
			'sannsynlighet_labels': {str(k): v for k, v in self.sannsynlighet_labels.items()},
			'konsekvens_dimensjoner': list(self.konsekvens_dimensjoner),
			'konsekvens_beskrivelser': {
				str(level): list(self.konsekvens_beskrivelser[level]) for level in LEVELS
			},
			'sannsynlighet_beskrivelser': {
				str(level): dict(self.sannsynlighet_beskrivelser[level]) for level in LEVELS
			},
			'konsekvenstyper': [
				{'slug': item['slug'], 'label': item['label']} for item in self.konsekvenstyper
			],
			'sannsynlighetstyper': [
				{'slug': item['slug'], 'label': item['label']} for item in self.sannsynlighetstyper
			],
		}

	def _build_label_aliases(self):
		aliases = {}
		for level, label in self.konsekvens_labels.items():
			norm = _normalize_label(label)
			if norm:
				aliases[norm] = (level, 'konsekvens')
		for level, label in self.sannsynlighet_labels.items():
			norm = _normalize_label(label)
			if norm:
				aliases[norm] = (level, 'sannsynlighet')
		# Disambiguation for overlapping words
		aliases['lav'] = (2, 'konsekvens')
		aliases['liten'] = (2, 'sannsynlighet')
		aliases['moderat'] = (3, 'konsekvens')
		for level, label in self.sannsynlighet_labels.items():
			if _normalize_label(label) == 'moderat':
				aliases['moderat'] = (level, 'sannsynlighet')
				break
		return aliases

	def label_to_level(self, text, kind=None):
		norm = _normalize_label(text)
		if not norm:
			return None
		if norm in self._label_aliases:
			level, alias_kind = self._label_aliases[norm]
			if kind and alias_kind != kind:
				if kind == 'konsekvens' and norm == 'lav':
					return 2
				if kind == 'sannsynlighet' and norm == 'liten':
					return 2
				if kind == 'konsekvens' and norm == 'moderat':
					return 3
				if kind == 'sannsynlighet' and norm == 'moderat':
					return 3
			return level
		for alias, (level, alias_kind) in sorted(self._label_aliases.items(), key=lambda x: -len(x[0])):
			if alias in norm or norm in alias:
				if kind and alias_kind != kind:
					continue
				return level
		return None

	def risk_label(self, sannsynlighet, konsekvens):
		if not sannsynlighet or not konsekvens:
			return ''
		try:
			s = int(sannsynlighet)
			k = int(konsekvens)
		except (TypeError, ValueError):
			return ''
		row = self.risk_matrix.get(s)
		if not row:
			return ''
		return row.get(k, '')

	def konsekvens_lookup_label(self, level):
		return _lookup_level_label(level, self.konsekvens_labels)

	def sannsynlighet_lookup_label(self, level):
		return _lookup_level_label(level, self.sannsynlighet_labels)

	def parse_konsekvenstyper(self, raw):
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
			if slug in self.konsekvenstype_slugs and slug not in seen:
				seen.add(slug)
				result.append(slug)
		order = {slug: index for index, slug in enumerate(self.konsekvenstype_order)}
		result.sort(key=lambda slug: order.get(slug, 99))
		return result

	def konsekvenstype_to_storage(self, raw):
		return ','.join(self.parse_konsekvenstyper(raw))

	def konsekvenstype_tag_dicts(self, raw):
		return [
			{'slug': slug, 'label': self.konsekvenstype_labels[slug]}
			for slug in self.parse_konsekvenstyper(raw)
		]

	def parse_sannsynlighetstyper(self, raw):
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
			if slug in self.sannsynlighetstype_slugs and slug not in seen:
				seen.add(slug)
				result.append(slug)
		order = {slug: index for index, slug in enumerate(self.sannsynlighetstype_order)}
		result.sort(key=lambda slug: order.get(slug, 99))
		return result

	def sannsynlighetstype_to_storage(self, raw):
		return ','.join(self.parse_sannsynlighetstyper(raw))

	def sannsynlighetstype_tag_dicts(self, raw):
		return [
			{'slug': slug, 'label': self.sannsynlighetstype_labels[slug]}
			for slug in self.parse_sannsynlighetstyper(raw)
		]

	def build_akseptkriterier_context(self):
		konsekvens_rows = []
		for level in range(5, 0, -1):
			konsekvens_rows.append({
				'level': level,
				'label': self.konsekvens_labels[level],
				'level_css': level_cell_css_class(level),
				'dimensjoner': [
					{'navn': navn, 'tekst': tekst}
					for navn, tekst in zip(self.konsekvens_dimensjoner, self.konsekvens_beskrivelser[level])
				],
			})
		sannsynlighet_rows = []
		for level in range(5, 0, -1):
			sannsynlighet_rows.append({
				'level': level,
				'label': self.sannsynlighet_labels[level],
				'level_css': level_cell_css_class(level),
				'beskrivelser': [
					{
						'slug': item['slug'],
						'label': item['label'],
						'tekst': self.sannsynlighet_beskrivelser[level].get(item['slug'], ''),
					}
					for item in self.sannsynlighetstyper
				],
			})
		return {
			'konsekvens_rows': konsekvens_rows,
			'sannsynlighet_rows': sannsynlighet_rows,
		}

	def build_matrix_reference_context(self):
		grid = []
		for sannsynlighet in range(5, 0, -1):
			row_cells = []
			for konsekvens in range(1, 6):
				label = self.risk_label(sannsynlighet, konsekvens)
				row_cells.append({
					'sannsynlighet': sannsynlighet,
					'konsekvens': konsekvens,
					'label': label,
					'css_class': risk_cell_css_class(label),
				})
			grid.append({
				'sannsynlighet': sannsynlighet,
				'sannsynlighet_label': self.sannsynlighet_labels[sannsynlighet],
				'cells': row_cells,
			})
		return grid

	def build_matrix_context(self, scenarios, use_residual=False):
		cells = matrix_placements(scenarios, use_residual=use_residual, criteria=self)
		grid = []
		for sannsynlighet in range(5, 0, -1):
			row_cells = []
			for konsekvens in range(1, 6):
				label = self.risk_label(sannsynlighet, konsekvens)
				row_cells.append({
					'sannsynlighet': sannsynlighet,
					'konsekvens': konsekvens,
					'label': label,
					'css_class': risk_cell_css_class(label),
					'scenarios': cells.get((sannsynlighet, konsekvens), []),
				})
			grid.append({
				'sannsynlighet': sannsynlighet,
				'sannsynlighet_label': self.sannsynlighet_labels[sannsynlighet],
				'cells': row_cells,
			})
		return grid

	def meta_choices(self):
		from systemoversikt.models import RISIKOBEHANDLING_VALG, RISK_ACTION_STATUS_VALG
		return {
			'konsekvens_labels': self.konsekvens_labels,
			'sannsynlighet_labels': self.sannsynlighet_labels,
			'risk_matrix': self.risk_matrix,
			'risikobehandling': [{'value': v, 'label': l} for v, l in RISIKOBEHANDLING_VALG],
			'tiltak_status': [{'value': v, 'label': l} for v, l in RISK_ACTION_STATUS_VALG],
			'konsekvenstyper': [
				{'value': item['slug'], 'label': item['label']} for item in self.konsekvenstyper
			],
			'sannsynlighetstyper': [
				{'value': item['slug'], 'label': item['label']} for item in self.sannsynlighetstyper
			],
		}


def invalidate_criteria_cache():
	cache.delete(CRITERIA_CACHE_KEY)


def get_active_criteria():
	cached = cache.get(CRITERIA_CACHE_KEY)
	if cached is not None:
		return cached
	try:
		from systemoversikt.models import RiskCriteriaConfig
		row = RiskCriteriaConfig.objects.filter(is_active=True).first()
		if row and row.criteria:
			bundle = CriteriaBundle.from_dict(row.criteria)
		else:
			bundle = CriteriaBundle.from_defaults()
	except Exception:
		bundle = CriteriaBundle.from_defaults()
	cache.set(CRITERIA_CACHE_KEY, bundle, timeout=3600)
	return bundle


def get_or_create_active_config(user=None):
	from systemoversikt.models import RiskCriteriaConfig
	row = RiskCriteriaConfig.objects.filter(is_active=True).first()
	if row:
		return row
	defaults = build_default_criteria_dict()
	return RiskCriteriaConfig.objects.create(
		title='Standard akseptkriterier',
		is_active=True,
		criteria=defaults,
		oppdatert_av=user,
	)


def criteria_from_post(post):
	"""Build criteria dict from superuser edit form POST data."""
	data = {
		'risk_matrix': {},
		'konsekvens_labels': {},
		'sannsynlighet_labels': {},
		'konsekvens_dimensjoner': [],
		'konsekvens_beskrivelser': {},
		'sannsynlighet_beskrivelser': {},
		'konsekvenstyper': [],
		'sannsynlighetstyper': [],
	}
	for s in LEVELS:
		row = {}
		for k in LEVELS:
			row[str(k)] = (post.get('matrix_%d_%d' % (s, k)) or '').strip()
		data['risk_matrix'][str(s)] = row
	for level in LEVELS:
		data['konsekvens_labels'][str(level)] = (post.get('konsekvens_label_%d' % level) or '').strip()
		data['sannsynlighet_labels'][str(level)] = (post.get('sannsynlighet_label_%d' % level) or '').strip()
	for index in range(5):
		data['konsekvens_dimensjoner'].append((post.get('konsekvens_dim_%d' % index) or '').strip())
	for level in LEVELS:
		data['konsekvens_beskrivelser'][str(level)] = [
			(post.get('konsekvens_besk_%d_%d' % (level, dim)) or '').strip()
			for dim in range(5)
		]
	for index in range(5):
		data['sannsynlighetstyper'].append({
			'slug': (post.get('sannsynlighetstype_slug_%d' % index) or '').strip(),
			'label': (post.get('sannsynlighetstype_label_%d' % index) or '').strip(),
		})
	for level in LEVELS:
		data['sannsynlighet_beskrivelser'][str(level)] = {
			item['slug']: (post.get('sannsynlighet_%d_%s' % (level, item['slug'])) or '').strip()
			for item in data['sannsynlighetstyper']
		}
	for index in range(5):
		data['konsekvenstyper'].append({
			'slug': (post.get('konsekvenstype_slug_%d' % index) or '').strip(),
			'label': (post.get('konsekvenstype_label_%d' % index) or '').strip(),
		})
	return data


def validate_slug_changes(old_bundle, new_data):
	"""Block removal/rename of konsekvenstype/sannsynlighetstype slugs still referenced in scenarios."""
	errors = []
	try:
		new_bundle = CriteriaBundle.from_dict(new_data)
	except ValueError as exc:
		return [str(exc)]
	from systemoversikt.models import RiskScenario

	def _blocked_removed(old_slugs, new_slugs, parse_fn, storage_field, label):
		removed = old_slugs - new_slugs
		if not removed:
			return []
		used = set()
		for raw in RiskScenario.objects.exclude(**{storage_field: ''}).values_list(storage_field, flat=True):
			used.update(parse_fn(raw))
		blocked = sorted(removed & used)
		if blocked:
			return ['Kan ikke fjerne %s som er i bruk: %s' % (label, ', '.join(blocked))]
		return []

	errors.extend(_blocked_removed(
		old_bundle.konsekvenstype_slugs,
		new_bundle.konsekvenstype_slugs,
		old_bundle.parse_konsekvenstyper,
		'konsekvenstyper',
		'konsekvenstyper',
	))
	errors.extend(_blocked_removed(
		old_bundle.sannsynlighetstype_slugs,
		new_bundle.sannsynlighetstype_slugs,
		old_bundle.parse_sannsynlighetstyper,
		'sannsynlighetstyper',
		'sannsynlighetstyper',
	))
	return errors


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
	return get_active_criteria().label_to_level(text, kind=kind)


def risikobehandling_from_text(text):
	if not text:
		return ''
	return RISIKOBEHANDLING_FROM_TEXT.get(_normalize_label(text), '')


def tiltak_status_from_text(text):
	if not text:
		return 'besluttet'
	return TILTAK_STATUS_FROM_TEXT.get(_normalize_label(text), 'besluttet')


def risk_label(sannsynlighet, konsekvens):
	return get_active_criteria().risk_label(sannsynlighet, konsekvens)


def risk_cell_css_class(label):
	"""Bootstrap-friendly cell background class for matrix cells."""
	if label == 'Lav':
		return 'risk-cell-lav'
	if label == 'Middels':
		return 'risk-cell-middels'
	if label == 'Høy':
		return 'risk-cell-hoy'
	return 'risk-cell-empty'


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
	return get_active_criteria().konsekvens_lookup_label(level)


def sannsynlighet_lookup_label(level):
	return get_active_criteria().sannsynlighet_lookup_label(level)


def _lookup_level_label(level, labels):
	if level is None or level == '':
		return ''
	try:
		n = int(level)
	except (TypeError, ValueError):
		return ''
	return labels.get(n, '')


def parse_kit_dimensjoner(text):
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
	return get_active_criteria().parse_konsekvenstyper(raw)


def konsekvenstype_to_storage(raw):
	return get_active_criteria().konsekvenstype_to_storage(raw)


def konsekvenstype_tag_dicts(raw):
	return get_active_criteria().konsekvenstype_tag_dicts(raw)


def parse_sannsynlighetstyper(raw):
	return get_active_criteria().parse_sannsynlighetstyper(raw)


def sannsynlighetstype_to_storage(raw):
	return get_active_criteria().sannsynlighetstype_to_storage(raw)


def sannsynlighetstype_tag_dicts(raw):
	return get_active_criteria().sannsynlighetstype_tag_dicts(raw)


def effective_residual_levels(scenario):
	k = scenario.konsekvens_etter or scenario.konsekvens_nivaa
	s = scenario.sannsynlighet_etter or scenario.sannsynlighet_nivaa
	return s, k


def matrix_placements(scenarios, use_residual=False, criteria=None):
	if criteria is None:
		criteria = get_active_criteria()
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
	return get_active_criteria().meta_choices()
