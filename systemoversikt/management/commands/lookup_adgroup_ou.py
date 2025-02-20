# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
import sys, os, time

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "lokal_match_grp_ou"
		LOG_EVENT_TYPE = 'Oppslag ADgrp-ADou'
		KILDE = "Lokal"
		PROTOKOLL = "N/A"
		BESKRIVELSE = "Kobler AD-gruppe med OU"
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

		try:

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")
			runtime_t0 = time.time()

			# built in group that are needed
			missing = [
					{"dn": "CN=Users,DC=oslofelles,DC=oslo,DC=kommune,DC=no", "ou": "Users"},
					{"dn": "CN=Builtin,DC=oslofelles,DC=oslo,DC=kommune,DC=no", "ou": "Builtin"},
					{"dn": "CN=Microsoft Exchange System Objects,DC=oslofelles,DC=oslo,DC=kommune,DC=no", "ou": "Microsoft Exchange System Objects"},
					{"dn": "DC=oslofelles,DC=oslo,DC=kommune,DC=no", "ou": "DC root"},
				]

			for item in missing:
				if len(ADOrgUnit.objects.filter(distinguishedname=item["dn"])) == 0:
					ADOrgUnit.objects.create(
							distinguishedname=item["dn"],
							ou=item["ou"]
						)

			failed = []
			vellykket = 0

			@transaction.atomic  # for speeding up database performance
			def atomic():
				nonlocal vellykket
				for g in ADgroup.objects.filter(parent=None):
					#sys.stdout.flush()
					# antar komma ikke tillates i gruppenavn ref. https://docs.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2003/cc776019(v=ws.10)?redirectedfrom=MSDN
					parent_str = ",".join(g.distinguishedname.split(',')[1:]) # alt utenom første term.
					try:
						parent = ADOrgUnit.objects.get(distinguishedname=parent_str)
						g.parent = parent
						g.save()
						vellykket += 1
						#print("u", end="")
					except ObjectDoesNotExist:
						nonlocal failed
						failed.append(parent_str)
						#print("x", end="")
						continue
				#print("\n")

			atomic()

			print("Grupper igjen uten parent:")
			for f in sorted(failed):
				print(f"* {f}")

			runtime_t1 = time.time()
			logg_total_runtime = runtime_t1 - runtime_t0
			logg_entry_message = f"Kjøretid {round(logg_total_runtime, 1)} sekunder. {vellykket} var vellykket og {len(failed)} feilet."
			print(logg_entry_message)
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_entry_message
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