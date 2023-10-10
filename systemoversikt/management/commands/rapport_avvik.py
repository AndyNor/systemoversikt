# -*- coding: utf-8 -*-
# Hente ut statisikk på utvalgte grupper. Kjøres normalt 1 gang per uke.
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from dateutil import parser
from datetime import datetime
import simplejson as json
import os

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
		int_config.save()

		print(f"Starter {SCRIPT_NAVN}")

		try:

			# forenklet logikk som kun henter ut tallene nødvendig og lagrer disse
			innhentingsbehov = []
			for i in RapportGruppemedlemskaper.objects.all():
				innhentingsbehov.append({
					"id": i,
					"grupper": [g.common_name for g in i.grupper.all()],
					"AND_grupper":[g.common_name for g in i.AND_grupper.all()],
					"tidslinjedata": i.tidslinjedata,
				})


			def rapport_konkrete_brukere(grupper):
				gruppeemdlemmer = set()
				for gruppe in grupper:
					try:
						gruppe = ADgroup.objects.get(common_name__iexact=gruppe)
					except:
						print(f"fant ikke gruppen {gruppe}")
						continue
					brukere = json.loads(gruppe.member)
					for bruker in brukere:
						try:
							gruppeemdlemmer.add(bruker.split(',')[0].split('CN=')[1])
						except:
							print(f"fant ikke bruker {bruker}")
							pass
				return gruppeemdlemmer


			def rapport_hent_statistikk(i):
				antall = 0
				if len(i["AND_grupper"]) == 0: # Det er bare ordinære grupper som kan slås opp direkte. Er mye raskere enn å dekode enkeltbrukere.
					for gruppe in i["grupper"]:
						try:
							gruppe = ADgroup.objects.get(common_name__iexact=gruppe)
							antall += gruppe.membercount
						except:
							print(f"fant ikke gruppen {gruppe}")
							pass
				else: # Det er 1 eller flere grupper som skal AND-es sammen. Vi må derfor lese ut faktiske identer.
					gruppeemdlemmer = rapport_konkrete_brukere(i["grupper"])
					AND_gruppemedlemmer = rapport_konkrete_brukere(i["AND_grupper"])
					medlemmer_snitt = gruppeemdlemmer.intersection(AND_gruppemedlemmer)

					antall = len(medlemmer_snitt)
					i["konkrete_medlemmer"] = list(medlemmer_snitt)

				i["medlemmer"] = antall
				return i


			statistikk = []
			for i in innhentingsbehov:
				statistikk.append(rapport_hent_statistikk(i))

			for s in statistikk:
				if s["tidslinjedata"] != None:
					tidslinjedata = json.loads(s["tidslinjedata"])
				else:
					tidslinjedata = []

				date_str = datetime.now().strftime("%d.%m")
				tidslinjedata.append({"date": date_str, "count": s["medlemmer"]})

				object_ref = s["id"]
				object_ref.tidslinjedata = json.dumps(tidslinjedata)
				object_ref.save()

			#logg dersom vellykket
			logg_message = f"Innlasting av statistikk utført."
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message
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
