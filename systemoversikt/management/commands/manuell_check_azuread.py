
from django.core.management.base import BaseCommand
from django.db import transaction
import os
import requests

from django.conf import settings
from systemoversikt.models import *


class Command(BaseCommand):
	def handle(self, **options):

		proxies = {
			'https': os.environ['PROXY_ADDR_HTTP'],
		}
		response_jwks = requests.get(
			"https://login.microsoftonline.com/common/discovery/v2.0/keys",
			verify=True,
			timeout=5,
			proxies=proxies,
		)
		response_jwks.raise_for_status()
		jwks = response_jwks.json()
		print(jwks)