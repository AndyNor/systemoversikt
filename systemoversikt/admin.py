# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import models
from django.contrib import messages
from django.shortcuts import redirect
from .models import *
from simple_history.admin import SimpleHistoryAdmin

class SikkerhetstesterAdmin(SimpleHistoryAdmin):
	list_display = ('testet_av', 'dato_rapport', 'type_test', 'rapport',)
	autocomplete_fields = ('systemer', 'testet_av')


class SystemAdmin(SimpleHistoryAdmin):
	list_display = ('systemnavn', 'systembeskrivelse')
	search_fields = ('systemnavn', 'systembeskrivelse')
	list_filter = ('sikkerhetsnivaa', 'systemtyper', 'livslop_status')
	filter_horizontal = ('systemkategorier',)
	autocomplete_fields = (
		'systemeier',
		'systemforvalter',
		'programvarer',
		'datautveksling_avleverer_til',
		'datautveksling_mottar_fra',
		'avhengigheter_referanser',
		'applikasjonsdriftleverandor',
		'basisdriftleverandor',
		'systemurl',
		'systemleverandor',
		'systemeier_kontaktpersoner_referanse',
		'systemforvalter_kontaktpersoner_referanse',
		'kontaktperson_innsyn',
		'cmdbref_prod',
		'cmdbref',
		'systemtyper',
		'loggingalternativer',
		'autentiseringsalternativer',
		'informasjonsklassifisering',
	)

	fieldsets = (

		('Initiell registrering', {
			'description': 'Dette er felter ansett som obligatoriske, og kreves utfylt for å kunne krysse av for at informasjonen er kvalitetssikret..',
			'fields': (
				'ibruk',
				'informasjon_kvalitetssikret',
				'systemnavn',
				'systembeskrivelse',
				'systemtyper',
				'systemeierskapsmodell',
				'systemeier',
				'systemeier_kontaktpersoner_referanse',
				'systemforvalter',
				'systemforvalter_kontaktpersoner_referanse',
				'driftsmodell_foreignkey',
				'informasjonsklassifisering',
				'sikkerhetsnivaa',
				'systemkategorier',
				('risikovurdering_behovsvurdering', 'dato_sist_ros'),
				'url_risikovurdering',
				'risikovurdering_tekst',
				'datautveksling_mottar_fra',
				'datautveksling_avleverer_til',
				'avhengigheter_referanser',
				'avhengigheter',
				'systemurl',
			),
		}),
		('Tekniske og sikkerhetsmessige vurderinger', {
			'description': 'Se <a target="_blank" href="https://confluence.oslo.kommune.no/x/ywUfBg">definisjoner på Confluence</a>.',
			'fields': (
				'livslop_status',
				'funksjonell_egnethet',
				'teknisk_egnethet',
				'kjente_mangler',
				'konfidensialitetsvurdering',
				'integritetsvurdering',
				('tilgjengelighetsvurdering','tilgjengelighet_kritiske_perioder'),
			)
		}),
		('Dokumentasjon og drift', {
			'fields': (
				'systemleverandor',
				'basisdriftleverandor',
				('applikasjonsdriftleverandor', 'applikasjonsdrift_behov_databehandleravtale'),
				'cmdbref_prod',
				'cmdbref',
				'brukerdokumentasjon_url',
				'high_level_design_url',
				'low_level_design_url',
				'programvarer',
				'database',
				'isolert_drift',
			),
		}),
		('Utdypende opplysninger om systemet', {
			'classes': ('collapse',),
			'fields': (
				'leveransemodell_fip',
				'kontaktgruppe_url',
				'datamodell_url',
				'datasett_url',
				'api_url',
				'kildekode_url',
				'superbrukere',
				'nokkelpersonell',
				'tjenestenivaa',
			),
		}),
		('DPIA / personvern', {
			'classes': ('collapse',),
			'fields': (
				('kontaktperson_innsyn', 'innsyn_innbygger', 'innsyn_ansatt'),
				'autentiseringsalternativer',
				'loggingalternativer',
				'autorisasjon_differensiering_beskrivelse',
				'autorisasjon_differensiering_saksalder',
				'dataminimalisering',
				'sletting_av_personopplysninger',
				'funksjonalitet_kryptering',
				'anonymisering_pseudonymisering',
				'sikkerhetsmessig_overvaaking'
			),
		}),
		('Utfases', {
			'classes': ('collapse',),
			'fields': (
				'systemtekniske_sikkerhetstiltak',
				'programvarekategori',
				'strategisk_egnethet',
				'selvbetjening',
				'kommentar',
			),
		}),
	)


