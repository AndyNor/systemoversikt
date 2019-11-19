"""systemoversikt URL Configuration
The `urlpatterns` list routes URLs to views. For more information please see:
	https://docs.djangoproject.com/en/1.11/topics/http/urls/
"""
from django.conf.urls import url
from django.contrib import admin

from rest_framework import routers
from django.urls import include, path, re_path
from systemoversikt.restapi import views as apiviews
from django.views.generic.base import RedirectView

router = routers.DefaultRouter()
router.register(r'systemer', apiviews.SystemViewSet, 'systemer')
router.register(r'systemer_HEL', apiviews.HELSystemViewSet, 'systemer_HEL')
router.register(r'virksomhet', apiviews.VirksomhetViewSet)
router.register(r'driftsmodell', apiviews.DriftsmodellViewSet)
router.register(r'ansvarlig', apiviews.AnsvarligViewSet)
#router.register(r'user', apiviews.UserViewSet)
router.register(r'avtale', apiviews.AvtaleViewSet)
router.register(r'leverandor', apiviews.LeverandorViewSet)
#router.register(r'systembruk', apiviews.SystemBrukViewSet)
#router.register(r'systemkateogri', apiviews.SystemktegoriViewSet)
router.register(r'behandling', apiviews.VirksomhetViewSet)


import systemoversikt.views as views
import systemoversikt.views_import as views_import
from django.conf.urls import include
from django.conf import settings
from django.contrib.auth import logout, login

favicon_view = RedirectView.as_view(url='/static/favicon/favicon.ico', permanent=True)

