# -*- coding: utf-8 -*-
# 2026-07-07: InfobloxHost + NetworkContainer EA fields for Infoblox IP search enrichment.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

	dependencies = [
		('systemoversikt', '0007_risk_scope_omfang_fil'),
	]

	operations = [
		migrations.AddField(
			model_name='networkcontainer',
			name='ip_helper',
			field=models.CharField(max_length=200, null=True, verbose_name='IP-helper'),
		),
		migrations.AddField(
			model_name='networkcontainer',
			name='location_name',
			field=models.CharField(max_length=200, null=True, verbose_name='Lokasjon'),
		),
		migrations.AddField(
			model_name='networkcontainer',
			name='vlan_name',
			field=models.CharField(max_length=200, null=True, verbose_name='VLAN-navn'),
		),
		migrations.CreateModel(
			name='InfobloxHost',
			fields=[
				('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('sist_oppdatert', models.DateTimeField(auto_now=True, verbose_name='Sist oppdatert')),
				('record_type', models.CharField(max_length=50, verbose_name='Infoblox record type')),
				('fqdn', models.CharField(blank=True, default='', max_length=500, verbose_name='FQDN / navn')),
				('mac_address', models.CharField(blank=True, max_length=50, null=True, verbose_name='MAC-adresse')),
				('comment', models.CharField(blank=True, max_length=500, null=True, verbose_name='Kommentar')),
				('disabled', models.BooleanField(default=False, verbose_name='Deaktivert')),
				('locationid', models.CharField(blank=True, max_length=50, null=True, verbose_name='Location ID')),
				('orgname', models.CharField(blank=True, max_length=200, null=True, verbose_name='Org name')),
				('equipment_label', models.CharField(blank=True, max_length=200, null=True, verbose_name='Utstyrsbetegnelse')),
				('vrfname', models.CharField(blank=True, max_length=200, null=True, verbose_name='VRF name')),
				('netcategory', models.CharField(blank=True, max_length=200, null=True, verbose_name='Nettverkskategori')),
				('interface_label', models.CharField(blank=True, max_length=200, null=True, verbose_name='Interface')),
				('network_ip', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='infoblox_hosts', to='systemoversikt.networkipaddress', verbose_name='IP-adresse')),
			],
			options={
				'verbose_name': 'Infoblox host',
				'verbose_name_plural': 'CMDB: Infoblox hosts',
				'default_permissions': ('add', 'change', 'delete', 'view'),
				'unique_together': {('network_ip', 'record_type', 'fqdn')},
			},
		),
	]
