# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
from django.conf import settings
import os
import time
import sys
import json
from systemoversikt.models import *
from django.db.models import Q
import requests

class Command(BaseCommand):
	def handle(self, **options):

		#in case the need to reset all
		#for v in PRKvalg.objects.all():
		#	v.delete()

		runetime_t0 = time.time()

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
				message = "Django PRK_skjemaimport klarte ikke koble til API"
				logg_entry = ApplicationLog.objects.create(
						event_type='PRK-skjemaimport',
						message=message,
				)
				logg_entry.save()
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


		for item in data:
			try:
				skjema = PRKskjema.objects.get(skjemanavn=item["skjemanavn"], skjematype=item["skjematype"])
			except:
				skjema = PRKskjema.objects.create(skjemanavn=item["skjemanavn"], skjematype=item["skjematype"])
				# Mangler virksomhet (kan finne fra gruppe) - men trenger egentlig ikke

			feltnavn = item["feltnavn"]
			if feltnavn == None:
				feltnavn = "__mangler__"
			try:
				gruppe = PRKgruppe.objects.get(feltnavn=feltnavn)
			except:
				gruppe = PRKgruppe.objects.create(feltnavn=feltnavn)


			# PRK lager alltid et DS-prefiks. Det finnes GS-prefix i AD, men de skal vist ikke komme fra AD.
			helt_gruppenavn = "CN=DS-%s,%s,%s" % (item["gruppenavn"],item["relpath"],"DC=oslofelles,DC=oslo,DC=kommune,DC=no")
			if helt_gruppenavn in sjekk_alle_gruppenavn:
				sjekk_alle_gruppenavn.remove(helt_gruppenavn)

			valgnavn = item["valgnavn"]
			if valgnavn == None:
				valgnavn = "__mangler__"
				# betyr at dette er en "parent", bør ikke importeres og kan fjernes fra API-et.

			try:
				valg = PRKvalg.objects.get(gruppenavn=helt_gruppenavn)
				#sjekke om behov for oppdatering
				print("Valgnavn %s" % valgnavn)
				ant_eksisterende_valg += 1
				if (valg.valgnavn != valgnavn) or (valg.beskrivelse != item["beskrivelse"]):
					valg.valgnavn = valgnavn
					valg.beskrivelse = item["beskrivelse"]
					valg.save()
					ant_oppdateringer += 1
			except:
				ant_nye_valg += 1
				print("Valgnavn %s" % valgnavn)
				valg = PRKvalg.objects.create(
						valgnavn=valgnavn,
						gruppenavn=helt_gruppenavn,
						beskrivelse=item["beskrivelse"],
						gruppering=gruppe,
						skjemanavn=skjema,
					)

		print("Rydder opp..")
		#sjekke om det er eksisterende valg som må fjernes (skjema, grupper og valg)
		for valg in sjekk_alle_gruppenavn:
			valg = PRKvalg.objects.get(gruppenavn=valg)
			related_ad_groups = valg.ad_group_ref.all() # many to many
			for g in related_ad_groups:
				g.from_prk = False  # hvis vi oppdager at valget er borte, merker vi AD-gruppen som "ikke fra AD"
				g.save()
			valg.delete()
			ant_slettet += 1
		for skjema in PRKskjema.objects.filter(PRKvalg_skjemanavn__isnull=True): # ingen flere referanser tilbake
			skjema.delete()
		for gruppe in PRKgruppe.objects.filter(PRKvalg_gruppering__isnull=True): # ingen flere referanser tilbake
			gruppe.delete()

		message = "Import av PRK-data: %s eksisterende, %s nye, derav %s oppdateringer. %s slettet." % (ant_eksisterende_valg, ant_nye_valg, ant_oppdateringer, ant_slettet)
		print(message)

		runetime_t1 = time.time()
		logg_total_runtime = runetime_t1 - runetime_t0

		logg_entry_message = "Kjøretid: %s: %s" % (
				round(logg_total_runtime, 1),
				message

		)
		logg_entry = ApplicationLog.objects.create(
				event_type='PRK-skjemaimport',
				message=logg_entry_message,
		)
		logg_entry.save()
