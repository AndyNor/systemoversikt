# -*- coding: utf-8 -*-
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core import serializers
from systemoversikt.models import *
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Count
from django.template.loader import render_to_string
from django.db.models.functions import Lower
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.urls import reverse
from django.db import transaction
from django.db.models import Sum
import os
import datetime
import json
import re
import time
import struct
from django.utils import timezone



##########################
# Fellesvariabler #
##########################

LEVERANDORTILGANG_KJENTE_GRUPPER = ['DS-UVALEVTILGANG', 'DS-DRIFT_DML_', 'TASK-OF2-LevtilgangWTS', 'DS-KEM_RPA', 'DS-LEV_TREDJEPARTSDRIFT', 'TASK-OF2-DRIFTWTS', 'DS-DRIFT_SC2_']



##########################
# Støttefunksjoner start #
##########################

def auth_er_ansvarlig(user):
	return True if len(Ansvarlig.objects.filter(brukernavn=user)) > 0 else False

def auth_er_systemforvalter(user):
	if auth_er_ansvarlig(user):
		# nå vet vi at vedkommende er registrert som ansvarlig
		ansvarlig = user.ansvarlig_brukernavn
		return True if System.objects.filter(Q(systemeier_kontaktpersoner_referanse=ansvarlig) | Q(systemforvalter_kontaktpersoner_referanse=ansvarlig)) else False
	else:
		return False

def auth_er_virksomhetsrolle(user):
	if auth_er_ansvarlig(user):
		ansvarlig = user.ansvarlig_brukernavn
		return True if Virksomhet.objects.filter(Q(ikt_kontakt=ansvarlig) | Q(personvernkoordinator=ansvarlig) | Q(informasjonssikkerhetskoordinator=ansvarlig)) else False
	else:
		return False

def sharepoint_get_file(filename):
	from azure.identity import ClientSecretCredential
	from msgraph.core import GraphClient
	from django.utils.timezone import make_aware
	import os
	import requests

	print(f'Starter nedlasting av "{filename}"...')

	client_credential = ClientSecretCredential(
			tenant_id=os.environ['AZURE_TENANT_ID'],
			client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
			client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
	)
	site_id = os.environ['SHAREPOINT_SITE_ID']
	library_id = os.environ['SHAREPOINT_LIBRARY_ID']

	client = GraphClient(credential=client_credential, api_version='beta')
	#query = f"/sites/{site_id}/drives/{library_id}/root/children" # liste alle elementer
	query = f"/sites/{site_id}/drives/{library_id}/items/root:/{filename}"
	#print(f"Spørring: {query}")
	resp = client.get(query)
	file_metadata = json.loads(resp.text)

	#print(file_metadata["lastModifiedDateTime"])
	modified_date = make_aware(datetime.datetime.strptime(file_metadata["lastModifiedDateTime"], "%Y-%m-%dT%H:%M:%SZ"))
	destination_file = f'systemoversikt/import/{filename}'

	response = requests.get(file_metadata["@microsoft.graph.downloadUrl"])
	with open(destination_file, "wb") as f:
		f.write(response.content)
	#print(f"Lastet ned fil til {destination_file} ")

	return {"destination_file": destination_file, "modified_date": modified_date}

	#gammelt
	#from office365.runtime.auth.authentication_context import AuthenticationContext
	#from office365.sharepoint.client_context import ClientContext
	#from office365.sharepoint.files.file import File

	#ctx_auth = AuthenticationContext(os.environ['SHAREPOINT_SITE'])
	#ctx_auth.acquire_token_for_app(os.environ['SHAREPOINT_CLIENT_ID'], os.environ['SHAREPOINT_CLIENT_SECRET'])
	#ctx = ClientContext(os.environ['SHAREPOINT_SITE'], ctx_auth)

	#file = ctx.web.get_file_by_server_relative_path(source_filepath).get().execute_query()
	#modified_date = make_aware(datetime.datetime.strptime(file.time_last_modified, "%Y-%m-%dT%H:%M:%SZ"))
	#print(file.length)
	#FILNAVN = source_filepath.split("/")[-1] # last element of split
	#destination_file = f'systemoversikt/import/{FILNAVN}'

	#with open(destination_file, "wb") as local_file:
	#	file.download(local_file)
	#	ctx.execute_query()
	#print(f"Lastet ned fil til {destination_file} ")

	#return {"destination_file": destination_file, "modified_date": modified_date}



def decode_useraccountcontrol(code): # støttefunksjon for LDAP
	#https://support.microsoft.com/nb-no/help/305144/how-to-use-useraccountcontrol-to-manipulate-user-account-properties
	active_codes = ""
	status_codes = {
			"SCRIPT": 0,
			"ACCOUNTDISABLE": 1,
			"LOCKOUT": 3,
			"PASSWD_NOTREQD": 5,
			"PASSWD_CANT_CHANGE": 6,
			"NORMAL_ACCOUNT": 9,
			"DONT_EXPIRE_PASSWORD": 16,
			"SMARTCARD_REQUIRED": 18,
			"PASSWORD_EXPIRED": 23,
		}
	for key in status_codes:
		if int(code) >> status_codes[key] & 1:
			active_codes += " " + key
	return active_codes


def push_pushover(message):
	import os, requests
	import http.client
	USER_KEY = os.environ['PUSHOVER_USER_KEY']
	APP_TOKEN = os.environ['PUSHOVER_APP_TOKEN']
	if USER_KEY != "" and APP_TOKEN != "":
		try:
			payload = {"message": message, "user": USER_KEY, "token": APP_TOKEN}
			r = requests.post('https://api.pushover.net/1/messages.json', data=payload, headers={'User-Agent': 'Python'})
			conn = http.client.HTTPSConnection("api.pushover.net:443")
		except Exception as e:
			print(f"Error: Kan ikke sende til pushover grunnet {e}")
		return
	print(f"Pushover er ikke konfigurert")


def get_client_ip(request): # støttefunksjon
	try:
		x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
		if x_forwarded_for:
			ip = x_forwarded_for.split(',')[0]
		else:
			ip = request.META.get('REMOTE_ADDR')
		return ip
	except:
		return "get_client_ip() feilet"


def ldap_query(ldap_path, ldap_filter, ldap_properties, timeout): # støttefunksjon for LDAP
	import ldap, os
	server = 'ldaps://ldaps.oslofelles.oslo.kommune.no:636'
	user = os.environ["KARTOTEKET_LDAPUSER"]
	password = os.environ["KARTOTEKET_LDAPPASSWORD"]
	ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # have to deactivate sertificate check
	ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
	ldapClient = ldap.initialize(server)
	ldapClient.timeout = timeout
	ldapClient.set_option(ldap.OPT_REFERRALS, 0)  # tells the server not to chase referrals
	ldapClient.bind_s(user, password)  # synchronious

	result = ldapClient.search_s(
			ldap_path,
			ldap.SCOPE_SUBTREE,
			ldap_filter,
			ldap_properties
	)

	ldapClient.unbind_s()
	return result

"""
def ldap_get_user_details(username): # støttefunksjon for LDAP

	ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
	ldap_filter = ('(&(objectClass=user)(cn=%s))' % username)
	ldap_properties = ['cn', 'mail', 'givenName', 'displayName', 'sn', 'userAccountControl', 'logonCount', 'memberOf', 'lastLogonTimestamp', 'title', 'description', 'otherMobile', 'mobile', 'objectClass']

	result = ldap_query(ldap_path=ldap_path, ldap_filter=ldap_filter, ldap_properties=ldap_properties, timeout=10)
	users = []
	for cn,attrs in result:
		if cn:
			attrs_decoded = {}
			for key in attrs:
				attrs_decoded[key] = []
				if key == "lastLogonTimestamp":
					# always just one timestamp, hence item 0 hardcoded
					ms_timestamp = int(attrs[key][0][:-1].decode())  # removing one trailing digit converting 100ns to microsec.
					converted_date = datetime.datetime(1601,1,1) + datetime.timedelta(microseconds=ms_timestamp)
					attrs_decoded[key].append(converted_date)
				elif key == "userAccountControl":
					accountControl = decode_useraccountcontrol(int(attrs[key][0].decode()))
					attrs_decoded[key].append(accountControl)
				elif key == "memberOf":
					for element in attrs[key]:
						e = element.decode()
						regex_find_group = re.search(r'cn=([^\,]*)', e, re.I).groups()[0]

						attrs_decoded[key].append({
								"group": regex_find_group,
								"cn": e,
						})
					continue  # skip the next for..
				else:
					for element in attrs[key]:
						attrs_decoded[key].append(element.decode())

			users.append({
					"cn": cn,
					"attrs": attrs_decoded,
			})
	return users


def ldap_get_group_details(group): # støttefunksjon for LDAP

	ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
	ldap_filter = ('(&(cn=%s)(objectclass=group))' % group)
	ldap_properties = ['description', 'cn', 'member', 'objectClass']

	result = ldap_query(ldap_path=ldap_path, ldap_filter=ldap_filter, ldap_properties=ldap_properties, timeout=10)

	groups = []
	for cn,attrs in result:
		if cn:
			attrs_decoded = {}
			for key in attrs:
				attrs_decoded[key] = []
				if key == "member":
					for element in attrs[key]:
						e = element.decode()
						regex_find_username = re.search(r'cn=([^\,]*)', e, re.I).groups()[0]

						try:
							user = User.objects.get(username__iexact=regex_find_username)
						except:
							user = None

						attrs_decoded[key].append({
								"username": regex_find_username,
								"user": user,
								"cn": e,
						})
					continue  # skip the next for..
				for element in attrs[key]:
					attrs_decoded[key].append(element.decode())

			groups.append({
					"cn": cn,
					"attrs": attrs_decoded,
			})
	return groups
"""


def ldap_get_recursive_group_members(group): # støttefunksjon for LDAP
	ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
	ldap_filter = ('(&(objectCategory=person)(objectClass=user)(memberOf:1.2.840.113556.1.4.1941:=%s))' % group)
	ldap_properties = ['cn', 'displayName', 'description']

	result = ldap_query(ldap_path=ldap_path, ldap_filter=ldap_filter, ldap_properties=ldap_properties, timeout=100)
	users = []

	for cn,attrs in result:
		if cn:
			attrs_decoded = {}
			for key in attrs:
				attrs_decoded[key] = []
				for element in attrs[key]:
					attrs_decoded[key].append(element.decode())

			users.append({
					"cn": cn,
					"attrs": attrs_decoded,
			})

	return users


def ldap_users_securitygroups(user): # støttefunksjon for LDAP
	ldap_filter = ('(cn=%s)' % user)
	result = ldap_query(ldap_path="DC=oslofelles,DC=oslo,DC=kommune,DC=no", ldap_filter=ldap_filter, ldap_properties=[], timeout=5)
	try:
		memberof = result[0][1]['memberOf']
		return([g.decode() for g in memberof])
	except:
		#print(f"Finner ikke 'memberof' attributtet for {user}.")
		#print("error ldap_users_securitygroups(): %s" %(result))
		return []


def convert_distinguishedname_cn(liste): # støttefunksjon
	return [re.search(r'cn=([^\,]*)', g, re.I).groups()[0] for g in liste]


def decode_sid(sid):
	revision, sub_authority_count = struct.unpack('BB', sid[:2])
	identifier_authority = struct.unpack('>Q', b'\x00\x00' + sid[2:8])[0]
	sub_authorities = struct.unpack('<' + 'I' * sub_authority_count, sid[8:])
	return 'S-{}-{}-{}'.format(revision, identifier_authority, '-'.join(map(str, sub_authorities)))


def ldap_get_details(name, ldap_filter, request): # støttefunksjon
	ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
	ldap_properties = []
	result = ldap_query(ldap_path=ldap_path, ldap_filter=ldap_filter, ldap_properties=ldap_properties, timeout=10)
	groups = []
	users = []
	computers = []

	for cn,attrs in result:
		if cn:

			if b'computer' in attrs["objectClass"]:
				attrs_decoded = {}
				for key in attrs:
					if key in ['description', 'cn', 'objectClass', 'operatingSystem', 'operatingSystemVersion', 'dNSHostName',]:
						attrs_decoded[key] = []
						for element in attrs[key]:
							attrs_decoded[key].append(element.decode())
					else:
						continue

				computers.append({
						"cn": cn,
						"attrs": attrs_decoded,
				})

				return ({
						"computers": computers,
						"raw": result,
					})


			if b'user' in attrs["objectClass"]:
				import codecs
				attrs_decoded = {}
				for key in attrs:
					try:
						if key in ['objectGUID', 'objectSid', 'cn', 'sAMAccountName', 'mail', 'givenName', 'displayName', 'whenCreated', 'sn', 'userAccountControl', 'logonCount', 'memberOf', 'lastLogonTimestamp', 'title', 'description', 'otherMobile', 'mobile', 'objectClass', 'thumbnailPhoto']:
							# if not, then we don't bother decoding the value for now
							attrs_decoded[key] = []
							if key == "lastLogonTimestamp":
								# always just one timestamp, hence item 0 hardcoded
								## TODO flere steder
								ms_timestamp = int(attrs[key][0][:-1].decode())  # removing one trailing digit converting 100ns to microsec.
								converted_date = datetime.datetime(1601,1,1) + datetime.timedelta(microseconds=ms_timestamp)
								attrs_decoded[key].append(converted_date)

							elif key == "objectGUID":
								import uuid
								for element in attrs[key]:
									attrs_decoded[key].append(uuid.UUID(bytes_le=element))

							elif key == "objectSid":
								for element in attrs[key]:
									attrs_decoded[key].append(decode_sid(element))

							elif key == "whenCreated":
								value = attrs[key][0].decode().split('.')[0]
								converted_date = datetime.datetime.strptime(value, "%Y%m%d%H%M%S")
								attrs_decoded[key].append(converted_date)
							elif key == "userAccountControl":
								accountControl = decode_useraccountcontrol(int(attrs[key][0].decode()))
								attrs_decoded[key].append(accountControl)
							elif key == "thumbnailPhoto":
								attrs_decoded[key].append(codecs.encode(attrs[key][0], 'base64').decode('utf-8'))
							elif key == "memberOf":
								for element in attrs[key]:
									e = element.decode()
									regex_find_group = re.search(r'cn=([^\,]*)', e, re.I).groups()[0]

									attrs_decoded[key].append({
											"group": regex_find_group,
											"cn": e,
									})
								continue  # skip the next for..
							else:
								for element in attrs[key]:
									attrs_decoded[key].append(element.decode())
						else:
							continue
					except Exception as e:
						messages.warning(request, e)

				users.append({
						"cn": cn,
						"attrs": attrs_decoded,
				})
				return ({
						"users": users,
						"raw": result,
					})


			if b'group' in attrs["objectClass"]:
				attrs_decoded = {}
				for key in attrs:
					if key in ['description', 'cn', 'member', 'objectClass', 'memberOf']:
						attrs_decoded[key] = []
						if key == "member":
							for element in attrs[key]:
								e = element.decode()
								regex_find_username = re.search(r'cn=([^\,]*)', e, re.I).groups()[0]

								try:
									user = User.objects.get(username__iexact=regex_find_username)
								except:
									user = None

								attrs_decoded[key].append({
										"username": regex_find_username,
										"user": user,
										"cn": e,
								})
							continue  # skip the next for..
						for element in attrs[key]:
							attrs_decoded[key].append(element.decode())
					else:
						continue

				groups.append({
						"cn": cn,
						"attrs": attrs_decoded,
				})
				return ({
						"groups": groups,
						"raw": result,
					})
	return None

"""
def ldap_exact(name): # støttefunksjon for LDAP
	ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
	ldap_filter = ('(distinguishedName=%s)' % name)
	ldap_properties = []

	result = ldap_query(ldap_path=ldap_path, ldap_filter=ldap_filter, ldap_properties=ldap_properties, timeout=100)
	prepare = []

	for cn,attrs in result:
		if cn:
			attrs_decoded = {}
			for key in attrs:
				attrs_decoded[key] = []
				for element in attrs[key]:
					try:
						attrs_decoded[key].append(element.decode())
					except:
						attrs_decoded[key].append(element)

			prepare.append({
					"cn": cn,
					"attrs": attrs_decoded,
			})

	return {"raw": prepare}
"""


def prk_api(filename): # støttefunksjon
	path = "/var/kartoteket/source/systemoversikt/systemoversikt/import/" + filename
	with open(path, 'rt', encoding='utf-8') as file:
		response = HttpResponse(file, content_type='text/csv; charset=utf-8')
		response['Content-Disposition'] = 'attachment; filename="' + filename + '"'
	return response


def get_ipaddr_instance(address):

	if address == "" or address == None or address == "0.0.0.0":
		return None
	import ipaddress
	try:
		return NetworkIPAddress.objects.get(ip_address=address)
	except:
		n = NetworkIPAddress.objects.create(ip_address=address)
		n.ip_address_integer = int(ipaddress.ip_address(n.ip_address))
		n.save()
		return n

def virksomhet_til_bruker(request):
	"""
	Slå opp brukers virksomhet
	TODO: flytte til en modell-metode
	"""
	try:
		vir = request.user.profile.virksomhet.virksomhetsforkortelse
	except:
		vir = False
	return vir

def behandlingsprotokoll_egne(virksomhet):
	"""
	finne alle egne behandlinger
	"""
	virksomhetens_behandlinger = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=virksomhet)
	return virksomhetens_behandlinger

def behandlingsprotokoll_felles(virksomhet):
	"""
	finne systemer virksomheten abonnerer på behandlinger for
	"""
	systembruk_virksomhet = []
	virksomhetens_relevante_bruk = SystemBruk.objects.filter(brukergruppe=virksomhet).filter(del_behandlinger=True)
	for bruk in virksomhetens_relevante_bruk:
		systembruk_virksomhet.append(bruk.system)
	# finne alle behandlinger for identifiserte systemer merket fellesbehandling
	delte_behandlinger = BehandlingerPersonopplysninger.objects.filter(systemer__in=systembruk_virksomhet).filter(fellesbehandling=True)
	return delte_behandlinger

def behandlingsprotokoll(virksomhet):
	#slå sammen felles og egne behandlinger til et sett med behandlinger
	virksomhetens_behandlinger = behandlingsprotokoll_egne(virksomhet)
	delte_behandlinger = behandlingsprotokoll_felles(virksomhet)
	alle_relevante_behandlinger = virksomhetens_behandlinger.union(delte_behandlinger).order_by('internt_ansvarlig')
	return alle_relevante_behandlinger


"""
def csrf403(request):
	#Støttefunksjon for å vise feilmelding
	return render(request, 'csrf403.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})
"""

def login(request):
	"""
	støttefunksjon for å logge inn
	"""
	if settings.THIS_ENVIRONMENT == "PROD":
		return redirect(reverse('oidc_authentication_init'))
	else:
		return redirect("/admin/")

def unique_splitted_items(text):
	text = text.strip() # leading and trailing spaces
	filtered = text.replace('\"','').replace('\'','').replace(',',' ').replace(';',' ').replace(':',' ').replace('|',' ').lower()
	splitted = filtered.split()
	unike = set(splitted)
	return unike


def formater_permissions(permissions):
	if permissions == None:
		return []
	return [tag.replace(".", ": ").replace("_", " ") for tag in permissions]


def adgruppe_utnosting(gr): # støttefunksjon
	hierarki = []
	hierarki.append(gr)

	def identifiser_underliggende_grupper(gr):
		child_groups = []
		for element in json.loads(gr.member):
			try: # fra LDAP-svaret vet vi ikke om en member er en gruppe eller en brukerident. Vi må derfor slå opp.
				g = ADgroup.objects.get(distinguishedname=element)
				child_groups.append(g)
			except:
				pass # må være noe annet enn en gruppe, gitt at kartotekets database er synkronisert med AD
		return child_groups

	stack = []
	stack += identifiser_underliggende_grupper(gr)

	while stack:
		denne_gruppen = stack.pop()
		#print(denne_gruppen)
		hierarki.append(denne_gruppen)
		nye_undergrupper = identifiser_underliggende_grupper(denne_gruppen)
		for ug in nye_undergrupper:
			if ug not in hierarki:
				stack.append(ug)

	return hierarki



def human_readable_members(items, onlygroups=False): # støttefunksjon
	groups = []
	users = []
	notfound = []

	for item in items:
		match = False
		if onlygroups == False:
			regex_username = re.search(r'cn=([^\,]*)', item, re.I).groups()[0]
			try:
				u = User.objects.get(username__iexact=regex_username)
				users.append(u)
				match = True
				continue
			except:
				pass
		try:
			g = ADgroup.objects.get(distinguishedname=item)
			groups.append(g)
		except:
			notfound.append(item)  # vi fant ikke noe, returner det vi fikk

	return {"groups": groups, "users": users, "notfound": notfound}




##########################
# Støttefunksjoner slutt #
##########################



##################
# Ordinære views #
##################

def mal(request):
	required_permissions = ['systemoversikt.XYZ']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	return render(request, 'mal.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})


def tools_index(request):
	required_permissions = None
	return render(request, 'tools_index.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})


def debug_info(request):
	"""
	Denne funksjonen viser debug-informasjon ifm. feilsøking av bibliotek og moduler
	Tilgjengelig for personer som kan se logger
	"""
	required_permissions = ['auth.view_logentry']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import sqlite3
	sqlite_info = "SQLite: %s %s" % (sqlite3.version, sqlite3.__path__)

	import sys
	python_info = "Python: %s %s" % (sys.version, sys.executable)

	import django
	django_info = "Django: %s %s" % (django.VERSION, django.__path__)

	return render(request, 'system_debug_info.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'sqlite_info': sqlite_info,
		'python_info': python_info,
		'django_info': django_info,

	})


def tool_ntfs(request):
	required_permissions = ['systemoversikt.auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


	#GENERIC_READ            = 0x80000000
	#GENERIC_WRITE           = 0x40000000
	#GENERIC_EXECUTE         = 0x20000000
	#GENERIC_ALL             = 0x10000000
	#MAXIMUM_ALLOWED         = 0x02000000
	#ACCESS_SYSTEM_SECURITY  = 0x01000000
	#SYNCHRONIZE             = 0x00100000
	#WRITE_OWNER             = 0x00080000
	#WRITE_DACL              = 0x00040000
	#READ_CONTROL            = 0x00020000
	#DELETE                  = 0x00010000


	#sddl_string = "D:AI(A;OICI;FA;;;S-1-5-21-1123878227-590538075-4181424053-65398)(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)(A;OICI;FA;;;S-1-5-21-1123878227-590538075-4181424053-48099)(A;OICI;0x1200a9;;;S-1-5-21-1123878227-590538075-4181424053-73462)(A;OICI;0x1301bf;;;S-1-5-21-1123878227-590538075-4181424053-73463)(A;OICIID;0x1200a9;;;S-1-5-21-1123878227-590538075-4181424053-64527)(A;OICIID;0x1301bf;;;S-1-5-21-1123878227-590538075-4181424053-64528)(A;OICIID;FA;;;S-1-5-21-1123878227-590538075-4181424053-65398)(A;OICIID;FA;;;BA)(A;CIID;0x1200a9;;;S-1-5-21-1123878227-590538075-4181424053-304757)(A;OICIID;FA;;;SY)(A;OICIID;FA;;;S-1-5-21-1123878227-590538075-4181424053-48099)(A;OICIID;FA;;;S-1-5-21-1123878227-590538075-4181424053-442325)(A;OICIID;FA;;;S-1-5-21-1123878227-590538075-4181424053-167812)"
	#https://github.com/qtc-de/wconv?tab=readme-ov-file#parse-sddl


	return render(request, 'tool_ntfs.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})


def tool_word_count(request):
	required_permissions = None
	import collections
	inndata = request.POST.get('inndata', '')
	filtered = inndata.replace(',',' ').replace(';',' ').replace(':',' ').replace('|',' ').replace('.','').lower()
	words = filtered.split()
	stripped_words = []
	for w in words:
		stripped_words.append(w.strip())

	counter = collections.Counter(stripped_words)
	alle_ord = [{"ord": word, "frekvens": frequency} for word, frequency in dict(counter).items()]

	return render(request, 'tool_word_count.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"alle_ord": alle_ord,
		"inndata": inndata,
	})


def vulnstats(request):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


	try:
		integrasjonsstatus = IntegrasjonKonfigurasjon.objects.get(informasjon__icontains="qualys")
	except:
		integrasjonsstatus = None

	from django.db.models import Count
	from django.db.models.functions import TruncMonth, TruncYear, TruncDay
	data = {}

	data["count_all"] = QualysVuln.objects.all().count()

	data["count_uten_server"] = QualysVuln.objects.filter(server=None).count()

	data["count_status"] = QualysVuln.objects.values('status').annotate(count=Count('status'))

	data["count_unike_alvorligheter"] = QualysVuln.objects.values('severity').annotate(count=Count('severity'))
	severities = {item['severity'] for item in data["count_unike_alvorligheter"]}
	[data["count_unike_alvorligheter"].append({"severity": severity, "count": 0}) for severity in range(1, 6) if severity not in severities]
	data["count_unike_alvorligheter"] = sorted(data["count_unike_alvorligheter"], key=lambda x: x['severity'], reverse=False)

	data["count_unike_vulns"] = QualysVuln.objects.values('severity').annotate(unique_titles=Count('title', distinct=True))
	severities = {item['severity'] for item in data["count_unike_vulns"]}
	[data["count_unike_vulns"].append({"severity": severity, "unique_titles": 0}) for severity in range(1, 6) if severity not in severities]
	data["count_unike_vulns"] = sorted(data["count_unike_vulns"], key=lambda x: x['severity'], reverse=False)

	data["count_unike_known_exploited_vulns"] = list(QualysVuln.objects.filter(known_exploited=True).values('severity').annotate(unique_titles=Count('title', distinct=True)))
	severities = {item['severity'] for item in data["count_unike_known_exploited_vulns"]}
	[data["count_unike_known_exploited_vulns"].append({"severity": severity, "unique_titles": 0}) for severity in range(1, 6) if severity not in severities]
	data["count_unike_known_exploited_vulns"] = sorted(data["count_unike_known_exploited_vulns"], key=lambda x: x['severity'], reverse=False)


	data["count_unike_known_exploited_public_face"] = list(QualysVuln.objects.filter(known_exploited=True, public_facing=True).values('severity').annotate(unique_titles=Count('title', distinct=True)))
	severities = {item['severity'] for item in data["count_unike_known_exploited_public_face"]}
	[data["count_unike_known_exploited_public_face"].append({"severity": severity, "unique_titles": 0}) for severity in range(1, 6) if severity not in severities]
	data["count_unike_known_exploited_public_face"] = sorted(data["count_unike_known_exploited_public_face"], key=lambda x: x['severity'], reverse=False)


	data["count_first_seen_monthly"] = QualysVuln.objects.annotate(
				year=TruncYear('first_seen'),
				month=TruncMonth('first_seen')
				).values('year', 'month').annotate(count=Count('id')).order_by('year', 'month')

	data["count_last_seen_monthly"] = QualysVuln.objects.annotate(
				year=TruncYear('last_seen'),
				day=TruncDay('last_seen')
				).values('year', 'day').annotate(count=Count('id')).order_by('year', 'day')

	data["count_first_seen_monthly_public_facing"] = QualysVuln.objects.filter(known_exploited=True, severity__in=[5]).annotate(
				year=TruncYear('first_seen'),
				month=TruncMonth('first_seen')
				).values('year', 'month').annotate(count=Count('id')).order_by('year', 'month')

	data["vulns_first_seen_monthly_public_facing"] = QualysVuln.objects.filter(known_exploited=True, severity__in=[5]).values('title').annotate(count=Count('title')).order_by('-count')


	data["count_servere_aktive"] = CMDBdevice.objects.filter(device_type="SERVER").count()
	data["count_servere_uten_vuln"] = CMDBdevice.objects.filter(device_type="SERVER").filter(qualys_vulnerabilities=None).count()


	# eksponert internett kartoteket vs qualys
	dager_gamle = 30
	tidsgrense = datetime.date.today() - datetime.timedelta(days=dager_gamle)
	kartoteket_internett_eksponert = set(CMDBdevice.objects.filter(eksternt_eksponert_dato__gte=tidsgrense))
	qualys_internett_eksponert = set(CMDBdevice.objects.filter(qualys_vulnerabilities__public_facing=True))
	data["eksponert_kun_kartoteket"] = kartoteket_internett_eksponert - qualys_internett_eksponert
	data["eksponert_kun_qualys"] = qualys_internett_eksponert - kartoteket_internett_eksponert
	data["eksponert_dager_gamle"] = dager_gamle

	data["count_known_exploited"] = QualysVuln.objects.filter(known_exploited=True).count()
	data["count_known_exploited_unique"] = QualysVuln.objects.filter(known_exploited=True).values("title").annotate(count=Count('title')).count()

	# servere uten offering-kobling
	data["servere_uten_offering"] = CMDBdevice.objects.filter(service_offerings=None, device_type__in=["SERVER", "NETTWORK"])

	# finne flere kandidater til ansvar basisdrift

	# vise top 10 ting basisdrift ikke har patchet

	# vise top 10 ting forvalter ikke har patchet

	# vise alle service offerings med antall sårbarheter og sårbarheter per server

	# vise alle enheter i en service offering med antall sårbarheter per enhet

	# vise alle sårbarheter for en enhet, sortert på mest kritisk først

	# obsolete server med i graph over sist sett og først sett



	return render(request, 'rapport_vulnstats.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'integrasjonsstatus': integrasjonsstatus,
	})


def vulnstats_ukjente_servere(request):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	try:
		integrasjonsstatus = IntegrasjonKonfigurasjon.objects.get(informasjon__icontains="qualys")
	except:
		integrasjonsstatus = None

	data = {}
	data["unique_source_no_server"] = QualysVuln.objects.filter(server=None).values('source').annotate(count=Count('source')).order_by("source")

	return render(request, 'rapport_vulnstats_ukjente_servere.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'integrasjonsstatus': integrasjonsstatus,
	})


def vulnstats_severity_known_exploited_public(request, severity):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	try:
		integrasjonsstatus = IntegrasjonKonfigurasjon.objects.get(informasjon__icontains="qualys")
	except:
		integrasjonsstatus = None

	data = {}

	data["top_unike_vulns"] = QualysVuln.objects.filter(known_exploited=True, public_facing=True).filter(severity=severity).values('title').annotate(count=Count('title')).order_by('-count')

	return render(request, 'rapport_vulnstats_severity_known_exp_public.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'severity': severity,
		'integrasjonsstatus': integrasjonsstatus,
	})


def vulnstats_severity_known_exploited(request, severity):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	try:
		integrasjonsstatus = IntegrasjonKonfigurasjon.objects.get(informasjon__icontains="qualys")
	except:
		integrasjonsstatus = None

	data = {}

	data["top_unike_vulns"] = QualysVuln.objects.filter(known_exploited=True).filter(severity=severity).values('title').annotate(count=Count('title')).order_by('-count')

	return render(request, 'rapport_vulnstats_severity_known_exp.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'severity': severity,
		'integrasjonsstatus': integrasjonsstatus,
	})


def vulnstats_severity(request, severity):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	try:
		integrasjonsstatus = IntegrasjonKonfigurasjon.objects.get(informasjon__icontains="qualys")
	except:
		integrasjonsstatus = None

	data = {}

	top_unike_vulns = QualysVuln.objects.filter(severity=severity).values('title').annotate(count=Count('title')).order_by('-count')
	data["top_unike_vulns"] = top_unike_vulns

	return render(request, 'rapport_vulnstats_severity.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'severity': severity,
		'integrasjonsstatus': integrasjonsstatus,
	})


def vulnstats_whereis(request, vuln):
	required_permissions = ['systemoversikt.view_qualysvuln']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	try:
		integrasjonsstatus = IntegrasjonKonfigurasjon.objects.get(informasjon__icontains="qualys")
	except:
		integrasjonsstatus = None

	data = {}

	vulnerabilities = QualysVuln.objects.filter(title=vuln)
	data["vulnerabilities"] = vulnerabilities

	return render(request, 'rapport_vulnstats_whereis.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'integrasjonsstatus': integrasjonsstatus,
		'vuln': vuln,
	})


def tool_systemimport(request):
	required_permissions = ['systemoversikt.change_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import json
	innlogget_som = request.user.profile.virksomhet_innlogget_som

	if request.GET.get('upload') == "true":
		# Det er lastet opp nye data
		user_input_new_data = request.POST.get('user_input_new_data', '')
		try:
			user_input_json = json.loads(user_input_new_data)
			import_data_result = ""
			validated = True
		except:
			import_data_result = "Det du limte inn er ikke gyldig JSON"
			validated = False

		if validated:
			oppdatert = 0
			totalt = len(user_input_json['systemer'])
			for system_new in user_input_json['systemer']:
				if not 'id' in system_new:
					import_data_result += f"feltet id er obligatorisk.\n"
					continue
				system_new_id = system_new['id']
				try:
					system_old = System.objects.get(pk=system_new_id)
					import_data_result += f"Starter på {system_old}\n"
				except:
					import_data_result += f"Feilet å finne system med ID: {system_new_id}.\n"
					continue

				if system_old.systemforvalter == innlogget_som or system_old.systemeier == innlogget_som:

					try:
						if 'systemnavn' in system_new:
							system_old.systemnavn = system_new['systemnavn']
							import_data_result += f"- oppdaterte systemnavn\n"

						if 'alias' in system_new:
							system_old.alias = system_new['alias']
							import_data_result += f"- oppdaterte alias\n"

						if 'er_arkiv' in system_new:
							system_old.er_arkiv = system_new['er_arkiv']
							import_data_result += f"- oppdaterte er_arkiv\n"

						if 'antall_brukere' in system_new:
							system_old.antall_brukere = system_new['antall_brukere']
							import_data_result += f"- oppdaterte antall_brukere\n"

						if 'livslop_status' in system_new:
							system_old.livslop_status = system_new['livslop_status']
							import_data_result += f"- oppdaterte livslop_status\n"

						if 'url_risikovurdering' in system_new:
							system_old.url_risikovurdering = system_new['url_risikovurdering']
							import_data_result += f"- oppdaterte url_risikovurdering\n"

						if 'systembeskrivelse' in system_new:
							system_old.systembeskrivelse = system_new['systembeskrivelse']
							import_data_result += f"- oppdaterte systembeskrivelse\n"

						if 'konfidensialitetsvurdering' in system_new:
							system_old.konfidensialitetsvurdering = system_new['konfidensialitetsvurdering']
							import_data_result += f"- oppdaterte konfidensialitetsvurdering\n"

						if 'tilgjengelighetsvurdering' in system_new:
							system_old.tilgjengelighetsvurdering = system_new['tilgjengelighetsvurdering']
							import_data_result += f"- oppdaterte tilgjengelighetsvurdering\n"

						if 'driftsmodell_foreignkey' in system_new:
							system_old.driftsmodell_foreignkey.pk = system_new['driftsmodell_foreignkey']
							import_data_result += f"- oppdaterte driftsmodell_foreignkey\n"

						if 'forvaltning_epost' in system_new:
							system_old.forvaltning_epost = system_new['forvaltning_epost']
							import_data_result += f"- oppdaterte forvaltning_epost\n"

						if 'kritisk_kapabilitet' in system_new:
							system_old.kritisk_kapabilitet.clear()
							for kapabilitet in system_new['kritisk_kapabilitet']:
								system_old.kritisk_kapabilitet.add(kapabilitet)
							import_data_result += f"- oppdaterte kritisk_kapabilitet\n"

						"""
						if 'avhengigheter_referanser' in system_new:
							system_old.avhengigheter_referanser.clear()
							for avhengighet in system_new['avhengigheter_referanser']:
								system_old.avhengigheter_referanser.add(avhengighet)
							import_data_result += f"- oppdaterte avhengigheter_referanser\n"
						"""

						if 'dato_sist_ros' in system_new:
							system_old.dato_sist_ros = datetime.datetime.strptime(system_new['dato_sist_ros'], '%Y-%m-%d')
							import_data_result += f"- oppdaterte dato_sist_ros\n"

						if 'systemforvalter_kontaktpersoner_referanse' in system_new:
							system_old.systemforvalter_kontaktpersoner_referanse.clear()
							for email in system_new['systemforvalter_kontaktpersoner_referanse']:
								try:
									user = User.objects.get(email=email)
								except:
									import_data_result += f"Person med e-postadresse {email} finnes ikke.\n"
									continue

								try:
									ansvarlig = Ansvarlig.objects.get(brukernavn=user)
								except:
									ansvarlig = Ansvarlig.objects.create(brukernavn=user)
									import_data_result += f"{user} opprettet som ansvarlig.\n"

								system_old.systemforvalter_kontaktpersoner_referanse.add(ansvarlig)
							import_data_result += f"- oppdaterte systemforvalter_kontaktpersoner_referanse\n"

						system_old.save()
						import_data_result += f"Ferdig med {system_old}\n"
						oppdatert += 1

					except Exception as e:
						import_data_result += f"Feilet for {system_old} med: {e}\n"

				else:
					import_data_result += f"Du har ikke rettigheter til å endre {system_old}.\n"

			import_data_result += f"Importerte {oppdatert} av {totalt}."

	valgte_systemer_eksport = request.POST.getlist('eksport_systemer', None)
	if valgte_systemer_eksport:
		valgte_systemer_eksport = list(map(int, valgte_systemer_eksport))
		eksport_systemdata = []
		for system in valgte_systemer_eksport:
			try:
				system = System.objects.get(pk=system)
			except:
				continue

			eksport_systemdata.append({
					"id": system.pk,
					"systemnavn": system.systemnavn,
					"alias": system.alias,
					"er_arkiv": system.er_arkiv,
					"antall_brukere": system.antall_brukere,
					"livslop_status": system.livslop_status,
					"kritisk_kapabilitet": [k.pk for k in system.kritisk_kapabilitet.all()],
					"url_risikovurdering": system.url_risikovurdering,
					"dato_sist_ros": system.dato_sist_ros.strftime('%Y-%m-%d') if system.dato_sist_ros else None,
					"systembeskrivelse": system.systembeskrivelse,
					"konfidensialitetsvurdering": system.konfidensialitetsvurdering,
					"tilgjengelighetsvurdering": system.tilgjengelighetsvurdering,
					"systemforvalter_kontaktpersoner_referanse": [ansvarlig.brukernavn.email for ansvarlig in system.systemforvalter_kontaktpersoner_referanse.all()],
					"driftsmodell_foreignkey": system.driftsmodell_foreignkey.pk if system.driftsmodell_foreignkey else None,
					"forvaltning_epost": system.forvaltning_epost,
					#"avhengigheter_referanser": [referanse.pk for referanse in system.avhengigheter_referanser.all()]
				})

		oppslagstabeller = {
			"driftsmodell_foreignkey": {driftsmodell.pk: driftsmodell.__str__() for driftsmodell in Driftsmodell.objects.all()},
			"livslop_status": {livslop[0]: livslop[1] for livslop in LIVSLOEP_VALG},
			"konfidensialitetsvurdering": {valg[0]: valg[1] for valg in VURDERINGER_SIKKERHET_VALG},
			"tilgjengelighetsvurdering": {valg[0]: valg[1] for valg in VURDERINGER_SIKKERHET_VALG},
			"kritisk_kapabilitet": {kapabilitet.pk: kapabilitet.__str__() for kapabilitet in KritiskKapabilitet.objects.all()},
			#"avhengigheter_referanser": {system.pk: system.__str__() for system in System.objects.all()},
		}

		eksport_json = {
			"systemer": eksport_systemdata,
			"oppslagstabeller": oppslagstabeller,
		}


	mine_systemer = System.objects.filter(Q(systemeier=innlogget_som)|Q(systemforvalter=innlogget_som))
	for system in mine_systemer:
		if system.pk in valgte_systemer_eksport:
			system.valgt = True

	return render(request, 'tool_systemimport.html', {
		'request': request,
		'innlogget_som': innlogget_som,
		'mine_systemer': mine_systemer,
		'import_data_result': import_data_result if 'import_data_result' in locals() else None,
		'eksport_json': json.dumps(eksport_json, indent=4) if 'eksport_json' in locals() else None,
		'valgte_systemer_eksport': valgte_systemer_eksport,
		'user_input_new_data': user_input_new_data if 'user_input_new_data' in locals() else ''
	})



def tool_docx2html(request):
	required_permissions = None
	html = None
	messages = None
	if request.method == "POST":
		#print(request.POST)
		import mammoth
		from bs4 import BeautifulSoup
		try:
			docx_file = request.FILES['fileupload']
			filename = docx_file.name + ".html"
		except:
			html = "Ingen fil valgt"
			filename = "error.html"

		result = mammoth.convert_to_html(docx_file)
		html = BeautifulSoup(result.value).prettify()
		messages = result.messages

		if "download" in request.POST:
			response = HttpResponse(html, content_type='text/plain')
			response['Content-Disposition'] = 'attachment; filename={0}'.format(filename)
			return response

		# ellers så var det "preview" in request.POST. Da returnerer vi HTML direkte

	return render(request, 'tool_docx2html.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"html": html,
		"messages": messages,
	})


