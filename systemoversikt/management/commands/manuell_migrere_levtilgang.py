# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import *

class Command(BaseCommand):
	def handle(self, **options):

		for l in Leverandortilgang.objects.all():
			l.adgrupper.add(l.adgruppe)
			print(f"adding {l.adgruppe} to new field adgrupper")
			l.save()