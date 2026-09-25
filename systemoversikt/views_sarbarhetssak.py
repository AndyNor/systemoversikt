# -*- coding: utf-8 -*-
# Change log:
# 2026-09-25: Free-text oppgavestatus, and Qualys hit counts when a CVE matches cve_info.
# 2026-09-25: Relative "sist endret" (for x minutter/dager/uker siden) on the list and in autosave JSON.
# 2026-09-25: Display name Sårbarhetsoppfølging; only title is required on save.
# 2026-09-25: List includes closed cases so the checkbox can show them without a reload.
# 2026-09-25: Inline list autosave – JSON create/update with the same validation and change log as the form.
# 2026-09-25: Sårbarhetssak list, detail, create and edit – same permission as vulnstats.

import json
import re
from urllib.parse import quote

from django import forms
from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from systemoversikt.auto_oidc import render_access_denied
from systemoversikt.models import (
	SARBARHETSSAK_STATUS_LUKKET,
	SARBARHETSSAK_STATUS_VALG,
	SARBARHETSSAK_TILTAKSEIER_VALG,
	QualysVuln,
	Sarbarhetssak,
)
from systemoversikt.object_change_log import log_object_change
from systemoversikt.views import _cves_from_qualys_cve_info, formater_permissions

REQUIRED_PERMISSIONS = ['systemoversikt.view_qualysvuln']

_LOG_FIELDS = (
	('cve', 'CVE', None),
	('tittel', 'tittel', None),
	('tiltakseier', 'tiltakseier', SARBARHETSSAK_TILTAKSEIER_VALG),
	('saksreferanse', 'saksreferanse', None),
	('saksstatus', 'saksstatus', SARBARHETSSAK_STATUS_VALG),
	('oppgavestatus', 'status', None),
)


class SarbarhetssakForm(forms.ModelForm):
	class Meta:
		model = Sarbarhetssak
		fields = ('cve', 'tittel', 'tiltakseier', 'saksreferanse', 'saksstatus', 'oppgavestatus')
		widgets = {
			'cve': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '40'}),
			'tittel': forms.TextInput(attrs={'class': 'form-control'}),
			'tilakseier': forms.Select(attrs={'class': 'form-control'}),
			'saksreferanse': forms.TextInput(attrs={'class': 'form-control'}),
			'saksstatus': forms.Select(attrs={'class': 'form-control'}),
			'oppgavestatus': forms.Textarea(attrs={
				'class': 'form-control',
				'rows': 4,
				'maxlength': '2000',
				'placeholder': 'Status på oppgaven',
			}),
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# 2026-09-25: Title is the only required field. Owner may stay empty.
		self.fields['cve'].required = False
		self.fields['tiltakseier'].required = False
		self.fields['tittel'].required = True
		self.fields['tiltakseier'].choices = [('', 'Velg tiltakseier')] + list(SARBARHETSSAK_TILTAKSEIER_VALG)

	def clean_cve(self):
		return (self.cleaned_data.get('cve') or '').strip().upper()

	def clean_tittel(self):
		return (self.cleaned_data.get('tittel') or '').strip()

	def clean_tiltakseier(self):
		return (self.cleaned_data.get('tiltakseier') or '').strip()

	def clean_saksreferanse(self):
		return (self.cleaned_data.get('saksreferanse') or '').strip()

	def clean_oppgavestatus(self):
		return (self.cleaned_data.get('oppgavestatus') or '').strip()


def _deny_unless_vuln_permission(request):
	if not any(map(request.user.has_perm, REQUIRED_PERMISSIONS)):
		return render_access_denied(request, REQUIRED_PERMISSIONS)
	return None


def _base_context(request):
	return {
		'request': request,
		'required_permissions': formater_permissions(REQUIRED_PERMISSIONS),
	}


def _choice_label(choices, value):
	if not value:
		return '–'
	return dict(choices).get(value, value)


def _field_display(value, choices):
	if choices is not None:
		return _choice_label(choices, value)
	text = (value or '').strip()
	return text or '–'


def _diff_parts(before, after):
	parts = []
	for field_name, label, choices in _LOG_FIELDS:
		old = _field_display(before.get(field_name), choices)
		new = _field_display(getattr(after, field_name), choices)
		if old != new:
			parts.append('%s: «%s» → «%s»' % (label, old, new))
	return parts


def _snapshot(sak):
	return {field_name: getattr(sak, field_name) for field_name, _label, _choices in _LOG_FIELDS}


def _create_log_message(sak):
	message = 'Sårbarhetsoppfølging opprettet: %s – %s (tiltakseier %s, saksstatus %s, referanse %s)' % (
		sak.cve,
		sak.tittel,
		sak.get_tiltakseier_display() or '–',
		sak.get_saksstatus_display(),
		sak.saksreferanse or '–',
	)
	if sak.oppgavestatus:
		message += ', status «%s»' % sak.oppgavestatus
	return message


_CVE_PATTERN = re.compile(r'^CVE-\d{4}-\d+$', re.IGNORECASE)


