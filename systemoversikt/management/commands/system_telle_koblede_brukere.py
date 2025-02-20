# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Q
from django.db import transaction
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
import os, time


class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "lokal_duplikatteller"
		LOG_EVENT_TYPE = "Duplikatteller"
		KILDE = "Lokal"
		PROTOKOLL = "N/A"
		BESKRIVELSE = "Telle opp koblede brukerkontoer"
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
		runtime_t0 = time.time()


		try:
			@transaction.atomic
			def opptelling():
				idx = 1
				antall_profiler = Profile.objects.all().count()
				for profile in Profile.objects.all():
					if idx % 5000 == 0:
						print(f"{idx} av {antall_profiler}")
					idx += 1
					if profile.ansattnr_ref != None:
						antall = len(profile.ansattnr_ref.userprofile.all())
						if profile.ansattnr_antall != antall:
							profile.ansattnr_antall = antall
							profile.save()

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="Starter..")
			opptelling()
			logg_entry_message = "Ferdig med opptelling"
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)
			print(logg_entry_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_entry_message
			runtime_t1 = time.time()
			int_config.runtime = int(runtime_t1 - runtime_t0)
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

