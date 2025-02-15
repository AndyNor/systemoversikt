# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import System, Database
import requests
import time
import json

class Command(BaseCommand):
	def handle(self, **options):

		schema = "https://"
		domain = ".oslo.kommune.no"
		names = ["fin","fob","info","fkok"]
		for name in names:
			print(name)
			try:
				time.sleep(1)
				url = f"{schema}{name}{domain}"
				headers = None

				r = requests.get(url, headers=headers)
				#print(f"{r.status_code} fra {url}")
				if r.status_code == 200:
					with open('dns_scan_200_OK.txt', 'a+') as file:
						file.write(json.dumps({"code": r.status_code, "name": name}))
						file.write("\n")
				else:
					with open('dns_scan_other.txt', 'a+') as file:
						file.write(json.dumps({"code": r.status_code, "name": name}))
						file.write("\n")
			except Exception as e:
				with open('dns_scan_failed.txt', 'a+') as file:
					file.write(json.dumps({"code": None, "name": name}))
					file.write("\n")


