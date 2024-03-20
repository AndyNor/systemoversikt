# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from systemoversikt.models import *
from django.db import transaction
import json, os, io
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from systemoversikt.views import sharepoint_get_file

class Command(BaseCommand):
	def handle(self, **options):

		skip_sharepoint = True # Sett til True ved lokal testing

		INTEGRASJON_KODEORD = "sp_citrix"
		LOG_EVENT_TYPE = "Citrix publikasjon"
		KILDE = "Citrix"
		PROTOKOLL = "Manuelt"
		BESKRIVELSE = "Citrixpubliseringer fra intern og sikker sone"
		FILNAVN = {
				"citrix_is": "citrix_publikasjoner_is.json",
				"citrix_is_desktop_gr": "citrix_BrokerDesktopGroups_is.json",
				"citrix_ss": "citrix_publikasjoner_ss.json",
				"citrix_ss_desktop_gr": "citrix_BrokerDesktopGroups_ss.json",
			}
		URL = ""
		FREKVENS = "Manuelt"

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
		int_config.save()

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")

		try:
			def hent_fil(filnavn):
				source_filepath = f"{filnavn}"
				result = sharepoint_get_file(source_filepath)
				destination_file = result["destination_file"]
				modified_date = result["modified_date"]
				print(f"{filnavn} er datert {modified_date}")
				return (destination_file, modified_date)

			sp_citrix_is = FILNAVN["citrix_is"]
			sp_citrix_ss = FILNAVN["citrix_ss"]
			sp_citrix_is_desktop_gr = FILNAVN["citrix_is_desktop_gr"]
			sp_citrix_ss_desktop_gr = FILNAVN["citrix_ss_desktop_gr"]

			if skip_sharepoint:
				citrix_is_lokalfil, citrix_is_date = ("systemoversikt/import/citrix_publikasjoner_is.json", None)
				citrix_ss_lokalfil, citrix_ss_date = ("systemoversikt/import/citrix_publikasjoner_ss.json", None)
				citrix_is_desktop_gr_lokalfil, citrix_is_desktop_gr_date = ("systemoversikt/import/citrix_BrokerDesktopGroups_is.json", None)
				citrix_ss_desktop_gr_lokalfil, citrix_ss_desktop_gr_date = ("systemoversikt/import/citrix_BrokerDesktopGroups_ss.json", None)
			else:
				citrix_is_lokalfil, citrix_is_date = hent_fil(sp_citrix_is)
				citrix_ss_lokalfil, citrix_ss_date = hent_fil(sp_citrix_ss)
				citrix_is_desktop_gr_lokalfil, citrix_is_desktop_gr_date = hent_fil(sp_citrix_is_desktop_gr)
				citrix_ss_desktop_gr_lokalfil, citrix_ss_desktop_gr_date = hent_fil(sp_citrix_ss_desktop_gr)

			logg_entry_message = ""

			@transaction.atomic
			def import_citrix(filnavn, filsti, dato, zone, desktop_groups_sti):

				with open(filsti, 'r', encoding="utf-8") as f:
					#print(f"Encoding er {f.encoding}") # de originale filene var "cp1252", men er konvertert via Sublime text editor
					data = f.read()#.encode('latin1').decode('cp1252').encode('utf-8')

				with open(desktop_groups_sti, 'r', encoding="utf-8") as f:
					desktop_gr_data = f.read()

				json_data = json.loads(data)
				json_desktop_gr = json.loads(desktop_gr_data)
				antall_records = len(json_data)

				for line in json_data:
					c, created = CitrixPublication.objects.get_or_create(publikasjon_UUID=line['UUID'])
					c.sone = zone

					AllAssociatedDesktopGroupUids_Name = []
					for desktopgroup in line['AllAssociatedDesktopGroupUids']:
						oppslag = None
						for obj in json_desktop_gr:
							if obj["Uid"] == desktopgroup:
								oppslag = obj["DesktopGroupName"]
						#print(f"{desktopgroup} --> {oppslag}")
						AllAssociatedDesktopGroupUids_Name.append(oppslag)
					line["AllAssociatedDesktopGroupUids_Name"] = AllAssociatedDesktopGroupUids_Name

					if any(sub in line["CommandLineExecutable"].lower() for sub in ["\\appv\\", "app-v", "sfttray.exe"]):
						c.type_vApp = True  # default False

					if any(sub in line["CommandLineExecutable"].lower() for sub in ["chrome.exe","firefox.exe","msedge.exe", "iexplore.exe"]):
						c.type_nettleser = True # default False

					if any(sub in line["CommandLineExecutable"].lower() for sub in ["mstsc.exe",]):
						c.type_remotedesktop = True # default False

					if any(sub in line["BrowserName"].lower() for sub in ["demo","test","kurs", "preprod"]):
						c.type_produksjon = False # default True
					if any(sub in line["ApplicationName"].lower() for sub in ["demo","test","kurs", "preprod"]):
						c.type_produksjon = False # default True

					if len(line["AssociatedUserFullNames"]) == 0:
						c.type_medlemmer = False # default True

					c.publikasjon_json = json.dumps(line)
					c.publikasjon_active = line['Enabled']
					c.save()


				logg_entry_message = f'Fant {antall_records} publikasjoner datert {dato} i {filnavn}'
				print(logg_entry_message)
				return logg_entry_message

			"""
			@transaction.atomic
			def koble_system():
				teller = 0
				alle = System.objects.all().count()
				for system in System.objects.all().order_by('tilgjengelighetsvurdering'):
					teller += 1
					if teller % 30 == 0:
						print(f"{teller} av {alle}")
					for publisering in system.citrix_publiseringer_pk():
						if publisering.systemknytning == None:
							publisering.systemknytning = system
							publisering.save()
							#print(f"Koblet {publisering} med {system}")
						else:
							pass
							#print(f"Publisering {publisering} var allerede koblet til {publisering.systemknytning}")
			"""

			#eksekver
			CitrixPublication.objects.all().delete() # ved behov
			print(f"Importerer fra {sp_citrix_is}")
			logg_entry_message += import_citrix(sp_citrix_is, citrix_is_lokalfil, citrix_is_date, "Intern", citrix_is_desktop_gr_lokalfil)
			print(f"Importerer fra {sp_citrix_ss}")
			logg_entry_message += import_citrix(sp_citrix_ss, citrix_ss_lokalfil, citrix_ss_date, "Sikker", citrix_ss_desktop_gr_lokalfil)

			#koble mot systemer
			#koble_system()

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = citrix_is_date # eller timezone.now()
			int_config.sist_status = logg_entry_message
			int_config.save()


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# Push error
			push_pushover(f"{SCRIPT_NAVN} feilet")
