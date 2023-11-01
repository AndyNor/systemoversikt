# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from systemoversikt.views import push_pushover
from systemoversikt.models import *
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
import pandas as pd
import numpy as np
import os


class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_ardoc_import"
		LOG_EVENT_TYPE = "CMDB ardoq import"
		KILDE = "Ardoq"
		PROTOKOLL = "Sharepoint"
		BESKRIVELSE = "Oppdaterte data fra ardoc"
		FILNAVN = "eksport_ardoq.xlsx"
		URL = ""
		FREKVENS = "Ved behov"


		reset_data = [
		(1847,4),
		(1520,5),
		(1826,2),
		(1669,3),
		(609,6),
		(686,4),
		(1115,8),
		(968,3),
		(1683,3),
		(1822,5),
		(701,7),
		(1622,4),
		(1442,4),
		(648,8),
		(447,8),
		(635,4),
		(807,8),
		(1663,4),
		(1789,2),
		(456,4),
		(1819,5),
		(659,4),
		(1886,3),
		(1662,4),
		(1790,3),
		(727,4),
		(1306,8),
		(1073,5),
		(646,4),
		(1816,5),
		(534,4),
		(1764,1),
		(679,6),
		(1399,3),
		(432,4),
		(1667,1),
		(1814,None),
		(1659,4),
		(535,4),
		(1424,4),
		(1111,3),
		(1804,3),
		(1519,4),
		(469,8),
		(583,4),
		(1657,4),
		(1259,2),
		(1055,5),
		(706,4),
		(1516,4),
		(1243,4),
		(1063,4),
		(561,4),
		(521,5),
		(379,4),
		(349,2),
		(423,7),
		(501,3),
		(1557,1),
		(1058,4),
		(1742,3),
		(1823,None),
		(1820,None),
		(347,5),
		(533,4),
		(366,2),
		(487,3),
		(1525,4),
		(749,4),
		(1812,None),
		(536,3),
		(919,5),
		(958,5),
		(1124,2),
		(1123,4),
		(1563,4),
		(1068,4),
		(1564,3),
		(1054,7),
		(1364,4),
		(1756,4),
		(926,4),
		(467,4),
		(1803,None),
		(459,4),
		(681,4),
		(835,4),
		(604,4),
		(573,4),
		(500,4),
		(1425,4),
		(1479,3),
		(1605,8),
		(1105,3),
		(1388,5),
		(1598,4),
		(1763,1),
		(499,5),
		(1101,5),
		(707,5),
		(1360,4),
		(386,5),
		(1676,4),
		(728,4),
		(1422,3),
		(576,5),
		(957,2),
		(1815,3),
		(890,4),
		(734,2),
		(1677,3),
		(1325,4),
		(1821,3),
		(645,4),
		(1673,2),
		(1427,3),
		(876,5),
		(913,4),
		(1658,2),
		(1518,5),
		(517,5),
		(449,4),
		(1583,3),
		(511,5),
		(1475,3),
		(1671,5),
		(955,4),
		(577,7),
		(760,3),
		(1833,1),
		(378,3),
		(340,3),
		(1098,3),
		(699,5),
		(1851,3),
		(773,3),
		(1402,4),
		(1419,4),
		(1828,2),
		(537,3),
		(1733,3),
		(1344,3),
		(1380,5),
		(611,4),
		(1884,None),
		(1824,None),
		(1809,5),
		(1825,5),
		(1471,4),
		(1394,5),
		(1670,3),
		(498,4),
		(642,5),
		(553,5),
		(693,3),
		(1747,4),
		(436,5),
		(438,3),
		(1672,2),
		(497,7),
		(1103,4),
		(1127,5),
		(1418,3),
		(768,4),
		(1813,1),
		(1817,4),
		(1349,4),
		(1441,3),
		(1255,5),
		]

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

		print(f"------ Starter {SCRIPT_NAVN} ------")

		try:

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

			source_filepath = f"{FILNAVN}"
			from systemoversikt.views import sharepoint_get_file
			result = sharepoint_get_file(source_filepath)
			destination_file = result["destination_file"]
			modified_date = result["modified_date"]
			print(f"Filen er datert {modified_date}")

			print(f"Åpner filen..")
			# https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls/66749978#66749978
			import warnings
			warnings.simplefilter("ignore")

			dfRaw = pd.read_excel(destination_file)
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			data = dfRaw.to_dict('records')

			antall_records = len(data)

			#for item in reset_data:
			#	s = System.objects.get(pk=item[0])
			#	ny_verdi = item[1]
			#	print(f"endrer {s}: fra {s.livslop_status} tilbake til {ny_verdi}")
			#	s.livslop_status = ny_verdi
			#	s.save()

			for record in data:
				try:
					ardoc_system_id = int(record["Kartoteket SYS ID"])
				except:
					ardoc_system_id = None
				ardoc_systemnavn = record["Name"]
				ardoc_systembeskrivelse = record["Description"]
				try:
					ardoc_livsløpsstatus = record["INV Livsløpstatus"][0]
				except:
					ardoc_livsløpsstatus = None

				try:
					system_ref = System.objects.get(pk=ardoc_system_id)
					#print(f"{system_ref.pk} {system_ref.livslop_status}")
				except:
					#print(f"Fant ikke system med id {ardoc_system_id}: {ardoc_systemnavn}")
					continue

				#if system_ref.systemnavn != ardoc_systemnavn:
				#	print(f"Systemnavn er endret fra '{system_ref.systemnavn}' til '{ardoc_systemnavn}'.")

				#if system_ref.systembeskrivelse != ardoc_systembeskrivelse:
				#	print(f"Systembeskrivelse for '{system_ref.systemnavn}' er endret fra '{system_ref.systembeskrivelse}' til '{ardoc_systembeskrivelse}'.")
				if ardoc_livsløpsstatus != None:
					if system_ref.livslop_status != int(ardoc_livsløpsstatus):
						print(f"Livsløpstatus for '{system_ref.systemnavn}' blir endret fra '{system_ref.livslop_status}' til '{ardoc_livsløpsstatus}'.")
						system_ref.livslop_status = int(ardoc_livsløpsstatus)
						system_ref.save()
						#pass


			logg_entry_message = f"Det var {antall_records} systemer i filen"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_entry_message,
				)

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = modified_date # her setter vi filens dato, ikke dato for kjøring av script
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