class VirksomhetAdmin(SimpleHistoryAdmin):
	list_display = ('virksomhetsforkortelse', 'virksomhetsnavn', 'ansatte')
	search_fields = ('virksomhetsnavn', 'virksomhetsforkortelse')
	list_filter = ('resultatenhet',)
	filter_horizontal = ('overordnede_virksomheter',)
	autocomplete_fields = (
		'leder',
		'informasjonssikkerhetskoordinator',
		'personvernkoordinator',
		'ikt_kontakt',
		'uke_kam_referanse',
		'autoriserte_bestillere_sertifikater',
		'autoriserte_bestillere_tjenester',
		'autoriserte_bestillere_tjenester_uke',
	)

	fieldsets = (

			('Initiell registrering', {
				'fields': (
					'virksomhetsnavn',
					'virksomhetsforkortelse',
					'ordinar_virksomhet',
					'orgnummer',
					'resultatenhet',
					'ikt_kontakt',
					'leder',
					'autoriserte_bestillere_tjenester',
					'autoriserte_bestillere_tjenester_uke',
				),
			}),
			('GDPR / sikkerhet', {
				'classes': ('collapse',),
				'fields': (
					'personvernkoordinator',
					'informasjonssikkerhetskoordinator',
					'rutine_tilgangskontroll',
					'rutine_behandling_personopplysninger',
					'rutine_klage_behandling',
				),
			}),
			('Organisatorisk', {
				'classes': ('collapse',),
				'fields': (
					'overordnede_virksomheter',
					'kan_representeres',
					'ansatte',
					'intranett_url',
					'www_url',
				),
			}),
			('Sertifikatadministrasjon', {
				'classes': ('collapse',),
				'fields': (
					'autoriserte_bestillere_sertifikater',
					('sertifikatfullmakt_avgitt_web', 'sertifikatfullmakt_avgitt_virksomhet'),
				),
			}),
			('UKE-spesifikt', {
				'classes': ('collapse',),
				'fields': (
					'uke_kam_referanse',
				),
			})
		)

class SystemBrukAdmin(SimpleHistoryAdmin):
	list_display = ('system', 'brukergruppe', 'kommentar', 'avtaletype', 'systemeierskap', 'kostnadersystem')
	search_fields = ('system__systemnavn', 'system__systembeskrivelse', 'kommentar', 'systemforvalter')
	list_filter = ('avtalestatus', 'avtale_kan_avropes', 'systemeierskapsmodell', 'brukergruppe')
	autocomplete_fields = ('brukergruppe', 'system', 'systemforvalter', 'systemforvalter_kontaktpersoner_referanse', 'avhengigheter_referanser')

	fieldsets = (
		('Initiell registrering', {
			'fields': (
				'brukergruppe',
				'system',
				'del_behandlinger',
				'kommentar',
				'systemforvalter_kontaktpersoner_referanse',
				'url_risikovurdering',
				'dato_sist_ros',
				'risikovurdering_tekst',
				'strategisk_egnethet',
				'funksjonell_egnethet',
				'teknisk_egnethet',
			),
		}),
		('Vurderinger', {
			'classes': ('collapse',),
			'fields': (
				'konfidensialitetsvurdering',
				'integritetsvurdering',
				'tilgjengelighetsvurdering',
				'avtaletype',
				'avtalestatus',
			),
		}),
		('Avvikles', {
			'classes': ('collapse',),
			'fields': (
				'kostnadersystem',
				'avtale_kan_avropes',
				'systemeierskap',
				'livslop_status',
				'systemforvalter',
				'avhengigheter_referanser',
				'avhengigheter',
				'driftsmodell_foreignkey',
				'systemeierskapsmodell',
				'programvarekategori',
			),
		})
	)

