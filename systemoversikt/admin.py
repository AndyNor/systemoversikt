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
from django.db.models import Q
from django.http import HttpResponse
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from .models import *

def is_admin(request):
	return request.user.groups.filter(name="/DS-SYSTEMOVERSIKT_ADMINISTRATOR_ADMINISTRATOR").exists()


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
		response.write(u'\ufeff'.encode('utf8'))

		writer = csv.writer(response, quoting=csv.QUOTE_ALL)

		if header:
			writer.writerow(list(field_names))
		for obj in queryset:
			data = [str(getattr(obj, field)) for field in field_names]
			cleaned_data = []
			for value in data:
				if type(value) == str:
					value = value.replace("\r\n", " ").replace("\n", " ")
				cleaned_data.append(value)
			writer.writerow(cleaned_data)

		return response

	export_as_csv.short_description = description
	return export_as_csv


@admin.register(QualysVuln)
class QualysVulnAdmin(admin.ModelAdmin):
	list_display=('source', 'server', 'title', 'status', 'severity', 'first_seen', 'last_seen', 'public_facing', 'cve_info', 'result', 'os')
	search_fields = ('cve_info', 'title', 'source')
	list_filter = ('severity', 'os', 'status', 'public_facing', 'first_seen')
	autocomplete_fields = ('server',)
	def has_change_permission(self, request, obj=None):
		return False


@admin.register(IpProtocol)
class IpProtocolAdmin(admin.ModelAdmin):
	list_display=search_fields=readonly_fields = ('protocol', 'port', 'description')


@admin.register(AzureUserConsents)
class AzureUserConsentsAdmin(admin.ModelAdmin):
	list_display=search_fields=readonly_fields = ('appId', 'appDisplayName', 'userId', 'userDisplayName', 'scopes')


@admin.register(AzureApplicationKeys)
class AzureApplicationKeysAdmin(admin.ModelAdmin):
	list_display = ('applcaion_ref', 'key_id', 'display_name', 'key_type', 'key_usage', 'end_date_time')
	search_fields = ('key_id', 'display_name',)
	list_filter = ('key_type', 'key_usage', 'applcaion_ref')
	autocomplete_fields = ('applcaion_ref',)
	readonly_fields = ["key_id",]


@admin.register(AzureNamedLocations)
class AzureNamedLocationsAdmin(admin.ModelAdmin):
	list_display = ('active', 'displayName', 'sist_endret', 'isTrusted', 'ipRanges', 'countriesAndRegions', 'ipNamedLocation_id',)
	search_fields = ('displayName',)
	readonly_fields = ['displayName', 'isTrusted', 'ipRanges', 'countriesAndRegions', 'ipNamedLocation_id', 'active', 'sist_endret',]




@admin.register(CitrixPublication)
class CitrixPublicationAdmin(admin.ModelAdmin):
	list_display = ('publikasjon_UUID', 'sone', 'publikasjon_active',)
	search_fields = ('publikasjon_UUID', 'publikasjon_json')
	list_filter = ('publikasjon_active', 'sone', 'type_vApp', 'type_nettleser', 'type_remotedesktop', 'type_produksjon', 'type_medlemmer')
	readonly_fields = ['publikasjon_UUID', 'sone', 'publikasjon_active', 'publikasjon_json', 'type_vApp', 'type_nettleser', 'type_remotedesktop', 'type_produksjon', 'type_medlemmer']


@admin.register(AzureApplication)
class AzureApplicationAdmin(admin.ModelAdmin):
	list_display = ('displayName', 'risikonivaa', 'createdDateTime', 'appId', 'sist_oppdatert',)
	search_fields = ('displayName', 'appId',)
	list_filter = ('risikonivaa',)
	autocomplete_fields = ('requiredResourceAccess',)
	readonly_fields = ["appId",]

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('azure_applications', kwargs={}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('azure_applications', kwargs={}))
		return super().response_change(request, obj)

@admin.register(AzurePublishedPermissionScopes)
class AzurePublishedPermissionScopesAdmin(admin.ModelAdmin):
	list_display = ('value', 'permission_type', 'resourceAppStr', 'isEnabled', 'sist_oppdatert', 'grant_type', 'adminConsentDisplayName', 'scope_id')
	search_fields = ('value', 'scope_id', 'resourceAppId', 'resourceAppStr')
	list_filter = ('grant_type', 'isEnabled',)


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


@admin.register(NyeFunksjoner)
class NyeFunksjonerAdmin(admin.ModelAdmin):
	list_display = ('beskrivelse', 'tidspunkt', 'reverse_url',)


@admin.register(LOS)
class LOSAdmin(admin.ModelAdmin):
	list_display = ('verdi', 'unik_id', 'kategori_ref', 'active',)
	search_fields = ('verdi', 'parent_id__verdi',)
	autocomplete_fields = ('kategori_ref', 'parent_id', 'buffer_alle_tema',)
	list_filter = ('active',)

	def get_queryset(self, request):
		qs = super().get_queryset(request)
		return qs.filter(~Q(parent_id=None)) # ønsker ikke hovedtema. Hovedtema har ikke noen parent.

"""
@admin.register(Klientutstyr)
class KlientutstyrAdmin(admin.ModelAdmin):
	list_display = ('maskinadm_wsnummer', 'maskinadm_virksomhet', 'maskinadm_virksomhet_str', 'maskinadm_klienttype', 'maskinadm_sone', 'maskinadm_servicenivaa', 'maskinadm_sist_oppdatert')
	search_fields = ('maskinadm_wsnummer',)
	list_filter = ('maskinadm_servicenivaa', 'maskinadm_sone', 'maskinadm_klienttype', 'maskinadm_virksomhet', 'maskinadm_sist_oppdatert')
"""

