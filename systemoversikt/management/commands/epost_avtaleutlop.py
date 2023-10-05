# -*- coding: utf-8 -*-
#Vi går her igjennom alle avtaler og sjekker om- og når de går ut, slik at vi kan varsle riktige personer.

from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import EmailMessage
from systemoversikt.models import Ansvarlig, Avtale
from django.urls import reverse
from django.db.models import Q
from datetime import date

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "epost_avtaleutlop"
		LOG_EVENT_TYPE = "E-post sende avtaleutløp"
		varslingstidspunkt = [90, 30] # dager før utløp. merk at det ikke er noen hukommelse på utsendte varsler.

		alle_relevante_avtaler = Avtale.objects.filter(fornying_varsling_valg=True) # kun avtaler hvor det er krysset av for varsling
		for avtale in alle_relevante_avtaler:
			if not avtale.fornying_dato:
				#print("Ingen dato å varsle på")
				continue

			dager_til_utlop = (avtale.fornying_dato - date.today()).days
			if not dager_til_utlop in varslingstidspunkt:
				#print("Ikke riktig tidspunkt å varsle på")
				continue

			e_post_mottakere = []
			e_post_mottakere.extend([person.brukernavn.email for person in avtale.avtaleansvarlig.all()]) # sende til alle avtaleansvarlige
			e_post_mottakere.extend([person.brukernavn.email for person in avtale.fornying_ekstra_varsling.all()]) # sende til alle andre oppgitt som mottakere

			avtale_url = reverse("avtaledetaljer", args=[avtale.pk])
			avtalenavn = avtale.kortnavn

			subject = "Kartoteket: Påminnelse om avtaleutløp"
			reply_to = "andre.nordbo@uke.oslo.kommune.no"
			recipients = e_post_mottakere
			message = '''\

Hei,

I Kartoteket er du oppgitt som mottaker av varsel når denne avtalen er i ferd med å utløpe.
Det gjelder avtalen {avtalenavn} som du finner på https://kartoteket.oslo.kommune.no{url}
Avtalen utløper om {dager_til_utlop} dager.

Hilsen Kartoteket

'''.format(avtalenavn=avtalenavn, url=avtale_url, dager_til_utlop=dager_til_utlop)

			if recipients:
				email = EmailMessage(
						subject=subject,
						body=message,
						from_email=settings.DEFAULT_FROM_EMAIL,
						to=recipients,
						reply_to=[reply_to],
				)
				email.send()