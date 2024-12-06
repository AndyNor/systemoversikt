from django.core.management.base import BaseCommand
import os
import simplejson as json
from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient
from systemoversikt.models import *
from dateutil import parser

class Command(BaseCommand):
	def handle(self, **options):

		maks = 0
		for system in System.objects.values('systemnavn', 'alias'):
			try:
				if len(system['alias']) > 100:
					print(system['systemnavn'])
				if len(system['alias']) > maks:
					maks = len(system['alias'])
			except:
				pass
		print(maks)