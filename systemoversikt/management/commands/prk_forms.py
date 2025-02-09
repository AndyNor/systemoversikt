# -*- coding: utf-8 -*-
#Hensikten med denne koden er å laste inn alle aktive PRK-valg.

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from django.conf import settings
from systemoversikt.models import *
from django.db.models import Q
import requests
import os
import time
import sys

class Command(BaseCommand):
	def handle(self, **options):

		#in case the need to reset all
		#for v in PRKvalg.objects.all():
		#	v.delete()

		INTEGRASJON_KODEORD = "prk_forms"
		LOG_EVENT_TYPE = 'PRK-skjemaimport'
		KILDE = "PRK"
		PROTOKOLL = "REST"
		BESKRIVELSE = "Tilgangsskjema"
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

		try:

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")
			runtime_t0 = time.time()

			url = os.environ["PRK_FORM_URL"]
			apikey = os.environ["PRK_FORM_APIKEY"]
			headers = {"apikey": apikey}
			LOCAL_DEBUG = False
			debug_file = os.path.dirname(os.path.abspath(__file__)) + "/lokalt/prk_forms_result.json"


			if os.environ['THIS_ENV'] == "PROD":
				print(f"Connecting to {url}...")
				r = requests.get(url, headers=headers)
				if r.status_code == 200:
					data = r.json()
				else:
					message = "PRK_skjemaimport klarte ikke koble til API"
					logg_entry = ApplicationLog.objects.create(
							event_type=LOG_EVENT_TYPE,
							message=message,
					)
					#sys.exit(message)

			if os.environ['THIS_ENV'] == "TEST":
				#print(f"Opening test file {debug_file}")
				#with open(debug_file, 'r') as file:
				#	import_data = file.read()
				#data = json.loads(import_data)
				print(f"Connecting to {url}...")
				r = requests.get(url, headers=headers)
				if r.status_code == 200:
					data = r.json()
				else:
					message = "PRK_skjemaimport klarte ikke koble til API"
					logg_entry = ApplicationLog.objects.create(
							event_type=LOG_EVENT_TYPE,
							message=message,
					)

			ant_eksisterende_valg = 0
			ant_nye_valg = 0
			ant_oppdateringer = 0
			ant_slettet = 0


			#alle eksisterende valg, for å kunne oppdage om valg er tatt bort mellom synkronisering
			sjekk_alle_gruppenavn = list(PRKvalg.objects.values_list('gruppenavn', flat=True))

			@transaction.atomic  # for speeding up database performance
			def atomic():
				#print(data[0:10])
				idx = 0
				antall_records = len(data)
				for item in data:

					idx += 1
					if idx % 1500 == 0:
						print(f"{idx} av {antall_records}")

					#sys.stdout.flush()
					skjemanavn = item["skjemanavn"]
					skjematype = item["skjematype"]


					if skjematype == "LOKAL":
						er_lokalt = True
					if skjematype == "FELLES":
						er_lokalt = False

					try:
						skjema = PRKskjema.objects.get(skjemanavn=skjemanavn, skjematype=skjematype)
						skjema.er_lokalt = er_lokalt
						skjema.save()
					except:
						skjema = PRKskjema.objects.create(skjemanavn=skjemanavn, skjematype=skjematype)
						skjema.er_lokalt = er_lokalt
						skjema.save()
						# Mangler virksomhet (kan finne fra gruppe) - men trenger egentlig ikke

					feltnavn = item["feltnavn"] # gruppering
					if feltnavn == None:
						# dataene her tilhører skjemaet
						continue
					else:
						try:
							gruppe = PRKgruppe.objects.get(feltnavn=feltnavn)
						except:
							gruppe = PRKgruppe.objects.create(feltnavn=feltnavn)

					valgnavn = item["valgnavn"]
					if valgnavn == None:
						# betyr at dette er en "parent", bør ikke importeres og kan fjernes fra API-et.
						continue

					# PRK lager alltid et DS-prefiks. Det finnes GS-prefix i AD, men de skal vist ikke komme fra AD.
					helt_gruppenavn = "CN=DS-%s,%s,%s" % (item["gruppenavn"],item["relpath"],"DC=oslofelles,DC=oslo,DC=kommune,DC=no")
					if helt_gruppenavn in sjekk_alle_gruppenavn:
						sjekk_alle_gruppenavn.remove(helt_gruppenavn)



					try:
						tbf = re.search("ou=([A-Z]{3,5}),ou=Tilgangsgrupper,ou=OK", helt_gruppenavn).group(1)
						virksomhet = Virksomhet.objects.get(virksomhetsforkortelse=tbf)
					except:
						virksomhet = None

					try:
						valg = PRKvalg.objects.get(gruppenavn=helt_gruppenavn)
						nonlocal ant_eksisterende_valg
						ant_eksisterende_valg += 1

						if (valg.valgnavn != valgnavn) or (valg.beskrivelse != item["beskrivelse"]) or (valg.virksomhet != virksomhet):
							valg.valgnavn = valgnavn
							valg.beskrivelse = item["beskrivelse"]
							valg.virksomhet = virksomhet
							valg.save()

							nonlocal ant_oppdateringer
							ant_oppdateringer += 1
					except:  # finnes ikke fra før av
						nonlocal ant_nye_valg
						ant_nye_valg += 1

						valg = PRKvalg.objects.create(
								valgnavn=valgnavn,
								gruppenavn=helt_gruppenavn,
								beskrivelse=item["beskrivelse"],
								gruppering=gruppe,
								skjemanavn=skjema,
								virksomhet=virksomhet,
							)

			atomic()

			@transaction.atomic  # for speeding up database performance
			def opprydding():
				print("Rydder opp..")
				#sjekke om det er eksisterende valg som må fjernes (skjema, grupper og valg)
				for valg in sjekk_alle_gruppenavn:
					valg = PRKvalg.objects.get(gruppenavn=valg)

					ad_group = valg.ad_group_ref
					if ad_group != None:
						ad_group.from_prk = False  # hvis vi oppdager at valget er borte, merker vi AD-gruppen som "ikke fra AD"
						ad_group.save()

					valg.delete()
					#print("x", end="")
					nonlocal ant_slettet
					ant_slettet += 1
				for skjema in PRKskjema.objects.filter(PRKvalg_skjemanavn__isnull=True): # ingen flere referanser tilbake
					skjema.delete()
				for gruppe in PRKgruppe.objects.filter(PRKvalg_gruppering__isnull=True): # ingen flere referanser tilbake
					gruppe.delete()

			opprydding()

			message = "Import av PRK-data: %s eksisterende, %s nye, derav %s oppdateringer. %s slettet." % (
					ant_eksisterende_valg,
					ant_nye_valg,
					ant_oppdateringer,
					ant_slettet
				)
			print(message)

			runtime_t1 = time.time()
			logg_total_runtime = runtime_t1 - runtime_t0

			logg_entry_message = "Kjøretid: %s: %s" % (
					round(logg_total_runtime, 1),
					message

			)
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_entry_message,
			)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_entry_message
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

