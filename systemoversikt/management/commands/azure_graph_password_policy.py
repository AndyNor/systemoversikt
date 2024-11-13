# -*- coding: utf-8 -*-
#Graph-klienten heter "UKE - Kartoteket - Lesetilgang MS Graph"

from django.core.management.base import BaseCommand
import io
import os
import simplejson as json
from django.utils.timezone import make_aware
from datetime import datetime
from datetime import timedelta
from django.utils import timezone
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from systemoversikt.views import push_pushover
from systemoversikt.models import *

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "azure_password_polcy"
		LOG_EVENT_TYPE = "Azure Password policy"
		KILDE = "Azure Graph"
		PROTOKOLL = "REST"
		BESKRIVELSE = "Informasjon om passordpolicy"
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
			query = "/policies/authenticationMethods"
			resp = client.get(query)
			json_data = json.loads(resp.text)

			print(json.dumps(json_data, sort_keys=True, indent=4))


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

			#print("*** Ferdig innlest")


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# Push error
			push_pushover(f"{SCRIPT_NAVN} feilet")