def tool_csv_converter(request):
	if request.method == "POST":
		import csv
		from io import StringIO
		file_content = request.FILES['fileupload'].read().decode('utf-8')
		rows = list(csv.DictReader(StringIO(file_content), delimiter=","))
		header = list(rows[0].keys())

		#print(header)
		#print(rows)

	return render(request, 'tool_csv_converter.html', {
		'request': request,
		'rows': rows if 'rows' in locals() else None,
		'header': header if 'header' in locals() else None,
	})


def tool_compare_items(request):
	required_permissions = []

	boks_a_raw = request.POST.get('boks_a', '')
	boks_b_raw = request.POST.get('boks_b', '')

	boks_a = unique_splitted_items(boks_a_raw)
	boks_b = unique_splitted_items(boks_b_raw)

	bare_i_a = boks_a.difference(boks_b)
	bare_i_b = boks_b.difference(boks_a)
	begge_a_og_b = boks_a.intersection(boks_b)
	a_og_b = boks_a.union(boks_b)

	return render(request, 'tool_compare_items.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"boks_a_raw": boks_a_raw,
		"boks_b_raw": boks_b_raw,
		"bare_i_a": bare_i_a,
		"bare_i_b": bare_i_b,
		"begge_a_og_b": begge_a_og_b,
		"a_og_b": a_og_b,
	})



def tool_unique_items(request):
	required_permissions = []

	raw = request.POST.get('data', '').strip()  # strip removes trailing and leading space
	filtered = raw.replace('\"','').replace('\'','').replace(',',' ').replace(';',' ').replace(':',' ').replace('|',' ').lower()
	splitted = filtered.split()
	unike = sorted(set(splitted))

	return render(request, 'tool_unique_items.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"result": unike,
		"query": raw,
	})


# def tool_longest_substring
# def tool_item_count


def cmdb_adcs_index(request):
	required_permissions = ['systemoversikt.change_azureapplication']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from os import path, listdir
	from os.path import isfile, join

	path = path.dirname(path.abspath(__file__)) + "/pki/"
	limit = 60
	summary = []

	selected_file_str = request.GET.get("file", None)
	if selected_file_str:
		if re.match(r"^\d{14}_Certipy.json$", selected_file_str):
			# only if valid open the file
			with open(f"{path}/{selected_file_str}") as f:
				selected_file = list(json.load(f).items())

			for k, v in selected_file[1][1].items():
				summary.append({
						"template": v["Template Name"],
						"ca": v["Certificate Authorities"],
						"key_usage": v["Extended Key Usage"],
						"validity_period": v["Validity Period"],
						"vulnerabilities": v["[!] Vulnerabilities"]
					})
		else:
			raise Http404
	else:
		selected_file = None

	# always show file list
	filelist = [f for f in listdir(path) if isfile(join(path, f))]
	filelist = sorted(filelist, reverse=True)
	if len(filelist) > limit:
		filelist = filelist[:limit]

	filelist_readable = []
	for item in filelist:
		tekst = f"{item[0:4]}-{item[4:6]}-{item[6:8]} {item[8:10]}:{item[10:12]}.{item[12:14]}"
		filelist_readable.append({
				"filename": item,
				"tekst": tekst,
			})

	return render(request, 'cmdb_adcs_index.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"filelist": filelist_readable,
		"selected_file": json.dumps(selected_file, indent=4),
		"summary": summary,
	})



def cmdb_per_virksomhet(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	template_data = list()
	bs_alle = list(CMDBbs.objects.filter(operational_status=True, eksponert_for_bruker=True))
	for virksomhet in Virksomhet.objects.all():
		bs_eier = []
		for system in virksomhet.systemer_eier.all():
			offerings = system.service_offerings.all()
			for offering in offerings:
				bs_eier.append(offering)
				try:
					bs_alle.remove(offering)
				except:
					pass

		bs_forvalter = []
		for system in virksomhet.systemer_systemforvalter.all():
			if hasattr(system, 'bs_system_referanse'):
				bs = system.bs_system_referanse
				bs_forvalter.append(bs)
		template_data.append({"virksomhet": virksomhet, "bs_eier": bs_eier, "bs_forvalter": bs_forvalter,})

	return render(request, 'cmdb_per_virksomhet.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'template_data': template_data,
		"resterende_bs": bs_alle,
	})



def o365_avvik(request):
	#Viser alle avvik per virksomhet (cisco, bigip..)
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	innhentingsbehov = []
	for i in RapportGruppemedlemskaper.objects.all().order_by('kategori'):
		innhentingsbehov.append({
				"kategori": i.kategori,
				"beskrivelse": i.beskrivelse,
				"kommentar": i.kommentar,
				"grupper": [g.common_name for g in i.grupper.all()],
				"AND_grupper":[g.common_name for g in i.AND_grupper.all()],
				"tidslinjedata": json.loads(i.tidslinjedata),
			})

	def rapport_konkrete_brukere(grupper):
		gruppeemdlemmer = set()
		for gruppe in grupper:
			try:
				gruppe = ADgroup.objects.get(common_name__iexact=gruppe)
			except:
				messages.error(request, f"fant ikke gruppen {gruppe}")
				continue

			brukere = json.loads(gruppe.member)
			for bruker in brukere:
				try:
					gruppeemdlemmer.add(bruker.split(',')[0].split('CN=')[1])
				except:
					messages.error(request, f"Kunne ikke splitte opp {bruker}")

		return gruppeemdlemmer


	def rapport_hent_statistikk(i):
		antall = 0
		if len(i["AND_grupper"]) == 0: # Det er bare ordinære grupper som kan slås opp direkte. Er mye raskere enn å dekode enkeltbrukere.
			for gruppe in i["grupper"]:
				try:
					gruppe = ADgroup.objects.get(common_name__iexact=gruppe)
					antall += gruppe.membercount
				except:
					messages.error(request, f"fant ikke gruppen {gruppe}")
					pass
		else: # Det er 1 eller flere grupper som skal AND-es sammen. Vi må derfor lese ut faktiske identer.
			gruppeemdlemmer = rapport_konkrete_brukere(i["grupper"])
			AND_gruppemedlemmer = rapport_konkrete_brukere(i["AND_grupper"])
			medlemmer_snitt = gruppeemdlemmer.intersection(AND_gruppemedlemmer)

			antall = len(medlemmer_snitt)
			i["konkrete_medlemmer"] = list(medlemmer_snitt)

		i["medlemmer"] = antall
		return i

	statistikk = []
	for i in innhentingsbehov:
		statistikk.append(rapport_hent_statistikk(i))

	alle_virskomhet = Virksomhet.objects.filter(ordinar_virksomhet=True)

	return render(request, 'rapport_sikkerhetsavvik.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'statistikk': statistikk,
		'virksomheter': alle_virskomhet,
	})



def prk_api_usr(request): #API
	if request.method == "GET":

		key = request.headers.get("key", None)
		if key == None:
			key = request.GET.get("key", None)

		allowed_keys = APIKeys.objects.filter(navn__startswith="prk_").values_list("key", flat=True)
		if key in list(allowed_keys):
			owner = APIKeys.objects.get(key=key).navn
			ApplicationLog.objects.create(event_type="PRK API download", message="Nøkkel %s" %(owner))
			return prk_api("usr.csv")

		else:
			return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)



def prk_api_grp(request): #API
	if request.method == "GET":

		key = request.headers.get("key", None)
		if key == None:
			key = request.GET.get("key", None)

		allowed_keys = APIKeys.objects.filter(navn__startswith="prk_").values_list("key", flat=True)
		if key in list(allowed_keys):
			from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
			try:
				owner = APIKeys.objects.get(key=key).navn
			except MultipleObjectsReturned:
				owner = "Flere treff på nøkkeleier"

			ApplicationLog.objects.create(event_type="PRK API download", message="Nøkkel %s" %(owner))
			return prk_api("grp.csv")

		else:
			return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)


def azure_user_consents(request):
	#Vise liste over alle Azure enterprise applications med rettigheter de har fått tildelt
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	userconsents = AzureUserConsents.objects.all()

	return render(request, 'rapport_azure_user_consents.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'userconsents': userconsents,
	})


def azure_applications(request):
	#Vise liste over alle Azure enterprise applications med rettigheter de har fått tildelt
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	applikasjoner = AzureApplication.objects.filter(active=True).order_by('-createdDateTime')

	return render(request, 'cmdb_azure_applications.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'applikasjoner': applikasjoner,
	})



def azure_application_keys(request):
	#Vise liste over alle Azure enterprise application keys etter utløpsdato
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	keys = AzureApplicationKeys.objects.order_by('end_date_time')

	return render(request, 'cmdb_azure_application_keys.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'keys': keys,
	})



def rapport_startside(request):
	required_permissions = None
	return render(request, 'rapport_startside.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})



def isk_ansvarlig_for_system(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	aktuelle_systemer = list()
	systemer = System.objects.all()
	for s in systemer:
		if s.er_infrastruktur():
			continue # skip

		if s.driftsmodell_foreignkey != None:
			if s.driftsmodell_foreignkey.type_plattform != 1: # 1 er private cloud
				continue # skip

			if s.driftsmodell_foreignkey.ansvarlig_virksomhet != None: # hvis noen eier denne plattformen
				if s.driftsmodell_foreignkey.ansvarlig_virksomhet.virksomhetsforkortelse == "UKE": # og dersom denne eier er UKE
					aktuelle_systemer.append(s)

	return render(request, 'rapport_systemer_per_isk.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'aktuelle_systemer': aktuelle_systemer,
	})



def o365_lisenser(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	data = []
	data.append({"tekst": "Brukere i gruppe 1 - Tykk klient", "antall": len(User.objects.filter(profile__o365lisence=1))})
	data.append({"tekst": "Brukere i gruppe 2 - Flerbruker", "antall": len(User.objects.filter(profile__o365lisence=2))})
	data.append({"tekst": "Brukere i gruppe 3 - Mangler epost", "antall": len(User.objects.filter(profile__o365lisence=3))})
	data.append({"tekst": "Brukere i gruppe 4 - Educaton", "antall": len(User.objects.filter(profile__o365lisence=4))})

	virksomheter = Virksomhet.objects.filter(ordinar_virksomhet=True)

	return render(request, 'rapport_o365_lisenser.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'data': data,
		'virksomheter': virksomheter,
	})



def systemer_citrix(request):
	#Viser alle systemer som er knyttet til Citrix med metadata
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	systemer_på_citrix = System.objects.filter(~Q(citrix_publications=None))

	for s in systemer_på_citrix:

		citrix_apps = s.citrix_publications.filter(publikasjon_active=True)

		s.tmp_antall_publiseringer = len(citrix_apps)
		s.tmp_intern = True if any(app.sone == "Intern" for app in citrix_apps) else False
		s.tmp_sikker = True if any(app.sone == "Sikker" for app in citrix_apps) else False


		s.tmp_vApp = True if any(app.type_vApp for app in citrix_apps) else False
		s.tmp_nettleser = True if any(app.type_nettleser for app in citrix_apps) else False
		s.tmp_remotedesktop = True if any(app.type_remotedesktop for app in citrix_apps) else False

		s.tmp_nhn = True if any(app.type_nhn for app in citrix_apps) else False
		s.tmp_antall_brukere = max(app.cache_antall_publisert_til for app in citrix_apps)

		s.tmp_executable = True if any(app.type_executable for app in citrix_apps) else False
		s.tmp_vbs = True if any(app.type_vbs for app in citrix_apps) else False
		s.tmp_ps1 = True if any(app.type_ps1 for app in citrix_apps) else False
		s.tmp_bat = True if any(app.type_bat for app in citrix_apps) else False
		s.tmp_cmd = True if any(app.type_cmd for app in citrix_apps) else False

		unike_desktop_groups = []
		for app in citrix_apps:
			decoded_json = json.loads(app.publikasjon_json)
			#print(decoded_json)
			unike_desktop_groups.extend(decoded_json["AllAssociatedDesktopGroupUids_Name"])

		s.tmp_desktop_groups = set(unike_desktop_groups)


	try:
		integrasjonsstatus = IntegrasjonKonfigurasjon.objects.get(informasjon__icontains="citrixpubliseringer")
	except:
		integrasjonsstatus = None

	return render(request, 'systemer_citrix.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer_på_citrix,
		'integrasjonsstatus': integrasjonsstatus,
	})




def system_kritisk_funksjon(request):
	#Viser alle kritiske funksjoner og hvilke systemer som understøtter dem
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	kritiske_funksjoner = KritiskFunksjon.objects.all()
	kritiske_kapabiliteter = KritiskKapabilitet.objects.all()
	systemer = System.objects.filter(~Q(kritisk_kapabilitet=None))

	return render(request, 'system_kritisk_funksjon.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'kritiske_funksjoner': kritiske_funksjoner,
		'systemer': systemer,
		'kritiske_kapabiliteter': kritiske_kapabiliteter,
	})



def system_informasjonsbehandling(request):
	#Vise alle LOS-begreper og systemer som er knyttet til
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	los_hovedtema = LOS.objects.filter(kategori_ref__verdi="Tema", active=True, parent_id=None)

	return render(request, 'system_los_oversikt.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'los_hovedtema': los_hovedtema,
	})



def system_los_struktur(request, pk=None):
	#Vise alle LOS-begreper grafisk
	required_permissions = None
	los_graf = {"nodes": [], "edges": []}

	nodes = LOS.objects.filter(active=True).filter(~Q(kategori_ref=None))

	if pk:
		nodes = nodes.filter(buffer_alle_tema=pk)
		nodes = list(nodes)
		nodes.append(LOS.objects.get(pk=pk))

	for node in nodes:

		if not pk:
			if node.kategori_ref.verdi != "Tema":
				continue

		los_graf["nodes"].append(
				{"data": {
					"id": node.pk,
					#"parent": node.hovedtema(),
					"name": node.verdi,
					"shape": "ellipse",
					"color": node.color(),
					#"size": node.size(),
					"href": reverse('system_los_struktur', args=[node.pk])
					}
				})

		for parent in node.parent_id.all():
			if parent in nodes:
				los_graf["edges"].append(
						{"data": {
							"source": node.pk,
							"target": parent.pk,
							"linestyle": "solid"
							}
						})

	return render(request, 'system_los_struktur.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'los_graf': los_graf,
		'nodes': nodes,
	})

def citrix_desktop_group(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	group_name = request.GET.get("gruppe", "")
	citrix_desktop_group_members = CMDBdevice.objects.filter(citrix_desktop_group=group_name)

	return render(request, 'cmdb_citrix_desktop_group.html', {
		'request': request,
		'citrix_desktop_group_members': citrix_desktop_group_members,
		'group_name': group_name,
	})



def alle_citrixpub(request, pk=None):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	antall_apper_totalt = CitrixPublication.objects.all().count()
	antall_apper_koblet = CitrixPublication.objects.filter(publikasjon_active=True, systemer=None).count()

	citrixapps = CitrixPublication.objects.filter(publikasjon_active=True)

	if pk:
		citrixapps = citrixapps.filter(systemer=pk)


	for app in citrixapps:
		app.publikasjon_json = json.loads(app.publikasjon_json)

	try:
		antall_apper_koblet_pct = antall_apper_koblet / len(citrixapps)
	except:
		antall_apper_koblet_pct = "?"

	unike_siloer = CMDBdevice.objects.order_by().values('citrix_desktop_group').distinct()

	try:
		integrasjonsstatus = IntegrasjonKonfigurasjon.objects.get(informasjon__icontains="citrixpubliseringer")
	except:
		integrasjonsstatus = None

	return render(request, 'cmdb_citrix_apps.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'citrixapps': citrixapps,
		'filter': True if pk else False,
		'antall_apper_totalt': antall_apper_totalt,
		'antall_apper_koblet': antall_apper_koblet,
		'antall_apper_koblet_pct': f"{round(antall_apper_koblet_pct * 100, 1)}%" if antall_apper_koblet_pct != "?" else None,
		'unike_siloer': unike_siloer,
		'integrasjonsstatus': integrasjonsstatus,
	})

def alle_nettverksenheter(request):
	#Viser alle nettverksenheter (cisco, bigip..)
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	nettverksenehter = CMDBdevice.objects.filter(device_type="NETWORK")

	return render(request, 'cmdb_nettverksenehter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'nettverksenehter': nettverksenehter,
	})


def rapport_cmdb_status(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	integrasjoner = IntegrasjonKonfigurasjon.objects.all()

	return render(request, 'rapport_cmdb_status.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'integrasjoner': integrasjoner,
	})


def rapport_ad_identer(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	ad_brukere_per_virksomhet = []
	for virksomhet in Virksomhet.objects.all():
		interne = Profile.objects.filter(accountdisable=False, virksomhet=virksomhet, account_type="Intern").count()
		eksterne = Profile.objects.filter(accountdisable=False, virksomhet=virksomhet, account_type="Ekstern").count()
		servicekontoer = Profile.objects.filter(accountdisable=False, virksomhet=virksomhet, account_type="Servicekonto").count()
		ressurser = Profile.objects.filter(accountdisable=False, virksomhet=virksomhet, account_type="Ressurs").count()
		kontakter = Profile.objects.filter(accountdisable=False, virksomhet=virksomhet, account_type="Kontakt").count()

		ad_brukere_per_virksomhet.append({
			'virksomhet': virksomhet,
			'interne': interne,
			'eksterne': eksterne,
			'servicekontoer': servicekontoer,
			'ressurser': ressurser,
			'kontakter': kontakter,
			})

	return render(request, 'rapport_ad_identer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ad_brukere_per_virksomhet': ad_brukere_per_virksomhet,
	})



def cmdb_statistikk(request):
	#Vise alle statistikk over alt i CMDB
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	count_office_ea = AzureApplication.objects.all().count()
	count_office_ea_keys = AzureApplicationKeys.objects.all().count()
	count_ad_users = User.objects.all().count()
	count_prk_users = User.objects.filter(profile__from_prk=True).count()
	count_prk_skjema = PRKskjema.objects.all().count()
	count_prk_skjema_valg = PRKvalg.objects.all().count()
	count_ad_grupper = ADgroup.objects.all().count()
	count_bs = CMDBbs.objects.filter(operational_status=True).count()
	count_bss = CMDBRef.objects.filter(operational_status=1).count()
	count_klienter = CMDBdevice.objects.filter(device_type="KLIENT").all().count()
	count_server = CMDBdevice.objects.filter(device_type="SERVER").all().count()
	count_vlan = NetworkContainer.objects.all().count()
	count_vip = virtualIP.objects.all().count()
	count_vip_pool = VirtualIPPool.objects.all().count()
	count_oracle = CMDBdatabase.objects.filter(db_version__icontains="oracle", db_operational_status=True).all().count()
	count_mssql = CMDBdatabase.objects.filter(db_version__icontains="mssql", db_operational_status=True).all().count()
	count_mem = CMDBdevice.objects.filter(device_type="SERVER").aggregate(Sum('comp_ram'))["comp_ram__sum"]
	if count_mem:
		count_mem = count_mem * 1000*1000 # summen er MB --> bytes
	count_disk = CMDBdevice.objects.filter(device_type="SERVER").aggregate(Sum('comp_disk_space'))["comp_disk_space__sum"] #summen er i bytes
	count_oracle_disk = CMDBdatabase.objects.filter(db_version__icontains="oracle", db_operational_status=True).aggregate(Sum('db_u_datafilessizekb'))["db_u_datafilessizekb__sum"] # summen er i bytes
	count_mssql_disk = CMDBdatabase.objects.filter(db_version__icontains="mssql", db_operational_status=True).aggregate(Sum('db_u_datafilessizekb'))["db_u_datafilessizekb__sum"] # summen er i bytes
	count_dns_arecords = DNSrecord.objects.filter(dns_type="A record").count()
	count_dns_cnames = DNSrecord.objects.filter(dns_type="CNAME").count()
	count_cisco = CMDBdevice.objects.filter(device_type="NETWORK").filter(comp_os__icontains="cisco").count()
	count_bigip = CMDBdevice.objects.filter(device_type="NETWORK").filter(comp_os__icontains="f5").count()
	count_backup = CMDBbackup.objects.all().aggregate(Sum('backup_size_bytes'))["backup_size_bytes__sum"]
	count_service_accounts = User.objects.filter(profile__distinguishedname__icontains="OU=Servicekontoer").filter(profile__accountdisable=False).count()
	count_drift_accounts = User.objects.filter(Q(profile__distinguishedname__icontains="OU=DRIFT,OU=Eksterne brukere") | Q(profile__distinguishedname__icontains="OU=DRIFT,OU=Brukere")).filter(profile__accountdisable=False).count()
	count_ressurs_accounts = User.objects.filter(profile__distinguishedname__icontains="OU=Ressurser").filter(profile__accountdisable=False).count()
	count_inactive_accounts = User.objects.filter(profile__accountdisable=True).count()
	count_utenfor_OK_accounts = User.objects.filter(~Q(profile__distinguishedname__icontains="OU=OK")).filter(profile__accountdisable=False).count()

	return render(request, 'cmdb_statistikk.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'count_office_ea': count_office_ea,
		'count_office_ea_keys': count_office_ea_keys,
		'count_ad_users': count_ad_users,
		'count_prk_users': count_prk_users,
		'count_prk_skjema': count_prk_skjema,
		'count_prk_skjema_valg': count_prk_skjema_valg,
		'count_ad_grupper': count_ad_grupper,
		'count_bs': count_bs,
		'count_bss': count_bss,
		'count_server': count_server,
		'count_klienter': count_klienter,
		'count_vlan': count_vlan,
		'count_vip': count_vip,
		'count_vip_pool': count_vip_pool,
		'count_oracle': count_oracle,
		'count_mssql': count_mssql,
		'count_mem': count_mem,
		'count_disk': count_disk,
		'count_oracle_disk': count_oracle_disk,
		'count_mssql_disk': count_mssql_disk,
		'count_dns_arecords': count_dns_arecords,
		'count_dns_cnames': count_dns_cnames,
		'count_cisco': count_cisco,
		'count_bigip': count_bigip,
		'count_backup': count_backup,
		'count_service_accounts': count_service_accounts,
		'count_drift_accounts': count_drift_accounts,
		'count_ressurs_accounts': count_ressurs_accounts,
		'count_inactive_accounts': count_inactive_accounts,
		'count_utenfor_OK_accounts': count_utenfor_OK_accounts,
	})



def detaljer_vip(request, pk):
	#Vise detaljer for lastbalanserte URL-er med deres pool-medlemmer
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	vip = virtualIP.objects.get(pk=pk)

	return render(request, 'cmdb_alle_vip.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'alle_viper': [vip],
	})



def cmdb_devicedetails(request, pk):
	#Vise detaljer for server/klient (ting med IP)
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	device = CMDBdevice.objects.get(pk=pk)

	return render(request, 'cmdb_devicedetails.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'device': device,
	})



def alle_dns(request):
	#Vise alle DNS navn og alias
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	alle_dnsnavn = DNSrecord.objects.all()
	return render(request, 'cmdb_alle_dns.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'alle_dnsnavn': alle_dnsnavn,
	})



def dns_txt(request):
	#Vise alle DNS navn og alias
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	txt_records = DNSrecord.objects.filter(dns_type="TXT")

	return render(request, 'cmdb_dns_txt.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'txt_records': txt_records,
	})



def alle_vip(request):
	#Vise alle lastbalanserte URL-er med deres pool-medlemmer
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	def vip_loopup(term):
		return virtualIP.objects.filter(
				Q(vip_name__icontains=search_term) |
				Q(pool_name__icontains=search_term) |
				Q(ip_address__icontains=search_term)
			)

	search_term_raw = request.GET.get('search_term', '')
	search_term = search_term_raw.strip()

	if search_term == "__ALL__":
		alle_viper = virtualIP.objects.all()

	elif len(search_term) > 1:
		alle_viper = vip_loopup(search_term)

	else:
		alle_viper = []

	return render(request, 'cmdb_alle_vip.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'alle_viper': alle_viper,
		'vip_search_term': search_term_raw,
	})



def nettverk_detaljer(request, pk):
	#Vise brannmuråpninger koblet til et nettverk
	required_permissions = ['systemoversikt.view_brannmurregel']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	nettverk = NetworkContainer.objects.get(pk=pk)
	network_ip_addresses = nettverk.network_ip_address.all().order_by('ip_address_integer')
	firewall_openings = nettverk.firewall_rules.filter(active=True)

	return render(request, 'cmdb_nettverk_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'nettverk': nettverk,
		'network_ip_addresses': network_ip_addresses,
		'firewall_openings': firewall_openings,
		'config_maximum_mark_server': 100,
	})



def alle_nettverk(request):
	#Vise alle nettverk
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	def network_loopup(term):
		return NetworkContainer.objects.filter(
				Q(ip_address__icontains=search_term) |
				Q(orgname__icontains=search_term) |
				Q(comment__icontains=search_term) |
				Q(vrfname__icontains=search_term) |
				Q(locationid__icontains=search_term)
			)

	search_term_raw = request.GET.get('search_term', '')
	search_term = search_term_raw.strip().split('/')[0]

	if search_term == "__ALL__":
		nettverk = NetworkContainer.objects.all()

	elif len(search_term) > 1:
		nettverk = network_loopup(search_term)

		if len(nettverk) == 0: # ingen treff, kan være søk på en IP i et nettverk
			try:
				import ipaddress
				nettverk = []
				search_ip = ipaddress.ip_address(search_term)
				alle_vlan = NetworkContainer.objects.all()
				for vlan in alle_vlan:
					vlan_network = ipaddress.ip_network(vlan.ip_address + "/" + str(vlan.subnet_mask))
					if search_ip in vlan_network:
						nettverk.append(vlan)
			except:
				pass

	else:
		nettverk = []

	return render(request, 'cmdb_alle_nettverk.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'alle_nettverk': nettverk,
		'vlan_search_term': search_term_raw,
	})



def cmdb_uten_backup(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	uten_backup = CMDBdevice.objects.filter(backup=None, device_type="SERVER").order_by('service_offerings__parent_ref')

	return render(request, 'cmdb_uten_backup.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'uten_backup': uten_backup,
	})



def cmdb_backup_index(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	count_backup = CMDBbackup.objects.all().aggregate(Sum('backup_size_bytes'))["backup_size_bytes__sum"]
	offering_all = CMDBRef.objects.all()

	sum_offering_all = 0
	for offering in offering_all:
		sum_offering_all += offering.backup_size()

	volum_servere_d30 = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D30"):
		volum_servere_d30 += backup_data.backup_size_bytes

	volum_oracle_d40 = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D40"):
		volum_oracle_d40 += backup_data.backup_size_bytes

	volum_file_exch_DWMY = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D30-W13-M12-Y10").filter(~Q(device_str__icontains="SQL")):
		volum_file_exch_DWMY += backup_data.backup_size_bytes

	volum_mssql_DWMY = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D30-W13-M12-Y10", device_str__icontains="SQL"):
		volum_mssql_DWMY += backup_data.backup_size_bytes

	volum_ukjent = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency=""):
		volum_ukjent += backup_data.backup_size_bytes

	volum_servere_d30_test = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D30", environment__in=[2,3,4,5,6,7,8]):
		volum_servere_d30_test += backup_data.backup_size_bytes

	volum_oracle_d40_test = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D40", environment__in=[2,3,4,5,6,7,8]):
		volum_oracle_d40_test += backup_data.backup_size_bytes

	volum_file_exch_DWMY_test = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D30-W13-M12-Y10", environment__in=[2,3,4,5,6,7,8]).filter(~Q(device_str__icontains="SQL")):
		volum_file_exch_DWMY_test += backup_data.backup_size_bytes

	volum_mssql_DWMY_test = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="D30-W13-M12-Y10", device_str__icontains="SQL", environment__in=[2,3,4,5,6,7,8]):
		volum_mssql_DWMY_test += backup_data.backup_size_bytes

	volum_ukjent_test = 0
	for backup_data in CMDBbackup.objects.filter(backup_frequency="", environment__in=[2,3,4,5,6,7,8]):
		volum_ukjent_test += backup_data.backup_size_bytes

	pct_servere_d30 = round(100 * volum_servere_d30_test / count_backup, 1)
	pct_oracle_d40 = round(100 * volum_oracle_d40_test / count_backup, 1)
	pct_file_exch_DWMY = round(100 * volum_file_exch_DWMY_test / count_backup, 1)
	pct_mssql_DWMY = round(100 * volum_mssql_DWMY_test / count_backup, 1)
	pct_ukjent = round(100 * volum_ukjent_test / count_backup, 1)


	return render(request, 'cmdb_backup_index.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'count_backup': count_backup,
		'offering_all': offering_all,
		'sum_offering_all': sum_offering_all,
		'volum_servere_d30': volum_servere_d30,
		'volum_oracle_d40': volum_oracle_d40,
		'volum_file_exch_DWMY': volum_file_exch_DWMY,
		'volum_mssql_DWMY': volum_mssql_DWMY,
		'volum_ukjent': volum_ukjent,
		'volum_servere_d30_test': volum_servere_d30_test,
		'volum_oracle_d40_test': volum_oracle_d40_test,
		'volum_file_exch_DWMY_test': volum_file_exch_DWMY_test,
		'volum_mssql_DWMY_test': volum_mssql_DWMY_test,
		'volum_ukjent_test': volum_ukjent_test,
		'pct_servere_d30': pct_servere_d30,
		'pct_oracle_d40': pct_oracle_d40,
		'pct_file_exch_DWMY': pct_file_exch_DWMY,
		'pct_mssql_DWMY': pct_mssql_DWMY,
		'pct_ukjent': pct_ukjent,
	})



def cmdb_lagring_index(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	count_san_allocated = CMDBdevice.objects.filter(device_type="SERVER").aggregate(Sum('vm_disk_allocation'))["vm_disk_allocation__sum"]
	count_san_used = CMDBdevice.objects.filter(device_type="SERVER").aggregate(Sum('vm_disk_usage'))["vm_disk_usage__sum"]
	pct_used = int(count_san_used / count_san_allocated * 100)
	count_san_missing_bs = CMDBdevice.objects.filter(device_type="SERVER").filter(service_offerings=None).aggregate(Sum('vm_disk_allocation'))["vm_disk_allocation__sum"]
	count_not_active = CMDBdevice.objects.filter(device_type="SERVER").aggregate(Sum('vm_disk_allocation'))["vm_disk_allocation__sum"]

	bs_all = CMDBbs.objects.all()

	return render(request, 'cmdb_lagring_index.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'count_san_allocated': count_san_allocated,
		'count_san_used': count_san_used,
		'pct_used': pct_used,
		'count_san_missing_bs': count_san_missing_bs,
		'count_not_active': count_not_active,
		'bs_all': bs_all,

	})



def cmdb_minne_index(request):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	try:
		count_ram_allocated = CMDBdevice.objects.filter(device_type="SERVER").aggregate(Sum('comp_ram'))["comp_ram__sum"] * 1000**2 #MB->bytes
	except:
		count_ram_allocated = 0
	try:
		count_ram_missing_bs = CMDBdevice.objects.filter(device_type="SERVER").filter(sub_name=None).aggregate(Sum('comp_ram'))["comp_ram__sum"] * 1000**2 #MB->bytes
	except:
		count_ram_missing_bs = 0

	bs_all = CMDBbs.objects.all()

	return render(request, 'cmdb_minne_index.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'count_ram_allocated': count_ram_allocated,
		'count_ram_missing_bs': count_ram_missing_bs,
		'bs_all': bs_all,

	})



def cmdb_ad_flere_brukeridenter(request):
	#Viser informasjon om personer med mer enn 1 brukerident
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import collections
	ansattnr = []
	relevante_brukere = User.objects.filter(profile__accountdisable=False).filter(Q(profile__distinguishedname__icontains="OU=Eksterne brukere,OU=OK")|Q(profile__distinguishedname__icontains="OU=Brukere,OU=OK"))#.values_list("username", flat=True)
	for anr in relevante_brukere:
		match = re.search(r'(\d{4,})', anr.username, re.I)
		if match:
			ansattnr.append(match[0])

	counter = collections.Counter(ansattnr)
	ansattnr_flere = sorted([{"anr": anr, "count": count} for anr, count in counter.items() if count>1], key=lambda x: x['count'], reverse=True)
	ant_ansattnr_flere = len(ansattnr_flere)

	relevante_brukere = Profile.objects.filter(accountdisable=False).filter(ansattnr_antall__gt=1)

	stat_brukertype = relevante_brukere.values('usertype').annotate(count=Count('usertype')).order_by('-count')

	stat_virksomhet = relevante_brukere.values('virksomhet').annotate(count=Count('virksomhet')).order_by('-count')
	for s in stat_virksomhet:
		if s["count"] > 0:
			s["virksomhet"] = Virksomhet.objects.get(pk=s["virksomhet"])

	stat_ou = relevante_brukere.values('ou').annotate(count=Count('ou')).order_by('-count')
	for s in stat_ou:
		if s["count"] > 0:
			s["ou"] = HRorg.objects.get(pk=s["ou"])

	return render(request, 'cmdb_ad_flere_brukeridenter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ant_ansattnr_unike': ant_ansattnr_flere,
		'ant_ansattnr_totalt': len(relevante_brukere),
		'stat_brukertype': stat_brukertype,
		'stat_virksomhet': stat_virksomhet,
		'stat_ou': stat_ou,
		'raw': ansattnr_flere,
	})


def ad_brukerlistesok(request):
	#Denne funksjonen er for å søke opp mange brukernavn og se informasjon om de det er treff på
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_raw = request.POST.get('user_search_term', '').strip()  # strip removes trailing and leading space
	search_term = search_raw
	users = []
	not_users = []

	search_term = search_term.replace('\"','').replace('\'','').replace(',',' ').replace(';',' ').replace('(',' ').replace(')',' ')
	search_term = search_term.split()

	for term in search_term:
		term_lower = term.lower()
		try:
			user = User.objects.get(Q(username=term_lower) | Q(email__contains=term_lower) | Q(profile__object_sid__iexact=term_lower))
			users.append(user)
		except:
			not_users.append(term_lower)
			continue

	return render(request, 'ad_brukerlistesok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'user_search_term': search_raw,
		'users': users,
		'not_users': not_users,
	})


