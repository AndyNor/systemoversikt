# -*- coding: utf-8 -*-
#Hensikten med denne koden er å oppdatere en lokal oversikt over alle AD-grupper, både for å kunne analysere medlemskap, f.eks. tomme grupper, kunne finne grupper som ikke stammer fra AD, kunne følge med på opprettelse av nye grupper.

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from django.contrib.auth.models import User
from systemoversikt.views import ldap_users_securitygroups
from systemoversikt.views import push_pushover
import os
import time

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "ad_drift_tilganger"
		LOG_EVENT_TYPE = "AD gruppemedlemskap for alle aktive driftbrukere"
		KILDE = "Active Directory OSLOFELLES"
		PROTOKOLL = "LDAP"
		BESKRIVELSE = "Tilgangsgrupper for alle aktive driftbrukere"
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

		runtime_t0 = time.time()
		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")

		try:
			antall_oppslag = 0
			driftbrukere = User.objects.filter(username__istartswith="DRIFT").filter(profile__accountdisable=False)
			antall_brukere = len(driftbrukere)
			for bruker in driftbrukere:
				antall_oppslag += 1
				if antall_oppslag % 100 == 0:
					print(f"{antall_oppslag} av {antall_brukere}")
				#print("slår opp %s" % (bruker))
				bruker.profile.adgrupper.clear() # tøm alle eksisterende
				grupper = ldap_users_securitygroups(bruker.username)
				for g in grupper:
					try:
						adg = ADgroup.objects.get(distinguishedname=g)
						bruker.profile.adgrupper.add(adg)
						bruker.profile.adgrupper_antall = len(grupper)
						bruker.save()
					except:
						print("Error, fant ikke %s" % (g))

			#logg dersom vellykket

			runtime_t1 = time.time()
			logg_total_runtime = runtime_t1 - runtime_t0

			logg_message = f"Lastet inn alle grupper for {antall_oppslag} brukere. Det tok {round(logg_total_runtime, 1)} sekunder."
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

