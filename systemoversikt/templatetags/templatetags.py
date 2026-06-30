# Change log:
# 2026-06-30: under_revurdering status – arrow-clockwise-circle icon (repeat/review).
# 2026-06-30: access_denied_icon – red 🛇 for missing read permission.
# 2026-06-30: bootstrap_icon – inline Bootstrap Icons SVGs (replaces open-iconic static files).
# 2026-06-30: risiko_scope_status – workflow status icon + label on collection list.
# 2026-06-30: risiko_sannsynlighetstype_tags – probability dimension badges on scenario table.
# 2026-06-30: risiko_konsekvenstype_tags – consequence dimension badges on scenario table.
# 2026-06-30: risiko_tiltak_status_tag – forslag/besluttet status badge colors.
# 2026-06-30: risiko_tiltak_status_tag – colored status badge in scope tiltak table.
# 2026-06-25: risiko_level_tag – level label as colored tag in scenario table.
# 2026-06-25: risiko_kit_tags – K/I/T dimension badges with icons for risk scenario table.
# 2026-06-24: ca_overview_label – filterable CA overview tag markup (button or span).
# 2026-06-24: ca_condition_label_icon – leading SVG icons on CA overview condition tags.
# 2026-06-21: tjeneste_ikon_* – SVG glyphs and accent colours for tjeneste tile overview.
from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe
import string
import random
from systemoversikt.models import *
from django.contrib.auth.models import Permission
import datetime
import re
from urllib.parse import quote

register = template.Library()

_TJENESTE_IKON_FARGER = ('#2A2859', '#28277e', '#5c5a8a', '#925900', '#c45c52')

_TJENESTE_IKON_REGLER = (
	(re.compile(r'data|database|register|arkiv|lagring|datalake', re.I), 'data'),
	(re.compile(r'sky|cloud|azure|saas', re.I), 'sky'),
	(re.compile(r'bruker|saks|innbygg|borger|personal|hr|ansatt', re.I), 'people'),
	(re.compile(r'sikker|tilgang|identitet|pålogg|login|auth', re.I), 'shield'),
	(re.compile(r'bygg|eiendom|plan|byggesak', re.I), 'building'),
	(re.compile(r'rapport|statistikk|analyse|dashboard|innsikt', re.I), 'chart'),
	(re.compile(r'post|e-post|epost|melding|varsel|sms', re.I), 'mail'),
	(re.compile(r'drift|infrastruktur|plattform|server|cmdb', re.I), 'gear'),
	(re.compile(r'kart|geo|sted|lokasjon|adresse', re.I), 'map'),
	(re.compile(r'helse|lege|pasient|omsorg', re.I), 'health'),
	(re.compile(r'skole|barnehage|barn|utdanning|læring', re.I), 'education'),
	(re.compile(r'økonomi|regnskap|faktura|betaling|budsjett|ubw', re.I), 'money'),
	(re.compile(r'nettverk|integrasjon|api|kobling|utveksling', re.I), 'network'),
)

