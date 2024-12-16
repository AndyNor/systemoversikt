# -*- coding: utf-8 -*-
#Graph-klienten heter "UKE - Kartoteket - Lesetilgang MS Graph"

from django.core.management.base import BaseCommand
import os
import simplejson as json
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from systemoversikt.models import *
from datetime import datetime

class Command(BaseCommand):
	def handle(self, **options):

		SCRIPT_NAVN = os.path.basename(__file__)
		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")

		client_credential = ClientSecretCredential(
				tenant_id=os.environ['AZURE_TENANT_ID'],
				client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
				client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
		)
		api_version = "beta"
		client = GraphClient(credential=client_credential, api_version=api_version)

		#appId = "035644cb-58d9-40c6-b99d-ff54da8420f0"
		#id = "f08b16ec-0cf0-49cd-b218-bea08ea89473"

		#appId = "a958cfb9-702f-4749-91b9-76425c24607d"
		#id = "08d19d40-dc96-4c23-ab8e-9924217988e3"

		#appId="de8bc8b5-d9f9-48b1-a8ad-b748da725064"
		#id = "a4df79b7-738d-45eb-bd43-9027794e90f3"
		#resourceId = "f79aa4bf-5541-4a86-9dd0-37eca09a4047"

		#appId = "73b44d20-8bc2-4baf-a286-75aa54e95638"
		#id = "633049f5-6ae7-4e84-aca5-8364465e8f69"

		#appId="860884e1-4787-4f49-8bc1-cf3042cafea1"
		#id = "860884e1-4787-4f49-8bc1-cf3042cafea1"


		#query = f"/servicePrincipals?filter=appId eq '{appId}'"
		#print(query)
		#resp = client.get(query)
		#load_appdata = json.loads(resp.text)
		#print(json.dumps(load_appdata, sort_keys=True, indent=4))


		#query = f"/servicePrincipals/{id}/oauth2PermissionGrants" # delegatedPermissionClassifications
		#print(query)
		#resp = client.get(query)
		#load_appdata = json.loads(resp.text)
		#print(json.dumps(load_appdata, sort_keys=True, indent=4))

		#query = f"/servicePrincipals?filter=id eq 'f79aa4bf-5541-4a86-9dd0-37eca09a4047'"
		#print(query)
		#resp = client.get(query)
		#load_appdata = json.loads(resp.text)
		#print(json.dumps(load_appdata, sort_keys=True, indent=4))


		"""
		query = f"/applications/"
		print(query)
		resp = client.get(query)
		load_appdata = json.loads(resp.text)
		for element in load_appdata["value"]:
			if element.get('appId') == appId:
				print(json.dumps(element, sort_keys=True, indent=4))
		"""

		#query = f"/users/29d3e814-e58e-464e-84b9-35807bb290f3"
		#print(query)
		#resp = client.get(query)
		#load_appdata = json.loads(resp.text)
		#print(json.dumps(load_appdata, sort_keys=True, indent=4))

		#app_id = "dee03267-cbae-4d3f-bc72-95e36a634816"
		#query = f"/servicePrincipals?filter=appId eq '{app_id}'"
		#print(query)
		#resp = client.get(query)
		#load_appdata = json.loads(resp.text)
		#print(json.dumps(load_appdata, sort_keys=True, indent=4))

		app_id = "dee03267-cbae-4d3f-bc72-95e36a634816"
		sp_id = "4ee994db-e657-4bfe-9b4a-e00eed407b3a"
		id_ = "ab122a5a-88ba-4aff-8faf-ca5e07973180"
		query = f"/servicePrincipals/{id_}/"
		#print(query)
		resp = client.get(query)
		load_appdata = json.loads(resp.text)
		print(json.dumps(load_appdata, sort_keys=True, indent=4))
