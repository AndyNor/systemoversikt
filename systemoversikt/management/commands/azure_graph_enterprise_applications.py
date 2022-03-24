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

		# det antas i denne implementeringen at det ikke skjer endringer på en permissionscope ID
		def servicePrincipalsLookup(resourceAppId):
			# for en enkel forklaring på feltene, les https://joonasw.net/view/defining-permissions-and-roles-in-aad
			client = GraphClient(credential=client_credential, api_version='beta')
			query = "/servicePrincipals?filter=appId eq '%s'" % (resourceAppId)
			resp = client.get(query)
			load_appdata = json.loads(resp.text)
			#print(json.dumps(load_appdata, sort_keys=True, indent=4))
			for permissionScope in load_appdata["value"][0]["publishedPermissionScopes"]: # Delegated
				try:
					s = AzurePublishedPermissionScopes.objects.get(scope_id=permissionScope["id"])
				except:
					s = AzurePublishedPermissionScopes.objects.create(scope_id=permissionScope["id"])

				s.resourceAppId = resourceAppId
				s.resourceAppStr = load_appdata["value"][0]["appDisplayName"]
				s.permission_type = "Delegated"
				s.isEnabled = permissionScope["isEnabled"]
				s.value = permissionScope["value"]
				s.grant_type = [permissionScope["type"]]
				s.adminConsentDescription = permissionScope["adminConsentDescription"]
				s.adminConsentDisplayName = permissionScope["adminConsentDisplayName"]
				s.userConsentDescription = permissionScope["userConsentDescription"]
				s.userConsentDisplayName = permissionScope["userConsentDisplayName"]
				s.save()
				print("Added PermissionScope %s" % permissionScope["value"])

			for role in load_appdata["value"][0]["appRoles"]: # Application
				try:
					s = AzurePublishedPermissionScopes.objects.get(scope_id=role["id"])
				except:
					s = AzurePublishedPermissionScopes.objects.create(scope_id=role["id"])

				s.resourceAppId = resourceAppId
				s.resourceAppStr = load_appdata["value"][0]["appDisplayName"]
				s.permission_type = "Application"
				s.isEnabled = role["isEnabled"]
				s.value = role["value"]
				s.grant_type = role["allowedMemberTypes"]
				s.adminConsentDescription = role["description"]
				s.adminConsentDisplayName = role["displayName"]
				s.userConsentDescription = ""
				s.userConsentDisplayName = ""
				s.save()
				print("Added role %s" % role["value"])

			logg_message = "servicePrincipalsLookup() har lastet rettigheter fra %s" % (load_appdata["value"][0]["appDisplayName"])
			logg_entry = ApplicationLog.objects.create(
					event_type='Azure Enterprise Applications',
					message=logg_message,
				)
			#print(logg_message)



		def permissionScopeLookup(resourceAppId, scope_id):
			# finnes scope_id fra før av?
			try:
				# den eksisterer, og vi kan returnere den
				permissionScope = AzurePublishedPermissionScopes.objects.get(scope_id=scope_id)
				return permissionScope
			except:
				# den eksisterer ikke, og vi må hente den ned fra Azure.
				print("Fant ikke permissionScope, slår opp..")
				servicePrincipalsLookup(resourceAppId)
				try:
					# vi prøver nok en gang. Nå bør den eksistere.
					permissionScope = AzurePublishedPermissionScopes.objects.get(scope_id=scope_id)
					return permissionScope
				except:
					return None


		# tester
		#servicePrincipalsLookup("00000002-0000-0000-c000-000000000000")
		#print(permissionScopeLookup("00000002-0000-0000-c000-000000000000", "a42657d6-7f20-40e3-b6f0-cee03008a62a"))


		def load_azure_apps():
			client = GraphClient(credential=client_credential, api_version='beta')

			APPLICATIONS_FOUND = 0

			def load_next_response(nextLink):
				resp = client.get(nextLink)
				load_appdata = json.loads(resp.text)
				#print(json.dumps(load_appdata, sort_keys=True, indent=4))
				extract_and_store(load_appdata)
				try:
					return load_appdata["@odata.nextLink"]
				except:
					return False

			def extract_and_store(json_text):

				for app in json_text["value"]:
					nonlocal APPLICATIONS_FOUND
					APPLICATIONS_FOUND += 1
					try:
						a = AzureApplication.objects.get(appId=app['appId'])
					except:
						a = AzureApplication.objects.create(appId=app['appId'])

					a.createdDateTime = parser.parse(app['createdDateTime']) # 2021-12-15T13:10:38Z
					a.displayName = app['displayName']
					print(app['displayName'])
					#slett tidligere koblinger:
					a.requiredResourceAccess.clear()
					for rra in app['requiredResourceAccess']: #publishedPermissionScopes hvis serviceprincipal
						resourceAppId = rra["resourceAppId"]
						for ra in rra["resourceAccess"]:
							scope_id = ra["id"]
							a.requiredResourceAccess.add(permissionScopeLookup(resourceAppId, scope_id))

					a.save()

					# legger til alle nøkler som identifiseres og kobler dem til riktig app
					# det antas at tabellen med nøkler tømmes ved hver kjøring, se #1

					for keycredential in app['keyCredentials']:
						key_end_date = parser.parse(keycredential["endDateTime"])
						k = AzureApplicationKeys.objects.create(
								applcaion_ref=a, # a i the application we are looping through
								key_id=keycredential["keyId"],
								display_name=keycredential["displayName"],
								key_type=keycredential["type"],
								key_usage=keycredential["usage"],
								end_date_time=key_end_date,
								)

					for passwordcredential in app['passwordCredentials']:
						key_end_date = parser.parse(passwordcredential["endDateTime"])
						k = AzureApplicationKeys.objects.create(
								applcaion_ref=a, # a i the application we are looping through
								key_id=passwordcredential["keyId"],
								display_name=passwordcredential["displayName"],
								key_type="Client Secret",
								key_usage="",
								end_date_time=key_end_date,
								hint=passwordcredential["hint"]
								)


			safety = 10 # må justeres om det blir veldig mange apper.
			results_per_page = 100
			maximum_results = (safety + 1) * results_per_page

			# fjerner alle registrerte nøkler (keys) (#1)
			AzureApplicationKeys.objects.all().delete()

			initial_query = '/applications?$top=%s' % results_per_page
			next_page = load_next_response(initial_query)
			while(next_page):
				next_page = load_next_response(next_page)
				safety -= 1
				if safety <= 0:
					break

			logg_message = "Fant %s applikasjoner. Maksgrense er satt til %s" % (APPLICATIONS_FOUND, maximum_results)
			logg_entry = ApplicationLog.objects.create(
					event_type='Azure Enterprise Applications',
					message=logg_message,
				)
			print(logg_message)


		load_azure_apps()