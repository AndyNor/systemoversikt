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


		filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/group_permissions.json"
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
		logg_entry.save()
		messages.success(request, logg_entry_message)

		return render(request, 'home.html', {
			'request': request,
		})
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
			logg_entry.save()
			messages.success(request, logg_entry_message)

		return render(request, 'home.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


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

			all_existing_db = list(CMDBdatabase.objects.filter(db_operational_status=True))

			for record in data["records"]:
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

				cmdb_db.db_database = record["db_database"]
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
				event_type='CMDB server import',
				message=logg_entry_message,
			)
		logg_entry.save()
		messages.success(request, logg_entry_message)

		return render(request, 'home.html', {
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
		logg_entry.save()
		messages.success(request, logg_entry_message)

		return render(request, 'home.html', {
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
				result_text += (item["beskrivelse"] + " (" + item["vlan"] + ")" + " (" + item["sikkerhetsnivaa"] + ")")
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


"""
def add_dns_vlan_vip(request):
	required_permissions = 'systemoversikt.change_cmdbref'
	if request.user.has_perm(required_permissions):



		messages.success(request, "Alt ok")
		return render(request, 'home.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })
"""

"""
def fixcmdb(request):

	alle_cmdbref = CMDBRef.objects.all()
	for ref in alle_cmdbref:
		if " prod" in ref.navn.lower():
			ref.environment = 1  # set tl produksjon
		if "test" in ref.navn.lower():
			ref.environment = 2  # set til test
		#if ref.system_cmdbref.count() > 0:
		#	ref.cmdb_type = 1  # set til system
		#	print(ref.system_cmdbref.all())

		ref.save()

	return render(request, 'home.html', {
		'request': request,
	})
"""


"""
def import_iktkontakt(request):
	import csv, os
	filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/hovedkontakter.csv"
	with open(filepath, 'r', encoding='iso-8859-1') as csvfile:
		data = list(csv.DictReader(csvfile, delimiter=","))
		for line in data:
			try:
				virksomhet = Virksomhet.objects.get(virksomhetsforkortelse=line["tbf"])
			except:
				error = "kunne ikke finne %s" % (line["tbf"])
				messages.warning(request, error)
				continue
			try:
				ansvarlig = Ansvarlig.objects.get(navn=line["navn"])
			except:
				ansvarlig = Ansvarlig.objects.create(navn=line["navn"])
			virksomhet.ikt_kontakt.add(ansvarlig)
			# trenger ikke kalle save()

	return render(request, 'home.html', {
		'request': request,
	})
"""



"""
@user_passes_test(lambda u: u.is_superuser)
def sett_created_til_sist_oppdatert(request):
	antall_endringer = 0
	modeller = [Ansvarlig, Avtale, BehandlingerPersonopplysninger, CMDBRef, DPIA, Leverandor, Programvare, System, SystemUrl, Tjeneste, Virksomhet]
	for m in modeller:
		for o in m.objects.all():
			print("%s og %s" % (o.opprettet, o.sist_oppdatert))
			o.opprettet = o.sist_oppdatert
			o.save()
			antall_endringer += 1

	messages.success(request, 'Har oppdatert %s datofelt' % (antall_endringer))
	return render(request, 'home.html', {
		'request': request,
	})
"""




"""
@permission_required('systemoversikt.change_system', raise_exception=True)
def import_cmdb(request):
	import csv
	import os
	filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/cmdb.csv"
	with open(filepath, 'r', encoding='iso-8859-1') as csvfile:
		data = list(csv.DictReader(csvfile, delimiter=";"))
		for line in data:
			print(line["CMDBREF"] + " " + line["CRITICALITY"] + " " + line["TYPE"])
			try:
				CMDBRef.objects.create(
						navn=line['CMDBREF'],
						kritikalitet=line['CRITICALITY'],
						cmdb_type=line['TYPE'],
					)
			except:
				continue

	return render(request, 'home.html', {
		'request': request,
	})

@login_required
@never_cache
def import_vir(request):
	import csv
	import os
	errors = []
	ok = 0
	fail = 0


	filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/vir.tsv"
	with open(filepath, 'r') as csvfile:
		data = list(csv.DictReader(csvfile, delimiter="\t"))

		for line in data:
			try:
				vir = Virksomhet(
					virksomhetsforkortelse=line["Tbf"],
					virksomhetsnavn=line["Virksomheter"],
					resultatenhet=line["Resultatenhet"],
					kontaktpersoner_kko=line["KontaktpersonerKko"],
					ansatte=line["Ansatte"]
					)
				vir.save()
				ok += 1
			except Exception as e:
				errors.append(e)
				fail += 1

	return render(request, 'import.html', {
		'request': request,
		'result': {"ok":ok, "fail":fail, "errors":errors},
	})

@login_required
@never_cache
def import_sys(request):
	import csv
	import os
	ok = 0
	fail = 0
	errors = []

	filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/sys_gammel.tsv"
	with open(filepath, 'r') as csvfile:
		data = list(csv.DictReader(csvfile, delimiter="\t"))
		for line in data:

			try:
				systemeier = Virksomhet.objects.get(virksomhetsnavn=line["systemeier"])
			except ObjectDoesNotExist:
				systemeier = None
				errors.append("Fant ikke virksomhet " + line["systemeier"])

			try:
				systemkategori = SystemKategori.objects.get(kategorinavn=line["systemkategorier"])
			except ObjectDoesNotExist:
				systemkategori = SystemKategori(kategorinavn=line["systemkategorier"],definisjon=None)
				systemkategori.save()

			sys = System(
				systemnavn=line["systemnavn"],
				tjenestenivaa=line["tjenestenivaa"].upper(), # must be UPPERCASE
				systemeierskapsmodell=line["systemeierskapsmodell"],
				systemeier=systemeier
				)

			try:
				sys.save()
				sys.systemkategorier.add(systemkategori)
				sys.save()
				ok += 1
			except Exception as e:
				fail += 1
				errors.append(e)


	return render(request, 'import.html', {
		'request': request,
		'result': {"ok":ok, "fail":fail, "errors":errors},
	})

@login_required
@never_cache
def import_sys_new(request):
	import csv
	import os
	ok = 0
	fail = 0
	pass2 = 0
	errors = []

	filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/programvarer.tsv"
	with open(filepath, 'r') as csvfile:
		data = list(csv.DictReader(csvfile, delimiter="\t"))
		for line in data:

			def intOrNone(string):
				if string is "":
					return None
				else:
					return int(string)

			try:
				sys = System.objects.get(systemnavn=line["systemnavn"])

				sys.systembeskrivelse = line["systembeskrivelse"]
				sys.systemeierskapsmodell = line["systemeierskapsmodell"]
				sys.programvarekategori = intOrNone(line["programvarekategori"])
				sys.livslop_status = intOrNone(line["livslop_status"])
				sys.strategisk_egnethet = intOrNone(line["strategisk_egnethet"])
				sys.funksjonell_egnethet = intOrNone(line["funksjonell_egnethet"])
				sys.teknisk_egnethet = intOrNone(line["teknisk_egnethet"])
				sys.konfidensialitetsvurdering = intOrNone(line["konfidensialitetsvurdering"])
				sys.integritetsvurdering = intOrNone(line["integritetsvurdering"])
				sys.tilgjengelighetsvurdering = intOrNone(line["tilgjengelighetsvurdering"])
				sys.selvbetjening = intOrNone(line["selvbetjening"])

				# systemkategorier1 og systemkategorier2
				for syskat in ("systemkategorier1", "systemkategorier2"):
					if line[syskat] is not "":
						try:
							systemkategori = SystemKategori.objects.get(kategorinavn=line[syskat])
							sys.systemkategorier.add(systemkategori)
						except ObjectDoesNotExist:
							systemkategori = SystemKategori(kategorinavn=line[syskat])
							systemkategori.save()
							sys.systemkategorier.add(systemkategori)

				# systemleverandor1 og systemleverandor2
				for syslev in ("systemleverandor1", "systemleverandor2"):
					if line[syslev] is not "":
						try:
							systemleverandor = Leverandor.objects.get(leverandor_navn=line[syslev])
							sys.systemleverandor.add(systemleverandor)
						except ObjectDoesNotExist:
							systemleverandor = Leverandor(leverandor_navn=line[syslev])
							systemleverandor.save()
							sys.systemleverandor.add(systemleverandor)
				pass2 += 1

			except ObjectDoesNotExist:
				sys = System(
					systemnavn=line["systemnavn"],
					systembeskrivelse=line["systembeskrivelse"],
					systemeierskapsmodell=line["systemeierskapsmodell"],
					programvarekategori=intOrNone(line["programvarekategori"]),
					livslop_status=intOrNone(line["livslop_status"]),
					strategisk_egnethet=intOrNone(line["strategisk_egnethet"]),
					funksjonell_egnethet=intOrNone(line["funksjonell_egnethet"]),
					teknisk_egnethet=intOrNone(line["teknisk_egnethet"]),
					konfidensialitetsvurdering=intOrNone(line["konfidensialitetsvurdering"]),
					integritetsvurdering=intOrNone(line["integritetsvurdering"]),
					tilgjengelighetsvurdering=intOrNone(line["tilgjengelighetsvurdering"]),
					selvbetjening=intOrNone(line["selvbetjening"])
					)

			try:
				sys.save()
				ok += 1
			except Exception as e:
				fail += 1
				errors.append(e)


	return render(request, 'import.html', {
		'request': request,
		'result': {"ok":ok, "fail":fail, "errors":errors, "pass2": pass2},
	})



@login_required
@never_cache
def import_bruk(request):
	import csv
	import os
	ok = 0
	fail = 0
	pass2 = 0
	errors = []

	def intOrNone(string):
		if string is "":
			return None
		else:
			return int(string)

	filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/programmerprvirksomhet.tsv"
	with open(filepath, 'r') as csvfile:
		data = list(csv.DictReader(csvfile, delimiter="\t"))
		for line in data:

			# Does it already exist?
			try:
				system = System.objects.get(systemnavn=line["systemnavn"])
				virksomhet = Virksomhet.objects.get(virksomhetsnavn=line["brukergruppe"])
				bruk = SystemBruk.objects.filter(system=system, brukergruppe=virksomhet).get()

				# what we have here is "systemkategorier" and "systemleverandor" also at the "use-of-system"-level.
				# We could have imported these directly into the corresponding system-instance, but the
				# data quality is too low. It can be aggregated manually...
				for syskat in ("systemkategorier1", "systemkategorier2"):
					if line[syskat] is not "":
						try:
							systemkategori = SystemKategori.objects.get(kategorinavn=line[syskat])
							bruk.systemkategorier.add(systemkategori)
						except ObjectDoesNotExist:
							systemkategori = SystemKategori(kategorinavn=line[syskat])
							systemkategori.save()
							bruk.systemkategorier.add(systemkategori)
				for syslev in ("systemleverandor1", "systemleverandor2"):
					if line[syslev] is not "":
						try:
							systemleverandor = Leverandor.objects.get(leverandor_navn=line[syslev])
							bruk.systemleverandor.add(systemleverandor)
						except ObjectDoesNotExist:
							systemleverandor = Leverandor(leverandor_navn=line[syslev])
							systemleverandor.save()
							bruk.systemleverandor.add(systemleverandor)
				pass2 += 1
			except:
				# Make a new object when it could not be found
				try:
					system = System.objects.get(systemnavn=line["systemnavn"])
				except:
					system = None
				try:
					brukergruppe = Virksomhet.objects.get(virksomhetsnavn=line["brukergruppe"])
				except:
					brukergruppe = None

				kommentar = "\n".join([line["kommentar1"],line["kommentar2"],line["kommentar3"],line["kommentar4"],line["kommentar5"]])
				systemeierskap = "\n".join([line["systemeierskap1"],line["systemeierskap2"]])
				bruk = SystemBruk(
					system=system,
					brukergruppe=brukergruppe,
					antall_brukere=intOrNone(line["antall_brukere"]),
					avtalestatus=intOrNone(line["avtalestatus"]),
					borger=intOrNone(line["borger"]),
					funksjonell_egnethet=intOrNone(line["funksjonell_egnethet"]),
					ibruk=intOrNone(line["ibruk"]),
					integritetsvurdering=intOrNone(line["integritetsvurdering"]),
					kommentar=kommentar,
					konfidensialitetsvurdering=intOrNone(line["konfidensialitetsvurdering"]),
					livslop_status=intOrNone(line["livslop_status"]),
					systemeierskap=systemeierskap,
					strategisk_egnethet=intOrNone(line["strategisk_egnethet"]),
					teknisk_egnethet=intOrNone(line["teknisk_egnethet"]),
					tilgjengelighetsvurdering=intOrNone(line["tilgjengelighetsvurdering"]),
					avtaletype=line["avtaletype"],
					programvarekategori=intOrNone(line["programvarekategori"]),
					systemeierskapsmodell=line["systemeierskapsmodell"].upper(),
					kostnadersystem=intOrNone(line["kostnadersystem"]),
					driftsmodell=intOrNone(line["driftsmodell"]),
					)
			try:
				bruk.save()
				ok += 1
			except Exception as e:
				#print("***" + line["brukergruppe"] + " - " + line["systemnavn"] + " | " + line["ibruk"])  # debugging
				errors.append(e)
				fail += 1

	return render(request, 'import.html', {
		'request': request,
		'result': {"ok":ok, "fail":fail, "errors":errors, "pass2": pass2},
	})
"""

"""
@permission_required('systemoversikt.view_behandlingerpersonopplysninger', raise_exception=True)
def match_ansvarlig_brukerobjekt(request):

	data = [
		["Abraham Gerezgiher", "VAV1231"],
	]

	# alle på listen, bytt ihht dette

	for item in data:
		navn = item[0]
		brukernavn = item[1].lower()

		try:
			ansvarlig = Ansvarlig.objects.get(navn=navn)
		except:
			messages.warning(request, 'Fant ikke ansvarlig %s' % navn)
		try:
			bruker = User.objects.get(username=brukernavn)
		except:
			messages.warning(request, 'Fant ikke bruker %s' % brukernavn)
		try:
			ansvarlig.brukernavn = bruker
			ansvarlig.save()
			messages.success(request, 'Koblet %s' % navn)
		except:
			messages.warning(request, 'Klarte ikke sette bruker på ansvarlig %s' % navn)

	users = User.objects.all()
	for ansvarlig in Ansvarlig.objects.all():
		ansvarlig_full_name = ansvarlig.navn
		for user in users:
			user_full_name = ("%s %s" % (user.first_name, user.last_name))
			if user_full_name == ansvarlig_full_name:
				ansvarlig.brukernavn = user
				try:
					ansvarlig.save()
				except:
					messages.warning(request, 'Kunne ikke lagre %s' % ansvarlig_full_name)


	return render(request, 'home.html', {
		'request': request,
	})
"""



"""
@permission_required('auth.change_group', raise_exception=True)
def slettBrukIkkeIBruk(request):
	#alle_systembruk = SystemBruk.objects.filter(ibruk=2).values('ibruk', 'system', 'brukergruppe')
	#return JsonResponse({'ansvarlige': list(alle_systembruk)})
	alle_systembruk_ikkeibruk = SystemBruk.objects.filter(ibruk=2) # 2 = "nei"
	for item in alle_systembruk_ikkeibruk:
		print(item)
		item.delete()

	alle_programvarebruk_ikkeibruk = ProgramvareBruk.objects.filter(ibruk=2) # 2 = "nei"
	for item in alle_programvarebruk_ikkeibruk:
		print(item)
		item.delete()
	return JsonResponse({'result': "OK"})
"""


"""
@permission_required('auth.change_group', raise_exception=True)
def import_ansvarlige_brukere(request):

	brukerobjekter = [
		{'cn': 'BSR17658', 'sn': 'Wijeyaraj', 'givenName': 'Abraham Lincoln', 'userAccountControl': [], 'mail': 'abraham.wijeyaraj@bsr.oslo.kommune.no'},
	]

	from django.contrib.auth.models import User
	for item in brukerobjekter:
		username = item["cn"].lower()
		print(username)
		try:
			new_user = User.objects.get(username=username)
		except:
			new_user = User.objects.create_user(username=username, is_staff=True)

		new_user.first_name = item.get("givenName", "")
		new_user.last_name = item.get("sn", "")
		new_user.email = item.get("mail", "")

		try:
			virksomhet_tbf = username[0:3].upper()
			virksomhet_obj_ref = Virksomhet.objects.get(virksomhetsforkortelse=virksomhet_tbf)
			new_user.profile.virksomhet = virksomhet_obj_ref
		except:
			continue

		if "ACCOUNTDISABLE" in item["userAccountControl"]:
			print("ACCOUNTDISABLE")
			new_user.profile.accountdisable = True
		if "LOCKOUT" in item["userAccountControl"]:
			new_user.profile.lockout = True
		if "PASSWD_NOTREQD" in item["userAccountControl"]:
			new_user.profile.passwd_notreqd = True
		if "DONT_EXPIRE_PASSWORD" in item["userAccountControl"]:
			new_user.profile.dont_expire_password = True
		if "PASSWORD_EXPIRED" in item["userAccountControl"]:
			new_user.profile.password_expired = True
		new_user.save()


	return render(request, 'home.html', {
		'request': request,
		'oidctoken': request.session.get('oidc-token', ''),
	})
"""