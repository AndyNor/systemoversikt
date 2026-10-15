# 2026-10-15: SystemBruk.kommentar verbose_name «Kommentar til bruken» (was Innhold); field name unchanged.
from django.db import migrations, models


class Migration(migrations.Migration):

	dependencies = [
		('systemoversikt', '0033_godkjentelektroniskarkiv_system_protect'),
	]

	operations = [
		migrations.AlterField(
			model_name='historicalsystembruk',
			name='kommentar',
			field=models.TextField(
				blank=True,
				help_text='Beskriv om virksomheten bruker systemet til noe mer enn det systemeier har godkjent, om det er spesialtilpasninger for virksomheten, og annen relevant informasjon om bruken som er virksomhetsspesifikk.',
				null=True,
				verbose_name='Kommentar til bruken',
			),
		),
		migrations.AlterField(
			model_name='systembruk',
			name='kommentar',
			field=models.TextField(
				blank=True,
				help_text='Beskriv om virksomheten bruker systemet til noe mer enn det systemeier har godkjent, om det er spesialtilpasninger for virksomheten, og annen relevant informasjon om bruken som er virksomhetsspesifikk.',
				null=True,
				verbose_name='Kommentar til bruken',
			),
		),
	]
