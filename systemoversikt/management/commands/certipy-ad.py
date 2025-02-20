# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from systemoversikt.views import push_pushover
from systemoversikt.models import *
from django.utils import timezone
from datetime import datetime
import subprocess
import os, time

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "ad_certificate_templates"
		LOG_EVENT_TYPE = "ADCS sårbare maler"
		KILDE = "Active Directory OSLOFELLES"
		PROTOKOLL = "LDAP"
		BESKRIVELSE = "Søk etter sårbare sertifikatmaler"
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
			username = os.environ['KARTOTEKET_LDAPUSER'].split("\\")[1]
			password = os.environ['KARTOTEKET_LDAPPASSWORD']
			ldap_server = os.environ["KARTOTEKET_LDAPSERVER"]

			command = f"certipy find -json -stdout -dc-only -u {username} -p {password} -target {ldap_server} -enabled -vulnerable -timeout 240"
			result = subprocess.check_output(command, shell=True)


			logg_message = f"Kjøring av Certipy utført"
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