urlpatterns = [
	path('api/', include(router.urls)),
	path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),

	re_path(r'^favicon\.ico$', favicon_view),

	url(r'^$', views.home, name='home'),
	url(r'^admin/', admin.site.urls, name="admin"),
	url(r'^oidc/', include('mozilla_django_oidc.urls')),
	url(r'^login/$', admin.site.login, name='login'),
	url(r'^logout/$', logout, {'next_page': settings.LOGOUT_REDIRECT_URL}, name='logout'),

	url(r'^sys/profil/', views.minside, name="minside"),
	url(r'^sys/logger/database/$', views.logger, name='logger'),
	url(r'^sys/logger/audit/$', views.logger_audit, name='logger_audit'),
	url(r'^sys/roller/$', views.roller, name='roller'),
	url(r'^sys/rettigheter/$', views.permissions, name='permissions'),


	url(r'^systemer/$', views.alle_systemer, name='alle_systemer'),
	url(r'^systemer/pakket/$', views.systemer_pakket, name='systemer_pakket'),
	url(r'^systemer/test/$', views.systemer_test, name='systemer_test'),
	url(r'^systemer/(?P<utvalg>\w{1,30})/(?P<items>\d{1,5})/(?P<page>\d{1,5})/$', views.alle_systemer, name='alle_systemer_sideref'),
	url(r'^systemer/detaljer/(?P<pk>\d{1,8})/$', views.systemdetaljer, name='systemdetaljer'),
	url(r'^systemer/bruk/$', views.mine_systembruk, name='mine_systembruk'),
	url(r'^systemer/bruk/(?P<pk>\d{1,8})/$', views.bruksdetaljer, name='bruksdetaljer'),
	url(r'^systemer/bruk/registrer_bruk/(?P<system>\d{1,8})/$', views.registrer_bruk, name='registrer_bruk'),
	url(r'^systemer/virksomhet/(?P<pk>\d{1,8})/$', views.all_bruk_for_virksomhet, name='all_bruk_for_virksomhet'),
	url(r'^systemer/systemklassifisering/(?P<id>[A-Z-]{1,30})/$', views.systemklassifisering_detaljer, name='systemklassifisering_detaljer'),
	url(r'^systemer/systemtype/(?P<pk>\d{1,8})/$', views.systemtype_detaljer, name='systemtype_detaljer'),
	#url(r'^systemer/ITAS/$', views.alle_systemer_itas, name='alle_systemer_itas'),
	#url(r'^systemer/sektor_og_fellessystemer/$', views.sektor_og_fellessystemer, name='sektor_og_fellessystemer'),
	#url(r'^systemer/systemapplikasjoner/$', views.alle_applikasjoner, name='alle_applikasjoner'),

	url(r'^behandlinger/$', views.mine_behandlinger, name='mine_behandlinger'),
	url(r'^behandlinger/alle/$', views.alle_behandlinger, name='alle_behandlinger'),
	url(r'^behandlinger/kopier/(?P<system_pk>\d{1,8})/$', views.behandling_kopier, name='behandling_kopier'),
	url(r'^behandlinger/alle_detaljer/(?P<pk>\d{1,8})/$', views.alle_behandlinger_alle_detaljer, name='alle_behandlinger_alle_detaljer'),
	url(r'^behandlinger/vir/(?P<pk>\d{1,8})/$', views.alle_behandlinger_virksomhet, name='alle_behandlinger_virksomhet'),
	url(r'^behandlinger/vir/(?P<pk>\d{1,8})/(?P<internt_ansvarlig>.*)/$', views.alle_behandlinger_virksomhet, name='behandlinger_virksomhet_ansvarlig'),
	url(r'^behandlinger/detaljer/(?P<pk>\d{1,8})/$', views.behandlingsdetaljer, name='behandlingsdetaljer'),
	url(r'^behandlinger/filtrerte/virksomhet/(?P<pk>\d{1,8})/$', views.behandlinger_filtrerte, name='behandlinger_filtrerte'),

	url(r'^avtaler/$', views.alle_avtaler, name='alle_avtaler'),
	url(r'^avtaler/detaljer/(?P<pk>\d{1,8})/$', views.avtaledetaljer, name='avtaledetaljer'),
	url(r'^avtaler/(?P<virksomhet>\d{1,8})/$', views.alle_avtaler, name='avtalervirksomhet'),
	url(r'^avtaler/databehandleravtale/virksomhet/(?P<pk>\d{1,8})/$', views.databehandleravtaler_virksomhet, name='databehandleravtaler_virksomhet'),

	url(r'^virksomhet/$', views.alle_virksomheter, name='alle_virksomheter'),
	url(r'^virksomhet/bytt_virksomhet/$', views.bytt_virksomhet, name='bytt_virksomhet'),
	url(r'^virksomhet/min/$', views.min_virksomhet, name='min_virksomhet'),
	url(r'^virksomhet/sertifikatmyndighet/$', views.sertifikatmyndighet, name='sertifikatmyndighet'),
	url(r'^virksomhet/(?P<pk>\d{1,8})/$', views.virksomhet, name='virksomhet'),

	url(r'^leverandor/$', views.alle_leverandorer, name='alle_leverandorer'),
	url(r'^leverandor/(?P<pk>\d{1,8})/$', views.leverandor, name='leverandor'),

	url(r'^hovedkategorier/$', views.alle_hovedkategorier, name='alle_hovedkategorier'),
	url(r'^hovedkategorier/subkategorier/$', views.alle_systemkategorier, name='alle_systemkategorier'),
	url(r'^hovedkategorier/subkategorier/uten_kategori/$', views.uten_systemkategori, name='uten_systemkategorier'),
	url(r'^hovedkategorier/subkategorier/(?P<pk>\d{1,8})/$', views.systemkategori, name='systemkategori'),

	url(r'^domener/$', views.alle_systemurler, name='alle_systemurler'),
	#url(r'^systemurl/(?P<pk>\d{1,8})/$', views.systemurl, name='systemurl'),


	url(r'^/script/bytt_kategori/(?P<fra>\d{1,8})/(?P<til>\d{1,8})/$', views.bytt_kategori, name='bytt_kategori'),
	url(r'^/script/bytt_leverandor/(?P<fra>\d{1,8})/(?P<til>\d{1,8})/$', views.bytt_leverandor, name='bytt_leverandor'),

	#url(r'^tjenester/$', views.alle_tjenester, name='alle_tjenester'),
	#url(r'^tjenester/(?P<pk>\d{1,8})/$', views.tjenestedetaljer, name='tjenestedetaljer'),

	url(r'^programvare/$', views.alle_programvarer, name='alle_programvarer'),
	url(r'^programvare/(?P<pk>\d{1,8})/$', views.programvaredetaljer, name='programvaredetaljer'),
	url(r'^programvare/virksomhet/(?P<pk>\d{1,8})/$', views.all_programvarebruk_for_virksomhet, name='all_programvarebruk_for_virksomhet'),
	url(r'^programvare/bruk/(?P<pk>\d{1,8})/$', views.programvarebruksdetaljer, name='programvarebruksdetaljer'),

	url(r'^ansvarlig/$', views.alle_ansvarlige, name='alle_ansvarlige'),
	url(r'^ansvarlig/eksport/$', views.alle_ansvarlige_eksport, name='alle_ansvarlige_eksport'),
	url(r'^ansvarlig/(?P<pk>\d{1,8})/$', views.ansvarlig, name='ansvarlig'),

	url(r'^cmdb/$', views.alle_cmdbref, name='alle_cmdbref'),
	url(r'^cmdb/(?P<pk>\d{1,8})/$', views.cmdbdevice, name='cmdbdevice'),
	url(r'^cmdb/servere/$', views.alle_servere, name='alle_servere'),
	url(r'^cmdb/klienter/$', views.alle_klienter, name='alle_klienter'),
	url(r'^cmdb/databaser/$', views.alle_databaser, name='alle_databaser'),

	url(r'^dpia/$', views.alle_dpia, name='alle_dpia'),
	url(r'^dpia/(?P<pk>\d{1,8})/$', views.detaljer_dpia, name='detaljer_dpia'),

	url(r'^driftsmodell/$', views.alle_driftsmodeller, name='alle_driftsmodeller'),
	url(r'^driftsmodell/(?P<pk>\d{1,8})/$', views.detaljer_driftsmodell, name='detaljer_driftsmodell'),

	url(r'^definisjon/$', views.alle_definisjoner, name='alle_definisjoner'),
	url(r'^definisjon/(?P<begrep>[-_a-zA-Z0-9\s]{1,150})/$', views.definisjon, name='definisjon'),

	#url(r'^import/iktkontakt/$', views.import_iktkontakt, name='import_iktkontakt'),
	#url(r'^import/users/$', views.import_ansvarlige_brukere, name='import_ansvarlige_brukere'),
	#url(r'^automate/fixcmdb/$', views.fixcmdb, name='fixcmdb'),
	#url(r'^automate/slettikkeibruk/$', views.slettBrukIkkeIBruk, name='slettBrukIkkeIBruk'),
	#url(r'^automate/tommecreated/$', views.sett_created_til_sist_oppdatert, name='sett_created_til_sist_oppdatert'),
	#url(r'^automate/ansvarlig_bruker/$', views.match_ansvarlig_brukerobjekt, name='match_ansvarlig_brukerobjekt'),

	url(r'^dashboard/$', views.dashboard_all, name='dashboard_all'),
	url(r'^dashboard/(?P<virksomhet>\d{1,8})/$', views.dashboard_all, name='dashboard_all'),

	# import og konvertering
	#url(r'^import_vir/$', views.import_vir, name='import_vir'),
	#url(r'^import_lev/$', views.import_lev, name='import_lev'),
	#url(r'^import_sys/$', views.import_sys, name='import_sys'),
	url(r'^import/groups/permissions/$', views_import.import_group_permissions, name='import_group_permissions'),
	url(r'^import/cmdb/business_services/$', views_import.import_business_services, name='import_cmdb'),
	url(r'^import/cmdb/servers/$', views_import.import_cmdb_servers, name='import_cmdb'),
	url(r'^import/cmdb/databases/$', views_import.import_cmdb_databases, name='import_databases'),
	url(r'^import/definisjon/organisasjon/$', views_import.import_organisatorisk_forkortelser, name='import_organisatorisk_forkortelser'),


	#url(r'^import_sys_new/$', views.import_sys_new, name='import_sys_new'),
	#url(r'^import_bruk/$', views.import_bruk, name='import_bruk'),
	#url(r'^system_til_programvare/(?P<system_id>\d{1,8})/$', views.system_til_programvare, name='system_til_programvare'),

	#url(r'^ad/user/(?P<username>[a-zA-Z0-9]{2,15})/$', views.ad_user_details, name='ad_user_details'),
	#url(r'^ad/group/$', views.ad_group_details, name='ad_group_details'),
	#url(r'^ad/group/(?P<group>[-_a-zA-Z0-9\s]{2,100})/$', views.ad_group_details, name='ad_group_details'),
	url(r'^ad/$', views.ad, name='ad'),
	url(r'^ad/(?P<name>[-._a-zA-Z0-9\s]{2,100})/$', views.ad_details, name='ad_details'),
	url(r'^ad/recursive/(?P<group>[-_=,a-zA-Z0-9\s]{2,200})/$', views.recursive_group_members, name='recursive_group_members'),
]
