# 2026-07-07: Optional reader_groups M2M on RiskSammenstilling – read-only tilgang via tilgangsgrupper.

from django.db import migrations, models


class Migration(migrations.Migration):

	dependencies = [
		('systemoversikt', '0009_alter_historicalriskscope_beskrivelse'),
	]

	operations = [
		migrations.AddField(
			model_name='risksammenstilling',
			name='reader_groups',
			field=models.ManyToManyField(
				blank=True,
				related_name='reader_sammenstillinger',
				to='systemoversikt.riskvirksomhetgroup',
				verbose_name='Lesergrupper',
			),
		),
	]
