# -*- coding: utf-8 -*-

# En enkel skanner for å sjekke om server er et åpent rele. Kjøres ved behov.

from django.core.management.base import BaseCommand
import smtplib

class Command(BaseCommand):
	def handle(self, **options):

		email = EmailMessage(
				subject="test av SMTP ut fra server",
				body="test av SMTP ut fra server",
				from_email=settings.DEFAULT_FROM_EMAIL,
				to=[settings.DEFAULT_FROM_EMAIL],
		)
		email.send()