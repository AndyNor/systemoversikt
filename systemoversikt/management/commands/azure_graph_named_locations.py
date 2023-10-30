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

		INTEGRASJON_KODEORD = "azure_named_locations"
		LOG_EVENT_TYPE = "Azure named locations"
		KILDE = "Azure Graph"
		PROTOKOLL = "REST"
		BESKRIVELSE = "Navngitte lokasjoner"
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

		try:

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

			def oversett_iso3166(koder):
				return_data = []
				for code in koder:
					if code in countrycodes:
						name = countrycodes[code]
					else:
						name = code
					return_data.append({"code": code, "name": name})
				return json.dumps(return_data)


			def hentSubnet(ipRanges):
				ranges = set()
				for iprange in ipRanges:
					ranges.add(iprange["cidrAddress"])
				return json.dumps(list(ranges))



			date_format = "%Y-%m-%dT%H:%M:%S"
			def str_to_date(date_string):
				date_string = date_string.split(".")[0]
				return make_aware(datetime.strptime(date_string, date_format))


			antall_lagret = 0
			for named_location in json_data["value"]:
				#print("Laster " + named_location["displayName"] + " (" + named_location["id"] + ")")

				try:
					nl = AzureNamedLocations.objects.get(ipNamedLocation_id=named_location["id"])
				except:
					nl = AzureNamedLocations.objects.create(ipNamedLocation_id=named_location["id"])

				nl.active = True
				nl.displayName = named_location["displayName"]

				if "isTrusted" in named_location:
					nl.isTrusted = named_location["isTrusted"]

				if named_location["modifiedDateTime"] != None:
					sist_endret = str_to_date(named_location["modifiedDateTime"])
					nl.sist_endret = sist_endret

				if "ipRanges" in named_location:
					nl.ipRanges = hentSubnet(named_location["ipRanges"])

				if "countriesAndRegions" in named_location:
					koder = oversett_iso3166(named_location["countriesAndRegions"])
					nl.countriesAndRegions = koder

				nl.save()
				antall_lagret += 1

			# sjekke om noe ikke ble oppdatert og sette deaktivert

			tidligere = timezone.now() - timedelta(hours=6) # 6 timer gammelt
			deaktive = AzureNamedLocations.objects.filter(sist_oppdatert__lte=tidligere)
			for d in deaktive:
				d.active = False
				d.save()
				print("%s satt deaktiv" % d)


			#logg dersom vellykket
			logg_message = f"Innlasting av named {antall_lagret} lokasjoner utført"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message
			int_config.save()

			print("*** Ferdig innlest")


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# Push error
			push_pushover(f"{SCRIPT_NAVN} feilet")

