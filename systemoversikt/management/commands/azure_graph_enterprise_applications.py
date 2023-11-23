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

		api_version = "v1.0"

		# det antas i denne implementeringen at det ikke skjer endringer på en permissionscope ID
		def servicePrincipalsLookup(resourceAppId):
			# for en enkel forklaring på feltene, les https://joonasw.net/view/defining-permissions-and-roles-in-aad
			client = GraphClient(credential=client_credential, api_version=api_version)
			query = "/servicePrincipals?filter=appId eq '%s'" % (resourceAppId)
			resp = client.get(query)
			load_appdata = json.loads(resp.text)
			#print(json.dumps(load_appdata, sort_keys=True, indent=4))
			if "value" in load_appdata:
				for permissionScope in load_appdata["value"][0]["publishedPermissionScopes"]: # Delegated
					try:
						s = AzurePublishedPermissionScopes.objects.get(scope_id=permissionScope["id"])
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
					#print("Added PermissionScope %s" % permissionScope["value"])

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
					#print("Added role %s" % role["value"])

				logg_message = "servicePrincipalsLookup() har lastet rettigheter fra %s" % (load_appdata["value"][0]["appDisplayName"])
				logg_entry = ApplicationLog.objects.create(
						event_type=LOG_EVENT_TYPE,
						message=logg_message,
					)
				print(logg_message)
			else:
				# Det ble ikke funnet noen rettigheter
				logg_message = "servicePrincipalsLookup() fant ingen rettigheter"
				logg_entry = ApplicationLog.objects.create(
						event_type=LOG_EVENT_TYPE,
						message=logg_message,
					)
				print(logg_message)


		def permissionScopeLookup(resourceAppId, scope_id):
			# finnes scope_id fra før av?
			try:
				# den eksisterer, og vi kan returnere den
				permissionScope = AzurePublishedPermissionScopes.objects.get(scope_id=scope_id)
				return permissionScope
			except:
				# den eksisterer ikke, og vi må hente den ned fra Azure.
				print(f"Fant ikke permissionScope {scope_id}. Slår opp..")
				servicePrincipalsLookup(resourceAppId)
				try:
					# vi prøver nok en gang. Nå bør den eksistere.
					permissionScope = AzurePublishedPermissionScopes.objects.get(scope_id=scope_id)
					return permissionScope
				except:
					print(f"permissionScopeLookup() returnerte Null for app {resourceAppId} med scope_id {scope_id}")
					return None


		# tester
		#servicePrincipalsLookup("00000002-0000-0000-c000-000000000000")
		#print(permissionScopeLookup("00000002-0000-0000-c000-000000000000", "a42657d6-7f20-40e3-b6f0-cee03008a62a"))


		def load_azure_apps():
			client = GraphClient(credential=client_credential, api_version=api_version)

			def load_next_response_app(nextLink):
				resp = client.get(nextLink)
				load_appdata = json.loads(resp.text)
				#print(json.dumps(load_appdata, sort_keys=True, indent=4))
				extract_and_store_app(load_appdata)
				try:
					return load_appdata["@odata.nextLink"]
				except:
					return False

			def extract_and_store_app(json_text):
				for app in json_text["value"]:
					nonlocal APPLICATIONS_FOUND_ALL
					APPLICATIONS_FOUND_ALL += 1

					servicePrincipalType = app.get('servicePrincipalType')
					displayName = app.get('displayName')

					#print(f"{APPLICATIONS_FOUND_ALL}: {servicePrincipalType} {displayName}")

					try:
						a = AzureApplication.objects.get(appId=app['appId'])
					except:
						a = AzureApplication.objects.create(appId=app['appId'])

					a.createdDateTime = parser.parse(app['createdDateTime']) # 2021-12-15T13:10:38Z
					a.displayName = displayName
					a.active = True if app.get('accountEnabled') == True else False
					a.servicePrincipalType = servicePrincipalType
					a.tags = app.get('tags')
					a.notes = app.get('notes')
					a.requiredResourceAccess.clear()
					a.publisherName = app.get('publisherName')
					a.save()

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

					displayName = app.get('displayName')
					#print(f"{APPLICATIONS_FOUND}: {displayName}")

					try:
						a = AzureApplication.objects.get(appId=app['appId'])
					except:
						print(f"Fant ikke app {displayName}")
						continue

					a.from_applications = True

					#slett tidligere rettighetskoblinger og sett dem på nytt
					a.requiredResourceAccess.clear()
					if 'requiredResourceAccess' in app:
						for rra in app['requiredResourceAccess']: #publishedPermissionScopes hvis serviceprincipal
							resourceAppId = rra["resourceAppId"]
							for ra in rra["resourceAccess"]:
								scope_id = ra["id"]
								a.requiredResourceAccess.add(permissionScopeLookup(resourceAppId, scope_id))
					a.save()

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

			# henter inn alle azure apps
			APPLICATIONS_FOUND_ALL = 0
			initial_query = '/servicePrincipals?$select=appId,notes,publisherName,displayName,accountEnabled,createdDateTime,tags,servicePrincipalType,keyCredentials,passwordCredentials'

			next_page = load_next_response_app(initial_query)
			while(next_page):
				next_page = load_next_response_app(next_page)

			# henter inn mer informasjon om alle application
			APPLICATIONS_FOUND = 0
			initial_query = '/applications?$select=appId,displayName,requiredResourceAccess,keyCredentials,passwordCredentials'

			next_page = load_next_response(initial_query)
			while(next_page):
				next_page = load_next_response(next_page)


			#sette applikasjoner som ikke har vært sett til deaktivt
			tidligere = timezone.now() - timedelta(hours=6) # 6 timer gammelt
			deaktive_apper = AzureApplication.objects.filter(sist_oppdatert__lte=tidligere)
			for a in deaktive_apper:
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