_TJENESTE_IKON_SVG = {
	'data': (
		'<ellipse cx="32" cy="18" rx="16" ry="6" fill="none" stroke="white" stroke-width="2.5"/>'
		'<path d="M16 18v28c0 3.3 7.2 6 16 6s16-2.7 16-6V18" fill="none" stroke="white" stroke-width="2.5"/>'
		'<ellipse cx="32" cy="32" rx="16" ry="6" fill="none" stroke="white" stroke-width="2"/>'
	),
	'sky': (
		'<path d="M18 40h30a10 10 0 0 0-2-19.8A14 14 0 0 0 20 24a9 9 0 0 0-2 16z" '
		'fill="none" stroke="white" stroke-width="2.5" stroke-linejoin="round"/>'
	),
	'people': (
		'<circle cx="24" cy="24" r="6" fill="none" stroke="white" stroke-width="2.5"/>'
		'<path d="M12 46c0-7 5.4-12 12-12s12 5 12 12" fill="none" stroke="white" stroke-width="2.5"/>'
		'<circle cx="44" cy="26" r="5" fill="none" stroke="white" stroke-width="2"/>'
		'<path d="M36 46c0-5 3.6-9 8-9s8 4 8 9" fill="none" stroke="white" stroke-width="2"/>'
	),
	'shield': (
		'<path d="M32 10L14 18v16c0 12 8 18 18 22 10-4 18-10 18-22V18L32 10z" '
		'fill="none" stroke="white" stroke-width="2.5" stroke-linejoin="round"/>'
		'<path d="M24 32l6 6 12-14" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"/>'
	),
	'building': (
		'<rect x="16" y="14" width="32" height="36" rx="2" fill="none" stroke="white" stroke-width="2.5"/>'
		'<rect x="22" y="22" width="8" height="8" fill="none" stroke="white" stroke-width="2"/>'
		'<rect x="34" y="22" width="8" height="8" fill="none" stroke="white" stroke-width="2"/>'
		'<rect x="22" y="36" width="8" height="8" fill="none" stroke="white" stroke-width="2"/>'
		'<rect x="34" y="36" width="8" height="8" fill="none" stroke="white" stroke-width="2"/>'
		'<path d="M28 50h8" stroke="white" stroke-width="2.5" stroke-linecap="round"/>'
	),
	'chart': (
		'<path d="M14 48V28M26 48V20M38 48V32M50 48V14" stroke="white" stroke-width="4" stroke-linecap="round"/>'
		'<path d="M10 50h48" stroke="white" stroke-width="2.5" stroke-linecap="round"/>'
	),
	'mail': (
		'<rect x="12" y="18" width="40" height="28" rx="3" fill="none" stroke="white" stroke-width="2.5"/>'
		'<path d="M12 22l20 14 20-14" fill="none" stroke="white" stroke-width="2.5" stroke-linejoin="round"/>'
	),
	'gear': (
		'<circle cx="32" cy="32" r="10" fill="none" stroke="white" stroke-width="2.5"/>'
		'<circle cx="32" cy="32" r="4" fill="white"/>'
		'<path d="M32 12v8M32 44v8M12 32h8M44 32h8M18.3 18.3l5.7 5.7M40 40l5.7 5.7M45.7 18.3 40 24M24 40l-5.7 5.7" '
		'stroke="white" stroke-width="2.5" stroke-linecap="round"/>'
	),
	'map': (
		'<path d="M32 12c-8 0-14 6-14 14 0 11 14 24 14 24s14-13 14-24c0-8-6-14-14-14z" '
		'fill="none" stroke="white" stroke-width="2.5" stroke-linejoin="round"/>'
		'<circle cx="32" cy="26" r="5" fill="none" stroke="white" stroke-width="2.5"/>'
	),
	'health': (
		'<rect x="28" y="14" width="8" height="36" rx="2" fill="white"/>'
		'<rect x="14" y="28" width="36" height="8" rx="2" fill="white"/>'
	),
	'education': (
		'<path d="M10 24l22-10 22 10-22 10-22-10z" fill="none" stroke="white" stroke-width="2.5" stroke-linejoin="round"/>'
		'<path d="M18 30v12c0 4 8 8 14 8s14-4 14-8V30" fill="none" stroke="white" stroke-width="2.5"/>'
		'<path d="M54 26v16" stroke="white" stroke-width="2.5" stroke-linecap="round"/>'
	),
	'money': (
		'<circle cx="32" cy="32" r="18" fill="none" stroke="white" stroke-width="2.5"/>'
		'<path d="M32 20v24M26 24h10a4 4 0 1 1 0 8h-6a4 4 0 1 0 0 8h12" '
		'fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"/>'
	),
	'network': (
		'<circle cx="18" cy="32" r="6" fill="none" stroke="white" stroke-width="2.5"/>'
		'<circle cx="46" cy="18" r="6" fill="none" stroke="white" stroke-width="2.5"/>'
		'<circle cx="46" cy="46" r="6" fill="none" stroke="white" stroke-width="2.5"/>'
		'<path d="M24 30l16-8M24 34l16 8" stroke="white" stroke-width="2.5"/>'
	),
	'service': (
		'<path d="M32 8l18 10v16L32 54 14 34V18z" fill="none" stroke="white" stroke-width="2.5" stroke-linejoin="round"/>'
		'<path d="M32 22v20M22 28h20" stroke="white" stroke-width="2.5" stroke-linecap="round"/>'
	),
}


def _tjeneste_ikon_meta(navn):
	navn_lower = (navn or '').lower()
	for pattern, slug in _TJENESTE_IKON_REGLER:
		if pattern.search(navn_lower):
			farge = _TJENESTE_IKON_FARGER[sum(ord(c) for c in navn_lower) % len(_TJENESTE_IKON_FARGER)]
			return slug, farge
	farge = _TJENESTE_IKON_FARGER[sum(ord(c) for c in navn_lower) % len(_TJENESTE_IKON_FARGER)]
	return 'service', farge


