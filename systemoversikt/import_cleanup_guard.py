# -*- coding: utf-8 -*-
# Change log:
# 2026-06-11: Shared import volume checks – skip mass cleanup when source returns too few rows.
# 2026-06-11: IMPORT_CLEANUP_MIN_AGE_HOURS – minimum stale age before import cleanup may delete.

"""Guards against mass deletion after failed or empty imports."""

# Daily imports should finish within a few hours; wait at least one full day before stale cleanup.
IMPORT_CLEANUP_MIN_AGE_HOURS = 24


class ImportCleanupAborted(Exception):
	"""Raised when an import returned too few rows to safely run cleanup."""


def validate_import_volume(
	import_count,
	*,
	label,
	existing_count=None,
	previous_count=None,
	min_absolute=1,
	min_ratio_vs_previous=0.5,
	min_ratio_vs_existing=0.5,
):
	"""
	Raise ImportCleanupAborted if import_count is too low to trust a cleanup/delete phase.

	Compares against the previous successful run (IntegrasjonKonfigurasjon.elementer)
	and/or current row count in the database.
	"""
	import_count = int(import_count or 0)
	previous_count = int(previous_count) if previous_count else None
	existing_count = int(existing_count) if existing_count else None

	if import_count < min_absolute:
		raise ImportCleanupAborted(
			f"{label}: import returnerte {import_count} rader (minimum {min_absolute}) – cleanup avbrutt."
		)

	if previous_count is not None and previous_count > 0:
		threshold = int(previous_count * min_ratio_vs_previous)
		if import_count < threshold:
			raise ImportCleanupAborted(
				f"{label}: import returnerte {import_count} rader, forventet minst {threshold} "
				f"(50 % av forrige kjøring med {previous_count}) – cleanup avbrutt."
			)

	if existing_count is not None and existing_count > 0:
		threshold = int(existing_count * min_ratio_vs_existing)
		if import_count < threshold:
			raise ImportCleanupAborted(
				f"{label}: import returnerte {import_count} rader, forventet minst {threshold} "
				f"(50 % av {existing_count} eksisterende) – cleanup avbrutt."
			)

	return f"{label}: volum OK ({import_count} rader)."
