# -*- coding: utf-8 -*-

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
		La oss gå igjennom alle ansvarlige, se om de er eier eller forvalter for noe og så ende dem en varsel om dette per e-post
		"""
		alle_ansvarlige = Ansvarlig.objects.all() #.filter(brukernavn__profile__virksomhet__in=[163, 145])
		for ansvarlig in alle_ansvarlige:
			systemer_eier_for = System.objects.filter(systemeier_kontaktpersoner_referanse=ansvarlig.pk).filter(~Q(ibruk=False))
			systemer_forvalter_for = System.objects.filter(systemforvalter_kontaktpersoner_referanse=ansvarlig.pk).filter(~Q(ibruk=False))

			if systemer_eier_for or systemer_forvalter_for: #hvis begge er tomme dropper vi å sende mail

				systemer_eier = ""
				for system in systemer_eier_for:
					systemer_eier = "\n * ".join((systemer_eier, system.systemnavn))

				systemer_forvalter = ""
				for system in systemer_forvalter_for:
					systemer_forvalter = "\n * ".join((systemer_forvalter, system.systemnavn))

				url = reverse("ansvarlig",args=[ansvarlig.pk])
				fornavn = ansvarlig.brukernavn.first_name

				subject = "Systemeierforum 16.04: Hvordan skaper man løsninger med god brukskvalitet?"
				reply_to = "thomas.rigvar@byr.oslo.kommune.no"
				recipients = [ansvarlig.brukernavn.email]
				message = '''\

---

Denne e-posten er sendt ut fra Kartoteket til alle som er registrert som eier eller forvlater av et system.
Du er registrert som eier av følgende systemer:
{systemer_eier}

Du er registrert som forvalter av følgende systemer:
{systemer_forvalter}

Gå til https://kartoteket.oslo.kommune.no{url} for en komplett oversikt over dine ansvarsområder.

'''.format(fornavn=fornavn, systemer_eier=systemer_eier, systemer_forvalter=systemer_forvalter, url=url)

				if recipients:
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
					email.send()