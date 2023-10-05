# -*- coding: utf-8 -*-

# En enkel skanner for å sjekke om server er et åpent rele. Kjøres ved behov.

from django.core.management.base import BaseCommand
import smtplib

class Command(BaseCommand):
	def handle(self, **options):

		target_server = 'fill inn'
		target_port = 25
		sender = "fill inn"
		receivers = ["fill inn",]
		message = f"test av apent rele mot {target_server}."

		smtpObj = smtplib.SMTP(target_server, target_port)
		smtpObj.sendmail(sender, receivers, message)
		smtpObj.quit()