class LeverandorAdmin(SimpleHistoryAdmin):
	list_display = ('leverandor_navn', 'kontaktpersoner', 'orgnummer')
	search_fields = ('leverandor_navn', 'orgnummer', 'notater')



class BehandlingerPersonopplysningerAdmin(SimpleHistoryAdmin):
	list_display = ('behandlingsansvarlig', 'internt_ansvarlig', 'funksjonsomraade', 'behandlingen')
	search_fields = ('behandlingen', 'internt_ansvarlig', 'funksjonsomraade',)
	list_filter = ('behandlingsgrunnlag_valg', 'den_registrerte', 'kategorier_personopplysninger', 'behandlingsansvarlig')
	filter_horizontal = ('relasjon_registrerte', 'den_registrerte_hovedkateogi', 'virksomhet_blacklist', 'programvarer', 'systemer', 'navn_databehandler', 'kategorier_personopplysninger', 'den_registrerte', 'behandlingsgrunnlag_valg')
	autocomplete_fields = ('behandlingsansvarlig', 'oppdateringsansvarlig')

	fieldsets = (

		('Metadata', {
			'classes': ('',),
			'fields': (
				'behandlingsansvarlig',
				'internt_ansvarlig',
				'oppdateringsansvarlig',
				'informasjon_kvalitetssikret',
				'fellesbehandling',
			),
		}),
		('Obligatorisk registrering', {
			'classes': ('',),
			'fields': (
				'behandlingen',
				'formaal',
				('den_registrerte', 'den_registrerte_detaljer',),
				('kategorier_personopplysninger', 'personopplysninger_utdyping'),
				('utlevering_ekstern_myndighet', 'utlevering_ekstern_myndighet_utdyping'),
				('utlevering_utenfor_EU', 'garantier_overforing'),
				'oppbevaringsplikt',
				('krav_slettefrister', 'planlagte_slettefrister'),
				'hoy_personvernrisiko',
				'systemer',
			),
		}),
		('Anbefalte ekstraopplysninger', {
			'classes': ('',),
			'fields': (
				'opplysningskilde',
				('behandlingsgrunnlag_valg', 'behandlingsgrunnlag_utdyping', 'behandlingsgrunnlag_saerlige_kategorier'),
				'navn_databehandler',
				('databehandleravtale_status', 'databehandleravtale_status_boolean'),
				'tjenesteleveranse_land',
				'sikre_dataminimalisering',
				'begrensning_tilgang',
				'informering_til_registrerte',
				'innsyn_egenkontroll',
				'rette_opplysninger',
				'programvarer',
			),
		}),
		('Ekstraopplysninger dersom DPIA er nødvendig', {
			'classes': ('collapse',),
			'fields': (
				'dpia_unnga_hoy_risiko',
				'dpia_dekker_formal',
				'dpia_effekt_enkelte',
				'dpia_effekt_samfunnet',
				'dpia_proporsjonalitet_enkelte_samfunnet',
				'forventet_bruk',
				'ny_endret_prosess',
				'antall_registrerte',
				'tilgang_opplysninger',
				'dpia_dba_ivaretakelse_sikkerhet',
				'dpia_prosess_godkjenne_underleverandor',
				'dpia_tidligere_bekymringer_risikoer',
				'dpia_tidligere_avdekket_sikkerhetsbrudd',
				'sikkerhetstiltak'
			),
		}),
		('Utfases', {
			'classes': ('collapse',),
			'fields': (
				'virksomhet_blacklist',
				'krav_sikkerhetsnivaa',
				('innhenting_ekstern_myndighet', 'innhenting_ekstern_myndighet_utdyping'),
				('utlevering_registrerte_samtykke', 'utlevering_registrerte_samtykke_utdyping'),
				'relasjon_registrerte',
				('valgfriget_registrerte', 'den_registrerte_sarbare_grupper'),
				'funksjonsomraade',
				'den_registrerte_hovedkateogi',
				('kommunens_maler', 'kommunens_maler_hvis_nei'),
				'frekvens_automatisert_innsamling',
				'frekvens_innsamling_manuelt',
			),
		}),
	)

	def save_model(self, request, obj, form, change):
		# vi ønsker å begrense tilgang til å opprette behandlinger for andre virksomheter
		if not request.user.is_superuser:
			obj.behandlingsansvarlig = request.user.profile.virksomhet  # uansett hva en ikke-superbruker gjør vil behandlingen knyttes til innlogget brukers virksomhet
		super().save_model(request, obj, form, change)

	def has_change_permission(self, request, obj=None):
		if obj:
			if request.user.is_superuser:
				return True
			if obj.behandlingsansvarlig == request.user.profile.virksomhet:
				if request.user.has_perm('systemoversikt.change_behandlingerpersonopplysninger'):
					return True
			else:
				messages.error(request, 'Du får ikke endre behandlinger for andre virksomheter')
				return False

	def has_delete_permission(self, request, obj=None):
		if obj:
			if request.user.is_superuser:
				return True
			if obj.behandlingsansvarlig == request.user.profile.virksomhet:
				if request.user.has_perm('systemoversikt.delete_behandlingerpersonopplysninger'):
					return True
			else:
				messages.error(request, 'Du får ikke slette behandlinger for andre virksomheter')
				return False



