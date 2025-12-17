from django import template
from django.conf import settings
from django.utils.html import format_html
import string
import random
from systemoversikt.models import *
from django.contrib.auth.models import Permission
import datetime
import re

register = template.Library()


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
				ad_group = ADgroup.objects.get(common_name=group_name)
				if len(ad_group.prkvalg.all()) == 1:
					prk_valg = ad_group.prkvalg.all()[0]
					result.append(f'AD-gruppen heter "{group_name}"')
				else:
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
	html = format_html('''
		<a data-toggle="collapse" href="#{}" role="button" aria-expanded="false" aria-controls="collapseExample">
		<img style="width: 10px; margin: 0px 4px;" src="{}open-iconic/svg/magnifying-glass.svg" alt="rediger"></a>
		<div class="collapse" style="background-color: #ffffe2;" id="{}">{}</div>
		''',
		random_id,
		settings.STATIC_URL,
		random_id,
		text,
	)
	return html

@register.simple_tag
def get_aduser_count_for(adgruppe, virksomhet):
	return adgruppe.brukere_for_virksomhet(virksomhet)

