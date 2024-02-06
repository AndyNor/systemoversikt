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
import requests
import time
import os
import sys
import csv

class Command(BaseCommand):
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
			ant_nye_valg = 0
			ant_oppdateringer = 0
			ant_deaktivert = 0
			debug_file = os.path.dirname(os.path.abspath(__file__)) + "/org.csv"

			if os.environ['THIS_ENV'] == "PROD":
				url = os.environ["PRK_ORG_URL"]
				apikey = os.environ["PRK_ORG_APIKEY"]
				headers = {"apikey": apikey}

				print("Kobler til %s" % url)
				r = requests.get(url, headers=headers)
				print("Original encoding: %s" % r.encoding)
				r.encoding = "latin-1" # need to override
				print("New encoding: %s" % r.encoding)
				print("Statuskode: %s" % r.status_code)
				try:
					if r.status_code == 200:
						with open('systemoversikt/import/grp.csv', 'w') as file_handle:
							file_handle.write(r.text)
						csv_data = list(csv.DictReader(r.text.splitlines(), delimiter=";"))
				except:
					ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="kunne ikke skrive til fil..")
					sys.exit()


			if os.environ['THIS_ENV'] == "TEST":
				with open(debug_file, 'r', encoding='latin-1') as file:
					csv_data = list(csv.DictReader(file, delimiter=";"))
					#headers: OU;OUSHORT;OUID;OUTYPE;OUSUBTYPE;O;ODEPARTMENTNUMBER;ODISPLAYNAME;OUBELONGSTOOUID;OULEVEL;MANAGER;MANAGEREMPLOYEENUMBER;DESCRIPTION;MAIL

			@transaction.atomic  # for speeding up database performance
			def atomic():
				def get_user(username):
					try:
						user = User.objects.get(username=username)
					except:
						user = None
					return user

				def get_virksomhet(odepartmentnumber):
					try:
						v = Virksomhet.objects.get(odepartmentnumber=odepartmentnumber)
					except:
						v = None
					return v

				def get_or_create(ouid):
					if ouid == "":
						return None
					else:
						try:
							u = HRorg.objects.get(ouid=ouid)
							nonlocal ant_oppdateringer
							ant_oppdateringer += 1
						except Exception as e:
							u = HRorg.objects.create(ouid=ouid)
							nonlocal ant_nye_valg
							ant_nye_valg += 1
						return u

				print("Det er %s enheter i datasettet" % (len(csv_data)))
				for unit in csv_data:

					if unit["OUSUBTYPE"] == "VIRK":  # virksomhet
						try:
							v = Virksomhet.objects.get(virksomhetsforkortelse__iexact=unit["O"])
							v.odepartmentnumber = unit["ODEPARTMENTNUMBER"]
							v.save()
						except Exception as e:
							print("%s finnes ikke. %s" % (unit["O"], e))

					u = get_or_create(unit["OUID"])
					u.ou = unit["OU"]
					u.level = unit["OULEVEL"]
					username = unit["O"] + unit["MANAGEREMPLOYEENUMBER"]
					u.leder = get_user(username)
					u.virksomhet_mor = get_virksomhet(unit["ODEPARTMENTNUMBER"])
					u.direkte_mor = get_or_create(unit["OUBELONGSTOOUID"])
					u.save()
					#print(unit["OU"])

			atomic()

			@transaction.atomic  # for speeding up database performance
			def opprydding():
				print("Rydder opp..")
				###

			opprydding()


			runtime_t1 = time.time()
			logg_total_runtime = runtime_t1 - runtime_t0

			logg_entry_message = "Import av organisatoriske enheter: Kjøretid: %s: %s nye, %s oppdaterte og %s deaktiverte" % (
					round(logg_total_runtime, 1),
					ant_nye_valg,
					ant_oppdateringer,
					ant_deaktivert

			)
			print(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_entry_message,
			)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_entry_message
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
