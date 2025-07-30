# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import os, time
from systemoversikt.models import *
from dateutil import parser
from django.utils import timezone
import datetime
from systemoversikt.views import push_pushover
from systemoversikt.views import AZUREAPP_KEY_EXPIRE_WARNING_EXCLUDE_PREFIXES
from django.conf import settings
from django.core.mail import EmailMessage

class Command(BaseCommand):

	ANTALL_GRAPH_KALL = 0

	def handle(self, **options):

		# initielt oppsett
		INTEGRASJON_KODEORD = "azure_key_expiration_notifications"
		KILDE = "Local"
		PROTOKOLL = ""
		BESKRIVELSE = "E-postvarsel om nøkkelutløp"
		FILNAVN = ""
		URL = ""
		FREKVENS = "Hver natt"

		LOG_EVENT_TYPE = "Azure nøkkelutløp e-postvarsling"

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
			subject = "Kartoteket: Påminnelse om nøkler og sertifikater som snart utgår"
			recipients = ["andre.nordbo@uke.oslo.kommune.no"]

			ANTALL_DAGER_VARSEL = 21
			periode = (timezone.now() + datetime.timedelta(ANTALL_DAGER_VARSEL))  # antall dager frem i tid
			keys = AzureApplicationKeys.objects.filter(end_date_time__gte=timezone.now()).filter(end_date_time__lte=periode).filter(~Q(key_type="AsymmetricX509Cert",key_usage="Verify")).exclude(AZUREAPP_KEY_EXPIRE_WARNING_EXCLUDE_PREFIXES).order_by('end_date_time')

			keys_message = ""
			for key in keys:
				notes = key.application_ref.notes.replace('\n', ' ') if key.application_ref.notes else ""

				if key.application_ref.from_applications:
					link = f"<a href='https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/~/Credentials/appId/{key.application_ref.appId}'>{key.application_ref}</a>"
				else:
					link = f"<a href='https://portal.azure.com/#view/Microsoft_AAD_IAM/ManagedAppMenuBlade/~/Credentials/objectId/{key.application_ref.appId}'>{key.application_ref}</a>"

				keys_message += f"<li>App {link}: {notes}<br>{key.key_type} {key.display_name} utløper {key.end_date_time.strftime('%Y-%m-%d')}</li>"


			#print(keys_message)

			innhold = f"Nøkler som utløper de neste {ANTALL_DAGER_VARSEL} dagene:\n{keys_message}"

			message = f"<p>Dette er en automatisk e-post fra Kartoteket med formål å varsle om Azure enterprise applications med nøkler eller sertifikater som snart utgår.</p><p>{innhold}</p><p>Hilsen Kartoteket</p>"
			email = EmailMessage(
					subject=subject,
					body=message,
					from_email=settings.DEFAULT_FROM_EMAIL,
					to=recipients,
			)
			email.content_subtype = "html"
			email.send()
			print("E-post er lagt til kø for utsending")


			# logge og fullføre
			logg_message = f"Klartgjort e-post om nøkkelutløp"
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

