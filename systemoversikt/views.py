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
from django.http import HttpResponseBadRequest, JsonResponse
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
import datetime
from django.urls import reverse

FELLES_OG_SEKTORSYSTEMER = ("FELLESSYSTEM", "SEKTORSYSTEM")
SYSTEMTYPE_PROGRAMMER = "Selvstendig klientapplikasjon"


def virksomhet_til_bruker(request):
	try:
		vir = request.user.profile.virksomhet.virksomhetsforkortelse
	except:
		vir = False
	return vir


def minside(request):
	return render(request, 'minside.html', {
		'request': request,
	})


def dashboard_all(request, virksomhet=None):
	try:
		virksomhet = Virksomhet.objects.get(pk=virksomhet)
	except:
		raise Http404("Virksomhet med angitt ID finnes ikke.")

	alle_virksomheter = Virksomhet.objects.all()

	systemer_drifter = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=virksomhet).filter(~Q(ibruk=False)).order_by('systemnavn')
	systemer_eier = System.objects.filter(systemeier=virksomhet).filter(~Q(ibruk=False)).order_by('systemnavn')
	systemer_forvalter = System.objects.filter(systemforvalter=virksomhet).filter(~Q(ibruk=False)).order_by('systemnavn')
	systemer_felles = System.objects.filter(systemeierskapsmodell="FELLESSYSTEM").filter(~Q(ibruk=False)).order_by('systemnavn')

	# finne systemer virksomheten abonnerer på behandlinger for
	systembruk_virksomhet = []
	virksomhetens_relevante_bruk = SystemBruk.objects.filter(brukergruppe=virksomhet).filter(del_behandlinger=True)
	for bruk in virksomhetens_relevante_bruk:
		systembruk_virksomhet.append(bruk.system)
	# finne alle egne behandlinger
	virksomhetens_behandlinger = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=virksomhet)
	# finne alle behandlinger for identifiserte systemer merket fellesbehandling
	delte_behandlinger = BehandlingerPersonopplysninger.objects.filter(systemer__in=systembruk_virksomhet).filter(fellesbehandling=True)
	# slå sammen felles og egne behandlinger til et sett
	alle_relevante_behandlinger = virksomhetens_behandlinger.union(delte_behandlinger).order_by('internt_ansvarlig')
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
		ros_ikke_behov = systemer.filter(risikovurdering_behovsvurdering=0).count()
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

	return render(request, 'dashboard.html', {
		'request': request,
		'systemlister': systemlister,
		'alle_virksomheter': alle_virksomheter,
	})


def permissions(request):
	required_permissions = 'auth.view_ansvarlig'
	if request.user.has_perm(required_permissions):
		ansvarlige = Ansvarlig.objects.all()
		return render(request, 'permissions.html', {
			'ansvarlige': ansvarlige,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def roller(request):
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
			return render(request, 'roller.html', {
				'request': request,
				'groups': groups,
	})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })



def video(request):
	return render(request, 'video.html', {
		'request': request,
	})


def csrf403(request):
	return render(request, 'csrf403.html', {
		'request': request,
	})


def login(request):
	return redirect("/admin/")


def logger(request):
	recent_admin_loggs = LogEntry.objects.order_by('-action_time')[:300]
	return render(request, 'logger.html', {
		'request': request,
		'recent_admin_loggs': recent_admin_loggs,
	})


def logger_audit(request):
	recent_loggs = ApplicationLog.objects.order_by('-opprettet')[:150]
	return render(request, 'logger_audit.html', {
		'request': request,
		'recent_loggs': recent_loggs,
	})


def home(request):

	antall_systemer = System.objects.count()
	nyeste_systemer = System.objects.all().order_by('-pk')[:5]

	antall_programvarer = Programvare.objects.count()
	nyeste_programvarer = Programvare.objects.all().order_by('-pk')[:5]

	antall_behandlinger = BehandlingerPersonopplysninger.objects.count()

	#print(nyeste_systemer)
	kategorier = SystemKategori.objects.all()

	return render(request, 'home.html', {
		'request': request,
		'kategorier': kategorier,
		'antall_systemer': antall_systemer,
		'nyeste_systemer': nyeste_systemer,
		'antall_programvarer': antall_programvarer,
		'nyeste_programvarer': nyeste_programvarer,
		'antall_behandlinger': antall_behandlinger,
	})


def alle_definisjoner(request):
	definisjoner = Definisjon.objects.all().order_by('begrep')
	return render(request, 'alle_definisjoner.html', {
		'request': request,
		'definisjoner': definisjoner,
	})


def definisjon(request, begrep):
	passende_definisjoner = Definisjon.objects.filter(begrep=begrep)
	return render(request, 'detaljer_definisjon.html', {
		'request': request,
		'begrep': begrep,
		'definisjoner': passende_definisjoner,
	})


