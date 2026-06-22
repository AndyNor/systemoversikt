# -*- coding: utf-8 -*-
# Change log:
# 2026-06-22: Programvare leaf nodes on service components – dark black tag shape.
# 2026-06-21: Group by systemforvalter virksomhet – replaces driftsplattform compound boxes.
# 2026-06-21: Direct dependencies only – no multi-level expansion or URL/CMDB nodes.
# 2026-06-21: Tjeneste ecosystem graph – separate from system detail generer_graf_ny.
from django.db.models import Prefetch
from django.urls import reverse

from systemoversikt.models import SYSTEM_COLORS, SystemIntegration


def _parent_virksomhet(system):
	if system.systemforvalter_id:
		return f"virksomhet_{system.systemforvalter_id}"
	return "virksomhet_ukjent"


def _virksomhet_visningsnavn(virksomhet):
	if virksomhet is None:
		return "Ukjent virksomhet"
	return virksomhet.virksomhetsforkortelse or virksomhet.virksomhetsnavn


def _graf_node_navn(tekst, maximum=40):
	if len(tekst) > maximum:
		return tekst[:maximum] + "…"
	return tekst


def _graf_kant(graf, kilde, mal, farge):
	graf["edges"].append({"data": {
		"source": kilde,
		"target": mal,
		"linewidth": 1,
		"curve-style": "bezier",
		"linecolor": farge,
		"linestyle": "dotted",
	}})


def _legg_til_system_node(graf, system, *, er_komponent, observerte_virksomheter, observerte_systemer):
	if system.pk in observerte_systemer:
		return
	observerte_systemer.add(system.pk)
	farge = SYSTEM_COLORS["chart_service_component"] if er_komponent else SYSTEM_COLORS["chart_external_system"]
	graf["nodes"].append({"data": {
		"id": system.pk,
		"parent": _parent_virksomhet(system),
		"name": system.systemnavn,
		"shape": "ellipse",
		"color": farge,
		"href": reverse('systemdetaljer', args=[system.pk]),
	}})
	observerte_virksomheter.add(system.systemforvalter)


def generer_tjeneste_okosystem_graf(tjeneste):
	"""Build a Cytoscape graph with direct integration neighbours of service components."""
	komponenter = list(
		tjeneste.systemer
		.select_related('systemforvalter')
		.prefetch_related(
			'programvarer',
			Prefetch(
				'system_integration_source',
				queryset=SystemIntegration.objects.select_related(
					'destination_system',
					'destination_system__systemforvalter',
				),
			),
			Prefetch(
				'system_integration_destination',
				queryset=SystemIntegration.objects.select_related(
					'source_system',
					'source_system__systemforvalter',
				),
			),
		)
	)
	komponent_ids = {s.pk for s in komponenter}

	graf = {"nodes": [], "edges": []}
	if not komponenter:
		return graf

	observerte_virksomheter = set()
	observerte_systemer = set()
	observerte_integrasjoner = set()

	for system in komponenter:
		_legg_til_system_node(
			graf, system,
			er_komponent=True,
			observerte_virksomheter=observerte_virksomheter,
			observerte_systemer=observerte_systemer,
		)

	for aktuelt_system in komponenter:
		for integrasjon in aktuelt_system.system_integration_source.all():
			destinasjon = integrasjon.destination_system
			_legg_til_system_node(
				graf, destinasjon,
				er_komponent=destinasjon.pk in komponent_ids,
				observerte_virksomheter=observerte_virksomheter,
				observerte_systemer=observerte_systemer,
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
				observerte_virksomheter=observerte_virksomheter,
				observerte_systemer=observerte_systemer,
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

	virksomhet_gruppe_shape = "roundrectangle"
	virksomhet_gruppe_color = "#F1F9FF"
	for virksomhet in observerte_virksomheter:
		if virksomhet is None:
			graf["nodes"].append({"data": {
				"id": "virksomhet_ukjent",
				"name": _virksomhet_visningsnavn(None),
				"shape": virksomhet_gruppe_shape,
				"color": virksomhet_gruppe_color,
			}})
		else:
			graf["nodes"].append({"data": {
				"id": f"virksomhet_{virksomhet.pk}",
				"name": _virksomhet_visningsnavn(virksomhet),
				"shape": virksomhet_gruppe_shape,
				"color": virksomhet_gruppe_color,
			}})

	programvare_color = SYSTEM_COLORS["chart_programvare"]
	observerte_programvare = set()
	for system in komponenter:
		for pv in system.programvarer.all():
			node_id = f"programvare_{pv.pk}"
			if pv.pk not in observerte_programvare:
				observerte_programvare.add(pv.pk)
				graf["nodes"].append({"data": {
					"id": node_id,
					"name": _graf_node_navn(pv.programvarenavn),
					"shape": "tag",
					"color": programvare_color,
					"href": reverse("programvaredetaljer", args=[pv.pk]),
				}})
			_graf_kant(graf, system.pk, node_id, programvare_color)

	return graf
