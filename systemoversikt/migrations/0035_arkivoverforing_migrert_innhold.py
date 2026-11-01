# 2026-11-01: ArkivOverforing – avsender_system, optional SystemBruk, content period labels,
# beskrivelse/henvisning (replace kommentar); conditional unique constraints.
import django.db.models.deletion
from django.db import migrations, models


def forwards_fill_avsender_and_beskrivelse(apps, schema_editor):
	ArkivOverforing = apps.get_model('systemoversikt', 'ArkivOverforing')
	HistoricalArkivOverforing = apps.get_model('systemoversikt', 'HistoricalArkivOverforing')
	SystemBruk = apps.get_model('systemoversikt', 'SystemBruk')
	bruk_system = dict(SystemBruk.objects.values_list('pk', 'system_id'))
	for row in ArkivOverforing.objects.all().iterator():
		updates = {}
		if row.avsender_bruk_id and not row.avsender_system_id:
			system_id = bruk_system.get(row.avsender_bruk_id)
			if system_id:
				updates['avsender_system_id'] = system_id
		if row.kommentar and not row.beskrivelse:
			updates['beskrivelse'] = row.kommentar
		if updates:
			ArkivOverforing.objects.filter(pk=row.pk).update(**updates)
	for row in HistoricalArkivOverforing.objects.all().iterator():
		updates = {}
		if row.avsender_bruk_id and not row.avsender_system_id:
			system_id = bruk_system.get(row.avsender_bruk_id)
			if system_id:
				updates['avsender_system_id'] = system_id
		if row.kommentar and not row.beskrivelse:
			updates['beskrivelse'] = row.kommentar
		if updates:
			HistoricalArkivOverforing.objects.filter(history_id=row.history_id).update(**updates)


def noop_reverse(apps, schema_editor):
	pass


class Migration(migrations.Migration):

	dependencies = [
		('systemoversikt', '0034_systembruk_kommentar_verbose_name'),
	]

	operations = [
		migrations.RemoveConstraint(
			model_name='arkivoverforing',
			name='unique_arkivoverforing_bruk_mottaker',
		),
		migrations.AddField(
			model_name='arkivoverforing',
			name='avsender_system',
			field=models.ForeignKey(
				null=True,
				on_delete=django.db.models.deletion.CASCADE,
				related_name='arkivoverforinger_som_avsender_system',
				to='systemoversikt.system',
				verbose_name='Avsendersystem',
			),
		),
		migrations.AddField(
			model_name='historicalarkivoverforing',
			name='avsender_system',
			field=models.ForeignKey(
				blank=True,
				db_constraint=False,
				null=True,
				on_delete=django.db.models.deletion.DO_NOTHING,
				related_name='+',
				to='systemoversikt.system',
				verbose_name='Avsendersystem',
			),
		),
		migrations.AddField(
			model_name='arkivoverforing',
			name='beskrivelse',
			field=models.TextField(
				blank=True,
				null=True,
				verbose_name='Overordnet beskrivelse av innholdet som er migrert',
			),
		),
		migrations.AddField(
			model_name='historicalarkivoverforing',
			name='beskrivelse',
			field=models.TextField(
				blank=True,
				null=True,
				verbose_name='Overordnet beskrivelse av innholdet som er migrert',
			),
		),
		migrations.AddField(
			model_name='arkivoverforing',
			name='henvisning_dokumentasjon',
			field=models.TextField(
				blank=True,
				help_text='Henvisning til sak i virksomhetens sakarkiv (ikke kun en lenke).',
				null=True,
				verbose_name='Henvisning til dokumentasjon på mappingregler og valg',
			),
		),
		migrations.AddField(
			model_name='historicalarkivoverforing',
			name='henvisning_dokumentasjon',
			field=models.TextField(
				blank=True,
				help_text='Henvisning til sak i virksomhetens sakarkiv (ikke kun en lenke).',
				null=True,
				verbose_name='Henvisning til dokumentasjon på mappingregler og valg',
			),
		),
		migrations.AlterField(
			model_name='arkivoverforing',
			name='avsender_bruk',
			field=models.ForeignKey(
				blank=True,
				help_text='Valgfri. Tom = migreringen gjelder hele systemet.',
				null=True,
				on_delete=django.db.models.deletion.CASCADE,
				related_name='arkivoverforinger_som_avsender',
				to='systemoversikt.systembruk',
				verbose_name='Avsender (systembruk)',
			),
		),
		migrations.AlterField(
			model_name='historicalarkivoverforing',
			name='avsender_bruk',
			field=models.ForeignKey(
				blank=True,
				db_constraint=False,
				help_text='Valgfri. Tom = migreringen gjelder hele systemet.',
				null=True,
				on_delete=django.db.models.deletion.DO_NOTHING,
				related_name='+',
				to='systemoversikt.systembruk',
				verbose_name='Avsender (systembruk)',
			),
		),
		migrations.AlterField(
			model_name='arkivoverforing',
			name='dato_start',
			field=models.DateField(
				blank=True,
				null=True,
				verbose_name='Dato for når informasjonsinnholdet er produsert (fra)',
			),
		),
		migrations.AlterField(
			model_name='historicalarkivoverforing',
			name='dato_start',
			field=models.DateField(
				blank=True,
				null=True,
				verbose_name='Dato for når informasjonsinnholdet er produsert (fra)',
			),
		),
		migrations.AlterField(
			model_name='arkivoverforing',
			name='dato_avsluttet',
			field=models.DateField(
				blank=True,
				null=True,
				verbose_name='Dato for når informasjonsinnholdet er produsert (til)',
			),
		),
		migrations.AlterField(
			model_name='historicalarkivoverforing',
			name='dato_avsluttet',
			field=models.DateField(
				blank=True,
				null=True,
				verbose_name='Dato for når informasjonsinnholdet er produsert (til)',
			),
		),
		migrations.RunPython(forwards_fill_avsender_and_beskrivelse, noop_reverse),
		migrations.AlterField(
			model_name='arkivoverforing',
			name='avsender_system',
			field=models.ForeignKey(
				on_delete=django.db.models.deletion.CASCADE,
				related_name='arkivoverforinger_som_avsender_system',
				to='systemoversikt.system',
				verbose_name='Avsendersystem',
			),
		),
		migrations.RemoveField(
			model_name='arkivoverforing',
			name='kommentar',
		),
		migrations.RemoveField(
			model_name='historicalarkivoverforing',
			name='kommentar',
		),
		migrations.AddConstraint(
			model_name='arkivoverforing',
			constraint=models.UniqueConstraint(
				condition=models.Q(('avsender_bruk__isnull', True)),
				fields=('avsender_system', 'mottaker_system'),
				name='unique_arkivoverforing_system_mottaker',
			),
		),
		migrations.AddConstraint(
			model_name='arkivoverforing',
			constraint=models.UniqueConstraint(
				condition=models.Q(('avsender_bruk__isnull', False)),
				fields=('avsender_bruk', 'mottaker_system'),
				name='unique_arkivoverforing_bruk_mottaker',
			),
		),
	]
