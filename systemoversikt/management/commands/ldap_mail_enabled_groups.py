# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.db import transaction
from systemoversikt.models import *
from django.utils import timezone
from datetime import datetime
from systemoversikt.views import push_pushover
import json, os, time

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "ad_mail_enabled_groups"
		LOG_EVENT_TYPE = "AD gruppemedlemskap for alle aktive brukere"
		KILDE = "Active Directory OSLOFELLES"
		PROTOKOLL = "LDAP"
		BESKRIVELSE = "Mail-enabled gruppemedlemskap basert på cached AD-data"
		FILNAVN = ""
		URL = ""
		FREKVENS = "Hver natt"

		int_config, opprettet = IntegrasjonKonfigurasjon.objects.get_or_create(kodeord=INTEGRASJON_KODEORD)
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
			from systemoversikt.models import Profile

			# Build lookup: DN -> profile for all active users
			print("Henter alle aktive brukerprofiler...")
			active_profiles = Profile.objects.filter(
				accountdisable=False
			).exclude(
				distinguishedname__isnull=True
			).exclude(
				distinguishedname=""
			).select_related('user')

			dn_to_profile = {p.distinguishedname: p for p in active_profiles}
			antall_brukere = len(dn_to_profile)
			print(f"Fant {antall_brukere} aktive brukere med DN")

			# Get all mail-enabled groups
			print("Henter alle mail-enabled grupper...")
			mail_groups = ADgroup.objects.exclude(mail__isnull=True).exclude(mail="")
			antall_grupper = mail_groups.count()
			print(f"Fant {antall_grupper} mail-enabled grupper")

			# Clear all existing mail_enabled_groups for active users
			print("Fjerner eksisterende koblinger...")
			with transaction.atomic():
				for profile in active_profiles.iterator():
					profile.mail_enabled_groups.clear()

			# For each mail-enabled group, find matching users from cached member list
			print("Bygger nye koblinger fra cached data...")
			antall_koblinger = 0
			for idx, group in enumerate(mail_groups.iterator(), 1):
				if idx % 500 == 0:
					print(f"Behandlet {idx} av {antall_grupper} grupper")

				members = json.loads(group.member) if group.member else []
				matching_profiles = [dn_to_profile[dn] for dn in members if dn in dn_to_profile]

				if matching_profiles:
					with transaction.atomic():
						group.user_profile.add(*matching_profiles)
					antall_koblinger += len(matching_profiles)

			runtime_t1 = time.time()
			logg_total_runtime = runtime_t1 - runtime_t0

			logg_message = f"Oppdatert mail-enabled grupper for {antall_brukere} brukere fra {antall_grupper} grupper ({antall_koblinger} koblinger). Det tok {round(logg_total_runtime, 1)} sekunder."
			ApplicationLog.objects.create(
				event_type=LOG_EVENT_TYPE,
				message=logg_message,
			)
			print(logg_message)

			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message
			int_config.runtime = int(logg_total_runtime)
			int_config.helsestatus = "Vellykket"
			int_config.save()

		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			import traceback
			int_config.helsestatus = f"Feilet\n{traceback.format_exc()}"
			int_config.save()
			push_pushover(f"{SCRIPT_NAVN} feilet")
