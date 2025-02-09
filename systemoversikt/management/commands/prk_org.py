# -*- coding: utf-8 -*-
#Hensikten med denne koden er å laste inn organisatoriske enheter og informasjon om leder.

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
	virksomheter_eksisterer_ikke = []

	def handle(self, **options):

		INTEGRASJON_KODEORD = "prk_org"
		LOG_EVENT_TYPE = 'PRK org-import'
		KILDE = "PRK"
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
		int_config.save()

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")

		try:

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")
			runtime_t0 = time.time()

			filepath = 'systemoversikt/import/grp.csv'

			if os.environ['THIS_ENV'] == "PROD":
				use_cache_data = False
				keep_file_locally = True
				apikey = os.environ["PRK_ORG_APIKEY"]

			if os.environ['THIS_ENV'] == "TEST":
				use_cache_data = False # settes til True ved feilsøking lokalt
				keep_file_locally = True # sett til True ved feilsøking
				apikey = os.environ["PRK_GENERELLEKSPORT_APIKEY"]

			if use_cache_data == True:
				print("Bruker lokale data")
				with open(filepath, 'r', encoding='latin-1') as file:
					datastructure = list(csv.DictReader(file, delimiter=";"))
			else:
				print("Henter data fra API")
				url = os.environ["PRK_ORG_URL"]
				headers = {"apikey": apikey}
				print("Kobler til %s" % url)
				r = requests.get(url, headers=headers)
				print("Original encoding: %s" % r.encoding)
				r.encoding = "latin-1" # need to override
				print("New encoding: %s" % r.encoding)
				print("Statuskode: %s" % r.status_code)

				if r.status_code == 200:
					print("Data er lastet inn")
					csv_data = list(csv.DictReader(r.text.splitlines(), delimiter=";"))
					if keep_file_locally:
						print("Lagrer data til fil på disk")
						with open(filepath, 'w') as file_handle:
							file_handle.write(r.text)
					else:
						print("Sletter datafil")
						os.remove(filepath)
				else:
					print(f"Error connecting: {r.status_code}.")


			def get_user(username):
				try:
					return User.objects.get(username=username)
				except:
					return None

			def get_virksomhet(odepartmentnumber):
				try:
					return Virksomhet.objects.get(odepartmentnumber=odepartmentnumber)
				except:
					return None

			def get_or_create(ouid):
				if ouid == "":
					return None
				else:
					try:
						u = HRorg.objects.get(ouid=ouid)
						Command.ant_oppdateringer += 1
					except Exception as e:
						u = HRorg.objects.create(ouid=ouid)
						Command.ant_nye_valg += 1
					return u

			@transaction.atomic  # for speeding up database performance
			def eksekver():

				print(f"Det er {len(csv_data)} enheter i datasettet")
				for unit in csv_data:

					if unit["OUSUBTYPE"] == "VIRK":  # virksomhet
						try:
							v = Virksomhet.objects.get(virksomhetsforkortelse__iexact=unit["O"])
							v.odepartmentnumber = unit["ODEPARTMENTNUMBER"]
							v.save()
						except Exception as e:
							print(f"Virksomheten {unit['O']} finnes ikke")
							Command.virksomheter_eksisterer_ikke.append(unit['O'])

					u = get_or_create(unit["OUID"])
					u.ou = unit["OU"]
					u.level = unit["OULEVEL"]
					username = unit["O"] + unit["MANAGEREMPLOYEENUMBER"]
					u.leder = get_user(username)
					u.virksomhet_mor = get_virksomhet(unit["ODEPARTMENTNUMBER"])
					u.direkte_mor = get_or_create(unit["OUBELONGSTOOUID"])
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

			logg_entry_message = f"Import av organisatoriske enheter: Kjøretid: {logg_total_runtime}: {Command.ant_nye_valg} nye, {Command.ant_oppdateringer} oppdaterte og {Command.ant_deaktivert} deaktiverte. Følgende virksomheter finnes ikke i databasen {Command.virksomheter_eksisterer_ikke}"
			print(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message,)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_entry_message
			int_config.runtime = logg_total_runtime
			int_config.save()

		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message,)
			print(logg_message)
			push_pushover(f"{SCRIPT_NAVN} feilet") # Push error
