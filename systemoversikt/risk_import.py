# -*- coding: utf-8 -*-
# Change log:
# 2026-06-30: create_risk_scope helper – membership + virksomhet instead of eier FK.
# 2026-06-26: Eksisterende tiltak column → RiskAction per paragraph (status utfort).
# 2026-06-26: Scope-level tiltak linked to scenarios via M2M (reuse across scenarios).
# 2026-06-24: Excel import for security risk module (Risikoanalyse + Tiltak sheets).

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from django.db import transaction

from systemoversikt.models import RiskAction, RiskScenario, RiskScope
from systemoversikt.risk_membership import create_risk_scope
from systemoversikt.risk_criteria import (
	label_to_level,
	risikobehandling_from_text,
	tiltak_status_from_text,
)


@dataclass
class ImportResult:
	scope: RiskScope = None
	scenario_count: int = 0
	action_count: int = 0
	warnings: list = field(default_factory=list)


def _normalize_header(value):
	if value is None:
		return ''
	return re.sub(r'\s+', ' ', str(value).replace('\n', ' ')).strip()


def _header_map(ws):
	headers = {}
	for col in range(1, ws.max_column + 1):
		raw = ws.cell(1, col).value
		if raw is not None:
			headers[_normalize_header(raw)] = col
	return headers


def _cell(ws, row, headers, *names):
	for name in names:
		col = headers.get(name)
		if col:
			return ws.cell(row, col).value
	return None


def _coerce_level(text_value, numeric_fallback, kind):
	if text_value is not None and str(text_value).strip():
		level = label_to_level(text_value, kind=kind)
		if level is not None:
			return level
	if numeric_fallback is not None:
		try:
			n = int(numeric_fallback)
			if 1 <= n <= 5:
				return n
		except (TypeError, ValueError):
			pass
	return None


def _parse_foreslatte_tiltak(text):
	if not text or not str(text).strip():
		return []
	text = str(text).strip()
	parts = re.split(r'(?m)^\s*(\d+)\)\s*', text)
	if len(parts) < 3:
		# No numbered list – single action
		return [(1, text)]
	actions = []
	i = 1
	while i < len(parts) - 1:
		try:
			nr = int(parts[i])
		except ValueError:
			i += 1
			continue
		body = parts[i + 1].strip()
		if body:
			actions.append((nr, body))
		i += 2
	return actions


def _parse_eksisterende_tiltak(text):
	"""Split cell text into one tiltak per paragraph (blank line); fallback: whole cell."""
	if not text or not str(text).strip():
		return []
	text = str(text).strip()
	parts = re.split(r'\n\s*\n+', text)
	paragraphs = [p.strip() for p in parts if p.strip()]
	if paragraphs:
		return paragraphs
	return [text]


def _parse_tiltak_sheet(wb, warnings):
	"""Return dict scenario_num -> list of action dicts."""
	if 'Tiltak' not in wb.sheetnames:
		return {}
	ws = wb['Tiltak']
	headers = _header_map(ws)
	result = {}
	for row in range(2, ws.max_row + 1):
		beskrivelse = _cell(ws, row, headers, 'Tiltak')
		if not beskrivelse or not str(beskrivelse).strip():
			continue
		scenario_ref = _cell(ws, row, headers, 'Risikoscenario')
		if scenario_ref is None:
			continue
		try:
			scenario_num = int(scenario_ref)
		except (TypeError, ValueError):
			warnings.append('Tiltak rad %d: ugyldig Risikoscenario %r' % (row, scenario_ref))
			continue
		tiltak_id = _cell(ws, row, headers, 'Tiltak-ID')
		try:
			int(tiltak_id) if tiltak_id is not None else 0
		except (TypeError, ValueError):
			pass
		frist_val = _cell(ws, row, headers, 'Frist')
		frist = None
		if isinstance(frist_val, datetime):
			frist = frist_val.date()
		elif isinstance(frist_val, date):
			frist = frist_val
		status_text = _cell(ws, row, headers, 'Status')
		result.setdefault(scenario_num, []).append({
			'beskrivelse': str(beskrivelse).strip(),
			'ansvarlig': str(_cell(ws, row, headers, 'Ansvarlig') or '').strip(),
			'frist': frist,
			'status': tiltak_status_from_text(status_text),
			'kilde': 'tiltak_sheet',
		})
	return result


def _title_from_filename(filename):
	name = filename.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
	for ext in ('.xlsx', '.xlsm', '.xls'):
		if name.lower().endswith(ext):
			name = name[:-len(ext)]
			break
	return name.strip() or 'Risikovurdering'