@register.filter
def tjeneste_ikon_farge(navn):
	return _tjeneste_ikon_meta(navn)[1]


@register.simple_tag
def tjeneste_ikon_svg(navn):
	slug, _ = _tjeneste_ikon_meta(navn)
	inner = _TJENESTE_IKON_SVG.get(slug, _TJENESTE_IKON_SVG['service'])
	return format_html(
		'<svg class="tjeneste-ikon-svg" viewBox="0 0 64 64" aria-hidden="true" focusable="false">{}</svg>',
		format_html(inner),
	)


# Bootstrap Icons paths (16×16) for CA overview condition tag kinds.
_CA_CONDITION_LABEL_ICONS = {
	'user': (
		'<path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6"/>'
		'<path d="M14 14s-1-4-6-4-6 4-6 4 1 1 6 1 6-1 6-1"/>'
	),
	'group': (
		'<path d="M7 14s-1 0-1-1 1-4 5-4 5 2 5 4-1 1-1 1H7zm4-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6m-5.784 6A2.238 2.238 0 0 1 5 13c0-1.355.68-2.75 1.936-3.72A6.325 6.325 0 0 0 5 9c-4 0-5 3-5 4s1 1 1 1zM4.5 8a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5"/>'
	),
	'location': (
		'<path d="M8 16s6-5.686 6-10A6 6 0 0 0 2 6c0 4.314 6 10 6 10m0-7a3 3 0 1 1 0-6 3 3 0 0 1 0 6"/>'
	),
	'app': (
		'<path d="M1 2.5A1.5 1.5 0 0 1 2.5 1h2A1.5 1.5 0 0 1 6 2.5v2A1.5 1.5 0 0 1 4.5 6h-2A1.5 1.5 0 0 1 1 4.5zm8 0A1.5 1.5 0 0 1 10.5 1h2A1.5 1.5 0 0 1 14 2.5v2A1.5 1.5 0 0 1 12.5 6h-2A1.5 1.5 0 0 1 9 4.5zm-8 8A1.5 1.5 0 0 1 2.5 9h2A1.5 1.5 0 0 1 6 10.5v2A1.5 1.5 0 0 1 4.5 14h-2A1.5 1.5 0 0 1 1 12.5zm8 0A1.5 1.5 0 0 1 10.5 9h2a1.5 1.5 0 0 1 1.5 1.5v2a1.5 1.5 0 0 1-1.5 1.5h-2A1.5 1.5 0 0 1 9 12.5v-2z"/>'
	),
	'role': (
		'<path d="M8 0l1.669.864 1.858.282-.842 1.68L11.5 5l-1.715 1.174.842 1.68-1.858.282L8 7.864 6.336 8.136l-1.858-.282.842-1.68L4.5 5l1.715-1.174-.842-1.68 1.858-.282zM6.5 5a1.5 1.5 0 1 0 3 0 1.5 1.5 0 0 0-3 0"/>'
	),
}


@register.simple_tag
def ca_condition_label_icon(kind):
	"""Small leading icon for a CA overview condition tag (user, group, location, app, role)."""
	html = _bootstrap_icon_svg('ca-' + kind, css_class='ca-overview-label__icon')
	return mark_safe(html) if html else ''


def _ca_condition_label_icon_html(kind):
	paths = _CA_CONDITION_LABEL_ICONS.get(kind)
	if not paths:
		return ''
	return _bootstrap_icon_svg('ca-' + kind, css_class='ca-overview-label__icon')


