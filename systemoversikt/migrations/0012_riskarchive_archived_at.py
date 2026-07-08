from django.db import migrations, models


class Migration(migrations.Migration):
	dependencies = [
		('systemoversikt', '0011_risk_snapshot'),
	]

	operations = [
		migrations.AddField(
			model_name='riskscope',
			name='archived_at',
			field=models.DateTimeField(
				db_index=True,
				null=True,
				blank=True,
				verbose_name='Arkivert',
			),
		),
		migrations.AddField(
			model_name='historicalriskscope',
			name='archived_at',
			field=models.DateTimeField(
				db_index=True,
				null=True,
				blank=True,
				verbose_name='Arkivert',
			),
		),
		migrations.AddField(
			model_name='risksammenstilling',
			name='archived_at',
			field=models.DateTimeField(
				db_index=True,
				null=True,
				blank=True,
				verbose_name='Arkivert',
			),
		),
		migrations.AddField(
			model_name='historicalrisksammenstilling',
			name='archived_at',
			field=models.DateTimeField(
				db_index=True,
				null=True,
				blank=True,
				verbose_name='Arkivert',
			),
		),
	]

