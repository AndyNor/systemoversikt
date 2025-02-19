# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from systemoversikt.models import *
import os, requests, json, time
from datetime import datetime
from django.db.models import Q
from systemoversikt.views import push_pushover


class Command(BaseCommand):

	ANTALL_GRAPH_KALL = 0
	ANTALL_LAGRET = 0
	ANTALL_FEILET = 0
	ANTALL_MED_LISENS = 0

	def handle(self, **options):


		INTEGRASJON_KODEORD = "azure_ad_auth_methods"
		LOG_EVENT_TYPE = 'Entra ID autentiseringsmetoder'
		KILDE = "Azure Graph"
		PROTOKOLL = "REST"
		BESKRIVELSE = "Hente ned brukeres autentiseringsmetoder"
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

			# maksimum 20 per batch
			def create_batch_request(users):
				requests = []
				for i, user in enumerate(users):
					upn = user.email
					requests.append({
						"id": i,
						"method": "GET",
						"url": f"/users/{upn}/authentication/methods"
					})
				#print({"requests": requests})
				return {"requests": requests}


			def lookup_and_save(users):
				batch_payload = create_batch_request(users)
				runtime_start = time.time()
				response = client.post('/$batch', json=batch_payload)
				Command.ANTALL_GRAPH_KALL += 1
				response_data = response.json()
				#print(f"{json.dumps(response_data, indent=2)}")
				runtime_end = time.time()
				profiles_to_update = []

				for result in response_data.get('responses', []):
					user_id = int(result['id'])
					user = users[user_id]
					#print(f"prosesserer {user}")
					status = result['status']
					if status != 200:
						print(f"HTTP {status}\n{json.dumps(result, indent=2)}")
					#print(f"HTTP {status}")
					body = result['body']
					#print(f"{status}: {user}")
					#print(f"{json.dumps(body, indent=2)}")
					if status == 200:
						users_methods = []
						for auth_method in body["value"]:
							try:
								#opprettet = datetime.datetime.strptime(auth_method["createdDateTime"], "%Y-%m-%dT%H:%M:%SZ")
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
						#for m in users_methods:
						#	print(m)
						user.profile.auth_methods = json.dumps(users_methods, indent=2)
						profiles_to_update.append(user.profile)
						Command.ANTALL_LAGRET += 1
					else:
						user.profile.auth_methods = json.dumps({"status": "Oppslag feilet"}, indent=2)
						profiles_to_update.append(user.profile)
						Command.ANTALL_FEILET += 1
						pass

				Profile.objects.bulk_update(profiles_to_update, ["auth_methods",])
				return runtime_end - runtime_start


			# Start oppsplitting
			users_with_license = User.objects.filter(profile__accountdisable=False).filter(profile__virksomhet__id=163).filter(~Q(profile__ny365lisens=None))
			Command.ANTALL_MED_LISENS = len(users_with_license)
			print(f"Fant {Command.ANTALL_MED_LISENS} brukere med M365-lisens for oppslag av autentiseringsmetode")

			split_size = 20
			for i in range(0, len(users_with_license), split_size):
				#print(f"Ny batch fra {i} til {i + split_size}")
				timedelta = lookup_and_save(users_with_license[i:i + split_size])
				print(f"Ny batch fra {i} til {i + split_size} ferdig. Graph-kallet tok {round(timedelta, 3)} sekunder")


			runtime_t1 = time.time()
			logg_total_runtime = runtime_t1 - runtime_t0
			logg_entry_message = f"Utførte {Command.ANTALL_GRAPH_KALL} kall mot MS Graph. Lagret {Command.ANTALL_LAGRET} profiler. {Command.ANTALL_FEILET} feilet."

			print(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_entry_message
			int_config.runtime = int(logg_total_runtime)
			int_config.save()


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			push_pushover(f"{SCRIPT_NAVN} feilet") # Push error









