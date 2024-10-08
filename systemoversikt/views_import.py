# -*- coding: utf-8 -*-
from django.shortcuts import render, redirect
from django.core.exceptions import ObjectDoesNotExist
from django.core import serializers
from systemoversikt.models import *
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.db.models import Count
from django.db.models.functions import Lower
from django.db.models import Q
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponseBadRequest, JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
import datetime
import json, os
from django.db import transaction


def import_group_permissions(request):
	import json, os
	from django.contrib.auth.models import Group, Permission

	required_permissions = ['auth.change_group']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


	if request.POST:
		filepath = os.path.dirname(os.path.abspath(__file__)) + "/auth/group_permissions.json"
		try:
			with open(filepath, 'r', encoding='UTF-8') as json_file:
				data = json.load(json_file)
				Group.objects.all().delete()
				for group in data:
					group_name = group["group"]
					try:
						g = Group.objects.get(name=group_name)
					except:
						g = Group.objects.create(name=group_name)
						messages.warning(request, 'Gruppen %s eksisterte ikke, men er nå opprettet.' % group_name)

					g.permissions.clear()
					for new_perm in group["permissions"]:
						#print(new_perm)
						try:
							p = Permission.objects.get(Q(codename=new_perm["codename"]) & Q(content_type__app_label=new_perm["content_type__app_label"]))
							g.permissions.add(p)
						except:
							messages.warning(request, 'Rettigheten %s finnes ikke' % new_perm["codename"])
							continue

			logg_entry_message = ("Det er utført en import fra fil av %s" % request.user)
			logg_entry = ApplicationLog.objects.create(
					event_type='Grupperettigheter import',
					message=logg_entry_message,
				)
			messages.success(request, logg_entry_message)

			return render(request, 'site_home.html', {
				'request': request,
				'required_permissions': required_permissions,
			})
		except:
			messages.warning(request, 'Filen %s finnes ikke' % (filepath))
			return render(request, 'admin_import.html', {'request': request,})

	else:
		return render(request, 'admin_import.html', {'request': request,})


def import_organisatorisk_forkortelser(request):
	required_permissions = 'systemoversikt.add_definisjon'
	if request.user.has_perm(required_permissions):

		antall_importert = 0

		try:
			definisjonskontekst = DefinisjonKontekster.objects.get(navn="Organisatorisk forkortelse")
		except:
			definisjonskontekst = DefinisjonKontekster.objects.create(navn="Organisatorisk forkortelse")

		alle_virksomheter = Virksomhet.objects.all()
		for v in alle_virksomheter:
			virksomhetsforkortelse = v.virksomhetsforkortelse
			virksomhetsnavn = v.virksomhetsnavn
			try:
				d = Definisjon.objects.get(begrep=v.virksomhetsforkortelse)
				#messages.info(request, "Forkortelsen %s eksisterer fra før av, går til neste" % v.virksomhetsforkortelse)
			except:
				if v.virksomhetsforkortelse:
					d = Definisjon.objects.create(
						status=1,
						begrep=v.virksomhetsforkortelse,
						definisjon=v.virksomhetsnavn)
					d.kontekst_ref = definisjonskontekst
					d.save()
					antall_importert += 1
					messages.success(request, "Importerte begrepet %s" % v.virksomhetsforkortelse)
				else:
					messages.warning(request, "Hopper over %s" % v.virksomhetsnavn)

		messages.success(request, "Alle virksomhetsforkortelser er nå lagt til")
		return HttpResponseRedirect(reverse('alle_definisjoner'))
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })



def load_dns_sonefile(filename, domain):
	import dns.zone
	z = dns.zone.from_file(filename, domain)
	dns_datastructure = []
	for (name, ttl, rdata) in z.iterate_rdatas('A'):
		data = {"name":name,"target":"", "ip_address":rdata.address}
		dns_datastructure.append(data)
	for (name, ttl, rdata) in z.iterate_rdatas('CNAME'):
		lookup = z.get_rdataset(rdata.target, 'A')
		if lookup is None:
			pass
		else:
			lookup = lookup.to_text().split()[3]
		data = {"name":name,"target":rdata.target, "ip_address":lookup}
		dns_datastructure.append(data)
	return dns_datastructure