class BehandlingsgrunnlagAdmin(SimpleHistoryAdmin):
	list_display = ('grunnlag', 'lovparagraf', 'lov')

class PersonsonopplysningskategoriAdmin(SimpleHistoryAdmin):
	list_display = ('navn', 'artikkel', 'hovedkategori', 'eksempler')

class RegistrerteAdmin(SimpleHistoryAdmin):
	list_display = ('kategorinavn', 'definisjon')

class ProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'virksomhet')
	search_fields = ('user__username',)
	autocomplete_fields = ('user',)

class SystemUrlAdmin(SimpleHistoryAdmin):
	search_fields = ('domene',)
	list_display = ('domene', 'maalgruppe', 'registrar')
	list_filter = ('https', 'maalgruppe')
	autocomplete_fields = ('registrar', 'eier')

class SystemKategoriAdmin(SimpleHistoryAdmin):
	list_display = ('kategorinavn', 'definisjon')
	search_fields = ('kategorinavn', 'definisjon')
	list_filter = ('systemhovedkategori_systemkategorier',)

class SystemtypeAdmin(SimpleHistoryAdmin):
	search_fields = ('kategorinavn',)
	list_display = ('kategorinavn', 'definisjon')

class SystemHovedKategoriAdmin(SimpleHistoryAdmin):
	list_display = ('hovedkategorinavn', 'definisjon')
	search_fields = ('hovedkategorinavn', 'definisjon')
	filter_horizontal = ('subkategorier',)

class AnsvarligAdmin(SimpleHistoryAdmin):
	list_display = ('brukernavn', 'kommentar')
	search_fields = ('brukernavn__username', 'brukernavn__first_name', 'brukernavn__last_name')
	autocomplete_fields = ('brukernavn',)

	fieldsets = (

		('Initiell registrering', {
			'fields': (
				'brukernavn',
				'kommentar'
				)
			}
		),
		('Sertifikatadministrasjon', {
			'classes': ('collapse',),
			'fields': (
				'telefon',
				'fdato'
				)
			}
		),
	)

class ProgramvareAdmin(SimpleHistoryAdmin):
	list_display = ('programvarenavn', 'programvarebeskrivelse', 'kommentar')
	search_fields = ('programvarenavn', 'programvarebeskrivelse', 'kommentar')
	filter_horizontal = ('programvareleverandor', 'kategorier')

