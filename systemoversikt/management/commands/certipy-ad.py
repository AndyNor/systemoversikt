# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
import os
import subprocess

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "ad_certificate_templates"
		LOG_EVENT_TYPE = "ADCS sårbare maler"

		username = os.environ['KARTOTEKET_LDAPUSER'].split("\\")[1]
		password = os.environ['KARTOTEKET_LDAPPASSWORD']
		ldap_server = os.environ["KARTOTEKET_LDAPSERVER"]

		command = f"certipy find -json -stdout -dc-only -u {username} -p {password} -target {ldap_server} -enabled -vulnerable -timeout 240"
		#print(command)
		result = subprocess.check_output(command, shell=True)
		#print(result)