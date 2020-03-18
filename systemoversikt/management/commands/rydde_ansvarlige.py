# -*- coding: utf-8 -*-

"""
Hensikten med denne koden å
"""

from django.core.management.base import BaseCommand
from django.conf import settings
import os
import time
import sys
import json
import csv
import requests
from systemoversikt.models import ApplicationLog, Ansvarlig
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.db import transaction


# nå importert alle brukere

class Command(BaseCommand):
	def handle(self, **options):
		"""
		Her sjekker vi først klassen "ansvarlige" for alle felter og avhengig av relasjonstype identifiserer vi om det er aktive relasjoner til dem. Normalt benyttes mangetilmange-relasjoner mot ansvarlige, men det er noen få unntak med OneToOneFields.
		"""

		runtime_t0 = time.time()
		antall_slettet = 0

		@transaction.atomic
		def perform_atomic_update():
			alle_ansvarlige = Ansvarlig.objects.all()
			m2m_relations = []
			fk_relations = []

			print("Identifiserer aktuelle relasjonsfelt:\n")

			for f in Ansvarlig._meta.get_fields(include_hidden=False):
				if f.get_internal_type() in ["ManyToManyField"]:
					#print(f.__dict__)
					m2m_relations.append(f)

				if f.get_internal_type() in ["ForeignKey"]:
					#print(f.__dict__)
					fk_relations.append(f)

			for m2m in m2m_relations:
				print("%s.%s" % (m2m.related_model._meta, m2m.field.name))
			for fk in fk_relations:
				print("%s.%s" % (fk.related_model._meta, fk.field.name))

			print("\nLeter etter brukere som kan deaktiveres")


			for ansvarlig in alle_ansvarlige:
				ansvar_teller = 0
				for m2m in m2m_relations:
					ansvarlig_for = getattr(ansvarlig, m2m.name).all()
					ansvar_teller += len(ansvarlig_for)

				for fk in fk_relations:
					model = fk.related_model
					fieldname =  fk.field.name
					ansvarlig_for = model.objects.filter(**{ fieldname: ansvarlig.pk})
					ansvar_teller += len(ansvarlig_for)

				if ansvar_teller == 0:
					print("* %s slettes" % ansvarlig)
					ansvarlig.delete()
					nonlocal antall_slettet
					antall_slettet += 1


		perform_atomic_update()

		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		logg_entry_message = "Kjøretid: %s sekunder. Slettet %s ansvarlige uten ansvar." % (
				round(logg_total_runtime, 1),
				antall_slettet,
		)
		print(logg_entry_message)
		logg_entry = ApplicationLog.objects.create(
				event_type='Rydde ansvarlige',
				message=logg_entry_message,
		)