def _empty_qualys(cve):
	return {
		'treff': 0,
		'enheter': 0,
		'alvorlighet': None,
		'kjent_utnyttet': False,
		'url': reverse('vulnstats_search') + '?query=' + quote(cve),
	}


def _qualys_for_cves(cves):
	# 2026-09-25: icontains prefilter, then exact CVE tokens – avoids CVE-2024-1 matching CVE-2024-12345.
	wanted = []
	seen = set()
	for raw in cves:
		cve = (raw or '').strip().upper()
		if not cve or cve in seen or not _CVE_PATTERN.match(cve):
			continue
		seen.add(cve)
		wanted.append(cve)
	result = {cve: _empty_qualys(cve) for cve in wanted}
	if not wanted:
		return result

	query = Q()
	for cve in wanted:
		query |= Q(cve_info__icontains=cve)
	rows = QualysVuln.objects.filter(query).values_list(
		'cve_info', 'severity', 'known_exploited', 'server_id',
	)
	servers = {cve: set() for cve in wanted}
	for cve_info, severity, known_exploited, server_id in rows.iterator(chunk_size=2000):
		found = _cves_from_qualys_cve_info(cve_info) & seen
		for cve in found:
			bucket = result[cve]
			bucket['treff'] += 1
			if severity is not None and (bucket['alvorlighet'] is None or severity > bucket['alvorlighet']):
				bucket['alvorlighet'] = severity
			if known_exploited:
				bucket['kjent_utnyttet'] = True
			if server_id:
				servers[cve].add(server_id)
	for cve, ids in servers.items():
		result[cve]['enheter'] = len(ids)
	return result


def _qualys_visning(cve, lookup=None):
	cve = (cve or '').strip().upper()
	if not _CVE_PATTERN.match(cve):
		return None
	if lookup is None:
		lookup = _qualys_for_cves([cve])
	return lookup.get(cve)


def _attach_qualys(saker):
	lookup = _qualys_for_cves(sak.cve for sak in saker)
	for sak in saker:
		sak.qualys = _qualys_visning(sak.cve, lookup)


def sarbarhetssak_liste(request):
	# 2026-09-25: All cases are rendered; closed rows start hidden unless vis_lukkede=1.
	# 2026-09-25: Owner and status choices for inline editing in the list.
	denied = _deny_unless_vuln_permission(request)
	if denied:
		return denied

	vis_lukkede = request.GET.get('vis_lukkede') == '1'
	saker = list(Sarbarhetssak.objects.all())
	# 2026-09-25: Relative "sist endret" in the list; exact time stays on the cell tooltip.
	for sak in saker:
		sak.sist_oppdatert_tekst = _format_timestamp(sak.sist_oppdatert)
		sak.sist_oppdatert_tidspunkt = _format_timestamp_abs(sak.sist_oppdatert)
	_attach_qualys(saker)
	if vis_lukkede:
		synlige_antall = len(saker)
	else:
		synlige_antall = sum(1 for sak in saker if sak.saksstatus != SARBARHETSSAK_STATUS_LUKKET)

	context = _base_context(request)
	context.update({
		'saker': saker,
		'vis_lukkede': vis_lukkede,
		'synlige_antall': synlige_antall,
		'tilakseier_valg': SARBARHETSSAK_TILTAKSEIER_VALG,
		'status_valg': SARBARHETSSAK_STATUS_VALG,
	})
	return render(request, 'sarbarhetssak_liste.html', context)


def sarbarhetssak_detaljer(request, pk):
	# 2026-09-25: Single vulnerability case, including closed cases opened by direct link.
	denied = _deny_unless_vuln_permission(request)
	if denied:
		return denied

	sak = get_object_or_404(Sarbarhetssak, pk=pk)
	sak.qualys = _qualys_visning(sak.cve)
	context = _base_context(request)
	context['sak'] = sak
	return render(request, 'sarbarhetssak_detaljer.html', context)


def sarbarhetssak_opprett(request):
	# 2026-09-25: Create form uses view_qualysvuln, same audience as the list.
	return _sarbarhetssak_skjema(request, sak=None)


def sarbarhetssak_endre(request, pk):
	# 2026-09-25: Edit form uses view_qualysvuln; unchanged saves are not logged.
	denied = _deny_unless_vuln_permission(request)
	if denied:
		return denied
	sak = get_object_or_404(Sarbarhetssak, pk=pk)
	return _sarbarhetssak_skjema(request, sak=sak)


def _sarbarhetssak_skjema(request, sak):
	denied = _deny_unless_vuln_permission(request)
	if denied:
		return denied

	creating = sak is None
	before = {} if creating else _snapshot(sak)
	if request.method == 'POST':
		form = SarbarhetssakForm(request.POST, instance=sak)
		if form.is_valid():
			updated = form.save(commit=False)
			if creating:
				updated.save()
				log_object_change(
					request.user,
					updated,
					_create_log_message(updated),
					action_flag=ADDITION,
				)
				messages.success(request, 'Sårbarhetsoppfølging opprettet.')
				return redirect('sarbarhetssak_detaljer', pk=updated.pk)

			parts = _diff_parts(before, updated)
			if not parts:
				messages.info(request, 'Ingen endringer å lagre.')
				return redirect('sarbarhetssak_detaljer', pk=sak.pk)
			updated.save()
			log_object_change(
				request.user,
				updated,
				'Sårbarhetsoppfølging: %s' % '; '.join(parts),
				action_flag=CHANGE,
			)
			messages.success(request, 'Sårbarhetsoppfølging oppdatert.')
			return redirect('sarbarhetssak_detaljer', pk=updated.pk)
	else:
		form = SarbarhetssakForm(instance=sak)

	context = _base_context(request)
	context.update({
		'form': form,
		'sak': sak,
		'creating': creating,
	})
	return render(request, 'sarbarhetssak_skjema.html', context)


