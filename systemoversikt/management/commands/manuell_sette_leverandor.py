# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import *

class Command(BaseCommand):
	def handle(self, **options):

		# systemer på DIG Felles Azure
			#basis er Microsoft
			#appdrift manuell gjennomgang
			#utv manuell

		# systemer på DIG Felles gammel fabrikk
			#basis er 2S
			#appdrift hvis tom er 2S
			#utv er manuell

		# systemer på 	DIG Felles ITAS .NET
			#basis er 2S
			#appdrift er UVA del 2
			#utvikling er UVA del 2

		#systemer på DIG Felles Marvin
			#basis er 2S
			#appdrift er UVA del 2
			#utvikling er UVA del 2

		#systemer på DIG Felles ny fabrikk
			#basis er 2S
			#appdrift hvis tom er 2S
			#utv er manuell

		#systemer på DIG Felles RPA
			#basis er 2S
			#appdrift hvis tom er DIG
			#utv hvis tom er DIG

		# systemer på DIG OsloTek
			#basis er Microsoft
			#appdrift hvis tom er 2S
			#utv er manuell



