# Generated manually for risk rapport omfang files.
# 2026-07-07: RiskScopeOmfangFil – scope figure/original stored as bytes in PostgreSQL.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

	dependencies = [
		('systemoversikt', '0006_riskaction_eskaleres'),
	]

	operations = [
		migrations.CreateModel(
			name='RiskScopeOmfangFil',
			fields=[
				('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('figur_data', models.BinaryField(blank=True, null=True, verbose_name='Omfangsfigur')),
				('figur_content_type', models.CharField(blank=True, default='', max_length=100, verbose_name='Omfangsfigur MIME-type')),
				('figur_filnavn', models.CharField(blank=True, default='', max_length=300, verbose_name='Omfangsfigur filnavn')),
				('original_data', models.BinaryField(blank=True, null=True, verbose_name='Originalfil for figur')),
				('original_content_type', models.CharField(blank=True, default='', max_length=100, verbose_name='Originalfil MIME-type')),
				('original_filnavn', models.CharField(blank=True, default='', max_length=300, verbose_name='Originalfil filnavn')),
				('scope', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='omfang_fil', to='systemoversikt.riskscope', verbose_name='Risikoomfang')),
			],
			options={
				'verbose_name': 'risikoomfang fil',
				'verbose_name_plural': 'Risiko: omfangsfiler',
				'default_permissions': ('add', 'change', 'delete', 'view'),
			},
		),
		migrations.AlterField(
			model_name='riskscope',
			name='beskrivelse',
			field=models.TextField(
				blank=True,
				default='',
				help_text='Omfangsbeskrivelse som inngår i den arkiverte risikovurderingsrapporten.',
				verbose_name='Beskrivelse',
			),
		),
	]
