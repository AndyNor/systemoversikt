# -*- coding: utf-8 -*-
from django.utils import timezone
from datetime import timedelta
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from datetime import datetime
from systemoversikt.models import *
from django.db.models import Q
import os, time

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "lokal_match_system_adgrp"
		LOG_EVENT_TYPE = "Koble system og adgrp"
		KILDE = "Lokal"
		PROTOKOLL = "N/A"
		BESKRIVELSE = "Koble systemer med AD-grupper"
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

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
		runtime_t0 = time.time()

		try:

			antall_records = System.objects.filter(ibruk=True).count()
			for idx, s in enumerate(System.objects.filter(ibruk=True).all()):
				if idx % 100 == 0:
					print(f"{idx} av {antall_records}")
				if hasattr(s, "bs_system_referanse"):
					if s.bs_system_referanse != None:
						lookup_words = []
						if len(s.systemnavn.split("(")[0].strip()) > 3:
							lookup_words.append(s.systemnavn.split("(")[0].strip())
						if s.alias != None:
							for a in s.alias.split():
								if len(a.split("(")[0].strip()) > 3:
									lookup_words.append(a.split("(")[0].strip())
						#print(lookup_words)
						for word in lookup_words:
							adgrp = ADgroup.objects.filter(Q(common_name__icontains=word) | Q(display_name__icontains=word))
							for grp in adgrp:
								# Aktive PRK-valg
								if len(grp.prkvalg.all()) > 0:
									for prkvalg in grp.prkvalg.all():
										#print("   PRK:%s: %s - %s" % (grp.common_name, prkvalg.skjemanavn, prkvalg))
										if s not in prkvalg.systemer.all():
											prkvalg.systemer.add(s)
											prkvalg.save()
								#print("   ADgruppe:%s (%s)" % (grp.common_name, grp.display_name))
								if s not in grp.systemer.all():
									grp.systemer.add(s)
									grp.save()
						#print("------")

			logg_entry_message = "Slått opp AD-grupper for alle system"
			print(logg_entry_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_entry_message
			runtime_t1 = time.time()
			int_config.runtime = int(runtime_t1 - runtime_t0)
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