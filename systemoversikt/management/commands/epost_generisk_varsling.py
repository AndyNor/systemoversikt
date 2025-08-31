# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import os, time
from systemoversikt.models import *
from dateutil import parser
from django.utils import timezone
import datetime
from systemoversikt.views import push_pushover
from django.conf import settings
from django.core.mail import EmailMessage

class Command(BaseCommand):

	UTSENDINGSDAG = 31  # dag av måned
	UTSENDINGER_HOVEDKONTAKT = 0
	UTSENDINGER_FORVALTERE = 0

	def handle(self, **options):

		# initielt oppsett
		INTEGRASJON_KODEORD = "systemoversikt_epostvarsling"
		KILDE = "Local"
		PROTOKOLL = ""
		BESKRIVELSE = "E-postvarsel om virksomhet- og systemansvar"
		FILNAVN = ""
		URL = ""
		FREKVENS = "Hver natt"

		LOG_EVENT_TYPE = "E-postvarsel systemoversikt"

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

		timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
		runtime_t0 = time.time()

		try:


			today = datetime.datetime.today().day
			if today == Command.UTSENDINGSDAG:

				# melding til IKT-hovedkontakter dersom ansvarlige i virksomhet er deaktivert
				for virksomhet in Virksomhet.objects.filter(ordinar_virksomhet=True):

					subject = "Kartoteket: Påminnelse om ansatte med ansvar som har sluttet"
					recipients = [ansvarlig.brukernavn.email for ansvarlig in virksomhet.ikt_kontakt.all()]

					ansvarlige_systemforvaltere = Ansvarlig.objects.filter(brukernavn__profile__virksomhet=virksomhet).filter(~Q(system_forvalter_for=None))
					ansvarlige_systemforvaltere_html = "".join([f"\n<li><a href=\"https://kartoteket.oslo.kommune.no/brukere/ad/{ansvarlig.brukernavn.pk}/\">{ansvarlig.brukernavn}</a></li>" for ansvarlig in ansvarlige_systemforvaltere])
					ansvarlige_systemforvaltere_html = f"<p>Deaktive personer angitt som systemforvalter:\n<ol>{ansvarlige_systemforvaltere_html}\n</ol></p>" if len(ansvarlige_systemforvaltere) > 0 else "<p>Dere har ingen deaktiverte systemforvaltere. Godt jobbet!</p>"

					ansvarlige_lokale_systemforvaltere = Ansvarlig.objects.filter(brukernavn__profile__virksomhet=virksomhet).filter(~Q(systembruk_forvalter_for=None))
					ansvarlige_lokale_systemforvaltere_html = "".join([f"\n<li><a href=\"https://kartoteket.oslo.kommune.no/brukere/ad/{ansvarlig.brukernavn.pk}/\">{ansvarlig.brukernavn}</a></li>" for ansvarlig in ansvarlige_lokale_systemforvaltere])
					ansvarlige_lokale_systemforvaltere_html = f"\n<p>Deaktive personer angitt som lokal systemforvalter:\n<ol>{ansvarlige_lokale_systemforvaltere_html}\n</ol></p>" if len(ansvarlige_lokale_systemforvaltere) > 0 else "<p>Dere har ingen deaktiverte lokale systemforvaltere. Godt jobbet!</p>"

					antall_inaktive = len(ansvarlige_systemforvaltere) + len(ansvarlige_lokale_systemforvaltere)

					forklaring = "<p>Det kan hende at et navn listet opp her skylles en midlertidig deaktivering, men dersom det er en permanent endring ber vi deg sørge for at ansvaret flyttes over på personer som jobber fast i virksomheten. Når dere klikker på de deaktive navnene, vil dere se en oppsummeringsside med roller og ansvar vedkommende har. For å flytte alt ansvar til en ny person, kan du bruke dere linken \"flytt ansvaret til en annen person\". Dersom ansvaret  skal fordeles på nye personer, må du inn på hver enkelt rolle, system eller systembruk for å angi ansvar direkte der.</p>" if antall_inaktive > 0 else ""

					message = f"""
Hei IKT-hovedkontakter i {virksomhet.virksomhetsforkortelse},
<p>Denne e-posten går ut en gang per måned</p>
{ansvarlige_systemforvaltere_html}
{ansvarlige_lokale_systemforvaltere_html}
<p>For en oversikt over alle ansvarlige for din virksomhet kan du gå til <a href="https://kartoteket.oslo.kommune.no/virksomhet/ansvarlige/{virksomhet.pk}/">https://kartoteket.oslo.kommune.no/virksomhet/ansvarlige/{virksomhet.pk}/</a></p>
<p>Hver natt kjøres det en bakgrunnsjobb i Kartoteket for å slette ansvarlige som ikke lenger har roller eller ansvar.</p>
<p>Husk også å sjekke om virksomhetens kontaktpersoner er oppdatert på https://kartoteket.oslo.kommune.no/virksomhet/min/ via knappen "Rediger virksomhetsdetaljer og kontaktpersoner".</p>
<br><br>Vennlig hilsen<br>Kartoteket
"""
					email = EmailMessage(
							subject=subject,
							body=message,
							from_email=settings.DEFAULT_FROM_EMAIL,
							to=recipients,
					)
					email.content_subtype = "html"
					if recipients:
						print(f"E-post er lagt til kø for utsending til {virksomhet.virksomhetsforkortelse}")
						#email.send()
						Command.UTSENDINGER_HOVEDKONTAKT += 1
					else:
						print(f"Kan ikke sende e-post til {virksomhet.virksomhetsforkortelse} fordi det mangler e-post på hovedkontakt")



				# melding til alle systemforvaltere og lokale systemforvaltere om hva er er oppgitt som ansvarlig for samt oppfordre til å oppdatere
				for ansvarlig in Ansvarlig.objects.filter(brukernavn__profile__accountdisable=False): # alle aktive ansvarlige
					system_forvalter_for = ansvarlig.system_forvalter_for.all()
					systembruk_forvalter_for = ansvarlig.systembruk_forvalter_for.all()

					sum_ansvar = len(system_forvalter_for) + len(systembruk_forvalter_for)
					if sum_ansvar < 1:
						continue # ikke send melding og hopp til neste ansvarlige

					system_forvalter_for_html = "".join([f"\n<li><a href=\"https://kartoteket.oslo.kommune.no/systemer/detaljer/{system.pk}/\">{system}</a></li>" for system in system_forvalter_for])
					system_forvalter_for_html = f"\n<p>Systemer du er angitt som forvalter for:\n<ol>{system_forvalter_for_html}\n</ol></p>" if len(system_forvalter_for) > 0 else "<p>Du er ikke registrert som systemforvalter direkte på noe system.</p>"

					systembruk_forvalter_for_html = "".join([f"\n<li><a href=\"https://kartoteket.oslo.kommune.no/systemer/bruk/{systembruk.pk}/\">{systembruk}</a></li>" for systembruk in systembruk_forvalter_for])
					systembruk_forvalter_for_html = f"\n<p>Systemer du er angitt som lokal forvalter for:\n<ol>{systembruk_forvalter_for_html}\n</ol></p>" if len(systembruk_forvalter_for) > 0 else "<p>Du er ikke registrert som lokal systemforvalter for noe system.</p>"


					subject = "Kartoteket: Påminnelse om dine roller i systemoversikten"
					recipients = [ansvarlig.brukernavn.email]
					recipients = ["andre.nordbo@uke.oslo.kommune.no"]
					message = f"""
Hei {ansvarlig.brukernavn.profile.displayName},
<p>Denne e-posten går ut en gang per måned for å minne deg om dine roller i systemoversikten.</p>
{system_forvalter_for_html}
{systembruk_forvalter_for_html}
<p>Hvis du ser noe du ikke kjenner deg igjen i her, ber vi deg ta kontakt med din IKT-organisasjon for å avklare ansvaret. Du kan høre med din nærmeste leder eller eventuelt med din nærmeste IKT-hovedkontakt.</p>
<p>Det kan hende du har flere roller i systemoversikten enn de som er listet opp her. For full oversikt kan du gå til <a href="https://kartoteket.oslo.kommune.no/brukere/ad/{ansvarlig.brukernavn.pk}/">https://kartoteket.oslo.kommune.no/brukere/ad/{ansvarlig.brukernavn.pk}/</a>.</p>
<br><br>Vennlig hilsen<br>Kartoteket
"""
					#print(message)
					email = EmailMessage(
							subject=subject,
							body=message,
							from_email=settings.DEFAULT_FROM_EMAIL,
							to=recipients,
					)
					email.content_subtype = "html"
					if recipients:
						print(f"E-post er lagt til kø for utsending til {ansvarlig.brukernavn}")
						email.send()
						Command.UTSENDINGER_FORVALTERE += 1
					else:
						print(f"Kan ikke sende e-post til {ansvarlig.brukernavn} fordi det mangler e-postadresse")



				logg_message = f"Klartgjort e-post om ansvarlige som har sluttet og melding til alle systemforvaltere. Klargjort {Command.UTSENDINGER_HOVEDKONTAKT} e-poster til hovedkontakter og {Command.UTSENDINGER_FORVALTERE} meldinger til forvaltere."

			else:
				logg_message = f"Det er ikke dag {Command.UTSENDINGSDAG} av måneden og dropper derfor utsending"


			# logge og fullføre
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
				)
			print(logg_message)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = logg_message

			runtime_t1 = time.time()
			logg_total_runtime = int(runtime_t1 - runtime_t0)
			int_config.runtime = logg_total_runtime
			int_config.elementer = None
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

