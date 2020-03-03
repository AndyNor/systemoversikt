# -*- coding: utf-8 -*-

"""
Hensikten med denne koden er å laste inn alle aktive PRK-valg.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
import os
import time
import sys

from django.conf import settings
from systemoversikt.models import *
from django.db.models import Q
import requests

class Command(BaseCommand):
	def handle(self, **options):

		#in case the need to reset all
		#for v in PRKvalg.objects.all():
		#	v.delete()

		runtime_t0 = time.time()

		url = os.environ["PRK_FORM_URL"]
		apikey = os.environ["PRK_FORM_APIKEY"]
		headers = {"apikey": apikey}
		LOCAL_DEBUG = False
		debug_file = os.path.dirname(os.path.abspath(__file__)) + "/prk_forms_result.json"


		if LOCAL_DEBUG == False:
			r = requests.get(url, headers=headers)
			if r.status_code == 200:
				data = r.json()
				#with open('debug_file', 'w') as outfile:
				#json.dump(data, outfile)
			else:
				message = "PRK_skjemaimport klarte ikke koble til API"
				logg_entry = ApplicationLog.objects.create(
						event_type='PRK-skjemaimport',
						message=message,
				)
				sys.exit(message)

		if LOCAL_DEBUG == True:
			with open(debug_file, 'r') as file:
				import_data = file.read()
			data = json.loads(import_data)


		ant_eksisterende_valg = 0
		ant_nye_valg = 0
		ant_oppdateringer = 0
		ant_slettet = 0


		#alle eksisterende valg, for å kunne oppdage om valg er tatt bort mellom synkronisering
		sjekk_alle_gruppenavn = list(PRKvalg.objects.values_list('gruppenavn', flat=True))

		@transaction.atomic  # for speeding up database performance
		def atomic():
			for item in data:

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
				print("x", end="")
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
				event_type='PRK-skjemaimport',
				message=logg_entry_message,
		)
