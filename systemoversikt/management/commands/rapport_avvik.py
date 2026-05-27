# -*- coding: utf-8 -*-
# Change log:
# 2026-05-27: Use rapport_gruppemedlemskaper_antall_brukere – same unique transitive count as sikkerhetsavvik page.
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover, rapport_gruppemedlemskaper_antall_brukere
from django.core.management.base import BaseCommand
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from dateutil import parser
from datetime import datetime
import simplejson as json
import os, time

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "ad_graph_sikkerhetsavvik"
		LOG_EVENT_TYPE = 'Grafdata for sikkerhetsavvik'
		KILDE = "Active Directory OSLOFELLES"
		PROTOKOLL = "LDAP"
		BESKRIVELSE = "Antall personer i utvalgte AD-grupper"
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
			# forenklet logikk som kun henter ut tallene nødvendig og lagrer disse
			innhentingsbehov = []
			for i in RapportGruppemedlemskaper.objects.all():
				innhentingsbehov.append({
					"id": i,
					"grupper": list(i.grupper.all()),
					"AND_grupper": list(i.AND_grupper.all()),
					"tidslinjedata": i.tidslinjedata,
				})

			def rapport_hent_statistikk(i):
				print(f"Leser ut grupper for {i['id'].beskrivelse}")
				antall, _ = rapport_gruppemedlemskaper_antall_brukere(i["grupper"], i["AND_grupper"] or None)
				i["medlemmer"] = antall
				return i


			statistikk = []
			for i in innhentingsbehov:
				statistikk.append(rapport_hent_statistikk(i))


			for s in statistikk:
				print(f"laster inn tidsdata for {s['id'].beskrivelse}")
				try:
					tidslinjedata = json.loads(s["tidslinjedata"])
				except:
					print(f"*** Det manglet tidslinjedata for {s['id'].beskrivelse}")
					tidslinjedata = []

				date_str = datetime.now().strftime("%d.%m")
				dagens_antall = {"date": date_str, "count": s["medlemmer"]}
				print(f"legger til {dagens_antall}")
				tidslinjedata.append(dagens_antall)

				object_ref = s["id"]
				object_ref.tidslinjedata = json.dumps(tidslinjedata)
				object_ref.save()


			logg_message = f"Innlasting av statistikk utført."
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
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