def get_client_for_graph():
	import os
	from msgraph.core import GraphClient
	from azure.identity import ClientSecretCredential
	client_credential = ClientSecretCredential(
			tenant_id=os.environ['AZURE_TENANT_ID'],
			client_id=os.environ['AZURE_ENTERPRISEAPP_CLIENT'],
			client_secret=os.environ['AZURE_ENTERPRISEAPP_SECRET'],
	)
	api_version = "beta"
	client = GraphClient(credential=client_credential, api_version=api_version)
	return client


def fetch_groups_for_user_id(user_id):
	client = get_client_for_graph()
	query = f"/users/{user_id}/memberOf"
	groups = []
	response = client.get(query)
	data = response.json()
	groups.extend(data.get('value', []))
	next_link = data.get('@odata.nextLink')
	while next_link:
		response = client.get(next_link)
		data = response.json()
		groups.extend(data.get('value', []))
		next_link = data.get('@odata.nextLink')
	return groups


def get_usermetadata_from_spn_or_email(spn_or_email):
	client = get_client_for_graph()
	query = f"/users?$count=true&$filter=startsWith(userPrincipalName, '{spn_or_email}') or onPremisesExtensionAttributes/extensionAttribute2 eq '{spn_or_email.upper()}'"
	resp = client.get(query, headers={'ConsistencyLevel': 'eventual'})
	if resp.status_code == 200:
		return resp.json()
	return False


def auth_kartoteket_group_lookup(username):
	user = get_usermetadata_from_spn_or_email(username)
	if not user:
		print("Auth: fant ingen bruker")
		return False

	if not user["@odata.count"] == 1:
		print("Auth: fant flere brukere")
		return False

	# bare ét treff
	metadata = user["value"][0] # det er bare ét treff, så vi kan ta det første
	#print(metadata)
	groups = fetch_groups_for_user_id(metadata["id"])
	#print(groups)

	relevant_groups = []
	for g in groups:
		if "onPremisesSyncEnabled" in g:
			if g["onPremisesSyncEnabled"]:
				relevant_groups.append(g["mailNickname"])

	#print(relevant_groups)
	return relevant_groups



	client = get_client_for_graph()
	query = f"/users?$count=true$onPremisesExtensionAttributes/extensionAttribute2 eq '{username.upper()}'"
	resp = client.get(query, headers={'ConsistencyLevel': 'eventual'})
	if resp.status_code == 200:
		metadata = json.loads(resp.text)
		if metadata["@odata.count"] == 1:
			metadata = metadata["value"][0] # det er bare ét treff, så vi kan ta det første
			groups = fetch_groups_for_user_id(metadata["id"])
			relevant_groups = []



def entra_id_oppslag(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import re
	inndata = request.POST.get('inndata', "")
	#message = f"{request.user} søkte på: {inndata}."
	inndata = re.sub(r'[^A-Za-z0-9\.\@]', '', inndata) # sørge for at det kun er lovlige tegn

	if inndata != "":
		#ApplicationLog.objects.create(event_type="Azure AD brukersøk", message=message)

		client = get_client_for_graph()
		metadata = get_usermetadata_from_spn_or_email(inndata)

		if metadata:
			if metadata["@odata.count"] == 1:
				metadata = metadata["value"][0] # det er bare ét treff, så vi kan ta det første
				groups = fetch_groups_for_user_id(metadata["id"])
			else:
				messages.info(request, f'Flere treff på: "{inndata}" i Entra ID. Sørg for at det er unikt.')
				metadata = None
				groups = None

		else: # returned False meaning not a 200 OK from server
			messages.info(request, f'Ingen treff på: "{inndata}" i Entra ID.')
			metadata = None
			groups = None

	metadata = metadata if 'metadata' in locals() else None
	groups = groups if 'groups' in locals() else None

	return render(request, 'ad_entraid_oppslag.html', {
		'request': request,
		'metadata': metadata,
		'groups': groups,
		'inndata': inndata,
		'raw_groups': json.dumps(groups, sort_keys=True, indent=4),
		'raw_metadata': json.dumps(metadata, sort_keys=True, indent=4),
	})



def bruker_sok(request):
	#Denne funksjonen utfører søk etter brukere basert på e-post, brukernavn og displayname
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from functools import reduce
	from operator import or_, and_
	#from unidecode import unidecode
	search_term = request.GET.get('search_term', '').replace(","," ").strip().lower()
	# vi ønsker her å søke med AND-operatør mellom alle ord mot displayname, men OR-et med første ordet mot username.
	fields = (
		'profile__displayName__contains',
	)
	parts = []
	terms = search_term.split(" ")
	for term in terms:
		for field in fields:
			parts.append(Q(**{field: term}))

	query_display = reduce(and_, parts)
	username_query = Q(**{'username__contains': terms[0]})
	email_query = Q(**{'email': terms[0]})
	query = reduce(or_, [query_display, username_query, email_query])
	#print(query)

	print(query)

	if len(search_term) > 2:
		users = User.objects.filter(query).distinct()

	else:
		users = User.objects.none()

	return render(request, 'system_brukerdetaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'search_term': search_term,
		'users': users,
	})



def passwdneverexpire(request, pk):
	#Denne funksjonen viser alle personer som har satt passord utløper aldri
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	users = User.objects.filter(profile__virksomhet=virksomhet.pk).filter(profile__usertype__in=["Ansatt", "Ekstern"]).filter(profile__dont_expire_password=True).order_by('profile__displayName')

	return render(request, 'virksomhet_passwordneverexpire.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'users': users,
	})



def ansatte_virksomhet(request, pk):
	#Denne funksjonen viser alle personer i en virksomhet
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from datetime import datetime
	dato = datetime.today().strftime('%Y-%m-%d')

	virksomhet = Virksomhet.objects.get(pk=pk)
	brukere = User.objects.filter(profile__virksomhet=virksomhet, profile__accountdisable=False)

	# relevante grupper knyttet til lisens
	nye_adgrupper = [
		{"gruppe":"Task-OF2-Lisens-O365-G1", "navn": "G1 Standardklient"},
		{"gruppe":"Task-OF2-Lisens-O365-G2", "navn": "G2 Flerbruker"},
		{"gruppe":"Task-OF2-Lisens-O365-G3", "navn": "G3 Uten e-post"},
		{"gruppe":"Task-OF2-Lisens-O365-G4", "navn": "G4 Education"},
		{"gruppe":"Task-OF2-Lisens-O365-G5", "navn": "G5 Beskrivelse?"}
	]

	#bufre alle gruppemedlemmer direkte under nye_adgrupper
	for idx, group in enumerate(nye_adgrupper):
		try:
			adgroup = ADgroup.objects.get(common_name=group["gruppe"])
		except:
			continue

		adgroup_members = json.loads(adgroup.member)
		adgroup_members_clean = set()
		for m in adgroup_members:
			try:
				adgroup_members_clean.add(m.split(",")[0].split("=")[1].lower())
			except:
				pass
		group["adgroup_members_clean"] = list(adgroup_members_clean)

	# slå opp for hver bruker ny lisens
	for bruker in brukere:
		match = False
		for group in nye_adgrupper:
			try:
				members = group["adgroup_members_clean"]
			except:
				members = [] # skjer dersom gruppen ikke finnes
			if bruker.username.lower() in members:
				bruker.ny365lisens = group["navn"]
				match = True
				break
		if not match:
			bruker.ny365lisens = "-"

	return render(request, 'virksomhet_ansatte_virksomhet.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'brukere': brukere,
		'dato': dato,
	})



def tom_epost(request, pk):
	#Denne funksjonen viser alle personer som har passordutløp kommende periode
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	count_brukere_i_virksomhet = User.objects.filter(profile__virksomhet=virksomhet, profile__accountdisable=False, profile__account_type__in=['Ekstern', 'Intern']).count()
	brukere_uten_epost = User.objects.filter(email="", profile__virksomhet=virksomhet, profile__accountdisable=False, profile__account_type__in=['Ekstern', 'Intern'])

	return render(request, 'virksomhet_tom_epost.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'count_brukere_i_virksomhet': count_brukere_i_virksomhet,
		'brukere_uten_epost': brukere_uten_epost,
	})


def cmdb_uten_epost_stat(request):
	#Denne funksjonen viser alle personer som har passordutløp kommende periode
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	stats = []
	totalt_uten_epost = 0
	totalt_antall_brukere = 0

	for virksomhet in Virksomhet.objects.all():

		if virksomhet.virksomhetsforkortelse == "DRIFT":
			continue # hopp over

		brukere_i_virksomhet = User.objects.filter(profile__virksomhet=virksomhet, profile__accountdisable=False, profile__account_type__in=['Ekstern', 'Intern']).count()
		brukere_uten_epost = User.objects.filter(email="", profile__virksomhet=virksomhet, profile__accountdisable=False, profile__account_type__in=['Ekstern', 'Intern']).count()

		totalt_uten_epost += brukere_uten_epost
		totalt_antall_brukere += brukere_i_virksomhet

		try:
			andel_brukere_i_virksomhet = round(100*brukere_uten_epost / brukere_i_virksomhet)
		except:
			andel_brukere_i_virksomhet = None

		stats.append(
				{
					"virksomhet": virksomhet,
					"brukere_i_virksomhet": brukere_i_virksomhet,
					"brukere_uten_epost": brukere_uten_epost,
					"andel_brukere_i_virksomhet": andel_brukere_i_virksomhet,
				}
			)

	return render(request, 'cmdb_uten_epost_stat.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'stats': stats,
		'totalt_uten_epost': totalt_uten_epost,
		'totalt_antall_brukere': totalt_antall_brukere,
	})


def passwordexpire(request, pk):
	#Denne funksjonen viser alle personer som har passordutløp kommende periode
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	periode = 14 ## dager
	innaktiv = 182 ## dager
	now = timezone.now()
	virksomhet = Virksomhet.objects.get(pk=pk)

	if request.GET.get('alt') == "ja":
		users = User.objects.filter(profile__userPasswordExpiry__gte=now)
	else:
		users = User.objects.filter(profile__virksomhet=pk)

	users = users.filter(profile__usertype__in=["Ansatt", "Ekstern"]).filter(profile__accountdisable=False).filter(profile__userPasswordExpiry__lte=now+datetime.timedelta(days=periode)).order_by('profile__userPasswordExpiry')

	for u in users:
		if u.profile.lastLogonTimestamp:
			if u.profile.lastLogonTimestamp < (now - datetime.timedelta(days=innaktiv)):
				u.inactive = True
			else:
				u.inactive = False
		else:
			u.inactive = False

		if u.profile.userPasswordExpiry < now:
			u.expired = True
		else:
			u.expired = False

	return render(request, 'virksomhet_passwordexpire.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'users': users,
		'periode': periode,
		'innaktiv': innaktiv,
	})



def bruker_detaljer(request, pk):
	#Denne funksjonen viser detaljer om en bruker lastet inn i kartoteket
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	user = User.objects.get(pk=pk)
	return render(request, 'system_brukerdetaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'users': [user],
	})



def lokasjoner_hos_virksomhet(request, pk):
	required_permissions = ['systemoversikt.view_virksomhet']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	lokasjoner = WANLokasjon.objects.filter(virksomhet=virksomhet)
	return render(request, 'virksomhet_lokasjoner.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'lokasjoner': lokasjoner,
	})



def klienter_hos_virksomhet(request, pk):
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	alle_klienter_hos_virksomhet = CMDBdevice.objects.filter(client_virksomhet=virksomhet).filter(~Q(client_last_loggedin_user=None))

	return render(request, 'virksomhet_klientoversikt.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'alle_klienter_hos_virksomhet': alle_klienter_hos_virksomhet,
	})



def virksomhet_leverandortilgang(request, pk=None):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if pk == None:
		raise Http404

	virksomhet = Virksomhet.objects.get(pk=pk)
	relevante_grupper = list()

	levprofiler = Leverandortilgang.objects.all()
	for profile in levprofiler:
		for system in profile.systemer.all():
			if system.systemforvalter == virksomhet:
				relevante_grupper.extend(profile.adgrupper.all())

	users = list()
	for gruppe in relevante_grupper:
		users.extend(json.loads(gruppe.member))

	users = list(set(users)) # sørger for unike personer
	member = human_readable_members(users)

	return render(request, 'virksomhet_leverandortilgang.html', {
		'show_access_groups': False,
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'member': member,
	})



def virksomhet_sikkerhetsavvik(request, pk=None):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if pk == None:
		try:
			pk = request.user.profile.virksomhet.pk
		except:
			pass

	virksomhet = Virksomhet.objects.get(pk=pk)
	logg = ""

	def hent_brukere(grupper, logg):
		brukerliste = set()
		for g in grupper:
			try:
				gruppe = ADgroup.objects.get(common_name=g)
				members = json.loads(gruppe.member)
				for m in members:
					username = m.split(",")[0].split("=")[1]
					if virksomhet.virksomhetsforkortelse in username:
						logg += "la til %s " % (username)
						brukerliste.add(username)
				if len(brukerliste) > 500:
					#print("For mange brukere")
					return (["Over 500 personer"], "")
			except:
				logg = "" # deaktivert # += "feilet for %s " % (g)
				#print("fant ikke gruppen %s" % g)

		brukerliste = [b.lower() for b in brukerliste]
		brukerobjekter = User.objects.filter(username__in=brukerliste)
		return (brukerobjekter, logg)

	#Grupper for å gi EM+S E5-lisens
	grupper_med_emse5 = [
		"DS-OFFICE365_OPSJON_E5SECURITY",
	]
	brukere_med_emse5, logg = hent_brukere(grupper_med_emse5, logg)

	#Grupper for å unnta fra krav om kjent enhet
	grupper_ikke_administrert = [
		"DS-OFFICE365_OPSJON_IKKEADMINISTRERT",
		"DS-OFFICE365E5S_OPSJON_IKKEADMINISTRERT",
		"DS-OFFICE365SVC_UNNTAK_KJENTENHET"
	]
	brukere_ikke_administrert, logg = hent_brukere(grupper_ikke_administrert, logg)

	#unntak MFA
	grupper_unntak_mfa = [
		"DS-OFFICE365SVC_UNNTAK_MFA",
	]
	brukere_unntak_mfa, logg = hent_brukere(grupper_unntak_mfa, logg)

	#unntak innenfor EU
	grupper_utenfor_eu = [
		"DS-OFFICE365SVC_UNNTAK_EUROPEISKIP",
		"DS-OFFICE365SPES_UNNTAK_EUROPEISKIP",
	]
	brukere_utenfor_eu, logg = hent_brukere(grupper_utenfor_eu, logg)

	grupper_hoyrisikoland = [
		"DS-OFFICE365SPES_UNNTAK_HOYRISIKO",
	]
	brukere_hoyrisikoland, logg = hent_brukere(grupper_hoyrisikoland, logg)

	#opptak
	grupper_med_opptak = [
		"DS-OFFICE365SPES_OPPTAK_OPPTAK",
	]
	brukere_med_opptak, logg = hent_brukere(grupper_med_opptak, logg)

	grupper_med_liveevent = [
		"DS-OFFICE365SPES_LIVEEVENT_LIVEEVENT",
	]
	brukere_med_liveevent, logg = hent_brukere(grupper_med_liveevent, logg)

	#spesialroller
	grupper_omraadeadm = [
		"DS-OFFICE365SPES_OMRAADEADM_OMRAADEADM",
	]
	brukere_omraadeadm, logg = hent_brukere(grupper_omraadeadm, logg)
	for user in brukere_omraadeadm:
		if user in brukere_ikke_administrert:
			user.avvik_kjent_enhet = True
		else:
			user.avvik_kjent_enhet = False

	grupper_gjestegodk = [
		"DS-OFFICE365SPES_OMRAADEADM_GJESTEGODK",
	]
	brukere_gjestegodk, logg = hent_brukere(grupper_gjestegodk, logg)

	grupper_gruppeadm = [
		"DS-OFFICE365SPES_OMRAADEADM_GRUPPEOPPRETTER",
	]
	brukere_gruppeadm, logg = hent_brukere(grupper_gruppeadm, logg)

	grupper_byod_vpn = [
		"DS-FJARB_OF20_SA_LISENS",
	]
	brukere_byod_vpn, logg = hent_brukere(grupper_byod_vpn, logg)

	grupper_filefullcontrol_applomr = [
		"DS-File-FullControl-Alle-%s-ApplOmr" % (virksomhet.virksomhetsforkortelse),
	]
	brukere_filefullcontrol_applomr, logg = hent_brukere(grupper_filefullcontrol_applomr, logg)

	grupper_filefullcontrol_fellesomr = [
		"DS-File-FullControl-Alle-%s-FellesOmr" % (virksomhet.virksomhetsforkortelse),
	]
	brukere_filefullcontrol_fellesomr, logg = hent_brukere(grupper_filefullcontrol_fellesomr, logg)

	grupper_filefullcontrol_hjemmeomr = [
		"DS-File-FullControl-Alle-%s-HomeFolders" % (virksomhet.virksomhetsforkortelse),
	]
	brukere_filefullcontrol_hjemmeomr, logg = hent_brukere(grupper_filefullcontrol_hjemmeomr, logg)

	grupper_lokalskriver_is = [
		"DS-%s_APP_KLIENT_LOCALPRINT" % (virksomhet.virksomhetsforkortelse),
	]
	brukere_lokalskriver_is, logg = hent_brukere(grupper_lokalskriver_is, logg)

	grupper_lokalskriver_ss = [
		"DS-%s_APP_KLIENT_LOCALPRINTSS" % (virksomhet.virksomhetsforkortelse),
	]
	brukere_lokalskriver_ss, logg = hent_brukere(grupper_lokalskriver_ss, logg)

	grupper_usb_tykklient = [
		"DS-%s_APP_KLIENT_USBAKSESSTYKK" % (virksomhet.virksomhetsforkortelse),
		"DS-%s_APP_KLIENT_USBACCESSTYKK" % (virksomhet.virksomhetsforkortelse),

	]
	brukere_usb_tykklient, logg = hent_brukere(grupper_usb_tykklient, logg)

	grupper_usb_tynnklient = [
		"DS-%s_APP_KLIENT_USBAKSESSTYNN" % (virksomhet.virksomhetsforkortelse),
		"DS-%s_APP_KLIENT_USBACCESSTYNN" % (virksomhet.virksomhetsforkortelse),
	]
	brukere_usb_tynnklient, logg = hent_brukere(grupper_usb_tynnklient, logg)

	grupper_lokal_administrator = [
		"DS-%s_APP_SUPPORT_LOKAL_ADMINISTRATOR" % (virksomhet.virksomhetsforkortelse),
		"DS-SIKKERHETKLIENT_LOKALADMIN_ADMINKLIENT",
	]
	brukere_lokal_administrator, logg = hent_brukere(grupper_lokal_administrator, logg)

	grupper_nettleserutvidelser = [
		"DS-SIKKERHETKLIENT_NETTLESERUTVIDELSER_INSTALLNETTLE",
	]
	brukere_nettleserutvidelser, logg = hent_brukere(grupper_nettleserutvidelser, logg)

	return render(request, 'virksomhet_sikkerhetsavvik.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'grupper_med_emse5': grupper_med_emse5,
		'brukere_med_emse5': brukere_med_emse5,
		'grupper_uten_administrert_klient': grupper_ikke_administrert,
		'brukere_uten_administrert_klient': brukere_ikke_administrert,
		'grupper_unntak_mfa': grupper_unntak_mfa,
		'brukere_unntak_mfa': brukere_unntak_mfa,
		'grupper_utenfor_eu': grupper_utenfor_eu,
		'brukere_utenfor_eu': brukere_utenfor_eu,
		'grupper_hoyrisikoland': grupper_hoyrisikoland,
		'brukere_hoyrisikoland': brukere_hoyrisikoland,
		'grupper_med_opptak': grupper_med_opptak,
		'brukere_med_opptak': brukere_med_opptak,
		'grupper_med_liveevent': grupper_med_liveevent,
		'brukere_med_liveevent': brukere_med_liveevent,
		'grupper_omraadeadm': grupper_omraadeadm,
		'brukere_omraadeadm': brukere_omraadeadm,
		'grupper_gjestegodk': grupper_gjestegodk,
		'brukere_gjestegodk': brukere_gjestegodk,
		'grupper_gruppeadm': grupper_gruppeadm,
		'brukere_gruppeadm': brukere_gruppeadm,
		'grupper_byod_vpn': grupper_byod_vpn,
		'brukere_byod_vpn': brukere_byod_vpn,
		'grupper_filefullcontrol_applomr': grupper_filefullcontrol_applomr,
		'brukere_filefullcontrol_applomr': brukere_filefullcontrol_applomr,
		'grupper_filefullcontrol_fellesomr': grupper_filefullcontrol_fellesomr,
		'brukere_filefullcontrol_fellesomr': brukere_filefullcontrol_fellesomr,
		'grupper_filefullcontrol_hjemmeomr': grupper_filefullcontrol_hjemmeomr,
		'brukere_filefullcontrol_hjemmeomr': brukere_filefullcontrol_hjemmeomr,
		'grupper_lokalskriver_is': grupper_lokalskriver_is,
		'brukere_lokalskriver_is': brukere_lokalskriver_is,
		'grupper_lokalskriver_ss': grupper_lokalskriver_ss,
		'brukere_lokalskriver_ss': brukere_lokalskriver_ss,
		'grupper_usb_tykklient': grupper_usb_tykklient,
		'brukere_usb_tykklient': brukere_usb_tykklient,
		'grupper_usb_tynnklient': grupper_usb_tynnklient,
		'brukere_usb_tynnklient': brukere_usb_tynnklient,
		'grupper_lokal_administrator': grupper_lokal_administrator,
		'brukere_lokal_administrator': brukere_lokal_administrator,
		'grupper_nettleserutvidelser': grupper_nettleserutvidelser,
		'brukere_nettleserutvidelser': brukere_nettleserutvidelser,
		'logging': logg,
	})



def minside(request):
	#Når innlogget, vise informasjon om innlogget bruker
	required_permissions = None
	try:
		oidctoken = request.session['oidc-token']
	except:
		oidctoken = "OIDC er ikke i bruk"

	if request.user.is_authenticated:
		return render(request, 'site_minside.html', {
			'request': request,
			'required_permissions': formater_permissions(required_permissions),
			'oidctoken': oidctoken,
		})
	else:
		return redirect("/")



def dashboard_all(request, virksomhet=None):
	# UTFASET
	#Generere virksomhets dashboard med statistikk over systmemer
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	try:
		virksomhet = Virksomhet.objects.get(pk=virksomhet)
	except:
		raise Http404("Virksomhet med angitt ID finnes ikke.")

	alle_virksomheter = Virksomhet.objects.all()

	systemer_drifter = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet).filter(~Q(ibruk=False)).order_by('systemnavn')
	systemer_eier = System.objects.filter(systemeier=virksomhet).filter(~Q(ibruk=False)).order_by('systemnavn')
	systemer_forvalter = System.objects.filter(systemforvalter=virksomhet).filter(~Q(ibruk=False)).order_by('systemnavn')
	systemer_felles = System.objects.filter(systemeierskapsmodell="FELLESSYSTEM").filter(~Q(ibruk=False)).order_by('systemnavn')

	alle_relevante_behandlinger = behandlingsprotokoll(virksomhet)

	systemer_behandler_i = []
	for behandling in alle_relevante_behandlinger:
		for system in behandling.systemer.all():
			if system not in systemer_behandler_i:
				systemer_behandler_i.append(system.pk)
	systemer_behandler_i = System.objects.filter(pk__in=systemer_behandler_i).order_by('systemnavn')

	antall_systemer_uten_driftsmodell = len(System.objects.filter(driftsmodell_foreignkey=None).filter(~Q(ibruk=False)).all())

	def systemeierPerVirksomhet(systemer):
		#print(type(systemer))
		resultat = []
		for virksomhet in alle_virksomheter:
			resultat.append(systemer.filter(systemeier=virksomhet).count())
		resultat.append(systemer.filter(systemeier=None).count())
		return resultat

	def systemforvalterPerVirksomhet(systemer):
		resultat = []
		for virksomhet in alle_virksomheter:
			resultat.append(systemer.filter(systemforvalter=virksomhet).count())
		resultat.append(systemer.filter(systemforvalter=None).count())
		return resultat

	def statusRoS(systemer):
		minus_six_months = datetime.date.today() - datetime.timedelta(days=182)
		minus_twelve_months = minus_six_months - datetime.timedelta(days=183)

		ros_seks_mnd_siden = systemer.filter(dato_sist_ros__gt=minus_six_months).count()
		ros_et_aar_siden = systemer.filter(dato_sist_ros__gt=minus_twelve_months).filter(dato_sist_ros__lte=minus_six_months).count()
		ros_gammel = systemer.filter(dato_sist_ros__lte=minus_twelve_months).count()
		ros_mangler_prioritert = systemer.filter(Q(dato_sist_ros=None) & Q(risikovurdering_behovsvurdering=2)).count()
		ros_mangler_ikke_prioritert = systemer.filter(Q(dato_sist_ros=None) & Q(risikovurdering_behovsvurdering=1)).count()
		ros_ikke_behov = systemer.filter(Q(dato_sist_ros=None) & Q(risikovurdering_behovsvurdering=0)).count() # 0 er "Ikke behov / inngår i annet systems risikovurdering"
		return [ros_ikke_behov,ros_seks_mnd_siden,ros_et_aar_siden,ros_gammel,ros_mangler_prioritert,ros_mangler_ikke_prioritert]

	def statusDPIA(systemer):
		#['Utført', 'Ikke utført', 'Ikke behov',]
		dpia_ok = systemer.filter(~Q(DPIA_for_system=None)).count()
		dpia_mangler = systemer.filter(Q(DPIA_for_system=None))
		dpia_ikke_behov = 0
		for system in dpia_mangler:
			behandlinger = BehandlingerPersonopplysninger.objects.filter(systemer=system)
			behandlinger.filter(hoy_personvernrisiko=True)
			if behandlinger.count() > 0:
				dpia_ikke_behov += 1
		dpia_mangler_antall = dpia_mangler.count()
		return [dpia_ok, dpia_mangler_antall - dpia_ikke_behov, dpia_ikke_behov]

	def statusSikkerhetsnivaa(systemer):
		#['Gradert', 'Sikret', 'Internt', 'Eksternt', 'Ukjent']
		gradert = systemer.filter(sikkerhetsnivaa=4).count()
		sikret = systemer.filter(sikkerhetsnivaa=3).count()
		internt = systemer.filter(sikkerhetsnivaa=2).count()
		eksternt = systemer.filter(sikkerhetsnivaa=1).count()
		ukjent = systemer.filter(sikkerhetsnivaa=None).count()
		return [gradert,sikret,internt,eksternt,ukjent]

	def statusTjenestenivaa(systemer):
		kritikalitet = []
		for s in systemer:
			kritikalitet.append(s.fip_kritikalitet())

		t_one = sum(x == 1 for x in kritikalitet)
		t_two = sum(x == 2 for x in kritikalitet)
		t_tree = sum(x == 3 for x in kritikalitet)
		t_four = sum(x == 4 for x in kritikalitet)
		t_unknown = sum(x == None for x in kritikalitet)
		#['T1', 'T2', 'T3', 'T4','Ukjent']
		return [t_one,t_two,t_tree,t_four,t_unknown]

	def statusKvalitet(systemer):
		kvalitetssikret = systemer.filter(informasjon_kvalitetssikret=True).count()
		ikke = systemer.filter(informasjon_kvalitetssikret=False).count()
		return[kvalitetssikret, ikke]

	def statusLivslop(systemer):
		anskaffelse = systemer.filter(livslop_status=1).count()
		nytt = systemer.filter(livslop_status=2).count()
		moderne = systemer.filter(livslop_status=3).count()
		modent = systemer.filter(livslop_status=4).count()
		byttes = systemer.filter(livslop_status=5).count()
		ukjent = systemer.filter(livslop_status=None).count()
		return [anskaffelse,nytt,moderne,modent,byttes,ukjent]

	systemlister = [
		{
			"id": "systemer_eier",
			"beskrivelse": "Systemer angitt med valgt virksomhet som eier.",
			"tittel": "Systemer %s eier" % virksomhet.virksomhetsforkortelse,
			"systemer": systemer_eier,
			"systemeiere_per_virksomhet": systemeierPerVirksomhet(systemer_eier),
			"systemforvaltere_per_virksomhet":systemforvalterPerVirksomhet(systemer_eier),
			"status_ros": statusRoS(systemer_eier),
			"status_dpia": statusDPIA(systemer_eier),
			"status_sikkerhetsnivaa": statusSikkerhetsnivaa(systemer_eier),
			"status_tjenestenivaa": statusTjenestenivaa(systemer_eier),
			'status_kvalitetssikret': statusKvalitet(systemer_eier),
			'status_livslop': statusLivslop(systemer_eier),
		},
		{
			"id": "systemer_forvalter",
			"beskrivelse": "Systemer angitt med valgt virksomhet som forvalter.",
			"tittel": "Systemer %s forvalter" % virksomhet.virksomhetsforkortelse,
			"systemer": systemer_forvalter,
			"systemeiere_per_virksomhet": systemeierPerVirksomhet(systemer_forvalter),
			"systemforvaltere_per_virksomhet": systemforvalterPerVirksomhet(systemer_forvalter),
			"status_ros": statusRoS(systemer_forvalter),
			"status_dpia": statusDPIA(systemer_forvalter),
			"status_sikkerhetsnivaa": statusSikkerhetsnivaa(systemer_forvalter),
			"status_tjenestenivaa": statusTjenestenivaa(systemer_forvalter),
			'status_kvalitetssikret': statusKvalitet(systemer_forvalter),
			'status_livslop': statusLivslop(systemer_forvalter),
		},
		{
			"id": "systemer_behandler_i",
			"beskrivelse": "Systemer virksomheten har registrert behandling på direkte, samt systemer virksomheten har registrert bruk av (git at abonnering av behandlinger er aktivert).",
			"tittel": "Systemer %s behandler personopplysninger i" % virksomhet.virksomhetsforkortelse,
			"systemer": systemer_behandler_i,
			"systemeiere_per_virksomhet": systemeierPerVirksomhet(systemer_behandler_i),
			"systemforvaltere_per_virksomhet": systemforvalterPerVirksomhet(systemer_behandler_i),
			"status_ros": statusRoS(systemer_behandler_i),
			"status_dpia": statusDPIA(systemer_behandler_i),
			"status_sikkerhetsnivaa": statusSikkerhetsnivaa(systemer_behandler_i),
			"status_tjenestenivaa": statusTjenestenivaa(systemer_behandler_i),
			'status_kvalitetssikret': statusKvalitet(systemer_behandler_i),
			'status_livslop': statusLivslop(systemer_behandler_i),
		},
		{
			"id": "systemer_drifter",
			"beskrivelse": "Systemer angitt med en driftsplattform forvaltet av valgt virksomhet. Merk at det er %s systemer uten angivelse av driftsplattform." % (antall_systemer_uten_driftsmodell),
			"tittel": "Systemer %s drifter" % (virksomhet.virksomhetsforkortelse),
			"systemer": systemer_drifter,
			"systemeiere_per_virksomhet": systemeierPerVirksomhet(systemer_drifter),
			"systemforvaltere_per_virksomhet": systemforvalterPerVirksomhet(systemer_drifter),
			"status_ros": statusRoS(systemer_drifter),
			"status_dpia": statusDPIA(systemer_drifter),
			"status_sikkerhetsnivaa": statusSikkerhetsnivaa(systemer_drifter),
			"status_tjenestenivaa": statusTjenestenivaa(systemer_drifter),
			'status_kvalitetssikret': statusKvalitet(systemer_drifter),
			'status_livslop': statusLivslop(systemer_drifter),

		},
		{
			"id": "systemer_felles",
			"beskrivelse": "Systemer angitt som fellessystemer",
			"tittel": "Fellessystemer (hele Oslo kommune)",
			"systemer": systemer_felles,
			"systemeiere_per_virksomhet": systemeierPerVirksomhet(systemer_felles),
			"systemforvaltere_per_virksomhet": systemforvalterPerVirksomhet(systemer_felles),
			"status_ros": statusRoS(systemer_felles),
			"status_dpia": statusDPIA(systemer_felles),
			"status_sikkerhetsnivaa": statusSikkerhetsnivaa(systemer_felles),
			"status_tjenestenivaa": statusTjenestenivaa(systemer_felles),
			'status_kvalitetssikret': statusKvalitet(systemer_felles),
			'status_livslop': statusLivslop(systemer_felles),
		},
	]

	return render(request, 'virksomhet_dashboard.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemlister': systemlister,
		'alle_virksomheter': alle_virksomheter,
		'virksomhet': virksomhet,
	})



def ansvarlig_bytte(request):
	required_permissions = ['systemoversikt.change_ansvarlig']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	str_ansvarlig_fra = request.POST.get('ansvarlig_fra', '')
	str_ansvarlig_til = request.POST.get('ansvarlig_til', '')

	try:
		bruker_fra = User.objects.get(username=str_ansvarlig_fra)
		ansvarlig_fra = Ansvarlig.objects.get(brukernavn=bruker_fra)
	except:
		ansvarlig_fra = None

	try:
		bruker_til = User.objects.get(username=str_ansvarlig_til)
		try:
			ansvarlig_til = Ansvarlig.objects.get(brukernavn=bruker_til)
		except:
			# det kan hende personen ikke allerede er opprettet som ansvarlig, så da gjør vi det her
			ansvarlig_til = Ansvarlig.objects.create(brukernavn=bruker_til)
	except:
		ansvarlig_til = None

	if ansvarlig_fra == None or ansvarlig_til == None:
		feilmelding = "Et eller begge feltene inneholder et ugyldig brukernavn"
	else:
		feilmelding = ""

	resultat = []

	if ansvarlig_fra != None and ansvarlig_til != None and ansvarlig_fra != ansvarlig_til:

		# her lister vi først ut alle felter på Ansvarlig-klassen som er av typen mange-til-mange eller fremmednøkkel.
		m2m_relations = []
		fk_relations = []
		detaljert_logg = ""

		for f in Ansvarlig._meta.get_fields(include_hidden=False):
			if f.get_internal_type() in ["ManyToManyField"]:
				m2m_relations.append(f)
			if f.get_internal_type() in ["ForeignKey"]:
				fk_relations.append(f)

		#field
		#model
		#related_name
		#related_model

		for m2mr in m2m_relations:
			for obj in getattr(ansvarlig_fra, m2mr.name).all():
				object_field = getattr(obj, m2mr.field.name)
				object_field.remove(ansvarlig_fra)
				object_field.add(ansvarlig_til)
				melding = ("Fjernet %s og la til %s på %s %s" % (ansvarlig_fra, ansvarlig_til, obj.__class__.__name__, obj))
				detaljert_logg += ("%s %s, " % (obj.__class__.__name__, obj))
				resultat.append(melding)

		for fkr in fk_relations:
			for obj in getattr(ansvarlig_fra, fkr.name).all():
				setattr(obj, fkr.field.name, ansvarlig_til)
				obj.save()
				melding = ("Fjernet %s og la til %s på %s %s" % (ansvarlig_fra, ansvarlig_til, obj.__class__.__name__, obj))
				detaljert_logg += ("%s %s, " % (obj.__class__.__name__, obj))
				resultat.append(melding)

		logg_entry_message = "%s har overført alt ansvar fra %s til %s for %s" % (request.user, ansvarlig_fra, ansvarlig_til, detaljert_logg)

		ApplicationLog.objects.create(
				event_type='Overføring av ansvar',
				message=logg_entry_message,
			)
	else:
		resultat = None

	return render(request, "ansvarlig_bytte.html", {
		'request': request,
		'required_permissions': required_permissions,
		'str_ansvarlig_fra': str_ansvarlig_fra,
		'str_ansvarlig_til': str_ansvarlig_til,
		'ansvarlig_fra': ansvarlig_fra,
		'ansvarlig_til': ansvarlig_til,
		'resultat': resultat,
	})


"""
def user_clean_up(request):
	#Denne funksjonen er laget for å slette/anonymisere data i testmiljøet.
	required_permissions = ['auth.change_permission']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if settings.DEBUG == True:  # Testmiljø
		from django.contrib.auth.models import User
		for user in User.objects.all():
			try:
				user.delete()
			except:
				print("Kan ikke slette bruker %s. Forsøker å anonymisere" % user)

			anonymous_firstname = ("First-" + user.username[:3])
			user.first_name = anonymous_firstname
			anonymous_lastname = ("Last-" + user.username[3:])
			user.last_name = anonymous_lastname
			user.save()
	else:
		print("Du får ikke kjøre denne kommandoen i produksjon!")

	return render(request, "site_home.html", {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})
"""



def permissions(request):
	#viser informasjon om alle ansvarliges aktive rettigheter
	required_permissions = ['systemoversikt.change_ansvarlig']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	ansvarlige = Ansvarlig.objects.all()
	return render(request, 'site_permissions.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ansvarlige': ansvarlige,
	})



