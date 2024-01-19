# -*- coding: utf-8 -*-

# En enkel skanner for å sjekke om server er et åpent rele. Kjøres ved behov.

from django.core.management.base import BaseCommand
import smtplib
import os
from django.core.mail import EmailMessage

class Command(BaseCommand):
	def handle(self, **options):

		sender = os.environ['EMAIL_SECRET_EMAILADDR']

		email = EmailMessage(
				subject="test av SMTP ut fra server",
				body="test av SMTP ut fra server",
				from_email=sender,
				to=[sender],
		)
		email.send()