# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from systemoversikt.models import *
import os, requests, json, time
from datetime import datetime
from django.utils import timezone
from django.db.models import Q
from systemoversikt.views import push_pushover
import warnings

warnings.filterwarnings("ignore")

class Command(BaseCommand):

	ANTALL_GRAPH_KALL = 0
	ANTALL_LAGRET = 0
	ANTALL_FEILET = 0
	ANTALL_TOO_MANY_CALLS = 0
	ANTALL_UENDRET = 0
	users_to_be_processed = []

	SLEEP_BETWEEN = 0
	SLEEP_TOO_MANY = 20
	MAX_DETAILED_FETCHES = 15000

	def handle(self, **options):

		INTEGRASJON_KODEORD = "azure_ad_auth_methods_v2"
		LOG_EVENT_TYPE = 'Entra ID autentiseringsmetoder v2'
		KILDE = "Azure Graph"
		PROTOKOLL = "REST"
		BESKRIVELSE = "Hente ned brukeres autentiseringsmetoder (hybrid: rapport + detaljer ved endring)"
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

		try:

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")
			runtime_t0 = time.time()

			client_credential = ClientSecretCredential(
					tenant_id=os.environ['AZURE_TENANT_ID'],
					client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
					client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
			)
			api_version = "v1.0"
			client = GraphClient(credential=client_credential, api_version=api_version)


			# --- Phase 1: Fetch userRegistrationDetails report ---

			def get_bearer_token():
				token = client_credential.get_token("https://graph.microsoft.com/.default")
				return token.token

			def fetch_all_registration_details(token):
				"""Paginate through the report endpoint to get all users' registration status."""
				url = "https://graph.microsoft.com/v1.0/reports/authenticationMethods/userRegistrationDetails?$top=999"
				headers = {"Authorization": f"Bearer {token}"}
				all_users = {}
				page_count = 0
				while url:
					resp = requests.get(url, headers=headers)
					if resp.status_code == 429:
						retry_after = int(resp.headers.get("Retry-After", 30))
						print(f"Report endpoint: 429, venter {retry_after} sek...")
						time.sleep(retry_after)
						continue
					if resp.status_code != 200:
						raise Exception(f"Report endpoint returnerte HTTP {resp.status_code}: {resp.text[:500]}")
					data = resp.json()
					for user in data.get("value", []):
						upn = user.get("userPrincipalName", "").lower()
						if upn:
							all_users[upn] = user
					url = data.get("@odata.nextLink")
					page_count += 1
					if page_count % 10 == 0:
						print(f"  Rapport: hentet {len(all_users)} brukere over {page_count} sider...")
				return all_users


			# --- Phase 2: Determine who needs detailed refresh ---

			def parse_report_datetime(dt_string):
				"""Parse ISO datetime string from the report (UTC)."""
				if not dt_string:
					return None
				dt_string = dt_string.rstrip("Z")
				if "." in dt_string:
					dt_string = dt_string.split(".")[0]
				return datetime.strptime(dt_string, "%Y-%m-%dT%H:%M:%S")


			# --- Phase 3: Batch fetch detailed methods (same as v1) ---

			def create_batch_request(users):
				batch_requests = []
				for i, user in enumerate(users):
					upn = user.email
					batch_requests.append({
						"id": i,
						"method": "GET",
						"url": f"/users/{upn}/authentication/methods"
					})
				return {"requests": batch_requests}

			def lookup_and_save(users):
				batch_payload = create_batch_request(users)
				runtime_start = time.time()
				response = client.post('/$batch', json=batch_payload)
				runtime_end = time.time()
				time.sleep(Command.SLEEP_BETWEEN)
				Command.ANTALL_GRAPH_KALL += 1
				response_data = response.json()
				profiles_to_update = []

				for result in response_data.get('responses', []):
					user_id = int(result['id'])
					user = users[user_id]
					status = result['status']
					if status == 429:
						wait_sec = int(result['headers']['Retry-After']) + Command.SLEEP_TOO_MANY
						print(f"Too many requests, venter {wait_sec} sekunder...")
						Command.ANTALL_TOO_MANY_CALLS += 1
						time.sleep(wait_sec)
						Command.users_to_be_processed.extend(users)
						print(f"La gjeldende batch med brukere tilbake i køen...")
						break
					body = result['body']
					if status == 200:
						users_methods = []
						for auth_method in body["value"]:
							try:
								opprettet = auth_method["createdDateTime"]
							except:
								opprettet = None

							if auth_method['@odata.type'] == "#microsoft.graph.passwordAuthenticationMethod":
								users_methods.append({
									"status": "ok",
									"@odata.type": "#microsoft.graph.passwordAuthenticationMethod",
									"metode": "Passord",
									"beskrivelse": "Brukers passord for pålogging",
									"opprettet": opprettet,
								})
							if auth_method['@odata.type'] == "#microsoft.graph.emailAuthenticationMethod":
								users_methods.append({
									"status": "ok",
									"@odata.type": "#microsoft.graph.emailAuthenticationMethod",
									"metode": "E-post",
									"beskrivelse": "For tilbakestilling av passord",
									"opprettet": opprettet,
								})
							if auth_method['@odata.type'] == "#microsoft.graph.voiceAuthenticationMethod":
								users_methods.append({
									"status": "ok",
									"@odata.type": "#microsoft.graph.voiceAuthenticationMethod",
									"metode": "Oppringing til telefon",
									"beskrivelse": "Ekstra faktor ved pålogging",
									"opprettet": opprettet,
								})
							if auth_method['@odata.type'] == "#microsoft.graph.phoneAuthenticationMethod":
								users_methods.append({
									"status": "ok",
									"@odata.type": "#microsoft.graph.phoneAuthenticationMethod",
									"metode": "SMS engangskode",
									"beskrivelse": "Ekstra faktor ved pålogging og for tilbakestilling av passord",
									"opprettet": opprettet,
								})
							if auth_method['@odata.type'] == "#microsoft.graph.certificateBasedAuthentication":
								users_methods.append({
									"status": "ok",
									"@odata.type": "#microsoft.graph.certificateBasedAuthentication",
									"metode": "Sertifikat",
									"beskrivelse": f"Sertifikat med subject {auth_method['subjectName']}",
									"opprettet": opprettet,
								})
							if auth_method['@odata.type'] == "#microsoft.graph.temporaryAccessPassAuthenticationMethod":
								users_methods.append({
									"status": "ok",
									"@odata.type": "#microsoft.graph.temporaryAccessPassAuthenticationMethod",
									"metode": "TAP",
									"beskrivelse": f"Midlertidig tilgangspass med status {auth_method['methodUsabilityReason']}",
									"opprettet": opprettet,
								})
							if auth_method['@odata.type'] == "#microsoft.graph.windowsHelloForBusinessAuthenticationMethod":
								users_methods.append({
									"status": "ok",
									"@odata.type": "#microsoft.graph.windowsHelloForBusinessAuthenticationMethod",
									"metode": "Windows Hello",
									"beskrivelse": f"Maskinknyttet pålogging for {auth_method['displayName']}",
									"opprettet": opprettet,
								})
							if auth_method['@odata.type'] == "#microsoft.graph.fido2AuthenticationMethod":
								users_methods.append({
									"status": "ok",
									"@odata.type": "#microsoft.graph.fido2AuthenticationMethod",
									"metode": "FIDO2",
									"beskrivelse": f"{auth_method['displayName']} ({auth_method['model']})",
									"aaGuid": f"{auth_method.get('aaGuid')}",
									"opprettet": opprettet,
								})
							if auth_method['@odata.type'] == "#microsoft.graph.microsoftAuthenticatorAuthenticationMethod":
								users_methods.append({
									"status": "ok",
									"@odata.type": "#microsoft.graph.microsoftAuthenticatorAuthenticationMethod",
									"metode": "Authenticator",
									"beskrivelse": f"{auth_method['displayName']} ({auth_method['deviceTag']})",
									"opprettet": opprettet,
								})
							if auth_method['@odata.type'] == "#microsoft.graph.oathSoftwareTokenAuthenticationMethod":
								users_methods.append({
									"status": "ok",
									"@odata.type": "#microsoft.graph.oathSoftwareTokenAuthenticationMethod",
									"metode": "OTP software",
									"beskrivelse": f"",
									"opprettet": opprettet,
								})
							if auth_method['@odata.type'] == "#microsoft.graph.oathHardwareTokenAuthenticationMethod":
								users_methods.append({
									"status": "ok",
									"@odata.type": "#microsoft.graph.oathHardwareTokenAuthenticationMethod",
									"metode": "OTP hardware",
									"beskrivelse": f"{auth_method['displayName']} {auth_method['manufacturer']} {auth_method['model']}",
									"opprettet": opprettet,
								})
						user.profile.auth_methods = json.dumps(users_methods, indent=2)
						user.profile.auth_methods_last_update = datetime.now()
						profiles_to_update.append(user.profile)
						Command.ANTALL_LAGRET += 1
					else:
						user.profile.auth_methods = json.dumps({"status": "Oppslag feilet"}, indent=2)
						user.profile.auth_methods_last_update = datetime.now()
						profiles_to_update.append(user.profile)
						Command.ANTALL_FEILET += 1

				Profile.objects.bulk_update(profiles_to_update, ["auth_methods", "auth_methods_last_update"])
				return runtime_end - runtime_start


			# --- Main logic ---

			users_with_license = list(
				User.objects.filter(
					~Q(profile__ny365lisens=None),
					profile__accountdisable=False,
				).select_related('profile')
			)
			print(f"Fant {len(users_with_license)} brukere med M365-lisens")

			# Phase 1: Try to fetch report
			report_data = None
			use_hybrid = True
			try:
				print("Fase 1: Henter registreringsrapport fra MS Graph...")
				token = get_bearer_token()
				report_data = fetch_all_registration_details(token)
				print(f"Fase 1 ferdig: Hentet rapport for {len(report_data)} brukere")
			except Exception as e:
				print(f"Fase 1 feilet ({e}), faller tilbake til v1-oppførsel (eldste brukere først)")
				use_hybrid = False

			# Phase 2: Determine who needs refresh
			if use_hybrid and report_data:
				print("Fase 2: Sammenligner med lokale data for å finne endringer...")
				users_to_refresh = []
				for user in users_with_license:
					upn = (user.email or "").lower()
					report_entry = report_data.get(upn)
					if not report_entry:
						continue
					report_updated = parse_report_datetime(report_entry.get("lastUpdatedDateTime"))
					local_updated = user.profile.auth_methods_last_update
					if local_updated is None or (report_updated and report_updated > local_updated):
						users_to_refresh.append(user)

				print(f"Fase 2 ferdig: {len(users_to_refresh)} brukere trenger oppdatering, {len(users_with_license) - len(users_to_refresh)} er uendret")
				Command.ANTALL_UENDRET = len(users_with_license) - len(users_to_refresh)

				if len(users_to_refresh) > Command.MAX_DETAILED_FETCHES:
					print(f"Begrenser til maks {Command.MAX_DETAILED_FETCHES} brukere denne kjøringen")
					users_to_refresh = users_to_refresh[:Command.MAX_DETAILED_FETCHES]

				Command.users_to_be_processed = users_to_refresh
			else:
				# Fallback: same as v1, process oldest first
				users_with_none = [u for u in users_with_license if u.profile.auth_methods_last_update is None]
				users_with_dates = sorted(
					[u for u in users_with_license if u.profile.auth_methods_last_update is not None],
					key=lambda u: u.profile.auth_methods_last_update
				)
				all_sorted = users_with_none + users_with_dates
				Command.users_to_be_processed = all_sorted[:Command.MAX_DETAILED_FETCHES]
				print(f"Fallback: Plukker ut de {len(Command.users_to_be_processed)} eldste for oppdatering")

			# Phase 3: Batch fetch detailed methods
			total_to_process = len(Command.users_to_be_processed)
			print(f"Fase 3: Henter detaljerte autentiseringsmetoder for {total_to_process} brukere...")
			split_size = 20
			i = 0

			while Command.users_to_be_processed:
				how_many = min(split_size, len(Command.users_to_be_processed))
				current_batch = [Command.users_to_be_processed.pop(0) for _ in range(how_many)]

				timedelta = lookup_and_save(current_batch)
				i += how_many
				if i % 200 == 0 or i == total_to_process:
					print(f"  Prosessert {i}/{total_to_process} brukere. Graph-kallet tok {round(timedelta, 3)} sek")


			runtime_t1 = time.time()
			logg_total_runtime = runtime_t1 - runtime_t0
			logg_entry_message = (
				f"Hybrid v2: {Command.ANTALL_GRAPH_KALL} batch-kall mot MS Graph. "
				f"Fartsbegrenset {Command.ANTALL_TOO_MANY_CALLS} ganger. "
				f"Lagret {Command.ANTALL_LAGRET}, feilet {Command.ANTALL_FEILET}, "
				f"uendret (hoppet over) {Command.ANTALL_UENDRET}."
			)

			print(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)

			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_entry_message
			int_config.runtime = int(logg_total_runtime)
			int_config.helsestatus = "Vellykket"
			int_config.save()


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			import traceback
			int_config.helsestatus = f"Feilet\n{traceback.format_exc()}"
			print(int_config.helsestatus)
			int_config.save()
			push_pushover(f"{SCRIPT_NAVN} feilet")
