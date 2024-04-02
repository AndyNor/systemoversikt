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

		skip_sharepoint = False # Sett til True ved lokal testing

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
				"citrix_is_servers": "citrix_Machine_list_IS.json",
				"citrix_ss_servers": "citrix_Machine_list_SS.json",
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
			sp_citrix_is_servers = FILNAVN["citrix_is_servers"]
			sp_citrix_ss_servers = FILNAVN["citrix_ss_servers"]

			if skip_sharepoint:
				citrix_is_lokalfil, citrix_is_date = ("systemoversikt/import/citrix_publikasjoner_is.json", None)
				citrix_ss_lokalfil, citrix_ss_date = ("systemoversikt/import/citrix_publikasjoner_ss.json", None)
				citrix_is_desktop_gr_lokalfil, citrix_is_desktop_gr_date = ("systemoversikt/import/citrix_BrokerDesktopGroups_is.json", None)
				citrix_ss_desktop_gr_lokalfil, citrix_ss_desktop_gr_date = ("systemoversikt/import/citrix_BrokerDesktopGroups_ss.json", None)
				citrix_is_servers, citrix_is_servers_date = ("systemoversikt/import/citrix_Machine_list_IS.json.json", None)
				citrix_ss_servers, citrix_ss_servers_date = ("systemoversikt/import/citrix_Machine_list_SS.json.json", None)
			else:
				citrix_is_lokalfil, citrix_is_date = hent_fil(sp_citrix_is)
				citrix_ss_lokalfil, citrix_ss_date = hent_fil(sp_citrix_ss)
				citrix_is_desktop_gr_lokalfil, citrix_is_desktop_gr_date = hent_fil(sp_citrix_is_desktop_gr)
				citrix_ss_desktop_gr_lokalfil, citrix_ss_desktop_gr_date = hent_fil(sp_citrix_ss_desktop_gr)
				citrix_is_servers, citrix_is_servers_date = hent_fil(sp_citrix_is_servers)
				citrix_ss_servers, citrix_ss_servers_date = hent_fil(sp_citrix_ss_servers)

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

					c.display_name = f"{line['BrowserName']} - {line['ApplicationName']}"
					c.publikasjon_json = json.dumps(line)
					c.publikasjon_active = line['Enabled']
					c.save()


				logg_entry_message = f'Fant {antall_records} publikasjoner datert {dato} i {filnavn}'
				print(logg_entry_message)
				return logg_entry_message


			def import_desktop_groups(filsti):

				print(f"Laster inn DesktopGroups for {filsti}...")
				with open(filsti, 'r', encoding="utf-8") as f:
					citrix_desktop_groups = f.read()
				citrix_desktop_groups_json = json.loads(citrix_desktop_groups)

				antall_ok = 0
				feilede = 0

				for entry in citrix_desktop_groups_json:
					server_name = entry["HostedMachineName"]
					try:
						server = CMDBdevice.objects.get(comp_name__iexact=server_name)
					except:
						#print(f"Fant ikke server {server_name}")
						feilede += 1
						continue

					server.citrix_desktop_group = entry["DesktopGroupName"]
					server.save()
					antall_ok += 1

				logg_entry_message = f'Oppdaterte servere fra {filsti}. {antall_ok} lagt til. {feilede} feilet.'
				print(logg_entry_message)
				return logg_entry_message


			# importer
			print(f"Importerer fra {sp_citrix_is}")
			logg_entry_message += import_citrix(sp_citrix_is, citrix_is_lokalfil, citrix_is_date, "Intern", citrix_is_desktop_gr_lokalfil)
			print(f"Importerer fra {sp_citrix_ss}")
			logg_entry_message += import_citrix(sp_citrix_ss, citrix_ss_lokalfil, citrix_ss_date, "Sikker", citrix_ss_desktop_gr_lokalfil)


			# slette gamle
			print("Sletter gamle data..")
			#CitrixPublication.objects.all().delete() # ved behov
			for_gammelt = timezone.now() - timedelta(hours=6) # 6 timer gammelt
			deaktive = CitrixPublication.objects.filter(sist_oppdatert__lte=for_gammelt).delete()


			# laste inn DesktopGroups til servere
			print("Sletter tidligere DesktopGroups på alle servere")
			CMDBdevice.objects.all().update(citrix_desktop_group=None)

			logg_entry_message += import_desktop_groups(citrix_is_servers)
			logg_entry_message += import_desktop_groups(citrix_ss_servers)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = citrix_is_date # eller timezone.now()
			int_config.sist_status = logg_entry_message
			int_config.save()

			print("Ferdig")


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# Push error
			push_pushover(f"{SCRIPT_NAVN} feilet")