def roller(request):
	required_permissions = None
	from django.core import serializers
	from django.contrib.auth.models import Group
	groups = Group.objects.all()
	if request.GET.get('export') == "json":
		export = []
		for g in groups:
			unique_permissions = []
			for p in g.permissions.all():
				unique_permissions.append({"content_type__app_label": p.content_type.app_label, "codename": p.codename})
			export.append({"group": g.name, "permissions": unique_permissions})

		return JsonResponse(export, safe=False)
	else:
		header = []
		grupper_med_rettigheter = {}
		for g in groups:
			header.append(g.name.split("/DS-SYSTEMOVERSIKT_")[1].replace("_", " "))
			grupper_med_rettigheter[g.name] = [p.codename for p in g.permissions.all()]

		unique_permissions = list(set([ x for y in grupper_med_rettigheter.values() for x in y]))
		unique_permissions = sorted(unique_permissions)

		matrise = {}
		for key in unique_permissions:
			matrise[key] = [ True if key in rettigheter else False for gruppe, rettigheter in grupper_med_rettigheter.items() ]

		return render(request, 'site_roller.html', {
			'request': request,
			'required_permissions': formater_permissions(required_permissions),
			'header': header,
			'matrise': matrise,
	})



def logger(request):
	#viser alle endringer på objekter i løsningen
	required_permissions = ['admin.view_logentry']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	aktive_antall_uker = 2
	aktive_antall_personer = 10
	period = datetime.datetime.now() - datetime.timedelta(weeks=aktive_antall_uker)
	top_users = LogEntry.objects.filter(action_time__gte=period).values('user_id').annotate(count=Count('user_id')).order_by('-count')[:aktive_antall_personer]
	user_ids = [entry['user_id'] for entry in top_users]
	users = User.objects.filter(id__in=user_ids)
	top_endringer = []
	for user, entry in zip(users, top_users):
		top_endringer.append({"user": user, "email": user.email, "count": entry['count']})


	antall_vist = 500
	recent_admin_loggs = LogEntry.objects.order_by('-action_time')[:antall_vist]
	return render(request, 'site_audit_logger.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'recent_admin_loggs': recent_admin_loggs,
		'antall_vist': antall_vist,
		'top_endringer': top_endringer,
		'aktive_antall_uker': aktive_antall_uker,
		'aktive_antall_personer': aktive_antall_personer,

	})



def logger_audit(request):
	#viser alle endringer på objekter i løsningen
	required_permissions = ['systemoversikt.view_applicationlog']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	recent_loggs = ApplicationLog.objects.filter(~Q(event_type__icontains="api")).filter(~Q(event_type__icontains="Brukerpålogging")).order_by('-opprettet')[:1500]
	return render(request, 'site_logger_audit.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'recent_loggs': recent_loggs,
	})



def databasestatistikk(request):
	#viser størrelse på alle tabeller i databasefilen
	required_permissions = ['systemoversikt.view_applicationlog']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import os
	database_file = settings.DATABASES['default']['NAME']
	file_size = os.stat(database_file).st_size
	query = f'sqlite3 {database_file} "SELECT name, SUM(pgsize) AS size FROM dbstat GROUP BY name ORDER BY -size;" ".exit"'
	data = os.popen(query).read()
	data = data.splitlines()
	sum_size = 0.0
	stats = []

	for line in data:
		line = line.strip()
		name = line.split("|")[0]
		size = float(line.split("|")[1])
		sum_size += size
		stats.append({"name": name, "size": size})

	return render(request, 'site_databasestatistikk.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'stats': stats,
		'file_size': file_size,
		'sum_size': sum_size,
	})



#def logger_api_csirt(request):
#	#viser der cisrt-spørringer feiler
#	required_permissions = ['systemoversikt.view_applicationlog']
#	if not any(map(request.user.has_perm, required_permissions)):
#		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })
#
#	try:
#		siste_kjoring = ApplicationLog.objects.filter(event_type__icontains="API CSIRT").last().opprettet
#		time_delta = siste_kjoring - datetime.timedelta(hours=1)
#		recent_loggs = ApplicationLog.objects.filter(event_type__icontains="API CSIRT").filter(message__icontains="Ingen treff").filter(opprettet__gte=time_delta).order_by('-opprettet')
#	except:
#		recent_loggs = None
#
#	return render(request, 'site_logger_audit.html', {
#		'request': request,
#		'required_permissions': formater_permissions(required_permissions),
#		'recent_loggs': recent_loggs,
#	})



def logger_api(request):
	#viser alle endringer på objekter i løsningen
	required_permissions = ['systemoversikt.view_applicationlog']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	recent_loggs = ApplicationLog.objects.filter(event_type__icontains="api").order_by('-opprettet')[:5000]
	return render(request, 'site_logger_audit.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'recent_loggs': recent_loggs,
	})



def logger_autentisering(request):
	#viser alle endringer på objekter i løsningen
	required_permissions = ['systemoversikt.view_applicationlog']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	recent_loggs = ApplicationLog.objects.filter(event_type__icontains="Brukerpålogging").order_by('-opprettet')[:1500]
	return render(request, 'site_logger_audit.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'recent_loggs': recent_loggs,
	})



def logger_users(request):
	#viser selektive endringer på brukere/ansvarlige i løsningen
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	recent_loggs = UserChangeLog.objects.order_by('-opprettet')[:800]
	return render(request, 'site_logger_users.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'recent_loggs': recent_loggs,
	})



def alle_nyheter(request):
	required_permissions = None
	nyheter = NyeFunksjoner.objects.all().order_by('-tidspunkt')
	return render(request, 'system_nyheter_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'nyheter': nyheter,
	})



def home(request):
	#Startsiden med oversikt over systemer per kategori
	required_permissions = None
	antall_systemer = System.objects.filter(~Q(ibruk=False)).count()
	nyeste_systemer = System.objects.filter(~Q(ibruk=False)).order_by('-pk')[:10]
	antall_programvarer = Programvare.objects.count()
	nyeste_programvarer = Programvare.objects.order_by('-pk')[:10]
	antall_behandlinger = BehandlingerPersonopplysninger.objects.count()
	kategorier = SystemKategori.objects.all()
	nyheter = NyeFunksjoner.objects.all().order_by('-tidspunkt')[:10]

	return render(request, 'site_home.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'kategorier': kategorier,
		'antall_systemer': antall_systemer,
		'nyeste_systemer': nyeste_systemer,
		'antall_programvarer': antall_programvarer,
		'nyeste_programvarer': nyeste_programvarer,
		'antall_behandlinger': antall_behandlinger,
		'nyheter': nyheter,
	})



def home_chart(request):
	#Startsiden med oversikt over systemer per kategori
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	nodes = []
	parents = []

	def systemnavn_forkortet(system):
		maximum = 20
		if len(system.systemnavn) > maximum:
			return system.systemnavn[:maximum]
		return system.systemnavn

	def system_virksomhet(system, parents):
		if system.systemforvalter:
			parents.append(system.systemforvalter.virksomhetsnavn)
			return system.systemforvalter.virksomhetsnavn

		parents.append('Ingen')
		return 'Ingen'

	antall_graph_noder = 0
	for system in System.objects.all().order_by('systemnavn'):
		if not system.er_ibruk():
			continue

		if system.er_integrasjon():
			continue

		if system.er_infrastruktur():
			continue

		antall_graph_noder += 1
		nodes.append({
			'data': {
				'id': system.pk,
				'name': systemnavn_forkortet(system),
				'parent': system_virksomhet(system, parents),
				'shape': 'rectangle',
				'color': system.color(),
				'href': f'/systemer/detaljer/{system.pk}/',
			}
		})

	for p in set(parents):
		nodes.append(
			{'data':
				{'id': p,
				#'parent': virksomhet.virksomhetsforkortelse,
				'color': 'white'
				}
			},
		)

	node_size = 350 + 8*antall_graph_noder
	if node_size > 1920:
		node_size = 1920

	virksomheter = Virksomhet.objects.filter(ordinar_virksomhet=True)

	return render(request, 'site_home_chart.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'nodes': nodes,
		'node_size': node_size,
		'system_colors': SYSTEM_COLORS,
		'virksomheter': virksomheter,
	})


def alle_definisjoner(request):
	#Viser definisjoner
	required_permissions = None
	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space

	if (search_term == ""):
		definisjoner = Definisjon.objects.all()

	elif len(search_term) < 2: # if one or less, return nothing
		definisjoner = Definisjon.objects.none()

	else:
		definisjoner = Definisjon.objects.filter(
				Q(begrep__icontains=search_term) |
				Q(engelsk_begrep__icontains=search_term) |
				Q(definisjon__icontains=search_term) |
				Q(eksempel__icontains=search_term) |
				Q(legaldefinisjon__icontains=search_term)
		)
	definisjoner.order_by('begrep')

	return render(request, 'definisjon_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'definisjoner': definisjoner,
		'search_term': search_term,
	})



def definisjon(request, begrep):
	#Viser en definisjon
	required_permissions = None
	passende_definisjoner = Definisjon.objects.filter(begrep=begrep)
	return render(request, 'definisjon_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'begrep': begrep,
		'definisjoner': passende_definisjoner,
	})



def tjenestekatalogen_forvalter_api(request):
	#Dette er et API for å hente ut alle systemforvaltere.
	#Brukere: Tjenestekatalogen til UKE
	if request.method == "GET":

		key = request.headers.get("key", None)
		allowed_keys = APIKeys.objects.filter(navn="itas_tjenestekatalog").values_list("key", flat=True)
		if key in list(allowed_keys):

			owner = APIKeys.objects.get(key=key).navn
			ApplicationLog.objects.create(event_type="Forvalter-API", message="Brukt av %s" %(owner))

			forvaltere_eksport = []
			for ansvarlig in Ansvarlig.objects.all():

				forvalter_for = []
				for system in ansvarlig.system_systemforvalter_kontaktpersoner.all():
					if system.ibruk:
						forvalter_for.append({
								"system_id": system.pk,
								"system_navn": system.systemnavn,
								"system_alias": system.alias,
								"system_eier_virksomhet_kort": system.systemeier.virksomhetsforkortelse if system.systemeier else None,
								"system_eier_virksomhet": system.systemeier.virksomhetsnavn if system.systemeier else None,
								"system_forvalter_virksomhet_kort": system.systemforvalter.virksomhetsforkortelse if system.systemforvalter else None,
								"system_forvalter_virksomhet": system.systemforvalter.virksomhetsnavn if system.systemforvalter else None,
							})

				eier_av = []
				for system in ansvarlig.system_systemeier_kontaktpersoner.all():
					if system.ibruk:
						eier_av.append({
								"system_id": system.pk,
								"system_navn": system.systemnavn,
								"system_alias": system.alias,
								"system_eier_virksomhet_kort": system.systemeier.virksomhetsforkortelse if system.systemeier else None,
								"system_eier_virksomhet": system.systemeier.virksomhetsnavn if system.systemeier else None,
								"system_forvalter_virksomhet_kort": system.systemforvalter.virksomhetsforkortelse if system.systemforvalter else None,
								"system_forvalter_virksomhet": system.systemforvalter.virksomhetsnavn if system.systemforvalter else None,
							})

				if len(forvalter_for) < 1 and len(eier_av) < 1:  # begge er tomme
					continue  # hopp til neste person

				forvaltere_eksport.append({
					"brukernavn": ansvarlig.brukernavn.username,
					"fornavn": ansvarlig.brukernavn.first_name,
					"etternavn": ansvarlig.brukernavn.last_name,
					"epost": ansvarlig.brukernavn.email,
					#profil opprettes automatisk, så dette er trygt
					"visningsnavn": ansvarlig.brukernavn.profile.displayName,
					"prkid": ansvarlig.brukernavn.profile.ansattnr,
					"virksomhet_kort": ansvarlig.brukernavn.profile.virksomhet.virksomhetsforkortelse if ansvarlig.brukernavn.profile.virksomhet else None,
					"virksomhet": ansvarlig.brukernavn.profile.virksomhet.virksomhetsnavn if ansvarlig.brukernavn.profile.virksomhet else None,
					"orgenhet": ansvarlig.brukernavn.profile.org_unit.ou if ansvarlig.brukernavn.profile.org_unit else None,
					"forvalter_for": forvalter_for,
					"eier_av": eier_av,
					})

			data = {"message": "OK", "data": forvaltere_eksport}
			return JsonResponse(data, safe=False)

		else:
			return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False,status=403)
	else:
		raise Http404



def tjenestekatalogen_systemer_api(request):
	#Dette er et API for å hente ut alle systemforvaltere.
	#Brukere: Tjenestekatalogen til UKE
	if request.method == "GET":

		key = request.headers.get("key", None)
		allowed_keys = APIKeys.objects.filter(navn="itas_tjenestekatalog").values_list("key", flat=True)
		if key in list(allowed_keys):

			owner = APIKeys.objects.get(key=key).navn
			ApplicationLog.objects.create(event_type="Forvalter-API", message="Brukt av %s" %(owner))

			systemer_eksport = []
			for system in System.objects.all():

				systemeiere = []
				for eier in system.systemeier_kontaktpersoner_referanse.all():
					systemeiere.append({
							"pk": eier.pk,
							"full_name": eier.brukernavn.profile.displayName if eier.brukernavn.profile else None,
							"email": eier.brukernavn.email,
							"virksomhet": eier.brukernavn.profile.virksomhet.virksomhetsnavn if eier.brukernavn.profile.virksomhet else None,
						})
				systemer_eksport.append({
						"pk": system.pk,
						"systemnavn": system.systemnavn,
						"ibruk": system.ibruk,
						"systembeskrivelse": system.systembeskrivelse,
						"systemeier_kontaktpersoner_referanse": systemeiere,
					})

			data = {"message": "OK", "data": systemer_eksport}
			return JsonResponse(data, safe=False)

		else:
			return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False,status=403)
	else:
		raise Http404



def ansvarlig(request, pk):
	#Viser informasjon om en ansvarlig
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	ansvarlig = Ansvarlig.objects.get(pk=pk)
	if not ansvarlig.brukernavn.is_active:
		messages.warning(request, 'Denne brukeren er deaktivert!')

	systemeier_for = System.objects.filter(~Q(ibruk=False)).filter(systemeier_kontaktpersoner_referanse=pk)
	systemforvalter_for = System.objects.filter(~Q(ibruk=False)).filter(systemforvalter_kontaktpersoner_referanse=pk)
	systemforvalter_bruk_for = SystemBruk.objects.filter(systemforvalter_kontaktpersoner_referanse=pk)
	kam_for = Virksomhet.objects.filter(uke_kam_referanse=pk)
	avtale_ansvarlig_for = Avtale.objects.filter(avtaleansvarlig=pk)
	ikt_kontakt_for = Virksomhet.objects.filter(ikt_kontakt=pk)
	sertifikatbestiller_for = Virksomhet.objects.filter(autoriserte_bestillere_sertifikater__person=pk)
	virksomhetsleder_for = Virksomhet.objects.filter(leder=pk)
	autorisert_bestiller_for = Virksomhet.objects.filter(autoriserte_bestillere_tjenester=pk)
	personvernkoordinator_for = Virksomhet.objects.filter(personvernkoordinator=pk)
	informasjonssikkerhetskoordinator_for = Virksomhet.objects.filter(informasjonssikkerhetskoordinator=pk)
	behandlinger_for = BehandlingerPersonopplysninger.objects.filter(oppdateringsansvarlig=pk)
	definisjonsansvarlig_for = Definisjon.objects.filter(ansvarlig=pk)
	system_innsynskontakt_for = System.objects.filter(kontaktperson_innsyn=pk)
	autorisert_bestiller_uke_for = Virksomhet.objects.filter(autoriserte_bestillere_tjenester_uke=pk)
	programvarebruk_kontakt_for = ProgramvareBruk.objects.filter(lokal_kontakt=pk)
	kompass_godkjent_bestiller_for = System.objects.filter(godkjente_bestillere=pk)

	return render(request, 'ansvarlig_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ansvarlig': ansvarlig,
		'systemeier_for': systemeier_for,
		'systemforvalter_for': systemforvalter_for,
		'systemforvalter_bruk_for': systemforvalter_bruk_for,
		'kam_for': kam_for,
		'avtale_ansvarlig_for': avtale_ansvarlig_for,
		'ikt_kontakt_for': ikt_kontakt_for,
		'sertifikatbestiller_for': sertifikatbestiller_for,
		'virksomhetsleder_for': virksomhetsleder_for,
		'autorisert_bestiller_for': autorisert_bestiller_for,
		'personvernkoordinator_for': personvernkoordinator_for,
		'informasjonssikkerhetskoordinator_for': informasjonssikkerhetskoordinator_for,
		'behandlinger_for': behandlinger_for,
		'definisjonsansvarlig_for': definisjonsansvarlig_for,
		'system_innsynskontakt_for': system_innsynskontakt_for,
		'autorisert_bestiller_uke_for': autorisert_bestiller_uke_for,
		'programvarebruk_kontakt_for': programvarebruk_kontakt_for,
		'kompass_godkjent_bestiller_for': kompass_godkjent_bestiller_for,
	})



def alle_ansvarlige(request):
	#Viser informasjon om alle ansvarlige
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	ansvarlige = Ansvarlig.objects.all().order_by('brukernavn__first_name')

	return render(request, 'ansvarlig_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ansvarlige': ansvarlige,
		'suboverskrift': "Hele kommunen",
	})



def alle_ansvarlige_eksport(request):
	#Viser informasjon om alle ansvarlige
	required_permissions = ['systemoversikt.change_ansvarlig']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	ansvarlige = Ansvarlig.objects.filter(brukernavn__is_active=True)

	return render(request, 'ansvarlig_eksport.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ansvarlige': ansvarlige,
	})



def systemkvalitet_virksomhet(request, pk):
	#Viser informasjon om datakvalitet per system
	required_permissions = ['systemoversikt.view_virksomhet']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	systemer_ansvarlig_for = System.objects.filter(Q(systemeier=pk) | Q(systemforvalter=pk)).order_by(Lower('systemnavn'))

	return render(request, 'virksomhet_hvamangler.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'systemer': systemer_ansvarlig_for,
	})



def systemer_vurderinger(request):
	#Vise alle systemvurderinger
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	systemer = System.objects.all()

	return render(request, 'systemer_vurderinger.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
	})


def systemer_EOL(request):
	#EOS-visning for felles IKT-plattform
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=163)
	driftsmodeller = Driftsmodell.objects.filter(ansvarlig_virksomhet=virksomhet)
	alle_systemer = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet).filter(livslop_status__in=[5,6])

	systemer = []
	infrastruktur = []

	for s in alle_systemer:
		if s.er_infrastruktur() == True:
			infrastruktur.append(s)
		else:
			systemer.append(s)

	return render(request, 'systemer_EOL_vurderinger_FIP.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
		'infrastruktur': infrastruktur,
	})


def systemdetaljer(request, pk):
	#Viser detaljer om et system
	#Tilgangsstyring: Merk at noen informasjonselementer er begrenset i template
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	system = System.objects.get(pk=pk)

	follow_count = int(request.GET.get("follow_count", 0))

	def generer_graf_ny(system, follow_count):
		avhengigheter_graf = {"nodes": [], "edges": []}
		observerte_driftsmodeller = set()
		first_round = True
		follow_count = follow_count
		observerte_systemer = set()
		behandlede_systemer = set()
		aktivt_nivaa_systemer = set()  # aktiv runde
		neste_nivaa = set() # neste runde (nye ting vi ser i aktiv runde)

		def parent(system):
			if system.driftsmodell_foreignkey is not None:
				return f"drift_{system.driftsmodell_foreignkey.pk}"
			else:
				return "Ukjent"

		def systemfarge(self):
			if self.er_infrastruktur():
				return "gray"
			else:
				return "#dca85a"

		# initielt oppsett, registrere dette systemet som en node
		aktivt_nivaa_systemer.add(system)
		observerte_systemer.add(system)

		def avhengighetsrunde(aktivt_nivaa_systemer, neste_nivaa):
			for aktuelt_system in aktivt_nivaa_systemer:

				avhengigheter_graf["nodes"].append({"data": {
							"id": aktuelt_system.pk,
							"parent": parent(aktuelt_system),
							"name": aktuelt_system.systemnavn,
							"shape": "ellipse",
							"color": "#C63D3D"
						}},)
				observerte_driftsmodeller.add(aktuelt_system.driftsmodell_foreignkey)

				for s in aktuelt_system.system_integration_source.all():
					integrasjon = s
					s = s.destination_system
					if s not in observerte_systemer:
						neste_nivaa.add(s)
						observerte_systemer.add(s)
					if s not in behandlede_systemer:
						avhengigheter_graf["nodes"].append({"data": { "id": s.pk, "parent": parent(s), "name": s.systemnavn, "shape": "ellipse", "color": integrasjon.color(), "href": reverse('systemdetaljer', args=[s.pk]) }},)
						avhengigheter_graf["edges"].append({"data": { "source": aktuelt_system.pk, "target": s.pk, 'linewidth': 2, 'curve-style': 'bezier', "linecolor": integrasjon.color(), "linestyle": "solid" }},)
						observerte_driftsmodeller.add(s.driftsmodell_foreignkey)

				if first_round:
					for s in aktuelt_system.system_integration_destination.all():
						integrasjon = s
						s = s.source_system
						if s not in observerte_systemer:
							neste_nivaa.add(s)
							observerte_systemer.add(s)
						if s not in behandlede_systemer:
							avhengigheter_graf["nodes"].append({"data": { "id": s.pk, "parent": parent(s), "name": s.systemnavn, "shape": "ellipse", "color": integrasjon.color(), "href": reverse('systemdetaljer', args=[s.pk]) }},)
							avhengigheter_graf["edges"].append({"data": { "source": s.pk, "target": aktuelt_system.pk, 'linewidth': 1, 'curve-style': 'bezier', "linecolor": integrasjon.color(), "linestyle": "dashed" }},)
							observerte_driftsmodeller.add(s.driftsmodell_foreignkey)

				behandlede_systemer.add(aktuelt_system)

			# legger neste nivås systemer inn i gjendende nivå, klar for neste runde
			aktivt_nivaa_systemer = neste_nivaa
			neste_nivaa = set()

			return aktivt_nivaa_systemer, neste_nivaa

		aktivt_nivaa_systemer, neste_nivaa = avhengighetsrunde(aktivt_nivaa_systemer, neste_nivaa)
		first_round = False
		while follow_count > 0 and aktivt_nivaa_systemer: # det må være noen systemer å gå igjennom..
			aktivt_nivaa_systemer, neste_nivaa = avhengighetsrunde(aktivt_nivaa_systemer, neste_nivaa)
			follow_count-=1

		# legge til alle driftsmodeller som ble funnet
		for driftsmodell in observerte_driftsmodeller:
			if driftsmodell is not None:
				if driftsmodell.overordnet_plattform:
					avhengigheter_graf["nodes"].append({"data": { "id": f"drift_{driftsmodell.pk}", "name": driftsmodell.navn, "parent": f"drift_{driftsmodell.overordnet_plattform.pk}" }},)
					avhengigheter_graf["nodes"].append({"data": { "id": f"drift_{driftsmodell.overordnet_plattform.pk}", "name": driftsmodell.overordnet_plattform.navn }},)
				else:
					avhengigheter_graf["nodes"].append({"data": { "id": f"drift_{driftsmodell.pk}", "name": driftsmodell.navn }},)

		return avhengigheter_graf



	def generer_graf(system, follow_count):
		avhengigheter_graf = {"nodes": [], "edges": []}
		observerte_driftsmodeller = set()
		first_round = True
		follow_count = follow_count
		observerte_systemer = set()
		behandlede_systemer = set()
		aktivt_nivaa_systemer = set()  # aktiv runde
		neste_nivaa = set() # neste runde (nye ting vi ser i aktiv runde)

		def parent(system):
			if system.driftsmodell_foreignkey is not None:
				return system.driftsmodell_foreignkey.navn
			else:
				return "Ukjent"

		def systemfarge(self):
			if self.er_infrastruktur():
				return "gray"
			else:
				return "#dca85a"

		# initielt oppsett, registrere dette systemet som en node
		aktivt_nivaa_systemer.add(system)
		observerte_systemer.add(system)

		def avhengighetsrunde(aktivt_nivaa_systemer, neste_nivaa):
			for aktuelt_system in aktivt_nivaa_systemer:

				avhengigheter_graf["nodes"].append({"data": { "parent": parent(aktuelt_system), "id": aktuelt_system.pk, "name": aktuelt_system.systemnavn, "shape": "ellipse", "color": "black" }},)
				observerte_driftsmodeller.add(aktuelt_system.driftsmodell_foreignkey)

				if first_round: # bare første runde. De etterkommende rundene ignorerer vi systemer som avleverer informasjon til dette systemet.
					mottar_fra = set()  # et set har kun unike verdier
					for s in aktuelt_system.datautveksling_mottar_fra.all():
						mottar_fra.add(s)
					for s in aktuelt_system.system_datautveksling_avleverer_til.all():
						mottar_fra.add(s)
					for s in mottar_fra:
						if s not in observerte_systemer:
							neste_nivaa.add(s)
							observerte_systemer.add(s)
						if s not in behandlede_systemer:
							avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": systemfarge(s), "href": reverse('systemdetaljer', args=[s.pk]) }},)
							avhengigheter_graf["edges"].append({"data": { "source": s.pk, "target": aktuelt_system.pk, "linestyle": "solid" }},)
							observerte_driftsmodeller.add(s.driftsmodell_foreignkey)

				if first_round: # bare første runde. Vi må skille på utlevering og avhengighet
					avleverer_til = set()  # et set har kun unike verdier
					for s in aktuelt_system.datautveksling_avleverer_til.all():
						avleverer_til.add(s)
					for s in aktuelt_system.system_datautveksling_mottar_fra.all():
						avleverer_til.add(s)
					for s in avleverer_til:
						if s not in observerte_systemer:
							neste_nivaa.add(s)
							observerte_systemer.add(s)
						if s not in behandlede_systemer:
							avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": systemfarge(s), "href": reverse('systemdetaljer', args=[s.pk]) }},)
							avhengigheter_graf["edges"].append({"data": { "source": aktuelt_system.pk, "target": s.pk, "linestyle": "solid" }},)
							observerte_driftsmodeller.add(s.driftsmodell_foreignkey)

				# Dette er systemer dette systemet er avhengig av, kjøres uansett runde
				for s in aktuelt_system.avhengigheter_referanser.all():
					if s not in observerte_systemer:
						neste_nivaa.add(s)
						observerte_systemer.add(s)
					if s not in behandlede_systemer:
						avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": systemfarge(s), "href": reverse('systemdetaljer', args=[s.pk]) }},)
						avhengigheter_graf["edges"].append({"data": { "source": aktuelt_system.pk, "target": s.pk, "linestyle": "dashed" }},)
						observerte_driftsmodeller.add(s.driftsmodell_foreignkey)

				#dette er systemer som er avhengig av gitt system
				if first_round:
					for s in aktuelt_system.system_avhengigheter_referanser.all():
						if s not in observerte_systemer:
							neste_nivaa.add(s)
							observerte_systemer.add(s)
						if s not in behandlede_systemer:
							avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": systemfarge(s), "href": reverse('systemdetaljer', args=[s.pk]) }},)
							avhengigheter_graf["edges"].append({"data": { "source": s.pk, "target": aktuelt_system.pk, "linestyle": "dashed" }},)
							observerte_driftsmodeller.add(s.driftsmodell_foreignkey)

				# programvare knyttet til dette systemet, bare første runde
				if first_round:
					for p in aktuelt_system.programvarer.all():
						avhengigheter_graf["nodes"].append({"data": { "id": ("p%s" % p.pk), "name": p.programvarenavn, "shape": "ellipse", "color": "#64c14c", "href": reverse('programvaredetaljer', args=[p.pk]) }},)
						avhengigheter_graf["edges"].append({"data": { "source": aktuelt_system.pk, "target": ("p%s" % p.pk), "linestyle": "dashed" }},)

				behandlede_systemer.add(aktuelt_system)

			# legger neste nivås systemer inn i gjendende nivå, klar for neste runde
			aktivt_nivaa_systemer = neste_nivaa
			neste_nivaa = set()

			return aktivt_nivaa_systemer, neste_nivaa

		aktivt_nivaa_systemer, neste_nivaa = avhengighetsrunde(aktivt_nivaa_systemer, neste_nivaa)
		first_round = False
		while follow_count > 0 and aktivt_nivaa_systemer: # det må være noen systemer å gå igjennom..
			aktivt_nivaa_systemer, neste_nivaa = avhengighetsrunde(aktivt_nivaa_systemer, neste_nivaa)
			follow_count-=1

		# legge til alle driftsmodeller som ble funnet
		for driftsmodell in observerte_driftsmodeller:
			if driftsmodell is not None:
				avhengigheter_graf["nodes"].append({"data": { "id": driftsmodell.navn }},)

		return avhengigheter_graf




	siste_endringer_antall = 10
	system_content_type = ContentType.objects.get_for_model(system)
	siste_endringer = LogEntry.objects.filter(content_type=system_content_type).filter(object_id=pk).order_by('-action_time')[:siste_endringer_antall]

	systembruk = SystemBruk.objects.filter(system=pk).filter(ibruk=True).order_by("brukergruppe")
	behandlinger = BehandlingerPersonopplysninger.objects.filter(systemer=pk).order_by("funksjonsomraade")
	try:
		dpia = DPIA.objects.get(for_system=pk)
	except:
		dpia = None

	hoy_risiko = behandlinger.filter(hoy_personvernrisiko=True)

	# "avleverer til" fra et annet system tilsvarer "mottar fra" dette systemet
	datautveksling_mottar_fra = [i.source_system for i in SystemIntegration.objects.filter(personopplysninger=True,destination_system=system.pk).all()]
	datautveksling_avleverer_til = [i.destination_system for i in SystemIntegration.objects.filter(personopplysninger=True,source_system=system.pk).all()]
	avhengigheter_reverse_systemer = System.objects.filter(avhengigheter_referanser=pk)

	avhengigheter_graf = generer_graf(system, follow_count)

	avhengigheter_graf_ny = generer_graf_ny(system, follow_count)

	citrix_apps = system.citrix_publications.all()
	for app in citrix_apps:
		app.publikasjon_json = json.loads(app.publikasjon_json)

	current_user_is_owner = True if request.user.username in system.eiere() else False
	if request.user.groups.filter(name='/DS-SYSTEMOVERSIKT_SAARBARHETSOVERSIKT_SIKKERHETSANALYTIKER').exists():
		current_user_is_owner = True

	try:
		integrasjonsstatus = IntegrasjonKonfigurasjon.objects.get(informasjon__icontains="qualys")
	except:
		integrasjonsstatus = None

	return render(request, 'system_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemdetaljer': system,
		'systembruk': systembruk,
		'behandlinger': behandlinger,
		'datautveksling_mottar_fra': datautveksling_mottar_fra,
		'datautveksling_avleverer_til': datautveksling_avleverer_til,
		'avhengigheter_reverse_systemer': avhengigheter_reverse_systemer,
		'hoy_risiko': hoy_risiko,
		'dpia': dpia,
		'siste_endringer': siste_endringer,
		'siste_endringer_antall': siste_endringer_antall,
		'avhengigheter_graf': avhengigheter_graf,
		'avhengigheter_graf_ny': avhengigheter_graf_ny,
		'follow_count': follow_count,
		'avhengigheter_chart_size': 300 + len(avhengigheter_graf["nodes"])*20,
		'avhengigheter_chart_size_ny': 300 + len(avhengigheter_graf_ny["nodes"])*20,
		'citrix_apps': citrix_apps,
		'current_user_is_owner': current_user_is_owner,
		'integrasjonsstatus': integrasjonsstatus,
	})



def systemer_pakket(request):
	#Uferdig: vising av hvordan applikasjoner er pakket
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	systemer = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=163)  # 163=UKE
	programvarer = Programvare.objects.all()
	return render(request, 'system_hvordan_pakket.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
		'programvarer': programvarer,
	})



def systemklassifisering_detaljer(request, kriterie=None):
	#Vise systemer filtrert basert på systemeierskapsmodell (felles, sektor, virksomhet)
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if kriterie == None:
		kriterie = "FELLESSYSTEM_OBLIGATORISK"

	if kriterie == "__NONE__":
		utvalg_systemer = System.objects.filter(~Q(ibruk=False)).filter(systemeierskapsmodell=None)
		kriterie = "uten verdi"
	else:
		utvalg_systemer = System.objects.filter(~Q(ibruk=False)).filter(systemeierskapsmodell=kriterie)

	from systemoversikt.models import SYSTEMEIERSKAPSMODELL_VALG
	systemtyper = Systemtype.objects.all()

	return render(request, 'system_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'overskrift': ("Systemer der systemklassifisering er %s" % kriterie.lower()),
		'systemer': utvalg_systemer,
		'kommuneklassifisering': SYSTEMEIERSKAPSMODELL_VALG,
		'systemtyper': systemtyper,
	})



def systemtype_detaljer(request, pk=None):
	#Vise systemer filtrert basert på systemtype (web/app/infrastruktur osv.)
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if pk:
		utvalg_systemer = System.objects.filter(systemtyper=pk)
		systemtype_navn = Systemtype.objects.get(pk=pk).kategorinavn
		overskrift = ("Systemer av typen %s" % systemtype_navn.lower())
	else:
		utvalg_systemer = System.objects.filter(systemtyper=None)
		overskrift = "Systemer som mangler systemtype"

	from systemoversikt.models import SYSTEMEIERSKAPSMODELL_VALG
	systemtyper = Systemtype.objects.all()

	utvalg_systemer = utvalg_systemer.filter(livslop_status__in=[1,2,3,4,5]).order_by('ibruk', Lower('systemnavn'))
	return render(request, 'system_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'overskrift': overskrift,
		'systemer': utvalg_systemer,
		'kommuneklassifisering': SYSTEMEIERSKAPSMODELL_VALG,
		'systemtyper': systemtyper,
	})



def alle_systemer_forvaltere(request):
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	systemer = System.objects.all()

	return render(request, 'system_forvalteroversikt.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
	})



def alle_systemer_smart(request):
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	systemer = System.objects.all() #filter(driftsmodell_foreignkey__ansvarlig_virksomhet=163)  # 163=UKE

	return render(request, 'system_smart.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
	})



def alle_systemer(request):
	#Vise alle systemer
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('vis', 'fellessystem').strip()  # strip removes trailing and leading space
	aktuelle_systemer = System.objects.filter()
	aktuelle_systemer = aktuelle_systemer.order_by('-ibruk', Lower('systemnavn'))

	from systemoversikt.models import SYSTEMEIERSKAPSMODELL_VALG
	systemtyper = Systemtype.objects.all()

	return render(request, 'system_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': aktuelle_systemer,
		'kommuneklassifisering': SYSTEMEIERSKAPSMODELL_VALG,
		'systemtyper': systemtyper,
		'overskrift': ("Systemer"),
	})



def search(request):
	#Vise alle systemer
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space

	try:
		v = Virksomhet.objects.get(virksomhetsforkortelse__iexact=search_term)
		return redirect('virksomhet', v.pk)
	except:
		pass

	if len(search_term) > 4: # det er noen få brukernavn som er identiske med systemnavn..
		try:
			u = User.objects.get(username__iexact=search_term)
			return redirect('bruker_detaljer', u.pk)
		except:
			pass

	if search_term != '':
		aktuelle_systemer = System.objects.filter(~Q(livslop_status=7)).filter(Q(systemnavn__icontains=search_term)|Q(alias__icontains=search_term))
		#Her ønsker vi å vise treff i beskrivelsesfeltet, men samtidig ikke vise systemer på nytt
		potensielle_systemer = System.objects.filter(~Q(livslop_status=7)).filter(Q(systembeskrivelse__icontains=search_term) & ~Q(pk__in=aktuelle_systemer))
		aktuelle_programvarer = Programvare.objects.filter(Q(programvarenavn__icontains=search_term)|Q(alias__icontains=search_term))
		domenetreff = SystemUrl.objects.filter(domene__icontains=search_term)
		aktuelle_leverandorer = Leverandor.objects.filter(leverandor_navn__icontains=search_term)
		aktuelle_personer = User.objects.filter(username__iexact=search_term)
		business_services = CMDBRef.objects.filter(navn__icontains=search_term)
		aktuelle_adgrupper = ADgroup.objects.filter(common_name__icontains=search_term)
	else:
		aktuelle_systemer = System.objects.none()
		potensielle_systemer = System.objects.none()
		aktuelle_programvarer = Programvare.objects.none()
		domenetreff = SystemUrl.objects.none()
		aktuelle_leverandorer = Leverandor.objects.none()
		business_services = CMDBRef.objects.none()
		aktuelle_adgrupper = ADgroup.objects.none()

	if (len(aktuelle_systemer) == 1) and (len(aktuelle_programvarer) == 0) and (len(domenetreff) == 0):  # bare ét systemtreff og ingen programvaretreff.
		return redirect('systemdetaljer', aktuelle_systemer[0].pk)

	aktuelle_systemer = aktuelle_systemer.order_by('-ibruk', Lower('systemnavn'))
	potensielle_systemer = potensielle_systemer.order_by('ibruk', Lower('systemnavn'))
	aktuelle_programvarer.order_by(Lower('programvarenavn'))
	domenetreff.order_by(Lower('domene'))
	aktuelle_adgrupper.order_by(Lower('common_name'))

	from systemoversikt.models import SYSTEMEIERSKAPSMODELL_VALG
	systemtyper = Systemtype.objects.all()

	return render(request, 'site_search.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': aktuelle_systemer,
		'potensielle_systemer': potensielle_systemer,
		'search_term': search_term,
		'domenetreff': domenetreff,
		'aktuelle_programvarer': aktuelle_programvarer,
		'aktuelle_leverandorer': aktuelle_leverandorer,
		'business_services': business_services,
		'aktuelle_adgrupper': aktuelle_adgrupper,
	})



