# 2026-08-19: Store Entra ID Assignment required (appRoleAssignmentRequired) on AzureApplication.

from django.db import migrations, models


class Migration(migrations.Migration):
	dependencies = [
		('systemoversikt', '0014_riskaction_unntak_kontinuerlig_status'),
	]

	operations = [
		migrations.AddField(
			model_name='azureapplication',
			name='appRoleAssignmentRequired',
			field=models.BooleanField(
				blank=True,
				help_text='Entra ID Assignment required (appRoleAssignmentRequired). When false, assigned users/groups do not restrict access.',
				null=True,
				verbose_name='Tildeling påkrevd',
			),
		),
	]
