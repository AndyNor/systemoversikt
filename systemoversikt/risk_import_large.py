# -*- coding: utf-8 -*-
# Change log:
# 2026-07-08: Forside values may appear on rows below header (not only same row).
# 2026-07-08: Forside scan bounded to rows 1–33 and columns C–P.
# 2026-07-08: Collect verdi(er) from all 10 block rows (D may be on any line).
# 2026-07-08: Large «risikovurderingsverktøy» Excel import – Risikovurdering 10-row blocks.

from datetime import date, datetime

from django.db import transaction
from openpyxl.utils import column_index_from_string

from systemoversikt.models import RiskAction, RiskScenario
from systemoversikt.risk_criteria import get_active_criteria
from systemoversikt.risk_import import (
	ImportResult,
	_coerce_level,
	_is_placeholder_tiltak,
	_title_from_filename,
)
from systemoversikt.risk_membership import create_risk_scope

DATA_START_ROW = 5
BLOCK_SIZE = 10

_COL = {
	'risk_id': column_index_from_string('B'),
	'scenario': column_index_from_string('C'),
	'verdi': column_index_from_string('D'),
	'kit': column_index_from_string('E'),
	'trussel': column_index_from_string('G'),
	'trusselnivaa': column_index_from_string('H'),
	'sarbarhet': column_index_from_string('I'),
	'eks_tiltak': column_index_from_string('O'),
	'kons_begrunnelse': column_index_from_string('Q'),
	'konsekvens': column_index_from_string('R'),
	'sanns_begrunnelse': column_index_from_string('S'),
	'sannsynlighet': column_index_from_string('T'),
	'tiltak': column_index_from_string('W'),
	'ansvarlig': column_index_from_string('AB'),
	'frist': column_index_from_string('AE'),
	'konsekvens_etter': column_index_from_string('AF'),
	'sannsynlighet_etter': column_index_from_string('AG'),
}

_FORSIDE_SKIP_PREFIXES = (
	'her kan det',
	'hvis du',
	'med risikoeier',
	'nb!',
	'(',
)

_FORSIDE_MAX_ROW = 33
_FORSIDE_VALUE_COL_START = column_index_from_string('C')
_FORSIDE_VALUE_COL_END = column_index_from_string('P')
_FORSIDE_VALUE_COLS = range(_FORSIDE_VALUE_COL_START, _FORSIDE_VALUE_COL_END + 1)


def _cell_val(ws, row, col_key):
	return ws.cell(row, _COL[col_key]).value


def _str_val(value):
	if value is None:
		return ''
	return str(value).strip()


def _is_placeholder_tiltak_cell(text):
	"""Skip empty/xx-style stubs in O/W tiltak columns only."""
	return _is_placeholder_tiltak(text)


def _collect_sarbarheter(ws, start_row):
	"""All non-empty I-column strings in the block, one per line."""
	lines = []
	for offset in range(BLOCK_SIZE):
		text = _str_val(_cell_val(ws, start_row + offset, 'sarbarhet'))
		if text:
			lines.append(text)
	return lines


def _collect_verdier(ws, start_row):
	"""All non-empty D-column verdi names in the block (any of the 10 rows)."""
	names = []
	for offset in range(BLOCK_SIZE):
		name = _str_val(_cell_val(ws, start_row + offset, 'verdi'))
		if name:
			names.append(name)
	return names


def _coerce_frist(value):
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, date):
		return value
	return None


def _build_verdi_lookup(workbook):
	"""Verdivurdering col B name -> Beregnet verdi (1–5) from col J."""
	if 'Verdivurdering' not in workbook.sheetnames:
		return {}
	ws = workbook['Verdivurdering']
	lookup = {}
	for row in range(2, ws.max_row + 1):
		name = _str_val(ws.cell(row, 2).value)
		if not name:
			continue
		level = ws.cell(row, 10).value
		try:
			n = int(level)
			if 1 <= n <= 5:
				lookup[name] = n
		except (TypeError, ValueError):
			pass
	return lookup


def _build_trussel_lookup(workbook):
	"""Trusselvurdering col B name -> level text (manual P overrides auto O)."""
	if 'Trusselvurdering' not in workbook.sheetnames:
		return {}
	ws = workbook['Trusselvurdering']
	lookup = {}
	for row in range(3, ws.max_row + 1):
		name = _str_val(ws.cell(row, 2).value)
		if not name:
			continue
		manual = _str_val(ws.cell(row, 16).value)
		auto = _str_val(ws.cell(row, 15).value)
		level_text = manual or auto
		if level_text and level_text not in ('#N/A', '#REF!'):
			lookup[name] = level_text
	return lookup