class UserAdmin(admin.ModelAdmin):
	list_display = ('username', 'first_name', 'last_name', 'is_active', 'is_staff', 'has_usable_password', 'accountdisable', 'intern_person', 'virksomhet', 'evigvarende_passord', 'password_expired')
	search_fields = ('username', 'first_name', 'last_name')
	list_filter = ('is_staff', 'is_superuser', 'is_active', 'profile__dont_expire_password', 'profile__password_expired', 'profile__ekstern_ressurs', 'profile__accountdisable', 'profile__virksomhet', 'groups',)

	def has_usable_password(self, obj):
		return obj.has_usable_password()
	has_usable_password.short_description = "Admin usable passord"
	has_usable_password.boolean = True

	def accountdisable(self, obj):
		# her inverterer vi med vilje, og setter enabled i stedet for disabled
		return not obj.profile.accountdisable
	accountdisable.short_description = "AD: Account enabled"
	accountdisable.boolean = True

	def virksomhet(self, obj):
		return obj.profile.virksomhet
	virksomhet.short_description = "Virksomhet"

	def intern_person(self, obj):
		return not obj.profile.ekstern_ressurs
	intern_person.short_description = "Intern ressurs"
	intern_person.boolean = True

	def password_expired(self, obj):
		return not obj.profile.password_expired
	password_expired.short_description = "Aktivt passord"
	password_expired.boolean = True

	def evigvarende_passord(self, obj):
		return not obj.profile.dont_expire_password
	evigvarende_passord.short_description = "Passordutløp"
	evigvarende_passord.boolean = True


class ProgramvareBrukAdmin(SimpleHistoryAdmin):
	list_display = ('brukergruppe', 'programvare', 'kommentar')
	search_fields = ('programvare', 'kommentar')
	autocomplete_fields = ('brukergruppe', 'programvare')
	filter_horizontal = ('programvareleverandor',)

"""
class TjenesteAdmin(SimpleHistoryAdmin):
	list_display = ('tjenestenavn', 'beskrivelse')
	search_fields = ('tjenestenavn', 'beskrivelse')
	filter_horizontal = ('systemer', 'tjenesteleder', 'tjenesteforvalter')
"""

class CMDBRefAdmin(admin.ModelAdmin):
	search_fields = ('navn',)
	list_display = ('navn', 'kritikalitet', 'cmdb_type')

class AvtaleAdmin(SimpleHistoryAdmin):
	list_display = ('kortnavn', 'avtaletype', 'virksomhet', 'leverandor', 'leverandor_intern', 'avtalereferanse', 'dokumenturl')
	search_fields = ('kortnavn', 'beskrivelse', 'avtalereferanse')
	autocomplete_fields = ('virksomhet', 'leverandor', 'intern_avtalereferanse', 'leverandor_intern')
	filter_horizontal = ('avtaleansvarlig', 'for_system',)

class DPIAAdmin(SimpleHistoryAdmin):
	list_display = ('for_system', 'sist_gjennomforing_dpia', 'url_dpia', 'kommentar',)
	search_fields = ('for_system',)

	fieldsets = (
		('Initiell registrering', {
			'fields': (
				'informasjon_kvalitetssikret',
				'for_system',
				'sist_gjennomforing_dpia',
				'url_dpia',
				'kommentar'
			),
		}),
		('Trinn 2: Beskriv prosessene', {
			'fields': (
				'knyttning_identifiserbare_personer',
				'innhentet_dpia',
				'teknologi',
				'ny_endret_teknologi',
				'kjente_problemer_teknologien',
			),
		}),
		('Trinn 3: Konsultasjon brukergrupper', {
			'fields': (
				('konsultasjon_registrerte', 'konsultasjon_registrerte_oppsummering'),
				('konsultasjon_internt', 'konsultasjon_internt_oppsummering'),
				('konsultasjon_databehandlere', 'konsultasjon_databehandlere_oppsummering'),
				('konsultasjon_eksterne', 'konsultasjon_eksterne_oppsummering')
			),
		}),
		('Trinn 4: Vurdering av nødvendighet og proporsjonalitet', {
			'fields': (
				'hoveddatabehandler',
			),
		}),

		('Trinn 5: Godkjenning', {
			'fields': (
				'personvern_i_risikovurdering',
			),
		}),
		('Trinn 6: Risikoreduserende tiltak', {
			'fields': (
				'tiltak_innledende_ros',
				'tiltak_etter_ytterligere_tiltak',
				'tiltak_forhandsdroftelser',
			),
		}),
		('Trinn 7: Godkjenning', {
			'fields': (
				'godkjenning_personvernombudets_raad',
				'godkjenning_tiltak_restrisiko',
				'godkjenning_datatilsynet',
			),
		}),
	)

