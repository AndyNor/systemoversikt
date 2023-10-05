# -*- coding: utf-8 -*-

"""
Hensikten med denne koden å laste inn offentlige begreper / LOS slik at systemer kan tagges med disse begrepene
"""

from django.core.management.base import BaseCommand
from django.db import transaction
import os
import time
import sys
from rdflib import Graph, SKOS
from django.conf import settings
from systemoversikt.models import LOS, ApplicationLog
from django.db.models import Q

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "los_begreper"
		LOG_EVENT_TYPE = "Oppdatere LOS"

		ant_nye = 0
		ant_totalt = 0
		ant_deaktivert = 0

		LOG_EVENT_TYPE = 'Digdir LOS-import'
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")
		runtime_t0 = time.time()

		g = Graph()
		g.parse("https://psi.norge.no/los/samling/kommune-los/all.rdf")
		#g.parse("systemoversikt/all.rdf")
		for subj, pred, obj in g:
			if (subj, pred, obj) not in g:
				raise Exception("Error with parsing RDF")

		"""
		Ontologien er bygget opp med "tema" og "ord".
		Det benyttes "narrower"-relasjoner og "broader"-relasjoner for å koble ord og tema sammen.
		Vi representerer dataene i en klasse som består av
			unik_id: URL til begrepet eller ordet
			verdi: Verdien (bokmål)
			kategori: Referanse til ConceptScheme-ene "ord" eller "tema" (URL)
			parent_id: Referanse til et annet ord eller tema (mange til mange)
		"""

		from functools import lru_cache
		@lru_cache(maxsize=32)
		def lookup_LRU_obj(url):
			try:
				return LOS.objects.get(unik_id=url)
			except:
				return None

		# opprette alle begreper
		all_subjects = set()
		for s in g.subjects(None, None):
			all_subjects.add(s)

			los_verdi = None
			for o in g.objects(s, SKOS.prefLabel):
				if o.language == 'nb': # bokmål
					los_verdi = o
			if los_verdi == None:
				print("LOS-import: %s har ikke label på bokmål" % s)
				continue

			if not LOS.objects.filter(unik_id=s).exists():
				ant_nye += 1
				los_obj = LOS.objects.create(
					unik_id=s,
					verdi=los_verdi,
					)

		# koble opp alle begreper
		ant_totalt = len(all_subjects)
		for s in all_subjects:
			los_obj = lookup_LRU_obj(s)
			los_obj.active = True

			for o in g.objects(s, SKOS.broader):
				#try:
				los_obj.parent_id.add(lookup_LRU_obj(o))
				#except:
					#print("LOS-import: Kunne ikke koble %s til %s, fortsetter" % (s, o))

			los_kategori = g.value(s, SKOS.inScheme, None)  # vi antar kardinalitet 1
			#try:
			if los_kategori != None:
				los_obj.kategori_ref = lookup_LRU_obj(los_kategori)
			#except:
			#	print("LOS-import: Kunne ikke finne referanse til kategori for %s" % (los_kategori))

			los_obj.save()


		#opprydding
		from django.utils import timezone
		from datetime import timedelta
		tidligere = timezone.now() - timedelta(hours=6) # 6 timer gammelt
		deaktive_begrep = LOS.objects.filter(sist_oppdatert__lte=tidligere)
		for b in deaktive_begrep:
			b.active = False
			b.save()
			ant_deaktivert += 1
			print("LOS-import: %s satt deaktiv" % a)



		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		logg_entry_message = "Kjøretid: %s sekunder.\nImport av Digdir LOS er utført. %s totalt og %s nye. %s deaktivert." % (
				round(logg_total_runtime, 1),
				ant_totalt,
				ant_nye,
				ant_deaktivert,

		)
		print(logg_entry_message)
		logg_entry = ApplicationLog.objects.create(
				event_type=LOG_EVENT_TYPE,
				message=logg_entry_message,
		)