def _deny_unless_vuln_json(request):
	if not request.user.is_authenticated:
		return JsonResponse({'ok': False, 'error': 'session_expired'}, status=401)
	if not any(map(request.user.has_perm, REQUIRED_PERMISSIONS)):
		return JsonResponse({'ok': False, 'error': 'Ingen tilgang.'}, status=403)
	return None


def _parse_json_body(request):
	try:
		if not request.body:
			return {}
		data = json.loads(request.body.decode('utf-8'))
	except (json.JSONDecodeError, UnicodeDecodeError):
		return None
	if not isinstance(data, dict):
		return None
	return data


def _text(value):
	if value is None:
		return ''
	return str(value)


def _format_timestamp(value):
	# 2026-09-25: "for 5 minutter siden" – naturaltime omits the leading "for" in Norwegian.
	if value is None:
		return ''
	text = str(naturaltime(value))
	if text.endswith(' siden'):
		return 'for ' + text
	return text


def _format_timestamp_abs(value):
	if value is None:
		return ''
	if timezone.is_aware(value):
		value = timezone.localtime(value)
	return value.strftime('%Y-%m-%d %H:%M')


def _sak_json(sak, qualys=None, include_qualys=False):
	data = {
		'ok': True,
		'pk': sak.pk,
		'cve': sak.cve,
		'tittel': sak.tittel,
		'tilakseier': sak.tiltakseier,
		'saksreferanse': sak.saksreferanse,
		'saksstatus': sak.saksstatus,
		'oppgavestatus': sak.oppgavestatus,
		'sist_oppdatert': _format_timestamp(sak.sist_oppdatert),
		'sist_oppdatert_tidspunkt': _format_timestamp_abs(sak.sist_oppdatert),
		'lagt_til_uke': sak.lagt_til_uke(),
	}
	if include_qualys:
		data['qualys'] = qualys
	return data


def _form_errors(form):
	errors = {}
	for name, field_errors in form.errors.items():
		errors[name] = [str(item) for item in field_errors]
	return errors


def _apply_sarbarhetssak_save(request, sak):
	# 2026-09-25: One log row per autosave when fields actually change.
	payload = _parse_json_body(request)
	if payload is None:
		return JsonResponse({'ok': False, 'error': 'Ugyldig data.'}, status=400)

	creating = sak is None
	before = {} if creating else _snapshot(sak)
	data = {
		'cve': _text(payload.get('cve')),
		'tittel': _text(payload.get('tittel')),
		'tilakseier': _text(payload.get('tiltakseier')),
		'saksreferanse': _text(payload.get('saksreferanse')),
		'saksstatus': _text(payload.get('saksstatus')),
		'oppgavestatus': _text(payload.get('oppgavestatus')),
	}
	form = SarbarhetssakForm(data, instance=sak)
	if not form.is_valid():
		return JsonResponse({'ok': False, 'errors': _form_errors(form)}, status=400)

	updated = form.save(commit=False)
	if creating:
		updated.save()
		log_object_change(
			request.user,
			updated,
			_create_log_message(updated),
			action_flag=ADDITION,
		)
		return JsonResponse(
			_sak_json(updated, qualys=_qualys_visning(updated.cve), include_qualys=True),
			status=201,
		)

	parts = _diff_parts(before, updated)
	if not parts:
		return JsonResponse(_sak_json(sak))
	updated.save()
	log_object_change(
		request.user,
		updated,
		'Sårbarhetsoppfølging: %s' % '; '.join(parts),
		action_flag=CHANGE,
	)
	# 2026-09-25: Qualys lookup only when the CVE changed – title edits should not scan Qualys.
	cve_changed = (before.get('cve') or '') != updated.cve
	return JsonResponse(_sak_json(
		updated,
		qualys=_qualys_visning(updated.cve) if cve_changed else None,
		include_qualys=cve_changed,
	))


@require_POST
def sarbarhetssak_opprett_lagre(request):
	# 2026-09-25: Create a case from the inline list. Same validation and log as the form.
	denied = _deny_unless_vuln_json(request)
	if denied:
		return denied
	return _apply_sarbarhetssak_save(request, sak=None)


@require_POST
def sarbarhetssak_endre_lagre(request, pk):
	# 2026-09-25: Autosave one case from the inline list. Skip log when nothing changed.
	denied = _deny_unless_vuln_json(request)
	if denied:
		return denied
	sak = get_object_or_404(Sarbarhetssak, pk=pk)
	return _apply_sarbarhetssak_save(request, sak=sak)