def ansvarlig(request, pk):
	ansvarlig = Ansvarlig.objects.get(pk=pk)
	if not ansvarlig.brukernavn.is_active:
		messages.warning(request, 'Denne brukeren er deaktivert!')

	systemeier_for = System.objects.filter(~Q(ibruk=False)).filter(systemeier_kontaktpersoner_referanse=pk)
	systemforvalter_for = System.objects.filter(~Q(ibruk=False)).filter(systemforvalter_kontaktpersoner_referanse=pk)
	systemforvalter_bruk_for = SystemBruk.objects.filter(systemforvalter_kontaktpersoner_referanse=pk)
	kam_for = Virksomhet.objects.filter(uke_kam_referanse=pk)
	#tjenesteleder_for = Tjeneste.objects.filter(tjenesteleder=pk)
	#tjenesteforvalter_for = Tjeneste.objects.filter(tjenesteforvalter=pk)
	avtale_ansvarlig_for = Avtale.objects.filter(avtaleansvarlig=pk)
	ikt_kontakt_for = Virksomhet.objects.filter(ikt_kontakt=pk)
	sertifikatbestiller_for = Virksomhet.objects.filter(autoriserte_bestillere_sertifikater__person=pk)
	virksomhetsleder_for = Virksomhet.objects.filter(leder=pk)
	autorisert_bestiller_for = Virksomhet.objects.filter(autoriserte_bestillere_tjenester=pk)
	personvernkoordinator_for = Virksomhet.objects.filter(personvernkoordinator=pk)
	informasjonssikkerhetskoordinator_for = Virksomhet.objects.filter(informasjonssikkerhetskoordinator=pk)
	behandlinger_for = BehandlingerPersonopplysninger.objects.filter(oppdateringsansvarlig=pk)

	return render(request, 'detaljer_ansvarlig.html', {
		'request': request,
		'ansvarlig': ansvarlig,
		'systemeier_for': systemeier_for,
		'systemforvalter_for': systemforvalter_for,
		'systemforvalter_bruk_for': systemforvalter_bruk_for,
		'kam_for': kam_for,
		#'tjenesteleder_for': tjenesteleder_for,
		#'tjenesteforvalter_for': tjenesteforvalter_for,
		'avtale_ansvarlig_for': avtale_ansvarlig_for,
		'ikt_kontakt_for': ikt_kontakt_for,
		'sertifikatbestiller_for': sertifikatbestiller_for,
		'virksomhetsleder_for': virksomhetsleder_for,
		'autorisert_bestiller_for': autorisert_bestiller_for,
		'personvernkoordinator_for': personvernkoordinator_for,
		'informasjonssikkerhetskoordinator_for': informasjonssikkerhetskoordinator_for,
		'behandlinger_for': behandlinger_for,
	})


def alle_ansvarlige(request):
	ansvarlige = Ansvarlig.objects.all().order_by('brukernavn__first_name')
	return render(request, 'alle_ansvarlige.html', {
		'request': request,
		'ansvarlige': ansvarlige,
	})


