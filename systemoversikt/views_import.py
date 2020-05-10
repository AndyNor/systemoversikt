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



def import_group_permissions(request):
	import json, os
	from django.contrib.auth.models import Group, Permission
	required_permissions = 'auth.change_group'
	if request.user.has_perm(required_permissions):

		if request.POST:
			filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/group_permissions.json"
			try:
				with open(filepath, 'r', encoding='UTF-8') as json_file:
					data = json.load(json_file)
					for group in data:
						#print(group["group"])
						group_name = group["group"]
						try:
							g = Group.objects.get(name=group_name)
						except:
							messages.warning(request, 'Gruppen %s finnes ikke' % group_name)
							continue
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
				})
			except:
				messages.warning(request, 'Filen %s finnes ikke' % (filepath))
				return render(request, 'admin_import.html', {'request': request,})

		else:
			return render(request, 'admin_import.html', {'request': request,})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def konverter_environment(str):
	oppslagsmatrise = {
		"": 8,  # ukjent
		"production": 1,
		"staging": 6,
		"test": 2,
		"qa": 7,
		"development": 3,
		"training": 4,
		"demonstration": 2,
		"disaster recovery": 9,
	}
	try:
		return oppslagsmatrise[str.lower()]  # lowercase for å slippe unødige feil
	except:
		messages.success(request, 'Konvertere environment: fant ikke %s' % (str))
		return 8  # Ukjent


def konverter_kritikalitet(str):
	oppslagsmatrise = {
		"": None,  # ukjent
		"4 - not critical": 4,
		"3 - less critical": 3,
		"2 - somewhat critical": 2,
		"1 - most critical": 1,
	}
	try:
		return oppslagsmatrise[str.lower()]  # lowercase for å slippe unødige feil
	except:
		messages.error(request, 'Konvertere kritikalitet: fant ikke %s' % (str))
		return None  # Ukjent


def convertToInt(string):
	try:
		return int(string)
	except:
		return None


def convertToBool(string):
	if string.lower() == "yes":
		return True
	if string.lower() == "no":
		return False
	else:
		return None


