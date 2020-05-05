# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import models
from django.contrib import messages
from django.shortcuts import redirect
from simple_history.admin import SimpleHistoryAdmin
from django.db.models.functions import Lower
from django.utils.html import escape
from django.urls import reverse, NoReverseMatch
import csv
from django.http import HttpResponse
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.auth.models import User
from .models import *


# https://gist.github.com/jeremyjbowers/e8d007446155c12033e6
def export_as_csv_action(description="Export selected objects as CSV file", fields=None, exclude=None, header=True):
	"""
	This function returns an export csv action
	'fields' and 'exclude' work like in django ModelForm
	'header' is whether or not to output the column names as the first row
	"""
	def export_as_csv(modeladmin, request, queryset):
		"""
		Generic csv export admin action.
		based on http://djangosnippets.org/snippets/1697/
		"""
		opts = modeladmin.model._meta
		field_names = set([field.name for field in opts.fields])

		if fields:
			fieldset = set(fields)
			field_names = field_names & fieldset

		elif exclude:
			excludeset = set(exclude)
			field_names = field_names - excludeset

		response = HttpResponse(content_type='text/csv')
		response['Content-Disposition'] = 'attachment; filename=%s.csv' % str(opts).replace('.', '_')

		writer = csv.writer(response)

		if header:
			writer.writerow(list(field_names))
		for obj in queryset:
			writer.writerow([str(getattr(obj, field)).encode("utf-8","replace") for field in field_names])

		return response

	export_as_csv.short_description = description
	return export_as_csv


@admin.register(UserChangeLog)
class UserChangeLogAdmin(admin.ModelAdmin):
	list_display = ('event_type', 'message', 'opprettet',)
	search_fields = ('message',)
	list_filter = ('opprettet',)


@admin.register(Database)
class DatabaseAdmin(admin.ModelAdmin):
	list_display = ('navn',)
	search_fields = ('navn',)

	def get_ordering(self, request):
		return [Lower('navn')]


@admin.register(HRorg)
class HRorgAdmin(admin.ModelAdmin):
	list_display = ('ou', 'level', 'leder', 'virksomhet_mor', 'direkte_mor')
	search_fields = ('ou',)
	autocomplete_fields = ('leder', 'virksomhet_mor', 'direkte_mor')
	list_filter = ('active', 'opprettet', 'virksomhet_mor')


@admin.register(Klientutstyr)
class KlientutstyrAdmin(admin.ModelAdmin):
	list_display = ('maskinadm_wsnummer', 'maskinadm_virksomhet', 'maskinadm_virksomhet_str', 'maskinadm_klienttype', 'maskinadm_sone', 'maskinadm_servicenivaa', 'maskinadm_sist_oppdatert')
	search_fields = ('maskinadm_wsnummer',)
	list_filter = ('maskinadm_servicenivaa', 'maskinadm_sone', 'maskinadm_klienttype', 'maskinadm_virksomhet', 'maskinadm_sist_oppdatert')


@admin.register(Sikkerhetstester)
class SikkerhetstesterAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('testet_av', 'dato_rapport', 'type_test', 'rapport', 'notater')
	autocomplete_fields = ('systemer', 'testet_av')
	list_filter = ('dato_rapport',)

@admin.register(Autorisasjonsmetode)
class AutorisasjonsmetodeAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('navn', 'definisjon')
	search_fields = ('navn',)

	def get_ordering(self, request):
		return [Lower('navn')]


