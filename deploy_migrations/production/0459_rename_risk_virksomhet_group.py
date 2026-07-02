# Production-only – copy to systemoversikt/migrations/ on server.
# 2026-07-02: Equivalent to dev 0221 – rename read groups to virksomhet groups.
# Historical models renamed first to avoid state KeyError on AlterModelOptions.

from django.db import migrations, models


class Migration(migrations.Migration):

	dependencies = [
		('systemoversikt', '0458_risk_participant_groups'),
	]

	operations = [
		migrations.RenameModel(
			old_name='HistoricalRiskVirksomhetReadGroup',
			new_name='HistoricalRiskVirksomhetGroup',
		),
		migrations.RenameModel(
			old_name='HistoricalRiskVirksomhetReadGroupMember',
			new_name='HistoricalRiskVirksomhetGroupMember',
		),
		migrations.RenameModel(
			old_name='RiskVirksomhetReadGroup',
			new_name='RiskVirksomhetGroup',
		),
		migrations.RenameModel(
			old_name='RiskVirksomhetReadGroupMember',
			new_name='RiskVirksomhetGroupMember',
		),
		migrations.AlterModelOptions(
			name='riskvirksomhetgroup',
			options={
				'default_permissions': ('add', 'change', 'delete', 'view'),
				'ordering': ['virksomhet__virksomhetsnavn', 'title'],
				'verbose_name': 'risiko virksomhetsgruppe',
				'verbose_name_plural': 'Risiko: virksomhetsgrupper',
			},
		),
		migrations.AlterModelOptions(
			name='riskvirksomhetgroupmember',
			options={
				'default_permissions': ('add', 'change', 'delete', 'view'),
				'verbose_name': 'risiko virksomhetsgruppe-medlem',
				'verbose_name_plural': 'Risiko: virksomhetsgruppe-medlemmer',
			},
		),
		migrations.RemoveConstraint(
			model_name='riskvirksomhetgroup',
			name='risk_virksomhet_read_group_unique_title',
		),
		migrations.AddConstraint(
			model_name='riskvirksomhetgroup',
			constraint=models.UniqueConstraint(
				fields=('virksomhet', 'title'),
				name='risk_virksomhet_group_unique_title',
			),
		),
		migrations.RemoveConstraint(
			model_name='riskvirksomhetgroupmember',
			name='risk_virksomhet_read_group_member_unique',
		),
		migrations.AddConstraint(
			model_name='riskvirksomhetgroupmember',
			constraint=models.UniqueConstraint(
				fields=('group', 'user'),
				name='risk_virksomhet_group_member_unique',
			),
		),
		migrations.AlterField(
			model_name='riskscope',
			name='participant_groups',
			field=models.ManyToManyField(
				blank=True,
				related_name='participant_scopes',
				to='systemoversikt.riskvirksomhetgroup',
				verbose_name='Deltakergrupper',
			),
		),
	]