def bruksdetaljer(request, pk):
	#Vise detaljer om systembruk
	required_permissions = ['systemoversikt.view_behandlingerpersonopplysninger']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	bruk = SystemBruk.objects.get(pk=pk)

	return render(request, 'systembruk_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'bruk': bruk,
	})



def mine_systembruk(request):
	#Redirect for å sende bruker til detaljer om innlogget brukers virksomhets systembruk
	required_permissions = None

	try:
		brukers_virksomhet = virksomhet_til_bruker(request)
		pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
		return redirect('all_bruk_for_virksomhet', pk)
	except:
		messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
		return redirect('alle_virksomheter')



def all_bruk_for_virksomhet(request, pk):
	#Vise detaljer om en valgt virksomhets systembruk
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet_pk = pk
	all_systembruk = SystemBruk.objects.filter(brukergruppe=virksomhet_pk, ibruk=True).exclude(system__livslop_status__in=[6,7]).order_by(Lower('system__systemnavn'))  # sortering er ellers case-sensitiv
	ikke_i_bruk = SystemBruk.objects.filter(brukergruppe=virksomhet_pk).filter(system__livslop_status__in=[6,7]).order_by(Lower('system__systemnavn'))  # sortering er ellers case-sensitiv

	# ser ut til at excel 2016+ støtter dette..
	for bruk in all_systembruk:
		ant = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=virksomhet_pk).filter(systemer=bruk.system.pk).count()
		bruk.antall_behandlinger = ant

	try:
		virksomhet = Virksomhet.objects.get(pk=pk)
	except:
		messages.warning(request, 'Fant ingen virksomhet med denne ID-en.')
		virksomhet = Virksomhet.objects.none()

	all_programvarebruk = ProgramvareBruk.objects.filter(brukergruppe=virksomhet_pk).order_by(Lower('programvare__programvarenavn'))
	for bruk in all_programvarebruk:
		ant = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=virksomhet_pk).filter(programvarer=bruk.programvare.pk).count()
		bruk.antall_behandlinger = ant


	eier_eller_forvalter = set(System.objects.filter(Q(systemeier=virksomhet_pk) or Q(systemforvalter=virksomhet_pk)))  #{1, 2, 3, 4} #systemer virksomhet eier liste
	systembruk = set(SystemBruk.objects.filter(brukergruppe=virksomhet_pk)) # {3, 4} #systemer virksomhet bruker liste
	systemer_ibruk = []
	for b in systembruk:
		systemer_ibruk.append(b.system)
	systemer_ibruk = set(systemer_ibruk)

	#print([s.id for s in systemer_ibruk])
	#print([s.id for s in eier_eller_forvalter])
	mangler_bruk = eier_eller_forvalter - systemer_ibruk
	#print([s.id for s in mangler_bruk])

	return render(request, 'systembruk_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'all_systembruk': all_systembruk,
		'all_programvarebruk': all_programvarebruk,
		'ikke_i_bruk': ikke_i_bruk,
		'virksomhet': virksomhet,
		'mangler_bruk': mangler_bruk,
	})



def registrer_bruk(request, system):
	#Forenklet metode for å legge til bruk av system ved avkryssing
	required_permissions = ['systemoversikt.add_systembruk']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from django.core.exceptions import ObjectDoesNotExist
	system_instans = System.objects.get(pk=system)
	alle_virksomheter = list(Virksomhet.objects.all())

	if request.POST:
		virksomheter = request.POST.getlist("virksomheter", "")
		for str_virksomhet in virksomheter:
			virksomhet = Virksomhet.objects.get(pk=int(str_virksomhet))
			alle_virksomheter.remove(virksomhet)
			try:
				bruk = SystemBruk.objects.get(brukergruppe=virksomhet, system=system_instans)
				if bruk.ibruk == False:
					bruk.ibruk = True
					bruk.save()
					#print("Satt %s aktiv" % bruk)
			except ObjectDoesNotExist:
				bruk = SystemBruk.objects.create(
					brukergruppe=virksomhet,
					system=system_instans,
					ibruk=True,
				)
				#print("Opprettet %s" % bruk)
		for virk in alle_virksomheter: # alle som er igjen, ble ikke merket, merk som ikke i bruk
			try:
				bruk = SystemBruk.objects.get(system=system_instans, brukergruppe=virk)
				if bruk.ibruk == True:
					bruk.ibruk = False
					bruk.save()
					#print("Satt %s deaktiv" % bruk)
			except ObjectDoesNotExist:
				pass # trenger ikke sette et ikke-eksisterende objekt
		return redirect('systemdetaljer', system_instans.pk)

	virksomheter_template = list()
	for virk in Virksomhet.objects.all():
		try:
			bruk = SystemBruk.objects.get(system=system_instans, brukergruppe=virk, ibruk=True)
			virksomheter_template.append({"virksomhet": virk, "bruk": bruk})
		except:
			virksomheter_template.append({"virksomhet": virk, "bruk": None})

	return render(request, 'system_registrer_bruk.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'target': system_instans,
		'target_name': system_instans.systemnavn,
		'back_link': reverse('systemdetaljer', args=[system_instans.pk]),
		'virksomheter_template': virksomheter_template,
	})



def registrer_bruk_programvare(request, programvare):
	#Forenklet metode for å legge til bruk av programvare ved avkryssing
	required_permissions = ['systemoversikt.add_programvarebruk']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from django.core.exceptions import ObjectDoesNotExist
	programvare_instans = Programvare.objects.get(pk=programvare)
	alle_virksomheter = list(Virksomhet.objects.all())

	if request.POST:
		virksomheter = request.POST.getlist("virksomheter", "")
		for str_virksomhet in virksomheter:
			virksomhet = Virksomhet.objects.get(pk=int(str_virksomhet))
			alle_virksomheter.remove(virksomhet)
			try:
				bruk = ProgramvareBruk.objects.get(brukergruppe=virksomhet, programvare=programvare_instans)
				if bruk.ibruk == False:
					bruk.ibruk = True
					bruk.save()
					#print("Satt %s aktiv" % bruk)
			except ObjectDoesNotExist:
				bruk = ProgramvareBruk.objects.create(
					brukergruppe=virksomhet,
					programvare=programvare_instans,
					ibruk=True,
				)
				#print("Opprettet %s" % bruk)
		for virk in alle_virksomheter: # alle som er igjen, ble ikke merket, merk som ikke i bruk
			try:
				bruk = ProgramvareBruk.objects.get(programvare=programvare_instans, brukergruppe=virk)
				if bruk.ibruk == True:
					bruk.ibruk = False
					bruk.save()
					#print("Satt %s deaktiv" % bruk)
			except ObjectDoesNotExist:
				pass # trenger ikke sette et ikke-eksisterende objekt
		return redirect('programvaredetaljer', programvare_instans.pk)

	virksomheter_template = list()
	for virk in Virksomhet.objects.filter(ordinar_virksomhet=True):
		try:
			bruk = ProgramvareBruk.objects.get(programvare=programvare_instans, brukergruppe=virk, ibruk=True)
			virksomheter_template.append({"virksomhet": virk, "bruk": bruk})
		except:
			virksomheter_template.append({"virksomhet": virk, "bruk": None})

	return render(request, 'system_registrer_bruk.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'target': programvare_instans,
		'target_name': programvare_instans.programvarenavn,
		'back_link': reverse('programvaredetaljer', args=[programvare_instans.pk]),
		'virksomheter_template': virksomheter_template,
	})



def rapport_named_locations(request):

	required_permissions = None
	color_table = []
	color_table_display = []
	color_table.append(['Land', 'Fargekode'])

	def populate(named_location_id, color_code, color_name): # 1 is green, 2 is yellow, 3 is red and 4 is black
		named_location = AzureNamedLocations.objects.get(ipNamedLocation_id=named_location_id)
		for country in json.loads(named_location.countriesAndRegions):
			#print(country)
			color_table.append([{"v": country["code"], "f": country["name"]}, color_code])
			color_table_display.append({"land": country["name"], "farge": color_name})

	data = [
		{"named_location_id": '141f4101-6ea0-4cd0-9c6e-2b57e868876f', "color_code": 1, "color_name": "grønn"}, # grønn
		{"named_location_id": '1b0ee1ab-e197-45bf-b48c-c05999613ea8', "color_code": 2, "color_name": "gul"}, # gul
		{"named_location_id": '1c5daa1a-f370-4512-9078-bf81159ee7b2', "color_code": 3, "color_name": "rød"}, # rød
		{"named_location_id": '801537bb-85ee-4b84-8202-1e69779a54c3', "color_code": 4, "color_name": "sort"}, # sort
	]

	for item in data:
		populate(item["named_location_id"], item["color_code"], item["color_name"])

	return render(request, "rapport_named_locations.html", {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'color_table': color_table,
		'color_table_display': color_table_display,
	})



def programvaredetaljer(request, pk):
	#Vise detaljer for programvare
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	siste_endringer_antall = 10
	content_type = ContentType.objects.get_for_model(Programvare)
	siste_endringer = LogEntry.objects.filter(content_type=content_type).filter(object_id=pk).order_by('-action_time')[:siste_endringer_antall]
	programvare = Programvare.objects.get(pk=pk)
	programvarebruk = ProgramvareBruk.objects.filter(programvare=pk, ibruk=True).order_by("brukergruppe")
	behandlinger = BehandlingerPersonopplysninger.objects.filter(programvarer=pk).order_by("funksjonsomraade")

	return render(request, "programvare_detaljer.html", {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'programvare': programvare,
		'programvarebruk': programvarebruk,
		'behandlinger': behandlinger,
		'siste_endringer': siste_endringer,
		'siste_endringer_antall': siste_endringer_antall,
	})



def alle_programvarer(request):
	#Vise alle programvarer
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space

	if search_term == "":
		aktuelle_programvarer = Programvare.objects.all()
	elif len(search_term) < 2: # if one or less, return nothing
		aktuelle_programvarer = Programvare.objects.none()
	else:
		aktuelle_programvarer = Programvare.objects.filter(programvarenavn__icontains=search_term)

	aktuelle_programvarer = aktuelle_programvarer.order_by(Lower('programvarenavn'))

	programvare = Programvare.objects.values_list('programvarenavn', flat=True).distinct()
	leverandorer = Leverandor.objects.values_list('leverandor_navn', flat=True).distinct()
	systemer = System.objects.values_list('systemnavn', flat=True).distinct()
	programvare_json = json.dumps(list(programvare) + list(leverandorer) + list(systemer))

	return render(request, 'programvare_alle.html', {
		'overskrift': "Programvarer og applikasjoner",
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'programvarer': aktuelle_programvarer,
		'programvare_json': programvare_json,
	})




def programvarebruksdetaljer(request, pk):
	#Vise detaljer for bruk av programvare
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	bruksdetaljer = ProgramvareBruk.objects.get(pk=pk)

	return render(request, "programvarebruk_detaljer.html", {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'bruksdetaljer': bruksdetaljer,
	})


"""
def alle_tjenester(request):
	tjenester = Tjeneste.objects.all().order_by(Lower('tjenestenavn'))
	template = 'alle_tjenester.html'

	return render(request, template, {
		'overskrift': "Tjenester",
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'tjenester': tjenester,
	})

def tjenestedetaljer(request, pk):
	tjeneste = Tjeneste.objects.get(pk=pk)

	return render(request, 'detaljer_tjeneste.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'tjeneste': tjeneste,
	})
"""


def alle_behandlinger(request):
	#Vise alle behandlinger (av personopplysninger) registrert for kommunen
	required_permissions = ['systemoversikt.view_behandlingerpersonopplysninger']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	behandlinger = BehandlingerPersonopplysninger.objects.all()

	return render(request, 'behandling_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'behandlinger': behandlinger,
	})



def behandlingsdetaljer(request, pk):
	#Vise detaljer for en behandling av personopplysninger
	required_permissions = ['systemoversikt.view_behandlingerpersonopplysninger']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	behandling = BehandlingerPersonopplysninger.objects.get(pk=pk)

	siste_endringer_antall = 10
	system_content_type = ContentType.objects.get_for_model(BehandlingerPersonopplysninger)
	siste_endringer = LogEntry.objects.filter(content_type=system_content_type).filter(object_id=pk).order_by('-action_time')[:siste_endringer_antall]

	return render(request, 'behandling_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'behandling': behandling,
		'siste_endringer': siste_endringer,
		'siste_endringer_antall': siste_endringer_antall,
	})



def mine_behandlinger(request):
	#Vise alle behandling av personopplysninger for innlogget brukers virksomhet
	required_permissions = None # kun redirect
	try:
		brukers_virksomhet = virksomhet_til_bruker(request)
		pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
		return redirect('alle_behandlinger_virksomhet', pk)
	except:
		messages.warning(request, 'Din bruker er ikke knyttet til en virksomhet. Velg en virksomhet fra listen, og velg så "Våre behandlinger".')
		return redirect('alle_virksomheter')



def alle_behandlinger_virksomhet(request, pk, internt_ansvarlig=False):
	#Vise alle behandling av personopplysninger for en valgt virksomhet
	#Tilgangsstyring: Merk at noe informasjon i tillegg er tilgangsstyrt i template
	required_permissions = ['systemoversikt.view_behandlingerpersonopplysninger']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	# internt_ansvarlig benyttes for å filtrere ut på underavdeling/seksjon/
	vir = Virksomhet.objects.get(pk=pk)

	# finne behandlinger virksomheten abonnerer på
	delte_behandlinger = behandlingsprotokoll_felles(pk)

	# finne alle egne behandlinger
	virksomhetens_behandlinger = behandlingsprotokoll_egne(pk)

	# generere en liste med unike avdelinger
	virksomhetens_behandlinger_avdelinger = list(virksomhetens_behandlinger.values('internt_ansvarlig').distinct())
	delte_behandlinger_avdelinger = list(delte_behandlinger.values('internt_ansvarlig').distinct())
	for item in delte_behandlinger_avdelinger:
		if item not in virksomhetens_behandlinger_avdelinger:
			virksomhetens_behandlinger_avdelinger.append(item)

	# filter for å fjerne alt utenom en valgt avdeling
	if internt_ansvarlig:
		if internt_ansvarlig == "None": # denne kommer som en string
			virksomhetens_behandlinger = virksomhetens_behandlinger.filter(internt_ansvarlig=None)
		else:
			virksomhetens_behandlinger = virksomhetens_behandlinger.filter(internt_ansvarlig=internt_ansvarlig)
		delte_behandlinger = delte_behandlinger.filter(internt_ansvarlig=internt_ansvarlig)

	# slå sammen felles og egne behandlinger til et sett
	behandlinger = virksomhetens_behandlinger.union(delte_behandlinger).order_by('internt_ansvarlig')

	return render(request, "behandling_behandlingsprotokoll.html", {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'behandlinger': behandlinger,
		'virksomhet': vir,
		'interne_avdelinger': virksomhetens_behandlinger_avdelinger,
		'internt_ansvarlig_valgt': internt_ansvarlig,
	})



def behandling_kopier(request, system_pk):
	#Funksjon for å kunne velge og kopiere en behandling til innlogget brukers virksomhet
	#Tilgangsstyring: Legge til behandling (begrenset til egen virksomhet i kode)
	required_permissions = ['systemoversikt.add_behandlingerpersonopplysninger']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	din_virksomhet = request.user.profile.virksomhet
	dette_systemet = System.objects.get(pk=system_pk)
	kandidatbehandlinger = BehandlingerPersonopplysninger.objects.filter(systemer=dette_systemet).order_by("-fellesbehandling")
	valgte_behandlinger = request.POST.getlist("behandling", "")
	#messages.success(request, 'Du valgte: %s' % valgte_behandlinger)

	if valgte_behandlinger != "":
		for behandling_pk in valgte_behandlinger:
			behandling = BehandlingerPersonopplysninger.objects.get(pk=int(behandling_pk))
			behandling.behandlingsansvarlig = din_virksomhet
			behandling.internt_ansvarlig = "Må endres (kopi)"
			behandling.fellesbehandling = False  # en kopi er ikke en fellesbehandling

			opprinnelig_kategorier_personopplysninger = behandling.kategorier_personopplysninger.all()
			opprinnelig_den_registrerte = behandling.den_registrerte.all()
			opprinnelig_den_registrerte_hovedkateogi = behandling.den_registrerte_hovedkateogi.all()
			opprinnelig_behandlingsgrunnlag_valg = behandling.behandlingsgrunnlag_valg.all()
			opprinnelig_systemer = behandling.systemer.all()
			opprinnelig_programvarer = behandling.programvarer.all()
			opprinnelig_navn_databehandler = behandling.navn_databehandler.all()

			behandling.pk = None  # dette er nå en ny instans av objektet, og den gamle er uberørt
			behandling.save()

			behandling.kategorier_personopplysninger.set(opprinnelig_kategorier_personopplysninger)
			behandling.den_registrerte.set(opprinnelig_den_registrerte)
			behandling.den_registrerte_hovedkateogi.set(opprinnelig_den_registrerte_hovedkateogi)
			behandling.behandlingsgrunnlag_valg.set(opprinnelig_behandlingsgrunnlag_valg)
			behandling.systemer.set(opprinnelig_systemer)
			behandling.programvarer.set(opprinnelig_programvarer)
			behandling.navn_databehandler.set(opprinnelig_navn_databehandler)

			messages.success(request, 'Lagret ny kopi av %s med id %s' % (behandling_pk, behandling.pk))

	#TODO Denne mangler behandler virksomheten "abonnerer på". Må vurdere å lage en metode som returnerer virksomhetens aktive behandlinger og gjenbruke denne
	dine_eksisterende_behandlinger = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=din_virksomhet).filter(systemer=dette_systemet)

	return render(request, 'system_kopier_behandling.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'system': dette_systemet,
		'dine_eksisterende_behandlinger': dine_eksisterende_behandlinger,
		'kandidatbehandlinger': kandidatbehandlinger,
		'din_virksomhet': din_virksomhet,
	})



def virksomhet_ansvarlige(request, pk=None):

	if pk == None:
		try:
			brukers_virksomhet = virksomhet_til_bruker(request)
			pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
			return redirect('virksomhet_ansvarlige', pk)
		except:
			messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
			return redirect('alle_virksomheter')

	#Vise alle ansvarlige knyttet til valgt virksomhet
	required_permissions = ['systemoversikt.view_ansvarlig']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	ansvarlige = Ansvarlig.objects.filter(brukernavn__profile__virksomhet=pk).order_by('brukernavn__first_name')
	return render(request, 'ansvarlig_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'ansvarlige': ansvarlige,
		'virksomhet': virksomhet,
	})


def brukere_startside(request):
	required_permissions = ['auth.view_user']
	if any(map(request.user.has_perm, required_permissions)):

		return render(request, 'brukere_startside.html', {
			'request': request,
			'required_permissions': formater_permissions(required_permissions),
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def enhet_detaljer(request, pk):
	#Vise informasjon om en konkret organisatorisk enhet
	required_permissions = ['auth.view_user']
	if any(map(request.user.has_perm, required_permissions)):

		unit = HRorg.objects.get(pk=pk)
		sideenheter = HRorg.objects.filter(direkte_mor=unit).order_by('ou')
		personer = User.objects.filter(profile__org_unit=pk).order_by('profile__displayName')
		systemer_ansvarfor = System.objects.filter(systemforvalter_avdeling_referanse=unit).filter(~Q(livslop_status__in=[7]))

		return render(request, 'virksomhet_enhet_detaljer.html', {
			'request': request,
			'required_permissions': formater_permissions(required_permissions),
			'unit': unit,
			'sideenheter': sideenheter,
			'personer': personer,
			'systemer_ansvarfor': systemer_ansvarfor,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })



def virksomhet_enhetsok(request):
	#Vise informasjon om organisatorisk struktur
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term', "").strip()
	if len(search_term) > 1:
		units = HRorg.objects.filter(ou__icontains=search_term).filter(active=True).order_by('virksomhet_mor')
	else:
		units = HRorg.objects.none()

	return render(request, 'virksomhet_enhetsok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'units': units,
		'search_term': search_term,
	})



def virksomhet_enheter(request, pk):
	#Vise informasjon om organisatorisk struktur
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import math
	virksomhet = Virksomhet.objects.get(pk=pk)

	avhengigheter_graf = {"nodes": [], "edges": []}

	def color(unit):
		palett = {
			1: "black",
			2: "#ff0000",
			3: "#cc0033",
			4: "#990066",
			5: "#660099",
			6: "#3300cc",
			7: "#0000ff",
		}
		return palett[unit.level]

	"""
	def size(unit):
		minimum = 25
		if unit.num_members > 0:
			adjusted_member_count = minimum + (20 * math.log(unit.num_members, 10))
			return ("%spx" % adjusted_member_count)
		else:
			return ("%spx" % minimum)
	"""

	nodes = []
	units = HRorg.objects.filter(virksomhet_mor=pk).filter(active=True).filter(level__gt=2)
	for u in units:
		members = User.objects.filter(profile__org_unit=u.pk)
		if len(members) > 0:
			u.num_members = len(members)
			nodes.append(u)
			nodes.append(u.direkte_mor)
			avhengigheter_graf["edges"].append(
				{"data": {
					"source": u.direkte_mor.pk,
					"target": u.pk,
					"linestyle": "solid"
					}
				})
	for u in nodes:
		avhengigheter_graf["nodes"].append(
			{"data": {
				"id": u.pk,
				"name": u.ou,
				"parent": u.direkte_mor.ou,
				"shape": "ellipse",
				"color": color(u),
				#"size": size(u)
				#"href": reverse('adgruppe_detaljer', args=[m.pk])
				}
			})

	return render(request, 'virksomhet_enheter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'units': units,
		'virksomhet': virksomhet,
		'avhengigheter_graf': avhengigheter_graf,
	})


def api_overview(request):
	#Vise informasjon brukere som har leverandørtilgang
	required_permissions = ['auth.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


	return render(request, 'rapport_api_overview.html', {
		"request": request,
		"required_permissions": required_permissions,
	})



def leverandortilgang(request, valgt_gruppe=None):
	#Vise informasjon brukere som har leverandørtilgang
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if valgt_gruppe == None:

		leverandortilganger = Leverandortilgang.objects.all()
		connected_groups = []
		for lt in leverandortilganger:
			connected_groups.extend([getattr(adgruppe, 'distinguishedname') if adgruppe else "" for adgruppe in lt.adgrupper.all()])

		manglende_grupper = []

		for levtilganggruppe in LEVERANDORTILGANG_KJENTE_GRUPPER:
			dml_grupper = ADgroup.objects.filter(distinguishedname__icontains=levtilganggruppe).exclude(distinguishedname__in=[o for o in connected_groups])
			for g in dml_grupper:
				if g.common_name != None:
					if all(substring not in g.common_name for substring in ["_L0", "_L4", "_L1"]):
						manglende_grupper.append(g)

		manglende_grupper.sort(key=lambda g : g.common_name)

		virksomheter = virksomheter = Virksomhet.objects.filter(ordinar_virksomhet=True)

		return render(request, 'ad_leverandortilgang.html', {
			"request": request,
			"virksomheter": virksomheter,
			"required_permissions": required_permissions,
			"manglende_grupper": manglende_grupper,
			"leverandortilganger": leverandortilganger,
		})

	# må sjekkes, hva om ikke None?


def rapport_trusted_delegation(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	brukere = User.objects.filter(profile__trusted_for_delegation=True).order_by("username")

	for b in brukere:
		try:
			b.spns = json.loads(b.profile.service_principal_name)
		except:
			b.spns = None

	return render(request, 'rapport_trusted_delegation.html', {
		"request": request,
		"required_permissions": required_permissions,
		"brukere": brukere,
	})

def alle_spn(request):
	#Vise informasjon brukere som er opprettet for å teste noe (og ikke har blitt slettet i etterkant)
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	brukere = User.objects.filter(~Q(profile__service_principal_name=None)).order_by("username")

	for b in brukere:
		b.spns = json.loads(b.profile.service_principal_name)

	return render(request, 'ad_alle_spn.html', {
		"request": request,
		"required_permissions": required_permissions,
		"brukere": brukere,
	})

def tbrukere(request):
	#Vise informasjon brukere som er opprettet for å teste noe (og ikke har blitt slettet i etterkant)
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	brukere = User.objects.filter( Q(username__istartswith="t-") | Q(username__istartswith="t_") | Q(username__icontains="_t2") | Q(username__icontains="aks20") | Q(username__icontains="_qa") | Q(username__icontains="-qa") ).order_by("username")

	return render(request, 'ad_tbrukere.html', {
		"request": request,
		"required_permissions": required_permissions,
		"brukere": brukere,
	})



def drifttilgang(request):
	#Vise informasjon brukere som har drifttilgang
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	def adgruppe_oppslag(liste):
		oppslag = []
		for cn in liste:
			try:
				oppslag.append(ADgroup.objects.get(common_name=cn))
			except:
				#print("error adgruppe_oppslag() %s" % (cn))
				pass
		return oppslag

	serveradmins = [
		"GS-OpsRole-ErgoGroup-AdminAlleMemberServere",
		"GS-OpsRole-Ergogroup-ServerAdmins",
		"Task-OF2-ServerAdmin-AllMemberServers",
		"Role-OF2-Admin-Citrix Services",
		"DS-MemberServer-Admin-AlleManagementServere",
		"DS-MemberServer-Admin-AlleManagementServere",
		"DS-DRIFT_DRIFTSPERSONELL_SERVERMGMT_SERVERADMIN",
		"Role-OF2-AdminAlleMemberServere",
	]
	serveradmins = adgruppe_oppslag(serveradmins)

	domainadmins = [
		"Domain Admins",
		"Enterprise Admins",
		"Role-Domain-Admins-UVA",
		"On-Prem Domain Admins (009378fe-ecdf-4f49-bd65-d82411703915)",
	]
	domainadmins = adgruppe_oppslag(domainadmins)

	prkadmin = [
		"DS-GKAT_BRGR_SYSADM",
		"DS-GKAT_ADMSENTRALESKJEMA_ALLE",
		"DS-GKAT_ADMSENTRALESKJEMA_KOKS",
		"DS-GKAT_IMPSKJEMA_TIGIMP",
		"DS-GKAT_IMPSKJEMA_TSIMP",
		"DS-GKAT_MODULER_GLOBAL_ADMINISTRASJON",
		"DS-GKAT_DSGLOKALESKJEMA_ALLE",
		"DS-GKAT_DSGLOKALESKJEMA_INFOCARE",
		"DS-GKAT_DSGLOKALESKJEMA_OPPRETTE",
		"DS-GKAT_DSGSENTRALESKJEMA_ALLE",
		"DS-GKAT_DSGSENTRALESKJEMA_OPPRETTE",
		"DS-GKAT_ADMLOKALESKJEMA_ALLE",
		"DS-GKAT_ADMLOKALESKJEMA_APPLIKASJON",
	]
	prkadmin = adgruppe_oppslag(prkadmin)

	sqladmins = [
		"GS-UKE-MSSQL-DBA",
		"DS-OF2-SQL-SYSADMIN",
		"DS-DRIFT_DRIFTSPERSONELL_DATABASE_SQL",
		"GS-Role-MSSQL-DBA",
		"GS-UKE-MSSQL-DBA",
		"DS-Role-MSSQL-DBA",
		"DS-DRIFT_DRIFTSPERSONELL_DATABASE_ORACLE",
		"DS-OF2-TASK-SQLCluster",
	]
	sqladmins = adgruppe_oppslag(sqladmins)

	citrixadmin = [
		"Task-OF2-Admin-Citrix XenApp",
		"DS-DRIFT_DRIFTSPERSONELL_REMOTE_CITRIXDIRECTOR",
		"DS-DRIFT_DRIFTSPERSONELL_CITRIX_APPV_ADMIN",
		"DS-DRIFT_DRIFTSPERSONELL_CITRIX_CITRIX_NETSCALER_ADM",
		"DS-DRIFT_DRIFTSPERSONELL_CITRIX_ADMINISTRATOR",
		"DS-DRIFT_DRIFTSPERSONELL_CITRIX_DRIFT",
	]
	citrixadmin = adgruppe_oppslag(citrixadmin)

	sccmadmin = [
		"Task-SCCM-Application-Administrator",
		"Task-SCCM-Application-Author",
		"Task-SCCM-Application-Deployment-Manager",
		"Task-SCCM-Asset-Manager",
		"Task-SCCM-Compliance-Settings-Manager",
		"Task-SCCM-Endpoint-Protection-Manager",
		"Task-SCCM-Operations-Administrator",
		"Task-SCCM-OSD-Manager",
		"Task-SCCM-Infrastructure-Administrator",
		"Task-SCCM-Remote-Tools-Operator",
		"Task-SCCM-Security-Administrator",
		"Task-SCCM-Software-Update-Manager",
		"Task-SCCM-Full-Administrator",
		"Task-SCCM-SRV-Admin",
		"Task-SCCM-ClientInstall_SikkerSone_MP",
		"Task-SCCM-ClientInstall_InternSone_MP",
		"Task-SCCM-ClientInstall",
		"TASK-SCCM-CLIENT-INSTALL-EXCLUDE",
		"Task-SCCM-RemoteDesktop",
		"Task-SCCM-SQL-Admin",
		"DS-DRIFT_DRIFTSPERSONELL_SCCM_SCCMFULLADM",
		"DA-SCCM-SQL-SysAdmin-F",
	]
	sccmadmin = adgruppe_oppslag(sccmadmin)

	levtilgang = [
		"DS-DRIFT_DML_LEVTILGANG_LEVTILGANGSS",
		"DS-DRIFT_DML_LEVTILGANG_LEVTILGANG",
		"DS-DRIFT_DML_DRIFTTILGANG_DRIFTTILGANGIS",
		"DS-DRIFT_DML_DRIFTTILGANG_DRIFTTILGANGSS",
	]
	levtilgang = adgruppe_oppslag(levtilgang)

	dcadmin = [
		"DS-DRIFT_DRIFTSPERSONELL_SERVERMGMT_ADMINDC",
	]
	dcadmin = adgruppe_oppslag(dcadmin)

	exchangeadmin = [
		"DS-DRIFT_DRIFTSPERSONELL_MAIL_EXH_FULL_ADMINISTRATOR",
	]
	exchangeadmin = adgruppe_oppslag(exchangeadmin)

	filsensitivt = [
		"DS-DRIFT_DRIFTSPERSONELL_ACCESSMGMT_OVERGREPSMOTTAKET",
	]
	filsensitivt = adgruppe_oppslag(filsensitivt)

	brukere = User.objects.filter(Q(profile__distinguishedname__icontains="OU=DRIFT,OU=Eksterne brukere") | Q(profile__distinguishedname__icontains="OU=DRIFT,OU=Brukere")).filter(profile__accountdisable=False)
	tekst_type_konto = "drift"

	if "kilde" in request.GET:
		if request.GET["kilde"] == "servicekontoer":
			brukere = User.objects.filter(profile__distinguishedname__icontains="OU=Servicekontoer").filter(profile__accountdisable=False)
			tekst_type_konto = "service"
	#brukere = User.objects.filter(profile__accountdisable=False).filter(Q(profile__description__icontains="Sopra") | Q(profile__description__icontains="2S"))

	"""
	driftbrukere4 = User.objects.filter(username__istartswith="T-DRIFT")
	for u in list(set(driftbrukerex) - (set(driftbrukere))):
		print(u.username)
	driftbrukere2 = User.objects.filter(username__istartswith="t-")
	driftbrukerey = User.objects.filter(username__istartswith="a-")
	driftbrukere3 = User.objects.filter(profile__virksomhet=None)
	"""

	#adg_filter = set(serveradmins).union(set(domainadmins)).union(set(prkadmin)).union(set(sqladmins)).union(set(citrixadmin)).union(set(sccmadmin)).union(set(levtilgang)).union(set(dcadmin)).union(set(exchangeadmin)).union(set(filsensitivt))
	#b.reduserte_adgrupper = set(b.profile.adgrupper.all()).difference(adg_filter)

	"""
	for b in brukere:
		b.serveradmin = set(serveradmins).intersection(set(b.profile.adgrupper.all()))
		b.domainadmin = set(domainadmins).intersection(set(b.profile.adgrupper.all()))
		b.prkadmin = set(prkadmin).intersection(set(b.profile.adgrupper.all()))
		b.sqladmin = set(sqladmins).intersection(set(b.profile.adgrupper.all()))
		b.citrixadmin = set(citrixadmin).intersection(set(b.profile.adgrupper.all()))
		b.sccmadmin = set(sccmadmin).intersection(set(b.profile.adgrupper.all()))
		b.levtilgang = set(levtilgang).intersection(set(b.profile.adgrupper.all()))
		b.dcadmin = set(dcadmin).intersection(set(b.profile.adgrupper.all()))
		b.exchangeadmin = set(exchangeadmin).intersection(set(b.profile.adgrupper.all()))
		b.filsensitivt = set(filsensitivt).intersection(set(b.profile.adgrupper.all()))
	"""

	return render(request, 'ad_drifttilgang.html', {
		"request": request,
		"required_permissions": required_permissions,
		"brukere": brukere,
		"tekst_type_konto": tekst_type_konto,
	})



def prk_userlookup(request):
	#Vise informasjon om vilkårlige brukere
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if request.POST:
		query = request.POST.get('query', '').strip()
		users = re.findall(r"([^,;\t\s\n\r]+)", query)
		users_result = []
		for item in users:
			try:
				u = User.objects.get(username__iexact=item)
				users_result.append({
					"username": u.username,
					"organization": u.profile.org_tilhorighet,
					"accountdisable": u.profile.accountdisable,
					"name": u.profile.displayName,
					})
			except:
				messages.warning(request, 'Fant ikke info på "%s"' % (item))
				continue

	else:
		users_result = []
		query = ""

	return render(request, 'prk_userlookup.html', {
		"request": request,
		"required_permissions": required_permissions,
		"query": query,
		"users": users_result,
	})



def virksomhet_prkadmin(request, pk):
	#Vise alle PRK-administratorer for angitt virksomhet

	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from functools import lru_cache

	@lru_cache(maxsize=2048)
	def lookup_user(username):
		try:
			user = User.objects.get(username__iexact=username)
			return user
		except:
			return username
	try:
		vir = Virksomhet.objects.get(pk=pk)
	except:
		vir = None

	skjema_grupper = ADgroup.objects.filter(distinguishedname__icontains="gkat")
	prk_admins = {}

	for g in skjema_grupper:
		group_name = g.distinguishedname[6:].split(",")[0]
		if group_name == "GKAT":
			continue

		members = json.loads(g.member)
		users = []
		for m in members:
			match = re.search(r'CN=(' + re.escape(vir.virksomhetsforkortelse) + '\d{2,8}),', m, re.IGNORECASE)
			if match:
				user = lookup_user(match[1])
				users.append(user)
			else:
				pass

		prk_admins[group_name] = users

	user_set = set(a for b in prk_admins.values() for a in b)
	prk_admins_inverted = dict((new_key, [key for key,value in prk_admins.items() if new_key in value]) for new_key in user_set)

	return render(request, 'virksomhet_prkadm.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': vir,
		'prk_admins': prk_admins_inverted,
	})



def systemer_virksomhet_ansvarlig_for(request, pk=None):

	if pk == None:
		try:
			brukers_virksomhet = virksomhet_til_bruker(request)
			pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
			return redirect('systemer_virksomhet_ansvarlig_for', pk)
		except:
			messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
			return redirect('alle_virksomheter')

	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	systemer_ansvarlig_for = System.objects.filter(~Q(ibruk=False)).filter(Q(systemeier=pk) | Q(systemforvalter=pk)).order_by(Lower('systemnavn'))

	unike_ansvarlige_eiere = set()
	unike_ansvarlige_forvaltere = set()
	for system in systemer_ansvarlig_for:
		for ansvarlig in system.systemforvalter_kontaktpersoner_referanse.all():
			unike_ansvarlige_forvaltere.add(ansvarlig)
		for ansvarlig in system.systemeier_kontaktpersoner_referanse.all():
			unike_ansvarlige_eiere.add(ansvarlig)

	return render(request, 'virksomhet_systemer_ansvarfor.html', {
		"request": request,
		"required_permissions": required_permissions,
		'virksomhet': virksomhet,
		'systemer_ansvarlig_for': systemer_ansvarlig_for,
		'unike_ansvarlige_eiere': list(unike_ansvarlige_eiere),
		'unike_ansvarlige_forvaltere': list(unike_ansvarlige_forvaltere),
	})



def virksomhet_forvalter_isk(request, pk=None):

	if pk == None:
		try:
			brukers_virksomhet = virksomhet_til_bruker(request)
			pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
			return redirect('virksomhet_forvalter_isk', pk)
		except:
			messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
			return redirect('alle_virksomheter')


	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	systemer_ansvarlig_for = System.objects.filter(~Q(ibruk=False)).filter(Q(systemeier=pk) | Q(systemforvalter=pk)).order_by(Lower('systemnavn'))

	return render(request, 'virksomhet_forvalter_isk.html', {
		"request": request,
		"required_permissions": required_permissions,
		'virksomhet': virksomhet,
		'systemer_ansvarlig_for': systemer_ansvarlig_for,
	})



def systemer_virksomhet_ansvarlig_for_fip(request, pk):
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	uke = Virksomhet.objects.get(virksomhetsforkortelse="UKE")
	systemer_ansvarlig_for = System.objects.filter(~Q(ibruk=False)).filter(Q(systemeier=pk) | Q(systemforvalter=pk)).filter(driftsmodell_foreignkey__ansvarlig_virksomhet=uke).order_by(Lower('systemnavn'))

	unike_ansvarlige_eiere = set()
	unike_ansvarlige_forvaltere = set()
	for system in systemer_ansvarlig_for:
		for ansvarlig in system.systemforvalter_kontaktpersoner_referanse.all():
			unike_ansvarlige_forvaltere.add(ansvarlig)
		for ansvarlig in system.systemeier_kontaktpersoner_referanse.all():
			unike_ansvarlige_eiere.add(ansvarlig)

	return render(request, 'virksomhet_systemer_ansvarfor.html', {
		"request": request,
		"required_permissions": required_permissions,
		'virksomhet': virksomhet,
		'systemer_ansvarlig_for': systemer_ansvarlig_for,
		'unike_ansvarlige_eiere': list(unike_ansvarlige_eiere),
		'unike_ansvarlige_forvaltere': list(unike_ansvarlige_forvaltere),
	})



def virksomhet(request, pk):
	#Vise detaljer om en valgt virksomhet
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	antall_brukere = User.objects.filter(profile__virksomhet=pk).filter(profile__ekstern_ressurs=False).filter(is_active=True).count()
	antall_eksterne_brukere = User.objects.filter(profile__virksomhet=pk).filter(profile__ekstern_ressurs=True).filter(is_active=True).count()

	systemforvalter_ikke_kvalitetssikret = System.objects.filter(systemforvalter=pk).filter(informasjon_kvalitetssikret=False).count()
	systemeier_ikke_kvalitetssikret = System.objects.filter(systemeier=pk).filter(informasjon_kvalitetssikret=False).count()

	deaktiverte_brukere = Ansvarlig.objects.filter(brukernavn__profile__virksomhet=pk).filter(brukernavn__profile__accountdisable=True).count()
	ant_behandlinger = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=virksomhet).count()
	behandling_ikke_kvalitetssikret = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=virksomhet).filter(informasjon_kvalitetssikret=False).count()

	ant_systemer_bruk = SystemBruk.objects.filter(brukergruppe=pk).count()
	ant_systemer_eier = System.objects.filter(systemeier=pk).count()
	ant_systemer_forvalter = System.objects.filter(systemforvalter=pk).count()
	enheter = HRorg.objects.filter(virksomhet_mor=pk).filter(level=3)

	systemer_drifter = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=pk).filter(~Q(ibruk=False)).count()

	nodes = []
	parents = []

	def systemnavn_forkortet(system):
		maximum = 20
		if len(system.systemnavn) > maximum:
			return system.systemnavn[:maximum]
		return system.systemnavn

	def system_seksjon(system):
		if system.systemforvalter_avdeling_referanse:
			parents.append(system.systemforvalter_avdeling_referanse)
			return f"org_{system.systemforvalter_avdeling_referanse.pk}"

		try:
			forste_forvalters_ou = system.systemforvalter_kontaktpersoner_referanse.all()[0].brukernavn.profile.org_unit
			parents.append(forste_forvalters_ou)
			return forste_forvalters_ou.ou
		except:
			pass

		parents.append('Ukjent')
		return 'Ukjent'

	antall_graph_noder = System.objects.filter(systemforvalter=pk).filter(~Q(livslop_status__in=[6,7])).count()
	for system in System.objects.filter(systemforvalter=pk).filter(~Q(livslop_status__in=[6,7])).order_by('systemnavn'):
		if system.er_ibruk():
			nodes.append({
				'data': {
					'id': system.pk,
					'name': systemnavn_forkortet(system),
					'parent': system_seksjon(system),
					'shape': 'rectangle',
					'color': system.color(),
					'href': f'/systemer/detaljer/{system.pk}/',
				}
			})

	#print(list(set(parents)))

	all_parents = list(set(parents))
	work_queue = list(set(parents))
	while work_queue:
		item = work_queue.pop()
		if item == 'Ukjent' or item == None:
			continue
		if item.direkte_mor != None:
			if item.direkte_mor not in all_parents:
				#print(f"La til {item.direkte_mor}")
				work_queue.append(item.direkte_mor)
				all_parents.append(item.direkte_mor)
			else:
				#print(f"{item.direkte_mor} var allerede lagt til")
				pass


	for p in all_parents:
		if p == 'Ukjent':
			nodes.append({'data': {'id': p, 'name': p, 'color': 'white', 'shape': 'rectangle',}},)
			continue
		if p == None:
			continue
		if p.direkte_mor != None:
			nodes.append({'data': {'id': f"org_{p.pk}", 'name': p.ou, 'color': 'white', 'shape': 'rectangle', 'parent': f"org_{p.direkte_mor.pk}"}},)
			#nodes.append({'data': {'id': f"org_{p.direkte_mor.pk}", 'name': p.direkte_mor.ou, 'color': 'white',}},)
		else:
			nodes.append({'data': {'id': f"org_{p.pk}", 'name': p.ou, 'color': 'white', 'shape': 'rectangle',}},)

	from systemoversikt.models import SYSTEM_COLORS

	return render(request, 'virksomhet_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'antall_brukere': antall_brukere,
		'antall_eksterne_brukere': antall_eksterne_brukere,
		'systemforvalter_ikke_kvalitetssikret': systemforvalter_ikke_kvalitetssikret,
		'systemeier_ikke_kvalitetssikret': systemeier_ikke_kvalitetssikret,
		'deaktiverte_brukere': deaktiverte_brukere,
		'ant_behandlinger': ant_behandlinger,
		'behandling_ikke_kvalitetssikret': behandling_ikke_kvalitetssikret,
		'enheter': enheter,
		'ant_systemer_bruk': ant_systemer_bruk,
		'ant_systemer_eier': ant_systemer_eier,
		'ant_systemer_forvalter': ant_systemer_forvalter,
		'systemer_drifter': systemer_drifter,
		'nodes': nodes,
		'node_size': 600 + 5 * antall_graph_noder,
		'system_colors': SYSTEM_COLORS,
	})