@admin.register(System)
class SystemAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('systemnavn', 'alias', 'ibruk', 'systemeierskapsmodell', 'livslop_status', 'systemeier', 'systemforvalter', 'driftsmodell_foreignkey')
	search_fields = ('systemnavn', 'systembeskrivelse')
	list_filter = ('database_in_use', 'database_supported', 'ibruk', 'systemeier', 'systemforvalter', 'sikkerhetsnivaa', 'systemtyper', 'livslop_status', 'driftsmodell_foreignkey', 'systemeierskapsmodell', 'strategisk_egnethet', 'funksjonell_egnethet', 'teknisk_egnethet', 'isolert_drift')

	def response_add(self, request, obj, post_url_continue=None):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('systemdetaljer', kwargs={'pk': obj.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('systemdetaljer', kwargs={'pk': obj.pk}))
		return super().response_change(request, obj)

	def get_ordering(self, request):
		return [Lower('systemnavn')]

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
		'cmdbref',
		'systemtyper',
		'loggingalternativer',
		'autentiseringsteknologi',
		'autentiseringsalternativer',
		'autorisasjonsalternativer',
		'informasjonsklassifisering',
		'database_supported',
		'database_in_use',
	)
	fieldsets = (
		('Initiell registrering', {
			'description': 'Dette er felter ansett som obligatoriske, og kreves utfylt for å kunne krysse av for at informasjonen er kvalitetssikret..',
			'fields': (
				'ibruk',
				'informasjon_kvalitetssikret',
				('systemnavn', 'alias'),
				'systembeskrivelse',
				'systemtyper',
				'systemeierskapsmodell',
				'systemeier', 
				'systemeier_kontaktpersoner_referanse',
				('systemforvalter', 'systemforvalter_kontaktpersoner_referanse'),
				('autentiseringsteknologi', 'autentiseringsalternativer'),
				'autorisasjonsalternativer',
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
				#'cmdbref_prod',
				'cmdbref',
				'brukerdokumentasjon_url',
				'high_level_design_url',
				'low_level_design_url',
				'programvarer',
				'database_in_use',
				'database_supported',
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


@admin.register(Virksomhet)
class VirksomhetAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('virksomhetsforkortelse', 'virksomhetsnavn', 'resultatenhet', 'kan_representeres', 'ordinar_virksomhet', 'orgnummer')
	search_fields = ('virksomhetsnavn', 'virksomhetsforkortelse')
	list_filter = ('resultatenhet', 'ordinar_virksomhet')

	readonly_fields = ["odepartmentnumber"]

	filter_horizontal = ('overordnede_virksomheter',)

	def get_ordering(self, request):
		return [Lower('virksomhetsnavn')]

	def response_add(self, request, obj, post_url_continue=None):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('virksomhet', kwargs={'pk': obj.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('virksomhet', kwargs={'pk': obj.pk}))
		return super().response_change(request, obj)

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
					'odepartmentnumber',
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


@admin.register(SystemBruk)
class SystemBrukAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('system', 'brukergruppe', 'kommentar', 'avtaletype', 'systemeierskap', 'kostnadersystem')
	search_fields = ('system__systemnavn', 'system__systembeskrivelse', 'kommentar', 'systemforvalter')
	list_filter = ('avtalestatus', 'avtale_kan_avropes', 'systemeierskapsmodell', 'brukergruppe')
	autocomplete_fields = ('brukergruppe', 'system', 'systemforvalter', 'systemforvalter_kontaktpersoner_referanse', 'avhengigheter_referanser')
	
	def response_add(self, request, obj, post_url_continue=None):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('all_bruk_for_virksomhet', kwargs={'pk': obj.brukergruppe.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('all_bruk_for_virksomhet', kwargs={'pk': obj.brukergruppe.pk}))
		return super().response_change(request, obj)


	fieldsets = (
		('Initiell registrering', {
			'fields': (
				'brukergruppe',
				'system',
				'systemforvalter_kontaktpersoner_referanse',
				'del_behandlinger',
				'dato_sist_ros',
				'url_risikovurdering',
				'risikovurdering_tekst',
				'kommentar',

			),
		}),
		('Vurderinger', {
			'fields': (
				'strategisk_egnethet',
				'funksjonell_egnethet',
				'teknisk_egnethet',
				'konfidensialitetsvurdering',
				'integritetsvurdering',
				'tilgjengelighetsvurdering',
			),
		}),
		('Avvikles', {
			'classes': ('collapse',),
			'fields': (
				'avtaletype',
				'avtalestatus',
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


@admin.register(PRKvalg)
class PRKvalgAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('skjemanavn', 'gruppering', 'valgnavn', 'virksomhet', 'in_active_directory', 'beskrivelse', 'sist_oppdatert')
	search_fields = ('skjemanavn__skjemanavn', 'gruppenavn',)
	list_filter = ('sist_oppdatert', 'in_active_directory')
	autocomplete_fields = ('ad_group_ref',)


@admin.register(PRKgruppe)
class PRKgruppeAdmin(admin.ModelAdmin):
	list_display = ('feltnavn', 'sist_oppdatert', 'opprettet')
	search_fields = ('feltnavn',)
	list_filter = ('sist_oppdatert', 'opprettet')


@admin.register(PRKskjema)
class PRKskjemaAdmin(admin.ModelAdmin):
	list_display = ('skjemanavn', 'skjematype', 'sist_oppdatert', 'opprettet')
	search_fields = ('skjemanavn',)
	list_filter = ('sist_oppdatert', 'opprettet')


@admin.register(Leverandor)
class LeverandorAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('leverandor_navn', 'kontaktpersoner', 'orgnummer')
	search_fields = ('leverandor_navn', 'orgnummer', 'notater')

	def get_ordering(self, request):
		return [Lower('leverandor_navn')]


@admin.register(BehandlingerPersonopplysninger)
class BehandlingerPersonopplysningerAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('behandlingsansvarlig', 'internt_ansvarlig', 'funksjonsomraade', 'behandlingen')
	search_fields = ('behandlingen', 'internt_ansvarlig', 'funksjonsomraade',)
	list_filter = ('behandlingsgrunnlag_valg', 'den_registrerte', 'kategorier_personopplysninger', 'behandlingsansvarlig')
	filter_horizontal = ('relasjon_registrerte', 'den_registrerte_hovedkateogi', 'virksomhet_blacklist', 'programvarer', 'systemer', 'navn_databehandler', 'kategorier_personopplysninger', 'den_registrerte', 'behandlingsgrunnlag_valg')
	autocomplete_fields = ('behandlingsansvarlig', 'oppdateringsansvarlig')

	def response_add(self, request, obj, post_url_continue=None):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('behandlingsdetaljer', kwargs={'pk': obj.brukergruppe.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('behandlingsdetaljer', kwargs={'pk': obj.brukergruppe.pk}))
		return super().response_change(request, obj)

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
				'ekstern_DPIA_url',
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


@admin.register(Behandlingsgrunnlag)
class BehandlingsgrunnlagAdmin(SimpleHistoryAdmin):
	list_display = ('grunnlag', 'lovparagraf', 'lov')

	def get_ordering(self, request):
		return [Lower('grunnlag')]


@admin.register(Personsonopplysningskategori)
class PersonsonopplysningskategoriAdmin(SimpleHistoryAdmin):
	list_display = ('navn', 'artikkel', 'hovedkategori', 'eksempler')

	def get_ordering(self, request):
		return [Lower('navn')]


@admin.register(Registrerte)
class RegistrerteAdmin(SimpleHistoryAdmin):
	list_display = ('kategorinavn', 'definisjon')

	def get_ordering(self, request):
		return [Lower('kategorinavn')]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'virksomhet', 'usertype', 'from_prk')
	search_fields = ('user__username',)
	autocomplete_fields = ('user', 'ou', 'virksomhet', 'virksomhet_innlogget_som')
	list_filter = ('usertype', 'from_prk')


@admin.register(SystemUrl)
class SystemUrlAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('domene', 'eier', 'opprettet', 'https', 'vurdering_sikkerhetstest', 'maalgruppe', 'registrar')
	search_fields = ('domene',)
	list_filter = ('https', 'maalgruppe', 'opprettet', 'eier')
	autocomplete_fields = ('registrar', 'eier')

	def get_ordering(self, request):
		return [Lower('domene')]


@admin.register(SystemKategori)
class SystemKategoriAdmin(SimpleHistoryAdmin):
	list_display = ('kategorinavn', 'definisjon')
	search_fields = ('kategorinavn', 'definisjon')
	list_filter = ('systemhovedkategori_systemkategorier',)

	def get_ordering(self, request):
		return [Lower('kategorinavn')]


@admin.register(Systemtype)
class SystemtypeAdmin(SimpleHistoryAdmin):
	search_fields = ('kategorinavn',)
	list_display = ('kategorinavn', 'definisjon')

	def get_ordering(self, request):
		return [Lower('kategorinavn')]


@admin.register(SystemHovedKategori)
class SystemHovedKategoriAdmin(SimpleHistoryAdmin):
	list_display = ('hovedkategorinavn', 'definisjon')
	search_fields = ('hovedkategorinavn', 'definisjon', 'subkategorier')

	def get_ordering(self, request):
		return [Lower('hovedkategorinavn')]


@admin.register(Ansvarlig)
class AnsvarligAdmin(SimpleHistoryAdmin):
	list_display = ('brukernavn', 'brukers_brukernavn', 'kommentar')
	search_fields = ('brukernavn__username', 'brukernavn__first_name', 'brukernavn__last_name')
	autocomplete_fields = ('brukernavn',)

	def response_add(self, request, obj, post_url_continue=None):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('ansvarlig', kwargs={'pk': obj.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('ansvarlig', kwargs={'pk': obj.pk}))
		return super().response_change(request, obj)

	def get_ordering(self, request):
		return [Lower('brukernavn')]

	def brukers_brukernavn(self, obj):
		return obj.brukernavn.username
	brukers_brukernavn.short_description = "Brukernavn"

	def brukers_navn(self, obj):
		return obj.brukernavn
	brukers_brukernavn.short_description = "Brukernavn"

	fieldsets = (
		('Obligatorisk', {
			'fields': (
				'brukernavn',
				'vil_motta_epost_varsler',
				)
			}
		),
		('Fylles ut dersom rollen har fullmakt knyttet til sertifikatadministrasjon', {
			'classes': ('collapse',),
			'fields': (
				'telefon',
				'fdato',
				)
			}
		),
		('Utfases', {
			'classes': ('collapse',),
			'fields': (
				'kommentar',
				)
			}
		),
	)


@admin.register(Programvare)
class ProgramvareAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('programvarenavn', 'programvarebeskrivelse', 'kommentar')
	search_fields = ('programvarenavn', 'programvarebeskrivelse', 'kommentar')
	filter_horizontal = ('programvareleverandor', 'kategorier')

	def get_ordering(self, request):
		return [Lower('programvarenavn')]


admin.site.unregister(User)  # den er som standard registrert
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	list_display = ('username', 'last_login', 'userPasswordExpiry', 'first_name', 'last_name', 'from_prk', 'is_active', 'is_staff', 'has_usable_password', 'accountdisable', 'intern_person', 'virksomhet', 'evigvarende_passord', 'password_expired')
	search_fields = ('last_login', 'username', 'first_name', 'last_name')
	list_filter = ('profile__from_prk', 'profile__userPasswordExpiry', 'profile__virksomhet', 'is_staff', 'is_superuser', 'is_active', 'profile__dont_expire_password', 'profile__password_expired', 'profile__ekstern_ressurs', 'profile__accountdisable', 'groups',)

	def has_usable_password(self, obj):
		return obj.has_usable_password()
	has_usable_password.short_description = "Admin usable passord"
	has_usable_password.boolean = True

	def accountdisable(self, obj):
		# her inverterer vi med vilje, og setter enabled i stedet for disabled
		return not obj.profile.accountdisable
	accountdisable.short_description = "AD: Account enabled"
	accountdisable.boolean = True

	def userPasswordExpiry(self, obj):
		return obj.profile.userPasswordExpiry
	userPasswordExpiry.short_description = "Passord utløper"

	def virksomhet(self, obj):
		return obj.profile.virksomhet
	virksomhet.short_description = "Virksomhet"

	def from_prk(self, obj):
		return obj.profile.from_prk
	from_prk.short_description = "Fra PRK?"
	from_prk.boolean = True

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


@admin.register(ProgramvareBruk)
class ProgramvareBrukAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('brukergruppe', 'programvare', 'kommentar')
	search_fields = ('programvare', 'kommentar')
	autocomplete_fields = ('brukergruppe', 'programvare', 'programvareleverandor', 'lokal_kontakt')

	def response_add(self, request, obj, post_url_continue=None):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('all_programvarebruk_for_virksomhet', kwargs={'pk': obj.brukergruppe.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('all_programvarebruk_for_virksomhet', kwargs={'pk': obj.brukergruppe.pk}))
		return super().response_change(request, obj)

	fieldsets = (
			('Initiell registrering', {
				'fields': (
					'brukergruppe',
					'programvare',
					'lokal_kontakt',
					'kommentar',
					'strategisk_egnethet',
					'funksjonell_egnethet',
					'teknisk_egnethet',
				),
			}),
			('Diverse', {
				'classes': ('collapse',),
				'fields': (
					'livslop_status',
					'programvareeierskap',
					'antall_brukere',
					'avtaletype',
					'avtalestatus',
					'avtale_kan_avropes',
					'borger',
					'kostnader',
					'programvareleverandor',
				),
			}),
	)


@admin.register(CMDBRef)
class CMDBRefAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('navn', 'environment', 'kritikalitet', 'operational_status', 'service_classification', 'opprettet')
	search_fields = ('navn',)
	list_filter = ('environment', 'kritikalitet', 'operational_status', 'service_classification', 'opprettet')

	def get_ordering(self, request):
		return [Lower('navn')]


@admin.register(Avtale)
class AvtaleAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('kortnavn', 'avtaletype', 'virksomhet', 'leverandor', 'leverandor_intern', 'avtalereferanse', 'dokumenturl')
	search_fields = ('kortnavn', 'beskrivelse', 'avtalereferanse')
	autocomplete_fields = ('virksomhet', 'leverandor', 'intern_avtalereferanse', 'leverandor_intern')
	filter_horizontal = ('avtaleansvarlig', 'for_system',)

	def response_add(self, request, obj, post_url_continue=None):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('avtalervirksomhet', kwargs={'virksomhet': obj.virksomhet.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if ('_addanother' not in request.POST) and ('_continue' not in request.POST):
			return redirect(reverse('avtalervirksomhet', kwargs={'virksomhet': obj.virksomhet.pk}))
		return super().response_change(request, obj)

	def get_ordering(self, request):
		return [Lower('kortnavn')]

	fieldsets = (
				('Avtaleparter', {
					'fields': (
						'virksomhet',
						('leverandor', 'leverandor_intern'),
					),
				}),
				('Om avtalen', {
					'fields': (
						'avtaletype',
						'kortnavn',
						'beskrivelse',
						'avtaleansvarlig',
						'for_system',
						'avtalereferanse',
						'dokumenturl',
						'intern_avtalereferanse',
					),
				}),
		)


@admin.register(DPIA)
class DPIAAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
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


@admin.register(Driftsmodell)
class DriftsmodellAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
	list_display = ('navn', 'sikkerhetsnivaa', 'kommentar', 'ansvarlig_virksomhet', 'type_plattform')
	search_fields = ('navn',)
	filter_horizontal = ('lokasjon_lagring_valgmeny', 'leverandor', 'underleverandorer', 'avtaler', 'anbefalte_kategorier_personopplysninger', 'overordnet_plattform')
	autocomplete_fields = ('ansvarlig_virksomhet',)

	def get_ordering(self, request):
		return [Lower('navn')]

	fieldsets = (
			('Initiell registrering', {
				'fields': (
					'navn',
					'ansvarlig_virksomhet',
					'type_plattform',
					'overordnet_plattform',
					'risikovurdering',
					'kommentar',
					'leverandor',
					'underleverandorer',
					'avtaler'
				),
			}),
			('Sikkerhetsegenskaper', {
				'fields': (
					'sikkerhetsnivaa',
					'anbefalte_kategorier_personopplysninger',
					'databehandleravtale_notater',
					'lokasjon_lagring_valgmeny',
					'lokasjon_lagring',
					'Tilgangsstyring_driftspersonell',
					'nettverk_segmentering',
					'nettverk_sammenkobling_fip',
					'sikkerhet_patching',
					'sikkerhet_antiskadevare',
					'sikkerhet_backup',
					'sikkerhet_logging',
					'sikkerhet_fysisk_sikring',
				),
			}),
	)


@admin.register(ADOrgUnit)
class ADOrgUnitAdmin(admin.ModelAdmin):
	list_display = ('ou', 'when_created', 'distinguishedname',)
	search_fields = ('distinguishedname',)
	#list_filter = ()


@admin.register(ADgroup)
class ADgroupAdmin(admin.ModelAdmin):
	list_display = ('distinguishedname', 'from_prk', 'membercount', 'memberofcount', 'description', 'sist_oppdatert')
	search_fields = ('distinguishedname',)
	list_filter = ('from_prk', 'opprettet', 'sist_oppdatert')


@admin.register(AutorisertBestiller)
class AutorisertBestillerAdmin(SimpleHistoryAdmin):
	list_display = ('person', 'dato_fullmakt')
	autocomplete_fields = ('person',)
	search_fields = ('person',)


@admin.register(CMDBdevice)
class CMDBdeviceAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Export")]
	search_fields = ('comp_name',)


@admin.register(Loggkategori)
class LoggkategoriAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Export")]
	search_fields = ('navn', 'definisjon')



@admin.register(Autentiseringsteknologi)
class AutentiseringsteknologiAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Export")]
	search_fields = ('navn', 'definisjon')

	def get_ordering(self, request):
		return [Lower('navn')]


@admin.register(Autentiseringsmetode)
class AutentiseringsmetodeAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Export")]
	search_fields = ('navn', 'definisjon')

	def get_ordering(self, request):
		return [Lower('navn')]


@admin.register(InformasjonsKlasse)
class InformasjonsKlasseAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Export")]
	search_fields = ('navn', 'beskrivelse')

	def get_ordering(self, request):
		return [Lower('navn')]


@admin.register(Definisjon)
class DefinisjonAdmin(SimpleHistoryAdmin):
	list_display = ('begrep', 'status', 'ansvarlig',)
	actions = [export_as_csv_action("CSV Export")]
	autocomplete_fields = ('ansvarlig',)

	def get_ordering(self, request):
		return [Lower('begrep')]


@admin.register(BehovForDPIA)
class BehovForDPIAAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Export")]
	from django.forms.widgets import NullBooleanSelect
	formfield_overrides = {
		models.NullBooleanField: {'widget': NullBooleanSelect},
	}


admin.site.register(Region)


admin.site.register(RegistrertKlassifisering)


admin.site.register(RelasjonRegistrert)


@admin.register(ApplicationLog)
class ApplicationLogAdmin(admin.ModelAdmin):
	list_display = ('event_type', 'message', 'opprettet')
	search_fields = ('event_type', 'message')
	list_filter = ('opprettet',)


admin.site.register(DefinisjonKontekster)


@admin.register(CMDBdatabase)
class CMDBdatabaseAdmin(admin.ModelAdmin):
	list_display = ('db_database', 'db_version', 'db_used_for', 'db_operational_status')
	search_fields = ('db_database',)
	list_filter = ('opprettet', 'db_operational_status', 'db_version')


''' Visning av  logger i django adminpanelet
https://djangosnippets.org/snippets/3009/ '''
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


@admin.register(LogEntry)
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


@admin.register(UBWRapporteringsenhet)
class UBWRapporteringsenhetAdmin(admin.ModelAdmin):
	list_display = ('name',)
	search_fields = ('name',)
	#list_filter = ('users',)
	autocomplete_fields = ('users',)

@admin.register(UBWFakturaKategori)
class UBWFakturaKategoriAdmin(admin.ModelAdmin):
	list_display = ('name', 'belongs_to',)
	search_fields = ('name',)
	list_filter = ('belongs_to',)

@admin.register(UBWMetode)
class UBWMetodeAdmin(admin.ModelAdmin):
	list_display = ('name', 'belongs_to',)
	search_fields = ('name',)
	list_filter = ('belongs_to',)

@admin.register(UBWFaktura)
class UBWFakturaAdmin(admin.ModelAdmin):
	list_display = ('belongs_to', 'ubw_amount', 'ubw_xaccount', 'ubw_period', 'ubw_xdim_1', 'ubw_xdim_4', 'ubw_voucher_date', 'ubw_xapar_id', 'ubw_description')
	search_fields = ('event_type', 'message')
	list_filter = ('ubw_account', 'ubw_dim_1', 'ubw_dim_4', 'ubw_apar_id')

@admin.register(UBWMetadata)
class UBWMetadataAdmin(admin.ModelAdmin):
	list_display = ('belongs_to', 'periode_paalopt', 'kategori')
	#search_fields = ('',)
	#list_filter = ('',)

@admin.register(UBWEstimat)
class UBWEstimatAdmin(admin.ModelAdmin):
	list_display = ('belongs_to', 'aktiv', 'prognose_kategori', 'estimat_account', 'estimat_dim_1', 'estimat_dim_4', 'estimat_amount', 'periode_paalopt')

