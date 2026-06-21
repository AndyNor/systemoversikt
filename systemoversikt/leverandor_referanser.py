# -*- coding: utf-8 -*-
# Change log:
# 2026-06-21: Auto-discover reverse relations to Leverandor – new model refs picked up without manual list.
# 2026-06-21: Shared leverandør reference checks for overview stats and nightly cleanup job.

from django.db import connection
from django.db.models import Count, Q

from systemoversikt.models import Leverandor


def _leverandor_referanse_specs():
	"""Yield metadata for each live model field that references Leverandor."""
	qn = connection.ops.quote_name
	seen_through_tables = set()

	for f in Leverandor._meta.get_fields(include_hidden=True):
		if not f.is_relation or not f.auto_created:
			continue

		related_model = f.related_model
		if related_model._meta.object_name.startswith('Historical'):
			continue

		if f.many_to_many:
			forward_field = f.field
			through = forward_field.remote_field.through
			table = through._meta.db_table
			if table in seen_through_tables:
				continue
			seen_through_tables.add(table)
			lev_col = forward_field.m2m_reverse_name()
			yield {
				'modell': related_model._meta.object_name,
				'felt': forward_field.verbose_name,
				'union_sql': f'SELECT {qn(lev_col)} AS leverandor_id FROM {qn(table)}',
				'count_source': ('m2m', through, lev_col),
			}
		elif f.one_to_many or f.one_to_one:
			if related_model._meta.auto_created:
				continue
			fk_field = f.field
			col = fk_field.column
			table = related_model._meta.db_table
			yield {
				'modell': related_model._meta.object_name,
				'felt': fk_field.verbose_name,
				'union_sql': f'SELECT {qn(col)} AS leverandor_id FROM {qn(table)} WHERE {qn(col)} IS NOT NULL',
				'count_source': ('fk', related_model, col),
			}


def _leverandor_referanse_antall(count_source):
	source_type, model_or_through, col = count_source
	if source_type == 'm2m':
		return model_or_through.objects.values(col).distinct().count()
	return model_or_through.objects.exclude(**{f'{col}__isnull': True}).values(col).distinct().count()


def _sorted_leverandor_referanse_specs():
	return sorted(
		_leverandor_referanse_specs(),
		key=lambda spec: (spec['modell'].lower(), str(spec['felt']).lower()),
	)


def leverandor_koblede_pk_set():
	"""Return PKs for leverandører referenced by at least one model field."""
	union_parts = [spec['union_sql'] for spec in _leverandor_referanse_specs()]
	if not union_parts:
		return set()
	with connection.cursor() as cursor:
		cursor.execute(
			'SELECT DISTINCT leverandor_id FROM (' + ' UNION ALL '.join(union_parts) + ') refs'
		)
		return {row[0] for row in cursor.fetchall() if row[0] is not None}


def leverandor_uten_kobling_queryset():
	return Leverandor.objects.exclude(pk__in=leverandor_koblede_pk_set())


def leverandor_referanse_statistikk():
	specs = _sorted_leverandor_referanse_specs()
	referanse_rader = [{
		'modell': spec['modell'],
		'felt': spec['felt'],
		'antall_leverandorer': _leverandor_referanse_antall(spec['count_source']),
	} for spec in specs]

	agg = Leverandor.objects.aggregate(
		totalt=Count('pk'),
		med_land=Count('pk', filter=~Q(land__isnull=True) & ~Q(land='')),
	)
	totalt = agg['totalt'] or 0
	med_land = agg['med_land'] or 0

	union_parts = [spec['union_sql'] for spec in specs]
	with connection.cursor() as cursor:
		cursor.execute(
			'SELECT COUNT(DISTINCT leverandor_id) FROM (' + ' UNION ALL '.join(union_parts) + ') refs'
		)
		med_kobling = cursor.fetchone()[0] or 0

	return {
		'totalt': totalt,
		'med_land': med_land,
		'uten_land': totalt - med_land,
		'med_kobling': med_kobling,
		'uten_kobling': totalt - med_kobling,
		'referanser': referanse_rader,
	}