def min_virksomhet(request):
	#Vise detaljer om en innlogget brukers virksomhet
	required_permissions = None # kun redirect

	try:
		brukers_virksomhet = virksomhet_til_bruker(request)
		pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
		return redirect('virksomhet', pk)

	except:
		messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
		return redirect('alle_virksomheter')


def innsyn_virksomhet(request, pk):
	#Vise informasjon om kontaktpersoner for innsyn for en valgt virksomhet (for systemer virksomhet behandler personopplysninger i)
	required_permissions = ['systemoversikt.view_behandlingerpersonopplysninger']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	virksomhets_behandlingsprotokoll = behandlingsprotokoll(pk)
	systemer = []
	for behandling in virksomhets_behandlingsprotokoll:
		for system in behandling.systemer.all():
			if (system not in systemer) and (system.innsyn_innbygger or system.innsyn_ansatt) and (system.ibruk != False):
				systemer.append(system)

	return render(request, 'virksomhet_innsyn.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'systemer': systemer,
	})



def bytt_virksomhet(request):
	#Tilgangsstyring: Innlogget og avhengig av virksomhet innlogget bruker er logget inn som
	#returnere en liste over virksomheter som gjeldende bruker kan representere
	required_permissions = None
	brukers_virksomhet_innlogget_som = request.user.profile.virksomhet_innlogget_som
	if brukers_virksomhet_innlogget_som != None:
		# Vi tar med virksomheten bruker er logget inn med samt alle virksomheter som har angitt gjeldende virksomhet som overordnet virksomhet.
		dine_virksomheter = Virksomhet.objects.filter(Q(pk=brukers_virksomhet_innlogget_som.pk) | Q(overordnede_virksomheter=brukers_virksomhet_innlogget_som))
	else:
		dine_virksomheter = None

	representasjonsvalg_str = request.POST.get("virksomhet", "")
	if representasjonsvalg_str != "":
		valgt_virksomhet = Virksomhet.objects.get(pk=int(representasjonsvalg_str))
		try:
			tillatte_bytter = dine_virksomheter
			if valgt_virksomhet in tillatte_bytter:
				request.user.profile.virksomhet = valgt_virksomhet
				request.user.save()
				messages.success(request, 'Du representerer nå %s' % valgt_virksomhet)
				return redirect(reverse('minside'))
			else:
				messages.warning(request, 'Forsøk på ulovlig bytte')
		except:
			messages.warning(request, 'Noe gikk galt ved endring av virksomhetstilhørighet')

	# denne må vi vente med i tilfelle den blir endret ved en POST-request
	aktiv_representasjon = request.user.profile.virksomhet

	return render(request, 'site_bytt_virksomhet.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'brukers_virksomhet': aktiv_representasjon,
		'dine_virksomheter': dine_virksomheter,
	})


def sertifikatmyndighet(request):
	#Vise informasjon om delegeringer knyttet til sertifikater
	required_permissions = ['systemoversikt.view_virksomhet']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomheter = Virksomhet.objects.all().order_by('-sertifikatfullmakt_avgitt_web')

	return render(request, 'virksomhet_sertifikatmyndigheter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomheter': virksomheter,
	})



def alle_virksomheter(request):
	#Vise oversikt over alle virksomheter
	required_permissions = None

	search_term = request.GET.get('search_term', "").strip()

	if search_term in ("", "__all__"):
		virksomheter = Virksomhet.objects.all()
	else:
		virksomheter = Virksomhet.objects.filter(Q(virksomhetsnavn__icontains=search_term) | Q(virksomhetsforkortelse__iexact=search_term))

	virksomheter = virksomheter.order_by('-ordinar_virksomhet', 'virksomhetsnavn')

	return render(request, 'virksomhet_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomheter': virksomheter,
	})



def alle_virksomheter_kontaktinfo(request):
	#Vise oversikt over alle virksomheter
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomheter = Virksomhet.objects.all().order_by('-ordinar_virksomhet', 'virksomhetsnavn')

	return render(request, 'virksomhet_alle_kontaktinfo.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomheter': virksomheter,
	})


def virksomhet_arkivplan(request, pk):
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	systemer = System.objects.filter(Q(systemeier=virksomhet) | Q(systemforvalter=virksomhet))

	return render(request, 'virksomhet_arkivplan.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'systemer': systemer,
	})



def leverandor(request, pk):
	#Vise detaljer for en valgt leverandør
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	leverandor = Leverandor.objects.get(pk=pk)
	systemleverandor_for = System.objects.filter(systemleverandor=pk)
	databehandler_for = BehandlingerPersonopplysninger.objects.filter(navn_databehandler=pk)
	programvareleverandor_for = Programvare.objects.filter(programvareleverandor=pk)
	basisdriftleverandor_for = System.objects.filter(basisdriftleverandor=pk)
	applikasjonsdriftleverandor_for = System.objects.filter(applikasjonsdriftleverandor=pk)
	registrar_for = SystemUrl.objects.filter(registrar=pk)
	sikkerhetstester = Sikkerhetstester.objects.filter(testet_av=pk)
	plattformer = Driftsmodell.objects.filter(leverandor=pk)
	plattformer_underleverandor = Driftsmodell.objects.filter(underleverandorer=pk)

	return render(request, 'leverandor_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'leverandor': leverandor,
		'systemleverandor_for': systemleverandor_for,
		'databehandler_for': databehandler_for,
		'programvareleverandor_for': programvareleverandor_for,
		'basisdriftleverandor_for': basisdriftleverandor_for,
		'applikasjonsdriftleverandor_for': applikasjonsdriftleverandor_for,
		'registrar_for': registrar_for,
		'sikkerhetstester': sikkerhetstester,
		'plattformer': plattformer,
		'plattformer_underleverandor': plattformer_underleverandor,
	})



def alle_leverandorer(request):
	#Vise liste over alle leverandører
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	from django.db.models.functions import Lower
	search_term = request.GET.get('search_term', "").strip()

	if search_term == "":
		leverandorer = Leverandor.objects.all()
	else:
		leverandorer = Leverandor.objects.filter(leverandor_navn__icontains=search_term)

	leverandorer = leverandorer.order_by(Lower('leverandor_navn'))

	return render(request, 'leverandor_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'leverandorer': leverandorer,
	})



def alle_driftsmodeller(request):
	#Vise liste over alle driftsmodeller
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	driftsmodeller = Driftsmodell.objects.all().order_by('sort_order', 'navn')

	return render(request, 'driftsmodell_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'driftsmodeller': driftsmodeller,
	})



def driftsmodell_virksomhet_klassifisering(request, pk):
	#Vise informasjon om sikkerhethetsklassifisering for systemer driftet av en virksomhet (alle systemer koblet til driftsmodeller som forvaltes av valgt virksomhet)
	required_permissions = ['systemoversikt.change_systemkategori']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	driftsmodeller = Driftsmodell.objects.filter(ansvarlig_virksomhet=virksomhet)
	systemer_drifter = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet).filter(~Q(ibruk=False)).order_by('sikkerhetsnivaa')
	return render(request, 'alle_systemer_virksomhet_drifter_klassifisering.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'systemer': systemer_drifter,
		'driftsmodeller': driftsmodeller,
	})


def rapport_prioriteringer(request):
	#Vise indeks over systemprioritering
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomheter = Virksomhet.objects.filter(ordinar_virksomhet=True).filter(~Q(driftsmodell_ansvarlig_virksomhet=None))


	return render(request, 'rapport_prioriteringer.html', {
		'request': request,
		'virksomheter': virksomheter,
	})


def rapport_ukjente_identer(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	identer = User.objects.filter(profile__accountdisable=False, profile__virksomhet=None)

	return render(request, 'rapport_ukjente_identer.html', {
		'request': request,
		'identer': identer,
	})


def drift_beredskap_redirect(request):
	try:
		vir = request.user.profile.virksomhet
		return HttpResponseRedirect(reverse('drift_beredskap', kwargs={'pk': vir.pk}))
	except:
		messages.info("Du er ikke logget inn. Vennligst logg inn slik at du kan sendes til riktig beredskapsplan")
		return HttpResponseRedirect(reverse('home',))



def drift_beredskap(request, pk):
	#Vise systemer driftet av en virksomhet (alle systemer koblet til driftsmodeller som forvaltes av valgt virksomhet)
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	systemer_drifter = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet).filter(ibruk=True).order_by('cache_systemprioritet')

	antall_top_x = 30
	systemer_drifter_top_x = systemer_drifter[0:antall_top_x]

	ikke_infra = []
	for s in systemer_drifter:
		if not s.er_infrastruktur():
			ikke_infra.append(s)
	systemer_drifter = ikke_infra

	return render(request, 'systemer_drifter_prioritering.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'systemer': systemer_drifter,
		'systemer_drifter_top_x': systemer_drifter_top_x,
		'antall_top_x': antall_top_x,
	})



def driftsmodell_virksomhet(request, pk=None):

	if pk == None:
		try:
			brukers_virksomhet = virksomhet_til_bruker(request)
			pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
			return redirect('driftsmodell_virksomhet', pk)
		except:
			messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
			return redirect('alle_virksomheter')


	#Vise systemer driftet av en virksomhet (alle systemer koblet til driftsmodeller som forvaltes av valgt virksomhet)
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	driftsmodeller = Driftsmodell.objects.filter(ansvarlig_virksomhet=virksomhet).order_by("navn")
	systemer_drifter = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet).filter(~Q(ibruk=False)).order_by('systemnavn')

	return render(request, 'system_virksomhet_drifter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'virksomhet': virksomhet,
		'systemer': systemer_drifter,
		'driftsmodeller': driftsmodeller,
	})



def detaljer_driftsmodell(request, pk):
	#Vise detaljer om en valgt driftsmodell (inkl. systemer tilknyttet)
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	driftsmodell = Driftsmodell.objects.get(pk=pk)
	systemer = System.objects.filter(driftsmodell_foreignkey=pk)
	isolert_drift = systemer.filter(isolert_drift=True)

	# gjør et oppslag for å finne kategorier som er, og ikke er anbefalt
	anbefalte_personoppl_kategorier = driftsmodell.anbefalte_kategorier_personopplysninger.all()
	ikke_anbefalte_personoppl_kategorier = Personsonopplysningskategori.objects.filter(~Q(pk__in=anbefalte_personoppl_kategorier)).all()

	return render(request, 'driftsmodell_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'driftsmodell': driftsmodell,
		'systemer': systemer,
		'isolert_drift': isolert_drift,
		'ikke_anbefalte_personoppl_kategorier': ikke_anbefalte_personoppl_kategorier,
	})



def systemer_uten_driftsmodell(request):
	#Vise liste over systemer der driftsmodell mangler
	required_permissions = ['systemoversikt.view_system']

	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	mangler = System.objects.filter(Q(driftsmodell_foreignkey=None) & ~Q(systemtyper=1))

	return render(request, 'driftsmodell_mangler.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': mangler,
})


def systemer_utfaset(request):
	#Vise liste over systemer satt til "ikke i bruk"
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	systemer = System.objects.filter(livslop_status__in=[6,7]).order_by("-sist_oppdatert")

	return render(request, 'system_utfaset.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
})



def systemkategori(request, pk):
	#Vise detaljer om en kategori
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	kategori = SystemKategori.objects.get(pk=pk)
	systemer = System.objects.filter(systemkategorier=pk).order_by(Lower('systemnavn'))
	programvarer = Programvare.objects.filter(kategorier=pk).order_by(Lower('programvarenavn'))

	return render(request, 'kategori_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
		'kategori': kategori,
		'programvarer': programvarer,
	})



def alle_hovedkategorier(request):
	#Vise liste over alle hovedkategorier
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	hovedkategorier = SystemHovedKategori.objects.order_by('hovedkategorinavn')
	for kategori in hovedkategorier:
		systemteller = 0
		programteller = 0
		for subkategori in kategori.subkategorier.all():
			systemteller += len(subkategori.system_systemkategorier.all())
			programteller += len(subkategori.programvare_systemkategorier.all())
		kategori.systemteller = systemteller
		kategori.programteller = programteller

	subkategorier_uten_hovedkategori = []
	for subkategori in SystemKategori.objects.all():
		if len(subkategori.systemhovedkategori_systemkategorier.all()) == 0:
			subkategorier_uten_hovedkategori.append(subkategori)

	return render(request, 'kategori_hoved_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'hovedkategorier': hovedkategorier,
		'subkategorier_uten_hovedkategori': subkategorier_uten_hovedkategori,
	})



def alle_systemkategorier(request):
	#Vise liste over alle (under)kategorier
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	kategorier = SystemKategori.objects.order_by('kategorinavn')

	return render(request, 'kategori_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'kategorier': kategorier,
	})


def uten_systemkategori(request):
	#Vise liste over alle systemer uten (under)kategori
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	antall_systemer = System.objects.all().count()
	antall_programvarer = Programvare.objects.all().count()
	systemer = System.objects.annotate(num_categories=Count('systemkategorier')).filter(num_categories=0)
	programvarer = Programvare.objects.annotate(num_categories=Count('kategorier')).filter(num_categories=0)

	return render(request, 'kategori_system_uten.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': systemer,
		'programvarer': programvarer,
		'antall_systemer': antall_systemer,
		'antall_programvarer': antall_programvarer,
	})



def alle_systemurler(request):
	#Vise liste over alle URLer
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	urler = SystemUrl.objects.order_by('domene')

	return render(request, 'urler_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'web_urler': urler,
	})



def virksomhet_urler(request, pk):
	#Vise liste over alle URLer
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomhet = Virksomhet.objects.get(pk=pk)
	urler = SystemUrl.objects.filter(eier=virksomhet.pk).order_by('domene')

	return render(request, 'urler_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'web_urler': urler,
		'virksomhet': virksomhet,
	})



def bytt_kategori(request, fra, til):
	#Funksjon for å bytte all bruk av én kategori til en annen kategori
	required_permissions = ['systemoversikt.change_systemkategori']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	try:
		kategori_fra = SystemKategori.objects.get(pk=fra)
		kategori_til = SystemKategori.objects.get(pk=til)
	except:
		messages.warning(request, 'Erstatte kategori feilet. Enten "fra" eller "til" kategori finnes ikke.')
		return redirect('alle_virksomheter')

	kildesystemer = System.objects.filter(systemkategorier=fra)
	error = ok = 0
	for system in kildesystemer:
		try:
			system.systemkategorier.remove(kategori_fra)
			system.systemkategorier.add(kategori_til)
			ok += 1
		except:
			error += 1

	messages.success(request, 'Byttet fra %s til %s (ok: %s, error: %s)'% (
				kategori_fra.kategorinavn,
				kategori_til.kategorinavn,
				ok,
				error,
			))
	return redirect('alle_virksomheter')



def bytt_leverandor(request, fra, til):
	#Funksjon for å bytte all bruk av én leverandør til en annen leverandør
	required_permissions = ['systemoversikt.change_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	try:
		leverandor_fra = Leverandor.objects.get(pk=fra)
		leverandor_til = Leverandor.objects.get(pk=til)
	except:
		messages.warning(request, 'Erstatte leverandør feilet. Enten "fra" eller "til"-leverandør finnes ikke.')
		return redirect('alle_leverandorer')

	def bytt(message, kildesystemer, fra, til):
		error = ok = 0
		for kilde in kildesystemer:
			try:
				kilde.systemleverandor.remove(leverandor_fra)
				kilde.systemleverandor.add(leverandor_til)
				ok += 1
			except:
				error += 1
		messages.success(request, '%s: Byttet fra %s til %s (ok: %s, error: %s)'% (
					message,
					leverandor_fra.leverandor_navn,
					leverandor_til.leverandor_navn,
					ok,
					error,
				))

	bytt("Systemer",System.objects.filter(systemleverandor=fra), leverandor_fra, leverandor_til)
	bytt("Systemebruk",SystemBruk.objects.filter(systemleverandor=fra), leverandor_fra, leverandor_til)

	return redirect('alle_leverandorer')



def system_til_programvare(request, system_id=None):
	#Funksjon for å opprette en instans av programvare basert på system (systemet må slettes manuelt etterpå)
	required_permissions = ['systemoversikt.change_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	if system_id:
		try:
			#finne systemet som skal konverteres
			kildesystem = System.objects.get(pk=system_id)

			try:
				Programvare.objects.get(programvarenavn=kildesystem.systemnavn)
				messages.warning(request, 'Programvare med navn %s finnes allerede' % kildesystem.systemnavn)
				resume = False
			except:
				resume = True

			if resume:
				#nytt programvareobjekt med kopierte verdier
				ny_programvare = Programvare.objects.create(
						programvarenavn=kildesystem.systemnavn,
						programvarekategori=kildesystem.programvarekategori,
						programvarebeskrivelse=kildesystem.systembeskrivelse,
						kommentar=kildesystem.kommentar,
						strategisk_egnethet=kildesystem.strategisk_egnethet,
						funksjonell_egnethet=kildesystem.funksjonell_egnethet,
						teknisk_egnethet=kildesystem.teknisk_egnethet,
						selvbetjening=kildesystem.selvbetjening,
						livslop_status=kildesystem.livslop_status,
					)
				for leverandor in kildesystem.systemleverandor.all():
					ny_programvare.programvareleverandor.add(leverandor)
				for kategori in kildesystem.systemkategorier.all():
					ny_programvare.kategorier.add(kategori)
				for programvaretype in kildesystem.systemtyper.all():
					ny_programvare.programvaretyper.add(programvaretype)
				ny_programvare.save()

				#nye programvarebruk per systembruk
				for systembruk in kildesystem.systembruk_system.all():
					ny_programvarebruk = ProgramvareBruk.objects.create(
							brukergruppe=systembruk.brukergruppe,
							programvare=ny_programvare,
							livslop_status=systembruk.livslop_status,
							kommentar=systembruk.kommentar,
							strategisk_egnethet=systembruk.strategisk_egnethet,
							funksjonell_egnethet=systembruk.funksjonell_egnethet,
							teknisk_egnethet=systembruk.teknisk_egnethet,
						)

				#registrere behandlinger på programvaren fra systemet
				for behandling in kildesystem.behandling_systemer.all():
					behandling.programvarer.add(ny_programvare)
					behandling.save()

				messages.success(request, 'Konvertere system til programvare. Ny programvare %s er opprettet' % ny_programvare.programvarenavn)

		except Exception as e:
			messages.warning(request, 'Konvertere system til programvare feilet med feilmelding %s' % e)

	utvalg_systemer = System.objects.filter(systemtyper=1)

	return render(request, 'system_tilprogramvare.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'systemer': utvalg_systemer,
	})



def adorgunit_detaljer(request, pk=None):
	#Vise informasjon om en konkret AD-OU
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import os

	if pk == None:
		root_str = os.environ["KARTOTEKET_LDAPROOT"]
		ou = ADOrgUnit.objects.get(distinguishedname=root_str)
		pk = ou.pk
	else:
		ou = ADOrgUnit.objects.get(pk=pk)

	groups = ADgroup.objects.filter(parent=pk).order_by(Lower('distinguishedname'))
	parent_str = ",".join(ou.distinguishedname.split(',')[1:])
	try:
		parent = ADOrgUnit.objects.get(distinguishedname=parent_str)
	except:
		parent = None
	children = ADOrgUnit.objects.filter(parent=pk).order_by(Lower('distinguishedname'))

	users = User.objects.filter(profile__ou=pk).order_by(Lower('first_name'))

	return render(request, 'ad_adorgunit_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"ou": ou,
		"groups": groups,
		"parent": parent,
		"children": children,
		"users": users,
	})



def ad_gruppeanalyse(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	brukernavn_str = request.POST.get('brukernavn', "").strip().lower()

	try:
		bruker = User.objects.get(username=brukernavn_str)
		brukers_grupper = ldap_users_securitygroups(bruker.username)
		brukers_unike_grupper = sorted(convert_distinguishedname_cn(brukers_grupper))
	except:
		#print("ad_gruppeanalyse: Brukernavn finnes ikke")
		brukers_unike_grupper = None


	sikkerhetsgrupper_str = request.POST.get('sikkerhetsgrupper', "")
	sikkerhetsgrupper = []
	feilede_oppslag = []
	sikkerhetsgrupper_oppsplittet = re.findall(r"([^,;\n\r]+)", sikkerhetsgrupper_str) # alt mellom tegn som typisk brukes for å splitte unike ting.

	for gr in sikkerhetsgrupper_oppsplittet:
		stripped_gr = gr.strip()
		if "\\" in stripped_gr:
			stripped_gr = stripped_gr.split("\\")[1]
		try:
			sikkerhetsgrupper.append(ADgroup.objects.get(common_name=stripped_gr))
		except:
			feilede_oppslag.append(stripped_gr)

	utnostede_grupper = []
	for gr in sikkerhetsgrupper:
		utnostede_grupper += adgruppe_utnosting(gr)

	utnostede_grupper_ant_medlemmer = 0
	for gr in utnostede_grupper:
		utnostede_grupper_ant_medlemmer += gr.membercount


	if brukers_unike_grupper and utnostede_grupper:
		set_brukers_grupper = set(brukers_unike_grupper)
		set_sikkerhetsgruppeutnosting = [g.common_name for g in utnostede_grupper]
		sammenfallende = set_brukers_grupper.intersection(set_sikkerhetsgruppeutnosting)
	else:
		sammenfallende = None

	context = {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'form_brukernavn': brukernavn_str,
		'form_sikkerhetsgrupper': sikkerhetsgrupper_str,
		'brukers_unike_grupper': brukers_unike_grupper,
		'feilede_oppslag': feilede_oppslag,
		'unike_utnostede_grupper': utnostede_grupper,
		'sammenfallende': sammenfallende,
		'utnostede_grupper_ant_medlemmer': utnostede_grupper_ant_medlemmer,
	}
	return render(request, 'ad_gruppeanalyse.html', context)



def adgruppe_graf(request, pk):
	#Vise en graf over hvordan grupper er nøstet nedover fra en gitt gruppe
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import math
	morgruppe = ADgroup.objects.get(pk=pk)

	avhengigheter_graf = {"nodes": [], "edges": []}
	nye_grupper = []
	ferdige = []

	maks_grense = int(request.GET.get('maks_grense', 50))  # strip removes trailing and leading space
	grense = 0

	def define_color(gruppe):
		if gruppe.from_prk:
			return "#3bc319"
		else:
			return "#da3747"

	def define_size(gruppe):
		minimum = 25
		if gruppe.membercount > 0:
			adjusted_member_count = minimum + (20 * math.log(gruppe.membercount, 10))
			return ("%spx" % adjusted_member_count)
		else:
			return ("%spx" % minimum)

	def registrere_gruppe(gruppe):
		if gruppe not in ferdige:
			size = define_size(gruppe)
			avhengigheter_graf["nodes"].append(
					{"data": {
							"parent": '',
							"id": gruppe.pk,
							"name": gruppe.short(),
							"shape": "triangle",
							"size": size,
							"color": "#202020"
						},
					})
			ferdige.append(gruppe.pk)

		members = human_readable_members(json.loads(gruppe.member), onlygroups=True)
		for m in members["groups"]:
			color = define_color(m)
			size = define_size(m)
			if m not in ferdige and m.parent != None:
				nonlocal grense
				if grense < maks_grense:
					nye_grupper.append(m)
					grense += 1
				#print("added %s" % m)

				avhengigheter_graf["nodes"].append(
						{"data": {
							"parent": m.parent.pk,
							"id": m.pk,
							"name": m.display_name,
							"shape": "ellipse",
							"color": color,
							"size": size,
							"href": reverse('adgruppe_detaljer', args=[m.pk])
							}
						})
				avhengigheter_graf["edges"].append(
						{"data": {
							"source": gruppe.pk,
							"target": m.pk,
							"linestyle": "solid"
							}
						})
				ferdige.append(m.pk)

	registrere_gruppe(morgruppe)

	while nye_grupper:
		g = nye_grupper.pop()
		#print("removed %s" % g)
		registrere_gruppe(g)

	return render(request, 'ad_graf.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'avhengigheter_graf': avhengigheter_graf,
		'morgruppe': morgruppe,
		'maks_grense': maks_grense,
		'grense': grense,
	})



def adgruppe_detaljer(request, pk):
	#Vise informasjon om en konkret AD-gruppe
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	render_anyway = True if (request.GET.get('alt') == "ja") else False
	render_limit = 300
	rendered = False
	gruppe = ADgroup.objects.get(pk=pk)

	member = {}
	memberof = {}

	member_decoded = json.loads(gruppe.member)
	if (len(member_decoded) <= render_limit) or render_anyway:
		member = human_readable_members(member_decoded)
		rendered = True

	memberof = human_readable_members(json.loads(gruppe.memberof))

	return render(request, 'ad_adgruppe_detaljer.html', {
		"gruppe": gruppe,
		"member": member,
		"memberof": memberof,
		"render_anyway": render_anyway,
		"render_limit": render_limit,
		"rendered": rendered,
	})



def virksomhet_adgruppe_detaljer(request):
	#Vise informasjon om en konkret AD-gruppe for en enkelt virksomhet
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	try:
		virksomhetsforkotelse = request.user.profile.virksomhet_innlogget_som.virksomhetsforkortelse

	except:
		return render(request, 'ad_analyse.html', {
			'request': request,
			'required_permissions': formater_permissions(required_permissions),
		})

	valgt_gruppe = None
	valgt_gruppe_medlemmer = None
	valg_grupper = None
	search_term = ""

	search_term_raw = request.GET.get("search_term", False)
	if search_term_raw:
		valg_grupper = ADgroup.objects.filter(Q(distinguishedname__icontains=search_term_raw) | Q(display_name__icontains=search_term_raw))
		search_term = search_term_raw

	valgt_gruppe = request.GET.get("valgt_gruppe", False)
	if valgt_gruppe:

		gruppe = ADgroup.objects.get(pk=valgt_gruppe)
		members = json.loads(gruppe.member)
		filtrerte_medlemmer = set()
		for m in members:
			if virksomhetsforkotelse in m:
				filtrerte_medlemmer.add(m)

		members = human_readable_members(list(filtrerte_medlemmer))

		valgt_gruppe = gruppe
		valgt_gruppe_medlemmer = members
		search_term = gruppe

	return render(request, 'virksomhet_adgruppe_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"valg_grupper": valg_grupper,
		"valgt_gruppe": valgt_gruppe,
		"valgt_gruppe_medlemmer": valgt_gruppe_medlemmer,
		"search_term": search_term,
		"virksomhetsforkotelse": virksomhetsforkotelse,
	})



def ad_analyse(request):
	#Vise informasjon om tomme ADgrupper, AD-grupper ikke fra PRK osv.
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	antall_alle_grupper = ADgroup.objects.all().count()
	maks = int(request.GET.get('antall', 0))
	adgrupper_tomme = ADgroup.objects.filter(membercount__lte=maks)
	antall_tomme = len(adgrupper_tomme)

	return render(request, 'ad_analyse.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"adgrupper_tomme": adgrupper_tomme,
		"maks": maks,
		"antall_alle_grupper": antall_alle_grupper,
		"antall_tomme": antall_tomme,
	})


def rapport_ad_adgrupper(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	antall_adgr_tid = []
	logs = ApplicationLog.objects.filter(event_type="AD group-import", message__startswith="Det tok")
	for log in logs:
		antall_adgr_tid.append({"label": log.opprettet.strftime("%b %y"), "value": float(re.search(r'sekunder\. (\d+) treff', log.message, re.I).groups()[0])})


	return render(request, 'rapport_ad_adgrupper.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'antall_adgr_tid': antall_adgr_tid,
	})



def alle_adgrupper(request):
	#Vise informasjon om AD-grupper
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space
	if len(search_term) > 1:
		if search_term[0:3] == "CN=":
			search_term = search_term[3:]
		search_term = search_term.split(",")[0]
		adgrupper = ADgroup.objects.filter(Q(common_name__icontains=search_term) | Q(display_name__icontains=search_term) | Q(description__icontains=search_term))
		for g in adgrupper:
			members = json.loads(g.member)
			g.member_count = len(members)
	else:
		adgrupper = ADgroup.objects.none()

	return render(request, 'ad_adgrupper_sok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		"adgrupper": adgrupper,
		"search_term": search_term,
	})



def maskin_sok(request):
	#Søke opp hostnavn
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	hits = []
	misses = []
	query = request.POST.get('search_term', '').strip()
	if query != "":
		#servers = re.findall(r'\w+',search_term)
		servers = query.split("\n")
		for server in servers:
			try:
				match = CMDBdevice.objects.filter(comp_name__iexact=server.strip())
				for m in match.all():
					hits.append(m)
			except:
				misses.append(server.strip())

	return render(request, 'cmdb_maskin_sok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'query': query,
		'hits': hits,
		'misses': misses,
	})



def alle_ip(request):
	#Søke opp IP-adresser, både mot CMDB maskiner og via live dns-query
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	import ipaddress

	search_term = request.POST.get('search_term', '').strip()  # strip removes trailing and leading space
	host_matches = []
	network_matches = []
	not_ip_addresses = []

	if search_term != "":
		search_term = search_term.replace('\"','').replace('\'','').replace(':',' ').replace('/', ' ').replace('\\', ' ') # dette vil feile for IPv6, som kommer på formatet [xxxx:xxxx::xxxx]:port
		search_terms = re.findall(r"([^,;\t\s\n\r]+)", search_term)
		search_terms = set(search_terms)

		for term in search_terms:
			try:
				matches = NetworkIPAddress.objects.filter(ip_address=term)
				host_matches.extend(matches)
			except:
				pass

			try:
				matches = NetworkContainer.objects.filter(ip_address=term)
				network_matches.extend(matches)
			except:
				pass

			not_ip_addresses.append(term)
			continue  # skip this term

	return render(request, 'cmdb_ip_sok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'host_matches': host_matches,
		'network_matches': network_matches,
		'search_term': search_term,
		'not_ip_addresses': not_ip_addresses,
	})


"""
def ad_prk_sok(request):
		search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space
		search_term = search_term.replace(",DC=oslofelles,DC=oslo,DC=kommune,DC=no","")


		"CN=DS-BRE_OKNMI_BUDSJ_BUDSJFELL_IS,OU=BRE,OU=Tilgangsgrupper,OU=OK,DC=oslofelles,DC=oslo,DC=kommune,DC=no"
		"ou=DS-BRE_OKNMI_BUDSJ_BUDSJFELL_IS,ou=BRE,ou=Tilgangsgrupper,ou=OK"

		return render(request, 'ad_prk_sok.html', {
			'request': request,
		'required_permissions': formater_permissions(required_permissions),
			'search_term': search_term,
		})
"""


def prk_skjema(request, skjema_id):
	#Bla i PRK-skjemaer, vise et konkret skjema
	required_permissions = ['systemoversikt.view_prkvalg']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space
	skjema = PRKskjema.objects.get(pk=skjema_id)

	if search_term:
		valg = PRKvalg.objects.filter(skjemanavn=skjema).filter(virksomhet__virksomhetsforkortelse=search_term).order_by("gruppering")
	else:
		valg = PRKvalg.objects.filter(skjemanavn=skjema).order_by("gruppering")

	return render(request, 'prk_vis_skjema.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'skjema': skjema,
		'valg': valg,
	})



def prk_browse(request):
	#Bla i PRK-skjemaer
	required_permissions = ['systemoversikt.view_prkvalg']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space

	if search_term:
		skjema = PRKskjema.objects.filter(skjemanavn__icontains=search_term)
	else:
		skjema = PRKskjema.objects.all()

	skjema = skjema.order_by('skjematype', 'skjemanavn')

	return render(request, 'prk_bla.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'skjema': skjema,
		'search_term': search_term,
	})



