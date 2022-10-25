
from django.core.management.base import BaseCommand
from django.db import transaction
import os
import requests

from django.conf import settings
from systemoversikt.models import *


class Command(BaseCommand):
	def handle(self, **options):

		#cmd = 'export http_proxy="%s"' % (os.environ['PROXY_HTTPS'])
		#os.system(cmd)

		basicAuthCredentials = (os.environ['PROXY_USER'], os.environ['PROXY_PASSWORD'])

		proxies = {
			'https': os.environ['PROXY_ADDR_HTTP'],
		}
		response_jwks = requests.get(
			"https://login.microsoftonline.com/common/discovery/v2.0/keys",
			verify=True,
			timeout=5,
			proxies=proxies,
			auth=basicAuthCredentials,
		)
		response_jwks.raise_for_status()
		jwks = response_jwks.json()
		print(jwks)