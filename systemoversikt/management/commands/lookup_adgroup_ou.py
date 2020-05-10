# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er
"""
from django.core.management.base import BaseCommand
from systemoversikt.models import ADgroup, ADOrgUnit, ApplicationLog
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
import sys
import os
import time

class Command(BaseCommand):
	def handle(self, **options):

		LOG_EVENT_TYPE = 'Oppslag ADgrp-ADou'
		#ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

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

		@transaction.atomic  # for speeding up database performance
		def atomic():
			for g in ADgroup.objects.filter(parent=None):
				sys.stdout.flush()
				# antar komma ikke tillates i gruppenavn ref. https://docs.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2003/cc776019(v=ws.10)?redirectedfrom=MSDN
				parent_str = ",".join(g.distinguishedname.split(',')[1:]) # alt utenom første term.
				try:
					parent = ADOrgUnit.objects.get(distinguishedname=parent_str)
					g.parent = parent
					g.save()
					print("u", end="")
				except ObjectDoesNotExist:
					nonlocal failed
					failed.append(parent_str)
					print("x", end="")
					continue
			print("\n")

		atomic()

		print("Grupper igjen uten parent:")
		for f in sorted(failed):
			print('"%s"' % f)

		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		logg_entry_message = "Kjøretid: %s. Bom: %s" % (
				round(logg_total_runtime, 1),
				len(failed),
		)
		print(logg_entry_message)
		logg_entry = ApplicationLog.objects.create(
				event_type=LOG_EVENT_TYPE,
				message=logg_entry_message,
		)