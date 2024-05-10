# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
import sys
import os
import time

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "lokal_match_user_grp"
		LOG_EVENT_TYPE = 'Oppslag AD-bruker AD-grupper'
		KILDE = "Lokal"
		PROTOKOLL = "N/A"
		BESKRIVELSE = "Kobler AD-bruker mot AD-grupper"
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

		#try:

		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")
		runtime_t0 = time.time()


		@transaction.atomic  # for speeding up database performance
		def populate_groups_for_user(users):
			#print(f"processing {users}")
			for user in users:
				groups = ADgroup.objects.filter(member__icontains=user.username)
				user.profile.gruppemedlemskap.clear()
				user.profile.gruppemedlemskap.add(*groups)
			print(users)


		all_users = User.objects.all()[0:100]
		chunk_size = 25
		for i in range(0, len(all_users), chunk_size):
			chunk = all_users[i:i + chunk_size]
			populate_groups_for_user(chunk)



		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		logg_entry_message = f"Kjøretid {round(logg_total_runtime, 1)} sekunder."
		print(logg_entry_message)
		logg_entry = ApplicationLog.objects.create(
				event_type=LOG_EVENT_TYPE,
				message=logg_entry_message,
		)

		# lagre sist oppdatert tidspunkt
		int_config.dato_sist_oppdatert = timezone.now()
		int_config.sist_status = logg_entry_message
		int_config.save()


		"""
		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# Push error
			#push_pushover(f"{SCRIPT_NAVN} feilet")
		"""