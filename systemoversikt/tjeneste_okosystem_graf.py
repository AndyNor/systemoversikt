# -*- coding: utf-8 -*-
# Change log:
# 2026-06-21: Direct dependencies only – no multi-level expansion or URL/CMDB nodes.
# 2026-06-21: Tjeneste ecosystem graph – separate from system detail generer_graf_ny.
from django.urls import reverse

from systemoversikt.models import SYSTEM_COLORS


def _parent_driftsmodell(system):
	if system.driftsmodell_foreignkey is not None:
		return f"drift_{system.driftsmodell_foreignkey.pk}"
	return "Ukjent"


def _legg_til_system_node(graf, system, *, er_komponent, observerte_driftsmodeller, observerte_systemer, tjeneste_pk):
	if system.pk in observerte_systemer:
		return
	observerte_systemer.add(system.pk)
	farge = SYSTEM_COLORS["chart_service_component"] if er_komponent else SYSTEM_COLORS["chart_external_system"]
	parent = f"tjeneste_{tjeneste_pk}" if er_komponent else _parent_driftsmodell(system)
	graf["nodes"].append({"data": {
		"id": system.pk,
		"parent": parent,
		"name": system.systemnavn,
		"shape": "ellipse",
		"color": farge,
		"href": reverse('systemdetaljer', args=[system.pk]),
	}})
	observerte_driftsmodeller.add(system.driftsmodell_foreignkey)


def generer_tjeneste_okosystem_graf(tjeneste):
	"""Build a Cytoscape graph with direct integration neighbours of service components."""
	komponenter = list(
		tjeneste.systemer
		.select_related('driftsmodell_foreignkey', 'driftsmodell_foreignkey__overordnet_plattform')
		.prefetch_related(
			'system_integration_source',
			'system_integration_destination',
		)
	)
	komponent_ids = {s.pk for s in komponenter}

	graf = {"nodes": [], "edges": []}
	if not komponenter:
		return graf

	graf["nodes"].append({"data": {
		"id": f"tjeneste_{tjeneste.pk}",
		"name": tjeneste.navn,
		"shape": "roundrectangle",
		"color": "#F8F0DD",
	}})

	observerte_driftsmodeller = set()
	observerte_systemer = set()
	observerte_integrasjoner = set()

	for system in komponenter:
		_legg_til_system_node(
			graf, system,
			er_komponent=True,
			observerte_driftsmodeller=observerte_driftsmodeller,
			observerte_systemer=observerte_systemer,
			tjeneste_pk=tjeneste.pk,
		)

	for aktuelt_system in komponenter:
		for integrasjon in aktuelt_system.system_integration_source.all():
			destinasjon = integrasjon.destination_system
			_legg_til_system_node(
				graf, destinasjon,
				er_komponent=destinasjon.pk in komponent_ids,
				observerte_driftsmodeller=observerte_driftsmodeller,
				observerte_systemer=observerte_systemer,
				tjeneste_pk=tjeneste.pk,
			)
			if integrasjon.pk not in observerte_integrasjoner:
				observerte_integrasjoner.add(integrasjon.pk)
				graf["edges"].append({"data": {
					"id": f"integration_{integrasjon.pk}",
					"source": aktuelt_system.pk,
					"target": destinasjon.pk,
					"linewidth": 2,
					"curve-style": "bezier",
					"linecolor": integrasjon.color(),
					"linestyle": "solid",
					"href": reverse('admin:systemoversikt_systemintegration_change', args=[integrasjon.pk]),
				}})

		for integrasjon in aktuelt_system.system_integration_destination.all():
			kilde = integrasjon.source_system
			_legg_til_system_node(
				graf, kilde,
				er_komponent=kilde.pk in komponent_ids,
				observerte_driftsmodeller=observerte_driftsmodeller,
				observerte_systemer=observerte_systemer,
				tjeneste_pk=tjeneste.pk,
			)
			if integrasjon.pk not in observerte_integrasjoner:
				observerte_integrasjoner.add(integrasjon.pk)
				graf["edges"].append({"data": {
					"id": f"integration_{integrasjon.pk}",
					"source": kilde.pk,
					"target": aktuelt_system.pk,
					"linewidth": 2,
					"curve-style": "bezier",
					"linecolor": integrasjon.color(),
					"linestyle": "solid",
					"href": reverse('admin:systemoversikt_systemintegration_change', args=[integrasjon.pk]),
				}})

	drift_gruppe_shape = "roundrectangle"
	drift_gruppe_color = "#F1F9FF"
	for driftsmodell in observerte_driftsmodeller:
		if driftsmodell is None:
			continue
		if driftsmodell.overordnet_plattform:
			graf["nodes"].append({"data": {
				"id": f"drift_{driftsmodell.pk}",
				"name": driftsmodell.navn,
				"parent": f"drift_{driftsmodell.overordnet_plattform.pk}",
				"shape": drift_gruppe_shape,
				"color": drift_gruppe_color,
			}})
			graf["nodes"].append({"data": {
				"id": f"drift_{driftsmodell.overordnet_plattform.pk}",
				"name": driftsmodell.overordnet_plattform.navn,
				"shape": drift_gruppe_shape,
				"color": drift_gruppe_color,
			}})
		else:
			graf["nodes"].append({"data": {
				"id": f"drift_{driftsmodell.pk}",
				"name": driftsmodell.navn,
				"shape": drift_gruppe_shape,
				"color": drift_gruppe_color,
			}})

	return graf
