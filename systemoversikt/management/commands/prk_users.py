# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.db import transaction
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
import os, time, sys, json, csv, requests

class Command(BaseCommand):

	antall_feilet_brukeroppslag = 0
	antall_feilet_orgoppslag = 0
	antall_drift_treff = 0
	antall_profillagringer = 0


	def handle(self, **options):

		INTEGRASJON_KODEORD = "prk_users"
		LOG_EVENT_TYPE = 'PRK user import'
		KILDE = "PRK"
		PROTOKOLL = "REST"
		BESKRIVELSE = "Brukere"
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

			filepath = 'systemoversikt/import/usr.csv'

			if os.environ['THIS_ENV'] == "PROD":
				use_cache_data = False
				keep_file_locally = True
				apikey = os.environ["PRK_USERS_APIKEY"]

			if os.environ['THIS_ENV'] == "TEST":
				use_cache_data = True # settes til True ved feilsøking lokalt
				keep_file_locally = True # sett til True ved feilsøking
				apikey = os.environ["PRK_GENERELLEKSPORT_APIKEY"]

			if use_cache_data == True:
				print("Bruker lokale data")
				with open(filepath, 'r', encoding='latin-1') as file:
					datastructure = list(csv.DictReader(file, delimiter=";"))
			else:
				print("Henter data fra API")
				url = os.environ["PRK_USERS_URL"]
				headers = {"apikey": apikey}
				print("Kobler til %s" % url)
				r = requests.get(url, headers=headers)
				print("Original encoding: %s" % r.encoding)
				r.encoding = "latin-1" # need to override
				print("New encoding: %s" % r.encoding)
				print("Statuskode: %s" % r.status_code)

				if r.status_code == 200:
					print(f"Data er lastet inn")
					datastructure = list(csv.DictReader(r.text.splitlines(), delimiter=";"))
					if keep_file_locally:
						print("Lagrer data til fil på disk")
						with open(filepath, 'w') as file_handle:
							file_handle.write(r.text)
					else:
						print("Sletter datafil")
						os.remove(filepath)
				else:
					print(f"Error connecting: {r.status_code}.")


			def print_with_timestamp(message):
				current_time = datetime.now()
				print(f"{current_time.hour}:{current_time.minute} {message}")


			print_with_timestamp("Resetter usertype...")
			Profile.objects.all().update(usertype=None)
			print_with_timestamp("Resetter org_unit...")
			Profile.objects.all().update(org_unit=None)
			print_with_timestamp("Resetter ansattnr...")
			Profile.objects.all().update(ansattnr=None)
			print_with_timestamp("Resetter from_prk...")
			Profile.objects.all().update(from_prk=False)

			print_with_timestamp("Cacher HR-organisasjonen...")
			cache_hrorg = dict(HRorg.objects.values_list("ouid", "pk"))
			print_with_timestamp("Cacher alle brukere...")
			cache_users = dict(User.objects.values_list("username", "pk"))


			def lookup_hrorg(ouid):
				try:
					ouid = int(ouid)
					pk = cache_hrorg.get(ouid)
					return HRorg.objects.get(pk=pk)
				except:
					#print(f"lookup_hrorg fant ikke {ouid}")
					return None

			def lookup_users(username):
				try:
					pk = cache_users.get(username)
					return User.objects.get(pk=pk)
				except:
					#print(f"lookup_users fant ikke {username}")
					return None

			def save_to_database(chunck):
				antall_behandlet = 0
				profiles_to_update = []
				for line in chunck:
					antall_behandlet += 1
					usertype = f"{line['EMPLOYEETYPENAME']}"
					ansattnr = line["EMPLOYEENUMBER"]

					org_unit = lookup_hrorg(line["OUID"])
					if not org_unit:
						Command.antall_feilet_orgoppslag += 1

					if org_unit:
						min_leder = org_unit.leder
					else:
						min_leder = None
					#print(min_leder)

					username_str = f"{line['O']}{line['EMPLOYEENUMBER']}"
					u = lookup_users(username_str)
					if u != None:
						u.profile.usertype = usertype
						u.profile.org_unit = org_unit
						u.profile.ansattnr = ansattnr
						u.profile.from_prk = True
						u.profile.min_leder = min_leder
						profiles_to_update.append(u.profile)
						Command.antall_profillagringer += 1
					else:
						Command.antall_feilet_brukeroppslag += 1

					username_str = f"{'drift'}{line['EMPLOYEENUMBER']}"
					u = lookup_users(username_str)
					if u != None:
						u.profile.usertype = usertype
						u.profile.org_unit = org_unit
						u.profile.ansattnr = ansattnr
						u.profile.from_prk = True
						u.profile.min_leder = min_leder
						profiles_to_update.append(u.profile)
						Command.antall_profillagringer += 1
						Command.antall_drift_treff += 1

				# HUSK Å OPPDATERE DENNE!
				Profile.objects.bulk_update(profiles_to_update, ['usertype', 'org_unit', 'ansattnr', 'from_prk', 'min_leder'])

				return antall_behandlet


			print_with_timestamp("Processing...")
			total_processed = 0
			linjer_kilde = len(datastructure)
			split_size = 5000

			for i in range(0, linjer_kilde, split_size):
				total_processed += save_to_database(datastructure[i:i + split_size])
				message = f"Ferdig med batch {i}-{i+split_size}/{linjer_kilde}. Frem til nå er det {Command.antall_profillagringer} profillagringer, {Command.antall_feilet_brukeroppslag} feilede brukeroppslag, {Command.antall_feilet_orgoppslag} feilede HR-org oppslag og {Command.antall_drift_treff} treff på DRIFT-ident."
				print_with_timestamp(message)


			runtime_t1 = time.time()
			logg_total_runtime = int(runtime_t1 - runtime_t0)
			logg_entry_message = f"Kjøretid: {logg_total_runtime} sekunder: {total_processed} brukere importert, {Command.antall_feilet_orgoppslag} feilet oppslag mot HR-org, {Command.antall_feilet_brukeroppslag} feilet oppslag mot brukerID og {Command.antall_drift_treff} hadde drift-bruker knyttet til seg."

			print_with_timestamp(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message,)

			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_entry_message
			int_config.runtime = logg_total_runtime
			int_config.elementer = int(total_processed)
			int_config.save()


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message,)
			print(logg_message)
			push_pushover(f"{SCRIPT_NAVN} feilet") # Push error
