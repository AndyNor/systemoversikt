from django.core.management.base import BaseCommand
import io
import os
import simplejson as json
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from systemoversikt.models import *

class Command(BaseCommand):
	def handle(self, **options):

		f = io.open("systemoversikt/management/commands/iso-3166-2.json", mode="r", encoding="utf-8")
		content = f.read()
		countrycodes = json.loads(content)

		client_credential = ClientSecretCredential(
				tenant_id=os.environ['AZURE_TENANT_ID'],
				client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
				client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
		)

		client = GraphClient(credential=client_credential, api_version='beta')
		query = "/identity/conditionalAccess/namedLocations"
		resp = client.get(query)
		json_data = json.loads(resp.text)

		#print(json.dumps(json_data, sort_keys=True, indent=4))

		for named_location in json_data["value"]:
			print(named_location["displayName"] + " (" + named_location["id"] + ")")
			#isTrusted
			#createdDateTime # 2021-04-14T07:52:53.7467133Z
			# modifiedDateTime # bruker bare sist endret
			if "countriesAndRegions" in named_location:
				for code in named_location["countriesAndRegions"]:
					if code in countrycodes:
						print("** " + countrycodes[code])
					#print("** " + code)
					else:
						print(f"** {code}")
				#for ip in named_location["ipRanges"]:
					#print ("** " + ip["cidrAddress"])



