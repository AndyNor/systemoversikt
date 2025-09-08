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

		INTEGRASJON_KODEORD = "inaktive_systemer_opprydding"
		LOG_EVENT_TYPE = 'Rydde opp i deaktiverte systemer'
		KILDE = "Lokal"
		PROTOKOLL = "N/A"
		BESKRIVELSE = "Fjerne ansvarlige fra inaktive systemer"
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

		antall_ryddet = 0

		try:
			deaktiverte_systemer = System.objects.filter(livslop_status=7).filter(~Q(systembeskrivelse__contains="Dette systemet er fullstendig avviklet")) # Fullstendig avviklet
			for system in deaktiverte_systemer:

				if system.sist_oppdatert < timezone.now() - timedelta(hours=24):

					eiere = ", ".join(ansvarlig.brukernavn.email for ansvarlig in system.systemeier_kontaktpersoner_referanse.all())
					forvaltere = ", ".join(ansvarlig.brukernavn.email for ansvarlig in system.systemforvalter_kontaktpersoner_referanse.all())
					innsyn = ", ".join(ansvarlig.brukernavn.email for ansvarlig in system.kontaktperson_innsyn.all())
					bestillere = ", ".join(ansvarlig.brukernavn.email for ansvarlig in system.godkjente_bestillere.all())

					print(f"Legger til eiere: {eiere}, forvaltere: {forvaltere}, innsynskontakter {innsyn} og bestillere {bestillere} i systemets kommentarfelt og sletter koblingene til de ansvarlige")
					system.systembeskrivelse = f"Dette systemet er fullstendig avviklet.\nTidligere eiere var: {eiere}\nTidligere forvaltere var: {forvaltere}\nTidligere innsynskontakter var: {innsyn}\nTidligere bestillere var: {bestillere}\n\n{system.systembeskrivelse}"

					system.kontaktperson_innsyn.clear()
					system.godkjente_bestillere.clear()
					system.systemeier_kontaktpersoner_referanse.clear()
					system.systemforvalter_kontaktpersoner_referanse.clear()

					system.save()
					antall_ryddet += 1



			logg_message = f"Ferdig med å slette ansvarlige for {antall_ryddet} systemer som er inaktive."
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
