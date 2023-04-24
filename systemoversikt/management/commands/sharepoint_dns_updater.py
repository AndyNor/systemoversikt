from django.core.management.base import BaseCommand
from py_topping.data_connection.sharepoint import da_tran_SP365
from systemoversikt.models import *
from django.db import transaction
import os
import json, os
import pandas as pd
import numpy as np
from django.db.models import Q
import ipaddress
from systemoversikt.views import get_ipaddr_instance

class Command(BaseCommand):
	def handle(self, **options):

		sp_site = os.environ['SHAREPOINT_SITE']
		client_id = os.environ['SHAREPOINT_CLIENT_ID']
		client_secret = os.environ['SHAREPOINT_CLIENT_SECRET']
		sp = da_tran_SP365(site_url = sp_site, client_id = client_id, client_secret = client_secret)


		filename1 = "oslofelles_dns_ekstern"
		filename2 = "oslofelles_dns_intern"

		source_filepath1 = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename1
		source_filepath2 = "https://oslokommune.sharepoint.com/:x:/r/sites/74722/Begrensede-dokumenter/"+filename2


		source_file1 = sp.create_link(source_filepath1)
		source_file2 = sp.create_link(source_filepath2)


		destination_file1 = 'systemoversikt/import/'+filename1
		destination_file2 = 'systemoversikt/import/'+filename2

		sp.download(sharepoint_location = source_file1, local_location = destination_file1)
		sp.download(sharepoint_location = source_file2, local_location = destination_file2)


		@transaction.atomic
		def import_dns(source_file, filename_str, domain):

			dns_dropped = 0
			count_new = 0
			antall_a_records = 0
			antall_cname_records = 0
			cname_records_failed = 0
			ip_linker = 0


			def create_or_update(dns_name, dns_type, dns_target, ip_address, ttl, domain, txt, source):
				try:
					dns_inst = DNSrecord.objects.get(dns_name=dns_name, dns_type=dns_type)
					dns_inst.dns_target = dns_target
					dns_inst.ip_address = ip_address
					dns_inst.ttl = ttl
					dns_inst.dns_domain = domain
					dns_inst.txt = txt
					dns_inst.source = source

					dns_inst.save()
					print("u", end="", flush=True)


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
					print("n", end="", flush=True)


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

			logg_entry_message = 'Fant %s A-records og %s alias i %s. %s alias kunne ikke slås opp. %s nye A-records/CNAMES. %s IP-referanser skrevet. %s slettet.' % (
					antall_a_records,
					antall_cname_records,
					filename_str,
					cname_records_failed,
					count_new,
					ip_linker,
					antall_slettet,
				)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB DNS import',
					message=logg_entry_message,
				)
			print("\n")
			print(logg_entry_message)

		#eksekver
		import_dns(destination_file1, filename1, u"oslo.kommune.no")
		import_dns(destination_file2, filename2, u"oslo.kommune.no")
