from django.core.management.base import BaseCommand
import os
import simplejson as json
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from systemoversikt.models import *

class Command(BaseCommand):
	def handle(self, **options):

		client_credential = ClientSecretCredential(
				tenant_id=os.environ['AZURE_TENANT_ID'],
				client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
				client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
		)

		client = GraphClient(credential=client_credential, api_version='beta')
		query = "/identity/conditionalAccess/namedLocations"
		resp = client.get(query)
		load_appdata = json.loads(resp.text)
		print(json.dumps(load_appdata, sort_keys=True, indent=4))