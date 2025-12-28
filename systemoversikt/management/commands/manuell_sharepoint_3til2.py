# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from systemoversikt.models import *
from systemoversikt.views import sharepoint_get_file
import warnings
import pandas as pd


from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
import numpy as np
import os
from difflib import SequenceMatcher

class Command(BaseCommand):
	def handle(self, **options):

		sharepoint_file = sharepoint_get_file(f'Brukernavnliste.xlsx')
		content = sharepoint_file["destination_file"]
		modified_date = sharepoint_file["modified_date"]
		print(f"Filen er datert {modified_date}")
		warnings.simplefilter("ignore")

		dfRaw = pd.read_excel(content)
		dfRaw = dfRaw.replace(np.nan, '', regex=True)
		data = dfRaw.to_dict('records')

		antall_records = len(data)

		for record in data:
			email_gammel = record["Gammel_Epost"]
			email_ny = record["Ny_Epost"]

			ansvarlig = Ansvarlig.objects.filter(brukernavn__email=email_gammel).first()
			if ansvarlig:
				print(f'Fant {ansvarlig}')
				ny_ident = User.objects.filter(email=email_ny).first()
				if ny_ident:
					print(f'Oppdaterer {ansvarlig} fra {ansvarlig.brukernavn.email} til {email_ny}')
					ansvarlig.brukernavn = ny_ident
					ansvarlig.save()

					systemer = ansvarlig.system_forvalter_for.all()
					for system in systemer:
						print(f'Fjerner {system.systemforvalter_avdeling_referanse} fra {system}')
						system.systemforvalter_avdeling_referanse = None
						if ny_ident.profile.virksomhet:
							print(f'Setter {ny_ident.profile.virksomhet} som forvalter av {system}')
							system.systemforvalter = ny_ident.profile.virksomhet
						else:
							print(f'Virksomhet var None for ny ident..')
						system.save()
				else:
					print(f'Finner ikke ny ident {email_ny}')

			else:
				#print(f'Ingen treff på gammel ident {email_gammel}')
				pass


