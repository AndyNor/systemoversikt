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
			systemer_eier_for = System.objects.filter(systemeier_kontaktpersoner_referanse=ansvarlig.pk)
			systemer_forvalter_for = System.objects.filter(systemforvalter_kontaktpersoner_referanse=ansvarlig.pk)

			if systemer_eier_for or systemer_forvalter_for: #hvis begge er tomme dropper vi å sende mail

				systemer_eier = ""
				for system in systemer_eier_for:
					systemer_eier = "\n".join((systemer_eier, system.systemnavn))

				systemer_forvalter = ""
				for system in systemer_forvalter_for:
					systemer_forvalter = "\n".join((systemer_forvalter, system.systemnavn))

				url = reverse("ansvarlig",args=[ansvarlig.pk])
				fornavn = ansvarlig.brukernavn.first_name

				subject = "Oppdatering: invitasjon til forum for systemeiere i Oslo kommune"
				reply_to = "thomas.rigvar@byr.oslo.kommune.no"
				recipients = [ansvarlig.brukernavn.email]
				message = '''\
Det har vært høy interesse for systemeierforum. Byrådsavdeling for finans har besluttet å endre lokale til Rådhusets nye auditorium, samt økt antall plasser.
(Du finner lokalet ved å gå inn publikumsinngangen på Rådhuset på Fridtjof Nansens plass, og ned en etasje)
Dato er fremdeles 12.12.2019 09:00-12:00.

Om du forsøkte å melde deg på - men ikke fikk plass, kan du nå gjøre et nytt forsøk.
https://tjenester.oslo.kommune.no/ekstern/arrangement/bestilling/bestilling.aspx?Arrangement=033ff634-de2b-4cc2-8778-3d74b76edce8

---

Denne e-posten er sendt ut fra Kartoteket til alle som er registrert som eier eller forvlater av et system.
Du er registrert som eier av følgende systemer:
{systemer_eier}

Du er registrert som forvalter av følgende systemer:
{systemer_forvalter}

Gå til https://kartoteket.oslo.kommune.no{url} for en komplett oversikt over dine ansvarsområder knyttet til systemer og behandling.

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