# Bootstrap Icons paths (16×16) – same inline style as site_home.html.
_BOOTSTRAP_ICON_PATHS = {
	'search': (
		'<path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001l3.85 3.85a1 1 0 0 0 1.415-1.414zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0"/>'
	),
	'lock': (
		'<path d="M8 1a2 2 0 0 0-2 2v4H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2V3a2 2 0 0 0-2-2z"/>'
	),
	'pencil': (
		'<path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325z"/>'
	),
	'file': (
		'<path d="M14 4.5V14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2h5.5zM9.5 3V1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V4.5z"/>'
	),
	'arrow-clockwise-circle': (
		'<path d="M8 15A7 7 0 1 0 8 1a7 7 0 0 0 0 14m0 1A8 8 0 1 1 8 0a8 8 0 0 1 0 16z"/>'
		'<path d="M8 4a.5.5 0 0 1 .5.5v3.207l1.146-1.147a.5.5 0 0 1 .708.708l-2 2a.5.5 0 0 1-.708 0l-2-2a.5.5 0 1 1 .708-.708L7.5 7.707V4.5A.5.5 0 0 1 8 4"/>'
	),
	'clock': (
		'<path d="M8 3.5a.5.5 0 0 0-1 0V9a.5.5 0 0 0 .252.434l3.5 2a.5.5 0 0 0 .496-.868L8 8.71z"/>'
		'<path d="M8 16A8 8 0 1 0 8 0a8 8 0 0 0 0 16m7-8A7 7 0 1 1 1 8a7 7 0 0 1 14 0z"/>'
	),
	'check-circle': (
		'<path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0m-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/>'
	),
	'x-circle': (
		'<path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0M5.354 4.646a.5.5 0 0 0-.708.708L7.293 8l-2.647 2.646a.5.5 0 0 0 .708.708L8 8.707l2.646 2.647a.5.5 0 0 0 .708-.708L8.707 8l2.647-2.646a.5.5 0 0 0-.708-.708L8 7.293z"/>'
	),
}
# CA overview icons share the same SVG helper (keys prefixed with ca-).
for _ca_kind, _ca_paths in _CA_CONDITION_LABEL_ICONS.items():
	_BOOTSTRAP_ICON_PATHS['ca-' + _ca_kind] = _ca_paths


def _bootstrap_icon_svg(name, css_class='', width='1em', height='1em'):
	paths = _BOOTSTRAP_ICON_PATHS.get(name)
	if not paths:
		return ''
	if css_class:
		return format_html(
			'<svg class="{}" xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" '
			'viewBox="0 0 16 16" fill="currentColor" aria-hidden="true" focusable="false">{}</svg>',
			css_class,
			width,
			height,
			format_html(paths),
		)
	return format_html(
		'<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" '
		'viewBox="0 0 16 16" fill="currentColor" aria-hidden="true" focusable="false">{}</svg>',
		width,
		height,
		format_html(paths),
	)


@register.simple_tag
def bootstrap_icon(name, css_class='', width='1em', height='1em'):
	"""Inline Bootstrap Icons SVG (same style as site_home.html)."""
	html = _bootstrap_icon_svg(name, css_class=css_class, width=width, height=height)
	return mark_safe(html) if html else ''


@register.simple_tag
def access_denied_icon(size='1em'):
	"""Red prohibition sign (🛇) when the user lacks read permission."""
	return mark_safe(format_html(
		'<span class="access-denied-icon" style="font-size: {}" aria-hidden="true">🛇</span>',
		size,
	))


@register.simple_tag
def ca_overview_label(label):
	"""Render a CA overview tag; filterable labels become toggle buttons."""
	if not isinstance(label, dict):
		label = {'text': label, 'kind': 'grant', 'filter': None}
	text = label.get('text', '')
	kind = label.get('kind', '')
	tag = label.get('filter')
	group = label.get('filter_group')
	classes = 'ca-overview-label ca-overview-label--%s' % kind
	icon_html = _ca_condition_label_icon_html(kind)
	content = format_html('{}{}', icon_html, text)
	if tag and group:
		return format_html(
			'<button type="button" class="{} ca-overview-label--filter" '
			'data-filter-group="{}" data-filter-tag="{}">{}</button>',
			classes,
			group,
			tag,
			content,
		)
	return format_html('<span class="{}">{}</span>', classes, content)


### url_path_segment — for {% url %} path kwargs that may contain /, ?, @, etc.
@register.filter
def url_path_segment(value):
	if value is None:
		return ""
	return quote(str(value), safe="")


### quarter
@register.filter
def quarter(value):
	if isinstance(value, datetime.date):
		month = value.month
		if month in [1, 2, 3]:
			return "Q1"
		elif month in [4, 5, 6]:
			return "Q2"
		elif month in [7, 8, 9]:
			return "Q3"
		elif month in [10, 11, 12]:
			return "Q4"
	return ""


