# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import os, time
import simplejson as json
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from systemoversikt.models import *
from dateutil import parser
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover

class Command(BaseCommand):

	ANTALL_GRAPH_KALL = 0

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
		int_config.helsestatus = "Forbereder"
		int_config.save()

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
		runtime_t0 = time.time()

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
				query = f"/servicePrincipals?filter=appId eq '{resourceAppId}'"
			if mode == "id":
				query = f"/servicePrincipals?filter=id eq '{resourceAppId}'"

			resp = client.get(query)
			Command.ANTALL_GRAPH_KALL += 1
			load_appdata = json.loads(resp.text)
			#print(json.dumps(load_appdata, sort_keys=True, indent=4))
			if "value" in load_appdata:
				for permissionScope in load_appdata["value"][0]["publishedPermissionScopes"]: # Delegated
					try:
						s = AzurePublishedPermissionScopes.objects.get(scope_id=permissionScope["id"])
						continue # den finnes og vi gjør ingen ting
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
					print(f"La til delegert tilgang {permissionScope['value']}")

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
					print(f"La til applikasjonsrole {role['value']}")

				for resourceSpecific in load_appdata["value"][0]["resourceSpecificApplicationPermissions"]:  # Application
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
					print(f"La til applikasjonsrolle {resourceSpecific['value']}")

				logg_message = "servicePrincipalsLookup() har lastet rettigheter fra %s" % (load_appdata["value"][0]["appDisplayName"])
			else:
				# Det ble ikke funnet noen rettigheter
				logg_message = f"servicePrincipalsLookup() fant ingen rettigheter for {resourceAppId} {mode}"
				print(logg_message)
				pass


		def permissionScopeLookup(mode, resourceAppId, scope_id):
			try:
				permissionScope = AzurePublishedPermissionScopes.objects.get(scope_id=scope_id)
				return permissionScope
			except:
				servicePrincipalsLookup(resourceAppId, mode)

				try:
					# vi prøver nok en gang. Nå bør den eksistere.
					permissionScope = AzurePublishedPermissionScopes.objects.get(scope_id=scope_id)
					return permissionScope
				except:
					print(f"⚠️ Feilet oppslag på rettigheten {scope_id}")
					return None


		def permissionGrantLookup(mode, grant, a):
			resourceAppId = grant["resourceId"]
			scope_str = grant["scope"]
			scopes = []
			for scope_part in scope_str.strip().split(" "):
				try:
					permissionScope = AzurePublishedPermissionScopes.objects.get(resourceAppId=resourceAppId, value=scope_part, permission_type="Delegated")
					scopes.append(permissionScope)
					continue
				except:
					servicePrincipalsLookup(resourceAppId, mode)

					# vi prøver nok en gang. Nå bør den eksistere.
					matches = AzurePublishedPermissionScopes.objects.filter(resourceAppId=resourceAppId, value=scope_part, permission_type="Delegated")

					if matches.count() == 1:
						scopes.append(matches.first())
						continue
					elif matches.count() > 1:
						print(f"⚠️ {matches.count()} treff for rettigheten {scope_part} for {a.displayName}")
					else:
						print(f"⚠️ Ingen treff for rettigheten {scope_part} for {a.displayName}")

			# ferdig med loop, returner
			return scopes


		### Denne er tydeligvis ikke aktiv..
		def lookup_userDisplayName(user):
			#client = GraphClient(credential=client_credential, api_version=api_version)
			#query = f"/users/{user}"
			#print(query)
			#load_appdata = json.loads(client.get(query).text)
			return "" # for å anonymisere i produksjon


		def load_azure_apps():
			client = GraphClient(credential=client_credential, api_version=api_version)

			def load_next_response_servicePrincipals(nextLink):
				resp = client.get(nextLink)
				Command.ANTALL_GRAPH_KALL += 1
				load_appdata = json.loads(resp.text)
				#print(json.dumps(load_appdata, sort_keys=True, indent=4))
				extract_and_store_servicePrincipals(load_appdata)

				#print("Ferdig med en side, sjekker om det er flere..")

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

					#print(f"{APPLICATIONS_FOUND_ALL}: {servicePrincipalType} {displayName}")

					try:
						a = AzureApplication.objects.get(appId=appId)
					except:
						a = AzureApplication.objects.create(appId=appId)

					object_id = app.get('id')

					a.objectId = object_id
					a.json_response = app
					a.createdDateTime = parser.parse(app['createdDateTime']) # 2021-12-15T13:10:38Z
					a.displayName = displayName
					a.active = True if app.get('accountEnabled') == True else False
					a.servicePrincipalType = servicePrincipalType
					a.tags = app.get('tags')
					a.notes = app.get('notes')
					a.publisherName = app.get('publisherName')
					a.save()


					def getOauth2PermissionGrants(object_id):
						client = GraphClient(credential=client_credential, api_version=api_version)
						query = f"/servicePrincipals/{object_id}/oauth2PermissionGrants"

						#print(f"Slår opp oauth2PermissionGrants for {object_id}")

						Command.ANTALL_GRAPH_KALL += 1
						return json.loads(client.get(query).text)


					if servicePrincipalType != "ManagedIdentity":  # vi slår ikke opp for ManagedIdentity
						grant_data = getOauth2PermissionGrants(object_id)
						for grant in grant_data["value"]:

							if grant["consentType"] == "AllPrincipals":
								#print(f"AllPrincipals grant: {grant}")
								scopes = permissionGrantLookup("id", grant, a)
								for scope in scopes:
									a.requiredResourceAccess.add(scope)

							if grant["consentType"] == "Principal":
								#print(f"Principal grant: {grant}")
								user = grant["principalId"]
								scopes = grant["scope"]
								userDisplayName = lookup_userDisplayName(user)  # er anonymisert ved at den alltid returnerer ""
								AzureUserConsents.objects.create(appId=appId,appDisplayName=displayName,userId=user,scopes=scopes,userDisplayName=userDisplayName)
								#print(f"User {user} has consented for app {displayName} for scopes {scopes}")

							if grant["consentType"] not in ["AllPrincipals", "Principal"]:
								print(f"⚠️ Ukjent consentType {grant['consentType']}")


					# legger til alle nøkler som identifiseres og kobler dem til riktig app
					for keycredential in app['keyCredentials']:
						key_end_date = parser.parse(keycredential["endDateTime"])
						if not AzureApplicationKeys.objects.filter(key_id=keycredential["keyId"], application_ref=a).exists():
							k = AzureApplicationKeys.objects.create(
									application_ref=a,
									key_id=keycredential["keyId"],
									display_name=keycredential["displayName"],
									key_type=keycredential["type"],
									key_usage=keycredential["usage"],
									end_date_time=key_end_date,
									)
							#print(f"La til keycredential for {keycredential['displayName']}")

					for passwordcredential in app['passwordCredentials']:
						key_end_date = parser.parse(passwordcredential["endDateTime"])
						if not AzureApplicationKeys.objects.filter(key_id=passwordcredential["keyId"], application_ref=a).exists():
							k = AzureApplicationKeys.objects.create(
									application_ref=a,
									key_id=passwordcredential["keyId"],
									display_name=passwordcredential["displayName"],
									key_type="Client Secret",
									key_usage="",
									end_date_time=key_end_date,
									hint=passwordcredential["hint"]
									)
							#print(f"La til keycredential for {keycredential['displayName']}")


			def owner_for_sp(object_id):
				if object_id == None:
					return "Ugyldig object ID"
				client = GraphClient(credential=client_credential, api_version=api_version)
				query = f"/servicePrincipals/{object_id}/owners?$select=displayName,userPrincipalName"
				Command.ANTALL_GRAPH_KALL += 1
				return client.get(query).text


			def assigned_to_for_sp(object_id):
				if object_id == None:
					return "Ugyldig object ID"
				client = GraphClient(credential=client_credential, api_version=api_version)
				query = f"/servicePrincipals/{object_id}/appRoleAssignedTo"
				Command.ANTALL_GRAPH_KALL += 1
				return client.get(query).text


			def load_next_response_applications(nextLink):
				resp = client.get(nextLink)
				Command.ANTALL_GRAPH_KALL += 1
				load_appdata = json.loads(resp.text)
				#print(json.dumps(load_appdata, sort_keys=True, indent=4))
				extract_and_store_applications(load_appdata)

				#print("Ferdig med en side, sjekker om det er flere..")

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
						print(f"⚠️ Fant ikke applikasjonen {displayName}")
						continue

					a.from_applications = True
					a.assigned_to = assigned_to_for_sp(a.objectId)
					a.owner = owner_for_sp(a.objectId)
					a.save()

					# sett rettighetskoblinger. dette kan virke redundant, men denne matcher de som feiler i steget over med service principals.
					if 'requiredResourceAccess' in app:
						for rra in app['requiredResourceAccess']:
							resourceAppId = rra["resourceAppId"]
							for ra in rra["resourceAccess"]:
								scope_id = ra["id"]
								a.requiredResourceAccess.add(permissionScopeLookup("appid", resourceAppId, scope_id))


					# legger til alle nøkler som identifiseres og kobler dem til riktig app
					for keycredential in app['keyCredentials']:
						key_end_date = parser.parse(keycredential["endDateTime"])
						if not AzureApplicationKeys.objects.filter(key_id=keycredential["keyId"],application_ref=a).exists():
							k = AzureApplicationKeys.objects.create(
									application_ref=a,
									key_id=keycredential["keyId"],
									display_name=keycredential["displayName"],
									key_type=keycredential["type"],
									key_usage=keycredential["usage"],
									end_date_time=key_end_date,
									)
							#print(f"La til keycredential for {keycredential['displayName']}")

					for passwordcredential in app['passwordCredentials']:
						key_end_date = parser.parse(passwordcredential["endDateTime"])
						if not AzureApplicationKeys.objects.filter(key_id=passwordcredential["keyId"],application_ref=a).exists():
							k = AzureApplicationKeys.objects.create(
									application_ref=a,
									key_id=passwordcredential["keyId"],
									display_name=passwordcredential["displayName"],
									key_type="Client Secret",
									key_usage="",
									end_date_time=key_end_date,
									hint=passwordcredential["hint"]
									)
							#print(f"La til passwordcredential for {passwordcredential['displayName']}")


			# fjerner alle registrerte nøkler (keys) (#1)
			print("☕ Sletter all nøkkelinformasjon")
			AzureApplicationKeys.objects.all().delete()
			print("☕ Sletter all consent-informasjon")
			AzureUserConsents.objects.all().delete()

			# fjerner alle tidligere rettigheter
			print("☕ Sletter all rettighetsinformasjon")
			for app in AzureApplication.objects.all():
				app.requiredResourceAccess.clear() # trenger ikke lagre eksplisitt

			# henter inn alle service principals
			APPLICATIONS_FOUND_ALL = 0
			initial_query = '/servicePrincipals?$select=appId,id,notes,publisherName,displayName,accountEnabled,createdDateTime,tags,servicePrincipalType,keyCredentials,passwordCredentials'

			print("☕ Laster inn azure apps via /servicePrincipals")
			next_page = load_next_response_servicePrincipals(initial_query)
			while(next_page):
				next_page = load_next_response_servicePrincipals(next_page)

			# henter inn mer informasjon om alle application
			print("\n☕ Laster inn alle application via /applications")
			APPLICATIONS_FOUND = 0
			initial_query = '/applications?$select=appId,displayName,requiredResourceAccess,keyCredentials,passwordCredentials'

			next_page = load_next_response_applications(initial_query)
			while(next_page):
				next_page = load_next_response_applications(next_page)


			# sette applikasjoner som ikke har vært sett til deaktivt
			print("\n☕ Sletter applikasjoner som ikke har blitt oppdatert denne runden")
			tidligere = timezone.now() - timedelta(hours=6) # 6 timer gammelt
			deaktive_apper = AzureApplication.objects.filter(sist_oppdatert__lte=tidligere)
			for a in deaktive_apper:
				a.delete()
				print("Slettet %s" % a)

			# telle opp hvor mange graph-tilganger hver SP har
			print("☕ Teller opp og lagrer hvor mange graph-rettigheter hver SP har")
			rettigheter_totalt = 0
			for sp in AzureApplication.objects.all():
				sp.antall_graph_rettigheter = AzurePublishedPermissionScopes.objects.filter(azure_applications=sp).count()
				rettigheter_totalt += sp.antall_graph_rettigheter
				sp.save()


			# varsle om nye SP via pushover
			print("☕ Klargjør melding om nye apper til Pushover")
			message = "Nye SP i Azure med rettigheter:\n"
			antall_nye = 0
			limit = 10
			for sp in AzureApplication.objects.filter(opprettet__gte=tidligere):
				if limit > 0:
					if sp.antall_permissions() > 0:
						message += f"{sp.displayName} autonivå {sp.risikonivaa_autofill()}\n"
						antall_nye += 1
						limit -= 1
				else:
					message += f"Det er flere..\n"
					break

			print(message)
			if antall_nye > 0:
				push_pushover(message)

			# sende e-post om nøkler og sertifikater som snart utgår skjer i eget script som må kjøre etter dette.


			# logge og fullføre
			logg_message = f"\n ☕ Fant {APPLICATIONS_FOUND_ALL} applikasjoner under /servicePrincipals og {APPLICATIONS_FOUND} under /applications. Utførte {Command.ANTALL_GRAPH_KALL} kall. Det er {rettigheter_totalt} rettigheter totalt."
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
				)
			print(logg_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message

			runtime_t1 = time.time()
			logg_total_runtime = int(runtime_t1 - runtime_t0)
			int_config.runtime = logg_total_runtime
			int_config.elementer = int(APPLICATIONS_FOUND_ALL) +  int(APPLICATIONS_FOUND)
			int_config.helsestatus = "Vellykket"
			int_config.save()

		# eksekver
		try:
			load_azure_apps()

		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			import traceback
			int_config.helsestatus = f"Feilet\n{traceback.format_exc()}"
			int_config.save()
			push_pushover(f"{SCRIPT_NAVN} feilet") # Push error

