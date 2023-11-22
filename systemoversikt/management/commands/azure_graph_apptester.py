# -*- coding: utf-8 -*-
#Graph-klienten heter "UKE - Kartoteket - Lesetilgang MS Graph"

from django.core.management.base import BaseCommand
import os
import simplejson as json
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from systemoversikt.models import *

class Command(BaseCommand):
	def handle(self, **options):

		SCRIPT_NAVN = os.path.basename(__file__)
		print(f"------ Starter {SCRIPT_NAVN} ------")

		client_credential = ClientSecretCredential(
				tenant_id=os.environ['AZURE_TENANT_ID'],
				client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
				client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
		)
		api_version = "v1.0"
		client = GraphClient(credential=client_credential, api_version=api_version)

		#app_id = "1b1ca5e0-1306-4b87-ac13-3189513d07c3"
		app_id = "fa837fcc-63ef-48cc-93a7-6730b2b79208"

		print("###### servicePrincipals")
		query = f"/servicePrincipals?filter=appId eq '{app_id}'"
		resp = client.get(query)
		load_appdata = json.loads(resp.text)
		print(json.dumps(load_appdata, sort_keys=True, indent=4))

		query = f"/servicePrincipals/{app_id}/appRoleAssignments"
		resp = client.get(query)
		load_appdata = json.loads(resp.text)
		print(json.dumps(load_appdata, sort_keys=True, indent=4))

		print("\n\n###### applications")
		query = f"/applications/"
		resp = client.get(query)
		load_appdata = json.loads(resp.text)
		for element in load_appdata["value"]:
			if element.get('appId') == app_id:
				print(json.dumps(element, sort_keys=True, indent=4))