def import_business_services(request):

	required_permissions = 'systemoversikt.change_cmdbref'
	if request.user.has_perm(required_permissions):
		business_services_filename = "cmdb_ci_service.json"

		filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/" + business_services_filename
		messages.success(request, 'Lastet inn filen %s' % (filepath))
		with open(filepath, 'r', encoding='UTF-8') as json_file:
			data = json.load(json_file)
			antall_records = len(data["records"])
			messages.success(request, 'Fant %s elementer' % (antall_records))

			# Gå igjennom alle eksisterende business services, dersom ikke i ny fil, merk med "utgått"
			alle_eksisterende_cmdbref = list(CMDBRef.objects.filter(operational_status=1))

			# Importere enheter (andre data i importfil nummer 2)
			antall_nye_bs = 0
			for record in data["records"]:
				try:
					business_service = CMDBRef.objects.get(navn=record["name"])
					if business_service in alle_eksisterende_cmdbref:
						alle_eksisterende_cmdbref.remove(business_service)
				except:
					antall_nye_bs += 1
					business_service = CMDBRef.objects.create(
							navn=record["name"],
					)

				business_service.environment=konverter_environment(record["used_for"])
				business_service.kritikalitet=konverter_kritikalitet(record["busines_criticality"])
				business_service.u_service_portfolio=record["u_service_portfolio"]
				business_service.u_service_availability=record["u_service_availability"]
				business_service.u_service_operation_factor = record["u_service_operation_factor"]
				business_service.u_service_complexity = record["u_service_complexity"]
				business_service.operational_status = convertToInt(record["operational_status"])

				billable = convertToBool(record["u_service_billable"])
				if billable != None:
					business_service.u_service_billable = billable

				business_service.service_classification = record["service_classification"]

				try:
					business_service.comments = record["short_description"]
				except:
					continue

				business_service.save()

			for cmdbref in alle_eksisterende_cmdbref:
				cmdbref.operational_status = 0
				cmdbref.save()

			logg_entry_message = "Nye businessSerices: %s, utdaterte business services: %s. Utført av %s" % (antall_nye_bs, len(alle_eksisterende_cmdbref), request.user)
			logg_entry = ApplicationLog.objects.create(
					event_type='CMDB business service import',
					message=logg_entry_message,
				)
			messages.success(request, logg_entry_message)

		return render(request, 'site_home.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


# TODO to ganske like script for oracle og mssql. datakildene er ikke like..
def import_cmdb_databases_oracle(request):
	required_permissions = 'systemoversikt.change_cmdbref'
	if request.user.has_perm(required_permissions):

		messages.success(request, 'Klargjør import av databaser')
		import json, os
		filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/u_cmdb_bs_bss_db_oracle.json"
		with open(filepath, 'r', encoding='UTF-8') as json_file:
			data = json.load(json_file)

			antall_records = len(data["records"])
			messages.success(request, 'Fant %s elementer' % (antall_records))

			all_existing_db = list(CMDBdatabase.objects.filter(Q(db_version__startswith="Oracle ") & Q(db_operational_status=True)))

			for record in data["records"]:
				# vi sjekker om enheten finnes fra før
				try:
					cmdb_db = CMDBdatabase.objects.get(db_database=record["db_name"])
					# fjerner fra oversikt over alle vi hadde før vi startet
					if cmdb_db in all_existing_db: # i tilfelle reintrodusert
						all_existing_db.remove(cmdb_db)
				except:
					# lager en ny
					cmdb_db = CMDBdatabase.objects.create(db_database=record["db_name"])

				if record["db_operational_status"] == "1":
					cmdb_db.db_operational_status = True
				else:
					cmdb_db.db_operational_status = False

				cmdb_db.db_version = "Oracle " + record["db_version"]

				try:
					filesize = int(record.get("db_u_datafilessizekb", 0)) * 1024 # convert to bytes
				except:
					filesize = 0
				cmdb_db.db_u_datafilessizekb = filesize

				cmdb_db.db_used_for = record["db_used_for"]
				cmdb_db.db_comments = record["db_comments"]

				try:
					business_service = CMDBRef.objects.get(navn=record["sub_name"])
					cmdb_db.sub_name.clear() # reset old lookups
					cmdb_db.sub_name.add(business_service) # add this lookup
				except:
					pass

				cmdb_db.save()

		obsolete_devices = all_existing_db

		for item in obsolete_devices:
			item.db_operational_status = False
			item.save()

		logg_entry_message = 'Antall databaser som er inaktive: %s. Alle slike databaser er satt inaktive. Utført av %s.' % (len(obsolete_devices), request.user)
		logg_entry = ApplicationLog.objects.create(
				event_type='CMDB database import (Oracle)',
				message=logg_entry_message,
			)
		messages.success(request, logg_entry_message)

		return render(request, 'site_home.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


#MSSQL-import
def import_cmdb_databases(request):
	required_permissions = 'systemoversikt.change_cmdbref'
	if request.user.has_perm(required_permissions):

		messages.success(request, 'Klargjør import av databaser')
		import json, os
		filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/u_cmdb_service_to_db_2.json"
		with open(filepath, 'r', encoding='UTF-8') as json_file:
			data = json.load(json_file)

			antall_records = len(data["records"])
			messages.success(request, 'Fant %s elementer' % (antall_records))

			all_existing_db = list(CMDBdatabase.objects.filter(~Q(db_version__startswith="Oracle ") & Q(db_operational_status=True)))

			for record in data["records"]:
				if record["db_database"] == "":
					continue  # Det må være en verdi på denne
				# vi sjekker om enheten finnes fra før
				try:
					cmdb_db = CMDBdatabase.objects.get(db_database=record["db_database"])
					# fjerner fra oversikt over alle vi hadde før vi startet
					if cmdb_db in all_existing_db: # i tilfelle reintrodusert
						all_existing_db.remove(cmdb_db)
				except:
					# lager en ny
					cmdb_db = CMDBdatabase.objects.create(db_database=record["db_database"])

				if record["db_operational_status"] == "1":
					cmdb_db.db_operational_status = True
				else:
					cmdb_db.db_operational_status = False

				cmdb_db.db_version = record["db_version"]

				try:
					filesize = int(record.get("db_u_datafilessizekb", 0)) * 1024 # convert to bytes
				except:
					filesize = 0
				cmdb_db.db_u_datafilessizekb = filesize

				cmdb_db.db_used_for = record["db_used_for"]
				cmdb_db.db_comments = record["db_comments"]

				try:
					hostname = record["db_comments"].split("@")[1]
					print(hostname)
					server = CMDBdevice.objects.get(comp_name=hostname)
					cmdb_db.sub_name.clear() # reset old lookups
					for item in server.sub_name.all():
						cmdb_db.sub_name.add(item) # add this lookup
				except:
					pass

				cmdb_db.save()

		obsolete_devices = all_existing_db

		for item in obsolete_devices:
			item.db_operational_status = False
			item.save()

		logg_entry_message = 'Antall databaser som er inaktive: %s. Alle slike databaser er satt inaktive. Utført av %s.' % (len(obsolete_devices), request.user)
		logg_entry = ApplicationLog.objects.create(
				event_type='CMDB database import',
				message=logg_entry_message,
			)
		messages.success(request, logg_entry_message)

		return render(request, 'site_home.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })





def import_cmdb_servers(request):
	required_permissions = 'systemoversikt.change_cmdbref'
	if request.user.has_perm(required_permissions):

		messages.success(request, 'Klargjør import av CMDB-fil')
		import json, os
		filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/u_cmdb_computer_to_sub_to_bs.json"
		with open(filepath, 'r', encoding='UTF-8') as json_file:
			data = json.load(json_file)

			antall_records = len(data["records"])
			messages.success(request, 'Fant %s elementer' % (antall_records))

			all_existing_devices = list(CMDBdevice.objects.filter(active=True))
			# Importere enheter (andre data i importfil nummer 2)
			def convertToInt(string):
				try:
					return int(string)
				except:
					return None

			for record in data["records"]:
				# vi sjekker om enheten finnes fra før
				try:
					cmdbdevice = CMDBdevice.objects.get(comp_name=record["comp_name"])
					# fjerner fra oversikt over alle vi hadde før vi startet
					if cmdbdevice in all_existing_devices: # i tilfelle reintrodusert
						all_existing_devices.remove(cmdbdevice)
				except:
					# lager en ny
					cmdbdevice = CMDBdevice.objects.create(comp_name=record["comp_name"])

				cmdbdevice.active = True
				cmdbdevice.comp_disk_space = convertToInt(record["comp_disk_space"])
				cmdbdevice.bs_u_service_portfolio = record["bs_u_service_portfolio"]
				cmdbdevice.comp_u_cpu_total = convertToInt(record["comp_u_cpu_total"])
				cmdbdevice.comp_ram = convertToInt(record["comp_ram"])
				cmdbdevice.comp_ip_address = record["comp_ip_address"]
				cmdbdevice.comp_cpu_speed = convertToInt(record["comp_cpu_speed"])
				cmdbdevice.comp_os = record["comp_os"]
				cmdbdevice.comp_os_version = record["comp_os_version"]
				cmdbdevice.comp_os_service_pack = record["comp_os_service_pack"]

				try:
					sub_name = CMDBRef.objects.get(navn=record["sub_name"])
				except:
					messages.error(request, 'Fant ikke eksisterende business service: %s.' % (record["sub_name"]))
					sub_name = CMDBRef.objects.create(
							navn=record["sub_name"],
							operational_status=1,
						)

				cmdbdevice.sub_name.add(sub_name)
				cmdbdevice.save()

		obsolete_devices = all_existing_devices

		for item in obsolete_devices:
			item.active = False
			item.save()

		logg_entry_message = 'Antall servere som er inaktive: %s. Alle slike servere er satt inaktive. Utført av %s.' % (len(obsolete_devices), request.user)
		logg_entry = ApplicationLog.objects.create(
				event_type='CMDB server import',
				message=logg_entry_message,
			)
		messages.success(request, logg_entry_message)

		return render(request, 'site_home.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })



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
					"private_ip_address":line["Privat IP"],
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
