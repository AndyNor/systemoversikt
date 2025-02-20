# -*- coding: utf-8 -*-
from systemoversikt.models import *
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
from django.db import transaction
import json, os, re, time, sys
import pandas as pd
import numpy as np
from datetime import datetime
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.models import User

class Command(BaseCommand):
	def handle(self, **options):



		from systemoversikt.views import sharepoint_get_file
		source_filepath = f"{FILNAVN}"
		result = sharepoint_get_file(source_filepath)
		client_owner_dest_file = result["destination_file"]
		modified_date = result["modified_date"]
		print(f"Filen er datert {modified_date}")

		@transaction.atomic  # for speeding up database performance
		def run():

			# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
			import warnings
			warnings.simplefilter("ignore")

			dfRaw = pd.read_excel(client_owner_dest_file)
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			client_ower_data = dfRaw.to_dict('records')

			forloop_counter = 0
			unike_personer_i_client_ower_data = set()
			for row in client_ower_data:
				if row["Type"] == "TYKKLIENT":
					username = row["Owner"].replace("OSLOFELLES\\", "").lower()
					unike_personer_i_client_ower_data.add(username)
			unike_personer_i_client_ower_data = list(unike_personer_i_client_ower_data)
			print(f"Det er {len(unike_personer_i_client_ower_data)} unike personer logget inn på maskiner.")

			#organisatorik_education = []

			print("Opprydding")
			for profile in Profile.objects.filter(accountdisable=False).filter(account_type__in=['Ekstern']):
				if profile.o365lisence != 0:
					profile.o365lisence = 0
					profile.save()

			ant_aktive_profiler = Profile.objects.filter(accountdisable=False).filter(account_type__in=['Intern']).count()
			print("Starter gjennomgang")
			for profile in Profile.objects.filter(accountdisable=False).filter(account_type__in=['Intern']):
				forloop_counter += 1
				if forloop_counter % 5000 == 0:
					print(f"{forloop_counter} av {ant_aktive_profiler}")

				# Noen virksomheter skal ikke ha lisens fra UKE
				try:
					if profile.virksomhet.virksomhetsforkortelse.upper() in ["UDE", "BYS", "VAV", "INE", "PBE", "BBY", "KRV", "REG"]:
						profile.o365lisence = 0
						profile.save()
						#print(f"{forloop_counter} {profile} får ikke lisens fordi medlem i UDE, BYS eller VAV")
						continue
				except:
					pass


				# er i en seksjon som er knyttet til "barnehage", putt i gruppe 4
				try:
					if "barnehage" in profile.org_unit.ou.lower():
						profile.o365lisence = 4
						profile.save()
						#print(f"{forloop_counter} {profile} i gruppe 4: education")
						continue
				except:
					pass

				# mangler e-post, putt i gruppe 3
				if profile.user.email == "":
					profile.o365lisence = 3
					profile.save()
					#print(f"{forloop_counter} {profile} i gruppe 3: mangler epost")
					continue

				# har tykklient, har e-post, putt i gruppe 1
				if profile.user.username in unike_personer_i_client_ower_data:
					profile.o365lisence = 1
					profile.save()
					#print(f"{forloop_counter} {profile} i gruppe 1: Tykk klient")
					continue

				# Alle andre aktive personer, putt i gruppe 2
				profile.o365lisence = 2
				profile.save()
				#print(f"{forloop_counter} {profile} i gruppe 2: Flerbruker")
				continue

			ant_1 = len(User.objects.filter(profile__o365lisence=1))
			ant_2 = len(User.objects.filter(profile__o365lisence=2))
			ant_3 = len(User.objects.filter(profile__o365lisence=3))
			ant_4 = len(User.objects.filter(profile__o365lisence=4))

			logg_entry_message = f"Brukere i gruppe 1 - Tykk klient: {ant_1}\nBrukere i gruppe 2 - Flerbruker: {ant_2}\nBrukere i gruppe 3 - Mangler epost: {ant_3}\nBrukere i gruppe 4 - Educaton: {ant_4}"
			print(logg_entry_message)
			return logg_entry_message


		logg_entry_message = run()
		# lagre sist oppdatert tidspunkt
		int_config.dato_sist_oppdatert = modified_date # eller timezone.now()
		int_config.sist_status = logg_entry_message
		int_config.save()