def _konsekvens_label(level):
	if not level:
		return ''
	return get_active_criteria().konsekvens_lookup_label(level) or str(level)


def _parse_risikovurdering_data(workbook):
	"""Map risk block number (1-based) -> numeric level dict from hidden data sheet."""
	if 'Risikovurdering_data' not in workbook.sheetnames:
		return {}
	ws = workbook['Risikovurdering_data']
	result = {}
	for row in range(3, ws.max_row + 1, BLOCK_SIZE):
		risk_ref = ws.cell(row, 1).value
		if not risk_ref or str(risk_ref).strip() in ('0', ''):
			continue
		digits = ''.join(c for c in str(risk_ref) if c.isdigit())
		if not digits:
			continue
		block_num = int(digits)
		result[block_num] = {
			'sannsynlighet': ws.cell(row, 3).value,
			'konsekvens': ws.cell(row, 4).value,
			'sannsynlighet_etter': ws.cell(row, 6).value,
			'konsekvens_etter': ws.cell(row, 7).value,
		}
	return result


def _is_forside_boilerplate(label):
	lower = label.lower()
	return any(lower.startswith(p) for p in _FORSIDE_SKIP_PREFIXES)


def _collect_forside_row_values(ws, row):
	values = []
	for col in _FORSIDE_VALUE_COLS:
		v = _str_val(ws.cell(row, col).value)
		if v:
			values.append(v)
	return values


def _extract_forside_beskrivelse(workbook):
	"""Best-effort dump of Forside label/value pairs into scope beskrivelse."""
	if 'Forside' not in workbook.sheetnames:
		return ''
	ws = workbook['Forside']
	lines = []
	row = 1
	while row <= _FORSIDE_MAX_ROW:
		label = _str_val(ws.cell(row, 2).value)
		if not label or _is_forside_boilerplate(label):
			row += 1
			continue

		values = _collect_forside_row_values(ws, row)
		scan_row = row + 1
		while scan_row <= _FORSIDE_MAX_ROW:
			next_label = _str_val(ws.cell(scan_row, 2).value)
			if next_label and not _is_forside_boilerplate(next_label):
				break
			values.extend(_collect_forside_row_values(ws, scan_row))
			scan_row += 1

		if values:
			lines.append('%s: %s' % (label.rstrip(':'), ', '.join(values)))
		else:
			lines.append(label.rstrip(':'))
		row = scan_row
	return '\n'.join(lines).strip()


def _compose_uonsket_hendelse(scenario_text, verdier, trussel, trussel_level_text,
		verdi_lookup, trussel_lookup, warnings, risk_id):
	parts = []
	base = _str_val(scenario_text)
	if base:
		parts.append(base)

	verdi_bits = []
	for name in verdier:
		level = verdi_lookup.get(name)
		label = _konsekvens_label(level) if level else ''
		if label:
			verdi_bits.append('%s (%s)' % (name, label.lower()))
		else:
			verdi_bits.append(name)
			if name not in verdi_lookup:
				warnings.append('%s: ukjent verdi %r i Verdivurdering' % (risk_id, name))
	if verdi_bits:
		parts.append('Berører verdi(er): %s.' % ', '.join(verdi_bits))

	trussel_name = _str_val(trussel)
	if trussel_name:
		level_text = _str_val(trussel_level_text)
		if not level_text:
			level_text = trussel_lookup.get(trussel_name, '')
		if level_text:
			parts.append('Trussel: %s (%s).' % (trussel_name, level_text.lower()))
		else:
			parts.append('Trussel: %s.' % trussel_name)

	return ' '.join(parts).strip()


def _risk_id_from_block(risk_num):
	try:
		n = int(risk_num)
	except (TypeError, ValueError):
		n = risk_num
	return 'R%s' % n