def find_ip_in_dns(address, dns_data):
	import ipaddress
	result_text = ""
	for item in dns_data:
		if item["ip_address"] is not None:
			if ipaddress.ip_address(address) == ipaddress.ip_address(item["ip_address"]):
				result_text += str(item["name"])
				result_text += ", "
	return(result_text)


def load_vlan(filename):
	import csv
	vlan_data = []
	with open(filename, 'r', encoding='latin-1') as file:
		vlan_datastructure = list(csv.DictReader(file, delimiter="\t"))
		for line in vlan_datastructure:
			t = {
				"address": line["Subnett"],
				"address_v6": line["IPv6"],
				"beskrivelse": line["Beskrivelse"],
				"sikkerhetsnivaa": line["Sikkerhetsnivå"],
				"vlan": line["VLAN"],
				"vlan_name": line["VLAN-navn"],
			}
			vlan_data.append(t)
	return vlan_data

def ip_in_network(query, network):
	import ipaddress
	try:
		# ip_network supports a single network (like 10.0.0.1/32)
		network = ipaddress.ip_network(network)
	except:
		return False
	query_ip = ipaddress.ip_address(query)
	if query_ip in network:
		return True
	else:
		return False

def find_vlan(input_var, vlan_data):
	result_text = ""
	for item in vlan_data:
		network = (item["address"], item["address_v6"])
		for n in network:
			if ip_in_network(input_var, n):
				result_text += (item["beskrivelse"] + "(" + item["address"] + ")" + " (VLAN " + item["vlan"] + ")" + " (" + item["sikkerhetsnivaa"] + ")")
	return result_text


def load_nat(filename):
	import csv
	nat_datastructure = []
	with open(filename, 'r', encoding='latin-1') as file:
		nat_data = list(csv.DictReader(file, delimiter="\t"))
		for line in nat_data:
			t = {
					"public_ip_address": line["Offisiell IP"],
					"private_ip_address": line["Privat IP"],
					"firewall":line["FW"],
					"comment": line["Kommentar"]
			}
			nat_datastructure.append(t)
	return nat_datastructure

def find_ip_in_nat(ip, nat_data):
	for item in nat_data:
		if item["comment"] == "NAT hide for OKMAN mot DAX":
			continue  # they would end up in every 10.x.x.x search

		def pretty_print(item):
			result_text = (""
					+ str(item["public_ip_address"])
					+ " <--> "
					+ str(item["private_ip_address"])
					+ " ("
					+ str(item["firewall"])
					+ ", "
					+ str(item["comment"])
					+ ")"
			)
			return result_text

		if ip_in_network(ip, item["private_ip_address"]):
			return(pretty_print(item))
		if ip_in_network(ip, item["public_ip_address"]):
			return(pretty_print(item))


def load_bigip(filename):
	import csv
	bigip_data = []
	with open(filename, 'r', encoding='latin-1') as file:
		bigip_datastructure = list(csv.DictReader(file, delimiter="\t"))
		for line in bigip_datastructure:
			t = {
				"vip": line["VIP-adresse"],
				"vip_text": line["VIP"],
				"pool": line["Pool"],
				"port": line["Port"],
				"url": line["URL"]
			}
			bigip_data.append(t)
	return bigip_data

def find_bigip(input_var, bigip_data):
	for item in bigip_data:
		network = (item["vip"],item["pool"])
		for n in network:
			if ip_in_network(input_var, n):
				return(item["url"] + " (" + item["vip"] + " --> " + item["pool"] + " " + item["port"] + ")")
	return None