### get_odata_type
@register.filter
def get_odata_type(value):
	if value.get('@odata.type') == "#microsoft.graph.administrativeUnit":
		return "Administrative Unit"
	if value.get('@odata.type') == "#microsoft.graph.group":
		return "Group"
	return value.get('@odata.type', '')


### json_indent
@register.filter
def json_indent(value):
	try:
		return json.dumps(value, indent=4)
	except:
		'filter "json_indent" feilet'



### json_remove_empty
def filter_non_null_properties_recursive(json_obj):
	if isinstance(json_obj, dict):
		return {k: filter_non_null_properties_recursive(v) for k, v in json_obj.items() if v is not None and v != []}
	elif isinstance(json_obj, list):
		return [filter_non_null_properties_recursive(item) for item in json_obj if item is not None and item != []]
	else:
		return json_obj


@register.filter
def json_remove_empty(json_obj):
	if isinstance(json_obj, dict):
		return {k: filter_non_null_properties_recursive(v) for k, v in json_obj.items() if v is not None and v != []}
	elif isinstance(json_obj, list):
		return [filter_non_null_properties_recursive(item) for item in json_obj if item is not None and item != []]
	else:
		return json_obj


### group_from_permission
@register.simple_tag
def group_from_permission(permission_str):
	try:
		permission_parts = permission_str.split(".")
		app_label = permission_parts[0]
		codename = permission_parts[1]
		permissions = Permission.objects.filter(content_type__app_label=app_label, codename=codename)
		all_groups = set()
		for p in permissions:
			groups = p.group_set.all()
			for g in groups:
				all_groups.add(g.name)

		result = []
		for group_name in list(all_groups):
			if "/" in group_name:
				group_name = group_name.replace("/", "")
				result.append(f'AD-gruppen heter "{group_name}"')
		return result

	except:
		return f'Ingen treff på rettighet "{permission_str}"'


### fellesinformasjon
@register.simple_tag(name='fellesinformasjon')
def fellesinformasjon():

	try:
		siste_fellesinfo = Fellesinformasjon.objects.all().order_by("-pk")[0]
	except:
		return ""
	if siste_fellesinfo.aktiv:
		html = format_html('''
				<div style="color: black; position: fixed; font-size: 10pt; margin-left: 100px; text-align: center; background-color: #ffff0033;">{}</div>
				''',
				siste_fellesinfo.message,
			)
		return html
	else:
		return ""


''' https://stackoverflow.com/questions/14496978/fields-verbose-name-in-templates '''
@register.simple_tag
def get_verbose_field_name(instance, field_name):
	try:
		return instance._meta.get_field(field_name).verbose_name
	except:
		return "Unknown"


@register.simple_tag
def get_help_text(instance, field_name):
	try:
		return instance._meta.get_field(field_name).help_text
	except:
		return "Unknown"

def id_generator(size=8, chars=string.ascii_uppercase):
	return ''.join(random.choice(chars) for _ in range(size))


@register.simple_tag()
def explain_collapsed(text):
	random_id = id_generator()
	search_icon = _bootstrap_icon_svg('search', width='10px', height='10px')
	html = format_html('''
		<a data-toggle="collapse" href="#{}" role="button" aria-expanded="false" aria-controls="collapseExample">
		<span style="margin: 0px 4px;">{}</span></a>
		<div class="collapse" style="background-color: #ffffe2;" id="{}">{}</div>
		''',
		random_id,
		search_icon,
		random_id,
		text,
	)
	return html

@register.simple_tag
def get_aduser_count_for(adgruppe, virksomhet):
	return adgruppe.brukere_for_virksomhet(virksomhet)


_RISIKO_KIT_META = {
	'K': ('Konfidensialitet', 'risiko-kit-k'),
	'I': ('Integritet', 'risiko-kit-i'),
	'T': ('Tilgjengelighet', 'risiko-kit-t'),
}

_RISIKO_KIT_ICON_PATHS = {
	'K': (
		'<path d="M8 1a2 2 0 0 0-2 2v2H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2V3a2 2 0 0 0-2-2zM7 3a1 1 0 0 1 2 0v2H7V3z"/>'
	),
	'I': (
		'<path d="M8 1 2 3.5v5A6 6 0 0 0 8 15a6 6 0 0 0 6-6.5v-5L8 1zm0 1.5 4 1.7v3.3a4 4 0 0 1-8 0V4.2l4-1.7z"/>'
		'<path d="M6.2 8.2 7.5 9.5 10 7" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>'
	),
	'T': (
		'<path d="M8 3.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9zM2 8a6 6 0 1 1 12 0A6 6 0 0 1 2 8z"/>'
		'<path d="M8 5.5V8l1.8 1.2" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>'
	),
}


