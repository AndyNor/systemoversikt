# Production-only – copy to systemoversikt/migrations/ on server.
# 2026-07-02: Equivalent to dev 0222 – related_name on group FK fields (state only).

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

	dependencies = [
		migrations.swappable_dependency(settings.AUTH_USER_MODEL),
		('systemoversikt', '0459_rename_risk_virksomhet_group'),
	]

	operations = [
		migrations.AlterField(
			model_name='riskvirksomhetgroup',
			name='created_by',
			field=models.ForeignKey(
				blank=True,
				null=True,
				on_delete=django.db.models.deletion.SET_NULL,
				related_name='risk_groups_created',
				to=settings.AUTH_USER_MODEL,
				verbose_name='Opprettet av',
			),
		),
		migrations.AlterField(
			model_name='riskvirksomhetgroup',
			name='virksomhet',
			field=models.ForeignKey(
				on_delete=django.db.models.deletion.CASCADE,
				related_name='risk_groups',
				to='systemoversikt.virksomhet',
				verbose_name='Virksomhet',
			),
		),
		migrations.AlterField(
			model_name='riskvirksomhetgroupmember',
			name='added_by',
			field=models.ForeignKey(
				blank=True,
				null=True,
				on_delete=django.db.models.deletion.SET_NULL,
				related_name='risk_virksomhet_group_memberships_added',
				to=settings.AUTH_USER_MODEL,
				verbose_name='Lagt til av',
			),
		),
		migrations.AlterField(
			model_name='riskvirksomhetgroupmember',
			name='user',
			field=models.ForeignKey(
				on_delete=django.db.models.deletion.CASCADE,
				related_name='risk_virksomhet_group_memberships',
				to=settings.AUTH_USER_MODEL,
				verbose_name='Bruker',
			),
		),
	]
