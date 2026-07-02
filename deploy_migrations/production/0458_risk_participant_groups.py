# Production-only – copy to systemoversikt/migrations/ on server.
# 2026-07-02: Equivalent to dev 0220 – after prod 0457 (read groups create only).
# Adds virksomhet_read_only and participant_groups before rename in 0459.

from django.db import migrations, models


def set_existing_groups_virksomhet_read_only(apps, schema_editor):
	RiskVirksomhetReadGroup = apps.get_model('systemoversikt', 'RiskVirksomhetReadGroup')
	RiskVirksomhetReadGroup.objects.all().update(virksomhet_read_only=True)


class Migration(migrations.Migration):

	dependencies = [
		('systemoversikt', '0457_riskvirksomhetreadgroup_and_more'),
	]

	operations = [
		migrations.AddField(
			model_name='historicalriskvirksomhetreadgroup',
			name='virksomhet_read_only',
			field=models.BooleanField(
				default=False,
				help_text='Når aktivert får medlemmer lesetilgang til alle risikosamlinger for virksomheten.',
				verbose_name='Lesetilgang til hele virksomheten',
			),
		),
		migrations.AddField(
			model_name='riskscope',
			name='participant_groups',
			field=models.ManyToManyField(
				blank=True,
				related_name='participant_scopes',
				to='systemoversikt.riskvirksomhetreadgroup',
				verbose_name='Deltakergrupper',
			),
		),
		migrations.AddField(
			model_name='riskvirksomhetreadgroup',
			name='virksomhet_read_only',
			field=models.BooleanField(
				default=False,
				help_text='Når aktivert får medlemmer lesetilgang til alle risikosamlinger for virksomheten.',
				verbose_name='Lesetilgang til hele virksomheten',
			),
		),
		migrations.RunPython(
			set_existing_groups_virksomhet_read_only,
			migrations.RunPython.noop,
		),
	]
