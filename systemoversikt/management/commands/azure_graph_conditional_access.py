# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import os, time
import simplejson as json
from datetime import datetime
from django.utils import timezone
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from systemoversikt.views import push_pushover
from systemoversikt.models import *
from deepdiff import DeepDiff

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "azure_ad_conditional_access"
		LOG_EVENT_TYPE = "Conditional Access"
		KILDE = "Azure Graph"
		PROTOKOLL = "REST"
		BESKRIVELSE = "Conditional Access-regler (CA-regler)"
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

		try:
			client_credential = ClientSecretCredential(
					tenant_id=os.environ['AZURE_TENANT_ID'],
					client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
					client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
			)

			client = GraphClient(credential=client_credential, api_version='v1.0')
			query = "/identity/conditionalAccess/policies"
			resp = client.get(query)

			if resp.status_code != 200:
				raise requests.ConnectionError("Failed to connect to graph API: Got HTTP {resp.status_code}")

			print(f"HTTP {resp.status_code} OK")

			#print(json.dumps(json.loads(resp.text), indent=4))

			this_policy = EntraIDConditionalAccessPolicies.objects.create(json_policy=resp.text)
			print(f"Opprettet policy med pk={this_policy.pk}")


			try:
				last_policy_pk = this_policy.pk - 1
				last_policy = EntraIDConditionalAccessPolicies.objects.get(pk=last_policy_pk)
				print(f"Sammenlikner med policy med pk={last_policy.pk}")

				# Parse JSON strings into dictionaries
				dict_old = json.loads(last_policy.json_policy)
				dict_new = json.loads(this_policy.json_policy)

				# Find the differences
				diff = DeepDiff(dict_old, dict_new, ignore_order=True)
				print(f"Endring:\n{diff}")

				changes_detected = bool(diff)
				this_policy.modification = changes_detected
				this_policy.changes = diff
				this_policy.save()

			except Exception as e:
				error_message = f"Kan ikke sammenlikne med forrige version av policy: {e}"
				print(error_message)
				logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=error_message)
				pass



			print(f"Slår opp diverse GUIDs..")

			def find_nested_keys(data, key):
				if isinstance(data, dict):
					for k, v in data.items():
						if k == key:
							yield v
						if isinstance(v, (dict, list)):
							yield from find_nested_keys(v, key)
				elif isinstance(data, list):
					for item in data:
						yield from find_nested_keys(item, key)


			def lookup_user(guid):
				if guid == "None" or guid == "All" or guid == "GuestsOrExternalUsers":
					return AzureUser.objects.none()
				user, created = AzureUser.objects.get_or_create(guid=guid)
				if not created: # hvis den eksisterete fra før av
					#print(f"Fant treff på {guid}")
					return user

				user_url = f'/users/{guid}'
				user_response = client.get(user_url)
				time.sleep(0.5)

				if user_response.status_code == 200:
					user_data = user_response.json()
					user.userPrincipalName = user_data.get('userPrincipalName')
					user.displayName = user_data.get('displayName')
					user.mail = user_data.get('mail')
					print(f"Lagrer data om {guid}")
					user.save()
					return user
				else:
					print(f'Error: {user_response.status_code}')
					print(user_response.json())
					return AzureUser.objects.none()


			def lookup_group(guid):
				if guid == "None":
					return AzureGroup.objects.none()
				group, created = AzureGroup.objects.get_or_create(guid=guid)
				if not created: # hvis den eksisterete fra før av
					print(f"Fant treff på {guid}")
					return group

				group_url = f'/groups/{guid}'
				group_response = client.get(group_url)
				time.sleep(0.5)

				if group_response.status_code == 200:
					group_data = group_response.json()
					group.description = group_data.get('description')
					group.displayName = group_data.get('displayName')
					group.onPremisesSamAccountName = group_data.get('onPremisesSamAccountName')
					print(f"Lagrer data om {guid}")
					group.save()
					return group
				else:
					print(f'Error: {group_response.status_code}')
					print(group_response.json())
					return AzureGroup.objects.none()


			def lookup_directory_role(guid):
				if guid == "None" or guid == "All":
					return AzureDirectoryRole.objects.none()
				role, created = AzureDirectoryRole.objects.get_or_create(guid=guid)
				if not created: # hvis den eksisterete fra før av
					print(f"Fant treff på {guid}")
					return role

				role_url = f'/directoryRoles/{guid}'
				role_response = client.get(role_url)
				time.sleep(0.5)

				if role_response.status_code == 200:
					role_data = role_response.json()
					print(role_data)
					#role.description = role_data.get('description')
					#role.displayName = role_data.get('displayName')
					#role.onPremisesSamAccountName = role_data.get('onPremisesSamAccountName')
					print(f"Lagrer data om {guid}")
					role.save()
					return role
				else:
					print(f'Error: {role_response.status_code}')
					print(role_response.json())
					return AzureDirectoryRole.objects.none()

			policy = json.loads(resp.text)

			user_fields = ["excludeUsers", "includeUsers"]
			user_guids = []
			for field in user_fields:
				user_guids.extend(list(find_nested_keys(policy, field)))
			user_guids = set([user for sublist in user_guids for user in sublist])
			#print(f"Users: {user_guids}")


			group_fields = ["excludeGroups", "includeGroups"]
			group_guids = []
			for field in group_fields:
				group_guids.extend(list(find_nested_keys(policy, field)))
			group_guids = set([group for sublist in group_guids for group in sublist])
			#print(f"\n\nGroups: {group_guids}")


			role_fields = ["includeRoles", "excludeRoles"]
			role_guids = []
			for field in role_fields:
				role_guids.extend(list(find_nested_keys(policy, field)))
			role_guids = set([role for sublist in role_guids for role in sublist])
			#print(f"\n\nRoles: {role_guids}")

			for user in user_guids:
				print(lookup_user(user))


			for group in group_guids:
				print(lookup_group(group))


			# trenger directory read først
			#for role in role_guids:
			#	print(lookup_directory_role(role))


			logg_message = f"Innlasting av policy utført"
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message
			runtime_t1 = time.time()
			logg_total_runtime = int(runtime_t1 - runtime_t0)
			int_config.runtime = logg_total_runtime
			int_config.helsestatus = "Vellykket"
			int_config.save()



		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			import traceback
			int_config.helsestatus = f"Feilet\n{traceback.format_exc()}"
			int_config.save()
			push_pushover(f"{SCRIPT_NAVN} feilet") # Push error

