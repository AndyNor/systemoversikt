# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
from django.conf import settings
import os
import time
import sys
import json
from systemoversikt.models import System, SystemBruk
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

class Command(BaseCommand):
	def handle(self, **options):
		mangler = System.objects.filter(Q(driftsmodell_foreignkey=None) & ~Q(systemtyper=1) & Q(systemeier=None))
		for m in mangler:
			bruk = SystemBruk.objects.filter(system=m)
			if len(bruk) == 1:
				print("%s - %s" % (m, bruk[0].brukergruppe))
				m.systemeier = bruk[0].brukergruppe
				m.save()