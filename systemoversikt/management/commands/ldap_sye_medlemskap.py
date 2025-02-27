# -*- coding: utf-8 -*-
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
from django.db.models import Q
import os, time

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "ad_sye_tilganger"
		LOG_EVENT_TYPE = "AD gruppemedlemskap for alle aktive SYE-brukere"
		KILDE = "Active Directory OSLOFELLES"
		PROTOKOLL = "LDAP"
		BESKRIVELSE = "Tilgangsgrupper for alle aktive SYE-brukere"
		FILNAVN = ""
		URL = ""
		FREKVENS = "Hver natt"

		int_config = IntegrasjonKonfigurasjon.objects.get_or_create(kodeord=INTEGRASJON_KODEORD)
		int_config.kilde = KILDE
		int_config.protokoll = PROTOKOLL
		int_config.informasjon = BESKRIVELSE
		int_config.sp_filnavn = FILNAVN
		int_config.url = URL
		int_config.frekvensangivelse = FREKVENS
		int_config.log_event_type = LOG_EVENT_TYPE


		SCRIPT_NAVN = os.path.basename(__file__)
		int_config.script_navn = SCRIPT_NAVN
		int_config.sp_filnavn = json.dumps(FILNAVN)
		int_config.helsestatus = "Forbereder"
		int_config.save()

		runtime_t0 = time.time()
		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")

		try:
			antall_oppslag = 0
			syebrukere = User.objects.filter(profile__accountdisable=False).filter(Q(username__istartswith="SYE"))
			antall_brukere = len(syebrukere)
			for bruker in syebrukere:
				antall_oppslag += 1
				if antall_oppslag % 25 == 0:
					print(f"{antall_oppslag} av {antall_brukere}")
				#print("slår opp %s" % (bruker))
				bruker.profile.mail_enabled_groups.clear() # tøm alle eksisterende
				grupper = ldap_users_securitygroups(bruker.username)
				for g in grupper:
					try:
						adg = ADgroup.objects.get(distinguishedname=g)
						if adg.mail:
							bruker.mail_enabled_groups.add(adg)
						#bruker.profile.adgrupper.add(adg)
						#bruker.profile.adgrupper_antall = len(grupper)
						#bruker.profile.save() # Det er ikke behov for å lagre når en legger til ting
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

