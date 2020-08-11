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

				subject = "Systemeierforum 19.08: Datasentermigrering og ny erstatter for PRK"
				reply_to = "thomas.rigvar@byr.oslo.kommune.no"
				recipients = [ansvarlig.brukernavn.email]
				message = '''\

Kommende Systemeierforum 19.august holdes kl 9-11. På programmet har vi to viktige prosesser som vil berøre de fleste systemeiere:
1.	Vi flytter til SopraSterias driftsplattform. Lær mer om hva du som systemeier trenger å forberede
2.	Oslo kommune bytter ut PRK med en ny, selvbetjent løsning for styring av tilganger.

Link til møte på Teams: https://teams.microsoft.com/l/meetup-join/19%3ameeting_ODgyNTUxOTgtYzBiMy00OWE2LTkzOWEtNjk5NzQ2MTUwN2Zi%40thread.v2/0?context=%7b%22Tid%22%3a%22e6795081-6391-442e-9ab4-5e9ef74f18ea%22%2c%22Oid%22%3a%2240bc54f7-2595-4beb-80f3-64b7621107fa%22%7d

Se for øvrig innlegg på Workplace: https://oslo.workplace.com/groups/systemeierforum/permalink/619634115636107/

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