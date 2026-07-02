# Production-only – copy to systemoversikt/migrations/ on server.
# 2026-07-02: Equivalent to dev 0223 – historical group Meta labels after rename.

from django.db import migrations


class Migration(migrations.Migration):

	dependencies = [
		('systemoversikt', '0460_alter_risk_virksomhet_group_related_names'),
	]

	operations = [
		migrations.AlterModelOptions(
			name='historicalriskvirksomhetgroup',
			options={
				'get_latest_by': ('history_date', 'history_id'),
				'ordering': ('-history_date', '-history_id'),
				'verbose_name': 'historical risiko virksomhetsgruppe',
				'verbose_name_plural': 'historical Risiko: virksomhetsgrupper',
			},
		),
		migrations.AlterModelOptions(
			name='historicalriskvirksomhetgroupmember',
			options={
				'get_latest_by': ('history_date', 'history_id'),
				'ordering': ('-history_date', '-history_id'),
				'verbose_name': 'historical risiko virksomhetsgruppe-medlem',
				'verbose_name_plural': 'historical Risiko: virksomhetsgruppe-medlemmer',
			},
		),
	]