class DriftsmodellAdmin(SimpleHistoryAdmin):
	list_display = ('navn', 'sikkerhetsnivaa', 'kommentar', 'ansvarlig_virksomhet')
	search_fields = ('navn',)
	filter_horizontal = ('lokasjon_lagring_valgmeny', 'leverandor', 'underleverandorer', 'avtaler', 'anbefalte_kategorier_personopplysninger')
	autocomplete_fields = ('ansvarlig_virksomhet',)

class AutorisertBestillerAdmin(SimpleHistoryAdmin):
	list_display = ('person', 'dato_fullmakt')
	autocomplete_fields = ('person',)
	search_fields = ('person',)

class CMDBdeviceAdmin(admin.ModelAdmin):
	search_fields = ('comp_name',)

class LoggkategoriAdmin(admin.ModelAdmin):
	search_fields = ('navn', 'definisjon')

class AutentiseringsmetodeAdmin(admin.ModelAdmin):
	search_fields = ('navn', 'definisjon')

class InformasjonsKlasseAdmin(admin.ModelAdmin):
	search_fields = ('navn', 'beskrivelse')


class DefinisjonAdmin(SimpleHistoryAdmin):
	list_display = ('begrep', 'status', 'ansvarlig',)
	autocomplete_fields = ('ansvarlig',)


class BehovForDPIAAdmin(SimpleHistoryAdmin):
	from django.forms.widgets import NullBooleanSelect
	formfield_overrides = {
		models.NullBooleanField: {'widget': NullBooleanSelect},
	}

# Register your models here.
admin.site.register(System, SystemAdmin)
admin.site.register(Virksomhet, VirksomhetAdmin)
admin.site.register(Leverandor, LeverandorAdmin)
admin.site.register(SystemBruk, SystemBrukAdmin)
admin.site.register(BehandlingerPersonopplysninger, BehandlingerPersonopplysningerAdmin)
admin.site.register(SystemKategori, SystemKategoriAdmin)
admin.site.register(SystemUrl, SystemUrlAdmin)
admin.site.register(Personsonopplysningskategori, PersonsonopplysningskategoriAdmin)
admin.site.register(Registrerte, RegistrerteAdmin)
admin.site.register(Behandlingsgrunnlag, BehandlingsgrunnlagAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(Systemtype, SystemtypeAdmin)
admin.site.register(SystemHovedKategori, SystemHovedKategoriAdmin)
admin.site.register(Ansvarlig, AnsvarligAdmin)
admin.site.register(Programvare, ProgramvareAdmin)
admin.site.register(ProgramvareBruk, ProgramvareBrukAdmin)
#admin.site.register(Tjeneste, TjenesteAdmin)
admin.site.register(CMDBRef, CMDBRefAdmin)
admin.site.register(Avtale, AvtaleAdmin)
admin.site.register(DPIA, DPIAAdmin)
admin.site.register(Driftsmodell, DriftsmodellAdmin)
admin.site.register(AutorisertBestiller, AutorisertBestillerAdmin)
admin.site.register(Autentiseringsmetode,AutentiseringsmetodeAdmin)
admin.site.register(Region)
admin.site.register(RegistrertKlassifisering)
admin.site.register(Definisjon, DefinisjonAdmin)
admin.site.register(RelasjonRegistrert)
admin.site.register(CMDBdevice, CMDBdeviceAdmin)
admin.site.register(InformasjonsKlasse, InformasjonsKlasseAdmin)
admin.site.register(Loggkategori,LoggkategoriAdmin)
admin.site.register(ApplicationLog)
admin.site.register(Sikkerhetstester, SikkerhetstesterAdmin)
admin.site.register(DefinisjonKontekster)
admin.site.register(CMDBdatabase)
admin.site.register(BehovForDPIA, BehovForDPIAAdmin)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)


