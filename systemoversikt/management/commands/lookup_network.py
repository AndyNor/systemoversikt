# -*- coding: utf-8 -*-

"""
Hensikten med denne koden er å gjennomgå alle servere med IP, slå opp VLAN, DNS-info, medlemskap i BigIP pools.
"""


from django.core.management.base import BaseCommand
from django.conf import settings
import os
import time
import sys
import json
import re
import socket
from systemoversikt.models import CMDBdevice, ApplicationLog
from systemoversikt.views_import import load_dns_sonefile, load_vlan, load_nat, load_bigip
from systemoversikt.views_import import find_ip_in_dns, find_vlan, find_ip_in_nat, find_bigip
from django.db.models import Q
import requests
import logging

class Command(BaseCommand):
	def handle(self, **options):

		LOG_EVENT_TYPE = 'Nettverksoppslag'
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

		log = logging.getLogger(__name__)
		log.info("Starter oppslag av IP-adresser")

		runtime_t0 = time.time()
		socket.setdefaulttimeout(0.2)

		# TODO bør legge dette i en konfigurasjonsfil, da dette nå ligger to/flere steder.
		domain = "oslo.kommune.no"
		dns_ekstern = load_dns_sonefile(os.getcwd() + "/systemoversikt/import/oslofelles_dns_ekstern", domain)
		dns_intern = load_dns_sonefile(os.getcwd() + "/systemoversikt/import/oslofelles_dns_intern", domain)
		vlan_data = load_vlan(os.getcwd() + "/systemoversikt/import/oslofelles_vlan.tsv")
		nat_data = load_nat(os.getcwd() + "/systemoversikt/import/oslofelles_nat.tsv")
		bigip_data = load_bigip(os.getcwd() + "/systemoversikt/import/oslofelles_vip.tsv")

		stat_oppdatert = 0
		stat_manglet_ip_resolved = 0
		stat_manglet_ip_resolve_fail = 0

		cmdbdevices = CMDBdevice.objects.all()
		device_count = len(cmdbdevices)
		for idx, device in enumerate(cmdbdevices):
			print("%s av %s" % (idx, device_count))
			if re.match(r'ws[0-9].*', device.comp_name, re.I):
				#print("Er klient %s" % (device))
				continue # ikke noe poeng å slå opp IP på klienter. De bytter IP stadig vekk.

			if device.comp_ip_address == "" or device.comp_ip_address == None:
				#print("Do lookup %s" % (device))
				try:
					resolved_ip = socket.gethostbyname(device.comp_name)
					device.comp_ip_address = resolved_ip
					device.save()
					stat_manglet_ip_resolved += 1
				except:
					stat_manglet_ip_resolve_fail += 1
					print("Feilet IP-oppslag: %s" % (device))
					continue  # nytter ikke å fortsette uten IP-adresse

			#ip-address must be set at this stage

			dns = ""
			dns += ("%s, " % find_ip_in_dns(device.comp_ip_address, dns_intern))
			dns += find_ip_in_dns(device.comp_ip_address, dns_ekstern)
			vlan = find_vlan(device.comp_ip_address, vlan_data)
			nat = find_ip_in_nat(device.comp_ip_address, nat_data)
			vip = find_bigip(device.comp_ip_address, bigip_data)

			save = False
			if device.dns != dns:
				device.dns = dns
				save = True
			if device.vlan != vlan:
				device.vlan = vlan
				save = True
			if device.nat != nat:
				device.nat = nat
				save = True
			if device.vip != vip:
				device.vip = vip
				save = True

			if save:
				device.save()
				#print("Lagrer endring: %s" % (device))
				stat_oppdatert += 1



		message = "Oppslag av IP-adresser: %s oppdatert, %s IP-adresser slått opp, %s feilede IP-oppslag." % (
				stat_oppdatert,
				stat_manglet_ip_resolved,
				stat_manglet_ip_resolve_fail,
				)

		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0

		logg_entry_message = "Kjøretid: %s: %s" % (
				round(logg_total_runtime, 1),
				message

		)
		logg_entry = ApplicationLog.objects.create(
				event_type=LOG_EVENT_TYPE,
				message=logg_entry_message,
		)

		print(logg_entry_message)