def alle_prk(request):
	#Søke og vise PRK-skjemaer
	required_permissions = ['systemoversikt.view_prkvalg']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space

	if (search_term == "__all__"):
		skjemavalg = PRKvalg.objects
	elif len(search_term) < 2: # if one or less, return nothing
		skjemavalg = PRKvalg.objects.none()
	else:
		skjemavalg = PRKvalg.objects.filter(
				Q(valgnavn__icontains=search_term) |
				Q(beskrivelse__icontains=search_term) |
				Q(gruppering__feltnavn__icontains=search_term) |
				Q(skjemanavn__skjemanavn__icontains=search_term) |
				Q(gruppenavn__icontains=search_term)
		)

	skjemavalg = skjemavalg.order_by('skjemanavn__skjemanavn', 'gruppering__feltnavn')

	return render(request, 'prk_skjema_sok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'search_term': search_term,
		'skjemavalg': skjemavalg,
	})



def alle_klienter(request):
	#Søke og vise alle klienter
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('device_search_term', '').strip()  # strip removes trailing and leading space

	if search_term == '':
		maskiner = None
	elif search_term == '__all__':
		maskiner = CMDBdevice.objects.filter(device_type="KLIENT")
	else:
		maskiner = CMDBdevice.objects.filter(device_type="KLIENT").filter(Q(comp_name__icontains=search_term) | Q(comp_os_readable__icontains=search_term) | Q(client_model_id__icontains=search_term) )

	alle_cmdb_klienter = CMDBdevice.objects.filter(device_type="KLIENT").count()


	# klargjøring for statistikk
	if maskiner == None:
		stat_maskiner = CMDBdevice.objects.all()
	else:
		stat_maskiner = maskiner

	maskiner_os_stats = stat_maskiner.filter(device_type="KLIENT").values('comp_os_readable').annotate(Count('comp_os_readable'))
	maskiner_os_stats = sorted(maskiner_os_stats, key=lambda os: os['comp_os_readable__count'], reverse=True)

	maskiner_model_stats = stat_maskiner.filter(device_type="KLIENT").values('client_model_id').annotate(Count('client_model_id'))
	maskiner_model_stats = sorted(maskiner_model_stats, key=lambda os: os['client_model_id__count'], reverse=True)

	if maskiner != None:
		maskiner = maskiner.order_by('comp_name')

	return render(request, 'cmdb_maskiner_klienter.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'maskiner': maskiner,
		'device_search_term': search_term,
		'alle_cmdb_klienter': alle_cmdb_klienter,
		'maskiner_os_stats': maskiner_os_stats,
		'maskiner_model_stats': maskiner_model_stats,

	})



def cmdb_internetteksponerte_servere(request):
	#Søke og vise alle maskiner
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	dager_gamle = 30
	tidsgrense = datetime.date.today() - datetime.timedelta(days=dager_gamle)
	servere = CMDBdevice.objects.filter(eksternt_eksponert_dato__gte=tidsgrense).order_by("-eksternt_eksponert_dato")

	return render(request, 'cmdb_internetteksponerte_servere.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'servere': servere,
	})



def alle_servere(request):
	#Søke og vise alle maskiner
	required_permissions = ['systemoversikt.view_cmdbdevice']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('device_search_term', '').strip()  # strip removes trailing and leading space

	if search_term == '':
		maskiner = None
	elif search_term == '__all__':
		maskiner = CMDBdevice.objects.filter(device_type="SERVER")
	else:
		maskiner = CMDBdevice.objects.filter(device_type="SERVER").filter(Q(comp_name__icontains=search_term) | Q(comp_os_readable__iexact=search_term) | Q(service_offerings__navn__icontains=search_term)).order_by('comp_name')

	maskiner_stats = CMDBdevice.objects.filter(device_type="SERVER").values('comp_os_readable').annotate(Count('comp_os_readable'))
	maskiner_stats = sorted(maskiner_stats, key=lambda os: os['comp_os_readable__count'], reverse=True)

	vis_detaljer = True if request.GET.get('details') == "show" else False

	return render(request, 'cmdb_maskiner_servere.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'maskiner': maskiner,
		'device_search_term': search_term,
		'maskiner_stats': maskiner_stats,
		'vis_detaljer': vis_detaljer,
	})



def valgbarekategorier(request):
	#Vise noen linker knyttet til admin-panel. Valgfelt brukt i skjema.
	required_permissions = None

	return render(request, 'cmdb_valgbarekategorier.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})




def alle_databaser(request):
	#Søke og vise alle databaser
	required_permissions = ['systemoversikt.view_cmdbdatabase']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space

	if search_term == "__all__":
		databaser = CMDBdatabase.objects.filter(db_operational_status=1)
	elif len(search_term) < 2: # if one or less, return nothing
		databaser = CMDBdatabase.objects.none()
	else:
		databaser = CMDBdatabase.objects.filter(db_operational_status=1).filter(
				Q(db_database__icontains=search_term) |
				Q(sub_name__navn__icontains=search_term) |
				Q(db_version__icontains=search_term)
			)

	databaser = databaser.order_by('db_database')

	for d in databaser:
		try:
			server_str = d.db_comments.split("@")[1]
		except:
			server_str = None
		d.server_str = server_str # dette legger bare til et felt. Vi skriver ingen ting her.

	def cmdb_os_stats(maskiner):
		maskiner_stats = []
		for os in os_major:
			maskiner_stats.append({
				'major': os['db_version'],
				'count': os['db_version__count']
			})
		return sorted(maskiner_stats, key=lambda os: os['db_version'], reverse=True)

	databaseversjoner = CMDBdatabase.objects.filter(db_operational_status=True).values('db_version').distinct().annotate(Count('db_version'))
	databasestatistikk = []
	for versjon in databaseversjoner:
		if versjon["db_version"] == "":
			versjon["db_version"] = "ukjent"
		databasestatistikk.append({
				'versjon': versjon["db_version"],
				'antall': versjon["db_version__count"]
			})
	databasestatistikk = sorted(databasestatistikk, key=lambda v: v['antall'], reverse=True)

	return render(request, 'cmdb_databaser_sok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'databaser': databaser,
		'search_term': search_term,
		'databasestatistikk': databasestatistikk,
	})



def cmdb_forvaltere(request):
	required_permissions = ['systemoversikt.view_cmdbref', 'auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	relevant_business_services = CMDBbs.objects.filter(eksponert_for_bruker=True).order_by("navn", Lower("navn"))

	return render(request, 'cmdb_forvaltere.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'relevant_business_services': relevant_business_services,
	})



def alle_cmdbref(request):
	#Søke og vise alle business services (bs)
	required_permissions = ['systemoversikt.view_cmdbref', 'auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	search_term = request.GET.get('search_term', "").strip()

	if search_term == "__all__":
		cmdbref = CMDBRef.objects.all()#, parent_ref__operational_status=True)
	elif len(search_term) < 1:
		cmdbref = CMDBRef.objects.filter(operational_status=True).order_by("parent_ref__navn", Lower("navn"))
	else:
		cmdbref = CMDBRef.objects.filter(navn__icontains=search_term, parent_ref__navn__icontains=search_term)

	bs_uten_system = CMDBRef.objects.filter(operational_status=True).filter(Q(system=None))
	utfasede_bs = CMDBRef.objects.filter(operational_status=False).filter(~Q(system=None))

	skjult_server_db = []
	skjult_server_db_candidates = (CMDBbs.objects
			.filter(operational_status=True)
			.filter(eksponert_for_bruker=False)
			.distinct()
	)
	for bs in skjult_server_db_candidates:
		if bs.ant_devices() > 0 or bs.ant_databaser() > 0:
			skjult_server_db.append(bs)

	virksomhet_uke = Virksomhet.objects.get(virksomhetsforkortelse="UKE")
	#print(virksomhet_uke)
	# Alle plattformer knyttet til UKE som ikke er en underplattform (overordnet er None)
	system_uten_bs = (System.objects
			.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet_uke)
			.filter(driftsmodell_foreignkey__overordnet_plattform=None)
			.filter(service_offerings=None) # skal ikke ha kobling
			.filter(systemtyper__er_infrastruktur=False)
			.filter(ibruk=True)
			.order_by('driftsmodell_foreignkey')
			.distinct()
	)

	bs_utenfor_fip = (System.objects
			.filter(~Q(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet_uke))
			.filter(~Q(service_offerings=None)) # må ha kobling
			.filter(systemtyper__er_infrastruktur=False)
			.filter(ibruk=True)
			.order_by('driftsmodell_foreignkey')
			.distinct()
	)

	# telle servere med flere service offerings-koblinger
	from django.db.models import Count
	servere_flere_offerings = CMDBdevice.objects.annotate(num_offerings=Count('service_offerings')).filter(num_offerings__gt=1)
	servere_flereennto_offerings = CMDBdevice.objects.annotate(num_offerings=Count('service_offerings')).filter(num_offerings__gt=2)


	return render(request, 'cmdb_bs_sok.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'cmdbref': cmdbref,
		'search_term': search_term,
		'bs_uten_system': bs_uten_system,
		'utfasede_bs': utfasede_bs,
		'system_uten_bs': system_uten_bs,
		'bs_utenfor_fip': bs_utenfor_fip,
		'skjult_server_db': skjult_server_db,
		'servere_flere_offerings': servere_flere_offerings,
		'servere_flereennto_offerings': servere_flereennto_offerings,
	})



def cmdb_bss(request, pk):
	#Søke og vise maskiner og databaser tilknyttet en business service for et system
	required_permissions = ['systemoversikt.view_cmdbref']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	cmdbref = CMDBRef.objects.get(pk=pk)
	cmdbdevices = CMDBdevice.objects.filter(service_offerings=cmdbref)
	databaser = CMDBdatabase.objects.filter(sub_name=cmdbref)

	vlan_lagt_til = []
	def identifiser_vlan(network_ip_addresses):
		if len(network_ip_addresses) > 0:
			if len(network_ip_addresses[0].vlan.all()) > 0:
				mest_presise_vlan = network_ip_addresses[0].vlan.all().order_by('-subnet_mask')[0]
				nonlocal graf_data
				nonlocal vlan_lagt_til

				if mest_presise_vlan.comment not in vlan_lagt_til:
					graf_data["nodes"].append({"data": { "id": mest_presise_vlan.comment }})
					vlan_lagt_til.append(mest_presise_vlan.comment)
				return mest_presise_vlan.comment
		return "Ukjent VLAN"

	graf_data = {"nodes": [], "edges": []}
	graf_data["nodes"].append({"data": { "id": "root_parent", "name": cmdbref.navn, "shape": "ellipse", "color": "black" }})

	for server in cmdbdevices:
		graf_data["nodes"].append(
						{"data": {
							"parent": identifiser_vlan(server.network_ip_address.all()),
							"id": "server"+str(server.pk),
							"name": server.comp_name,
							"shape": "ellipse",
							"color": "#1668c1"
							}
						})
		graf_data["edges"].append(
						{"data": {
							"source": "server"+str(server.pk),
							"target": "root_parent",
							"linestyle": "solid",
							"linecolor": "#1668c1",
							}
						})

	for db in databaser:
		#try:
		dbserver = CMDBdevice.objects.get(comp_name=db.db_server)
		network_ip_address = dbserver.network_ip_address.all()
		#except:
		#	network_ip_address = []
		graf_data["nodes"].append(
						{"data": {
							"parent": identifiser_vlan(network_ip_address),
							"id": "db"+str(db.pk),
							"name": db.db_database,
							"shape": "diamond",
							"color": "#d35215" }
						})
		graf_data["edges"].append(
						{"data": {
							"source": "db"+str(db.pk),
							"target": "root_parent",
							"linestyle": "solid",
							"linecolor": "#d35215",
							}
						})


	backup_inst = CMDBbackup.objects.filter(device__service_offerings=cmdbref)

	return render(request, 'cmdb_maskiner_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'cmdbref': [cmdbref],
		'cmdbdevices': cmdbdevices,
		'databaser': databaser,
		'graf_data': graf_data,
		'backup_inst': backup_inst,
	})


def cmdb_bs_disconnect(request):
	# frikoble alle system - business service-koblinger
	required_permissions = ['systemoversikt.delete_system'] # kun administrator-rollen
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	#for service in CMDBbs.objects.all():
	#	service.systemreferanse = None
	#	service.save()

	from django.http import HttpResponseRedirect
	return HttpResponseRedirect(reverse('alle_cmdbref_sok'))


def alle_avtaler(request, virksomhet=None):
	#Vise alle avtaler
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	avtaler = Avtale.objects.all()
	if virksomhet:
		virksomhet = Virksomhet.objects.get(pk=virksomhet)
		avtaler = avtaler.filter(Q(virksomhet=virksomhet) | Q(leverandor_intern=virksomhet))

	return render(request, 'avtale_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'avtaler': avtaler,
		'virksomhet': virksomhet,
	})



def avtaledetaljer(request, pk):
	#Vise detaljer for en avtale
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	avtale = Avtale.objects.get(pk=pk)

	return render(request, 'avtale_detaljer.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'avtale': avtale,
	})



def databehandleravtaler_virksomhet(request, pk):
	#Vise alle databehandleravtaler for en valgt virksomhet
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	virksomet = Virksomhet.objects.get(pk=pk)
	utdypende_beskrivelse = ("Viser databehandleravtaler for %s" % virksomet)
	avtaler = Avtale.objects.filter(virksomhet=pk).filter(avtaletype=1) # 1 er databehandleravtaler

	return render(request, 'avtale_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'avtaler': avtaler,
		'utdypende_beskrivelse': utdypende_beskrivelse,
	})



def alle_dpia(request):
	#Under utvikling: Vise alle DPIA-vurderinger
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	alle_dpia = DPIA.objects.all()

	return render(request, 'dpia_alle.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'alle_dpia': alle_dpia,
	})



def detaljer_dpia(request, pk):
	#Under utvikling: Vise metadata om en DPIA-vurdering
	required_permissions = ['systemoversikt.view_system']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	dpia = DPIA.objects.get(pk=pk)

	return render(request, 'detaljer_dpia.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'dpia': dpia,
	})



def ad(request):
	#Startside for LDAP/AD-spørringer
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	return render(request, 'ad_index.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
	})



def ad_details(request, name):
	#Søke opp en eksakt CN i AD
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	runtime_t0 = time.time()
	ldap_filter = ('(cn=%s)' % name)
	result = ldap_get_details(name, ldap_filter, request)
	runtime_t1 = time.time()
	logg_total_runtime = runtime_t1 - runtime_t0
	messages.success(request, 'Dette søket tok %s sekunder' % round(logg_total_runtime, 1))

	return render(request, 'ad_details.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'result': result,
	})



def ad_exact(request, name):
	#Søke opp et eksakt DN i AD
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	runtime_t0 = time.time()
	ldap_filter = ('(distinguishedName=%s)' % name)
	result = ldap_get_details(name, ldap_filter, request)
	runtime_t1 = time.time()
	logg_total_runtime = runtime_t1 - runtime_t0
	messages.success(request, 'Dette søket tok %s sekunder' % round(logg_total_runtime, 1))

	return render(request, 'ad_details.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'result': result,
	})



def recursive_group_members(request, group):
	#Søke opp alle brukere rekursivt med tilgang til et DN i AD
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	runtime_t0 = time.time()
	result = ldap_get_recursive_group_members(group)
	runtime_t1 = time.time()
	logg_total_runtime = runtime_t1 - runtime_t0
	messages.success(request, 'Dette søket tok %s sekunder' % round(logg_total_runtime, 1))

	return render(request, 'ad_recursive.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'result': result,
	})



def tilgangsgrupper_api(request): #API
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="api_tilgangsgrupper").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
	try:
		owner = APIKeys.objects.get(key=key).navn
	except MultipleObjectsReturned:
		owner = "Flere treff på nøkkeleier"

	source_ip = get_client_ip(request)
	ApplicationLog.objects.create(event_type="API AD-grupper", message=f"Nøkkel tilhørende {owner} fra {source_ip}")

	if not "gruppenavn" in request.GET:
		return JsonResponse({"message": "Du må oppgi et gruppenavn som GET-variabel. ?gruppenavn=<navn>", "data": None}, safe=False, status=204)

	sporring = request.GET["gruppenavn"]
	try:
		adgruppe = ADgroup.objects.get(common_name__iexact=sporring)
	except MultipleObjectsReturned:
		return JsonResponse({"spørring": sporring, "status": "Spørringen gav flere treff. Dette burde ikke skje og bør undersøkes.", "data": []}, safe=False, status=204)
	except ObjectDoesNotExist:
		return JsonResponse({"spørring": sporring, "status": "Spørringen gav ingen treff. Vennligst oppgi et gyldig gruppenavn.", "data": []}, safe=False, status=204)
	except:
		return JsonResponse({"spørring": sporring, "status": "Ukjent feil", "data": []}, safe=False, status=500)
	data = {}

	def user_lookup(user):
		try:
			username = re.search(r'cn=([^\,]*)', user, re.I).groups()[0]
			user = User.objects.get(username__iexact=username)
			virksomhet = user.profile.virksomhet.virksomhetsforkortelse if user.profile.virksomhet else "Ukjent"
			return {
					"medlem": user.username,
					"status": "Treff på bruker i AD",
					"user_full_name": user.profile.displayName,
					"user_from_prk": user.profile.from_prk,
					"user_last_loggon": user.profile.lastLogonTimestamp,
					"user_passwd_expire": user.profile.userPasswordExpiry,
					"user_created": user.profile.whenCreated,
					"user_virksomhet": virksomhet,
					"user_description": user.profile.description,
					"user_disabled": user.profile.accountdisable,
					"user_passwd_never_expire": user.profile.dont_expire_password,
				}
		except ObjectDoesNotExist:
			return {
					"medlem": username,
					"status": "Ingen treff på bruker i AD. Kanskje objektet er en tilgangsgruppe?",
					"user_full_name": None,
					"user_from_prk": None,
					"user_last_loggon": None,
					"user_passwd_expire": None,
					"user_created": None,
					"user_virksomhet": None,
					"user_description": None,
					"user_disabled": None,
					"user_passwd_never_expire": None,
					}

	medlemmer = [user_lookup(user) for user in json.loads(adgruppe.member)]
	memberof = [user_lookup(mo) for mo in json.loads(adgruppe.memberof)]

	data['common_name'] = adgruppe.common_name
	data['distinguishedname'] = adgruppe.distinguishedname
	data['sist_oppdatert'] = adgruppe.sist_oppdatert
	data['description'] = adgruppe.description
	data['membercount'] = adgruppe.membercount
	data['from_prk'] = adgruppe.from_prk
	data['mail_enabled'] = adgruppe.mail
	data['medlemmer'] = medlemmer
	data['memberof'] = memberof

	resultat = {"spørring": sporring, "data": data}
	return JsonResponse(resultat, safe=False, status=200)



def systemer_api(request): #API

	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn="api_systemer").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False,status=403)

	data = []
	query = System.objects.filter(~Q(ibruk=False))
	for system in query:
		line = {}

		line["systemanvn"] = system.systemnavn
		line["alias"] = system.alias
		line["system_id"] = system.pk
		line["systemeierskapsmodell"] = system.get_systemeierskapsmodell_display()

		if system.systemeier:
			line["systemeier"] = system.systemeier.virksomhetsforkortelse
		if system.systemforvalter:
			line["systemforvalter"] = system.systemforvalter.virksomhetsforkortelse
		if system.driftsmodell_foreignkey:
			line["plattform"] = system.driftsmodell_foreignkey.navn

		kategoriliste = []
		for kategori in system.systemkategorier.all():
			kategoriliste.append(kategori.kategorinavn)
		line["systemkategorier"] = kategoriliste

		bruksliste = []
		for bruk in system.systembruk_system.all():
			bruksliste.append(bruk.brukergruppe.virksomhetsnavn)
		line["system_brukes_av"] = bruksliste

		data.append(line)

	resultat = {"antall systemer": len(query), "data": data}
	return JsonResponse(resultat, safe=False)



def system_excel_api(request, virksomhet_pk=None): #API

	if not request.method == "GET":
		raise Http404

	if not virksomhet_pk:
		return JsonResponse({"status": "Ingen virksomhet valgt", "data": None}, safe=False)

	virksomhet = Virksomhet.objects.get(pk=virksomhet_pk)

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="virksomhet_").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False,status=403)

	relevante_systemer = []

	systemer_ansvarlig_for = System.objects.filter(~Q(ibruk=False)).filter(Q(systemeier=virksomhet_pk) | Q(systemforvalter=virksomhet_pk))
	for system in systemer_ansvarlig_for:
		system.__midlertidig_type = "Eier eller forvalter"
		relevante_systemer.append(system)

	virksomhets_bruk = SystemBruk.objects.filter(brukergruppe=virksomhet_pk)
	for bruk in virksomhets_bruk:
		system = bruk.system
		if system not in relevante_systemer:
			system.__midlertidig_type = "Kun bruk"
			relevante_systemer.append(system)

	data = []
	for system in relevante_systemer:
		line = {}
		line["systemnavn"] = system.systemnavn
		line["alias"] = system.alias
		line["systembeskrivelse"] = system.systembeskrivelse
		line["type"] = system.__midlertidig_type
		line["systemeier"] = system.systemeier.virksomhetsforkortelse  if system.systemeier else "Ukjent"
		line["systemforvalter"] = system.systemforvalter.virksomhetsforkortelse if system.systemforvalter else "Ukjent"
		line["livslop"] = system.get_livslop_status_display()
		line["driftsmodell"] = system.driftsmodell_foreignkey.navn if system.driftsmodell_foreignkey else "Ukjent"
		line["leverandor_system"] = [leverandor.leverandor_navn for leverandor in system.systemleverandor.all()]
		line["leverandor_appdrift"] = [leverandor.leverandor_navn for leverandor in system.applikasjonsdriftleverandor.all()]
		line["leverandor_basisdrift"] = [leverandor.leverandor_navn for leverandor in system.basisdriftleverandor.all()]
		line["teknisk_egnethet"] = system.get_teknisk_egnethet_display()
		line["strategisk_egnethet"] = system.get_strategisk_egnethet_display()
		line["funksjonell_egnethet"] = system.get_funksjonell_egnethet_display()
		data.append(line)

	status = "OK. Data for %s." % virksomhet.virksomhetsforkortelse
	resultat = {"status": status, "data": data}
	return JsonResponse(resultat, safe=False)



def iga_api(request): #API
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="iga").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False,status=403)

	data = []
	for s in System.objects.all():
		systeminfo = {}
		systeminfo["navn"] = s.systemnavn
		systeminfo["pk"] = s.id
		systeminfo["ibruk"] = s.er_ibruk()
		systeminfo["status_id"] = s.livslop_status
		systeminfo["status_tekst"] = s.get_livslop_status_display()
		systeminfo["sist_oppdatert"] = s.sist_oppdatert
		systeminfo["beskrivelse"] = s.systembeskrivelse
		systeminfo["systemeier"] = s.systemeier.virksomhetsforkortelse if s.systemeier else None
		systeminfo["systemeier_personer"] = [ansvarlig.brukernavn.email for ansvarlig in s.systemeier_kontaktpersoner_referanse.all()]
		systeminfo["systemforvalter"] = s.systemforvalter.virksomhetsforkortelse if s.systemforvalter else None
		systeminfo["systemforvalter_personer"] = [ansvarlig.brukernavn.email for ansvarlig in s.systemforvalter_kontaktpersoner_referanse.all()]
		systeminfo["driftsmodell"] = s.driftsmodell_foreignkey.navn if s.driftsmodell_foreignkey else None
		systeminfo["service_offerings"] = [offering.navn for offering in s.service_offerings.all()]
		data.append(systeminfo)

	return JsonResponse(data, safe=False)



def get_api_tilganger(request): #API
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="get_api_tilganger").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False,status=403)

	business_services = set()
	email = request.GET.get('email', '').strip()
	try:
		user = User.objects.get(email=email)
	except:
		return JsonResponse({"error": "No match for email address or no email address given. Please supply GET variable 'email' (?email=<>)."}, safe=False, content_type='application/json; charset=utf-8')

	for system in user.ansvarlig_brukernavn.system_systemeier_kontaktpersoner.all():
		if hasattr(system, "bs_system_referanse"):
			business_services.add(system.bs_system_referanse.navn)

	for system in user.ansvarlig_brukernavn.system_systemforvalter_kontaktpersoner.all():
		if hasattr(system, "bs_system_referanse"):
			business_services.add(system.bs_system_referanse.navn)

	result = {"email": email, "username": user.username, "business_services": list(business_services)}
	return JsonResponse(result, safe=False)


# denne er ikke lenger i bruk
"""
def csirt_maskinlookup_api(request): #API
	#ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message=f"Innkommende kall fra {get_client_ip(request)}")
	if not request.method == "GET":
		#ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message="Feil: HTTP metode var ikke GET")
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="csirt_ipsok").values_list("key", flat=True)
	if not key in list(allowed_keys):
		ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message="Feil eller tom API-nøkkel")
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False,status=403)

	from django.core.exceptions import ObjectDoesNotExist

	maskin_string = request.GET.get('server', '').strip()
	if maskin_string == '':
		ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message="Ingen treff på tomt servernavn")
		return JsonResponse({"error": "Servernavn er ikke oppgitt. Send som GET-variabel 'server'"}, safe=False)

	try:
		server_match = CMDBdevice.objects.get(comp_name=maskin_string)
	except ObjectDoesNotExist:
		try:
			alias_string = DNSrecord.objects.get(dns_name=maskin_string).dns_target
			server_match = CMDBdevice.objects.get(comp_name=alias_string)
			ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message=f"Ingen treff på {maskin_string}, men treff på {alias_string}")
		except:
			ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message=f"Ingen treff på {maskin_string}")
			return JsonResponse({"error": "Ingen treff på servernavn"}, safe=False)

	try:
		business_sub_service = server_match.sub_name.navn
	except:
		business_sub_service = ""
	try:
		business_service = server_match.sub_name.parent_ref.navn
	except:
		business_service = ""
	try:
		systemnavn = server_match.sub_name.system.systemnavn
	except:
		systemnavn = ""
	try:
		systemalias = server_match.sub_name.system.alias
	except:
		systemalias = ""
	try:
		systemeier = server_match.sub_name.system.systemeier.virksomhetsforkortelse
	except:
		systemeier = ""
	try:
		systemforvalter = server_match.sub_name.system.systemforvalter.virksomhetsforkortelse
	except:
		systemforvalter = ""
	try:
		systemforvaltere = [ansvarlig.brukernavn.email for ansvarlig in server_match.sub_name.system.systemforvalter_kontaktpersoner_referanse.all()]
	except:
		systemforvaltere = []

	data = {
		"query": maskin_string,
		"hostname": server_match.comp_name,
		"os": server_match.comp_os_readable,
		"ip_address": server_match.comp_ip_address,
		"business_sub_service": business_sub_service,
		"business_service": business_service,
		"system": {
			"systemnavn": systemnavn,
			"systemalias": systemalias,
			"systemeier": systemeier,
			"systemforvalter": systemforvalter,
			"systemforvaltere": systemforvaltere,
		}
	}

	ApplicationLog.objects.create(event_type="API CSIRT maskin-søk", message=f"Vellykket kall mot {maskin_string}")
	return JsonResponse(data, safe=False)
"""


def csirt_iplookup_api(request):
	ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message=f"Innkommende kall fra {get_client_ip(request)}")
	if not request.method == "GET":
		ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message="Feil: HTTP metode var ikke GET")
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="vulnapp").values_list("key", flat=True)
	if not key in list(allowed_keys) and not os.environ['THIS_ENV'] == "TEST":
		ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message="Feil eller tom API-nøkkel")
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False,status=403)

	from django.core.exceptions import ObjectDoesNotExist
	import ipaddress

	ip_string = request.GET.get('ip', '').strip()
	port_string = request.GET.get('port', '').strip()
	if ip_string == '':
		#ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message="Ingen treff på tom IP-adresse")
		return JsonResponse({"error": "Ingen IP-adresse oppgitt. Send som GET-variabel 'ip'"}, safe=False)
	try:
		ip = ipaddress.ip_address(ip_string)
	except ValueError:
		#ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message=f"Ingen treff på ugyldig IP-adresse {ip_string}")
		return JsonResponse({"error": "Ikke en gyldig IP-adresse"}, safe=False)


	if DNSrecord.objects.filter(ip_address=ip_string).count() <= 15:
		dns_match = [inst.dns_name for inst in DNSrecord.objects.filter(ip_address=ip_string).all()]
	else:
		dns_match = ["Flere enn 15"]

	try:
		ip_match = NetworkIPAddress.objects.get(ip_address=ip_string)

		vlan_match = ["%s subnet /%s: %s" % (inst.ip_address, inst.subnet_mask, inst.comment) for inst in ip_match.vlan.all()]
		vip_match = ["%s port %s" % (vip.vip_name, vip.port) for vip in ip_match.viper.all()]
		members = []

		for vip in ip_match.viper.all():
			if port_string != "":
				if vip.port != int(port_string):
					continue
			for pool in vip.nested_pool_members():

				for local_ip in pool.server.network_ip_address.all(): # Det er bare ét, men det er en mange-til-mangerelasjon
					#host_vlan.append(["%s (%s/%s)" % (v.comment, v.ip_address, v.subnet_mask) for v in local_ip.vlan.all()])
					domaint_vlan = local_ip.dominant_vlan()
					host_vlan = "%s (%s/%s)" % (domaint_vlan.comment, domaint_vlan.ip_address, domaint_vlan.subnet_mask)

					pool.server.eksternt_eksponert_dato = timezone.now()
					pool.server.save()

				members.append({
					"server": pool.server.comp_name,
					"host_ip": pool.ip_address,
					"external_vip": "%s port %s" % (vip.vip_name, vip.port),
					"server_vlan": host_vlan,
					"bss": [offering.navn for offering in pool.server.service_offerings.all()],
				})
		vip_pool_members = members

	except ObjectDoesNotExist:
		#ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message=f"Ingen treff på {ip_string}")
		return JsonResponse({"error": "Ingen treff på IP-adresse"}, safe=False)

	data = {
		"query_ip": ip_string,
		"query_port": port_string,
		"dns_matches": dns_match,
		"vip_matches": vip_match,
		"vip_pool_members": vip_pool_members,
		"matching_vlans": vlan_match,
	}

	source_ip = get_client_ip(request)
	ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message=f"Vellykket kall mot {ip_string} utført fra {source_ip}")
	return JsonResponse(data, safe=False)




def vav_akva_api(request): #API
	ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message=f"Innkommende kall fra {get_client_ip(request)}")
	if not request.method == "GET":
		ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message="Feil: HTTP metode var ikke GET")
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="akva_vav").values_list("key", flat=True)
	if not key in list(allowed_keys):
		ApplicationLog.objects.create(event_type="API Akva VAV", message="Feil eller tom API-nøkkel")
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	from systemoversikt.settings import SITE_SCHEME, SITE_DOMAIN

	data = []
	for b in SystemBruk.objects.filter(brukergruppe__virksomhetsforkortelse="VAV"):
		systeminfo = {}
		systeminfo["system_navn"] = b.system.systemnavn
		systeminfo["system_navn_visning"] = b.system.__str__()
		systeminfo["system_id"] = b.system.id
		systeminfo["ibruk"] = b.system.er_ibruk()
		systeminfo["livslop_status"] = b.system.livslop_status if b.system.livslop_status != None else 0
		systeminfo["livslop_status_visning"] = b.system.get_livslop_status_display()
		systeminfo["system_klassifisering"] = b.system.systemeierskapsmodell
		systeminfo["systemkategorier"] = [kategori.kategorinavn for kategori in b.system.systemkategorier.all()]
		systeminfo["sist_oppdatert"] = b.system.sist_oppdatert
		systeminfo["systemeier"] = b.system.systemeier.virksomhetsforkortelse if b.system.systemeier else None
		systeminfo["systemeier_personer"] = [ansvarlig.brukernavn.email for ansvarlig in b.system.systemeier_kontaktpersoner_referanse.all()]
		systeminfo["systemforvalter"] = b.system.systemforvalter.virksomhetsforkortelse if b.system.systemforvalter else None
		systeminfo["systemforvalter_seksjon"] = b.system.systemforvalter_avdeling_referanse.ou if b.system.systemforvalter_avdeling_referanse else None
		systeminfo["systemforvalter_personer"] = [ansvarlig.brukernavn.email for ansvarlig in b.system.systemforvalter_kontaktpersoner_referanse.all()]
		systeminfo["lokal_systemforvalter_personer"] = [ansvarlig.brukernavn.email for ansvarlig in b.systemforvalter_kontaktpersoner_referanse.all()]
		systeminfo["lokal_systemeier_personer"] = [ansvarlig.brukernavn.email for ansvarlig in b.systemeier_kontaktpersoner_referanse.all()]
		systeminfo["url_webportal"] = [url.domene for url in b.system.systemurl.all()]
		systeminfo["url_systemoversikt"] = SITE_SCHEME + "://" + SITE_DOMAIN + reverse('systemdetaljer', kwargs={'pk': b.system.pk})
		systeminfo["systembeskrivelse"] = b.system.systembeskrivelse if b.system.systembeskrivelse != None else ""
		systeminfo["lokal_systembeskrivelse"] = b.kommentar if b.kommentar != None else ""
		systeminfo["leverandor_applikasjon"] = [leverandor.leverandor_navn for leverandor in b.system.systemleverandor.all()]
		systeminfo["leverandor_applikasjonsdrift"] = [leverandor.leverandor_navn for leverandor in b.system.applikasjonsdriftleverandor.all()]
		systeminfo["leverandor_driftsmiljo"] = [leverandor.leverandor_navn for leverandor in b.system.basisdriftleverandor.all()]
		systeminfo["funksjonell_egnethet"] = b.system.funksjonell_egnethet
		systeminfo["funksjonell_egnethet_tekst"] = b.system.get_funksjonell_egnethet_display()
		systeminfo["teknisk_egnethet"] = b.system.teknisk_egnethet
		systeminfo["teknisk_egnethet_tekst"] = b.system.get_teknisk_egnethet_display()
		systeminfo["konfidensialitetsvurdering"] = b.system.sikkerhetsnivaa
		systeminfo["konfidensialitetsvurdering_tekst"] = b.system.get_sikkerhetsnivaa_display()
		systeminfo["superbrukere"] = b.system.superbrukere
		systeminfo["driftsplattform"] = b.system.driftsmodell_foreignkey.__str__() if b.system.driftsmodell_foreignkey else None
		data.append(systeminfo)

	source_ip = get_client_ip(request)
	ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message=f"Vellykket kall fra {source_ip}")
	return JsonResponse(data, safe=False)


@csrf_exempt
def api_known_exploited(request): #API
	event_type = "API known exploited"
	ApplicationLog.objects.create(event_type=event_type, message=f"Innkommende kall fra {get_client_ip(request)}")

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="vulnapp_knownex").values_list("key", flat=True)
	if not key in list(allowed_keys) and not os.environ['THIS_ENV'] == "TEST":
		ApplicationLog.objects.create(event_type=event_type, message="Feil eller tom API-nøkkel")
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)


	if request.method == 'POST':
		try:
			data = json.loads(request.body)
			data = data.replace("vulnapp.exploitedvulnerability", "systemoversikt.exploitedvulnerability")

			count = 0
			for deserialized_object in serializers.deserialize('json', data):
				obj = deserialized_object.object
				obj.save()
				count += 1

			print(f"Updated {count} known exploited CVEs")

			ApplicationLog.objects.create(event_type=event_type, message=f"Vellykket oppdatering fra {get_client_ip(request)}")
			return JsonResponse({'message': 'Thanks for the update!'})
		except json.JSONDecodeError:
			ApplicationLog.objects.create(event_type=event_type, message=f"Invalid JSON fra {get_client_ip(request)}")
			return JsonResponse({'error': 'Invalid JSON'}, status=400)

	ApplicationLog.objects.create(event_type=event_type, message=f"Invalid request method fra {get_client_ip(request)}")
	return JsonResponse({'error': 'Invalid request method'}, status=405)






def api_programvare(request): #API
	ApplicationLog.objects.create(event_type="API programvare", message=f"Innkommende kall fra {get_client_ip(request)}")
	if not request.method == "GET":
		ApplicationLog.objects.create(event_type="API programvare", message="Feil: HTTP metode var ikke GET")
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="vulnapp").values_list("key", flat=True)
	if not key in list(allowed_keys) and not os.environ['THIS_ENV'] == "TEST":
		ApplicationLog.objects.create(event_type="API CSIRT IP-søk", message="Feil eller tom API-nøkkel")
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	programvare = Programvare.objects.filter(til_cveoversikt_og_nyheter=True).values_list('programvarenavn', flat=True).distinct()
	programvarelev = Programvare.objects.filter(til_cveoversikt_og_nyheter=True).filter(~Q(programvareleverandor=None)).values_list('programvareleverandor__leverandor_navn', flat=True).distinct()

	data = {"programvare": list(programvare), "programvarelev": list(programvarelev)}
	#leverandorer = Leverandor.objects.values_list('leverandor_navn', flat=True).distinct()
	#systemer = System.objects.values_list('systemnavn', flat=True).distinct()
	ApplicationLog.objects.create(event_type="API programvare", message=f"Vellykket kall fra {get_client_ip(request)}")
	return JsonResponse(data, safe=False)



