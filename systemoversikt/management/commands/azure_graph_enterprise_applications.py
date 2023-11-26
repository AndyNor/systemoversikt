# -*- coding: utf-8 -*-
#Graph-klienten heter "UKE - Kartoteket - Lesetilgang MS Graph"

from django.core.management.base import BaseCommand
import os
import simplejson as json
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from systemoversikt.models import *
from dateutil import parser
from django.utils import timezone
from datetime import timedelta
from systemoversikt.views import push_pushover

class Command(BaseCommand):
	def handle(self, **options):

		# initielt oppsett
		INTEGRASJON_KODEORD = "azure_enterprise_applications"
		LOG_EVENT_TYPE = "Azure enterprise applications"
		KILDE = "Azure Graph"
		PROTOKOLL = "REST"
		BESKRIVELSE = "Enterprise applications og nøkkelmetadata"
		FILNAVN = ""
		URL = ""
		FREKVENS = "Hver natt"

		try:
			int_config = IntegrasjonKonfigurasjon.objects.get(kodeord=INTEGRASJON_KODEORD)
		except:
			int_config = IntegrasjonKonfigurasjon.objects.create(
					kodeord=INTEGRASJON_KODEORD,
					kilde=KILDE,
					protokoll=PROTOKOLL,
					informasjon=BESKRIVELSE,
					sp_filnavn=FILNAVN,
					url=URL,
					frekvensangivelse=FREKVENS,
					log_event_type=LOG_EVENT_TYPE,
				)

		SCRIPT_NAVN = os.path.basename(__file__)
		int_config.script_navn = SCRIPT_NAVN
		int_config.sp_filnavn = json.dumps(FILNAVN)
		int_config.save()

		print(f"------ Starter {SCRIPT_NAVN} ------")

		client_credential = ClientSecretCredential(
				tenant_id=os.environ['AZURE_TENANT_ID'],
				client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
				client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
		)

		api_version = "beta"

		# det antas i denne implementeringen at det ikke skjer endringer på en permissionscope ID
		def servicePrincipalsLookup(resourceAppId, mode):
			# for en enkel forklaring på feltene, les https://joonasw.net/view/defining-permissions-and-roles-in-aad
			client = GraphClient(credential=client_credential, api_version=api_version)
			if mode == "appid":
				query = "/servicePrincipals?filter=appId eq '%s'" % (resourceAppId)
			if mode == "id":
				query = "/servicePrincipals?filter=id eq '%s'" % (resourceAppId)
			#print(query)
			resp = client.get(query)
			load_appdata = json.loads(resp.text)
			#print(json.dumps(load_appdata, sort_keys=True, indent=4))
			if "value" in load_appdata:
				for permissionScope in load_appdata["value"][0]["publishedPermissionScopes"]: # Delegated
					try:
						s = AzurePublishedPermissionScopes.objects.get(scope_id=permissionScope["id"])
						continue
					except:
						s = AzurePublishedPermissionScopes.objects.create(scope_id=permissionScope["id"])

					s.resourceAppId = resourceAppId
					s.resourceAppStr = load_appdata["value"][0]["appDisplayName"]
					s.permission_type = "Delegated"
					s.isEnabled = permissionScope["isEnabled"]
					#if permissionScope["value"] == "":
					#	print(permissionScope)
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
						continue
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

				for resourceSpecific in load_appdata["value"][0]["resourceSpecificApplicationPermissions"]:
					try:
						s = AzurePublishedPermissionScopes.objects.get(scope_id=resourceSpecific["id"])
						continue
					except:
						s = AzurePublishedPermissionScopes.objects.create(scope_id=resourceSpecific["id"])

					s.resourceAppId = resourceAppId
					s.resourceAppStr = load_appdata["value"][0]["appDisplayName"]
					s.permission_type = "Application"
					s.isEnabled = resourceSpecific["isEnabled"]
					s.value = resourceSpecific["value"]
					s.grant_type = None
					s.adminConsentDescription = resourceSpecific["description"]
					s.adminConsentDisplayName = resourceSpecific["displayName"]
					s.userConsentDescription = ""
					s.userConsentDisplayName = ""
					s.save()
					print("Added resourceSpecific %s" % resourceSpecific["value"])


				logg_message = "servicePrincipalsLookup() har lastet rettigheter fra %s" % (load_appdata["value"][0]["appDisplayName"])
				#logg_entry = ApplicationLog.objects.create(
				#		event_type=LOG_EVENT_TYPE,
				#		message=logg_message,
				#	)
				print(logg_message)
			else:
				# Det ble ikke funnet noen rettigheter
				logg_message = "servicePrincipalsLookup() fant ingen rettigheter"
				#logg_entry = ApplicationLog.objects.create(
				#		event_type=LOG_EVENT_TYPE,
				#		message=logg_message,
				#	)
				print(logg_message)


		def permissionScopeLookup(resourceAppId, scope_id, mode):
			# finnes scope_id fra før av?
			try:
				# den eksisterer, og vi kan returnere den
				permissionScope = AzurePublishedPermissionScopes.objects.get(scope_id=scope_id)
				return permissionScope
			except:
				# den eksisterer ikke, og vi må hente den ned fra Azure.
				print(f"Fant ikke permissionScope {scope_id}. Slår opp..")
				servicePrincipalsLookup(resourceAppId, mode)
				try:
					# vi prøver nok en gang. Nå bør den eksistere.
					permissionScope = AzurePublishedPermissionScopes.objects.get(scope_id=scope_id)
					return permissionScope
				except:
					print(f"permissionScopeLookup() returnerte Null for app {resourceAppId} med scope_id {scope_id}")
					return None


		def permissionGrantLookup(resourceAppId, scope_str, mode):
			tidligere_oppslag = False  # kun 1 oppslag per gjennomføring. Alle scopes skal være fra samme app.
			scopes = []
			for scope_part in scope_str.strip().split(" "):
				try:
					# den eksisterer, og vi kan returnere den
					permissionScope = AzurePublishedPermissionScopes.objects.get(resourceAppId=resourceAppId, value=scope_part, permission_type="Delegated")
					scopes.append(permissionScope)
					continue
				except:
					# den eksisterer ikke, og vi må hente den ned fra Azure.
					if tidligere_oppslag == False:
						print(f"Fant ikke permissionScope {scope_part}. Slår opp..")
						servicePrincipalsLookup(resourceAppId, mode)
						tidligere_oppslag = True
					try:
						# vi prøver nok en gang. Nå bør den eksistere.
						permissionScope = AzurePublishedPermissionScopes.objects.get(resourceAppId=resourceAppId, value=scope_part, permission_type="Delegated")
						scopes.append(permissionScope)
						continue
					except:
						print(f"permissionGrantLookup() returnerte Null for app {resourceAppId} med scope_id {scope_part}")
			return scopes

		def lookup_userDisplayName(user):
			#client = GraphClient(credential=client_credential, api_version=api_version)
			#query = f"/users/{user}"
			#print(query)
			#load_appdata = json.loads(client.get(query).text)
			return ""


		# tester
		#servicePrincipalsLookup("00000002-0000-0000-c000-000000000000")
		#print(permissionScopeLookup("00000002-0000-0000-c000-000000000000", "a42657d6-7f20-40e3-b6f0-cee03008a62a"))


		def load_azure_apps():
			client = GraphClient(credential=client_credential, api_version=api_version)

			def load_next_response_servicePrincipals(nextLink):
				resp = client.get(nextLink)
				load_appdata = json.loads(resp.text)
				#print(json.dumps(load_appdata, sort_keys=True, indent=4))
				extract_and_store_servicePrincipals(load_appdata)
				try:
					return load_appdata["@odata.nextLink"]
				except:
					return False

			def extract_and_store_servicePrincipals(json_text):
				for app in json_text["value"]:
					nonlocal APPLICATIONS_FOUND_ALL
					APPLICATIONS_FOUND_ALL += 1

					servicePrincipalType = app.get('servicePrincipalType')
					displayName = app.get('displayName')
					appId = app.get('appId')

					print(f"{APPLICATIONS_FOUND_ALL}: {servicePrincipalType} {displayName}")

					try:
						a = AzureApplication.objects.get(appId=appId)
					except:
						a = AzureApplication.objects.create(appId=appId)

					a.createdDateTime = parser.parse(app['createdDateTime']) # 2021-12-15T13:10:38Z
					a.displayName = displayName
					a.active = True if app.get('accountEnabled') == True else False
					a.servicePrincipalType = servicePrincipalType
					a.tags = app.get('tags')
					a.notes = app.get('notes')
					a.publisherName = app.get('publisherName')
					a.save()

					object_id = app.get('id')

					def getOauth2PermissionGrants(object_id):
						client = GraphClient(credential=client_credential, api_version=api_version)
						query = f"/servicePrincipals/{object_id}/oauth2PermissionGrants"
						#print(query)
						return json.loads(client.get(query).text)

					grant_data = getOauth2PermissionGrants(object_id)
					for grant in grant_data["value"]:
						if grant["consentType"] == "AllPrincipals":
							scopes = permissionGrantLookup(grant["resourceId"], grant["scope"], "id")
							for scope in scopes:
								a.requiredResourceAccess.add(scope)
						if grant["consentType"] == "Principal":
							user = grant["principalId"]
							scopes = grant["scope"]
							userDisplayName = lookup_userDisplayName(user)
							AzureUserConsents.objects.create(appId=appId,appDisplayName=displayName,userId=user,scopes=scopes,userDisplayName=userDisplayName)
							#print(f"User {user} has consented for app {displayName} for scopes {scopes}")



					# legger til alle nøkler som identifiseres og kobler dem til riktig app
					for keycredential in app['keyCredentials']:
						key_end_date = parser.parse(keycredential["endDateTime"])
						if not AzureApplicationKeys.objects.filter(key_id=keycredential["keyId"],applcaion_ref=a).exists():
							k = AzureApplicationKeys.objects.create(
									applcaion_ref=a,
									key_id=keycredential["keyId"],
									display_name=keycredential["displayName"],
									key_type=keycredential["type"],
									key_usage=keycredential["usage"],
									end_date_time=key_end_date,
									)

					for passwordcredential in app['passwordCredentials']:
						key_end_date = parser.parse(passwordcredential["endDateTime"])
						if not AzureApplicationKeys.objects.filter(key_id=passwordcredential["keyId"],applcaion_ref=a).exists():
							k = AzureApplicationKeys.objects.create(
									applcaion_ref=a,
									key_id=passwordcredential["keyId"],
									display_name=passwordcredential["displayName"],
									key_type="Client Secret",
									key_usage="",
									end_date_time=key_end_date,
									hint=passwordcredential["hint"]
									)



			def load_next_response_applications(nextLink):
				resp = client.get(nextLink)
				load_appdata = json.loads(resp.text)
				#print(json.dumps(load_appdata, sort_keys=True, indent=4))
				extract_and_store_applications(load_appdata)
				try:
					return load_appdata["@odata.nextLink"]
				except:
					return False

			def extract_and_store_applications(json_text):
				for app in json_text["value"]:
					nonlocal APPLICATIONS_FOUND
					APPLICATIONS_FOUND += 1

					displayName = app.get('displayName')
					#print(f"{APPLICATIONS_FOUND}: {displayName}")

					try:
						a = AzureApplication.objects.get(appId=app['appId'])
					except:
						print(f"Fant ikke app {displayName}")
						continue

					a.from_applications = True
					a.save()

					# sett rettighetskoblinger på nytt
					if 'requiredResourceAccess' in app:
						for rra in app['requiredResourceAccess']:
							resourceAppId = rra["resourceAppId"]
							for ra in rra["resourceAccess"]:
								scope_id = ra["id"]
								a.requiredResourceAccess.add(permissionScopeLookup(resourceAppId, scope_id,  "appid"))

					# legger til alle nøkler som identifiseres og kobler dem til riktig app
					for keycredential in app['keyCredentials']:
						key_end_date = parser.parse(keycredential["endDateTime"])
						if not AzureApplicationKeys.objects.filter(key_id=keycredential["keyId"],applcaion_ref=a).exists():
							k = AzureApplicationKeys.objects.create(
									applcaion_ref=a,
									key_id=keycredential["keyId"],
									display_name=keycredential["displayName"],
									key_type=keycredential["type"],
									key_usage=keycredential["usage"],
									end_date_time=key_end_date,
									)

					for passwordcredential in app['passwordCredentials']:
						key_end_date = parser.parse(passwordcredential["endDateTime"])
						if not AzureApplicationKeys.objects.filter(key_id=passwordcredential["keyId"],applcaion_ref=a).exists():
							k = AzureApplicationKeys.objects.create(
									applcaion_ref=a,
									key_id=passwordcredential["keyId"],
									display_name=passwordcredential["displayName"],
									key_type="Client Secret",
									key_usage="",
									end_date_time=key_end_date,
									hint=passwordcredential["hint"]
									)


			# fjerner alle registrerte nøkler (keys) (#1)
			AzureApplicationKeys.objects.all().delete()
			AzureUserConsents.objects.all().delete()

			# fjerner alle tidligere rettigheter
			for app in AzureApplication.objects.all():
				app.requiredResourceAccess.clear() # trenger ikke lagre eksplisitt

			# henter inn alle azure apps
			APPLICATIONS_FOUND_ALL = 0
			initial_query = '/servicePrincipals?$select=appId,id,notes,publisherName,displayName,accountEnabled,createdDateTime,tags,servicePrincipalType,keyCredentials,passwordCredentials'

			next_page = load_next_response_servicePrincipals(initial_query)
			while(next_page):
				next_page = load_next_response_servicePrincipals(next_page)

			# henter inn mer informasjon om alle application
			APPLICATIONS_FOUND = 0
			initial_query = '/applications?$select=appId,displayName,requiredResourceAccess,keyCredentials,passwordCredentials'

			next_page = load_next_response_applications(initial_query)
			while(next_page):
				next_page = load_next_response_applications(next_page)


			#sette applikasjoner som ikke har vært sett til deaktivt
			tidligere = timezone.now() - timedelta(hours=6) # 6 timer gammelt
			deaktive_apper = AzureApplication.objects.filter(sist_oppdatert__lte=tidligere)
			for a in deaktive_apper:
				if a.active:
					a.active = False
					a.save()
					print("%s satt deaktiv" % a)

			#logg dersom vellykket
			logg_message = f"Fant {APPLICATIONS_FOUND_ALL} applikasjoner under /servicePrincipals og {APPLICATIONS_FOUND} under /applications."
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
				)
			print(logg_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message
			int_config.save()

		# eksekver
		try:
			load_azure_apps()

		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# Push error
			push_pushover(f"{SCRIPT_NAVN} feilet")

