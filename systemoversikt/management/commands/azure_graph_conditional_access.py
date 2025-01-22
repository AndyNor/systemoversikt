# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import os
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
		int_config.save()

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")

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
				print(f"Kan ikke sammenlikne med forrige version av policy: {e}")
				pass

			#logg dersom vellykket
			logg_message = f"Innlasting av policy utført"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message
			int_config.save()

		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)
			# Push error
			push_pushover(f"{SCRIPT_NAVN} feilet")

