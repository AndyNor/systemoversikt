from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
from django.db import transaction
import json, os, re, time, sys
import pandas as pd
import numpy as np
from datetime import datetime
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.models import User
from systemoversikt.models import *



class Command(BaseCommand):
	def handle(self, **options):

		sp_site = os.environ['SHAREPOINT_SITE']
		client_id = os.environ['SHAREPOINT_CLIENT_ID']
		client_secret = os.environ['SHAREPOINT_CLIENT_SECRET']

		sp = da_tran_SP365(site_url = sp_site, client_id = client_id, client_secret = client_secret)

		print("Laster ned fil med klient-bruker-detaljer")
		client_owner_source_file = sp.create_link("https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/OK_computers.xlsx")
		client_owner_dest_file = 'systemoversikt/import/OK_computers.xlsx'
		sp.download(sharepoint_location = client_owner_source_file, local_location = client_owner_dest_file)

		dfRaw = pd.read_excel(client_owner_dest_file)
		dfRaw = dfRaw.replace(np.nan, '', regex=True)
		client_ower_data = dfRaw.to_dict('records')

		forloop_counter = 0
		unike_personer_i_client_ower_data = set()
		for row in client_ower_data:
			if row["Type"] == "TYKKLIENT":
				username = row["Owner"].replace("OSLOFELLES\\", "").lower()
				unike_personer_i_client_ower_data.add(username)

		organisatorik_education = []

		print("Opprydding")
		for profile in Profile.objects.filter(accountdisable=False).filter(account_type__in=['Ekstern']):
			if profile.o365lisence != 0:
				profile.o365lisence = 0
				profile.save()


		print("Starter gjennomgang")
		for profile in Profile.objects.filter(accountdisable=False).filter(account_type__in=['Intern']):
			forloop_counter += 1

			# mangler e-post, putt i gruppe 3
			if profile.user.email == "":
				profile.o365lisence = 3
				profile.save()
				print(f"{forloop_counter} {profile} i gruppe 3: mangler epost")
				continue

			# er i organisatorik_education, putt i gruppe 4



			# har tykklient, har e-post, putt i gruppe 1
			if profile.user.username in list(unike_personer_i_client_ower_data):
				profile.o365lisence = 1
				profile.save()
				print(f"{forloop_counter} {profile} i gruppe 1: Tykk klient")
				continue


			# Alle andre aktive personer, putt i gruppe 2
			profile.o365lisence = 2
			profile.save()
			print(f"{forloop_counter} {profile} i gruppe 2: Flerbruker")
			continue




		print("Brukere i gruppe 1 - Tykk klient")
		print(len(User.objects.filter(profile__o365lisence=1)))

		print("Brukere i gruppe 2 - Flerbruker")
		print(len(User.objects.filter(profile__o365lisence=2)))

		print("Brukere i gruppe 3 - mangler epost")
		print(len(User.objects.filter(profile__o365lisence=3)))

		print("Brukere i gruppe 4 - Educaton")
		print(len(User.objects.filter(profile__o365lisence=4)))