def _risiko_kit_icon_svg(code):
	paths = _RISIKO_KIT_ICON_PATHS.get(code)
	if not paths:
		return ''
	return format_html(
		'<svg class="risiko-kit-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" '
		'fill="currentColor" aria-hidden="true" focusable="false">{}</svg>',
		format_html(paths),
	)


_TILTAK_STATUS_TAG_CSS = {
	'forslag': 'risiko-tiltak-status-forslag',
	'besluttet': 'risiko-tiltak-status-besluttet',
	'ikke_startet': 'risiko-tiltak-status-besluttet',
	'under_arbeid': 'risiko-tiltak-status-under-arbeid',
	'utfort': 'risiko-tiltak-status-utfort',
}


@register.simple_tag
def risiko_tiltak_status_tag(status, status_display):
	if not status_display:
		return '-'
	css = _TILTAK_STATUS_TAG_CSS.get(status, 'risiko-tiltak-status-unknown')
	return mark_safe(format_html(
		'<span class="risiko-tiltak-status-tag {}">{}</span>',
		css,
		status_display,
	))


@register.simple_tag
def risiko_level_tag(label, css_class):
	if not label:
		return '-'
	cls = css_class or 'risk-cell-empty'
	return mark_safe(format_html(
		'<span class="risiko-level-tag {}">{}</span>',
		cls,
		label,
	))


@register.simple_tag
def risiko_kit_tags(kit_dimensjoner):
	from systemoversikt.risk_criteria import parse_kit_dimensjoner
	tags = parse_kit_dimensjoner(kit_dimensjoner)
	if not tags:
		return '-'
	parts = []
	for code in tags:
		label, css = _RISIKO_KIT_META[code]
		parts.append(format_html(
			'<span class="risiko-kit-tag {}" title="{}">{}{}</span>',
			css,
			label,
			_risiko_kit_icon_svg(code),
			label,
		))
	return mark_safe(' '.join(str(part) for part in parts))


@register.simple_tag
def risiko_konsekvenstype_tags(konsekvenstyper):
	from systemoversikt.risk_criteria import konsekvenstype_tag_dicts
	tags = konsekvenstype_tag_dicts(konsekvenstyper)
	if not tags:
		return '-'
	parts = []
	for tag in tags:
		parts.append(format_html(
			'<span class="risiko-konsekvenstype-tag" title="{}">{}</span>',
			tag['label'],
			tag['label'],
		))
	return mark_safe(' '.join(str(part) for part in parts))


_SCOPE_STATUS_META = {
	'forsteutkast': {
		'icon': 'file',
		'css': 'risiko-scope-status-forsteutkast',
	},
	'under_revurdering': {
		'icon': 'arrow-clockwise-circle',
		'css': 'risiko-scope-status-under-revurdering',
	},
	'til_godkjenning': {
		'icon': 'clock',
		'css': 'risiko-scope-status-til-godkjenning',
	},
	'godkjent': {
		'icon': 'check-circle',
		'css': 'risiko-scope-status-godkjent',
	},
}


@register.simple_tag
def risiko_scope_status(status, status_display):
	if not status_display:
		return '-'
	meta = _SCOPE_STATUS_META.get(status)
	if not meta:
		return status_display
	icon_html = _bootstrap_icon_svg(meta['icon'], css_class='risiko-scope-status-icon', width='16px', height='16px')
	return mark_safe(format_html(
		'<span class="risiko-scope-status {}" title="{}">'
		'{}'
		'<span class="risiko-scope-status-label">{}</span></span>',
		meta['css'],
		status_display,
		icon_html,
		status_display,
	))


@register.simple_tag
def risiko_sannsynlighetstype_tags(sannsynlighetstyper):
	from systemoversikt.risk_criteria import sannsynlighetstype_tag_dicts
	tags = sannsynlighetstype_tag_dicts(sannsynlighetstyper)
	if not tags:
		return '-'
	parts = []
	for tag in tags:
		parts.append(format_html(
			'<span class="risiko-sannsynlighetstype-tag" title="{}">{}</span>',
			tag['label'],
			tag['label'],
		))
	return mark_safe(' '.join(str(part) for part in parts))

