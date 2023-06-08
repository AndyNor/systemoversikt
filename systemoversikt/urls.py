"""systemoversikt URL Configuration
The `urlpatterns` list routes URLs to views. For more information please see:
	https://docs.djangoproject.com/en/1.11/topics/http/urls/
"""
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

	re_path(r'^debug_info$', views.debug_info, name='debug_info'),

	re_path(r'^$', views.home, name='home'),
	re_path(r'^chart/', views.home_chart, name='home_chart'),
	re_path(r'^oidc/', include('mozilla_django_oidc.urls')),
	re_path(r'^login/$', admin.site.login, name='login'),
	re_path(r'^logout/$', admin.site.logout, name='logout'),

	re_path(r'^admin/profil/', views.minside, name="minside"),
	re_path(r'^admin/logger/database/$', views.logger, name='logger'),
	re_path(r'^admin/logger/audit/$', views.logger_audit, name='logger_audit'),
	re_path(r'^admin/logger/autentisering/$', views.logger_autentisering, name='logger_autentisering'),
	re_path(r'^admin/logger/api/$', views.logger_api, name='logger_api'),
	re_path(r'^admin/logger/api/csirt/$', views.logger_api_csirt, name='logger_api_csirt'),
	re_path(r'^admin/roller/$', views.roller, name='roller'),
	re_path(r'^admin/rettigheter/$', views.permissions, name='permissions'),
	re_path(r'^admin/erstattansvarlig/$', views.ansvarlig_bytte, name='ansvarlig_bytte'),
	re_path(r'^admin/valgbarekategorier/$', views.valgbarekategorier, name='valgbarekategorier'),
	re_path(r'^admin/bytt_virksomhet/$', views.bytt_virksomhet, name='bytt_virksomhet'),
	re_path(r'^admin/databasestatistikk/$', views.databasestatistikk, name='databasestatistikk'),


	re_path(r'^admin/', admin.site.urls, name="admin"), # må stå til sist etter alle andre /admin/

	re_path(r'^sok/$', views.search, name='search'),
	re_path(r'^firewall/$', views.firewall_parser, name='firewall_parser'),

	re_path(r'^systemer/alle/$', views.alle_systemer, name='alle_systemer'),
	re_path(r'^systemer/forvalteroversikt/$', views.alle_systemer_forvaltere, name='alle_systemer_forvaltere'),
	re_path(r'^systemer/pakket/$', views.systemer_pakket, name='systemer_pakket'),
	re_path(r'^systemer/vurderinger/$', views.systemer_vurderinger, name='systemer_vurderinger'),
	re_path(r'^systemer/FIP/endoflife/$', views.systemer_EOL, name='systemer_EOL'),
	re_path(r'^systemer/detaljer/(?P<pk>\d{1,8})/$', views.systemdetaljer, name='systemdetaljer'),
	re_path(r'^systemer/bruk/$', views.mine_systembruk, name='mine_systembruk'),
	re_path(r'^systemer/utfaset/$', views.systemer_utfaset, name='systemer_utfaset'),
	re_path(r'^systemer/bruk/(?P<pk>\d{1,8})/$', views.bruksdetaljer, name='bruksdetaljer'),
	re_path(r'^systemer/bruk/registrer_bruk/(?P<system>\d{1,8})/$', views.registrer_bruk, name='registrer_bruk'),
	re_path(r'^systemer/systemklassifisering/(?P<id>[A-Z-_]{1,30})/$', views.systemklassifisering_detaljer, name='systemklassifisering_detaljer'),
	re_path(r'^systemer/systemtype/(?P<pk>\d{1,8})/$', views.systemtype_detaljer, name='systemtype_detaljer'),
	re_path(r'^systemer/systemtype/tom/$', views.systemtype_detaljer, name='systemtype_detaljer_mangler'),
	re_path(r'^system_til_programvare/$', views.system_til_programvare, name='system_til_programvare_indeks'),
	re_path(r'^system_til_programvare/(?P<system_id>\d{1,8})/$', views.system_til_programvare, name='system_til_programvare'),

	re_path(r'^behandlinger/user/$', views.mine_behandlinger, name='mine_behandlinger'),
	re_path(r'^behandlinger/alle/$', views.alle_behandlinger, name='alle_behandlinger'),
	re_path(r'^behandlinger/kopier/(?P<system_pk>\d{1,8})/$', views.behandling_kopier, name='behandling_kopier'),
	re_path(r'^virksomhet/behandlinger/(?P<pk>\d{1,8})/$', views.alle_behandlinger_virksomhet, name='alle_behandlinger_virksomhet'),
	#re_path(r'^virksomhet/behandlinger/(?P<pk>\d{1,8})/(?P<internt_ansvarlig>.*)/$', views.alle_behandlinger_virksomhet, name='behandlinger_virksomhet_ansvarlig'),
	re_path(r'^behandlinger/detaljer/(?P<pk>\d{1,8})/$', views.behandlingsdetaljer, name='behandlingsdetaljer'),

	re_path(r'^virksomhet/alle_avtaler/$', views.alle_avtaler, name='alle_avtaler'),
	re_path(r'^avtaler/detaljer/(?P<pk>\d{1,8})/$', views.avtaledetaljer, name='avtaledetaljer'),
	re_path(r'^virksomhet/avtaler/(?P<virksomhet>\d{1,8})/$', views.alle_avtaler, name='avtalervirksomhet'),
	re_path(r'^avtaler/databehandleravtale/virksomhet/(?P<pk>\d{1,8})/$', views.databehandleravtaler_virksomhet, name='databehandleravtaler_virksomhet'),

	re_path(r'^cmdb/bruker/(?P<pk>\d{1,8})/$', views.bruker_detaljer, name='bruker_detaljer'),
	re_path(r'^cmdb/bruker/$', views.bruker_sok, name='bruker_sok'),
	re_path(r'^cmdb/bruker/brukerlistesok/$', views.ad_brukerlistesok, name='cmdb_ad_brukerlistesok'),


	re_path(r'^virksomhet/$', views.alle_virksomheter, name='alle_virksomheter'),
	re_path(r'^virksomhet/kontaktinfo/$', views.alle_virksomheter_kontaktinfo, name='alle_virksomheter_kontaktinfo'),
	re_path(r'^virksomhet/alle/$', views.alle_virksomheter, name='alle_virksomheter_sidemeny'),
	re_path(r'^virksomhet/(?P<pk>\d{1,8})/$', views.virksomhet, name='virksomhet'),
	re_path(r'^virksomhet/passwdexpire/(?P<pk>\d{1,8})/$', views.passwordexpire, name='passwordexpire'),
	re_path(r'^virksomhet/tomepost/(?P<pk>\d{1,8})/$', views.tom_epost, name='tom_epost'),
	re_path(r'^virksomhet/vanlige_brukere/(?P<pk>\d{1,8})/$', views.ansatte_virksomhet, name='ansatte_virksomhet'),
	re_path(r'^virksomhet/passwdneverexpire/(?P<pk>\d{1,8})/$', views.passwdneverexpire, name='passwdneverexpire'),
	re_path(r'^virksomhet/ansvarlige/(?P<pk>\d{1,8})/$', views.virksomhet_ansvarlige, name='virksomhet_ansvarlige'),
	re_path(r'^virksomhet/min/$', views.min_virksomhet, name='min_virksomhet'),
	re_path(r'^virksomhet/arkivplan/(?P<pk>\d{1,8})/$', views.virksomhet_arkivplan, name='virksomhet_arkivplan'),
	re_path(r'^virksomhet/sertifikatmyndighet/$', views.sertifikatmyndighet, name='sertifikatmyndighet'),
	re_path(r'^virksomhet/innsyn/(?P<pk>\d{1,8})/$', views.innsyn_virksomhet, name='innsyn_virksomhet'),
	re_path(r'^virksomhet/systemkvalitet/(?P<pk>\d{1,8})/$', views.systemkvalitet_virksomhet, name='systemkvalitet_virksomhet'),
	re_path(r'^virksomhet/enhet/$', views.virksomhet_enhetsok, name='virksomhet_enhetsok'),
	re_path(r'^virksomhet/enhet/(?P<pk>\d{1,8})/$', views.enhet_detaljer, name='enhet_detaljer'),
	re_path(r'^virksomhet/enhet/graf/(?P<pk>\d{1,8})/$', views.virksomhet_enheter, name='virksomhet_enheter'),
	re_path(r'^virksomhet/prkadmin/(?P<pk>\d{1,8})/$', views.virksomhet_prkadmin, name='virksomhet_prkadmin'),
	re_path(r'^virksomhet/systemer/(?P<pk>\d{1,8})/$', views.all_bruk_for_virksomhet, name='all_bruk_for_virksomhet'),
	re_path(r'^virksomhet/systemer/ansvarligfor/(?P<pk>\d{1,8})/$', views.systemer_virksomhet_ansvarlig_for, name='systemer_virksomhet_ansvarlig_for'),
	re_path(r'^virksomhet/klienter/(?P<pk>\d{1,8})/$', views.klienter_hos_virksomhet, name='klienter_hos_virksomhet'),
	re_path(r'^virksomhet/sikkerhetsavvik/$', views.virksomhet_sikkerhetsavvik, name='virksomhet_sikkerhetsavvik'),
	re_path(r'^virksomhet/sikkerhetsavvik/(?P<pk>\d{1,8})/$', views.virksomhet_sikkerhetsavvik, name='virksomhet_sikkerhetsavvik'),
	re_path(r'^virksomhet/leverandortilgang/(?P<pk>\d{1,8})/$', views.virksomhet_leverandortilgang, name='virksomhet_leverandortilgang'),


	re_path(r'^leverandor/$', views.alle_leverandorer, name='alle_leverandorer'),
	re_path(r'^leverandor/bytt_leverandor/(?P<fra>\d{1,8})/(?P<til>\d{1,8})/$', views.bytt_leverandor, name='bytt_leverandor'),
	re_path(r'^leverandor/(?P<pk>\d{1,8})/$', views.leverandor, name='leverandor'),

	re_path(r'^hovedkategorier/alle/$', views.alle_hovedkategorier, name='alle_hovedkategorier'),
	re_path(r'^hovedkategorier/subkategorier/$', views.alle_systemkategorier, name='alle_systemkategorier'),
	re_path(r'^hovedkategorier/subkategorier/bytt_kategori/(?P<fra>\d{1,8})/(?P<til>\d{1,8})/$', views.bytt_kategori, name='bytt_kategori'),
	re_path(r'^hovedkategorier/subkategorier/uten_kategori/$', views.uten_systemkategori, name='uten_systemkategorier'),
	re_path(r'^hovedkategorier/subkategorier/(?P<pk>\d{1,8})/$', views.systemkategori, name='systemkategori'),

	re_path(r'^domener/alle/$', views.alle_systemurler, name='alle_systemurler'),
	re_path(r'^virksomhet/domener/(?P<pk>\d{1,8})/$', views.virksomhet_urler, name='virksomhet_urler'),

	re_path(r'^programvare/alle/$', views.alle_programvarer, name='alle_programvarer'),
	re_path(r'^programvare/(?P<pk>\d{1,8})/$', views.programvaredetaljer, name='programvaredetaljer'),
	re_path(r'^virksomhet/programvare/(?P<pk>\d{1,8})/$', views.all_programvarebruk_for_virksomhet, name='all_programvarebruk_for_virksomhet'),
	re_path(r'^programvare/bruk/(?P<pk>\d{1,8})/$', views.programvarebruksdetaljer, name='programvarebruksdetaljer'),

	re_path(r'^ansvarlige/alle/$', views.alle_ansvarlige, name='alle_ansvarlige'),
	re_path(r'^ansvarlige/eksport/$', views.alle_ansvarlige_eksport, name='alle_ansvarlige_eksport'),
	re_path(r'^ansvarlige/(?P<pk>\d{1,8})/$', views.ansvarlig, name='ansvarlig'),

	re_path(r'^cmdb/statistikk/$', views.cmdb_statistikk, name='cmdb_statistikk'),
	re_path(r'^cmdb/per_virksomhet/$', views.cmdb_per_virksomhet, name='cmdb_per_virksomhet'),
	re_path(r'^cmdb/bs/$', views.alle_cmdbref, name='alle_cmdbref_sok'),
	re_path(r'^cmdb/(?P<pk>\d{1,8})/$', views.cmdb_bss, name='cmdb_bss'),
	re_path(r'^cmdb/servere/$', views.alle_servere, name='alle_servere'),
	re_path(r'^cmdb/eksponerte_servere/$', views.cmdb_internetteksponerte_servere, name='cmdb_internetteksponerte_servere'),
	re_path(r'^cmdb/servere/diabledpoweredon/$', views.cmdb_servere_disabled_poweredon, name='cmdb_servere_disabled_poweredon'),
	re_path(r'^cmdb/klienter/$', views.alle_klienter, name='alle_klienter'),
	re_path(r'^cmdb/servere/utfaset/$', views.servere_utfaset, name='servere_utfaset'),
	re_path(r'^cmdb/devicedetails/(?P<pk>\d{1,8})/$', views.cmdb_devicedetails, name='cmdb_devicedetails'),
	re_path(r'^cmdb/databaser/$', views.alle_databaser, name='alle_databaser'),
	re_path(r'^cmdb/ip/$', views.alle_ip, name='alle_ip'),
	re_path(r'^cmdb/dns/$', views.alle_dns, name='alle_dns'),
	re_path(r'^cmdb/dns/txt/$', views.dns_txt, name='dns_txt'),
	re_path(r'^cmdb/nettverk/$', views.alle_nettverk, name='alle_nettverk'),
	re_path(r'^cmdb/nettverk/(?P<pk>\d{1,8})/$', views.nettverk_detaljer, name='nettverk_detaljer'),
	re_path(r'^cmdb/nettverksenheter/$', views.alle_nettverksenheter, name='alle_nettverksenheter'),
	re_path(r'^cmdb/vip/$', views.alle_vip, name='alle_vip'),
	re_path(r'^cmdb/vip/(?P<pk>\d{1,8})/$', views.detaljer_vip, name='detaljer_vip'),
	re_path(r'^cmdb/device/sok/$', views.maskin_sok, name='maskin_sok'),
	re_path(r'^cmdb/azure/applications/$', views.azure_applications, name='azure_applications'),
	re_path(r'^cmdb/azure/keys/$', views.azure_application_keys, name='azure_application_keys'),
	re_path(r'^cmdb/o365_avvik/$', views.o365_avvik, name='o365_avvik'),
	re_path(r'^cmdb/backup/$', views.cmdb_backup_index, name='cmdb_backup_index'),
	re_path(r'^cmdb/adcs/$', views.cmdb_adcs_index, name='cmdb_adcs_index'),
	re_path(r'^cmdb/uten_backup/$', views.cmdb_uten_backup, name='cmdb_uten_backup'),
	re_path(r'^cmdb/lagring/$', views.cmdb_lagring_index, name='cmdb_lagring_index'),
	re_path(r'^cmdb/minne/$', views.cmdb_minne_index, name='cmdb_minne_index'),
	re_path(r'^cmdb/forvaltere/$', views.cmdb_forvaltere, name='cmdb_forvaltere'),
	re_path(r'^cmdb/azure/uten_epost/$', views.cmdb_uten_epost_stat, name='cmdb_uten_epost_stat'),




	re_path(r'^cmdb/prk/$', views.alle_prk, name='alle_prk'),
	re_path(r'^cmdb/prk/browse/$', views.prk_browse, name='prk_browse'),
	re_path(r'^cmdb/prk/browse/(?P<skjema_id>\d{1,8})/$', views.prk_skjema, name='prk_skjema'),

	re_path(r'^cmdb/ad/leverandortilgang/$', views.leverandortilgang, name='leverandortilgang'),
	re_path(r'^cmdb/ad/leverandortilgang/(?P<valgt_gruppe>[-._a-zA-Z0-9\s]{2,100})/$', views.leverandortilgang, name='leverandortilgang_detaljer'),
	re_path(r'^cmdb/ad/drifttilgang/$', views.drifttilgang, name='drifttilgang'),
	re_path(r'^cmdb/ad/tbrukere/$', views.tbrukere, name='tbrukere'),
	re_path(r'^cmdb/bruker/logger/$', views.logger_users, name='logger_users'),
	re_path(r'^cmdb/bruker/flereidenter/$', views.cmdb_ad_flere_brukeridenter, name='cmdb_ad_flere_brukeridenter'),


	re_path(r'^cmdb/ad/lookup/$', views.ad, name='ad'),
	re_path(r'^cmdb/ad/analyse/$', views.ad_analyse, name='ad_analyse'),
	re_path(r'^cmdb/ad/adgruppe/$', views.alle_adgrupper, name='alle_adgrupper'),
	re_path(r'^cmdb/ad/adgruppe/(?P<pk>\d{1,8})/$', views.adgruppe_detaljer, name='adgruppe_detaljer'),
	re_path(r'^cmdb/ad/adgruppe/graf/(?P<pk>\d{1,8})/$', views.adgruppe_graf, name='adgruppe_graf'),
	re_path(r'^cmdb/ad/adorgunit/$', views.adorgunit_detaljer, name='adorgunit_detaljer'),
	re_path(r'^cmdb/ad/adorgunit/(?P<pk>\d{1,8})/$', views.adorgunit_detaljer, name='adorgunit_detaljer'),
	re_path(r'^cmdb/ad/lookup/(?P<name>[-._a-zA-Z0-9\s]{2,100})/$', views.ad_details, name='ad_details'),  #denne må komme etter ad/adgrupper/
	# i AD er følgende tegn ulovlige: # + " \ < > ; (RFC 2253)
	# komma tillates da det brukes for å skille elementer fra hverandre
	# leading space eller #, samt trailing space er heller ikke tillatt, men vi gjør ikke noe med dem.
	re_path(r'^cmdb/ad/lookup/recursive/(?P<group>[^#\+\"\\\<\>\;]{2,200})/$', views.recursive_group_members, name='recursive_group_members'),
	re_path(r'^cmdb/ad/lookup/exact/(?P<name>[^#\+\"\\\<\>\;]{2,200})/$', views.ad_exact, name='ad_exact'),
	re_path(r'^cmdb/prk/userlookup/$', views.prk_userlookup, name='prk_userlookup'),
	re_path(r'^cmdb/ad/gruppeanalyse/$', views.ad_gruppeanalyse, name='ad_gruppeanalyse'),


	re_path(r'^cmdb/tools/unique$', views.tool_unique_items, name='tool_unique_items'),
	re_path(r'^cmdb/tools/compare$', views.tool_compare_items, name='tool_compare_items'),
	re_path(r'^cmdb/tools/docx2html$', views.tool_docx2html, name='tool_docx2html'),
	re_path(r'^cmdb/tools/word_count$', views.tool_word_count, name='tool_word_count'),


	re_path(r'^dpia/$', views.alle_dpia, name='alle_dpia'),
	re_path(r'^dpia/(?P<pk>\d{1,8})/$', views.detaljer_dpia, name='detaljer_dpia'),

	re_path(r'^driftsmodell/alle/$', views.alle_driftsmodeller, name='alle_driftsmodeller'),
	re_path(r'^driftsmodell/(?P<pk>\d{1,8})/$', views.detaljer_driftsmodell, name='detaljer_driftsmodell'),
	re_path(r'^virksomhet/drift/prioriteringer/(?P<pk>\d{1,8})/$', views.drift_beredskap, name='drift_beredskap'),
	re_path(r'^virksomhet/drift/prioriteringer/(?P<pk>\d{1,8})/(?P<eier>\d{1,8})$', views.drift_beredskap, name='drift_beredskap_for_eier'),
	re_path(r'^virksomhet/driftsmodell/(?P<pk>\d{1,8})/$', views.driftsmodell_virksomhet, name='driftsmodell_virksomhet'),
	re_path(r'^virksomhet/driftsmodell/klassifisering/(?P<pk>\d{1,8})/$', views.driftsmodell_virksomhet_klassifisering, name='driftsmodell_virksomhet_klassifisering'),
	re_path(r'^driftsmodell/mangler_system/$', views.systemer_uten_driftsmodell, name='systemer_uten_driftsmodell'),

	re_path(r'^definisjon/alle/$', views.alle_definisjoner, name='alle_definisjoner'),
	re_path(r'^definisjon/(?P<begrep>[-_a-zA-Z0-9\s]{1,150})/$', views.definisjon, name='definisjon'),

	re_path(r'^dashboard/$', views.dashboard_all, name='dashboard_all'),
	re_path(r'^dashboard/(?P<virksomhet>\d+)/$', views.dashboard_all, name='dashboard_all'),

	# ubw
	re_path(r'^ubw/alle/$', views.ubw_home, name='ubw_home'),
	re_path(r'^ubw/faktura/(?P<pk>\d+)/$', views.ubw_enhet, name='ubw_enhet'),
	re_path(r'^ubw/api/(?P<pk>\d+)/$', views.ubw_api, name='ubw_api'), # brukes av UKE/POS
	re_path(r'^ubw/ekstra/(?P<faktura_id>\d+)/$', views.ubw_ekstra, name='ubw_ekstra_new'),
	re_path(r'^ubw/ekstra/(?P<faktura_id>\d+)/(?P<pk>\d+)/$', views.ubw_ekstra, name='ubw_ekstra_edit'),
	re_path(r'^ubw/kategori/(?P<belongs_to>\d+)/$', views.ubw_kategori, name='ubw_kategori'),
	re_path(r'^ubw/endreenhet/(?P<belongs_to>\d+)/$', views.ubw_endreenhet, name='ubw_endreenhet'),

	re_path(r'^ubw/(?P<belongs_to>\d+)/estimat/$', views.ubw_estimat_list, name='ubw_estimat_list'),
	re_path(r'^ubw/(?P<belongs_to>\d+)/estimat/create/$', views.ubw_estimat_create, name='ubw_estimat_create'),
	re_path(r'^ubw/(?P<belongs_to>\d+)/estimat/(?P<pk>\d+)/update/$', views.ubw_estimat_update, name='ubw_estimat_update'),
	re_path(r'^ubw/estimat/(?P<pk>\d+)/delete/$', views.ubw_estimat_delete, name='ubw_estimat_delete'),
	re_path(r'^ubw/estimat/(?P<pk>\d+)/copy/$', views.ubw_estimat_copy, name='ubw_estimat_copy'),
	re_path(r'^ubw/multiselect/$', views.ubw_multiselect, name='ubw_multiselect'),

	re_path(r'^prk/api/usr/$', views.prk_api_usr, name='prk_api_usr'),
	re_path(r'^prk/api/grp/$', views.prk_api_grp, name='prk_api_grp'),

	re_path(r'^tjenestekatalogen/forvaltere/$', views.tjenestekatalogen_forvalter_api, name='tjenestekatalogen_forvalter_api'), # brukes av UKE/tjenestekatalogen. Bruker API-nøkkel.
	re_path(r'^tjenestekatalogen/systemer/$', views.tjenestekatalogen_systemer_api, name='tjenestekatalogen_systemer_api'), # brukes av UKE/tjenestekatalogen. Bruker API-nøkkel.
	re_path(r'^cmdb/api/$', views.cmdb_api, name='cmdb_api'), # (det er innført behov for API-key)
	re_path(r'^cmdb/csirt_api/$', views.csirt_api, name='csirt_api'), # (det er innført behov for API-key)
	re_path(r'^cmdb/api/kompass/$', views.cmdb_api_kompass, name='cmdb_api_kompass'), # (det er innført behov for API-key)
	#re_path(r'^cmdb/api/test/$', views.cmdb_api_new, name='cmdb_api_new'), # (det er innført behov for API-key)
	re_path(r'^systemer/api/$', views.systemer_api, name='systemer_api'), # (det er innført behov for API-key)
	re_path(r'^virksomhet/(?P<virksomhet_pk>\d+)/excelapi/$', views.system_excel_api, name='system_excel_api'), # det må brukes API-key
	re_path(r'^systemer/iga/api/$', views.iga_api, name='iga_api'), # (det er innført behov for API-key)
	re_path(r'^systemer/behandlingsoversikt/api/$', views.behandlingsoversikt_api, name='behandlingsoversikt_api'), # (det er innført behov for API-key)
	re_path(r'^get-api/tilgangsgrupper/$', views.tilgangsgrupper_api, name='tilgangsgrupper_api'), # (det er innført behov for API-key)
	re_path(r'^ukecsirt/ipsok/api/$', views.csirt_iplookup_api, name='csirt_iplookup_api'), # (det er innført behov for API-key)
	re_path(r'^ukecsirt/maskinsok/api/$', views.csirt_maskinlookup_api, name='csirt_maskinlookup_api'), # (det er innført behov for API-key)

	# import og konvertering
	re_path(r'^import/groups/permissions/$', views_import.import_group_permissions, name='import_group_permissions'),
	re_path(r'^import/definisjon/organisasjon/$', views_import.import_organisatorisk_forkortelser, name='import_organisatorisk_forkortelser'),

	# Er denne i bruk?
	re_path(r'^user_clean_up/$', views.user_clean_up, name='user_clean_up'),

]
