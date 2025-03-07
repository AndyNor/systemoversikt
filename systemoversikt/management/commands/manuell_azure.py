from django.core.management.base import BaseCommand
import os
import simplejson as json
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from systemoversikt.models import *
from dateutil import parser

class Command(BaseCommand):
	def handle(self, **options):

		""" denne klienten heter "UKE - Kartoteket - Lesetilgang MS Graph"
		og er tildelt rettighetene "Read consent and permission grant policies" og
		"Read all applications" """
		client_credential = ClientSecretCredential(
				tenant_id=os.environ['AZURE_TENANT_ID'],
				client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
				client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
		)

		client = GraphClient(credential=client_credential, api_version='v1.0')

		resp = client.get(f"https://graph.microsoft.com/v1.0/$metadata#identity/conditionalAccess/policies(---)/grantControls/authenticationStrength/$entity")
		print(f"Response code {resp.status_code}")

		#response_show = json.dumps(json.loads(resp.text), indent=4)
		#print(f"Response:\n {response_show}")

		print(f"Response code {resp.text}")




