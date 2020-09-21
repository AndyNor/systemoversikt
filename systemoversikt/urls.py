"""systemoversikt URL Configuration
The `urlpatterns` list routes URLs to views. For more information please see:
	https://docs.djangoproject.com/en/1.11/topics/http/urls/
"""
from django.conf.urls import url
from django.contrib import admin
from django.conf.urls import include
from django.conf import settings
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView

import systemoversikt.views as views
import systemoversikt.views_import as views_import

from rest_framework import routers
from systemoversikt.restapi import views as apiviews

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

favicon_view = RedirectView.as_view(url='/static/favicon/favicon.ico', permanent=True)

urlpatterns = [
	path('api/', include(router.urls)),
	path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),

	re_path(r'^favicon\.ico$', favicon_view),

	url(r'^$', views.home, name='home'),
	url(r'^admin/', admin.site.urls, name="admin"),
	url(r'^oidc/', include('mozilla_django_oidc.urls')),
	url(r'^login/$', admin.site.login, name='login'),
	url(r'^logout/$', admin.site.logout, name='logout'),

	url(r'^admin/profil/', views.minside, name="minside"),
	url(r'^admin/logger/database/$', views.logger, name='logger'),
	url(r'^admin/logger/audit/$', views.logger_audit, name='logger_audit'),
	url(r'^admin/logger/users/$', views.logger_users, name='logger_users'),
	url(r'^admin/roller/$', views.roller, name='roller'),
	url(r'^admin/rettigheter/$', views.permissions, name='permissions'),

	url(r'^systemer/alle/$', views.alle_systemer, name='alle_systemer'),
	url(r'^systemer/pakket/$', views.systemer_pakket, name='systemer_pakket'),
	url(r'^systemer/detaljer/(?P<pk>\d{1,8})/$', views.systemdetaljer, name='systemdetaljer'),
	url(r'^systemer/bruk/$', views.mine_systembruk, name='mine_systembruk'),
	url(r'^systemer/utfaset/$', views.systemer_utfaset, name='systemer_utfaset'),
	url(r'^systemer/bruk/(?P<pk>\d{1,8})/$', views.bruksdetaljer, name='bruksdetaljer'),
	url(r'^systemer/bruk/registrer_bruk/(?P<system>\d{1,8})/$', views.registrer_bruk, name='registrer_bruk'),
	url(r'^virksomhet/systemer/(?P<pk>\d{1,8})/$', views.all_bruk_for_virksomhet, name='all_bruk_for_virksomhet'),
	url(r'^systemer/systemklassifisering/(?P<id>[A-Z-_]{1,30})/$', views.systemklassifisering_detaljer, name='systemklassifisering_detaljer'),
	url(r'^systemer/systemtype/(?P<pk>\d{1,8})/$', views.systemtype_detaljer, name='systemtype_detaljer'),
	url(r'^systemer/systemtype/tom/$', views.systemtype_detaljer, name='systemtype_detaljer_mangler'),
	url(r'^system_til_programvare/$', views.system_til_programvare, name='system_til_programvare_indeks'),
	url(r'^system_til_programvare/(?P<system_id>\d{1,8})/$', views.system_til_programvare, name='system_til_programvare'),

	url(r'^behandlinger/user/$', views.mine_behandlinger, name='mine_behandlinger'),
	url(r'^behandlinger/alle/$', views.alle_behandlinger, name='alle_behandlinger'),
	url(r'^behandlinger/kopier/(?P<system_pk>\d{1,8})/$', views.behandling_kopier, name='behandling_kopier'),
	url(r'^virksomhet/behandlinger/(?P<pk>\d{1,8})/$', views.alle_behandlinger_virksomhet, name='alle_behandlinger_virksomhet'),
	#url(r'^virksomhet/behandlinger/(?P<pk>\d{1,8})/(?P<internt_ansvarlig>.*)/$', views.alle_behandlinger_virksomhet, name='behandlinger_virksomhet_ansvarlig'),
	url(r'^behandlinger/detaljer/(?P<pk>\d{1,8})/$', views.behandlingsdetaljer, name='behandlingsdetaljer'),

	url(r'^avtaler/$', views.alle_avtaler, name='alle_avtaler'),
	url(r'^avtaler/detaljer/(?P<pk>\d{1,8})/$', views.avtaledetaljer, name='avtaledetaljer'),
	url(r'^virksomhet/avtaler/(?P<virksomhet>\d{1,8})/$', views.alle_avtaler, name='avtalervirksomhet'),
	url(r'^avtaler/databehandleravtale/virksomhet/(?P<pk>\d{1,8})/$', views.databehandleravtaler_virksomhet, name='databehandleravtaler_virksomhet'),

	url(r'^cmdb/klient/$', views.alle_klienter, name='alle_klienter'),
	url(r'^cmdb/bruker/(?P<pk>\d{1,8})/$', views.bruker_detaljer, name='bruker_detaljer'),
	url(r'^cmdb/bruker/$', views.bruker_sok, name='bruker_sok'),

	url(r'^virksomhet/$', views.alle_virksomheter, name='alle_virksomheter'),
	url(r'^virksomhet/alle/$', views.alle_virksomheter, name='alle_virksomheter_sidemeny'),
	url(r'^virksomhet/(?P<pk>\d{1,8})/$', views.virksomhet, name='virksomhet'),
	url(r'^virksomhet/passwdexpire/(?P<pk>\d{1,8})/$', views.passwordexpire, name='passwordexpire'),
	url(r'^virksomhet/passwdneverexpire/(?P<pk>\d{1,8})/$', views.passwdneverexpire, name='passwdneverexpire'),
	url(r'^virksomhet/ansvarlige/(?P<pk>\d{1,8})/$', views.virksomhet_ansvarlige, name='virksomhet_ansvarlige'),
	url(r'^virksomhet/bytt_virksomhet/$', views.bytt_virksomhet, name='bytt_virksomhet'),
	url(r'^virksomhet/min/$', views.min_virksomhet, name='min_virksomhet'),
	url(r'^virksomhet/arkivplan/(?P<pk>\d{1,8})/$', views.virksomhet_arkivplan, name='virksomhet_arkivplan'),
	url(r'^virksomhet/sertifikatmyndighet/$', views.sertifikatmyndighet, name='sertifikatmyndighet'),
	url(r'^virksomhet/innsyn/(?P<pk>\d{1,8})/$', views.innsyn_virksomhet, name='innsyn_virksomhet'),
	url(r'^virksomhet/systemkvalitet/(?P<pk>\d{1,8})/$', views.systemkvalitet_virksomhet, name='systemkvalitet_virksomhet'),
	url(r'^virksomhet/enhet/$', views.virksomhet_enhetsok, name='virksomhet_enhetsok'),
	url(r'^virksomhet/enhet/(?P<pk>\d{1,8})/$', views.enhet_detaljer, name='enhet_detaljer'),
	url(r'^virksomhet/enhet/graf/(?P<pk>\d{1,8})/$', views.virksomhet_enheter, name='virksomhet_enheter'),
	url(r'^virksomhet/prkadmin/(?P<pk>\d{1,8})/$', views.virksomhet_prkadmin, name='virksomhet_prkadmin'),
	url(r'^virksomhet/systemer/ansvarligfor/(?P<pk>\d{1,8})/$', views.systemer_virksomhet_ansvarlig_for, name='systemer_virksomhet_ansvarlig_for'),

	url(r'^leverandor/$', views.alle_leverandorer, name='alle_leverandorer'),
	url(r'^leverandor/bytt_leverandor/(?P<fra>\d{1,8})/(?P<til>\d{1,8})/$', views.bytt_leverandor, name='bytt_leverandor'),
	url(r'^leverandor/(?P<pk>\d{1,8})/$', views.leverandor, name='leverandor'),

	url(r'^hovedkategorier/alle/$', views.alle_hovedkategorier, name='alle_hovedkategorier'),
	url(r'^hovedkategorier/subkategorier/$', views.alle_systemkategorier, name='alle_systemkategorier'),
	url(r'^hovedkategorier/subkategorier/bytt_kategori/(?P<fra>\d{1,8})/(?P<til>\d{1,8})/$', views.bytt_kategori, name='bytt_kategori'),
	url(r'^hovedkategorier/subkategorier/uten_kategori/$', views.uten_systemkategori, name='uten_systemkategorier'),
	url(r'^hovedkategorier/subkategorier/(?P<pk>\d{1,8})/$', views.systemkategori, name='systemkategori'),

	url(r'^domener/alle/$', views.alle_systemurler, name='alle_systemurler'),
	url(r'^virksomhet/domener/(?P<pk>\d{1,8})/$', views.virksomhet_urler, name='virksomhet_urler'),

	url(r'^programvare/alle/$', views.alle_programvarer, name='alle_programvarer'),
	url(r'^programvare/(?P<pk>\d{1,8})/$', views.programvaredetaljer, name='programvaredetaljer'),
	url(r'^virksomhet/programvare/(?P<pk>\d{1,8})/$', views.all_programvarebruk_for_virksomhet, name='all_programvarebruk_for_virksomhet'),
	url(r'^programvare/bruk/(?P<pk>\d{1,8})/$', views.programvarebruksdetaljer, name='programvarebruksdetaljer'),

	url(r'^ansvarlige/alle/$', views.alle_ansvarlige, name='alle_ansvarlige'),
	url(r'^ansvarlige/eksport/$', views.alle_ansvarlige_eksport, name='alle_ansvarlige_eksport'),
	url(r'^ansvarlige/(?P<pk>\d{1,8})/$', views.ansvarlig, name='ansvarlig'),

	url(r'^cmdb/$', views.alle_cmdbref, name='alle_cmdbref_main'),
	url(r'^cmdb/alle/$', views.alle_cmdbref, name='alle_cmdbref'),
	url(r'^cmdb/(?P<pk>\d{1,8})/$', views.cmdbdevice, name='cmdbdevice'),
	url(r'^cmdb/servere/sok/$', views.alle_maskiner, name='alle_maskiner'),
	url(r'^cmdb/servere/utfaset/$', views.servere_utfaset, name='servere_utfaset'),
	url(r'^cmdb/databaser/$', views.alle_databaser, name='alle_databaser'),
	url(r'^cmdb/os/$', views.alle_os, name='alle_os'),
	url(r'^cmdb/ip/$', views.alle_ip, name='alle_ip'),

	url(r'^cmdb/prk/alle/$', views.alle_prk, name='alle_prk'),
	url(r'^cmdb/prk/browse/$', views.prk_browse, name='prk_browse'),
	url(r'^cmdb/prk/browse/(?P<skjema_id>\d{1,8})/$', views.prk_skjema, name='prk_skjema'),

	url(r'^cmdb/ad/lookup/$', views.ad, name='ad'),
	url(r'^cmdb/ad/adgruppe/$', views.alle_adgrupper, name='alle_adgrupper'),
	url(r'^cmdb/ad/adgruppe/(?P<pk>\d{1,8})/$', views.adgruppe_detaljer, name='adgruppe_detaljer'),
	url(r'^cmdb/ad/adgruppe/graf/(?P<pk>\d{1,8})/$', views.adgruppe_graf, name='adgruppe_graf'),
	url(r'^cmdb/ad/adorgunit/$', views.adorgunit_detaljer, name='adorgunit_detaljer'),
	url(r'^cmdb/ad/adorgunit/(?P<pk>\d{1,8})/$', views.adorgunit_detaljer, name='adorgunit_detaljer'),
	url(r'^cmdb/ad/lookup/(?P<name>[-._a-zA-Z0-9\s]{2,100})/$', views.ad_details, name='ad_details'),  #denne må komme etter ad/adgrupper/
	# i AD er følgende tegn ulovlige: # + " \ < > ; (RFC 2253)
	# komma tillates da det brukes for å skille elementer fra hverandre
	# leading space eller #, samt trailing space er heller ikke tillatt, men vi gjør ikke noe med dem.
	url(r'^cmdb/ad/lookup/recursive/(?P<group>[^#\+\"\\\<\>\;]{2,200})/$', views.recursive_group_members, name='recursive_group_members'),
	url(r'^cmdb/ad/lookup/exact/(?P<name>[^#\+\"\\\<\>\;]{2,200})/$', views.ad_exact, name='ad_exact'),
	url(r'^cmdb/prk/userlookup/$', views.prk_userlookup, name='prk_userlookup'),

	url(r'^dpia/$', views.alle_dpia, name='alle_dpia'),
	url(r'^dpia/(?P<pk>\d{1,8})/$', views.detaljer_dpia, name='detaljer_dpia'),

	url(r'^driftsmodell/alle/$', views.alle_driftsmodeller, name='alle_driftsmodeller'),
	url(r'^driftsmodell/(?P<pk>\d{1,8})/$', views.detaljer_driftsmodell, name='detaljer_driftsmodell'),
	url(r'^virksomhet/drift/prioriteringer/(?P<pk>\d{1,8})/$', views.drift_beredskap, name='drift_beredskap'),
	url(r'^virksomhet/driftsmodell/(?P<pk>\d{1,8})/$', views.driftsmodell_virksomhet, name='driftsmodell_virksomhet'),
	url(r'^virksomhet/driftsmodell/klassifisering/(?P<pk>\d{1,8})/$', views.driftsmodell_virksomhet_klassifisering, name='driftsmodell_virksomhet_klassifisering'),
	url(r'^driftsmodell/mangler_system/$', views.systemer_uten_driftsmodell, name='systemer_uten_driftsmodell'),

	url(r'^definisjon/alle/$', views.alle_definisjoner, name='alle_definisjoner'),
	url(r'^definisjon/(?P<begrep>[-_a-zA-Z0-9\s]{1,150})/$', views.definisjon, name='definisjon'),

	url(r'^dashboard/$', views.dashboard_all, name='dashboard_all'),
	url(r'^dashboard/(?P<virksomhet>\d+)/$', views.dashboard_all, name='dashboard_all'),

	# ubw
	url(r'^ubw/alle/$', views.ubw_home, name='ubw_home'),
	url(r'^ubw/faktura/(?P<pk>\d+)/$', views.ubw_enhet, name='ubw_enhet'),
	url(r'^ubw/api/(?P<pk>\d+)/$', views.ubw_api, name='ubw_api'), # brukes av UKE/POS
	url(r'^ubw/ekstra/(?P<faktura_id>\d+)/$', views.ubw_ekstra, name='ubw_ekstra_new'),
	url(r'^ubw/ekstra/(?P<faktura_id>\d+)/(?P<pk>\d+)/$', views.ubw_ekstra, name='ubw_ekstra_edit'),
	url(r'^ubw/kategori/(?P<belongs_to>\d+)/$', views.ubw_kategori, name='ubw_kategori'),

	url(r'^ubw/(?P<belongs_to>\d+)/estimat/$', views.ubw_estimat_list, name='ubw_estimat_list'),
	url(r'^ubw/(?P<belongs_to>\d+)/estimat/create/$', views.ubw_estimat_create, name='ubw_estimat_create'),
	url(r'^ubw/(?P<belongs_to>\d+)/estimat/(?P<pk>\d+)/update/$', views.ubw_estimat_update, name='ubw_estimat_update'),
	url(r'^ubw/estimat/(?P<pk>\d+)/delete/$', views.ubw_estimat_delete, name='ubw_estimat_delete'),
	url(r'^ubw/estimat/(?P<pk>\d+)/copy/$', views.ubw_estimat_copy, name='ubw_estimat_copy'),

	url(r'^prk/api/usr/$', views.prk_api_usr, name='prk_api_usr'),
	url(r'^prk/api/grp/$', views.prk_api_grp, name='prk_api_grp'),

	url(r'^forvaltere/api/$', views.forvalter_api, name='forvalter_api'), # brukes av UKE/tjenestekatalogen
	url(r'^cmdb/api/$', views.cmdb_api, name='cmdb_api'), # åpent api (innført logging?)
	url(r'^cmdb/api/test/$', views.cmdb_api_new, name='cmdb_api_new'), # åpent api (innført logging?)
	url(r'^systemer/api/$', views.systemer_api, name='systemer_api'), # åpent API (innført logging?)


	# import og konvertering
	url(r'^import/groups/permissions/$', views_import.import_group_permissions, name='import_group_permissions'),
	url(r'^import/cmdb/business_services/$', views_import.import_business_services, name='import_bsbss'),
	url(r'^import/cmdb/servers/$', views_import.import_cmdb_servers, name='import_servers'),
	url(r'^import/cmdb/disker/$', views_import.import_cmdb_disk, name='import_cmdb_disk'),
	url(r'^import/cmdb/databases/$', views_import.import_cmdb_databases, name='import_databases'),
	url(r'^import/cmdb/databases/oracle/$', views_import.import_cmdb_databases_oracle, name='import_cmdb_databases_oracle'),
	url(r'^import/definisjon/organisasjon/$', views_import.import_organisatorisk_forkortelser, name='import_organisatorisk_forkortelser'),

	# Er denne i bruk?
	url(r'^user_clean_up/$', views.user_clean_up, name='user_clean_up'),
]