def alle_ansvarlige_eksport(request):
	required_permissions = 'systemoversikt.view_behandlingerpersonopplysninger'
	if request.user.has_perm(required_permissions):
		ansvarlige = Ansvarlig.objects.filter(brukernavn__is_active=True)
		return render(request, 'alle_ansvarlige_eksport.html', {
			'request': request,
			'ansvarlige': ansvarlige,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def systemkvalitet_virksomhet(request, pk):
	required_permissions = 'systemoversikt.change_system'
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
	system = System.objects.get(pk=pk)


	avhengigheter_graf = {"nodes": [], "edges": []}
	observerte_driftsmodeller = set()

	def parent(system):
		if system.driftsmodell_foreignkey is not None:
			return system.driftsmodell_foreignkey.navn
		else:
			return "Ukjent"

	# registrere dette systemet som en node
	avhengigheter_graf["nodes"].append({"data": { "parent": parent(system), "id": system.pk, "name": system.systemnavn, "shape": "ellipse", "color": "#4f90d6" }},)
	observerte_driftsmodeller.add(system.driftsmodell_foreignkey)

	for s in system.datautveksling_mottar_fra.all():
		avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": "#dca85a", "href": reverse('systemdetaljer', args=[s.pk]) }},)
		avhengigheter_graf["edges"].append({"data": { "source": s.pk, "target": system.pk, "linestyle": "solid" }},)
		observerte_driftsmodeller.add(s.driftsmodell_foreignkey)
	for s in system.system_datautveksling_avleverer_til.all():
		avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": "#dca85a", "href": reverse('systemdetaljer', args=[s.pk]) }},)
		avhengigheter_graf["edges"].append({"data": { "source": s.pk, "target": system.pk, "linestyle": "solid" }},)
		observerte_driftsmodeller.add(s.driftsmodell_foreignkey)

	for s in system.datautveksling_avleverer_til.all():
		avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": "#dca85a", "href": reverse('systemdetaljer', args=[s.pk]) }},)
		avhengigheter_graf["edges"].append({"data": { "source": system.pk, "target": s.pk, "linestyle": "solid" }},)
		observerte_driftsmodeller.add(s.driftsmodell_foreignkey)
	for s in system.system_datautveksling_mottar_fra.all():
		avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": "#dca85a", "href": reverse('systemdetaljer', args=[s.pk]) }},)
		avhengigheter_graf["edges"].append({"data": { "source": system.pk, "target": s.pk, "linestyle": "solid" }},)
		observerte_driftsmodeller.add(s.driftsmodell_foreignkey)

	for s in system.avhengigheter_referanser.all():
		avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": "#9c9c9c", "href": reverse('systemdetaljer', args=[s.pk]) }},)
		avhengigheter_graf["edges"].append({"data": { "source": system.pk, "target": s.pk, "linestyle": "dashed" }},)
		observerte_driftsmodeller.add(s.driftsmodell_foreignkey)
	for s in system.system_avhengigheter_referanser.all():
		avhengigheter_graf["nodes"].append({"data": { "parent": parent(s), "id": s.pk, "name": s.systemnavn, "shape": "ellipse", "color": "#9c9c9c", "href": reverse('systemdetaljer', args=[s.pk]) }},)
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

	return render(request, 'detaljer_system.html', {
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
	systemer = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=163)  # 163=UKE
	programvarer = Programvare.objects.all()
	return render(request, 'alle_systemer_pakket.html', {
		'request': request,
		'systemer': systemer,
		'programvarer': programvarer,
	})


def systemer_test(request):
	systemer = System.objects.filter(driftsmodell_foreignkey__ansvarlig_virksomhet=163)  # 163=UKE
	return render(request, 'alle_systemer_test.html', {
		'request': request,
		'systemer': systemer,
	})


def systemklassifisering_detaljer(request, id):
	utvalg_systemer = System.objects.filter(systemeierskapsmodell=id)
	return render(request, 'alle_systemer_uten_paginering.html', {
		'request': request,
		'overskrift': ("Systemklassifisering: %s" % id.lower()),
		'systemer': utvalg_systemer,
	})


def systemtype_detaljer(request, pk):
	utvalg_systemer = System.objects.filter(systemtyper=pk)
	systemtype_navn = Systemtype.objects.get(pk=pk).kategorinavn
	return render(request, 'alle_systemer_uten_paginering.html', {
		'request': request,
		'overskrift': ("Systemtype: %s" % systemtype_navn),
		'systemer': utvalg_systemer,
	})


def alle_systemer(request, utvalg="alle", items=200, page=1):
	search_query = request.GET.get('search', '').strip()  # strip removes trailing and leading space
	if search_query != '':
		# veldig enkelt søk. Kun case insensitivt og må ellers matche 100%
		aktuelle_systemer = System.objects.filter(Q(systemnavn__icontains=search_query) | Q(systembeskrivelse__icontains=search_query))
	else:
		aktuelle_systemer = System.objects

	if utvalg != "alle":

		utvalg_systemer = System.objects.none()
		overskrift = "Ugyldig valg"

		if utvalg == "itas":
			utvalg_systemer = aktuelle_systemer.filter(driftsmodell_foreignkey__in=[8,])
			overskrift = "Funksjonalitet og rammeverk på ITAS"

		if utvalg == "sektorfelles":
			utvalg_systemer = aktuelle_systemer.filter(systemeierskapsmodell__in=FELLES_OG_SEKTORSYSTEMER)
			overskrift = "Sektor- og fellessystemer"

		if utvalg == "systemapplikasjoner":
			utvalg_systemer = aktuelle_systemer.filter(systemtyper__kategorinavn=SYSTEMTYPE_PROGRAMMER)
			overskrift = "Applikasjoner og enkeltstående programvarer"

		if utvalg == "nyfellesiktplattform":
			utvalg_systemer = aktuelle_systemer.filter(driftsmodell_foreignkey__in=[3,4,5,6,7])
			overskrift = "Systemer på (ny) felles IKT-plattform"

		if utvalg == "gammelfellesiktplattform":
			utvalg_systemer = aktuelle_systemer.filter(driftsmodell_foreignkey__in=[9,8])
			overskrift = "Systemer på Oslo kommunes datasenter (Oslofelles)"

		if utvalg == "lokaldrift":
			utvalg_systemer = aktuelle_systemer.filter(driftsmodell_foreignkey__in=[1,])
			overskrift = "Lokalt driftede"

		if utvalg == "saas":
			utvalg_systemer = aktuelle_systemer.filter(driftsmodell_foreignkey__in=[2,])
			overskrift = "Driftet av ekstern leverandør / kjøpt som skytjeneste"

		if utvalg == "utendriftsmodell":
			utvalg_systemer = aktuelle_systemer.filter(driftsmodell_foreignkey=None)
			overskrift = "Ukjent driftsmodell"

	else:  #utvalg er "alle"
		#systemer = System.objects.filter(~Q(systemeierskapsmodell__in=FELLES_OG_SEKTORSYSTEMER)).filter(~Q(systemtyper__kategorinavn="Selvstendig klientapplikasjon")).order_by(Lower('systemnavn'))
		utvalg_systemer = aktuelle_systemer.all().order_by(Lower('systemnavn'))
		overskrift = "Systemoversikt"

	utvalg_systemer = utvalg_systemer.order_by(Lower('systemnavn'))

	paginator = Paginator(utvalg_systemer, items)
	paginerte_systemer = paginator.get_page(page)

	return render(request, 'alle_systemer.html', {
		'request': request,
		'overskrift': overskrift,
		'systemer': paginerte_systemer,
		'pages': paginator.page_range,
		'perpage': items,
		'utvalg': utvalg,
		'search_query': search_query,
	})


"""
def alle_applikasjoner(request):
	systemer = System.objects.filter(systemtyper__kategorinavn=SYSTEMTYPE_PROGRAMMER).order_by(Lower('systemnavn'))
	template = 'alle_systemer.html'
	return render(request, template, {
		'overskrift': "Applikasjoner og enkeltstående programvarer",
		'request': request,
		'systemer': systemer,
	})

def alle_systemer_itas(request):
	systemer = System.objects.filter(driftsmodell=10).order_by(Lower('systemnavn'))
	template = 'alle_systemer.html'

	return render(request, template, {
		'overskrift': "Tjenester/funksjoner på ITAS",
		'request': request,
		'systemer': systemer,
	})

def sektor_og_fellessystemer(request):
	systemer = System.objects.filter(systemeierskapsmodell__in=FELLES_OG_SEKTORSYSTEMER).order_by(Lower('systemnavn'))
	return render(request, 'alle_systemer.html', {
		'request': request,
		'systemer': systemer,
		'overskrift': "Sektor- og fellessystemer",
	})
"""


def bruksdetaljer(request, pk):
	bruk = SystemBruk.objects.get(pk=pk)
	return render(request, 'detaljer_systembruk.html', {
		'request': request,
		'bruk': bruk,
	})


def mine_systembruk(request):
	try:
		brukers_virksomhet = virksomhet_til_bruker(request)
		pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
		return redirect('all_bruk_for_virksomhet', pk)
	except:
		messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
		return redirect('alle_virksomheter')


def all_bruk_for_virksomhet(request, pk):
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
	return render(request, 'alle_systembruk.html', {
		'request': request,
		'all_bruk': all_bruk,
		'virksomhet': virksomhet,
	})


def registrer_bruk(request, system):
	required_permissions = 'systemoversikt.change_systembruk'
	if request.user.has_perm(required_permissions):

		system_instans = System.objects.get(pk=system)
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

		virksomheter_med_bruk = SystemBruk.objects.filter(system=system_instans)
		vmb = [bruk.brukergruppe.pk for bruk in virksomheter_med_bruk]
		manglende_virksomheter = Virksomhet.objects.exclude(pk__in=vmb)

		return render(request, 'registrer_bruk.html', {
			'request': request,
			'system': system_instans,
			'virksomheter_uten_bruk': manglende_virksomheter,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def programvaredetaljer(request, pk):
	programvare = Programvare.objects.get(pk=pk)
	programvarebruk = ProgramvareBruk.objects.filter(programvare=pk).order_by("brukergruppe")
	behandlinger = BehandlingerPersonopplysninger.objects.filter(programvarer=pk).order_by("funksjonsomraade")
	return render(request, "detaljer_programvare.html", {
		'request': request,
		'programvare': programvare,
		'programvarebruk': programvarebruk,
		'behandlinger': behandlinger,
	})


def alle_programvarer(request):
	programvarer = Programvare.objects.order_by(Lower('programvarenavn'))
	template = 'alle_programvarer.html'

	return render(request, template, {
		'overskrift': "Programvarer",
		'request': request,
		'programvarer': programvarer,
	})


def all_programvarebruk_for_virksomhet(request, pk):
	virksomhet = Virksomhet.objects.get(pk=pk)
	virksomhet_pk = pk
	all_bruk = ProgramvareBruk.objects.filter(brukergruppe=virksomhet_pk).order_by(Lower('programvare__programvarenavn'))
	for bruk in all_bruk:
		ant = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=virksomhet_pk).filter(programvarer=bruk.programvare.pk).count()
		bruk.antall_behandlinger = ant

	return render(request, "alle_programvarebruk.html", {
		'request': request,
		'virksomhet': virksomhet,
		'all_bruk': all_bruk,
	})


def programvarebruksdetaljer(request, pk):
	bruksdetaljer = ProgramvareBruk.objects.get(pk=pk)
	return render(request, "detaljer_programvarebruk.html", {
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
	required_permissions = 'systemoversikt.view_behandlingerpersonopplysninger'
	if request.user.has_perm(required_permissions):

		behandlinger = BehandlingerPersonopplysninger.objects.all()
		return render(request, 'alle_behandlinger_totalt.html', {
			'request': request,
			'behandlinger': behandlinger,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def behandlingsdetaljer(request, pk):
	required_permissions = 'systemoversikt.view_behandlingerpersonopplysninger'
	if request.user.has_perm(required_permissions):

		behandling = BehandlingerPersonopplysninger.objects.get(pk=pk)
		return render(request, 'detaljer_behandling.html', {
			'request': request,
			'behandling': behandling,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def behandlinger_filtrerte(request, pk):
	required_permissions = 'systemoversikt.change_behandlingerpersonopplysninger'
	if request.user.has_perm(required_permissions):
		vir = Virksomhet.objects.get(pk=pk)
		filtrerte_behandlinger = BehandlingerPersonopplysninger.objects.all().filter(virksomhet_blacklist__in=[vir])

		return render(request, 'detaljer_behandlinger_filtrert.html', {
			'request': request,
			'behandlinger': filtrerte_behandlinger,
			'virksomhet': vir,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def alle_behandlinger_alle_detaljer(request, pk):
	required_permissions = 'systemoversikt.view_behandlingerpersonopplysninger'
	if request.user.has_perm(required_permissions):
		template = "alle_behandlinger_alle_detaljer.html"
		return alle_behandlinger_virksomhet(request, pk, template)
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def mine_behandlinger(request):
	try:
		brukers_virksomhet = virksomhet_til_bruker(request)
		pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
		return redirect('alle_behandlinger_virksomhet', pk)
	except:
		messages.warning(request, 'Din bruker er ikke knyttet til en virksomhet. Velg en virksomhet fra listen, og velg så "Våre behandlinger".')
		return redirect('alle_virksomheter')


# internt_ansvarlig benyttes for å filtrere ut på underavdeling/seksjon/
def alle_behandlinger_virksomhet(request, pk, internt_ansvarlig=False, template='alle_behandlinger.html'):
	vir = Virksomhet.objects.get(pk=pk)

	# finne systemer virksomheten abonnerer på behandlinger for
	systembruk_virksomhet = []
	virksomhetens_relevante_bruk = SystemBruk.objects.filter(brukergruppe=pk).filter(del_behandlinger=True)
	for bruk in virksomhetens_relevante_bruk:
		systembruk_virksomhet.append(bruk.system)

	# finne alle egne behandlinger
	virksomhetens_behandlinger = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=pk)
	# finne alle behandlinger for identifiserte systemer merket fellesbehandling
	delte_behandlinger = BehandlingerPersonopplysninger.objects.filter(systemer__in=systembruk_virksomhet).filter(fellesbehandling=True)#.filter(~Q(virksomhet_blacklist__in=[vir]))

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

	overskrift = ("Behandlingsprotokoll for %s" % vir.virksomhetsforkortelse)
	return render(request, template, {
		'request': request,
		'behandlinger': behandlinger,
		'virksomhet': vir,
		'overskrift': overskrift,
		'interne_avdelinger': virksomhetens_behandlinger_avdelinger,
		'internt_ansvarlig_valgt': internt_ansvarlig,
	})


def behandling_kopier(request, system_pk):
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

				behandling.pk = None
				behandling.save()  # dette er nå en ny instans av objektet, og den gamle er uberørt

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

		return render(request, 'kopier_behandling_system.html', {
			'request': request,
			'system': dette_systemet,
			'dine_eksisterende_behandlinger': dine_eksisterende_behandlinger,
			'kandidatbehandlinger': kandidatbehandlinger,
			'din_virksomhet': din_virksomhet,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def virksomhet(request, pk):
	virksomhet = Virksomhet.objects.get(pk=pk)
	#systemeier_for = System.objects.filter(systemeier=pk)
	#systemforvalter_for = System.objects.filter(systemforvalter=pk)
	systemer_ansvarlig_for = System.objects.filter(Q(systemeier=pk) | Q(systemforvalter=pk)).order_by(Lower('systemnavn'))
	systembruk_forvalter_for = SystemBruk.objects.filter(systemforvalter=pk)
	urleier_for = SystemUrl.objects.filter(eier=pk)
	avtaler = Avtale.objects.filter(Q(virksomhet=pk) | Q(leverandor_intern=pk))
	plattformer_vi_drifter = list(Driftsmodell.objects.filter(ansvarlig_virksomhet=pk))
	systemer_vi_drifter = System.objects.filter(driftsmodell_foreignkey__in=plattformer_vi_drifter)
	antall_brukere = User.objects.filter(profile__virksomhet=pk).filter(profile__ekstern_ressurs=False).filter(is_active=True).count()
	antall_eksterne_brukere = User.objects.filter(profile__virksomhet=pk).filter(profile__ekstern_ressurs=True).filter(is_active=True).count()

	system_ikke_kvalitetssikret = System.objects.filter(Q(systemeier=pk) | Q(systemforvalter=pk)).filter(informasjon_kvalitetssikret=False).count()
	deaktiverte_brukere = Ansvarlig.objects.filter(brukernavn__profile__virksomhet=pk).filter(brukernavn__profile__accountdisable=True).count()
	behandling_uten_ansvarlig = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=virksomhet).filter(oppdateringsansvarlig=None).count()
	behandling_ikke_kvalitetssikret = BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=virksomhet).filter(informasjon_kvalitetssikret=False).count()

	return render(request, 'detaljer_virksomhet.html', {
		'request': request,
		'virksomhet': virksomhet,
		#'systemeier_for': systemeier_for,
		#'systemforvalter_for': systemforvalter_for,
		'systemer_ansvarlig_for': systemer_ansvarlig_for,
		'systembruk_forvalter_for': systembruk_forvalter_for,
		'urleier_for': urleier_for,
		'avtaler': avtaler,
		'systemer_vi_drifter': systemer_vi_drifter,
		'antall_brukere': antall_brukere,
		'antall_eksterne_brukere': antall_eksterne_brukere,
		'system_ikke_kvalitetssikret': system_ikke_kvalitetssikret,
		'deaktiverte_brukere': deaktiverte_brukere,
		'behandling_uten_ansvarlig': behandling_uten_ansvarlig,
		'behandling_ikke_kvalitetssikret': behandling_ikke_kvalitetssikret,
	})


def min_virksomhet(request):
	try:
		brukers_virksomhet = virksomhet_til_bruker(request)
		pk = Virksomhet.objects.get(virksomhetsforkortelse=brukers_virksomhet).pk
		return redirect('virksomhet', pk)
	except:
		messages.warning(request, 'Din bruker er ikke tilknyttet en virksomhet')
		return redirect('alle_virksomheter')


def bytt_virksomhet(request):
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


	return render(request, 'bytt_virksomhet.html', {
		'request': request,
		'brukers_virksomhet': aktiv_representasjon,
		'dine_virksomheter': dine_virksomheter,
	})


def sertifikatmyndighet(request):
	virksomheter = Virksomhet.objects.all()
	return render(request, 'sertifikatmyndigheter.html', {
		'request': request,
		'virksomheter': virksomheter,
	})


def alle_virksomheter(request):
	virksomheter = Virksomhet.objects.order_by('virksomhetsnavn')
	return render(request, 'alle_virksomheter.html', {
		'request': request,
		'virksomheter': virksomheter,
	})


def leverandor(request, pk):
	leverandor = Leverandor.objects.get(pk=pk)
	systemleverandor_for = System.objects.filter(systemleverandor=pk)
	databehandler_for = BehandlingerPersonopplysninger.objects.filter(navn_databehandler=pk)
	programvareleverandor_for = Programvare.objects.filter(programvareleverandor=pk)
	basisdriftleverandor_for = System.objects.filter(basisdriftleverandor=pk)
	applikasjonsdriftleverandor_for = System.objects.filter(applikasjonsdriftleverandor=pk)
	registrar_for = SystemUrl.objects.filter(registrar=pk)
	return render(request, 'detaljer_leverandor.html', {
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
	from django.db.models.functions import Lower
	leverandorer = Leverandor.objects.order_by(Lower('leverandor_navn'))
	return render(request, 'alle_leverandorer.html', {
		'request': request,
		'leverandorer': leverandorer,
	})


def alle_driftsmodeller(request):
	driftsmodeller = Driftsmodell.objects.all()
	return render(request, 'alle_driftsmodeller.html', {
		'request': request,
		'driftsmodeller': driftsmodeller,
	})


def detaljer_driftsmodell(request, pk):
	driftsmodell = Driftsmodell.objects.get(pk=pk)
	systemer = System.objects.filter(driftsmodell_foreignkey=pk)
	isolert_drift = systemer.filter(isolert_drift=True)

	# gjør et oppslag for å finne kategorier som ikke er anbefalt
	anbefalte_personoppl_kategorier = driftsmodell.anbefalte_kategorier_personopplysninger.all()
	ikke_anbefalte_personoppl_kategorier = Personsonopplysningskategori.objects.filter(~Q(pk__in=anbefalte_personoppl_kategorier)).all()

	return render(request, 'detaljer_driftsmodell.html', {
		'request': request,
		'driftsmodell': driftsmodell,
		'systemer': systemer,
		'isolert_drift': isolert_drift,
		'ikke_anbefalte_personoppl_kategorier': ikke_anbefalte_personoppl_kategorier,
	})


def systemkategori(request, pk):
	kategori = SystemKategori.objects.get(pk=pk)
	systemer = System.objects.filter(systemkategorier=pk).order_by(Lower('systemnavn'))
	programvarer = Programvare.objects.filter(kategorier=pk).order_by(Lower('programvarenavn'))
	return render(request, 'detaljer_systemkategori.html', {
		'request': request,
		'systemer': systemer,
		'kategori': kategori,
		'programvarer': programvarer,
	})


def alle_hovedkategorier(request):
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


	return render(request, 'alle_systemhovedkategorier.html', {
		'request': request,
		'hovedkategorier': hovedkategorier,
		'subkategorier_uten_hovedkategori': subkategorier_uten_hovedkategori,
	})


def alle_systemkategorier(request):
	kategorier = SystemKategori.objects.order_by('kategorinavn')
	return render(request, 'alle_systemkategorier.html', {
		'request': request,
		'kategorier': kategorier,
	})


def uten_systemkategori(request):
	antall_systemer = System.objects.all().count()
	antall_programvarer = Programvare.objects.all().count()
	systemer = System.objects.annotate(num_categories=Count('systemkategorier')).filter(num_categories=0)
	programvarer = Programvare.objects.annotate(num_categories=Count('kategorier')).filter(num_categories=0)
	return render(request, 'alle_systemkategorier_uten_systemkategorier.html', {
		'request': request,
		'systemer': systemer,
		'programvarer': programvarer,
		'antall_systemer': antall_systemer,
		'antall_programvarer': antall_programvarer,
	})


def systemurl(request, pk):
	url = SystemUrl.objects.get(pk=pk)
	systemer = System.objects.filter(systemurl=pk)
	return render(request, 'detaljer_url.html', {
		'request': request,
		'web_url': url,
		'systemer': systemer,
	})


def alle_systemurler(request):
	urler = SystemUrl.objects.order_by('domene')
	return render(request, 'alle_urler.html', {
		'request': request,
		'web_urler': urler,
	})


def bytt_kategori(request, fra, til):
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
	required_permissions = 'systemoversikt.change_systembruk'
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


def system_til_programvare(request, system_id):
	required_permissions = 'systemoversikt.change_system'
	if request.user.has_perm(required_permissions):
		try:
			#finne systemet som skal konverteres
			kildesystem = System.objects.get(pk=system_id)

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
						programvareeierskap=systembruk.systemeierskap,
						antall_brukere=systembruk.antall_brukere,
						avtaletype=systembruk.avtaletype,
						avtalestatus=systembruk.avtalestatus,
						avtale_kan_avropes=systembruk.avtale_kan_avropes,
						borger=systembruk.borger,
						kostnader=systembruk.kostnadersystem,
						strategisk_egnethet=systembruk.strategisk_egnethet,
						funksjonell_egnethet=systembruk.funksjonell_egnethet,
						teknisk_egnethet=systembruk.teknisk_egnethet,
					)
				for leverandor in systembruk.systemleverandor.all():
					ny_programvarebruk.programvareleverandor.add(leverandor)
					ny_programvarebruk.save()

			#registrere behandlinger på programvaren fra systemet
			for behandling in kildesystem.behandling_systemer.all():
				behandling.programvarer.add(ny_programvare)
				behandling.save()

			messages.success(request, 'Konvertere system til programvare. Ny programvare med id: %s er opprettet' % ny_programvare.pk)
		except Exception as e:
			messages.warning(request, 'Konvertere system til programvare feilet med feilmelding %s' % e)

		return render(request, 'home.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def cmdb_stats(maskiner):
	maskiner_stats = []
	os_major = maskiner.values('comp_os').distinct()
	for os in os_major:
		minor_versions = maskiner.filter(comp_os=os['comp_os']).values('comp_os_version').annotate(Count('comp_os_version'))
		for minor in minor_versions:
			maskiner_stats.append({'major': os['comp_os'], 'minor': minor['comp_os_version'], 'count': minor['comp_os_version__count']})
	return maskiner_stats


def alle_servere(request):
	required_permissions = 'systemoversikt.change_system'
	if request.user.has_perm(required_permissions):
		maskiner = CMDBdevice.objects.filter(~Q(bs_u_service_portfolio="Digital workplace") & Q(active=True)).order_by('comp_os')
		maskiner_stats = cmdb_stats(maskiner)

		return render(request, 'alle_maskiner.html', {
			'request': request,
			'maskiner': maskiner,
			'maskiner_stats': maskiner_stats,
			"type": "servere",
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

def alle_klienter(request):
	required_permissions = 'systemoversikt.change_system'
	if request.user.has_perm(required_permissions):
		maskiner = CMDBdevice.objects.filter(Q(bs_u_service_portfolio="Digital workplace") & Q(active=True)).order_by('comp_os')
		maskiner_stats = cmdb_stats(maskiner)

		return render(request, 'alle_maskiner.html', {
			'request': request,
			'maskiner': maskiner,
			'maskiner_stats': maskiner_stats,
			"type": "klienter",
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def alle_databaser(request):
	required_permissions = 'systemoversikt.change_system'
	if request.user.has_perm(required_permissions):
		databaser = CMDBdatabase.objects.all()
		return render(request, 'alle_databaser.html', {
			'request': request,
			'databaser': databaser,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })

def alle_cmdbref(request):
	required_permissions = 'systemoversikt.change_system'
	if request.user.has_perm(required_permissions):
		cmdbref = CMDBRef.objects.all().order_by("-operational_status", Lower("navn")) #1 er operational (filter(operational_status=1))
		for c in cmdbref:
			ant_devices = CMDBdevice.objects.filter(sub_name=c.pk, active=True)
			c.ant_devices = ant_devices.count()

		return render(request, 'alle_cmdb.html', {
			'request': request,
			'cmdbref': cmdbref,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def cmdbdevice(request, pk):
	required_permissions = 'systemoversikt.change_system'
	if request.user.has_perm(required_permissions):
		cmdbref = CMDBRef.objects.get(pk=pk)
		cmdbdevices = CMDBdevice.objects.filter(sub_name=cmdbref)
		databaser = CMDBdatabase.objects.filter(sub_name=cmdbref)

		return render(request, 'detaljer_cmdbdevice.html', {
			'request': request,
			'cmdbref': cmdbref,
			'cmdbdevices': cmdbdevices,
			'databaser': databaser,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def alle_avtaler(request, virksomhet=None):
	alle_virksomheter = Virksomhet.objects.all()
	avtaler = Avtale.objects.all()
	utdypende_beskrivelse = "Viser alle avtaler registrert i Kartoteket."
	if virksomhet:
		virksomhet = int(virksomhet)
		#print(type(virksomhet))
		virksomhetsnavn = Virksomhet.objects.get(pk=virksomhet)
		avtaler = avtaler.filter(Q(virksomhet=virksomhet) | Q(leverandor_intern=virksomhet))
		utdypende_beskrivelse = "Viser alle avtaler der %s er avtalepart." % virksomhetsnavn
	return render(request, 'alle_avtaler.html', {
		'request': request,
		'alle_virksomheter': alle_virksomheter,
		'avtaler': avtaler,
		'utdypende_beskrivelse': utdypende_beskrivelse,
		'virksomhet_pk': virksomhet,
	})


def avtaledetaljer(request, pk):
	avtale = Avtale.objects.get(pk=pk)
	return render(request, 'detaljer_avtale.html', {
		'request': request,
		'avtale': avtale,
	})


def databehandleravtaler_virksomhet(request, pk):
	virksomet = Virksomhet.objects.get(pk=pk)
	utdypende_beskrivelse = ("Viser databehandleravtaler for %s" % virksomet)
	avtaler = Avtale.objects.filter(virksomhet=pk).filter(avtaletype=1) # 1 er databehandleravtaler
	return render(request, 'alle_avtaler.html', {
		'request': request,
		'avtaler': avtaler,
		'utdypende_beskrivelse': utdypende_beskrivelse,
	})


def alle_dpia(request):
	alle_dpia = DPIA.objects.all()
	return render(request, 'alle_dpia.html', {
		'request': request,
		'alle_dpia': alle_dpia,
	})


def detaljer_dpia(request, pk):
	dpia = DPIA.objects.get(pk=pk)
	return render(request, 'detaljer_dpia.html', {
		'request': request,
		'dpia': dpia,
	})


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


def ldap_query(ldap_path, ldap_filter, ldap_properties, timeout):
	import ldap, os
	server = 'ldaps://ldaps.oslofelles.oslo.kommune.no:636'
	user = os.environ["KARTOTEKET_LDAPUSER"]
	password = os.environ["KARTOTEKET_LDAPPASSWORD"]
	ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # have to deactivate sertificate check
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

def ldap_get_details(name):
	import re

	ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
	ldap_filter = ('(cn=%s)' % name)
	ldap_properties = []

	result = ldap_query(ldap_path=ldap_path, ldap_filter=ldap_filter, ldap_properties=ldap_properties, timeout=10)
	groups = []
	users = []
	for cn,attrs in result:
		if cn:
			if b'user' in attrs["objectClass"]:
				attrs_decoded = {}
				for key in attrs:
					if key in ['cn', 'mail', 'givenName', 'displayName', 'sn', 'userAccountControl', 'logonCount', 'memberOf', 'lastLogonTimestamp', 'title', 'description', 'otherMobile', 'mobile', 'objectClass']:
						# if not, then we don't bother decoding the value for now
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
					else:
						continue

				users.append({
						"cn": cn,
						"attrs": attrs_decoded,
				})

			if b'group' in attrs["objectClass"]:
				attrs_decoded = {}
				for key in attrs:
					if key in ['description', 'cn', 'member', 'objectClass']:
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

	return ({"users": users, "groups": groups})


"""
def ad_user_details(request, username):
	import time
	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):
		runetime_t0 = time.time()
		users = ldap_get_user_details(username)
		runetime_t1 = time.time()
		logg_total_runtime = runetime_t1 - runetime_t0
		messages.success(request, 'Dette søket tok %s sekunder' % round(logg_total_runtime, 1))

		return render(request, 'ad_bruker.html', {
			'request': request,
			'users': users,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })
"""

"""
def ad_group_details(request, group):
	import time
	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):
		runetime_t0 = time.time()
		result = ldap_get_group_details(group)
		runetime_t1 = time.time()
		logg_total_runtime = runetime_t1 - runetime_t0
		messages.success(request, 'Dette søket tok %s sekunder' % round(logg_total_runtime, 1))

		return render(request, 'ad_gruppe.html', {
			'request': request,
			'groups': result,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })
"""

def ad_details(request, name):
	import time
	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):
		runetime_t0 = time.time()
		result = ldap_get_details(name)
		runetime_t1 = time.time()
		logg_total_runtime = runetime_t1 - runetime_t0
		messages.success(request, 'Dette søket tok %s sekunder' % round(logg_total_runtime, 1))

		return render(request, 'ad_details.html', {
			'request': request,
			'result': result,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def ldap_get_recursive_group_members(group):
	#print(group)

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


def recursive_group_members(request, group):
	import time
	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):
		runetime_t0 = time.time()
		result = ldap_get_recursive_group_members(group)
		runetime_t1 = time.time()
		logg_total_runtime = runetime_t1 - runetime_t0
		messages.success(request, 'Dette søket tok %s sekunder' % round(logg_total_runtime, 1))

		return render(request, 'ad_recursive.html', {
			'request': request,
			'result': result,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def ad(request):
	required_permissions = 'auth.view_user'
	if request.user.has_perm(required_permissions):

		return render(request, 'ad_index.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })