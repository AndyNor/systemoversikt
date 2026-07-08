# -*- coding: utf-8 -*-
# Change log:
# 2026-07-08: Read-only views for versioned risk JSON snapshots (collection + sammenstilling).

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from systemoversikt.models import (
	RISK_SNAPSHOT_SOURCE_COLLECTION,
	RISK_SNAPSHOT_SOURCE_SAMMENSTILLING,
	RiskScope,
	RiskSammenstilling,
	RiskSnapshot,
)
from systemoversikt.risk_sammenstilling import user_can_view_sammenstilling
from systemoversikt.risk_snapshot import (
	collection_render_context,
	sammenstilling_render_context,
	snapshot_template_name,
)
from systemoversikt.views_risiko import _deny_scope_access, _has_scope_read_access


def _get_snapshot_or_404(snapshot_id, source_type, source_pk):
	snapshot = get_object_or_404(
		RiskSnapshot,
		snapshot_id=snapshot_id,
		source_type=source_type,
		source_pk=source_pk,
	)
	return snapshot


@login_required
@require_GET
def risiko_scope_snapshot_list(request, pk):
	scope = get_object_or_404(RiskScope.objects.select_related('virksomhet'), pk=pk)
	if not _has_scope_read_access(request, scope):
		return _deny_scope_access(request, scope=scope)
	snapshots = RiskSnapshot.objects.filter(
		source_type=RISK_SNAPSHOT_SOURCE_COLLECTION,
		source_pk=pk,
	).order_by('-captured_at')
	return render(request, 'risk_snapshots/risiko_snapshot_list.html', {
		'request': request,
		'required_permissions': [],
		'source_type': RISK_SNAPSHOT_SOURCE_COLLECTION,
		'source': scope,
		'source_label': 'Risikosamling',
		'snapshots': snapshots,
		'live_url_name': 'risiko_scope_detail',
		'live_pk': pk,
	})


@login_required
@require_GET
def risiko_scope_snapshot_rapport(request, pk, snapshot_id):
	scope = get_object_or_404(RiskScope.objects.select_related('virksomhet'), pk=pk)
	if not _has_scope_read_access(request, scope):
		return _deny_scope_access(request, scope=scope)
	snapshot = _get_snapshot_or_404(snapshot_id, RISK_SNAPSHOT_SOURCE_COLLECTION, pk)
	payload = snapshot.payload or {}
	ctx = collection_render_context(payload, live_scope=scope)
	ctx.update({
		'request': request,
		'required_permissions': [],
		'snapshot': snapshot,
		'snapshot_list_url_name': 'risiko_scope_snapshot_list',
	})
	template = snapshot_template_name(snapshot.template_version, 'risiko_scope_rapport.html')
	return render(request, template, ctx)


@login_required
@require_GET
def risiko_sammenstilling_snapshot_list(request, pk):
	sammenstilling = get_object_or_404(
		RiskSammenstilling.objects.select_related('framework', 'owner_group', 'owner_group__virksomhet'),
		pk=pk,
		is_active=True,
	)
	if not user_can_view_sammenstilling(request.user, sammenstilling):
		from systemoversikt.views_risiko import _render_risk_access_denied
		return _render_risk_access_denied(
			request, 'sammenstilling_view', sammenstilling=sammenstilling,
		)
	snapshots = RiskSnapshot.objects.filter(
		source_type=RISK_SNAPSHOT_SOURCE_SAMMENSTILLING,
		source_pk=pk,
	).order_by('-captured_at')
	return render(request, 'risk_snapshots/risiko_snapshot_list.html', {
		'request': request,
		'required_permissions': [],
		'source_type': RISK_SNAPSHOT_SOURCE_SAMMENSTILLING,
		'source': sammenstilling,
		'source_label': 'Risikosammenstilling',
		'snapshots': snapshots,
		'live_url_name': 'risiko_sammenstilling_detail',
		'live_pk': pk,
	})


@login_required
@require_GET
def risiko_sammenstilling_snapshot_detail(request, pk, snapshot_id):
	sammenstilling = get_object_or_404(
		RiskSammenstilling.objects.select_related('framework', 'owner_group', 'owner_group__virksomhet'),
		pk=pk,
		is_active=True,
	)
	if not user_can_view_sammenstilling(request.user, sammenstilling):
		from systemoversikt.views_risiko import _render_risk_access_denied
		return _render_risk_access_denied(
			request, 'sammenstilling_view', sammenstilling=sammenstilling,
		)
	snapshot = _get_snapshot_or_404(snapshot_id, RISK_SNAPSHOT_SOURCE_SAMMENSTILLING, pk)
	payload = snapshot.payload or {}
	ctx = sammenstilling_render_context(payload)
	ctx.update({
		'request': request,
		'required_permissions': [],
		'snapshot': snapshot,
		'snapshot_list_url_name': 'risiko_sammenstilling_snapshot_list',
	})
	template = snapshot_template_name(snapshot.template_version, 'risiko_sammenstilling_detail.html')
	return render(request, template, ctx)
