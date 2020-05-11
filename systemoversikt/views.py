# -*- coding: utf-8 -*-
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.core import serializers
from systemoversikt.models import *
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.db.models import Count
from django.template.loader import render_to_string
from django.db.models.functions import Lower
from django.db.models import Q
#from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponseBadRequest, JsonResponse
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.http import HttpResponseRedirect, HttpResponse
from django.conf import settings
import datetime
from django.urls import reverse
import json


FELLES_OG_SEKTORSYSTEMER = ("FELLESSYSTEM", "SEKTORSYSTEM")
SYSTEMTYPE_PROGRAMMER = "Selvstendig klientapplikasjon"

"""
Støttefunksjoner start
"""
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
	"""
	slå sammen felles og egne behandlinger til et sett med behandlinger
	"""
	virksomhetens_behandlinger = behandlingsprotokoll_egne(virksomhet)
	delte_behandlinger = behandlingsprotokoll_felles(virksomhet)
	alle_relevante_behandlinger = virksomhetens_behandlinger.union(delte_behandlinger).order_by('internt_ansvarlig')
	return alle_relevante_behandlinger

def csrf403(request):
	"""
	Støttefunksjon for å vise feilmelding
	"""
	return render(request, 'csrf403.html', {
		'request': request,
	})

def login(request):
	"""
	støttefunksjon for å logge inn
	"""
	if settings.THIS_ENVIRONMENT == "PROD":
		return redirect(reverse('oidc_authentication_init'))
	else:
		return redirect("/admin/")
"""
Støttefunksjoner slutt
"""





