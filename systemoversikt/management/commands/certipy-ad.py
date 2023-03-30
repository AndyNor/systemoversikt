# -*- coding: utf-8 -*-

"""
Hensikten med denne koden er ..
"""

from django.core.management.base import BaseCommand
import os
import subprocess

class Command(BaseCommand):
	def handle(self, **options):
		command = f"certipy find -json -stdout -dc-only -u {os.environ['KARTOTEKET_LDAPUSER']} -p {os.environ['KARTOTEKET_LDAPPASSWORD']} -target {os.environ["KARTOTEKET_LDAPSERVER"]} -enabled -vulnerable -timeout 240"
		result = subprocess.check_output(command, shell=True)
		print(result)