def import_risk_workbook(workbook, user, source_filename):
	"""
	Import Risikoanalyse (+ optional Tiltak) into a new RiskScope.
	Rolls back on error (atomic transaction).
	"""
	warnings = []
	if 'Risikoanalyse' not in workbook.sheetnames:
		raise ValueError('Mangler ark «Risikoanalyse» i Excel-filen.')

	ws = workbook['Risikoanalyse']
	headers = _header_map(ws)
	tiltak_by_scenario = _parse_tiltak_sheet(workbook, warnings)

	with transaction.atomic():
		scope = create_risk_scope(
			user,
			title=_title_from_filename(source_filename),
			sist_revidert=date.today(),
			source_filename=source_filename or '',
		)
		scenario_count = 0
		action_count = 0
		rekkefolge = 0

		for row in range(2, ws.max_row + 1):
			risk_id = _cell(ws, row, headers, 'RiskID')
			if not risk_id or not str(risk_id).strip():
				continue
			risk_id = str(risk_id).strip()
			rekkefolge += 1

			konsekvens = _coerce_level(
				_cell(ws, row, headers, 'Konsekvens'),
				_cell(ws, row, headers, 'Beregnet konsekvensverdi'),
				'konsekvens',
			)
			sannsynlighet = _coerce_level(
				_cell(ws, row, headers, 'Sannsynlighet'),
				_cell(ws, row, headers, 'Sanns_verdi'),
				'sannsynlighet',
			)
			konsekvens_etter = _coerce_level(
				_cell(ws, row, headers, 'Konsekvens etter tiltak'),
				_cell(ws, row, headers, 'Kons_etter_verdi'),
				'konsekvens',
			)
			sannsynlighet_etter = _coerce_level(
				_cell(ws, row, headers, 'Sannsynlighet etter tiltak'),
				_cell(ws, row, headers, 'Sanns_etter_verdi'),
				'sannsynlighet',
			)

			if konsekvens is None and _cell(ws, row, headers, 'Konsekvens'):
				warnings.append('%s: ukjent konsekvens %r' % (risk_id, _cell(ws, row, headers, 'Konsekvens')))
			if sannsynlighet is None and _cell(ws, row, headers, 'Sannsynlighet'):
				warnings.append('%s: ukjent sannsynlighet %r' % (risk_id, _cell(ws, row, headers, 'Sannsynlighet')))

			beh_text = _cell(ws, row, headers, 'Risiko-behandling', 'Risikobehandling')
			scenario = RiskScenario.objects.create(
				scope=scope,
				risk_id=risk_id,
				uonsket_hendelse=str(_cell(ws, row, headers, 'Uønsket hendelse') or '').strip(),
				kit_dimensjoner=str(_cell(ws, row, headers, 'K, I, T') or '').strip(),
				arsaker_svakheter=str(_cell(ws, row, headers, 'Årsaker/svakheter') or '').strip(),
				konsekvens_nivaa=konsekvens,
				sannsynlighet_nivaa=sannsynlighet,
				konsekvens_begrunnelse=str(_cell(ws, row, headers, 'Konsekvensbegrunnelse') or '').strip(),
				sannsynlighetsbegrunnelse=str(_cell(ws, row, headers, 'Sannsynlighetsbegrunnelse') or '').strip(),
				risikobehandling=risikobehandling_from_text(beh_text),
				konsekvens_etter=konsekvens_etter,
				sannsynlighet_etter=sannsynlighet_etter,
				rekkefolge=rekkefolge,
			)
			scenario_count += 1

			eksisterende = _cell(ws, row, headers, 'Eksisterende tiltak')
			for beskrivelse in _parse_eksisterende_tiltak(eksisterende):
				action = RiskAction.objects.create(
					scope=scope,
					beskrivelse=beskrivelse,
					kilde='parsed',
					status='utfort',
				)
				action.scenarios.add(scenario)
				action_count += 1

			scenario_num = scenario.scenario_nummer()
			sheet_actions = tiltak_by_scenario.get(scenario_num, [])
			if sheet_actions:
				for action_data in sheet_actions:
					action = RiskAction.objects.create(scope=scope, **action_data)
					action.scenarios.add(scenario)
					action_count += 1
			else:
				foreslatt = _cell(ws, row, headers, 'Foreslåtte tiltak')
				for _nr, beskrivelse in _parse_foreslatte_tiltak(foreslatt):
					action = RiskAction.objects.create(
						scope=scope,
						beskrivelse=beskrivelse,
						kilde='parsed',
						status='ikke_startet',
					)
					action.scenarios.add(scenario)
					action_count += 1

	return ImportResult(
		scope=scope,
		scenario_count=scenario_count,
		action_count=action_count,
		warnings=warnings,
	)
