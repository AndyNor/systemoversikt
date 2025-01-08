# -*- coding: utf-8 -*-
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from systemoversikt.models import *
from django.core.management.base import BaseCommand
from django.db import transaction
import json, os
import pandas as pd
import numpy as np
from django.db.models import Q
from systemoversikt.views import get_ipaddr_instance

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_network_eq"
		LOG_EVENT_TYPE = "CMDB Network device import"
		KILDE = "Service Now"
		PROTOKOLL = "SMTP og SharePoint"
		BESKRIVELSE = "BigIP instanser og nettverksinstanser"
		FILNAVN = {"filename1": "A34_CMDB_bigip_partitions.xlsx", "filename2": "A34_CMDB_nettwork_equipment.xlsx"}
		URL = "https://soprasteria.service-now.com/"
		FREKVENS = "Hver natt"

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


		filename1 = FILNAVN["filename1"]
		filename2 = FILNAVN["filename2"]

		from systemoversikt.views import sharepoint_get_file
		# bigip-data
		source_filepath = f"{filename1}"
		result = sharepoint_get_file(source_filepath)
		destination_file_bigip = result["destination_file"]
		destination_file_bigip_modified_date = result["modified_date"]
		print(f"Filen er datert {destination_file_bigip_modified_date}")

		# router-data
		source_filepath = f"{filename2}"
		result = sharepoint_get_file(source_filepath)
		destination_file_cisco = result["destination_file"]
		destination_file_cisco_modified_date = result["modified_date"]
		print(f"Filen er datert {destination_file_cisco_modified_date}")


		@transaction.atomic
		def import_network():

			num_cisco = 0
			num_cisco_new = 0
			num_bigip = 0
			num_bigip_new = 0

			### BigIP

			# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
			import warnings
			warnings.simplefilter("ignore")

			dfRaw = pd.read_excel(destination_file_bigip)
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			data = dfRaw.to_dict('records')

			num_bigip = len(data)
			for line in data:
				try:
					inst = CMDBdevice.objects.get(comp_name=line["Name"])
				except:
					inst = CMDBdevice.objects.create(comp_name=line["Name"], comp_ip_address=line["IP Address"])
					num_bigip_new += 1

				#print(inst.name)
				inst.device_type = "NETWORK"
				inst.comp_ip_address = line["IP Address"]
				inst.comp_os = line["Model ID"]
				inst.comp_os_version = ""
				inst.comp_os_readable = f"{line['Model ID']}"
				inst.eksternt_eksponert_dato = timezone.now()
				inst.save()

				# Linke IP-adresse
				ipaddr_ins = get_ipaddr_instance(inst.comp_ip_address)
				if ipaddr_ins != None:
					if not inst in ipaddr_ins.servere.all():
						ipaddr_ins.servere.add(inst)
						ipaddr_ins.save()


			### Cisco
			dfRaw = pd.read_excel(destination_file_cisco)
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			data = dfRaw.to_dict('records')

			num_cisco = len(data)
			for line in data:
				try:
					inst = CMDBdevice.objects.get(comp_name=line["Name"])
				except:
					inst = CMDBdevice.objects.create(comp_name=line["Name"], comp_ip_address=line["IP Address"])
					num_cisco_new += 1

				#print(inst.name)
				inst.device_type = "NETWORK"
				inst.comp_ip_address = line["IP Address"]
				model = "%s %s %s" % (line["Manufacturer"], line["Class"], line["Name.1"])
				inst.comp_os = model
				inst.comp_os_version = line["Firmware version"]
				inst.comp_os_readable = f"{model} {inst.comp_os_version}"
				inst.eksternt_eksponert_dato = timezone.now()
				inst.save()

				# Linke IP-adresse
				ipaddr_ins = get_ipaddr_instance(inst.comp_ip_address)
				if ipaddr_ins != None:
					if not inst in ipaddr_ins.servere.all():
						ipaddr_ins.servere.add(inst)
						ipaddr_ins.save()


			#opprydding alle nettverksenheter som ikke er sett ved oppdatering
			for_gammelt = timezone.now() - timedelta(hours=12) # 12 timer gammelt, scriptet bruker bare noen minutter..
			ikke_oppdatert = CMDBdevice.objects.filter(device_type="NETWORK").filter(sist_oppdatert__lte=for_gammelt)
			tekst_ikke_oppdatert = ",".join(ikke_oppdatert)
			antall_ikke_oppdatert = ikke_oppdatert.count()
			ikke_oppdatert.delete()


			logg_entry_message = f'Importerte {num_cisco} cisco-enheter hvor {num_cisco_new} var nye. Importerte {num_bigip} bigip-enheter hvor {num_bigip_new} var nye. Slettet {antall_ikke_oppdatert} enheter: {tekst_ikke_oppdatert}'
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_entry_message,
				)
			print(logg_entry_message)
			return logg_entry_message


		#eksekver
		logg_entry_message = import_network()

		# lagre sist oppdatert tidspunkt
		int_config.dato_sist_oppdatert = destination_file_bigip_modified_date # eller timezone.now()
		int_config.sist_status = logg_entry_message
		int_config.save()