'''
Mulighet til å se alle logger i django adminpanelet
https://djangosnippets.org/snippets/3009/
'''
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.utils.html import escape
#from django.core.urlresolvers import reverse, NoReverseMatch #  Har endret lokasjon
from django.urls import reverse, NoReverseMatch
from django.contrib.auth.models import User

action_names = {
	ADDITION: 'Ny',
	CHANGE:   'Endret',
	DELETION: 'Slettet',
}

class FilterBase(admin.SimpleListFilter):
	def queryset(self, request, queryset):
		if self.value():
			dictionary = dict(((self.parameter_name, self.value()),))
			return queryset.filter(**dictionary)

class ActionFilter(FilterBase):
	title = 'action'
	parameter_name = 'action_flag'
	def lookups(self, request, model_admin):
		return action_names.items()


class UserFilter(FilterBase):
	"""Use this filter to only show current users, who appear in the log."""
	title = 'user'
	parameter_name = 'user_id'
	def lookups(self, request, model_admin):
		return tuple((u.id, u.username)
			for u in User.objects.filter(pk__in =
				LogEntry.objects.values_list('user_id').distinct())
		)

class AdminFilter(UserFilter):
	"""Use this filter to only show current Superusers."""
	title = 'admin'
	def lookups(self, request, model_admin):
		return tuple((u.id, u.username) for u in User.objects.filter(is_superuser=True))

class StaffFilter(UserFilter):
	"""Use this filter to only show current Staff members."""
	title = 'staff'
	def lookups(self, request, model_admin):
		return tuple((u.id, u.username) for u in User.objects.filter(is_staff=True))


class LogEntryAdmin(admin.ModelAdmin):

	date_hierarchy = 'action_time'


	#readonly_fields = LogEntry._meta.get_all_field_names() virker ikke
	readonly_fields = [f.name for f in LogEntry._meta.get_fields()]

	list_filter = [
		UserFilter,
		ActionFilter,
		'content_type',
		# 'user',
	]

	search_fields = [
		'object_repr',
		'change_message'
	]


	list_display = [
		'action_time',
		'user',
		'content_type',
		'object_link',
		'action_flag',
		'action_description',
		'change_message',
	]

	def has_add_permission(self, request):
		return False

	def has_change_permission(self, request, obj=None):
		return request.user.is_superuser and request.method != 'POST'

	def has_delete_permission(self, request, obj=None):
		return False

	def object_link(self, obj):
		ct = obj.content_type
		repr_ = escape(obj.object_repr)
		try:
			href = reverse('admin:%s_%s_change' % (ct.app_label, ct.model), args=[obj.object_id])
			link = u'<a href="%s">%s</a>' % (href, repr_)
		except NoReverseMatch:
			link = repr_
		return link if obj.action_flag != DELETION else repr_
	object_link.allow_tags = True
	object_link.admin_order_field = 'object_repr'
	object_link.short_description = u'object'

	def queryset(self, request):
		return super(LogEntryAdmin, self).queryset(request) \
			.prefetch_related('content_type')

	def action_description(self, obj):
		return action_names[obj.action_flag]
	action_description.short_description = 'Action'


admin.site.register(LogEntry, LogEntryAdmin)