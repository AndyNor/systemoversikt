# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
import sys, os, time

class Command(BaseCommand):

	ANTALL_KOBLET = 0

	def handle(self, **options):

		INTEGRASJON_KODEORD = "lokal_match_usr_o365license"
		LOG_EVENT_TYPE = 'Oppslag bruker-o3635lisens'
		KILDE = "Lokal"
		PROTOKOLL = "N/A"
		BESKRIVELSE = "Kobler en brukers profil med en lisensmodell for ofice365"
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


			# relevante grupper knyttet til lisens
			nye_adgrupper = [
				{"gruppe":"Task-OF2-Lisens-O365-G1", "navn": "G1 Standardklient"},
				{"gruppe":"Task-OF2-Lisens-O365-G2", "navn": "G2 Flerbruker"},
				{"gruppe":"Task-OF2-Lisens-O365-G3", "navn": "G3 Uten e-post"},
				{"gruppe":"Task-OF2-Lisens-O365-G4", "navn": "G4 Education"},
				{"gruppe":"Task-OF2-Lisens-O365-G5", "navn": "G5 IDA basis (F1)"}
			]

			#bufre alle gruppemedlemmer direkte under nye_adgrupper
			for idx, group in enumerate(nye_adgrupper):

				try:
					adgroup = ADgroup.objects.get(common_name=group["gruppe"])
				except:
					continue

				adgroup_members = json.loads(adgroup.member)
				adgroup_members_clean = set()
				for m in adgroup_members:
					try:
						adgroup_members_clean.add(m.split(",")[0].split("=")[1].lower())
					except:
						pass
				group["adgroup_members_clean"] = list(adgroup_members_clean)

			def bulk_save(profiles_to_update):
				Profile.objects.bulk_update(profiles_to_update, ["ny365lisens",])

			def lookup_and_save(users):
				profiles_to_update = []
				for bruker in users:
					for group in nye_adgrupper:
						try:
							members = group["adgroup_members_clean"]
						except:
							members = [] # skjer dersom gruppen ikke finnes
						if bruker.username.lower() in members:
							bruker.profile.ny365lisens = group["navn"]
							profiles_to_update.append(bruker.profile)
							Command.ANTALL_KOBLET += 1
							break
				bulk_save(profiles_to_update)

			split_size = 5000
			alle_brukere = User.objects.all()
			# slå opp for hver bruker ny lisens
			for i in range(0, len(alle_brukere), split_size):
				print(f"Ny batch fra {i} til {i + split_size}")
				lookup_and_save(alle_brukere[i:i + split_size])


			runtime_t1 = time.time()
			logg_total_runtime = runtime_t1 - runtime_t0
			logg_entry_message = f"Ferdig med kobling av {Command.ANTALL_KOBLET} brukere til o365-lisens"

			print(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)

			# lagre sist oppdatert tidspunkt
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
			int_config.save()
			push_pushover(f"{SCRIPT_NAVN} feilet") # Push error