# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import EmailMessage
from django.urls import reverse
from django.db.models import Q
from datetime import date
from systemoversikt.models import *
import os
import time
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "epost_avtaleutlop"
		LOG_EVENT_TYPE = "E-post sende avtaleutløp"
		KILDE = "E-post"
		PROTOKOLL = "SMTP"
		BESKRIVELSE = "Varsel om avtaleutløp"
		FILNAVN = ""
		URL = ""
		FREKVENS = "90 og 30 dager før utløp"

		try:
			int_config = IntegrasjonKonfigurasjon.objects.get(kodeord=INTEGRASJON_KODEORD)
		except:
			int_config = IntegrasjonKonfigurasjon.objects.create(
					kodeord=INTEGRASJON_KODEORD,
					kilde=KILDE,
					protokoll=PROTOKOLL,
					informasjon=BESKRIVELSE,
					sp_filnavn=FILNAVN,
					url=URL,
					frekvensangivelse=FREKVENS,
					log_event_type=LOG_EVENT_TYPE,
				)

		SCRIPT_NAVN = os.path.basename(__file__)
		int_config.script_navn = SCRIPT_NAVN
		int_config.sp_filnavn = json.dumps(FILNAVN)
		int_config.helsestatus = "Forbereder"
		int_config.save()

		runtime_t0 = time.time()
		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")

		try:
			varslingstidspunkt = [90, 30] # dager før utløp. merk at det ikke er noen hukommelse på utsendte varsler.
			antall_klargjort = 0

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
					)
					email.send()
					antall_klargjort += 1

			#logg dersom vellykket
			logg_message = f"Klargjøring av {antall_klargjort} e-post til forvaltere utført. "
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# lagre sist oppdatert tidspunkt
			runtime_t1 = time.time()
			logg_total_runtime = int(runtime_t1 - runtime_t0)
			print(f"Det tok {logg_total_runtime} sekunder")
			int_config.runtime = logg_total_runtime
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message
			int_config.helsestatus = "Vellykket"
			int_config.save()


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			import traceback
			int_config.helsestatus = f"Feilet\n{traceback.format_exc()}"
			int_config.save()
			push_pushover(f"{SCRIPT_NAVN} feilet") # Push error