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

			if systemer_eier_for: #hvis begge er tomme dropper vi å sende mail

				systemer_eier = ""
				for system in systemer_eier_for:
					systemer_eier = "\n".join((systemer_eier, system.systemnavn))

				url = reverse("ansvarlig",args=[ansvarlig.pk])
				fornavn = ansvarlig.brukernavn.first_name

				subject = "Invitasjon til forum for systemeiere i Oslo kommune"
				reply_to = "thomas.rigvar@byr.oslo.kommune.no"
				recipients = [ansvarlig.brukernavn.email]
				message = '''\
Byrådsavdeling for finans ved Seksjon for informasjonssikkerhet og IKT inviterer alle virksomhetene til det første møte i «Forum for systemeiere i Oslo kommune (Systemeierforum)».

Formål med forumet er å bidra til større bevissthet om hvilke oppgaver som ligger under systemeierrollen og til deling av kunnskap og erfaringer om hvordan oppgavene kan løses.  Forumet skal også bidra til å identifisere og løfte felles behov for utvikling av Oslo kommunes styrende dokumenter på området, slik at disse utvikles i takt med kommunens behov.

Forumet ledes av Byrådsavdeling for finans og vil avholde møter 3-5 ganger per år.  Enkeltmøter kan ha innhold som er mer rettet om systemeiere av felles- eller sektorsystemer.  Det kan nedsettes egne, mindre arbeidsgrupper for å løse definerte oppgaver.

Forumet er åpent for systemeiere og systemforvaltere i Oslo kommune. Invitasjoner til forumets møter sendes automatisk til alle som er registrert som systemeier eller forvalter i Oslo kommunes systemoversikt, og til virksomhetenes postmottak.

Det første møte avholdes torsdag 12.desember 2019 kl. 09.00 – 11.30 i kurslokalene til Utdanningsetaten i Grensesvingen 6 på Helsfyr.

Vi har 72 plasser så meld deg på innen 6. desember via:
https://tjenester.oslo.kommune.no/ekstern/arrangement/bestilling/bestilling.aspx?Arrangement=033ff634-de2b-4cc2-8778-3d74b76edce8

Se forøvrig innkallingen på https://kartoteket.oslo.kommune.no/static/filer/invitasjon%20til%20f%C3%B8rste%20m%C3%B8te%20i%20systemeierforum.pdf

---

Denne e-posten er sendt ut fra Kartoteket til alle som er registrert som eier av et system.
Du er registrert som eier av følgende systemer:
{systemer_eier}

Gå til https://kartoteket.oslo.kommune.no{url} for en komplett oversikt over dine ansvarsområder knyttet til systemer og behandling.

'''.format(fornavn=fornavn, systemer_eier=systemer_eier, url=url)

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