"""
Funksjoner som genererer innhold / eksponert via URL. Tilgangsstyres dersom nødvendig.
"""
def mal(request, pk):
	"""
	Hva denne funksjonen gjør
	Tilgjengelig for hvem?
	"""
	required_permissions = ['auth.RETTIGHET']
	if any(map(request.user.has_perm, required_permissions)):

		#logikk
		search_term = request.GET.get('search_term', '').strip()

		return render(request, 'NAVN.html', {
			'request': request,
			'search_term': search_term,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def bruker_sok(request):
	"""
	Denne funksjonen viser resultat av søk etter brukere
	Tilgjengelig for de som har rettigheter til å se brukere
	"""
	required_permissions = ['auth.view_user']
	if any(map(request.user.has_perm, required_permissions)):

		search_term = request.GET.get('search_term', '').strip()

		if len(search_term) > 3:
			users = User.objects.filter(Q(username__icontains=search_term) | Q(profile__displayName__icontains=search_term))
		else:
			users = User.objects.none()

		return render(request, 'system_brukerdetaljer.html', {
			'request': request,
			'search_term': search_term,
			'users': users,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def passwdneverexpire(request, pk):
	"""
	Denne funksjonen viser alle personer som har satt passord utløper aldri
	Tilgjengelig for de som har rettigheter til å se brukere
	"""
	from django.utils import timezone
	required_permissions = ['auth.view_user']
	if any(map(request.user.has_perm, required_permissions)):

		virksomhet = Virksomhet.objects.get(pk=pk)

		users = User.objects.filter(profile__virksomhet=virksomhet.pk).filter(profile__usertype__in=["Ansatt", "Ekstern"]).filter(profile__dont_expire_password=True).order_by('profile__displayName')

		return render(request, 'virksomhet_passwordneverexpire.html', {
			'request': request,
			'virksomhet': virksomhet,
			'users': users,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def passwordexpire(request, pk):
	"""
	Denne funksjonen viser alle personer som har passordutløp kommende periode
	Tilgjengelig for de som har rettigheter til å se brukere
	"""
	from django.utils import timezone
	required_permissions = ['auth.view_user']
	if any(map(request.user.has_perm, required_permissions)):

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
			'virksomhet': virksomhet,
			'users': users,
			'periode': periode,
			'innaktiv': innaktiv,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

def bruker_detaljer(request, pk):
	"""
	Denne funksjonen viser detaljer om en bruker lastet inn i kartoteket
	Tilgjengelig for de som har rettigheter til å se brukere
	"""
	required_permissions = ['auth.view_user']
	if any(map(request.user.has_perm, required_permissions)):

		user = User.objects.get(pk=pk)
		return render(request, 'system_brukerdetaljer.html', {
			'request': request,
			'users': [user],
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })



def alle_klienter(request):

	required_permissions = ['auth.view_user']
	if any(map(request.user.has_perm, required_permissions)):

		import os
		import json
		alle_maskinadm_klienter = set(list(Klientutstyr.objects.values_list('maskinadm_wsnummer', flat=True)))
		alle_cmdb_klienter = set(list(CMDBdevice.objects.filter(active=True).filter(comp_name__istartswith="WS").values_list('comp_name', flat=True)))

		#for i in alle_maskinadm_klienter[0:10]:
		#	print(i)
		antall_maskinadm = len(alle_maskinadm_klienter)
		antal_cmdb = len(alle_cmdb_klienter)

		mangler_cmdb = alle_maskinadm_klienter - alle_cmdb_klienter
		mangler_maskinadm = alle_cmdb_klienter - alle_maskinadm_klienter

		vpn_ws = set()
		filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/vpn_ws.json"
		with open(filepath, 'r', encoding='UTF-8') as json_file:
			for line in json_file.readlines():
				j = json.loads(line)
				vpn_ws.add(j["result"]["user"])
		vpn_anomaly = sorted(vpn_ws - alle_maskinadm_klienter)

		alle_aktive_brukere = set(list(User.objects.filter(profile__accountdisable=False).values_list('username', flat=True)))
		try:
			filepath = "/import/vpn_users.json"
			filepath = os.path.dirname(os.path.abspath(__file__)) + filepath
			vpn_users = set()
			with open(filepath, 'r', encoding='UTF-8') as json_file:
				for line in json_file.readlines():
					j = json.loads(line)
					vpn_users.add(j["result"]["user"].lower())
			vpn_anomaly_user = sorted(vpn_users - alle_aktive_brukere)
		except:
			messages.warning(request, 'Filen %s finnes ikke!' % (filepath))
			vpn_anomaly_user = []

		return render(request, 'prk_klienter.html', {
			'request': request,
			'antall_maskinadm': antall_maskinadm,
			'antal_cmdb': antal_cmdb,
			'mangler_cmdb': mangler_cmdb,
			'mangler_maskinadm': mangler_maskinadm,
			'vpn_anomaly': vpn_anomaly,
			'vpn_anomaly_user': vpn_anomaly_user,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def minside(request):
	"""
	Når innlogget, vise informasjon om innlogget bruker
	"""

	oidctoken = request.session['oidc-token']

	if request.user.is_authenticated:
		return render(request, 'site_minside.html', {
			'request': request,
			'oidctoken': oidctoken,
		})
	else:
		return redirect("/")


def dashboard_all(request, virksomhet=None):
	"""
	Generere virksomhets dashboard med statistikk over systmemer
	Tilgangsstyring: ÅPEN
	"""
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


	#virksomheter per antall eier, antall forvalter
	#per system, antall ros 0,5 år, 1år, eldre og ingen
	#per system, antall med behandling og uten
	#per system, antall dpia og uten.

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
		'systemlister': systemlister,
		'alle_virksomheter': alle_virksomheter,
		'virksomhet': virksomhet,
	})


def user_clean_up(request):
	"""
	Denne funksjonen er laget for å slette/anonymisere data i testmiljøet.
	Tilgangsstyring: STRENGT BESKYTTET
	"""
	required_permissions = 'auth.change_permission'
	if request.user.has_perm(required_permissions):
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
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def permissions(request):
	"""
	viser informasjon om alle ansvarliges aktive rettigheter
	Tilgangsstyring: De som kan redigere ansvarlige
	"""
	required_permissions = 'systemoversikt.change_ansvarlig'
	if request.user.has_perm(required_permissions):
		ansvarlige = Ansvarlig.objects.all()
		return render(request, 'site_permissions.html', {
			'ansvarlige': ansvarlige,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def roller(request):
	"""
	Viser informasjon om kobling rettighet og (AD)-grupper
	Tilgangsstyring: De som kan se grupper
	"""
	from django.core import serializers
	from django.contrib.auth.models import Group

	required_permissions = 'auth.view_group'
	if request.user.has_perm(required_permissions):
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
			return render(request, 'site_roller.html', {
				'request': request,
				'groups': groups,
	})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


"""
def video(request):
	return render(request, 'video.html', {
		'request': request,
	})
"""


def logger(request):
	"""
	viser alle endringer på objekter i løsningen
	Tilgangsstyring: Se endringslogger
	"""
	required_permissions = 'admin.view_logentry'
	if request.user.has_perm(required_permissions):

		recent_admin_loggs = LogEntry.objects.order_by('-action_time')[:300]
		return render(request, 'site_audit_logger.html', {
			'request': request,
			'recent_admin_loggs': recent_admin_loggs,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def logger_audit(request):
	"""
	viser alle endringer på objekter i løsningen
	Tilgangsstyring: Se applikasjonslogger
	"""
	required_permissions = 'systemoversikt.view_applicationlog'
	if request.user.has_perm(required_permissions):

		recent_loggs = ApplicationLog.objects.order_by('-opprettet')[:150]
		return render(request, 'site_logger_audit.html', {
			'request': request,
			'recent_loggs': recent_loggs,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def logger_users(request):
	"""
	viser selektive endringer på brukere/ansvarlige i løsningen
	Tilgangsstyring: Se brukere
	"""
	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):

		recent_loggs = UserChangeLog.objects.order_by('-opprettet')[:150]
		return render(request, 'site_logger_users.html', {
			'request': request,
			'recent_loggs': recent_loggs,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def home(request):
	"""
	Startsiden med oversikt over systemer per kategori
	Tilgangsstyring: ÅPEN
	"""

	antall_systemer = System.objects.filter(~Q(ibruk=False)).count()
	nyeste_systemer = System.objects.filter(~Q(ibruk=False)).order_by('-pk')[:10]

	antall_programvarer = Programvare.objects.count()
	nyeste_programvarer = Programvare.objects.order_by('-pk')[:10]

	antall_behandlinger = BehandlingerPersonopplysninger.objects.count()

	#print(nyeste_systemer)
	kategorier = SystemKategori.objects.all()

	return render(request, 'site_home.html', {
		'request': request,
		'kategorier': kategorier,
		'antall_systemer': antall_systemer,
		'nyeste_systemer': nyeste_systemer,
		'antall_programvarer': antall_programvarer,
		'nyeste_programvarer': nyeste_programvarer,
		'antall_behandlinger': antall_behandlinger,
	})


def alle_definisjoner(request):
	"""
	Viser definisjoner
	Tilgangsstyring: ÅPEN
	"""
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
		'definisjoner': definisjoner,
		'search_term': search_term,
	})


def definisjon(request, begrep):
	"""
	Viser en definisjon
	Tilgangsstyring: ÅPEN
	"""
	passende_definisjoner = Definisjon.objects.filter(begrep=begrep)
	return render(request, 'definisjon_detaljer.html', {
		'request': request,
		'begrep': begrep,
		'definisjoner': passende_definisjoner,
	})


def ansvarlig(request, pk):
	"""
	Viser informasjon om en ansvarlig
	Tilgangsstyring: ÅPEN
	"""
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



	return render(request, 'ansvarlig_detaljer.html', {
		'request': request,
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
	})


def alle_ansvarlige(request):
	"""
	Viser informasjon om alle ansvarlige
	Tilgangsstyring: ÅPEN
	"""
	ansvarlige = Ansvarlig.objects.all().order_by('brukernavn__first_name')
	return render(request, 'ansvarlig_alle.html', {
		'request': request,
		'ansvarlige': ansvarlige,
		'suboverskrift': "Hele kommunen",
	})


def alle_ansvarlige_eksport(request):
	"""
	Viser informasjon om alle ansvarlige
	Tilgangsstyring: De som kan opprette/endre ansvarlige
	"""
	required_permissions = 'systemoversikt.change_ansvarlig'
	if request.user.has_perm(required_permissions):
		ansvarlige = Ansvarlig.objects.filter(brukernavn__is_active=True)
		return render(request, 'ansvarlig_eksport.html', {
			'request': request,
			'ansvarlige': ansvarlige,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def systemkvalitet_virksomhet(request, pk):
	"""
	Viser informasjon om datakvalitet per system
	Tilgangsstyring: De som kan se virksomheter
	"""
	required_permissions = 'systemoversikt.view_virksomhet'
	if request.user.has_perm(required_permissions):

		virksomhet = Virksomhet.objects.get(pk=pk)
		systemer_ansvarlig_for = System.objects.filter(Q(systemeier=pk) | Q(systemforvalter=pk)).order_by(Lower('systemnavn'))
		return render(request, 'virksomhet_hvamangler.html', {
			'request': request,
			'virksomhet': virksomhet,
			'systemer': systemer_ansvarlig_for,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def systemdetaljer(request, pk):
	"""
	Viser detaljer om et system
	Tilgangsstyring: ÅPENT (noen deler er begrenset i template)
	"""
	system = System.objects.get(pk=pk)

	avhengigheter_graf = {"nodes": [], "edges": []}
	observerte_driftsmodeller = set()

	def parent(system):
		if system.driftsmodell_foreignkey is not None:
			return system.driftsmodell_foreignkey.navn
		else:
			return "Ukjent"

	# registrere dette systemet som en node
	avhengigheter_graf["nodes"].append({"data": { "parent": parent(system), "id": system.pk, "name": system.systemnavn, "shape": "ellipse", "color": "black" }},)
	observerte_driftsmodeller.add(system.driftsmodell_foreignkey)

	def systemfarge(self):
		if self.er_infrastruktur():
			return "gray"
		else:
			return "#dca85a"

	for s in system.datautveksling_mottar_fra.all():
		avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": systemfarge(s), "href": reverse('systemdetaljer', args=[s.pk]) }},)
		avhengigheter_graf["edges"].append({"data": { "source": s.pk, "target": system.pk, "linestyle": "solid" }},)
		observerte_driftsmodeller.add(s.driftsmodell_foreignkey)
	for s in system.system_datautveksling_avleverer_til.all():
		avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": systemfarge(s), "href": reverse('systemdetaljer', args=[s.pk]) }},)
		avhengigheter_graf["edges"].append({"data": { "source": s.pk, "target": system.pk, "linestyle": "solid" }},)
		observerte_driftsmodeller.add(s.driftsmodell_foreignkey)

	for s in system.datautveksling_avleverer_til.all():
		avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": systemfarge(s), "href": reverse('systemdetaljer', args=[s.pk]) }},)
		avhengigheter_graf["edges"].append({"data": { "source": system.pk, "target": s.pk, "linestyle": "solid" }},)
		observerte_driftsmodeller.add(s.driftsmodell_foreignkey)
	for s in system.system_datautveksling_mottar_fra.all():
		avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": systemfarge(s), "href": reverse('systemdetaljer', args=[s.pk]) }},)
		avhengigheter_graf["edges"].append({"data": { "source": system.pk, "target": s.pk, "linestyle": "solid" }},)
		observerte_driftsmodeller.add(s.driftsmodell_foreignkey)

	for s in system.avhengigheter_referanser.all():
		avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": systemfarge(s), "href": reverse('systemdetaljer', args=[s.pk]) }},)
		avhengigheter_graf["edges"].append({"data": { "source": system.pk, "target": s.pk, "linestyle": "dashed" }},)
		observerte_driftsmodeller.add(s.driftsmodell_foreignkey)
	for s in system.system_avhengigheter_referanser.all():
		avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": systemfarge(s), "href": reverse('systemdetaljer', args=[s.pk]) }},)
		avhengigheter_graf["edges"].append({"data": { "source": s.pk, "target": system.pk, "linestyle": "dashed" }},)
		observerte_driftsmodeller.add(s.driftsmodell_foreignkey)

	for p in system.programvarer.all():
		avhengigheter_graf["nodes"].append({"data": { "id": ("p%s" % p.pk), "name": p.programvarenavn, "shape": "ellipse", "color": "#64c14c", "href": reverse('programvaredetaljer', args=[p.pk]) }},)
		avhengigheter_graf["edges"].append({"data": { "source": system.pk, "target": ("p%s" % p.pk), "linestyle": "dashed" }},)

	# legge til alle driftsmodeller som ble funnet
	for driftsmodell in observerte_driftsmodeller:
		if driftsmodell is not None:
			avhengigheter_graf["nodes"].append({"data": { "id": driftsmodell.navn }},)

		#url?
		#avtale drift?
		#avtale system?

	siste_endringer_antall = 10
	system_content_type = ContentType.objects.get_for_model(system)
	siste_endringer = LogEntry.objects.filter(content_type=system_content_type).filter(object_id=pk).order_by('-action_time')[:siste_endringer_antall]

	systembruk = SystemBruk.objects.filter(system=pk).order_by("brukergruppe")
	behandlinger = BehandlingerPersonopplysninger.objects.filter(systemer=pk).order_by("funksjonsomraade")
	try:
		dpia = DPIA.objects.get(for_system=pk)
	except:
		dpia = None

	hoy_risiko = behandlinger.filter(hoy_personvernrisiko=True)

	# "avleverer til" fra et annet system tilsvarer "mottar fra" dette systemet
	datautveksling_mottar_fra = System.objects.filter(datautveksling_avleverer_til__in=[system])
	datautveksling_avleverer_til = System.objects.filter(datautveksling_mottar_fra__in=[system])

	avhengigheter_reverse_systemer = System.objects.filter(avhengigheter_referanser=pk)
	avhengigheter_reverse_systembruk = SystemBruk.objects.filter(avhengigheter_referanser=pk)

	return render(request, 'system_detaljer.html', {
		'request': request,
		'systemdetaljer': system,
		'systembruk': systembruk,
		'behandlinger': behandlinger,
		'datautveksling_mottar_fra': datautveksling_mottar_fra,
		'datautveksling_avleverer_til': datautveksling_avleverer_til,
		'avhengigheter_reverse_systemer': avhengigheter_reverse_systemer,
		'avhengigheter_reverse_systembruk': avhengigheter_reverse_systembruk,
		'hoy_risiko': hoy_risiko,
		'dpia': dpia,
		'siste_endringer': siste_endringer,
		'siste_endringer_antall': siste_endringer_antall,
		'avhengigheter_graf': avhengigheter_graf,
	})


def systemer_pakket(request):
	"""
	Uferdig: vising av hvordan applikasjoner er pakket
	Tilgangsstyring: ÅPENT
	"""
	systemer = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=163)  # 163=UKE
	programvarer = Programvare.objects.all()
	return render(request, 'system_hvordan_pakket.html', {
		'request': request,
		'systemer': systemer,
		'programvarer': programvarer,
	})


def systemklassifisering_detaljer(request, id):
	"""
	Vise systemer filtrert basert på systemeierskapsmodell (felles, sektor, virksomhet)
	Tilgangsstyring: ÅPENT
	"""
	if id == "__NONE__":
		utvalg_systemer = System.objects.filter(~Q(ibruk=False)).filter(systemeierskapsmodell=None)
		id = "tom"
	else:
		utvalg_systemer = System.objects.filter(~Q(ibruk=False)).filter(systemeierskapsmodell=id)

	from systemoversikt.models import SYSTEMEIERSKAPSMODELL_VALG
	systemtyper = Systemtype.objects.all()

	return render(request, 'system_alle.html', {
		'request': request,
		'overskrift': ("Systemer der systemklassifisering er %s" % id.lower()),
		'systemer': utvalg_systemer,
		'kommuneklassifisering': SYSTEMEIERSKAPSMODELL_VALG,
		'systemtyper': systemtyper,
	})


def systemtype_detaljer(request, pk=None):
	"""
	Vise systemer filtrert basert på systemtype (web/app/infrastruktur osv.)
	Tilgangsstyring: ÅPENT
	"""
	if pk:
		utvalg_systemer = System.objects.filter(systemtyper=pk)
		systemtype_navn = Systemtype.objects.get(pk=pk).kategorinavn
		overskrift = ("Systemer av typen %s" % systemtype_navn.lower())
	else:
		utvalg_systemer = System.objects.filter(systemtyper=None)
		overskrift = "Systemer som mangler systemtype"

	from systemoversikt.models import SYSTEMEIERSKAPSMODELL_VALG
	systemtyper = Systemtype.objects.all()

	utvalg_systemer = utvalg_systemer.order_by('ibruk', Lower('systemnavn'))
	return render(request, 'system_alle.html', {
		'request': request,
		'overskrift': overskrift,
		'systemer': utvalg_systemer,
		'kommuneklassifisering': SYSTEMEIERSKAPSMODELL_VALG,
		'systemtyper': systemtyper,
	})


def alle_systemer(request):
	"""
	Vise alle systemer
	Tilgangsstyring: ÅPENT
	"""
	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space

	if search_term != '':
		aktuelle_systemer = System.objects.filter(Q(systemnavn__icontains=search_term)|Q(alias__icontains=search_term))
		#Her ønsker vi å vise treff i beskrivelsesfeltet, men samtidig ikke vise systemer på nytt
		potensielle_systemer = System.objects.filter(Q(systembeskrivelse__icontains=search_term) & ~Q(pk__in=aktuelle_systemer))
		aktuelle_programvarer = Programvare.objects.filter(programvarenavn__icontains=search_term)
	else:
		aktuelle_systemer = System.objects.all()
		potensielle_systemer = System.objects.none()
		aktuelle_programvarer = Programvare.objects.none()

	if (len(aktuelle_systemer) == 1) and (len(aktuelle_programvarer) == 0):  # bare ét systemtreff og ingen programvaretreff.
		return redirect('systemdetaljer', aktuelle_systemer[0].pk)

	aktuelle_systemer = aktuelle_systemer.order_by('ibruk', Lower('systemnavn'))
	potensielle_systemer = potensielle_systemer.order_by('ibruk', Lower('systemnavn'))
	aktuelle_programvarer.order_by(Lower('programvarenavn'))

	from systemoversikt.models import SYSTEMEIERSKAPSMODELL_VALG
	systemtyper = Systemtype.objects.all()

	return render(request, 'system_alle.html', {
		'request': request,
		'systemer': aktuelle_systemer,
		'potensielle_systemer': potensielle_systemer,
		'search_term': search_term,
		'kommuneklassifisering': SYSTEMEIERSKAPSMODELL_VALG,
		'systemtyper': systemtyper,
		'aktuelle_programvarer': aktuelle_programvarer,
		'overskrift': ("Alle systemer"),
	})


def bruksdetaljer(request, pk):
	"""
	Vise detaljer om systembruk
	Tilgangsstyring: ÅPENT
	"""
	bruk = SystemBruk.objects.get(pk=pk)
	return render(request, 'systembruk_detaljer.html', {
		'request': request,
		'bruk': bruk,
	})


def mine_systembruk(request):
	"""
	Vise detaljer om innlogget brukers virksomhets systembruk
	Tilgangsstyring: ÅPENT
	"""
	try:
		brukers_virksomhet = virksomhet_til_bruker(request)
		pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
		return redirect('all_bruk_for_virksomhet', pk)
	except:
		messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
		return redirect('alle_virksomheter')


def all_bruk_for_virksomhet(request, pk):
	"""
	Vise detaljer om en valgt virksomhets systembruk
	Tilgangsstyring: ÅPENT
	"""
	virksomhet_pk = pk
	all_bruk = SystemBruk.objects.filter(brukergruppe=virksomhet_pk).order_by(Lower('system__systemnavn'))  # sortering er ellers case-sensitiv

	# dette er litt databasegalskap, men ok..
	for bruk in all_bruk:
		ant = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=virksomhet_pk).filter(systemer=bruk.system.pk).count()
		bruk.antall_behandlinger = ant

	try:
		virksomhet = Virksomhet.objects.get(pk=pk)
	except:
		messages.warning(request, 'Fant ingen virksomhet med denne ID-en.')
		virksomhet = Virksomhet.objects.none()

	return render(request, 'systembruk_alle.html', {
		'request': request,
		'all_bruk': all_bruk,
		'virksomhet': virksomhet,
	})


def registrer_bruk(request, system):
	"""
	Forenklet metode for å legge til bruk av system ved avkryssing
	Tilgangsstyring: Må kunne legge til systembruk
	"""
	required_permissions = 'systemoversikt.add_systembruk'
	if request.user.has_perm(required_permissions):

		system_instans = System.objects.get(pk=system)

		if request.POST:
			virksomheter = request.POST.getlist("virksomheter", "")
			if virksomheter != "":
				for str_virksomhet in virksomheter:
					virksomhet = Virksomhet.objects.get(pk=int(str_virksomhet))
					try:
						bruk = SystemBruk.objects.create(
							brukergruppe=virksomhet,
							system=system_instans,
						)
						bruk.save()
					except:
						messages.warning(request, 'Kunne ikke opprette bruk for %s' % virksomhet)
			return redirect('systemdetaljer', system_instans.pk)

		virksomheter_med_bruk = SystemBruk.objects.filter(system=system_instans)
		vmb = [bruk.brukergruppe.pk for bruk in virksomheter_med_bruk]
		manglende_virksomheter = Virksomhet.objects.exclude(pk__in=vmb)

		return render(request, 'system_registrer_bruk.html', {
			'request': request,
			'system': system_instans,
			'virksomheter_uten_bruk': manglende_virksomheter,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def programvaredetaljer(request, pk):
	"""
	Vise detaljer for programvare
	Tilgangsstyring: ÅPEN
	"""
	programvare = Programvare.objects.get(pk=pk)
	programvarebruk = ProgramvareBruk.objects.filter(programvare=pk).order_by("brukergruppe")
	behandlinger = BehandlingerPersonopplysninger.objects.filter(programvarer=pk).order_by("funksjonsomraade")
	return render(request, "programvare_detaljer.html", {
		'request': request,
		'programvare': programvare,
		'programvarebruk': programvarebruk,
		'behandlinger': behandlinger,
	})


def alle_programvarer(request):
	"""
	Vise alle programvarer
	Tilgangsstyring: ÅPEN
	"""
	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space

	if search_term == "":
		aktuelle_programvarer = Programvare.objects.all()
	elif len(search_term) < 2: # if one or less, return nothing
		aktuelle_programvarer = Programvare.objects.none()
	else:
		aktuelle_programvarer = Programvare.objects.filter(programvarenavn__icontains=search_term)

	aktuelle_programvarer = aktuelle_programvarer.order_by(Lower('programvarenavn'))

	return render(request, 'programvare_alle.html', {
		'overskrift': "Programvarer",
		'request': request,
		'programvarer': aktuelle_programvarer,
	})


def all_programvarebruk_for_virksomhet(request, pk):
	"""
	Vise all bruk av programvare for en virksomhet
	Tilgangsstyring: ÅPEN
	"""
	virksomhet = Virksomhet.objects.get(pk=pk)
	virksomhet_pk = pk
	all_bruk = ProgramvareBruk.objects.filter(brukergruppe=virksomhet_pk).order_by(Lower('programvare__programvarenavn'))
	for bruk in all_bruk:
		ant = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=virksomhet_pk).filter(programvarer=bruk.programvare.pk).count()
		bruk.antall_behandlinger = ant

	return render(request, "programvarebruk_alle.html", {
		'request': request,
		'virksomhet': virksomhet,
		'all_bruk': all_bruk,
	})


def programvarebruksdetaljer(request, pk):
	"""
	Vise detaljer for bruk av programvare
	Tilgangsstyring: ÅPEN
	"""
	bruksdetaljer = ProgramvareBruk.objects.get(pk=pk)
	return render(request, "programvarebruk_detaljer.html", {
		'request': request,
		'bruksdetaljer': bruksdetaljer,
	})


"""
def alle_tjenester(request):
	tjenester = Tjeneste.objects.all().order_by(Lower('tjenestenavn'))
	template = 'alle_tjenester.html'

	return render(request, template, {
		'overskrift': "Tjenester",
		'request': request,
		'tjenester': tjenester,
	})

def tjenestedetaljer(request, pk):
	tjeneste = Tjeneste.objects.get(pk=pk)

	return render(request, 'detaljer_tjeneste.html', {
		'request': request,
		'tjeneste': tjeneste,
	})
"""

def alle_behandlinger(request):
	"""
	Vise alle behandlinger (av personopplysninger) registrert for kommunen
	Tilgangsstyring: Vise behandlinger
	"""
	required_permissions = 'systemoversikt.view_behandlingerpersonopplysninger'
	if request.user.has_perm(required_permissions):

		behandlinger = BehandlingerPersonopplysninger.objects.all()
		return render(request, 'behandling_alle.html', {
			'request': request,
			'behandlinger': behandlinger,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def behandlingsdetaljer(request, pk):
	"""
	Vise detaljer for en behandling av personopplysninger
	Tilgangsstyring: Vise behandlinger
	"""
	required_permissions = 'systemoversikt.view_behandlingerpersonopplysninger'
	if request.user.has_perm(required_permissions):

		behandling = BehandlingerPersonopplysninger.objects.get(pk=pk)

		siste_endringer_antall = 10
		system_content_type = ContentType.objects.get_for_model(BehandlingerPersonopplysninger)
		siste_endringer = LogEntry.objects.filter(content_type=system_content_type).filter(object_id=pk).order_by('-action_time')[:siste_endringer_antall]

		return render(request, 'behandling_detaljer.html', {
			'request': request,
			'behandling': behandling,
			'siste_endringer': siste_endringer,
			'siste_endringer_antall': siste_endringer_antall,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })



def mine_behandlinger(request):
	"""
	Vise alle behandling av personopplysninger for innlogget brukers virksomhet
	Tilgangsstyring: Innlogget + tilgang på siden det sendes til.
	"""
	try:
		brukers_virksomhet = virksomhet_til_bruker(request)
		pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
		return redirect('alle_behandlinger_virksomhet', pk)
	except:
		messages.warning(request, 'Din bruker er ikke knyttet til en virksomhet. Velg en virksomhet fra listen, og velg så "Våre behandlinger".')
		return redirect('alle_virksomheter')



def alle_behandlinger_virksomhet(request, pk, internt_ansvarlig=False):
	"""
	Vise alle behandling av personopplysninger for en valgt virksomhet
	Tilgangsstyring: ÅPEN (noe informasjon er tilgangsstyrt i template)
	"""
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
		'behandlinger': behandlinger,
		'virksomhet': vir,
		'interne_avdelinger': virksomhetens_behandlinger_avdelinger,
		'internt_ansvarlig_valgt': internt_ansvarlig,
	})


def behandling_kopier(request, system_pk):
	"""
	Funksjon for å kunne velge og kopiere en behandling til innlogget brukers virksomhet
	Tilgangsstyring: Legge til behandling (begrenset til egen virksomhet i kode)
	"""
	required_permissions = 'systemoversikt.add_behandlingerpersonopplysninger'
	if request.user.has_perm(required_permissions):

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
			'system': dette_systemet,
			'dine_eksisterende_behandlinger': dine_eksisterende_behandlinger,
			'kandidatbehandlinger': kandidatbehandlinger,
			'din_virksomhet': din_virksomhet,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def virksomhet_ansvarlige(request, pk):
	"""
	Vise alle ansvarlige knyttet til valgt virksomhet
	Tilgangsstyring: ÅPEN
	"""
	virksomhet = Virksomhet.objects.get(pk=pk)
	ansvarlige = Ansvarlig.objects.filter(brukernavn__profile__virksomhet=pk).order_by('brukernavn__first_name')
	return render(request, 'ansvarlig_alle.html', {
		'request': request,
		'ansvarlige': ansvarlige,
		'virksomhet': virksomhet,
	})


def enhet_detaljer(request, pk):
	"""
	Vise informasjon om en konkret organisatorisk enhet
	Tilgjengelig for de som kan se brukerdetaljer
	"""
	required_permissions = ['auth.view_user']
	if any(map(request.user.has_perm, required_permissions)):

		unit = HRorg.objects.get(pk=pk)
		sideenheter = HRorg.objects.filter(direkte_mor=unit).order_by('ou')
		personer = User.objects.filter(profile__org_unit=pk).order_by('profile__displayName')

		return render(request, 'virksomhet_enhet_detaljer.html', {
			'request': request,
			'unit': unit,
			'sideenheter': sideenheter,
			'personer': personer,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def virksomhet_enhetsok(request):
	"""
	Vise informasjon om organisatorisk struktur
	Tilgjengelig for de som kan se brukere
	"""
	required_permissions = ['auth.view_user']
	if any(map(request.user.has_perm, required_permissions)):

		search_term = request.GET.get('search_term', "").strip()
		if len(search_term) > 1:
			units = HRorg.objects.filter(ou__icontains=search_term).filter(active=True).order_by('virksomhet_mor')
		else:
			units = HRorg.objects.none()

		return render(request, 'virksomhet_enhetsok.html', {
			'request': request,
			'units': units,
			'search_term': search_term,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def virksomhet_enheter(request, pk):
	"""
	Vise informasjon om organisatorisk struktur
	Tilgjengelig for de som kan se brukere
	"""
	required_permissions = ['auth.view_user']
	if any(map(request.user.has_perm, required_permissions)):

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
						"shape": "ellipse",
						"color": color(u),
						#"size": size(u)
						#"href": reverse('adgruppe_detaljer', args=[m.pk])
						}
					})

		return render(request, 'virksomhet_enheter.html', {
			'request': request,
			'units': units,
			'virksomhet': virksomhet,
			'avhengigheter_graf': avhengigheter_graf,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def virksomhet_prkadmin(request, pk):
	"""
	Vise alle PRK-administratorer for angitt virksomhet
	Tilgangsstyring: må kunne vise informasjon om brukere
	"""
	import json
	from functools import lru_cache

	required_permissions = ['auth.view_user']
	if any(map(request.user.has_perm, required_permissions)):


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
			'virksomhet': vir,
			'prk_admins': prk_admins_inverted,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def systemer_virksomhet_ansvarlig_for(request, pk):
	virksomhet = Virksomhet.objects.get(pk=pk)
	systemer_ansvarlig_for = System.objects.filter(~Q(ibruk=False)).filter(Q(systemeier=pk) | Q(systemforvalter=pk)).order_by(Lower('systemnavn'))

	return render(request, 'virksomhet_systemer_ansvarfor.html', {
		'virksomhet': virksomhet,
		'systemer_ansvarlig_for': systemer_ansvarlig_for,
	})


def virksomhet(request, pk):
	"""
	Vise detaljer om en valgt virksomhet
	Tilgangsstyring: ÅPEN
	"""
	virksomhet = Virksomhet.objects.get(pk=pk)
	antall_brukere = User.objects.filter(profile__virksomhet=pk).filter(profile__ekstern_ressurs=False).filter(is_active=True).count()
	antall_eksterne_brukere = User.objects.filter(profile__virksomhet=pk).filter(profile__ekstern_ressurs=True).filter(is_active=True).count()

	system_ikke_kvalitetssikret = System.objects.filter(Q(systemeier=pk) | Q(systemforvalter=pk)).filter(informasjon_kvalitetssikret=False).count()
	deaktiverte_brukere = Ansvarlig.objects.filter(brukernavn__profile__virksomhet=pk).filter(brukernavn__profile__accountdisable=True).count()
	behandling_ikke_kvalitetssikret = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=virksomhet).filter(informasjon_kvalitetssikret=False).count()

	enheter = HRorg.objects.filter(virksomhet_mor=pk).filter(level=3)

	return render(request, 'virksomhet_detaljer.html', {
		'request': request,
		'virksomhet': virksomhet,
		'antall_brukere': antall_brukere,
		'antall_eksterne_brukere': antall_eksterne_brukere,
		'system_ikke_kvalitetssikret': system_ikke_kvalitetssikret,
		'deaktiverte_brukere': deaktiverte_brukere,
		'behandling_ikke_kvalitetssikret': behandling_ikke_kvalitetssikret,
		'enheter': enheter,
	})


def min_virksomhet(request):
	"""
	Vise detaljer om en innlogget brukers virksomhet
	Tilgangsstyring: redirect for innloggede brukere
	"""
	try:
		brukers_virksomhet = virksomhet_til_bruker(request)
		pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
		return redirect('virksomhet', pk)
	except:
		messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
		return redirect('alle_virksomheter')


def innsyn_virksomhet(request, pk):
	"""
	Vise informasjon om kontaktpersoner for innsyn for en valgt virksomhet (for systemer virksomhet behandler personopplysninger i)
	Tilgangsstyring: Vise behandlinger
	"""
	required_permissions = 'systemoversikt.view_behandlingerpersonopplysninger'
	if request.user.has_perm(required_permissions):

		virksomhet = Virksomhet.objects.get(pk=pk)
		virksomhets_behandlingsprotokoll = behandlingsprotokoll(pk)
		systemer = []
		for behandling in virksomhets_behandlingsprotokoll:
			for system in behandling.systemer.all():
				if (system not in systemer) and (system.innsyn_innbygger or system.innsyn_ansatt) and (system.ibruk != False):
					systemer.append(system)

		return render(request, 'virksomhet_innsyn.html', {
			'request': request,
			'virksomhet': virksomhet,
			'systemer': systemer,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def bytt_virksomhet(request):
	"""
	Støttefunksjon for å bytte virksomhet innlogget bruker representerer
	Tilgangsstyring: Innlogget og avhengig av virksomhet innlogget bruker er logget inn som
	"""
	#returnere en liste over virksomheter som gjeldende bruker kan representere
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
			else:
				messages.warning(request, 'Forsøk på ulovlig bytte')
		except:
			messages.warning(request, 'Noe gikk galt ved endring av virksomhetstilhørighet')

	# denne må vi vente med i tilfelle den blir endret ved en POST-request
	aktiv_representasjon = request.user.profile.virksomhet

	return render(request, 'site_bytt_virksomhet.html', {
		'request': request,
		'brukers_virksomhet': aktiv_representasjon,
		'dine_virksomheter': dine_virksomheter,
	})


def sertifikatmyndighet(request):
	"""
	Vise informasjon om delegeringer knyttet til sertifikater
	Tilgangsstyring: ÅPEN
	"""
	required_permissions = 'systemoversikt.view_virksomhet'
	if request.user.has_perm(required_permissions):

		virksomheter = Virksomhet.objects.all()
		return render(request, 'virksomhet_sertifikatmyndigheter.html', {
			'request': request,
			'virksomheter': virksomheter,
		})

	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def alle_virksomheter(request):
	"""
	Vise oversikt over alle virksomheter
	Tilgangsstyring: ÅPEN
	"""
	search_term = request.GET.get('search_term', "").strip()
	if search_term in ("", "__all__"):
		virksomheter = Virksomhet.objects.all()
	else:
		virksomheter = Virksomhet.objects.filter(Q(virksomhetsnavn__icontains=search_term) | Q(virksomhetsforkortelse__iexact=search_term))

	virksomheter = virksomheter.order_by('-ordinar_virksomhet', 'virksomhetsnavn')

	return render(request, 'virksomhet_alle.html', {
		'request': request,
		'virksomheter': virksomheter,
	})


def leverandor(request, pk):
	"""
	Vise detaljer for en valgt leverandør
	Tilgangsstyring: ÅPEN
	"""
	leverandor = Leverandor.objects.get(pk=pk)
	systemleverandor_for = System.objects.filter(systemleverandor=pk)
	databehandler_for = BehandlingerPersonopplysninger.objects.filter(navn_databehandler=pk)
	programvareleverandor_for = Programvare.objects.filter(programvareleverandor=pk)
	basisdriftleverandor_for = System.objects.filter(basisdriftleverandor=pk)
	applikasjonsdriftleverandor_for = System.objects.filter(applikasjonsdriftleverandor=pk)
	registrar_for = SystemUrl.objects.filter(registrar=pk)
	return render(request, 'leverandor_detaljer.html', {
		'request': request,
		'leverandor': leverandor,
		'systemleverandor_for': systemleverandor_for,
		'databehandler_for': databehandler_for,
		'programvareleverandor_for': programvareleverandor_for,
		'basisdriftleverandor_for': basisdriftleverandor_for,
		'applikasjonsdriftleverandor_for': applikasjonsdriftleverandor_for,
		'registrar_for': registrar_for,
	})


def alle_leverandorer(request):
	"""
	Vise liste over alle leverandører
	Tilgangsstyring: ÅPEN
	"""
	from django.db.models.functions import Lower

	search_term = request.GET.get('search_term', "").strip()

	if search_term == "":
		leverandorer = Leverandor.objects.all()
	else:
		leverandorer = Leverandor.objects.filter(leverandor_navn__icontains=search_term)

	leverandorer = leverandorer.order_by(Lower('leverandor_navn'))

	return render(request, 'leverandor_alle.html', {
		'request': request,
		'leverandorer': leverandorer,
	})


def alle_driftsmodeller(request):
	"""
	Vise liste over alle driftsmodeller
	Tilgangsstyring: ÅPEN
	"""
	driftsmodeller = Driftsmodell.objects.all().order_by('-ansvarlig_virksomhet', 'navn')
	return render(request, 'driftsmodell_alle.html', {
		'request': request,
		'driftsmodeller': driftsmodeller,
	})


def driftsmodell_virksomhet_klassifisering(request, pk):
	"""
	Vise informasjon om sikkerhethetsklassifisering for systemer driftet av en virksomhet (alle systemer koblet til driftsmodeller som forvaltes av valgt virksomhet)
	Tilgangsstyring: For plattformforvaltere
	"""
	required_permissions = 'systemoversikt.change_systemkategori'
	if request.user.has_perm(required_permissions):

		virksomhet = Virksomhet.objects.get(pk=pk)
		driftsmodeller = Driftsmodell.objects.filter(ansvarlig_virksomhet=virksomhet)
		systemer_drifter = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet).filter(~Q(ibruk=False)).order_by('sikkerhetsnivaa')
		return render(request, 'alle_systemer_virksomhet_drifter_klassifisering.html', {
			'virksomhet': virksomhet,
			'request': request,
			'systemer': systemer_drifter,
			'driftsmodeller': driftsmodeller,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def driftsmodell_virksomhet(request, pk):
	"""
	Vise systemer driftet av en virksomhet (alle systemer koblet til driftsmodeller som forvaltes av valgt virksomhet)
	Tilgangsstyring: ÅPEN
	"""
	virksomhet = Virksomhet.objects.get(pk=pk)
	driftsmodeller = Driftsmodell.objects.filter(ansvarlig_virksomhet=virksomhet).order_by("navn")
	systemer_drifter = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet).filter(~Q(ibruk=False)).order_by('systemnavn')
	return render(request, 'system_virksomhet_drifter.html', {
		'virksomhet': virksomhet,
		'request': request,
		'systemer': systemer_drifter,
		'driftsmodeller': driftsmodeller,
	})


def detaljer_driftsmodell(request, pk):
	"""
	Vise detaljer om en valgt driftsmodell (inkl. systemer tilknyttet)
	Tilgangsstyring: ÅPEN
	"""
	driftsmodell = Driftsmodell.objects.get(pk=pk)
	systemer = System.objects.filter(driftsmodell_foreignkey=pk)
	isolert_drift = systemer.filter(isolert_drift=True)

	# gjør et oppslag for å finne kategorier som er, og ikke er anbefalt
	anbefalte_personoppl_kategorier = driftsmodell.anbefalte_kategorier_personopplysninger.all()
	ikke_anbefalte_personoppl_kategorier = Personsonopplysningskategori.objects.filter(~Q(pk__in=anbefalte_personoppl_kategorier)).all()

	return render(request, 'driftsmodell_detaljer.html', {
		'request': request,
		'driftsmodell': driftsmodell,
		'systemer': systemer,
		'isolert_drift': isolert_drift,
		'ikke_anbefalte_personoppl_kategorier': ikke_anbefalte_personoppl_kategorier,
	})


def systemer_uten_driftsmodell(request):
	"""
	Vise liste over systemer der driftsmodell mangler
	Tilgangsstyring: ÅPEN
	"""
	mangler = System.objects.filter(Q(driftsmodell_foreignkey=None) & ~Q(systemtyper=1))
	return render(request, 'driftsmodell_mangler.html', {
		'systemer': mangler,
})


def systemer_utfaset(request):
	"""
	Vise liste over systemer satt til "ikke i bruk"
	Tilgangsstyring: ÅPEN
	"""
	systemer = System.objects.filter(ibruk=False).order_by("-sist_oppdatert")
	return render(request, 'system_utfaset.html', {
		'systemer': systemer,
})


def systemkategori(request, pk):
	"""
	Vise detaljer om en kategori
	Tilgangsstyring: ÅPEN
	"""
	kategori = SystemKategori.objects.get(pk=pk)
	systemer = System.objects.filter(systemkategorier=pk).order_by(Lower('systemnavn'))
	programvarer = Programvare.objects.filter(kategorier=pk).order_by(Lower('programvarenavn'))
	return render(request, 'kategori_detaljer.html', {
		'request': request,
		'systemer': systemer,
		'kategori': kategori,
		'programvarer': programvarer,
	})


def alle_hovedkategorier(request):
	"""
	Vise liste over alle hovedkategorier
	Tilgangsstyring: ÅPEN
	"""
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
		'hovedkategorier': hovedkategorier,
		'subkategorier_uten_hovedkategori': subkategorier_uten_hovedkategori,
	})


def alle_systemkategorier(request):
	"""
	Vise liste over alle (under)kategorier
	Tilgangsstyring: ÅPEN
	"""
	kategorier = SystemKategori.objects.order_by('kategorinavn')
	return render(request, 'kategori_alle.html', {
		'request': request,
		'kategorier': kategorier,
	})


def uten_systemkategori(request):
	"""
	Vise liste over alle systemer uten (under)kategori
	Tilgangsstyring: ÅPEN
	"""
	antall_systemer = System.objects.all().count()
	antall_programvarer = Programvare.objects.all().count()
	systemer = System.objects.annotate(num_categories=Count('systemkategorier')).filter(num_categories=0)
	programvarer = Programvare.objects.annotate(num_categories=Count('kategorier')).filter(num_categories=0)
	return render(request, 'kategori_system_uten.html', {
		'request': request,
		'systemer': systemer,
		'programvarer': programvarer,
		'antall_systemer': antall_systemer,
		'antall_programvarer': antall_programvarer,
	})


def alle_systemurler(request):
	"""
	Vise liste over alle URLer
	Tilgangsstyring: ÅPEN
	"""
	urler = SystemUrl.objects.order_by('domene')
	return render(request, 'urler_alle.html', {
		'request': request,
		'web_urler': urler,
	})

def virksomhet_urler(request, pk):
	"""
	Vise liste over alle URLer
	Tilgangsstyring: ÅPEN
	"""
	virksomhet = Virksomhet.objects.get(pk=pk)
	urler = SystemUrl.objects.filter(eier=virksomhet.pk).order_by('domene')
	return render(request, 'urler_alle.html', {
		'request': request,
		'web_urler': urler,
		'virksomhet': virksomhet,
	})


def bytt_kategori(request, fra, til):
	"""
	Funksjon for å bytte all bruk av én kategori til en annen kategori
	Tilgangsstyring: STRENG, krever tilgang til å endre systemkategorier.
	"""
	required_permissions = 'systemoversikt.change_systemkategori'
	if request.user.has_perm(required_permissions):
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
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })



def bytt_leverandor(request, fra, til):
	"""
	Funksjon for å bytte all bruk av én leverandør til en annen leverandør
	Tilgangsstyring: krever tilgang til å endre systemer.
	"""
	required_permissions = 'systemoversikt.change_system'
	if request.user.has_perm(required_permissions):
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
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def system_til_programvare(request, system_id=None):
	"""
	Funksjon for å opprette en instans av programvare basert på system (systemet må slettes manuelt etterpå)
	Tilgangsstyring: krever tilgang til å endre systemer.
	"""
	required_permissions = 'systemoversikt.change_system'
	if request.user.has_perm(required_permissions):

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
			'systemer': utvalg_systemer,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def adorgunit_detaljer(request, pk=None):
	"""
	Vise informasjon om en konkret AD-OU
	Tilgangsstyring: må kunne vise informasjon om brukere
	"""
	import os

	if pk == None:
		root_str = os.environ["KARTOTEKET_LDAPROOT"]
		ou = ADOrgUnit.objects.get(distinguishedname=root_str)
		pk = ou.pk
	else:
		ou = ADOrgUnit.objects.get(pk=pk)

	groups = ADgroup.objects.filter(parent=pk)
	parent_str = ",".join(ou.distinguishedname.split(',')[1:])
	try:
		parent = ADOrgUnit.objects.get(distinguishedname=parent_str)
	except:
		parent = None
	children = ADOrgUnit.objects.filter(parent=pk)

	users = User.objects.filter(profile__ou=pk)

	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):
		return render(request, 'ad_adorgunit_detaljer.html', {
				"ou": ou,
				"groups": groups,
				"parent": parent,
				"children": children,
				"users": users,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def adgruppe_graf(request, pk):
	"""
	Vise en graf over hvordan grupper er nøstet nedover fra en gitt gruppe
	Tilgangsstyring: Må kunne vise informasjon om brukere
	"""
	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):

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
				if m not in ferdige:
					nonlocal grense
					if grense < maks_grense:
						nye_grupper.append(m)
						grense += 1
					#print("added %s" % m)

					avhengigheter_graf["nodes"].append(
							{"data": {
								"parent": m.parent.pk,
								"id": m.pk,
								"name": m.short(),
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
			'avhengigheter_graf': avhengigheter_graf,
			'morgruppe': morgruppe,
			'maks_grense': maks_grense,
			'grense': grense,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def human_readable_members(items, onlygroups=False):
	groups = []
	users = []
	other_users = []
	notfound = []
	for item in items:
		try:
			g = ADgroup.objects.get(distinguishedname=item)
			groups.append(g)
			continue
		except Exception as e:
			#print("fant ikke gruppen med feilmelding %s" % (e))
			pass
		if onlygroups == False:
			try:
				regex_username = re.search(r'cn=([^\,]*)', item, re.I).groups()[0]
				u = User.objects.get(username__iexact=regex_username)
				users.append(u)
				continue
			except:
				pass
			try:
				# TODO-fix this as PRKuser is replaced with user.profile
				u = User.objects.get(profile__distinguishedname=item)
				other_users.append(u)
				continue
			except:
				notfound.append(item)  # vi fant ikke noe, returner det vi fikk
	return {"groups": groups, "users": users, "other_users": other_users, "notfound": notfound}


def adgruppe_detaljer(request, pk):
	"""
	Vise informasjon om en konkret AD-gruppe
	Tilgangsstyring: må kunne vise informasjon om brukere
	"""
	import json
	gruppe = ADgroup.objects.get(pk=pk)

	member = human_readable_members(json.loads(gruppe.member))
	memberof = human_readable_members(json.loads(gruppe.memberof))

	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):
		return render(request, 'ad_adgruppe_detaljer.html', {
				"gruppe": gruppe,
				"member": member,
				"memberof": memberof,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def alle_adgrupper(request):
	"""
	Vise informasjon om AD-grupper
	Tilgangsstyring: må kunne vise informasjon om brukere
	"""
	search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space
	if len(search_term) > 1:
		if search_term[0:3] == "CN=":
			search_term = search_term[3:]
		search_term = search_term.split(",")[0]
		adgrupper = ADgroup.objects.filter(common_name__contains=search_term)
		for g in adgrupper:
			members = json.loads(g.member)
			g.member_count = len(members)
	else:
		adgrupper = ADgroup.objects.none()

	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):
		return render(request, 'ad_adgrupper_sok.html', {
				"adgrupper": adgrupper,
				"search_term": search_term,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def alle_os(request):
	"""
	Vise statistikk over operativsystemer for servere og klienter
	Tilgangsstyring: må kunne vise cmdb-maskiner
	"""
	required_permissions = 'systemoversikt.view_cmdbdevice'
	if request.user.has_perm(required_permissions):

		def cmdb_os_stats(maskiner):
			maskiner_stats = []
			os_major = maskiner.values('comp_os').distinct()
			for os in os_major:
				minor_versions = maskiner.filter(comp_os=os['comp_os']).values('comp_os_version').annotate(Count('comp_os_version'))
				for minor in minor_versions:
					if os['comp_os'] == "":
						os['comp_os'] = "__empty__"
					if minor['comp_os_version'] == "":
						minor['comp_os_version'] = "__empty__"

					maskiner_stats.append({
							'major': os['comp_os'],
							'minor': minor['comp_os_version'],
							'count': minor['comp_os_version__count']
					})
			return sorted(maskiner_stats, key=lambda os: os['major'], reverse=True)

		maskiner = CMDBdevice.objects.filter(active=True)
		maskiner_stats = cmdb_os_stats(maskiner)

		return render(request, 'cmdb_alle_server_os.html', {
			'maskiner_stats': maskiner_stats,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def alle_ip(request):
	"""
	Søke opp IP-adresser, både mot CMDB maskiner og via live dns-query
	Tilgangsstyring: må kunne vise cmdb-maskiner
	"""
	required_permissions = 'systemoversikt.view_cmdbdevice'
	if request.user.has_perm(required_permissions):

		from systemoversikt.views_import import load_dns_sonefile, load_vlan, load_nat, load_bigip, find_ip_in_dns, find_vlan, find_ip_in_nat, find_bigip
		import os
		import socket
		socket.setdefaulttimeout(1)

		search_term = request.POST.get('search_term', '').strip()  # strip removes trailing and leading space
		if search_term != "":
			# må legge dette i en konfigurasjonsfil, da det nå ligger to steder.
			domain = "oslo.kommune.no"

			import re
			import ipaddress
			search_term = search_term.replace('\"','').replace('\'','').replace(':',' ').replace('/', ' ').replace('\\', ' ') # dette vil feile for IPv6, som kommer på formatet [xxxx:xxxx::xxxx]:port
			search_ips = re.findall(r"([^,;\t\s\n\r]+)", search_term)

			ip_lookup = []
			not_ip_addresses = []
			for item in search_ips:
				try:
					ip_address = ipaddress.ip_address(item)
				except:
					not_ip_addresses.append(item)
					continue  # skip this item

				dns_ekstern = load_dns_sonefile(os.path.dirname(os.path.abspath(__file__)) + "/import/oslofelles_dns_ekstern", domain)
				dns_intern = load_dns_sonefile(os.path.dirname(os.path.abspath(__file__)) + "/import/oslofelles_dns_intern", domain)
				vlan_data = load_vlan(os.path.dirname(os.path.abspath(__file__)) + "/import/oslofelles_vlan.tsv")
				nat_data = load_nat(os.path.dirname(os.path.abspath(__file__)) + "/import/oslofelles_nat.tsv")
				bigip_data = load_bigip(os.path.dirname(os.path.abspath(__file__)) + "/import/oslofelles_vip.tsv")

				dns_i = find_ip_in_dns(ip_address, dns_intern)
				dns_e = find_ip_in_dns(ip_address, dns_ekstern)
				vlan = find_vlan(ip_address, vlan_data)
				nat = find_ip_in_nat(ip_address, nat_data)
				vip = find_bigip(ip_address, bigip_data)

				def dns_live(ip_address):
					try:
						return socket.gethostbyaddr(str(ip_address))[0]
					except:
						return None

				dns_live = dns_live(ip_address)

				try:
					comp_name = CMDBdevice.objects.get(comp_ip_address=item).comp_name
				except:
					comp_name = None

				ip_lookup.append({
						"address": ip_address,
						"comp_name": comp_name,
						"dns_i": dns_i,
						"dns_e": dns_e,
						"dns_live": dns_live,
						"vlan": vlan,
						"vip": vip,
				})
		else:
			ip_lookup = None
			not_ip_addresses = None


		return render(request, 'cmdb_ip_sok.html', {
			'request': request,
			'ip_lookup': ip_lookup,
			'search_term': search_term,
			'not_ip_addresses': not_ip_addresses,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

"""
def ad_prk_sok(request):
		search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space
		search_term = search_term.replace(",DC=oslofelles,DC=oslo,DC=kommune,DC=no","")


		"CN=DS-BRE_OKNMI_BUDSJ_BUDSJFELL_IS,OU=BRE,OU=Tilgangsgrupper,OU=OK,DC=oslofelles,DC=oslo,DC=kommune,DC=no"
		"ou=DS-BRE_OKNMI_BUDSJ_BUDSJFELL_IS,ou=BRE,ou=Tilgangsgrupper,ou=OK"

		return render(request, 'ad_prk_sok.html', {
			'request': request,
			'search_term': search_term,
		})
"""

def prk_skjema(request, skjema_id):
	"""
	Bla i PRK-skjemaer, vise et konkret skjema
	Tilgangsstyring: må kunne vise prk-skjemaer
	"""
	required_permissions = 'systemoversikt.view_prkvalg'
	if request.user.has_perm(required_permissions):

		search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space

		skjema = PRKskjema.objects.get(pk=skjema_id)

		if search_term:
			valg = PRKvalg.objects.filter(skjemanavn=skjema).filter(virksomhet__virksomhetsforkortelse=search_term).order_by("gruppering")
		else:
			valg = PRKvalg.objects.filter(skjemanavn=skjema).order_by("gruppering")

		return render(request, 'prk_vis_skjema.html', {
			'request': request,
			'skjema': skjema,
			'valg': valg,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def prk_browse(request):
	"""
	Bla i PRK-skjemaer
	Tilgangsstyring: må kunne vise prk-skjemaer
	"""
	required_permissions = 'systemoversikt.view_prkvalg'
	if request.user.has_perm(required_permissions):

		search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space

		if search_term:
			skjema = PRKskjema.objects.filter(skjemanavn__icontains=search_term)
		else:
			skjema = PRKskjema.objects.all()

		skjema = skjema.order_by('skjematype', 'skjemanavn')

		return render(request, 'prk_bla.html', {
			'request': request,
			'skjema': skjema,
			'search_term': search_term,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def alle_prk(request):
	"""
	Søke og vise PRK-skjemaer
	Tilgangsstyring: må kunne vise prk-skjemaer
	"""
	required_permissions = 'systemoversikt.view_prkvalg'
	if request.user.has_perm(required_permissions):

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
			'search_term': search_term,
			'skjemavalg': skjemavalg,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })




def alle_maskiner(request):
	"""
	Søke og vise alle maskiner
	Tilgangsstyring: må kunne vise cmdb-maskiner
	"""
	required_permissions = 'systemoversikt.view_cmdbdevice'
	if request.user.has_perm(required_permissions):

		def filter(input):

			search_term = input["search_term"]
			comp_os = input["comp_os"]
			comp_os_version = input["comp_os_version"]

			if search_term == "" and comp_os == "" and comp_os_version == "":
				return CMDBdevice.objects.none()

			if search_term == "__all__":
				search_term = ""

			devices = CMDBdevice.objects.filter(active=True).filter(Q(comp_name__icontains=search_term) | Q(sub_name__navn__icontains=search_term))

			if comp_os == "__empty__" and comp_os_version == "__empty__":
				comp_os_and_version_none = CMDBdevice.objects.filter(active=True).filter(Q(comp_os="") & Q(comp_os_version=""))
				return devices & comp_os_and_version_none  # snitt/intersection av to sett

			if comp_os == "__empty__":
				comp_os_none = CMDBdevice.objects.filter(active=True).filter(comp_os="").filter(comp_os_version__icontains=comp_os_version)
				return devices & comp_os_none  # snitt/intersection av to sett

			if comp_os_version == "__empty__":
				comp_os_version_none = CMDBdevice.objects.filter(active=True).filter(comp_os_version="").filter(comp_os__icontains=comp_os)
				return devices & comp_os_version_none  # snitt/intersection av to sett

			if comp_os != "":
				devices = devices.filter(comp_os__icontains=comp_os)

			if comp_os_version != "":
				devices = devices.filter(comp_os_version__icontains=comp_os_version)

			return devices

		search_term = request.GET.get('search_term', '').strip()  # strip removes trailing and leading space
		comp_os = request.GET.get('comp_os', '').strip()
		comp_os_version = request.GET.get('comp_os_version', '').strip()

		maskiner = filter({
				"search_term": search_term,
				"comp_os": comp_os,
				"comp_os_version": comp_os_version
			})

		maskiner = maskiner.order_by('comp_os')

		return render(request, 'cmdb_maskiner_sok.html', {
			'request': request,
			'maskiner': maskiner,
			'search_term': search_term,
			'comp_os': comp_os,
			'comp_os_version': comp_os_version,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def servere_utfaset(request):
	"""
	Vise alle avviklede maskiner
	Tilgangsstyring: må kunne vise cmdb-maskiner
	"""
	required_permissions = 'systemoversikt.view_cmdbdevice'
	if request.user.has_perm(required_permissions):

		maskiner = CMDBdevice.objects.filter(active=False).order_by("-sist_oppdatert")
		return render(request, 'cmdb_alle_maskiner_utfaset.html', {
			'request': request,
			'maskiner': maskiner,
		})

	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

def alle_databaser(request):
	"""
	Søke og vise alle databaser
	Tilgangsstyring: må kunne vise cmdb-databaser
	"""
	required_permissions = 'systemoversikt.view_cmdbdatabase'
	if request.user.has_perm(required_permissions):

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


		return render(request, 'cmdb_databaser_sok.html', {
			'request': request,
			'databaser': databaser,
			'search_term': search_term,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

def alle_cmdbref(request):
	"""
	Søke og vise alle business services (bs)
	Tilgangsstyring: må kunne vise cmdb-referanser (bs)
	"""
	required_permissions = ['systemoversikt.view_cmdbref', 'auth.view_user']
	if any(map(request.user.has_perm, required_permissions)):

		search_term = request.GET.get('search_term', "").strip()

		if search_term == "__all__":
			cmdbref = CMDBRef.objects.all()
		elif len(search_term) < 1: # if one or less, return nothing
			cmdbref = CMDBRef.objects.none()
		else:
			cmdbref = CMDBRef.objects.filter(navn__icontains=search_term)

		cmdbref = cmdbref.order_by("-operational_status", "service_classification", Lower("navn"))

		return render(request, 'cmdb_bs_sok.html', {
			'request': request,
			'cmdbref': cmdbref,
			'search_term': search_term,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def cmdbdevice(request, pk):
	"""
	Søke og vise maskiner og databaser tilknyttet en business service for et system
	Tilgangsstyring: må kunne vise cmdb-referanser (bs)
	"""
	required_permissions = 'systemoversikt.view_cmdbref'
	if request.user.has_perm(required_permissions):
		cmdbref = CMDBRef.objects.get(pk=pk)
		cmdbdevices = CMDBdevice.objects.filter(sub_name=cmdbref)
		databaser = CMDBdatabase.objects.filter(sub_name=cmdbref)

		return render(request, 'cmdb_maskiner_detaljer.html', {
			'request': request,
			'cmdbref': [cmdbref],
			'cmdbdevices': cmdbdevices,
			'databaser': databaser,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def alle_avtaler(request, virksomhet=None):
	"""
	Vise alle avtaler
	Tilgangsstyring: ÅPEN
	"""
	avtaler = Avtale.objects.all()
	if virksomhet:
		virksomhet = Virksomhet.objects.get(pk=virksomhet)
		avtaler = avtaler.filter(Q(virksomhet=virksomhet) | Q(leverandor_intern=virksomhet))
	return render(request, 'avtale_alle.html', {
		'request': request,
		'avtaler': avtaler,
		'virksomhet': virksomhet,
	})


def avtaledetaljer(request, pk):
	"""
	Vise detaljer for en avtale
	Tilgangsstyring: ÅPEN
	"""
	avtale = Avtale.objects.get(pk=pk)
	return render(request, 'avtale_detaljer.html', {
		'request': request,
		'avtale': avtale,
	})


def databehandleravtaler_virksomhet(request, pk):
	"""
	Vise alle databehandleravtaler for en valgt virksomhet
	Tilgangsstyring: ÅPEN
	"""
	virksomet = Virksomhet.objects.get(pk=pk)
	utdypende_beskrivelse = ("Viser databehandleravtaler for %s" % virksomet)
	avtaler = Avtale.objects.filter(virksomhet=pk).filter(avtaletype=1) # 1 er databehandleravtaler
	return render(request, 'avtale_alle.html', {
		'request': request,
		'avtaler': avtaler,
		'utdypende_beskrivelse': utdypende_beskrivelse,
	})


def alle_dpia(request):
	"""
	Under utvikling: Vise alle DPIA-vurderinger
	Tilgangsstyring: ÅPEN
	"""
	alle_dpia = DPIA.objects.all()
	return render(request, 'dpia_alle.html', {
		'request': request,
		'alle_dpia': alle_dpia,
	})


def detaljer_dpia(request, pk):
	"""
	Under utvikling: Vise metadata om en DPIA-vurdering
	Tilgangsstyring: ÅPEN
	"""
	dpia = DPIA.objects.get(pk=pk)
	return render(request, 'detaljer_dpia.html', {
		'request': request,
		'dpia': dpia,
	})


# støttefunksjon for LDAP
def decode_useraccountcontrol(code):
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


# støttefunksjon for LDAP
def ldap_query(ldap_path, ldap_filter, ldap_properties, timeout):
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
def ldap_get_user_details(username):
	import re

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
"""

"""
def ldap_get_group_details(group):
	import re

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

# støttefunksjon for LDAP
def ldap_get_recursive_group_members(group):
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


# støttefunksjon for LDAP
def ldap_get_details(name, ldap_filter):
	import re
	import json

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
					if key in ['cn', 'sAMAccountName', 'mail', 'givenName', 'displayName', 'sn', 'userAccountControl', 'logonCount', 'memberOf', 'lastLogonTimestamp', 'title', 'description', 'otherMobile', 'mobile', 'objectClass', 'thumbnailPhoto']:
						# if not, then we don't bother decoding the value for now
						attrs_decoded[key] = []
						if key == "lastLogonTimestamp":
							# always just one timestamp, hence item 0 hardcoded
							## TODO flere steder
							ms_timestamp = int(attrs[key][0][:-1].decode())  # removing one trailing digit converting 100ns to microsec.
							converted_date = datetime.datetime(1601,1,1) + datetime.timedelta(microseconds=ms_timestamp)
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
def ldap_exact(name):
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


def ad(request):
	"""
	Startside for LDAP/AD-spørringer
	Tilgangsstyring: ÅPEN
	"""
	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):

		return render(request, 'ad_index.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def ad_details(request, name):
	"""
	Søke opp en eksakt CN i AD
	Tilgangsstyring: Må kunne vise informasjon om brukere
	"""
	import time
	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):
		runtime_t0 = time.time()
		ldap_filter = ('(cn=%s)' % name)
		result = ldap_get_details(name, ldap_filter)
		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		messages.success(request, 'Dette søket tok %s sekunder' % round(logg_total_runtime, 1))

		return render(request, 'ad_details.html', {
			'request': request,
			'result': result,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def ad_exact(request, name):
	"""
	Søke opp et eksakt DN i AD
	Tilgangsstyring: Må kunne vise informasjon om brukere
	"""
	import time
	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):
		runtime_t0 = time.time()
		ldap_filter = ('(distinguishedName=%s)' % name)
		result = ldap_get_details(name, ldap_filter)
		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		messages.success(request, 'Dette søket tok %s sekunder' % round(logg_total_runtime, 1))

		return render(request, 'ad_details.html', {
			'request': request,
			'result': result,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def recursive_group_members(request, group):
	"""
	Søke opp alle brukere rekursivt med tilgang til et DN i AD
	Tilgangsstyring: Må kunne vise informasjon om brukere
	"""
	import time
	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):
		runtime_t0 = time.time()
		result = ldap_get_recursive_group_members(group)
		runtime_t1 = time.time()
		logg_total_runtime = runtime_t1 - runtime_t0
		messages.success(request, 'Dette søket tok %s sekunder' % round(logg_total_runtime, 1))

		return render(request, 'ad_recursive.html', {
			'request': request,
			'result': result,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })




### UBW

"""
Det viktigste med tilgangsstyringen her er integritet, slik at en eier av en enhet kan være sikker på at ingen andre har importert/endret på sine data.
"""

def kvartal(date):
	try:
		kvartal = (date.month - 1) // 3 + 1 # // is floor division
		if kvartal in [1, 2, 3, 4]:
			return ("Q%s") % kvartal
	except:
		return "error"

def ubw_api(request, pk):
	enhet = UBWRapporteringsenhet.objects.get(pk=pk)

	faktura_eksport = []

	fakturaer = UBWFaktura.objects.filter(belongs_to=enhet).order_by('-ubw_voucher_date')
	for faktura in fakturaer:
		eksportdata = {}

		# noen felter er med vilje ikke tatt med
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

		eksportdata["UBW Virksomhets-ID"] = faktura.ubw_client
		eksportdata["UBW sist oppdatert"] = faktura.ubw_last_update

		try:
			eksportdata["Kategori"] = faktura.metadata_reference.kategori.name
		except:
			eksportdata["Kategori"] = ""
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
			leverandor = faktura.metadata_reference.leverandor
			if leverandor != None:
				eksportdata["Leverandør"] = leverandor
			else:
				eksportdata["Leverandør"] = faktura.ubw_xapar_id
		except:
			eksportdata["Leverandør"] = faktura.ubw_xapar_id

		faktura_eksport.append(eksportdata)

	estimat = UBWEstimat.objects.filter(belongs_to=enhet).filter(aktiv=True).order_by('-periode_paalopt')
	for e in estimat:
		eksportdata = {}

		# noen felter er med vilje ikke tatt med
		eksportdata["kilde"] = e.prognose_kategori
		eksportdata["UBW Kontonr"] = e.estimat_account
		eksportdata["UBW Koststednr"] = e.estimat_dim_1
		eksportdata["UBW prosjektnr"] = e.estimat_dim_4
		try: # i tilfelle noen glemmer å fylle ut et estimat i estimatet..
			eksportdata["UBW beløp"] = float(e.estimat_amount)
		except:
			eksportdata["UBW beløp"] = 0
		eksportdata["UBW beskrivelse"] = e.ubw_description
		eksportdata["Leverandør"] = e.leverandor
		"""
		eksportdata["UBW Kontonavn"] = ""
		eksportdata["UBW-periode (YYYYMM)"] = ""
		eksportdata["UBW Koststednavn"] = ""
		eksportdata["UBW prosjektnavn"] = ""
		eksportdata["UBW voucher_type"] = ""
		eksportdata["UBW voucher_no"] = ""
		eksportdata["UBW sequence_no"] = ""
		eksportdata["UBW bilagsdato"] = ""
		eksportdata["UBW leverandørnr"] = ""
		eksportdata["UBW leverandørnavn"] = ""
		eksportdata["UBW Virksomhets-ID"] = ""
		eksportdata["UBW sist oppdatert"] = ""
		"""
		try:
			eksportdata["Kategori"] = e.kategori.name
		except:
			eksportdata["Kategori"] = ""

		try:
			eksportdata["Periode påløpt år"] = e.periode_paalopt.year
			eksportdata["Periode påløpt måned"] = e.periode_paalopt.month
			eksportdata["Periode påløpt kvartal"] = kvartal(e.periode_paalopt)
		except:
			eksportdata["Periode påløpt år"] = ""
			eksportdata["Periode påløpt måned"] = ""
			eksportdata["Periode påløpt kvartal"] = ""

		faktura_eksport.append(eksportdata)

	return JsonResponse(faktura_eksport, safe=False)


def ubw_home(request):
	enheter = UBWRapporteringsenhet.objects.all()

	return render(request, 'ubw_home.html', {
				'enheter': enheter,
			})

def ubw_enhet(request, pk):
	import csv
	import datetime
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
			if row["account"] != None:
				try:
					obj, created = UBWFaktura.objects.get_or_create(
						ubw_voucher_no=try_int(row["voucher_no"]),
						ubw_sequence_no=try_int(row["sequence_no"]),
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
					obj.ubw_tab = row["tab"] #CharField
					obj.ubw_account = try_int(row["account"]) #IntegerField
					obj.ubw_xaccount = row["xaccount"] #CharField
					obj.ubw_period = try_int(row["period"]) #IntegerField
					obj.ubw_dim_1 = try_int(row["dim_1"]) #IntegerField
					obj.ubw_xdim_1 = row["xdim_1"] #CharField
					obj.ubw_dim_4 = try_int(row["dim_4"]) #IntegerField
					obj.ubw_xdim_4 = row["xdim_4"] #CharField
					obj.ubw_voucher_type = row["voucher_type"] #CharField
					#obj.ubw_voucher_no = try_int(row[""]) #IntegerField
					#obj.ubw_sequence_no = try_int(row[""]) #IntegerField
					obj.ubw_voucher_date = line["voucher_date"]
					obj.ubw_order_id = try_int(row["order_id"]) #IntegerField
					obj.ubw_apar_id = try_int(row["apar_id"]) #IntegerField
					obj.ubw_xapar_id = row["xapar_id"] #CharField
					obj.ubw_description = row["description"] #TextField
					obj.ubw_amount = row["amount"] #DecimalField
					obj.ubw_apar_type = row["apar_type"] #CharField
					obj.ubw_att_1_id = row["att_1_id"] #CharField
					obj.ubw_att_4_id = row["att_4_id"] #CharField
					obj.ubw_client = try_int(row["client"]) #IntegerField
					obj.ubw_last_update = line["last_update"]

					obj.save()
					if er_ny:
						count_new += 1
					else:
						count_updated += 1

				except Exception as e:
					error_message = ("Kunne ikke importere: %s" % e)
					messages.warning(request, error_message)
					print(error_message)
			else:
				messages.warning(request, "Raden manglet beløp, ignorert")

		ferdig_melding = ("Importerte %s nye. Oppdaterte %s som eksisterte fra før." % (count_new, count_updated))
		messages.success(request, ferdig_melding)

	if request.user in enhet.users.all():

		import pandas as pd
		import numpy as np
		import xlrd

		if request.method == "POST":
			try:
				file = request.FILES['fileupload'] # this is my file
				#print(file.name)
				uploaded_file = {"name": file.name, "size": file.size,}
				if ".csv" in file.name:
					#print("CSV")
					decoded_file = file.read().decode('latin1').splitlines()
					data = list(csv.DictReader(decoded_file, delimiter=";"))
					# need to convert date string to date and amount to Decimal
					for line in data:
						line["voucher_date"] = datetime.datetime.strptime(line["last_update"], "%d.%m.%Y").date() #DateField
						line["last_update"] = datetime.datetime.strptime(line["last_update"], "%d.%m.%Y").date() #DateField
						line["amount"] = Decimal((line["amount"].replace(",",".")))


				if ".xlsx" in file.name:
					#print("Excel")
					dfRaw = pd.read_excel(io=file.read())
					dfRaw = dfRaw.replace(np.nan, '', regex=True)
					data = dfRaw.to_dict('records')
					for line in data:
						line["amount"] = Decimal(line["amount"])


					#dfRaw["dateTimes"].map(lambda x: xlrd.xldate_as_tuple(x, datemode))
					#workbook = xlrd.open_workbook(file_contents=file.read())
					#datemode = workbook.datemode
					#sheet = workbook.sheet_by_index(0)
					#data = [sheet.row_values(rowx) for rowx in range(sheet.nrows)]
					#print(data)

					#data = list(csv.DictReader(decoded_file, delimiter=";"))

				print("\n%s\n" % data)
				import_function(data)

			except Exception as e:
				error_message = ("Kunne ikke lese fil: %s" % e)
				messages.warning(request, error_message)
				print(error_message)

		uploaded_file = None
		dager_gamle = 550
		tidsgrense = datetime.date.today() - datetime.timedelta(days=dager_gamle)
		gyldige_fakturaer = UBWFaktura.objects.filter(belongs_to=enhet).filter(ubw_voucher_date__gte=tidsgrense)
		nye_fakturaer = gyldige_fakturaer.filter(metadata_reference=None).order_by('-ubw_voucher_date')
		behandlede_fakturaer = gyldige_fakturaer.filter(~Q(metadata_reference=None)).order_by('-ubw_voucher_date')


		model = UBWFaktura
		domain = ("%s://%s") % (settings.SITE_SCHEME, settings.SITE_DOMAIN)

		return render(request, 'ubw_enhet.html', {
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

def ubw_generer_ekstra_valg(belongs_to):
	data = []

	# trenger kategorien to ganger da den ene er verdi og den andre er visning. Like i dette tilfellet.
	leverandor_kategorier = list(UBWFaktura.objects.filter(belongs_to=belongs_to).values_list('ubw_xapar_id', 'ubw_xapar_id').distinct())
	data.append({'field': 'leverandor', 'choices': leverandor_kategorier})

	return data


def ubw_ekstra(request, faktura_id, pk=None):
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
				'form': form,
				'faktura': faktura,
				'enhet': enhet,
				'ekstra': True,
				'kategorier': kategorier,
		})

def ubw_kategori(request, belongs_to):
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
	enhet = get_object_or_404(UBWRapporteringsenhet, pk=belongs_to)
	kategorier = UBWFakturaKategori.objects.filter(belongs_to=enhet)
	estimat = ubw_my_estimates(request, enhet)
	model = UBWEstimat
	return render(request, 'ubw_estimat_list.html', {
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

	prognose_koststednummer = list(UBWFaktura.objects.filter(belongs_to=belongs_to).values_list('ubw_account', 'ubw_xaccount').distinct())
	data.append({'field': 'estimat_account', 'choices': prognose_koststednummer})

	prognose_koststednummer = list(UBWFaktura.objects.filter(belongs_to=belongs_to).values_list('ubw_dim_1', 'ubw_xdim_1').distinct())
	data.append({'field': 'estimat_dim_1', 'choices': prognose_koststednummer})

	prognose_prosjektnummer = list(UBWFaktura.objects.filter(belongs_to=belongs_to).values_list('ubw_dim_4', 'ubw_xdim_4').distinct())
	data.append({'field': 'estimat_dim_4', 'choices': prognose_prosjektnummer})

	prognose_leverandor = list(UBWFaktura.objects.filter(belongs_to=belongs_to).values_list('ubw_xapar_id', 'ubw_xapar_id').distinct())
	data.append({'field': 'leverandor', 'choices': prognose_leverandor})

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


def ubw_estimat_delete(request, pk):
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


def ubw_estimat_copy(request, pk):
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


### UBW end