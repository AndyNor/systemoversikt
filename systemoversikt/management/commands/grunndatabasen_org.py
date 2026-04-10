# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.db import transaction
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
import requests, time, os, sys, csv

class Command(BaseCommand):

	ant_nye_valg = 0
	ant_oppdateringer = 0
	ant_deaktivert = 0
	ant_org_enheter = 0
	ant_uten_organisasjonId = 0

	def handle(self, **options):

		INTEGRASJON_KODEORD = "grunndatabase_org"
		LOG_EVENT_TYPE = 'HR-organisasjonsimport'
		KILDE = "Grunndatabasen"
		PROTOKOLL = "REST"
		BESKRIVELSE = "Organisasjonsstruktur"
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

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starteapi_response..")
			runtime_t0 = time.time()

			filepath = 'systemoversikt/import/hr_org.json'
			apikey = os.environ["GDB_ORG_APIKEY_PROD"]
			data_url = os.environ["GDB_ORG_URL_PROD"]

			if os.environ['THIS_ENV'] == "PROD":
				use_cache_data = False
				keep_file_locally = False

			if os.environ['THIS_ENV'] == "TEST":
				use_cache_data = False # settes til True ved feilsøking lokalt
				keep_file_locally = False # sett til True ved feilsøking

			if use_cache_data == True:
				print("Bruker lokale cachede data")
				with open(filepath, 'r') as file:
					org_datastructure = json.load(file)
			else:
				headers = {"apikey": apikey}
				print("Kobler til %s" % data_url)
				api_response = requests.get(data_url, headers=headers)
				print("Original encoding: %s" % api_response.encoding)
				print("Statuskode: %s" % api_response.status_code)

				if api_response.status_code == 200:
					print("Data er lastet inn fra API")
					org_datastructure = json.loads(api_response.text)

					if keep_file_locally:
						print("Lagrer data til fil på disk")
						with open(filepath, 'w', encoding='utf-8') as file_handle:
							file_handle.write(api_response.text)
					else:
						print("Sletter datafil")
						try:
							os.remove(filepath)
						except:
							print("Kunne ikke slette filen.")
				else:
					print(f"Feil med tilkobling: {api_response.status_code}: {api_response.text}")


			def get_user(username):
				try:
					return User.objects.get(username=username)
				except:
					return None

			def get_virksomhet(kortNavn):
				try:
					return Virksomhet.objects.get(virksomhetsforkortelse__iexact=kortNavn)
				except:
					return None

			def get_or_create(organisasjonId, hrOrganisasjonId=None, navn=None, kode=None):
				if organisasjonId in [None, ""]:
					#print(f"tom organisasjonId, men hrOrganisasjonId er {hrOrganisasjonId} og heter {navn} og har kode {kode}")
					Command.ant_uten_organisasjonId += 1
					return None
				else:
					try:
						u = HRorg.objects.get(ouid=organisasjonId)
						u.hrouid = hrOrganisasjonId
						Command.ant_oppdateringer += 1
					except Exception as e:
						u = HRorg.objects.create(ouid=organisasjonId)
						u.hrouid = hrOrganisasjonId
						Command.ant_nye_valg += 1
					return u

			def find_mother(forelderId):
				try:
					u = HRorg.objects.get(hrouid=forelderId)
				except:
					u = None
				return u


			@transaction.atomic  # for speeding up database performance
			def eksekver():

				Command.ant_org_enheter = len(org_datastructure)
				print(f"Det er {Command.ant_org_enheter} enheter i datasettet")
				for unit in org_datastructure:

					u = get_or_create(unit["organisasjonId"], unit["hrOrganisasjonId"], unit["navn"], unit["status"])
					if u:
						u.ou = unit["navn"]
						u.level = unit["nivaa"]
						if "lederId" in unit:
							username = f'{unit["kortNavn"].lower()}{unit["lederId"]}'
							u.leder = get_user(username)
						u.virksomhet_mor = get_virksomhet(unit["kortNavn"])
						if "forelderId" in unit:
							u.direkte_mor = find_mother(unit["forelderId"])
						u.hr_status = unit["status"]
						try:
							u.virksomhetId = int(unit["virksomhetId"])
						except:
							pass
						u.gateNavn = unit["gateNavn"]
						u.postnr = unit["postnr"]
						u.save()

			def opprydding():
				tidligere = timezone.now() - timedelta(hours=6) # 6 timer gammelt
				inaktive_orgledd = HRorg.objects.filter(sist_oppdatert__lte=tidligere)
				Command.ant_deaktivert = len(inaktive_orgledd)
				print(f"Sletter {Command.ant_deaktivert} inaktive HRorg-elementer")
				inaktive_orgledd.delete()


			print("Starter å importere til database...")
			eksekver()
			print("Rydder opp...")
			opprydding()

			runtime_t1 = time.time()
			logg_total_runtime = int(runtime_t1 - runtime_t0)

			logg_entry_message = f"Import av organisatoriske enheter: {Command.ant_nye_valg} nye, {Command.ant_oppdateringer} oppdaterte og {Command.ant_deaktivert} deaktiverte. Det var {Command.ant_uten_organisasjonId} uten organisasjonId som ble droppet."
			print(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message,)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_entry_message
			int_config.runtime = logg_total_runtime
			int_config.elementer = int(Command.ant_org_enheter)
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