@admin.register(virtualIP)
class virtualIPAdmin(admin.ModelAdmin):
	list_display = ('vip_name', 'pool_name', 'ip_address', 'port', 'hitcount',)
	search_fields = ('vip_name', 'pool_name', 'ip_address',)
	list_filter = ('port', )


@admin.register(VirtualIPPool)
class VirtualIPPoolAdmin(admin.ModelAdmin):
	list_display = ('pool_name', 'ip_address', 'port', 'server')
	search_fields = ('pool_name', 'ip_address',)
	list_filter = ('port', 'vip',)
	autocomplete_fields = ('vip', 'server',)


@admin.register(NetworkContainer)
class NetworkContainerAdmin(admin.ModelAdmin):
	list_display = ('ip_address', 'subnet_mask', 'disabled', 'network_zone', 'network_zone_description', 'comment', 'locationid', 'orgname', 'vlanid', 'vrfname', 'netcategory')
	search_fields = ('ip_address', 'comment', 'orgname', 'locationid', )
	list_filter = ('disabled', 'netcategory', 'network_zone',)


@admin.register(NetworkIPAddress)
class NetworkIPAddressAdmin(admin.ModelAdmin):
	list_display = ('ip_address', 'ip_address_integer', 'ant_servere', 'ant_dns', 'ant_vlan', 'ant_viper', 'ant_pools')
	search_fields = ('ip_address',)
	autocomplete_fields = ('servere', 'viper', 'dns', 'vlan', 'vip_pools',)



@admin.register(DNSrecord)
class DNSrecordAdmin(admin.ModelAdmin):
	list_display = ('sist_oppdatert', 'dns_name', 'dns_type', 'dns_domain', 'ip_address', 'dns_target', 'ttl',)
	search_fields = ('dns_name', 'ip_address', 'dns_target',)
	list_filter = ('dns_type', 'sist_oppdatert',)



from django.contrib.admin import SimpleListFilter
from django.db.models import Q
class SystemList(SimpleListFilter):
	title = "System"
	parameter_name = "systemer"
	def lookups(self, request, model_admin):
		return ((system.id, system.systemnavn) for system in System.objects.filter(~Q(sikkerhetstest_systemer=None)))

	def queryset(self, request, queryset):
		return queryset.filter(systemer=self.value()) if self.value() else queryset

@admin.register(Sikkerhetstester)
class SikkerhetstesterAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('dato_rapport', 'vis_systemer', 'type_test', 'testet_av', 'rapport', 'notater')
	list_filter = ('dato_rapport', SystemList)
	autocomplete_fields = ('systemer', 'testet_av')


	def vis_systemer(self, obj):
		return ", ".join([s.systemnavn for s in obj.systemer.all()[0:5]])
	vis_systemer.short_description = "Systemer testet (5 første)"

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('systemdetaljer', kwargs={'pk': obj.systemer.all()[0].pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('systemdetaljer', kwargs={'pk': obj.systemer.all()[0].pk}))
		return super().response_change(request, obj)



@admin.register(Autorisasjonsmetode)
class AutorisasjonsmetodeAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('navn', 'definisjon')
	search_fields = ('navn',)

	def get_ordering(self, request):
		return [Lower('navn')]


@admin.register(Leverandortilgang)
class AutorisasjonsmetodeAdmin(SimpleHistoryAdmin):
	list_display = ('pk', 'systemer_vis', 'navn', 'kommentar', 'opprettet')
	search_fields = ('navn',)

	def formfield_for_manytomany(self, db_field, request, **kwargs):
		if db_field.name == "adgrupper":
			query = Q()
			from systemoversikt.views import LEVERANDORTILGANG_KJENTE_GRUPPER
			for term in LEVERANDORTILGANG_KJENTE_GRUPPER:
				query |= Q(distinguishedname__icontains=term)
				kwargs["queryset"] = ADgroup.objects.filter(query)
		return super().formfield_for_manytomany(db_field, request, **kwargs)

	filter_horizontal = (
		'adgrupper',
	)

	autocomplete_fields = (
		'systemer',
	)

	def get_ordering(self, request):
		return [Lower('navn')]

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('leverandortilgang'))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('leverandortilgang'))
		return super().response_change(request, obj)


