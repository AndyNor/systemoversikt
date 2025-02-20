# -*- coding: utf-8 -*-
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from systemoversikt.views import push_pushover
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from systemoversikt.views import get_ipaddr_instance
from systemoversikt.models import *
import json, os, time
import pandas as pd
import numpy as np
import ipaddress


class Command(BaseCommand):

	ANTALL_IMPORTERT = 0

	def handle(self, **options):

		INTEGRASJON_KODEORD = "sp_dns"
		LOG_EVENT_TYPE = "CMDB DNS import"
		KILDE = "DNS bind-servere"
		PROTOKOLL = "SharePoint"
		BESKRIVELSE = "DNS-navn, alias og TXT-records"
		FILNAVN = {"filename1": "oslofelles_dns_ekstern", "filename2": "oslofelles_dns_intern"}
		URL = ""
		FREKVENS = "Manuelt på forespørsel"

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

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
		runtime_t0 = time.time()

		kilde_ekstern = FILNAVN["filename1"]
		kilde_intern = FILNAVN["filename2"]

		try:

			from systemoversikt.views import sharepoint_get_file
			source_filepath = f"{kilde_ekstern}"
			result = sharepoint_get_file(source_filepath)
			destination_file1 = result["destination_file"]
			destination_file1_modified_date = result["modified_date"]
			print(f"Filen er datert {destination_file1_modified_date}")

			source_filepath = f"{kilde_intern}"
			result = sharepoint_get_file(source_filepath)
			destination_file2 = result["destination_file"]
			destination_file2_modified_date = result["modified_date"]
			print(f"Filen er datert {destination_file2_modified_date}")

			@transaction.atomic
			def import_dns(source_file, filename_str, domain):

				dns_dropped = 0
				count_new = 0
				antall_a_records = 0
				antall_cname_records = 0
				cname_records_failed = 0
				antall_txt = 0
				antall_mx = 0
				ip_linker = 0


				def create_or_update(dns_name, dns_type, dns_target, ip_address, ttl, domain, txt, source):
					try:
						dns_inst = DNSrecord.objects.get(dns_name=dns_name, dns_type=dns_type, source=source)
						dns_inst.dns_target = dns_target
						dns_inst.ip_address = ip_address
						dns_inst.ttl = ttl
						dns_inst.dns_domain = domain
						dns_inst.txt = txt
						dns_inst.source = source

						dns_inst.save()
						#print("u", end="", flush=True)


					except:
						dns_inst = DNSrecord.objects.create(
								dns_name=dns_name,
								dns_type=dns_type,
								dns_target=dns_target,
								ip_address=ip_address,
								ttl=ttl,
								dns_domain=domain,
								txt=txt,
								source=source,
							)
						nonlocal count_new
						count_new += 1
						dns_inst.save()
						#print("n", end="", flush=True)


					# Linke IP-adresse
					ipaddr_ins = get_ipaddr_instance(ip_address)
					if ipaddr_ins != None:
						if not dns_inst in ipaddr_ins.dns.all():
							ipaddr_ins.dns.add(dns_inst)
							ipaddr_ins.save()
							nonlocal ip_linker
							ip_linker += 1


				import dns.zone
				z = dns.zone.from_file(source_file, domain)

				for (name, ttl, rdata) in z.iterate_rdatas('A'):
					antall_a_records += 1

					create_or_update(
							dns_name=name,
							dns_type="A record",
							dns_target=None,
							ip_address=rdata.address,
							ttl=int(ttl),
							domain=domain,
							txt=None,
							source=filename_str,
						)


				for (name, ttl, rdata) in z.iterate_rdatas('CNAME'):
					antall_cname_records += 1

					lookup = z.get_rdataset(rdata.target, 'A')
					if lookup is not None:
						ip_address = lookup.to_text().split()[3]
					else:
						ip_address = None
						cname_records_failed += 1

					create_or_update(
							dns_name=name,
							dns_type="CNAME",
							dns_target=rdata.target,
							ip_address=ip_address,
							ttl=None,
							domain=domain,
							txt=None,
							source=filename_str,
						)

				for (name, ttl, rdata) in z.iterate_rdatas('MX'):
					antall_mx += 1
					antall_cname_records += 1
					dns_target = str(rdata.exchange).strip(".")

					create_or_update(
							dns_name=name,
							dns_type="MX",
							dns_target=dns_target,
							ip_address=None,
							ttl=ttl,
							domain=domain,
							txt=rdata.preference,
							source=filename_str,
						)


				for (name, ttl, rdata) in z.iterate_rdatas('TXT'):
					antall_txt += 1
					create_or_update(
							dns_name=name,
							dns_type="TXT",
							dns_target=None,
							ip_address=None,
							ttl=int(ttl),
							domain=domain,
							txt=rdata,
							source=filename_str,
						)

				# slette alle innslag som ikke ble oppdatert
				from django.utils import timezone
				from datetime import timedelta
				tidligere = timezone.now() - timedelta(hours=1) # 6 timer gammelt
				gamle_dnsinnslag = DNSrecord.objects.filter(sist_oppdatert__lte=tidligere)
				antall_slettet = len(gamle_dnsinnslag)
				for entry in gamle_dnsinnslag:
					entry.delete()

				logg_entry_message = f'{filename_str}: Fant {antall_a_records} A-records, {antall_cname_records} alias, {antall_mx} mx og {antall_txt} txt. {cname_records_failed} alias kunne ikke slås opp. {count_new} nye A-records/CNAMES. {ip_linker} IP-referanser skrevet. {antall_slettet} slettet.'
				Command.ANTALL_IMPORTERT += antall_a_records
				logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_entry_message)
				print(logg_entry_message)
				return logg_entry_message

			#eksekver
			logg_entry_message1 = import_dns(destination_file1, "Ekstern DNS", u"oslo.kommune.no")
			logg_entry_message2 = import_dns(destination_file2, "Intern DNS", u"oslo.kommune.no")

			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = destination_file1_modified_date
			int_config.sist_status = f"{logg_entry_message1}\n{logg_entry_message2}"
			runtime_t1 = time.time()
			logg_total_runtime = int(runtime_t1 - runtime_t0)
			int_config.runtime = logg_total_runtime
			int_config.elementer = int(Command.ANTALL_IMPORTERT)
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