def behandlingsoversikt_api(request): #API
	ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message=f"Innkommende kall fra {get_client_ip(request)}")
	if not request.method == "GET":
		ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message="Feil: HTTP metode var ikke GET")
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="behandlingsoversikt").values_list("key", flat=True)
	if not key in list(allowed_keys):
		ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message="Feil eller tom API-nøkkel")
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	data = []
	for s in System.objects.all():
		systeminfo = {}
		systeminfo["system_navn"] = s.systemnavn
		systeminfo["system_navn_visning"] = s.__str__()
		systeminfo["system_id"] = s.id
		systeminfo["ibruk"] = s.er_ibruk()
		systeminfo["system_klassifisering"] = s.systemeierskapsmodell
		systeminfo["sist_oppdatert"] = s.sist_oppdatert
		systeminfo["systemeier"] = s.systemeier.virksomhetsforkortelse if s.systemeier else None
		systeminfo["systemeier_personer"] = [ansvarlig.brukernavn.email for ansvarlig in s.systemeier_kontaktpersoner_referanse.all()]
		systeminfo["systemforvalter"] = s.systemforvalter.virksomhetsforkortelse if s.systemforvalter else None
		systeminfo["systemforvalter_personer"] = [ansvarlig.brukernavn.email for ansvarlig in s.systemforvalter_kontaktpersoner_referanse.all()]
		data.append(systeminfo)

	source_ip = get_client_ip(request)
	ApplicationLog.objects.create(event_type="API Behandlingsoversikt", message=f"Vellykket kall fra {source_ip}")
	return JsonResponse(data, safe=False)



def csirt_api(request): #API
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="csirt").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False,status=403)

	data = []
	for s in System.objects.all():
		systeminfo = {}
		systeminfo["systemnavn"] = s.systemnavn
		systeminfo["systemalias"] = s.alias

		systeminfo["os"] = s.unike_server_os()

		systeminfo["applikasjoner"] = [a.programvarenavn for a in s.programvarer.all()]

		systeminfo["id"] = s.id
		systeminfo["systemeier"] = s.systemeier.virksomhetsforkortelse if s.systemeier else None
		systeminfo["systemforvalter"] = s.systemforvalter.virksomhetsforkortelse if s.systemforvalter else None
		data.append(systeminfo)

	return JsonResponse(data, safe=False)





def cmdb_api(request): #API
	# brukes for å samle inn faktureringsgrunnlag (koble servere til systemeier)
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="api_cmdb").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False,status=403)

	data = []
	# tar ikke med tykke klienter da disse 11k per nå bare vil støye ned
	query = CMDBRef.objects.filter(operational_status=True).filter(~Q(navn="OK-Tykklient"))
	for bss in query:
		line = {}
		line["business_subservice_navn"] = bss.navn
		line["business_subservice_billable"] = bss.u_service_billable
		line["business_service"] = bss.parent_ref.navn
		line["sist_oppdatert"] = bss.sist_oppdatert
		line["opprettet"] = bss.opprettet
		line["environment"] = bss.get_environment_display()
		line["busines_criticality"] = bss.kritikalitet
		line["service_availability"] = bss.u_service_availability
		line["service_operation_factor"] = bss.u_service_operation_factor
		line["service_complexity"] = bss.u_service_complexity
		if bss.parent_ref:
			if bss.system:
				system = bss.system
				line["tilknyttet_system"] = system.systemnavn if system else "Ikke koblet"
				line["systemeier"] = system.systemeier.virksomhetsforkortelse if system.systemeier else "Ikke oppgitt"
				line["systemforvalter"] = system.systemforvalter.virksomhetsforkortelse if system.systemforvalter else "Ikke oppgitt"
				line["plattform"] = system.driftsmodell_foreignkey.navn if system.driftsmodell_foreignkey else "Ikke oppgitt"
				line["er_infrastruktur"] = system.er_infrastruktur()
			else:
				line["tilknyttet_system"] = "Ikke koblet"
				line["systemeier"] = "Ukjent grunnet manglende systemkobling"
				line["systemforvalter"] = "Ukjent grunnet manglende systemkobling"
				line["plattform"] = "Ukjent grunnet manglende systemkobling"
				line["er_infrastruktur"] = "Ukjent grunnet manglende systemkobling"
		else:
			return("error")

		line["antall_servere"] = bss.ant_devices()

		serverliste = []
		for server in bss.devices.all():
			s = dict()
			s["server_navn"] = server.comp_name
			s["billable"] = server.billable
			s["server_os"] = server.comp_os
			s["server_ram"] = server.comp_ram
			if server.comp_disk_space:
				s["server_disk"] = server.comp_disk_space * 1000 * 1000  # ønskes oppgitt i megabyte (fra bytes)
			else:
				s["server_disk"] = None
			s["server_cpu_core_count"] = server.comp_cpu_core_count
			serverliste.append(s)

		line["servere"] = serverliste
		line["antall_databaser"] = bss.ant_databaser()
		databaseliste = []
		for database in bss.cmdbdatabase_sub_name.filter(db_operational_status=True):
			s = dict()
			s["navn"] = database.db_database
			s["server"] = database.db_server
			s["version"] = database.db_version
			s["billable"] = database.billable
			s["status"] = database.db_status
			s["datafilessizekb"] = database.db_u_datafilessizekb # Merk at dette faktisk er bytes!
			s["db_comments"] = database.db_comments
			databaseliste.append(s)

		line["databaser"] = databaseliste
		data.append(line)
		resultat = {"antall bss": len(query), "data": data}

	return JsonResponse(resultat, safe=False)



def cmdb_api_kompass(request): #API
	# brukes for å oppdatere Kompass med informasjon om drift (bss, systemer, maskiner osv.)
	if not request.method == "GET":
		raise Http404

	key = request.headers.get("key", None)
	allowed_keys = APIKeys.objects.filter(navn__startswith="api_cmdb_kompass").values_list("key", flat=True)
	if not key in list(allowed_keys):
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False,status=403)

	data = []
	query = CMDBbs.objects.filter(operational_status=True)#.filter(~Q(navn="OK-Tykklient"))
	for bs in query:
		line = {}
		line["business_service_operational_status"] = bool(bs.operational_status)
		line["business_service_name"] = bs.navn
		line["business_service_internal_ref"] = bs.pk
		line["business_service_external_ref"] = bs.bs_external_ref
		line["business_service_systemknytning_navn"] = bs.systemreferanse.systemnavn if bs.systemreferanse else None
		line["business_service_systemknytning_pk"] = bs.systemreferanse.pk if bs.systemreferanse else None

		bss_liste = []
		for bss in bs.cmdb_bss_to_bs.all():
			b = {}
			b["business_subservice_operational_status"] = bool(bss.operational_status)
			b["business_subservice_name"] = bss.navn
			b["business_subservice_environment"] = bss.get_environment_display()
			b["business_subservice_internal_ref"] = bss.pk
			b["business_subservice_external_ref"] = bss.bss_external_ref
			b["business_subservice_billable"] = bss.u_service_billable
			b["business_subservice_classification"] = bss.service_classification
			b["business_subservice_complexity"] = bss.u_service_complexity
			b["business_subservice_operation_factor"] = bss.u_service_operation_factor
			b["business_subservice_availability"] = bss.u_service_availability
			b["business_subservice_business_criticality"] = bss.kritikalitet
			b["business_subservice_business_criticality_str"] = bss.get_kritikalitet_display()
			b["business_subservice_comments"] = bss.comments
			bss_liste.append(b)

		line["Business_subservices"] = bss_liste
		data.append(line)

	resultat = {"antall business services": len(query), "data": data}
	return JsonResponse(resultat, safe=False)



def cmdb_firewall(request):
	required_permissions = ['systemoversikt.view_brannmurregel']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

	def firewall_loopup(term):
		return Brannmurregel.objects.filter(
				Q(source__icontains=search_term) |
				Q(destination__icontains=search_term) |
				Q(protocol__icontains=search_term) |
				Q(comment__icontains=search_term)
			)

	search_term_raw = request.GET.get('search_term', '')
	search_term = search_term_raw.strip()

	if search_term == "__ALL__":
		firewall_openings = Brannmurregel.objects.all()

	elif len(search_term) > 1:
		firewall_openings = firewall_loopup(search_term)

	else:
		firewall_openings = []

	return render(request, 'cmdb_brannmur.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'all_openings': firewall_openings,
		'brannmur_search_term': search_term_raw,
	})



#############
# UBW-modul #
#############

# Det viktigste med tilgangsstyringen her er integritet, slik at en eier av en enhet kan være sikker på at ingen andre har importert/endret på sine data.
def kvartal(date): # støttefunksjon
	try:
		kvartal = (date.month - 1) // 3 + 1 # // is floor division
		if kvartal in [1, 2, 3, 4]:
			return ("Q%s") % kvartal
	except:
		return "error"



def ubw_endreenhet(request, belongs_to):
	required_permissions = None
	from django.http import HttpResponseRedirect
	enhet = UBWRapporteringsenhet.objects.get(pk=belongs_to)
	if request.method == 'POST':
		form = UBWEnhetForm(data=request.POST, instance=enhet)
		if form.is_valid() and form.cleaned_data:
			if request.user in enhet.users.all(): # bare personer som allede er medlemmer kan endre nøkkel (og navn)
				e = form.save(commit=False)
				for user in enhet.users.all(): # vi endrer ikke på tilgangsstyring her, så vi kopierer den bare
					e.users.add(user)
				e.save()
				return HttpResponseRedirect(reverse('ubw_enhet', kwargs={'pk': enhet.pk}))
	else:
		form = UBWEnhetForm(instance=enhet)

	return render(request, 'ubw_ekstra.html', {
			'request': request,
			'required_permissions': required_permissions,
			'form': form,
			'enhet': enhet,
	})



def ubw_multiselect(request):
	from django.http import HttpResponseNotFound
	valgte = request.POST.getlist('selected_items', None)
	valgte_fakturaer = UBWFaktura.objects.filter(pk__in=[int(v) for v in valgte])
	required_permissions = None # Egen tilgangsstyring i logikk i koden

	# må finne ut hvilken enhet fakturaene tilhører. Alle må tilhøre samme enhet
	enhet = None
	for faktura in valgte_fakturaer:
		if enhet == None:
			pass
		else:
			if enhet != faktura.belongs_to:
				return HttpResponseNotFound("Alle fakturaer må tilhøre samme enhet")
		enhet = faktura.belongs_to

	# sjekker at bruker har tilgang til enheten for å gjøre endringer
	if enhet == None:
		return HttpResponseNotFound("Du må velge minst én post")
	if not request.user in enhet.users.all():
		return HttpResponseNotFound("Du må eie fakturaene for å kunne legge til metadata")

	form = UBWMetadataForm(
				belongs_to=enhet,
				data=request.POST,
				data_list=ubw_generer_ekstra_valg(enhet.pk),
			)

	submitted = request.GET.get('submitted', "nei")
	if request.method == 'POST' and form.is_valid() and submitted == "ja":

		# hvis det er metadata allerede registrert, dropper vi fakturaen. Ellers legger vil til samme innsendte metadata mot alle valgte faktura
		instance = form.save(commit=False)
		for faktura in valgte_fakturaer:
			if hasattr(faktura, "metadata_reference"):
				messages.warning(request, f"Faktura {faktura} er allerede registrert med metadata")
				for field in form.fields:
					if field == "periode_paalopt":
						continue # vi oppdaterer ikke dato på eksisterende metadata
					if getattr(instance, field) != None:
						setattr(faktura.metadata_reference, field, getattr(instance, field))
						faktura.metadata_reference.save()
						messages.success(request, f"Oppdaterte {field} til faktura {faktura} til {getattr(instance, field)}")
				continue

			instance.belongs_to = faktura
			instance.pk = None # triks for å få en ny instans. Ny pk tildeles automatisk.
			instance.save()
			messages.success(request, f"Opprettet metadata til faktura {faktura}")
			#print("lagrer %s" % instance)

		return HttpResponseRedirect(reverse('ubw_enhet', kwargs={'pk': enhet.pk}))

	return render(request, 'ubw_multiselect.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'post_data': valgte,
		'valgte_fakturaer': valgte_fakturaer,
		'form': form,
	})



def ubw_api(request, pk): #API
	supplied_key = request.headers.get("key", None)
	unit_key = UBWRapporteringsenhet.objects.get(pk=pk).api_key

	if unit_key != None and (not supplied_key == unit_key): # hvis ingen nøkkel er satt, er API åpent
		return JsonResponse({"message": "Missing or wrong key. Supply HTTP header 'key'", "data": None}, safe=False, status=403)

	import calendar
	enhet = UBWRapporteringsenhet.objects.get(pk=pk)
	faktura_eksport = []
	fakturaer = UBWFaktura.objects.filter(belongs_to=enhet).order_by('-ubw_voucher_date')
	for faktura in fakturaer:
		eksportdata = {}

		# noen felter er med vilje ikke tatt med. Rekkefølgen må være lik mellom faktura og estimat
		eksportdata["kilde"] = "UBW"
		eksportdata["UBW tab"] = str(faktura.ubw_tab_repr())
		eksportdata["UBW Kontonr"] = faktura.ubw_account
		eksportdata["UBW Kontonavn"] = faktura.ubw_xaccount
		eksportdata["UBW-periode (YYYYMM)"] = faktura.ubw_period
		eksportdata["UBW Koststednr"] = faktura.ubw_dim_1
		eksportdata["UBW Koststednavn"] = faktura.ubw_xdim_1
		eksportdata["UBW prosjektnr"] = faktura.ubw_dim_4
		eksportdata["UBW prosjektnavn"] = faktura.ubw_xdim_4
		eksportdata["UBW voucher_type"] = faktura.ubw_voucher_type
		eksportdata["UBW voucher_no"] = faktura.ubw_voucher_no
		eksportdata["UBW sequence_no"] = faktura.ubw_sequence_no
		eksportdata["UBW bilagsdato"] = faktura.ubw_voucher_date
		eksportdata["UBW leverandørnr"] = faktura.ubw_apar_id
		eksportdata["UBW leverandørnavn"] = faktura.ubw_xapar_id
		eksportdata["UBW beskrivelse"] = faktura.ubw_description
		try:
			eksportdata["UBW beløp"] = float(faktura.ubw_amount)
		except:
			eksportdata["UBW beløp"] = 0

		try:
			eksportdata["UBW budsjett"] = faktura.metadata_reference.budsjett_amount if faktura.metadata_reference else 0
		except:
			eksportdata["UBW budsjett"] = 0

		eksportdata["UBW Virksomhets-ID"] = faktura.ubw_client
		eksportdata["UBW sist oppdatert"] = faktura.ubw_last_update
		try:
			eksportdata["Kategori"] = faktura.metadata_reference.kategori.name
		except:
			eksportdata["Kategori"] = ""
		try:
			eksportdata["Kategori2"] = faktura.metadata_reference.ekstra_kategori.name
		except:
			eksportdata["Kategori2"] = ""
		try:
			eksportdata["Periode påløpt år"] = faktura.metadata_reference.periode_paalopt.year
		except:
			eksportdata["Periode påløpt år"] = "_"
		try:
			eksportdata["Periode påløpt måned"] = faktura.metadata_reference.periode_paalopt.month
		except:
			eksportdata["Periode påløpt måned"] = ""
		try:
			eksportdata["Periode påløpt kvartal"] = kvartal(faktura.metadata_reference.periode_paalopt)
		except:
			eksportdata["Periode påløpt kvartal"] = ""

		try:
			last_day_month = calendar.monthrange(faktura.metadata_reference.periode_paalopt.year,faktura.metadata_reference.periode_paalopt.month)[1] # returnerer f.eks. (1, 31), derfor [1] for å få den siste.
			eksportdata["Periode påløpt siste dag"] = "%s-%s-%s" % (faktura.metadata_reference.periode_paalopt.year, '{:02d}'.format(faktura.metadata_reference.periode_paalopt.month), last_day_month)
		except:
			eksportdata["Periode påløpt siste dag"] = ""

		try:
			leverandor = faktura.metadata_reference.leverandor
			if leverandor != None:
				eksportdata["Leverandør"] = leverandor
			else:
				eksportdata["Leverandør"] = faktura.ubw_xapar_id
		except:
			eksportdata["Leverandør"] = faktura.ubw_xapar_id
		try:
			eksportdata["Kommentar"] = faktura.metadata_reference.kommentar
		except:
			eksportdata["Kommentar"] = ""

		try:
			eksportdata["UBW artsgr2"] = faktura.ubw_artsgr2
		except:
			eksportdata["UBW artsgr2"] = ""

		try:
			eksportdata["UBW artsgr2 Teskt"] = faktura.ubw_artsgr2_text
		except:
			eksportdata["UBW artsgr2 Teskt"] = ""

		try:
			eksportdata["UBW kategori"] = faktura.ubw_kategori
		except:
			eksportdata["UBW kategori"] = ""

		try:
			eksportdata["UBW kategori Teskt"] = faktura.ubw_kategori_text
		except:
			eksportdata["UBW kategori Teskt"] = ""

		# ta vare på dette.
		faktura_eksport.append(eksportdata)

	# resten her handler om estimater. Vi trenger først noen tabeller å slå opp i der data faktisk ikke er registret på estimatet.
	# for å kunne fylle ut UBW Kontonavn
	ubw_kontonavn_oppslag = list(UBWFaktura.objects.filter(belongs_to=enhet).values_list('ubw_account', 'ubw_xaccount').distinct())
	#print(ubw_kontonavn_oppslag)

	# for å kunne fylle ut UBW Kontonavn
	ubw_koststednavn_oppslag = list(UBWFaktura.objects.filter(belongs_to=enhet).values_list('ubw_dim_1', 'ubw_xdim_1').distinct())
	#print(ubw_kontonavn_oppslag)

	# for å kunne fylle ut UBW Artsgr2
	ubw_artsgr2navn_oppslag = list(UBWFaktura.objects.filter(belongs_to=enhet).values_list('ubw_artsgr2', 'ubw_artsgr2_text').distinct())
	#print(ubw_artsgr2navn_oppslag)

	# for å kunne fylle ut UBW Kontonavn
	ubw_kategorinavn_oppslag = list(UBWFaktura.objects.filter(belongs_to=enhet).values_list('ubw_kategori', 'ubw_kategori_text').distinct())
	#print(ubw_kategorinavn_oppslag)

	def oppslag(verdi, oppslagsliste):
		for item in oppslagsliste:
			if item[0] == verdi:
				#print(item[1])
				return item[1]
		return "ukjent"

	estimat = UBWEstimat.objects.filter(belongs_to=enhet).filter(aktiv=True).order_by('-periode_paalopt')
	for e in estimat:
		eksportdata = {}

		# alle felter må være med for at PocketQuery (Confluence) skal forstå dataene og plassere dem i riktig rad.
		eksportdata["kilde"] = e.prognose_kategori
		eksportdata["UBW tab"] = ""
		eksportdata["UBW Kontonr"] = e.estimat_account
		eksportdata["UBW Kontonavn"] = oppslag(e.estimat_account, ubw_kontonavn_oppslag)
		eksportdata["UBW-periode (YYYYMM)"] = ""
		eksportdata["UBW Koststednr"] = e.estimat_dim_1
		eksportdata["UBW Koststednavn"] = oppslag(e.estimat_dim_1, ubw_koststednavn_oppslag)
		eksportdata["UBW prosjektnr"] = e.estimat_dim_4

		prosjektnavn = UBWFaktura.objects.filter(belongs_to=enhet).filter(ubw_dim_4=e.estimat_dim_4).values_list('ubw_xdim_4').distinct()
		try:
			eksportdata["UBW prosjektnavn"] = prosjektnavn[0][0]
		except:
			eksportdata["UBW prosjektnavn"] = ""
		eksportdata["UBW voucher_type"] = ""
		eksportdata["UBW voucher_no"] = ""
		eksportdata["UBW sequence_no"] = ""
		eksportdata["UBW bilagsdato"] = ""
		eksportdata["UBW leverandørnr"] = ""
		eksportdata["UBW leverandørnavn"] = ""
		eksportdata["UBW beskrivelse"] = e.ubw_description
		try: # i tilfelle noen glemmer å fylle ut et beløp i estimatet
			eksportdata["UBW beløp"] = float(e.estimat_amount)
		except:
			eksportdata["UBW beløp"] = 0
		try: # i tilfelle noen glemmer å fylle ut et beløp i estimatet
			eksportdata["UBW budsjett"] = float(e.budsjett_amount)
		except:
			eksportdata["UBW budsjett"] = 0

		eksportdata["UBW Virksomhets-ID"] = ""
		eksportdata["UBW sist oppdatert"] = ""
		try:
			eksportdata["Kategori"] = e.kategori.name
		except:
			eksportdata["Kategori"] = ""
		try:
			eksportdata["Kategori2"] = e.ekstra_kategori.name
		except:
			eksportdata["Kategori2"] = ""
		try:
			eksportdata["Periode påløpt år"] = e.periode_paalopt.year
		except:
			eksportdata["Periode påløpt år"] = ""
		try:
			eksportdata["Periode påløpt måned"] = e.periode_paalopt.month
		except:
			eksportdata["Periode påløpt måned"] = ""
		try:
			eksportdata["Periode påløpt kvartal"] = kvartal(e.periode_paalopt)
		except:
			eksportdata["Periode påløpt kvartal"] = ""
		try:
			last_day_month = calendar.monthrange(e.periode_paalopt.year,e.periode_paalopt.month)[1] # returnerer f.eks. (1, 31), derfor [1] for å få den siste.
			eksportdata["Periode påløpt siste dag"] = "%s-%s-%s" % (e.periode_paalopt.year, '{:02d}'.format(e.periode_paalopt.month), last_day_month)
		except:
			eksportdata["Periode påløpt siste dag"] = ""

		eksportdata["Leverandør"] = e.leverandor
		eksportdata["Kommentar"] = e.kommentar

		try:
			eksportdata["UBW artsgr2"] = e.ubw_artsgr2
		except:
			eksportdata["UBW artsgr2"] = ""

		eksportdata["UBW artsgr2 Tekst"] = oppslag(e.ubw_artsgr2, ubw_artsgr2navn_oppslag)

		try:
			eksportdata["UBW kategori"] = e.ubw_kategori
		except:
			eksportdata["UBW kategori"] = ""

		eksportdata["UBW kategori Tekst"] = oppslag(e.ubw_kategori, ubw_kategorinavn_oppslag)

		# ta vare på dette.
		faktura_eksport.append(eksportdata)

	return JsonResponse(faktura_eksport, safe=False)



def ubw_home(request):
	required_permissions = None
	enheter = UBWRapporteringsenhet.objects.all()

	return render(request, 'ubw_home.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'enheter': enheter,
	})



def ubw_enhet(request, pk):
	required_permissions = None

	import csv
	from decimal import Decimal
	enhet = UBWRapporteringsenhet.objects.get(pk=pk)
	kategorier = UBWFakturaKategori.objects.filter(belongs_to=enhet)

	def try_int(string):
		try:
			return int(string)
		except:
			return None

	def import_function(data):
		count_new = 0
		count_updated = 0
		for row in data:
			if row["Konto"] != None:
				#try:
				obj, created = UBWFaktura.objects.get_or_create(
					ubw_voucher_no=try_int(row["Bilagsnr"]),
					ubw_sequence_no=try_int(row["#"]),
					belongs_to=enhet,
					)
				if created:
					#print("ny opprettet")
					#messages.success(request, "Fant en ny rad..")
					er_ny = True
				else:
					#print("eksisterte, oppdaterer")
					#messages.success(request, "Prøver å oppdatere eksisterende..")
					er_ny = False


				#obj.belongs_to = enhet #UBWRapporteringsenhet
				obj.ubw_tab = row["T"] #CharField
				obj.ubw_account = try_int(row["Konto"]) #IntegerField
				obj.ubw_xaccount = row["Konto (T)"] #CharField
				obj.ubw_period = try_int(row["Periode"]) #IntegerField
				obj.ubw_dim_1 = try_int(row["Dim1"]) #IntegerField
				obj.ubw_xdim_1 = row["Dim1 (T)"] #CharField
				obj.ubw_dim_4 = try_int(row["Dim4"]) #IntegerField
				obj.ubw_xdim_4 = row["Dim4 (T)"] #CharField
				obj.ubw_voucher_type = row["BA"] #CharField
				#obj.ubw_voucher_no = try_int(row[""]) #IntegerField
				#obj.ubw_sequence_no = try_int(row[""]) #IntegerField
				obj.ubw_voucher_date = row["Bilagsdato"]
				obj.ubw_order_id = try_int(row["Linjenr"]) #IntegerField
				obj.ubw_apar_id = try_int(row["Resk.nr"]) #IntegerField
				obj.ubw_xapar_id = row["Resk.nr (T)"] #CharField
				obj.ubw_description = row["Tekst"] #TextField
				obj.ubw_amount = Decimal(row["Beløp"]) #DecimalField
				obj.ubw_apar_type = row["R"] #CharField
				obj.ubw_att_1_id = row["DM1"] #CharField
				obj.ubw_att_4_id = row["DM4"] #CharField
				obj.ubw_client = try_int(row["Firma"]) #IntegerField
				obj.ubw_last_update = row["Oppdatert"]
				obj.ubw_artsgr2 = row["Artsgr2"] #CharField
				obj.ubw_artsgr2_text = row["Artsgr2 (T)"] #CharField
				obj.ubw_kategori = try_int(row["Kategori"]) #IntegerField
				obj.ubw_kategori_text = row["Kategori (T)"] #CharField

				obj.save()
				if er_ny:
					count_new += 1
				else:
					count_updated += 1

				#except Exception as e:
				#	error_message = ("Kunne ikke importere: %s" % e)
				#	messages.warning(request, error_message)
				#	print(error_message)
			else:
				messages.warning(request, "Raden manglet beløp, ignorert")

		ferdig_melding = ("Importerte %s nye. Oppdaterte %s som eksisterte fra før." % (count_new, count_updated))
		messages.success(request, ferdig_melding)

	if request.user in enhet.users.all():

		import pandas as pd
		import numpy as np
		import xlrd

		if request.method == "POST":
			#try:
			file = request.FILES['fileupload'] # this is my file
			#print(file.name)
			uploaded_file = {"name": file.name, "size": file.size,}
			#if ".csv" in file.name:
			#	#print("CSV")
			#	decoded_file = file.read().decode('latin1').splitlines()
			#	data = list(csv.DictReader(decoded_file, delimiter=";"))
			#	# need to convert date string to date and amount to Decimal
			#	for line in data:
			#		line["voucher_date"] = datetime.datetime.strptime(line["last_update"], "%d.%m.%Y").date() #DateField
			#		line["last_update"] = datetime.datetime.strptime(line["last_update"], "%d.%m.%Y").date() #DateField
			#		line["amount"] = Decimal((line["amount"].replace(",",".")))

			if ".xlsx" in file.name:
				#print("Excel-import påstartet")
				dfRaw = pd.read_excel(io=file.read(), sheet_name=1)
				dfRaw = dfRaw.replace(np.nan, '', regex=True)
				#print(dfRaw)
				data = dfRaw.to_dict('records')

				#dfRaw["dateTimes"].map(lambda x: xlrd.xldate_as_tuple(x, datemode))
				#workbook = xlrd.open_workbook(file_contents=file.read())
				#datemode = workbook.datemode
				#sheet = workbook.sheet_by_index(0)
				#data = [sheet.row_values(rowx) for rowx in range(sheet.nrows)]
				#print(data)

				#data = list(csv.DictReader(decoded_file, delimiter=";"))

			#print("\n%s\n" % data)
			import_function(data)

			#except Exception as e:
			#	error_message = ("Kunne ikke lese fil: %s" % e)
			#	messages.warning(request, error_message)
			#	print(error_message)

		uploaded_file = None
		dager_gamle = int(request.GET.get("historikk", 365))
		tidsgrense = datetime.date.today() - datetime.timedelta(days=dager_gamle)
		gyldige_fakturaer = UBWFaktura.objects.filter(belongs_to=enhet).filter(ubw_voucher_date__gte=tidsgrense)
		nye_fakturaer = gyldige_fakturaer.filter(metadata_reference=None).order_by('-ubw_voucher_date')
		behandlede_fakturaer = gyldige_fakturaer.filter(~Q(metadata_reference=None)).order_by('-ubw_voucher_date')

		model = UBWFaktura
		domain = ("%s://%s") % (settings.SITE_SCHEME, settings.SITE_DOMAIN)

		return render(request, 'ubw_enhet.html', {
			'request': request,
			'required_permissions': formater_permissions(required_permissions),
			'enhet': enhet,
			'uploaded_file': uploaded_file,
			'nye_fakturaer': nye_fakturaer,
			'behandlede_fakturaer': behandlede_fakturaer,
			'model': model,
			'kategorier': kategorier,
			'domain': domain,
			'dager_gamle': dager_gamle,
		})
	else:
		messages.warning(request, 'Du har ikke tilgang på denne UBW-modulen. Logget inn?')
		return HttpResponseRedirect(reverse('home'))


"""
def check_belongs_to(user, enhet_id):
	try:
		e = UBWRapporteringsenhet.objects.get(pk=enhet)
		if user in e.users:
			return True
	except:
		pass
	return False
"""


def ubw_generer_ekstra_valg(belongs_to): # støttefunksjon
	data = []
	# trenger kategorien to ganger da den ene er verdi og den andre er visning. Like i dette tilfellet.
	leverandor_kategorier = list(UBWFaktura.objects.filter(belongs_to=belongs_to).values_list('ubw_xapar_id', 'ubw_xapar_id').distinct())
	data.append({'field': 'leverandor', 'choices': leverandor_kategorier})
	return data



def ubw_ekstra(request, faktura_id, pk=None):
	required_permissions = None
	faktura = UBWFaktura.objects.get(pk=faktura_id)
	enhet = faktura.belongs_to
	kategorier = UBWFakturaKategori.objects.filter(belongs_to=enhet)
	if request.user in enhet.users.all():

		if pk:
			instance = UBWMetadata.objects.get(pk=pk)
			form = UBWMetadataForm(
					instance=instance,
					belongs_to=faktura.belongs_to,
					data_list=ubw_generer_ekstra_valg(enhet.pk)
			)
		else:
			instance = None
			form = UBWMetadataForm(
					initial={'leverandor': faktura.ubw_xapar_id},
					belongs_to=faktura.belongs_to,
					data_list=ubw_generer_ekstra_valg(enhet.pk),
			)

		if request.method == 'POST':
			form = UBWMetadataForm(
					instance=instance,
					data=request.POST,
					belongs_to=faktura.belongs_to,
			)
			if form.is_valid():
				instance = form.save(commit=False)
				instance.belongs_to = faktura
				instance.save()
				return HttpResponseRedirect(reverse('ubw_enhet', kwargs={'pk': enhet.pk}))

		return render(request, 'ubw_ekstra.html', {
			'request': request,
			'required_permissions': formater_permissions(required_permissions),
			'form': form,
			'faktura': faktura,
			'enhet': enhet,
			'ekstra': True,
			'kategorier': kategorier,
		})



def ubw_kategori(request, belongs_to):
	required_permissions = None

	from django.http import HttpResponseRedirect
	enhet = UBWRapporteringsenhet.objects.get(pk=belongs_to)
	kategorier = UBWFakturaKategori.objects.filter(belongs_to=enhet)
	if request.method == 'POST':
		form = UBWFakturaKategoriForm(request.POST)
		if form.is_valid() and form.cleaned_data:
			if request.user in enhet.users.all():
				kategori = form.save(commit=False)
				kategori.belongs_to = enhet
				kategori.save()
				return HttpResponseRedirect(reverse('ubw_enhet', kwargs={'pk': enhet.pk}))
	else:
		form = UBWFakturaKategoriForm()

	return render(request, 'ubw_ekstra.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'form': form,
		'enhet': enhet,
		'kategori': True,
		'kategorier': kategorier,
	})



def ubw_my_estimates(request, enhet):
	if request.user in enhet.users.all():
		return UBWEstimat.objects.filter(belongs_to=enhet).order_by('-periode_paalopt')
	else:
		return UBWEstimat.objects.none()



def ubw_estimat_list(request, belongs_to):
	required_permissions = None

	enhet = get_object_or_404(UBWRapporteringsenhet, pk=belongs_to)
	kategorier = UBWFakturaKategori.objects.filter(belongs_to=enhet)
	estimat = ubw_my_estimates(request, enhet)
	model = UBWEstimat
	return render(request, 'ubw_estimat_list.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'estimat': estimat,
		'model': model,
		'enhet': enhet,
		'kategorier': kategorier,
	})



def save_ubw_estimat_form(request, belongs_to, form, template_name):
	data = dict()
	if request.method == 'POST':
		if form.is_valid():
			enhet = get_object_or_404(UBWRapporteringsenhet, pk=belongs_to)
			if request.user in enhet.users.all():
				i = form.save(commit=False)
				i.belongs_to = enhet
				i.save()
			else:
				messages.warning(request, 'Du har forsøkt å endre på noe du ikke har tilgang til!')

			data['form_is_valid'] = True
			estimat = ubw_my_estimates(request, enhet)
			data['html_estimat_list'] = render_to_string('ubw_estimat_partial_list.html', {
				'estimat': estimat,
			})
		else:
			data['form_is_valid'] = False
	context = {'form': form, 'belongs_to': belongs_to,}
	data['html_form'] = render_to_string(template_name, context, request=request)
	return JsonResponse(data)



def ubw_generer_estimat_valg(belongs_to):
	data = []

	# trenger kategorien to ganger da den ene er verdi og den andre er visning. Like i dette tilfellet.
	prognose_kategorier = list(UBWEstimat.objects.filter(belongs_to=belongs_to).values_list('prognose_kategori', 'prognose_kategori').distinct())
	data.append({'field': 'prognose_kategori', 'choices': prognose_kategorier})

	prognose_estimat_account = list(UBWFaktura.objects.filter(belongs_to=belongs_to).values_list('ubw_account', 'ubw_xaccount').distinct())
	data.append({'field': 'estimat_account', 'choices': prognose_estimat_account})

	prognose_estimat_dim_1 = list(UBWFaktura.objects.filter(belongs_to=belongs_to).values_list('ubw_dim_1', 'ubw_xdim_1').distinct())
	data.append({'field': 'estimat_dim_1', 'choices': prognose_estimat_dim_1})

	prognose_prosjektnummer = list(UBWFaktura.objects.filter(belongs_to=belongs_to).values_list('ubw_dim_4', 'ubw_xdim_4').distinct())
	data.append({'field': 'estimat_dim_4', 'choices': prognose_prosjektnummer})

	prognose_leverandor = list(UBWFaktura.objects.filter(belongs_to=belongs_to).values_list('ubw_xapar_id', 'ubw_xapar_id').distinct())
	data.append({'field': 'leverandor', 'choices': prognose_leverandor})

	prognose_ubw_artsgr2 = list(UBWFaktura.objects.filter(belongs_to=belongs_to).values_list('ubw_artsgr2', 'ubw_artsgr2_text').distinct())
	data.append({'field': 'ubw_artsgr2', 'choices': prognose_ubw_artsgr2})

	prognose_ubwkategori = list(UBWFaktura.objects.filter(belongs_to=belongs_to).values_list('ubw_kategori', 'ubw_kategori_text').distinct())
	data.append({'field': 'ubw_kategori', 'choices': prognose_ubwkategori})

	return data



def ubw_estimat_create(request, belongs_to):
	if request.method == 'POST':
		form = UBWEstimatForm(
				request.POST,
				data_list=ubw_generer_estimat_valg(belongs_to),
				belongs_to=belongs_to
		)
	else:
		form = UBWEstimatForm(data_list=ubw_generer_estimat_valg(belongs_to), belongs_to=belongs_to)
	return save_ubw_estimat_form(request, belongs_to, form, 'ubw_estimat_partial_create.html')



def ubw_estimat_update(request, belongs_to, pk):
	estimat = get_object_or_404(UBWEstimat, pk=pk)
	if request.method == 'POST':
		if request.user in estimat.belongs_to.users.all():
			form = UBWEstimatForm(
					request.POST, instance=estimat,
					data_list=ubw_generer_estimat_valg(belongs_to),
					belongs_to=belongs_to
			)
	else:
		form = UBWEstimatForm(
				instance=estimat,
				data_list=ubw_generer_estimat_valg(belongs_to),
				belongs_to=belongs_to
		)
	return save_ubw_estimat_form(request, belongs_to, form, 'ubw_estimat_partial_update.html')



def ubw_estimat_delete(request, pk): #API
	estimat = get_object_or_404(UBWEstimat, pk=pk)
	data = dict()
	if request.method == 'POST':
		if request.user in estimat.belongs_to.users.all():
			estimat.delete()
		else:
			messages.warning(request, 'Du har forsøkt å slette noe du ikke har tilgang til!')

		data['form_is_valid'] = True
		enhet = estimat.belongs_to
		estimat = ubw_my_estimates(request, enhet)
		data['html_estimat_list'] = render_to_string('ubw_estimat_partial_list.html', {
			'estimat': estimat
		})
	else:
		context = {'estimat': estimat}
		data['html_form'] = render_to_string('ubw_estimat_partial_delete.html', context, request=request)
	return JsonResponse(data)



def ubw_estimat_copy(request, pk): #API
	estimat = get_object_or_404(UBWEstimat, pk=pk)
	data = dict()
	if request.method == 'POST':
		if request.user in estimat.belongs_to.users.all():
			# ved å sette primary key til tom og lagre, opprettes en ny lik instans.
			estimat.pk = None
			estimat.save()
		else:
			messages.warning(request, 'Du har forsøkt å kopiere noe du ikke har tilgang til!')

		data['form_is_valid'] = True
		enhet = estimat.belongs_to
		estimat = ubw_my_estimates(request, enhet)
		data['html_estimat_list'] = render_to_string('ubw_estimat_partial_list.html', {
			'estimat': estimat
		})
	else:
		context = {'estimat': estimat}
		data['html_form'] = render_to_string('ubw_estimat_partial_copy.html', context, request=request)
	return JsonResponse(data)

###########
# UBW end #
###########