def import_large_risk_workbook(workbook, user, source_filename):
	"""
	Import large «risikovurderingsverktøy» template (Risikovurdering sheet).
	Rolls back on error (atomic transaction).
	"""
	if 'Risikovurdering' not in workbook.sheetnames:
		raise ValueError('Mangler ark «Risikovurdering» i Excel-filen.')

	warnings = []
	ws = workbook['Risikovurdering']
	verdi_lookup = _build_verdi_lookup(workbook)
	trussel_lookup = _build_trussel_lookup(workbook)
	data_by_block = _parse_risikovurdering_data(workbook)
	forside_text = _extract_forside_beskrivelse(workbook)
	if forside_text:
		warnings.append('Forside-tekst er limt inn i beskrivelse – vurder manuelt.')

	with transaction.atomic():
		scope = create_risk_scope(
			user,
			title=_title_from_filename(source_filename),
			beskrivelse=forside_text,
			sist_revidert=date.today(),
			source_filename=source_filename or '',
		)
		scenario_count = 0
		action_count = 0
		rekkefolge = 0

		for start_row in range(DATA_START_ROW, ws.max_row + 1, BLOCK_SIZE):
			risk_num = _cell_val(ws, start_row, 'risk_id')
			if risk_num is None or _str_val(risk_num) == '':
				break
			scenario_text = _str_val(_cell_val(ws, start_row, 'scenario'))
			if not scenario_text:
				break
			rekkefolge += 1
			risk_id = _risk_id_from_block(risk_num)

			try:
				block_num = int(risk_num)
			except (TypeError, ValueError):
				block_num = rekkefolge
			data_row = data_by_block.get(block_num, {})

			konsekvens = _coerce_level(
				_cell_val(ws, start_row, 'konsekvens'),
				data_row.get('konsekvens'),
				'konsekvens',
			)
			sannsynlighet = _coerce_level(
				_cell_val(ws, start_row, 'sannsynlighet'),
				data_row.get('sannsynlighet'),
				'sannsynlighet',
			)
			konsekvens_etter = _coerce_level(
				_cell_val(ws, start_row, 'konsekvens_etter'),
				data_row.get('konsekvens_etter'),
				'konsekvens',
			)
			sannsynlighet_etter = _coerce_level(
				_cell_val(ws, start_row, 'sannsynlighet_etter'),
				data_row.get('sannsynlighet_etter'),
				'sannsynlighet',
			)

			if konsekvens is None and _str_val(_cell_val(ws, start_row, 'konsekvens')):
				warnings.append('%s: ukjent konsekvens %r' % (
					risk_id, _cell_val(ws, start_row, 'konsekvens')))
			if sannsynlighet is None and _str_val(_cell_val(ws, start_row, 'sannsynlighet')):
				warnings.append('%s: ukjent sannsynlighet %r' % (
					risk_id, _cell_val(ws, start_row, 'sannsynlighet')))

			verdier = _collect_verdier(ws, start_row)

			uonsket_hendelse = _compose_uonsket_hendelse(
				scenario_text,
				verdier,
				_cell_val(ws, start_row, 'trussel'),
				_cell_val(ws, start_row, 'trusselnivaa'),
				verdi_lookup,
				trussel_lookup,
				warnings,
				risk_id,
			)

			sarbarheter = _collect_sarbarheter(ws, start_row)
			scenario = RiskScenario.objects.create(
				scope=scope,
				risk_id=risk_id,
				uonsket_hendelse=uonsket_hendelse,
				kit_dimensjoner=_str_val(_cell_val(ws, start_row, 'kit')),
				arsaker_svakheter='\n'.join(sarbarheter),
				konsekvens_nivaa=konsekvens,
				sannsynlighet_nivaa=sannsynlighet,
				konsekvens_begrunnelse=_str_val(_cell_val(ws, start_row, 'kons_begrunnelse')),
				sannsynlighetsbegrunnelse=_str_val(_cell_val(ws, start_row, 'sanns_begrunnelse')),
				risikobehandling='',
				konsekvens_etter=konsekvens_etter,
				sannsynlighet_etter=sannsynlighet_etter,
				rekkefolge=rekkefolge,
			)
			scenario_count += 1

			for offset in range(BLOCK_SIZE):
				row = start_row + offset
				eks = _cell_val(ws, row, 'eks_tiltak')
				if not _is_placeholder_tiltak_cell(eks):
					text = _str_val(eks)
					if text:
						action = RiskAction.objects.create(
							scope=scope,
							beskrivelse=text,
							kilde='parsed',
							status='utfort',
						)
						action.scenarios.add(scenario)
						action_count += 1

				plan = _cell_val(ws, row, 'tiltak')
				if not _is_placeholder_tiltak_cell(plan):
					text = _str_val(plan)
					if text:
						action = RiskAction.objects.create(
							scope=scope,
							beskrivelse=text,
							ansvarlig=_str_val(_cell_val(ws, row, 'ansvarlig')),
							frist=_coerce_frist(_cell_val(ws, row, 'frist')),
							kilde='parsed',
							status='besluttet',
						)
						action.scenarios.add(scenario)
						action_count += 1

	return ImportResult(
		scope=scope,
		scenario_count=scenario_count,
		action_count=action_count,
		warnings=warnings,
		format='large',
	)