@admin.register(SystemIntegration)
class SystemIntegrationAdmin(SimpleHistoryAdmin):
	list_display = ('pk', 'source_system', 'destination_system', 'integration_type', 'personopplysninger', 'description',)
	search_fields = ('source_system.systemnavn', 'destination_system.systemnavn','description',)
	list_filter = ('integration_type', 'personopplysninger',)
	autocomplete_fields = ('source_system', 'destination_system',)

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('systemdetaljer', kwargs={'pk': obj.source_system.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('systemdetaljer', kwargs={'pk': obj.source_system.pk}))
		return super().response_change(request, obj)



@admin.register(System)
class SystemAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('systemnavn', 'alias', 'kvalitetssikret', 'systemeierskapsmodell', 'er_arkiv', 'livslop_status', 'systemeier', 'systemforvalter', 'driftsmodell_foreignkey')
	search_fields = ('systemnavn', 'alias',)
	list_filter = ('autentiseringsteknologi', 'autentiseringsalternativer', 'database_in_use', 'database_supported', 'systemeier', 'systemforvalter', 'sikkerhetsnivaa', 'systemtyper', 'livslop_status', 'driftsmodell_foreignkey', 'systemeierskapsmodell', 'strategisk_egnethet', 'funksjonell_egnethet', 'teknisk_egnethet', 'isolert_drift')

	#readonly_fields = ['inv_konklusjon', 'inv_konklusjon_beskrivelse']

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('systemdetaljer', kwargs={'pk': obj.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('systemdetaljer', kwargs={'pk': obj.pk}))
		return super().response_change(request, obj)

	def get_ordering(self, request):
		return [Lower('systemnavn')]

	filter_horizontal = ('systemkategorier', 'informasjonsklassifisering', 'kritisk_kapabilitet', 'LOSref', 'service_offerings', 'citrix_publications',)
	autocomplete_fields = (
		'systemeier',
		'programvarer',
		'systemforvalter',
		#'LOSref',
		'systemforvalter_avdeling_referanse',
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
		'systemtyper',
		'loggingalternativer',
		'autentiseringsteknologi',
		'autentiseringsalternativer',
		#'kritisk_kapabilitet',
		'database_supported',
		'database_in_use',
		'godkjente_bestillere',
		'enterprise_applicatons',
		'tilgangsgrupper_ad',
	)

	fieldsets = (
		('Initiell registrering - informasjon alle systemer må ha utfylt', {
			'description': '',
			'fields': (
				('systemnavn', 'programvarer'),
				('alias', 'livslop_status'),
				('dato_etablert', 'dato_end_of_life'),
				('driftsmodell_foreignkey', 'systemeierskapsmodell'),
				'systembeskrivelse',
				('systemtyper', 'systemurl'),
				('systemeier', 'systemeier_kontaktpersoner_referanse'),
				'systemforvalter',
				('systemforvalter_avdeling_referanse', 'systemforvalter_kontaktpersoner_referanse'),
				'forvaltning_epost',
				'godkjente_bestillere',
			),
		}),
		('Informasjonsbehandling og andre vurderinger', {
			'description': '',
			'fields': (
				'kritisk_kapabilitet',
				'LOSref',
				'systemkategorier',
				'informasjonsklassifisering',
				('sikkerhetsnivaa', 'integritetsvurdering'),
				('tilgjengelighetsvurdering', 'tilgjengelighet_periodisk_kritisk', 'tilgjengelighet_timer_til_kritisk', 'tilgjengelighet_kritiske_perioder'),
				('er_arkiv', 'arkivkommentar'),
				('innsyn_innbygger', 'innsyn_ansatt'),
				'kontaktperson_innsyn',
				('risikovurdering_behovsvurdering', 'dato_sist_ros'),
				('teknisk_egnethet', 'funksjonell_egnethet'),
				'kjente_mangler',
				('url_risikovurdering', 'risikovurdering_tekst'),
			)
		}),
		('Brukerperspektivet og tilgangsstyring', {
			'fields': (
				'tilgangsgrupper_ad',
				'citrix_publications',
				'kontaktgruppe_url',
				'brukerdokumentasjon_url',
				'antall_brukere',
				'superbrukere',
			),
		}),
		('Leverandører og drift', {
			'fields': (
				'service_offerings',
				'basisdriftleverandor',
				('applikasjonsdriftleverandor', 'applikasjonsdrift_behov_databehandleravtale'),
				('systemleverandor', 'systemleverandor_vedlikeholdsavtale',),
				'nokkelpersonell',
				'high_level_design_url',
				('klargjort_ny_sikkerhetsmodell'),
				'inv_konklusjon',
				'inv_konklusjon_beskrivelse',
				'enterprise_applicatons',
				('autentiseringsteknologi', 'autentiseringsalternativer'),
				('legacy_klient_krever_smb', 'legacy_klient_krever_direkte_db'),
				('legacy_klient_krever_onprem_lisensserver', 'legacy_klient_autentisering'),
				'isolert_drift',
				('database_in_use', 'database_supported'),
				'low_level_design_url',
				'datamodell_url',
				'datasett_url',
				'api_url',
				'kildekode_url',
			),
		}),
		('Utfases', {
			'description': '<h3>Kun for oppslag. Dette vil bli avviklet</h3>',
			'classes': ('collapse',),
			'fields': (
				#'cmdbref',
				#'ibruk',
				('avhengigheter_referanser','avhengigheter'),
				('datautveksling_mottar_fra', 'datautveksling_avleverer_til'),
				'systemtekniske_sikkerhetstiltak',
				'programvarekategori',
				'strategisk_egnethet',
				'selvbetjening',
				'kommentar',
				'konfidensialitetsvurdering',
				'loggingalternativer',
				'autorisasjon_differensiering_beskrivelse',
				'autorisasjon_differensiering_saksalder',
				'dataminimalisering',
				'sletting_av_personopplysninger',
				'funksjonalitet_kryptering',
				'anonymisering_pseudonymisering',
				'sikkerhetsmessig_overvaaking',
				'tjenestenivaa',
				'leveransemodell_fip',
				'informasjon_kvalitetssikret',
			),
		}),
	)

	def save_model(self, request, obj, form, change):
		# vi ønsker å begrense tilgang til å opprette system mot andre virksomheter
		if not (request.user.is_superuser or is_admin(request)):
			if obj.systemforvalter != request.user.profile.virksomhet:
				messages.warning(request, f"Du har ikke rettigheter til å registrere systemer for andre virksomheter. Du tilhører {request.user.profile.virksomhet}.")
				return HttpResponseRedirect(request.path)
		super().save_model(request, obj, form, change)


	def has_change_permission(self, request, obj=None):
		if obj:
			if request.user.is_superuser:
				messages.warning(request, 'Du er root og kan endre alt!')
				return True
			if is_admin(request):
				#messages.warning(request, 'Du er superbruker')
				return True
			if request.user.has_perm('systemoversikt.change_system'):
				if obj.systemforvalter == request.user.profile.virksomhet:
					return True
				else:
					messages.warning(request, f'Du har ikke rettigheter til å endre systemer for andre virksomheter enn {request.user.profile.virksomhet.virksomhetsforkortelse}. Kun "superbrukere" har denne tilgangen.')
					return False
			messages.warning(request, f'Du har ikke rettigheter til å endre systemer.')
			return False


@admin.register(Virksomhet)
class VirksomhetAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('virksomhetsforkortelse', 'virksomhetsnavn', 'resultatenhet', 'kan_representeres', 'ordinar_virksomhet', 'orgnummer')
	search_fields = ('virksomhetsnavn', 'virksomhetsforkortelse')
	list_filter = ('resultatenhet', 'ordinar_virksomhet')

	readonly_fields = ["odepartmentnumber"]

	filter_horizontal = ('overordnede_virksomheter',)

	def get_ordering(self, request):
		return [Lower('virksomhetsnavn')]

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('virksomhet', kwargs={'pk': obj.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('virksomhet', kwargs={'pk': obj.pk}))
		return super().response_change(request, obj)

	autocomplete_fields = (
		'leder',
		'informasjonssikkerhetskoordinator',
		'personvernkoordinator',
		'arkitekturkontakter',
		'ikt_kontakt',
		'uke_kam_referanse',
		'autoriserte_bestillere_sertifikater',
		'autoriserte_bestillere_tjenester',
		'autoriserte_bestillere_tjenester_uke',
		'ks_fiks_admin_ref',
	)
	fieldsets = (
			('Initiell registrering', {
				'fields': (
					('virksomhetsnavn','orgnummer',),
					('virksomhetsforkortelse','gamle_virksomhetsforkortelser'),
					'ordinar_virksomhet',
					('odepartmentnumber', 'leder',),
					('overordnede_virksomheter','kan_representeres',),
					('resultatenhet',
					'office365'),
					'sertifikatfullmakt_avgitt_web',
					'autoriserte_bestillere_sertifikater',
					'intranett_url',
					'www_url',
				),
			}),
			('Organisatorisk', {
				'fields': (
					'ikt_kontakt',
					'personvernkoordinator',
					'informasjonssikkerhetskoordinator',
					'uke_kam_referanse',
					'arkitekturkontakter',
					'ks_fiks_admin_ref',
					'autoriserte_bestillere_tjenester',
					'autoriserte_bestillere_tjenester_uke',
				),
			}),
			('GDPR / sikkerhet', {
				'classes': ('collapse',),
				'fields': (
					'styringssystem',
					'rutine_tilgangskontroll',
					'rutine_behandling_personopplysninger',
					'rutine_klage_behandling',
				),
			}),
			('Utfaset', {
				'classes': ('collapse',),
				'fields': (
					'ansatte',
				),
			})
		)

	def save_model(self, request, obj, form, change):
		# vi ønsker å begrense tilgang til å redigere virksomheter for andre virksomheter
		if not (request.user.is_superuser or is_admin(request)):
			if request.user.profile.virksomhet != obj:
				messages.warning(request, f"Du har ikke rettigheter til å registrere andre virksomheter. Du tilhører {request.user.profile.virksomhet}.")
				return HttpResponseRedirect(request.path)
		super().save_model(request, obj, form, change)

	def has_change_permission(self, request, obj=None):
		if obj:
			if request.user.is_superuser:
				messages.warning(request, 'Du er root og kan endre alt!')
				return True
			if is_admin(request):
				#messages.warning(request, 'Du er superbruker')
				return True
			if request.user.has_perm('systemoversikt.change_virksomhet'):
				if request.user.profile.virksomhet == obj:
					return True
				else:
					messages.warning(request, f'Du har ikke rettigheter til å endre virksomhetsdetaljer for andre virksomheter enn {request.user.profile.virksomhet.virksomhetsforkortelse}. Kun "superbrukere" har denne tilgangen.')
					return False
			messages.warning(request, f'Du har ikke rettigheter til å endre virksomheter.')
			return False


@admin.register(SystemBruk)
class SystemBrukAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('system', 'brukergruppe', 'kommentar', 'avtaletype', 'systemeierskap', 'kostnadersystem')
	search_fields = ('system__systemnavn', 'system__systembeskrivelse', 'kommentar', 'systemforvalter')
	list_filter = ('avtalestatus', 'avtale_kan_avropes', 'systemeierskapsmodell', 'brukergruppe')
	autocomplete_fields = ('brukergruppe', 'system', 'systemforvalter', 'systemeier_kontaktpersoner_referanse', 'systemforvalter_kontaktpersoner_referanse', 'avhengigheter_referanser')

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('all_bruk_for_virksomhet', kwargs={'pk': obj.brukergruppe.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('all_bruk_for_virksomhet', kwargs={'pk': obj.brukergruppe.pk}))
		return super().response_change(request, obj)


	fieldsets = (
		('Initiell registrering', {
			'fields': (
				('brukergruppe', 'system'),
				('systemeier_kontaktpersoner_referanse'),
				('systemforvalter_kontaktpersoner_referanse', 'ibruk'),
				('kommentar', 'antall_brukere'), #reintrodusert 31.08.2020
				('url_risikovurdering', 'risikovurdering_tekst'),
				'dato_sist_ros',

			),
		}),
		('Vurderinger', {
			'fields': (
				('strategisk_egnethet', 'funksjonell_egnethet', 'teknisk_egnethet'),
				('konfidensialitetsvurdering', 'integritetsvurdering', 'tilgjengelighetsvurdering'),
			),
		}),
		('Avvikles', {
			'classes': ('collapse',),
			'fields': (
				'del_behandlinger',
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
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('skjemanavn', 'gruppering', 'valgnavn', 'ad_group_ref', 'virksomhet', 'in_active_directory', 'beskrivelse', 'sist_oppdatert')
	search_fields = ('skjemanavn__skjemanavn', 'gruppenavn', 'ad_group_ref__common_name')
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


@admin.register(Oppdatering)
class OppdateringAdmin(admin.ModelAdmin):
	list_display = ('opprettet', 'sist_oppdatert', 'tidspunkt', 'kommentar', 'user')
	search_fields = ('kommentar',)
	autocomplete_fields = ('user',)



@admin.register(RapportGruppemedlemskaper)
class RapportGruppemedlemskaperAdmin(admin.ModelAdmin):
	list_display = ('beskrivelse', 'kategori',)
	autocomplete_fields = ('grupper', 'AND_grupper',)




@admin.register(Leverandor)
class LeverandorAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('leverandor_navn', 'kontaktpersoner', 'orgnummer')
	search_fields = ('leverandor_navn', 'orgnummer', 'notater')


	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('leverandor', kwargs={'pk': obj.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('leverandor', kwargs={'pk': obj.pk}))
		return super().response_change(request, obj)

	def get_ordering(self, request):
		return [Lower('leverandor_navn')]


@admin.register(BehandlingInformering)
class BehandlingInformeringAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('navn', 'beskrivelse')
	search_fields = ('navn', 'beskrivelse')



@admin.register(BehandlingerPersonopplysninger)
class BehandlingerPersonopplysningerAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('behandlingsansvarlig', 'internt_ansvarlig', 'funksjonsomraade', 'behandlingen')
	search_fields = ('behandlingen', 'internt_ansvarlig', 'funksjonsomraade',)
	list_filter = ('behandlingsgrunnlag_valg', 'den_registrerte', 'kategorier_personopplysninger', 'behandlingsansvarlig')
	filter_horizontal = ('informering_til_registrerte_valg', 'relasjon_registrerte', 'den_registrerte_hovedkateogi', 'virksomhet_blacklist', 'programvarer', 'systemer', 'navn_databehandler', 'kategorier_personopplysninger', 'den_registrerte', 'behandlingsgrunnlag_valg')
	autocomplete_fields = ('behandlingsansvarlig', 'oppdateringsansvarlig')

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('behandlingsdetaljer', kwargs={'pk': obj.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('behandlingsdetaljer', kwargs={'pk': obj.pk}))
		return super().response_change(request, obj)

	fieldsets = (
		('Organisatorisk', {
			'classes': ('',),
			'fields': (
				'behandlingsansvarlig',
				'oppdateringsansvarlig',
				'behandlingen',
				'fellesbehandling',
				'informasjon_kvalitetssikret',
				'ekstern_DPIA_url',
			),
		}),
		('Obligatorisk registrering', {
			'classes': ('',),
			'fields': (
				'systemer',
				'den_registrerte',
				'kategorier_personopplysninger',
				'personopplysninger_utdyping',
				'formaal',
				'planlagte_slettefrister',
				('utlevering_ekstern_myndighet', 'utlevering_ekstern_myndighet_utdyping'),
				('utlevering_utenfor_EU', 'garantier_overforing'),
				# Dersom det er mulig, en generell beskrivelse av de tekniske og organisatoriske sikkerhetstiltakene nevnt i artikkel 32 nr. 1.
			),
		}),
		('Ekstraopplysninger', {
			'classes': ('collapse',),
			'fields': (
				'informering_til_registrerte_valg',
				'krav_slettefrister',
				'den_registrerte_detaljer',
				'oppbevaringsplikt',
				'opplysningskilde',
				'behandlingsgrunnlag_valg',
				'behandlingsgrunnlag_utdyping',
				'behandlingsgrunnlag_saerlige_kategorier',
				'navn_databehandler',
				'databehandleravtale_status',
				'databehandleravtale_status_boolean',
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
				'internt_ansvarlig',
				'hoy_personvernrisiko',
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
	list_display = ('kategorinavn', 'definisjon', 'saarbar_gruppe')

	def get_ordering(self, request):
		return [Lower('kategorinavn')]


@admin.register(IntegrasjonKonfigurasjon)
class IntegrasjonKonfigurasjonAdmin(admin.ModelAdmin):
	list_display = ('kodeord', 'kilde', 'protokoll', 'informasjon', 'dato_sist_oppdatert', 'log_event_type', 'sp_filnavn', 'script_navn', 'url', 'frekvensangivelse', 'sist_status')
	readonly_fields = ('dato_sist_oppdatert', 'script_navn', 'sist_status')

@admin.register(AnsattID)
class AnsattIDAdmin(SimpleHistoryAdmin):
	list_display = ('ansattnr',)
	search_fields = ('ansattnr',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'virksomhet', 'org_unit', 'usertype', 'from_prk', 'adgrupper_antall', 'description')
	search_fields = ('user__username', 'user__first_name', 'user__last_name', 'description', 'user__email',)
	autocomplete_fields = ('user', 'ou', 'virksomhet', 'virksomhet_innlogget_som', 'adgrupper', 'org_unit', 'ansattnr_ref')
	list_filter = ('usertype', 'from_prk', 'whenCreated')


@admin.register(SystemUrl)
class SystemUrlAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('domene', 'eier', 'opprettet', 'https', 'vurdering_sikkerhetstest', 'maalgruppe', 'registrar')
	search_fields = ('domene',)
	list_filter = ('https', 'maalgruppe', 'opprettet', 'eier')
	autocomplete_fields = ('registrar', 'eier')

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('alle_systemurler'))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('alle_systemurler'))
		return super().response_change(request, obj)

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
	list_display = ('kategorinavn', 'definisjon', 'har_url', 'er_infrastruktur', 'er_integrasjon',)
	search_fields = ('kategorinavn',)

	def get_ordering(self, request):
		return [Lower('kategorinavn')]


@admin.register(SystemHovedKategori)
class SystemHovedKategoriAdmin(SimpleHistoryAdmin):
	list_display = ('hovedkategorinavn', 'definisjon')
	search_fields = ('hovedkategorinavn', 'definisjon', 'subkategorier')
	filter_horizontal = ('subkategorier',)

	def get_ordering(self, request):
		return [Lower('hovedkategorinavn')]


@admin.register(Ansvarlig)
class AnsvarligAdmin(SimpleHistoryAdmin):
	list_display = ('brukernavn', 'vil_motta_epost_varsler', 'brukers_brukernavn', 'cache_seksjon')
	search_fields = ('brukernavn__username', 'brukernavn__first_name', 'brukernavn__last_name', 'brukernavn__email')
	autocomplete_fields = ('brukernavn',)
	readonly_fields = ('cache_seksjon',)

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('ansvarlig', kwargs={'pk': obj.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
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
				'cache_seksjon',
				)
			}
		),
		('Fylles ut dersom rollen har fullmakt knyttet til sertifikatadministrasjon', {
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
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('programvarenavn', 'programvarebeskrivelse',)
	search_fields = ('programvarenavn', 'programvarebeskrivelse',)
	list_filter = ('programvaretyper', 'programvareleverandor',)
	filter_horizontal = ('programvareleverandor', 'kategorier',)

	def get_ordering(self, request):
		return [Lower('programvarenavn')]


	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('programvaredetaljer', kwargs={'pk': obj.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('programvaredetaljer', kwargs={'pk': obj.pk}))
		return super().response_change(request, obj)

	autocomplete_fields = (
		'programvareleverandor',
		'programvaretyper',
		)

	fieldsets = (
		('Initiell registrering', {
			'fields': (
				'programvarenavn',
				'programvareleverandor',
				'programvarebeskrivelse',
				'kategorier',
				'programvaretyper',
				'klargjort_ny_sikkerhetsmodell',
			),
		}),
		('Utfases', {
			'classes': ('collapse',),
			'fields': (
				'programvarekategori',
				'alias',
				'livslop_status',
				'systemdokumentasjon_url',
				'funksjonell_egnethet',
				'teknisk_egnethet',
				'strategisk_egnethet',
				'kommentar',
			),
		}),
	)


admin.site.unregister(User)  # den er som standard registrert
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	list_display = (
				'username',
				'email',
				'first_name',
				'last_name',
				'is_active',
				'is_staff',
				'last_login',
			)
	search_fields = ('last_login', 'username', 'first_name', 'last_name', 'email')
	list_filter = (
				'is_superuser',
				'profile__accountdisable',
				'profile__passwd_notreqd',
				'profile__dont_req_preauth',
				'profile__trusted_for_delegation',
				'profile__not_delegated',
			)

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

	def userNot_delegated(self, obj):
		return obj.profile.not_delegated
	userNot_delegated.short_description = "Delegated"
	userNot_delegated.boolean = True

	def userDont_req_preauth(self, obj):
		return obj.profile.dont_req_preauth
	userDont_req_preauth.short_description = "Require preauth"
	userDont_req_preauth.boolean = True

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
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('brukergruppe', 'programvare', 'kommentar')
	search_fields = ('programvare', 'kommentar')
	autocomplete_fields = ('brukergruppe', 'programvare', 'programvareleverandor', 'lokal_kontakt')

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('all_bruk_for_virksomhet', kwargs={'pk': obj.brukergruppe.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('all_bruk_for_virksomhet', kwargs={'pk': obj.brukergruppe.pk}))
		return super().response_change(request, obj)

	fieldsets = (
			('Initiell registrering', {
				'fields': (
					'programvare',
					('brukergruppe', 'antall_brukere',),
					'ibruk',
					'lokal_kontakt',
					('funksjonell_egnethet', 'teknisk_egnethet',),
					'kommentar',
				),
			}),
			('Utfases', {
				'classes': ('collapse',),
				'fields': (
					'strategisk_egnethet',
					'livslop_status',
					'programvareeierskap',
					'avtaletype',
					'avtalestatus',
					'avtale_kan_avropes',
					'borger',
					'kostnader',
					'programvareleverandor',
				),
			}),
	)


@admin.register(CMDBbackup)
class CMDBbackupAdmin(admin.ModelAdmin):
	list_display = ('device_str', 'device', 'backup_size_bytes', 'backup_frequency', 'storage_policy',)
	search_fields = ('device_str',)
	list_filter = ('backup_frequency', 'storage_policy',)



@admin.register(CMDBRef)
class CMDBRefAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('navn', 'parent_ref', 'environment', 'operational_status', 'service_classification', 'bss_external_ref', 'opprettet')
	search_fields = ('navn',)
	list_filter = ('environment', 'operational_status', 'service_classification', 'opprettet')

	def get_ordering(self, request):
		return [Lower('navn')]



@admin.register(CMDBbs)
class CMDBRefAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('navn', 'operational_status', 'eksponert_for_bruker', 'ant_bss', 'ant_devices', 'ant_databaser', 'bs_external_ref', 'opprettet')
	search_fields = ('navn',)
	list_filter = ('eksponert_for_bruker', 'operational_status')
	readonly_fields = ('navn', 'operational_status', 'bs_external_ref',)
	autocomplete_fields = ()


	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('alle_cmdbref_sok'))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('alle_cmdbref_sok'))
		return super().response_change(request, obj)

	def get_ordering(self, request):
		return [Lower('navn')]

@admin.register(Fellesinformasjon)
class FellesinformasjonAdmin(admin.ModelAdmin):
	list_display = ('message', 'aktiv',)


@admin.register(APIKeys)
class APIKeysAdmin(admin.ModelAdmin):
	list_display = ('navn', 'kommentar', 'key', 'sist_oppdatert')


@admin.register(Avtale)
class AvtaleAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('kortnavn', 'avtaletype', 'virksomhet', 'leverandor', 'leverandor_intern', 'avtalereferanse', 'dokumenturl')
	search_fields = ('kortnavn', 'beskrivelse', 'avtalereferanse')
	autocomplete_fields = ('avtaleansvarlig_seksjon', 'avtaleansvarlig', 'virksomhet', 'leverandor', 'intern_avtalereferanse', 'leverandor_intern', 'fornying_ekstra_varsling', 'for_system', 'for_driftsmodell',)
	filter_horizontal = ('avtaleansvarlig', 'for_system',)

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('avtalervirksomhet', kwargs={'virksomhet': obj.virksomhet.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('avtalervirksomhet', kwargs={'virksomhet': obj.virksomhet.pk}))
		return super().response_change(request, obj)

	def get_ordering(self, request):
		return [Lower('kortnavn')]

	fieldsets = (
			('Om avtalen', {
				'fields': (
					('avtaletype', 'kortnavn'),
					('avtalereferanse', 'dokumenturl'),
				),
			}),
			('Avtaleparter', {
				'fields': (
					'virksomhet',
					('avtaleansvarlig_seksjon', 'avtaleansvarlig'),
					('leverandor', 'leverandor_intern'),
				),
			}),
			('Avtaleomfang', {
				'fields': (
					('for_system', 'for_driftsmodell'),
					'intern_avtalereferanse',
				),
			}),
			('Avtalefornying', {
				'fields': (
					'dato_signert',
					('fornying_dato', 'fornying_varsling_valg'),
					'fornying_ekstra_varsling',
				),
			}),
			('Kommentarer', {
				'fields': (
					'beskrivelse',
				),
			}),
		)


@admin.register(DPIA)
class DPIAAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
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
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('navn', 'sikkerhetsnivaa', 'kommentar', 'ansvarlig_virksomhet', 'type_plattform')
	search_fields = ('navn',)
	filter_horizontal = ('lokasjon_lagring_valgmeny', 'leverandor', 'underleverandorer', 'avtaler', 'anbefalte_kategorier_personopplysninger')
	autocomplete_fields = ('ansvarlig_virksomhet',)

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('detaljer_driftsmodell', kwargs={'pk': obj.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('detaljer_driftsmodell', kwargs={'pk': obj.pk}))
		return super().response_change(request, obj)

	def get_ordering(self, request):
		return ['sort_order', Lower('navn')]

	fieldsets = (
			('Obligatorisk informasjon', {
				'fields': (
					('navn', 'sort_order'),
					'ansvarlig_virksomhet',
					'overordnet_plattform',
					'type_plattform',
					('utviklingsplattform','samarbeidspartner'),
					'avtaler',
					'kommentar',
				),
			}),
			('Tilleggsinformasjon', {
				'classes': ('collapse',),
				'fields': (
					'leverandor',
					'underleverandorer',
					'risikovurdering',
					'anbefalte_kategorier_personopplysninger',
					'sikkerhetsnivaa',
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

	def save_model(self, request, obj, form, change):
		# vi ønsker å begrense tilgang til å redigere virksomheter for andre virksomheter
		if not (request.user.is_superuser or is_admin(request)):
			if request.user.profile.virksomhet != obj.ansvarlig_virksomhet:
				messages.warning(request, f"Du har ikke rettigheter til å endre på denne driftsmodellen. Du tilhører {request.user.profile.virksomhet}.")
				return HttpResponseRedirect(request.path)
		super().save_model(request, obj, form, change)

	def has_change_permission(self, request, obj=None):
		if obj:
			if request.user.is_superuser:
				messages.warning(request, 'Du er root og kan endre alt!')
				return True
			if is_admin(request):
				#messages.warning(request, 'Du er superbruker')
				return True
			if request.user.has_perm('systemoversikt.change_virksomhet'):
				if request.user.profile.virksomhet == obj.ansvarlig_virksomhet:
					return True
				else:
					messages.warning(request, f'Du har ikke rettigheter til å endre plattformer for andre virksomheter enn {request.user.profile.virksomhet.virksomhetsforkortelse}. Kun "superbrukere" har denne tilgangen.')
					return False
			messages.warning(request, f'Du har ikke rettigheter til å endre plattformer.')
			return False


@admin.register(ADOrgUnit)
class ADOrgUnitAdmin(admin.ModelAdmin):
	list_display = ('ou', 'when_created', 'distinguishedname',)
	search_fields = ('distinguishedname',)
	#list_filter = ()


@admin.register(ADgroup)
class ADgroupAdmin(admin.ModelAdmin):
	list_display = ('common_name', 'display_name', 'mail', 'from_prk', 'membercount', 'memberofcount', 'description', 'sist_oppdatert', 'distinguishedname',)
	search_fields = ('distinguishedname', 'display_name', 'mail', 'member')
	list_filter = ('from_prk', 'opprettet', 'sist_oppdatert')
	autocomplete_fields = ('parent',)


@admin.register(WANLokasjon)
class WANLokasjonAdmin(admin.ModelAdmin):
	list_display = ('lokasjons_id', 'virksomhet', 'aksess_type', 'adresse', 'beskrivelse')
	search_fields = ('lokasjons_id', 'virksomhet', 'adresse', 'beskrivelse')
	list_filter = ('virksomhet',)


@admin.register(AutorisertBestiller)
class AutorisertBestillerAdmin(SimpleHistoryAdmin):
	list_display = ('person', 'dato_fullmakt')
	autocomplete_fields = ('person',)
	search_fields = ('person',)


@admin.register(CMDBdevice)
class CMDBdeviceAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('comp_name', 'device_type', 'sist_oppdatert', 'model_id', 'sist_sett', 'last_loggedin_user', 'device_active', 'kilde_cmdb', 'kilde_prk', 'kilde_landesk', 'maskinadm_status', 'maskinadm_virksomhet_str', 'comp_ip_address', 'comp_os_readable', 'comp_ram', 'dns', 'vlan')
	search_fields = ('comp_name', 'comments', 'description')
	list_filter = ('device_active', 'device_type', 'comp_os_readable', 'sist_sett', 'kilde_cmdb', 'kilde_prk', 'kilde_landesk', 'maskinadm_status', 'maskinadm_klienttype', 'landesk_manufacturer', 'landesk_os_release', 'landesk_os', 'maskinadm_virksomhet',)
	autocomplete_fields = ('last_loggedin_user', 'maskinadm_virksomhet', 'landesk_login')
	filter_horizontal = ('service_offerings',)

@admin.register(CMDBDisk)
class UserChangeLogAdmin(admin.ModelAdmin):
	list_display = ('name', 'mount_point', 'operational_status', 'file_system', 'size_bytes', 'free_space_bytes', 'computer_ref' )
	search_fields = ('computer',)
	list_filter = ('file_system', 'operational_status', )


@admin.register(Loggkategori)
class LoggkategoriAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	search_fields = ('navn', 'definisjon')



@admin.register(Autentiseringsteknologi)
class AutentiseringsteknologiAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	search_fields = ('navn', 'definisjon')

	def get_ordering(self, request):
		return [Lower('navn')]


@admin.register(Autentiseringsmetode)
class AutentiseringsmetodeAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	search_fields = ('navn', 'definisjon')

	def get_ordering(self, request):
		return [Lower('navn')]


@admin.register(InformasjonsKlasse)
class InformasjonsKlasseAdmin(admin.ModelAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	search_fields = ('navn', 'beskrivelse')

	def get_ordering(self, request):
		return [Lower('navn')]


@admin.register(Definisjon)
class DefinisjonAdmin(SimpleHistoryAdmin):
	list_display = ('begrep', 'status', 'ansvarlig',)
	actions = [export_as_csv_action("CSV Eksport")]
	autocomplete_fields = ('ansvarlig',)

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('alle_definisjoner'))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('alle_definisjoner'))
		return super().response_change(request, obj)

	def get_ordering(self, request):
		return [Lower('begrep')]


@admin.register(BehovForDPIA)
class BehovForDPIAAdmin(SimpleHistoryAdmin):
	actions = [export_as_csv_action("CSV Eksport")]
	from django.forms.widgets import NullBooleanSelect
	formfield_overrides = {
		models.NullBooleanField: {'widget': NullBooleanSelect},
	}

	def response_add(self, request, obj, post_url_continue=None):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('behandlingsdetaljer', kwargs={'pk': obj.behandling.pk}))
		return super().response_add(request, obj, post_url_continue)

	def response_change(self, request, obj):
		if not any(header in ('_addanother', '_continue', '_popup') for header in request.POST):
			return redirect(reverse('behandlingsdetaljer', kwargs={'pk': obj.behandling.pk}))
		return super().response_change(request, obj)


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
	actions = [export_as_csv_action("CSV Eksport")]
	list_display = ('db_database', 'sub_name', 'db_version', 'db_u_datafilessizekb', 'db_used_for', 'db_operational_status', 'db_comments', )
	search_fields = ('db_database', 'sub_name__navn', 'db_comments', 'db_version')
	list_filter = ('opprettet', 'db_operational_status', 'db_version',)
	autocomplete_fields = ('db_server_modelref',)




@admin.register(Nettverksgruppe)
class NettverksgruppeAdmin(admin.ModelAdmin):
	list_display = ('name', 'members',)
	search_fields = ('name', 'members',)


@admin.register(Brannmurregel)
class BrannmurregelAdmin(admin.ModelAdmin):
	list_display = ('regel_id', 'active', 'permit', 'source', 'destination', 'protocol', 'comment',)
	search_fields = ('source', 'destination', 'protocol', 'comment',)
	list_filter = ('active', 'permit', 'brannmur',)
	autocomplete_fields = ('ref_vip', 'ref_server', 'ref_vlan',)


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
		if request.user.is_superuser:
			return True
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
	list_display = ('belongs_to', 'ubw_amount', 'ubw_xaccount', 'ubw_period', 'ubw_xdim_1', 'ubw_xdim_4', 'ubw_voucher_date', 'ubw_xapar_id', 'ubw_description', 'ubw_artsgr2', 'ubw_artsgr2_text', 'ubw_kategori', 'ubw_kategori_text')
	search_fields = ('event_type', 'message')
	list_filter = ('ubw_account', 'ubw_dim_1', 'ubw_dim_4', 'ubw_apar_id')

@admin.register(UBWMetadata)
class UBWMetadataAdmin(admin.ModelAdmin):
	list_display = ('belongs_to', 'periode_paalopt', 'kategori')
	#search_fields = ('',)
	#list_filter = ('',)

@admin.register(UBWEstimat)
class UBWEstimatAdmin(admin.ModelAdmin):
	list_display = ('belongs_to', 'aktiv', 'prognose_kategori', 'estimat_account', 'estimat_dim_1', 'estimat_dim_4', 'estimat_amount', 'budsjett_amount', 'periode_paalopt')


@admin.register(KritiskFunksjon)
class KritiskFunksjonAdmin(admin.ModelAdmin):
	list_display = ('navn', 'kategori',)
	search_fields = ('navn',)
	#list_filter = ('')


@admin.register(KritiskKapabilitet)
class KritiskKapabilitetAdmin(admin.ModelAdmin):
	list_display = ('navn', 'funksjon', 'beskrivelse')
	search_fields = ('navn', 'beskrivelse')
	#list_filter = ('')