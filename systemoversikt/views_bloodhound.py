# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: BloodHound snapshot status page – object counts from latest upload.
import re

from django.http import Http404
from django.shortcuts import render

from systemoversikt.models import BloodHoundSnapshot
from systemoversikt.views import _integrasjonsstatus, formater_permissions

SNAPSHOT_ID_RE = re.compile(r'^\d{14}$')


def sikkerhet_bloodhound_status(request):
	required_permissions = ['auth.view_user']
	if not any(map(request.user.has_perm, required_permissions)):
		return render(request, '403.html', {
			'required_permissions': required_permissions,
			'groups': request.user.groups,
		})

	selected_id = request.GET.get('snapshot', '').strip()
	if selected_id and not SNAPSHOT_ID_RE.match(selected_id):
		raise Http404

	snapshots = list(
		BloodHoundSnapshot.objects.filter(status='indexed').order_by('-snapshot_id')[:20]
	)
	if not snapshots:
		selected = None
	else:
		if selected_id:
			selected = BloodHoundSnapshot.objects.filter(snapshot_id=selected_id).first()
			if not selected:
				raise Http404
		else:
			selected = snapshots[0]

	return render(request, 'sikkerhet_bloodhound_status.html', {
		'request': request,
		'required_permissions': formater_permissions(required_permissions),
		'snapshots': snapshots,
		'selected': selected,
		'integrasjonsstatus': _integrasjonsstatus('bloodhound_ad'),
	})
