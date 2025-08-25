# -*- coding: utf-8 -*-

# DENNE ER HELT MANUELL. KJØRES BARE VED BEHOV

from django.core.management.base import BaseCommand
from django.conf import settings
#from mailer import send_mail
from django.core.mail import EmailMessage
from systemoversikt.models import Ansvarlig, System
from django.urls import reverse
from django.db.models import Q

class Command(BaseCommand):
	def handle(self, **options):

		"""
		La oss finne alle IKT-hovedkontakter
		"""
		hovedkontakter_og_isk = Ansvarlig.objects.filter(~Q(virksomhet_informasjonssikkerhetskoordinator__isnull=True) or Q(virksomhet_ikt_kontakt__isnull=True))


		for ansvarlig in hovedkontakter_og_isk:

			print(ansvarlig.brukernavn.email)

			subject = "Retanking av isolerte maskiner grunnet skadevareangrep"
			reply_to = "csirt@oslo.kommune.no"
			recipients = [ansvarlig.brukernavn.email]
			message = '''\
Hei,
 
info

'''


			email = EmailMessage(
					subject=subject,
					body=message,
					from_email=settings.DEFAULT_FROM_EMAIL,
					to=recipients,
					#bcc=['bcc@example.com'],
					reply_to=[reply_to],
					#headers={'Message-ID': 'foo'},
			)
			#print(email)
			#email.send()