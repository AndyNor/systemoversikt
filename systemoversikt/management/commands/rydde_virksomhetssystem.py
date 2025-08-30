# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
import collections, os, time

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "lokal_bruk_virksomhetssystem"
		LOG_EVENT_TYPE = 'Sette bruk av system'
		KILDE = "Lokal"
		PROTOKOLL = "N/A"
		BESKRIVELSE = "Sette bruk dersom det mangler for virksomhetssystem"
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

			teller = 0

			aktive_virksomhetssystem = System.objects.filter(~Q(livslop_status=7)).filter(systemeierskapsmodell="VIRKSOMHETSSYSTEM")
			for virksomhetssystem in aktive_virksomhetssystem:
				#print(f"Undersøker virksomhetssystemet {virksomhetssystem}")
				bruk, opprettet = SystemBruk.objects.get_or_create(
						brukergruppe=virksomhetssystem.systemforvalter,
						system=virksomhetssystem,
						)
				if opprettet:
					teller += 1
					print(f"Opprettet bruksregistrering av {virksomhetssystem.systemforvalter} for {virksomhetssystem}")

				if len(virksomhetssystem.systemforvalter_kontaktpersoner_referanse.all()) > 0 and len(bruk.systemforvalter_kontaktpersoner_referanse.all()) == 0:
					bruk.systemforvalter_kontaktpersoner_referanse.add(virksomhetssystem.systemforvalter_kontaktpersoner_referanse.all()[0]) # setter den første
					bruk.save()
					print(f"Satt lokal forvalter til {virksomhetssystem.systemforvalter_kontaktpersoner_referanse.all()[0].brukernavn}")


			logg_message = f"Ferdig med å opprette {teller} bruk, for alle aktive virksomhetssystem som manglet egen bruk."
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message
			runtime_t1 = time.time()
			logg_total_runtime = int(runtime_t1 - runtime_t0)
			int_config.runtime = logg_total_runtime
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
