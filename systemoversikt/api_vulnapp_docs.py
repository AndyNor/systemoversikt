# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: API documentation metadata for Sårbarhetsoversikten (vulnapp) developer page.
import json

BASE_URL = "https://kartoteket.oslo.kommune.no"

AUTH_INFO = {
	"description_no": (
		"Autentisering varierer per endepunkt. De fleste krever HTTP-header «key». "
		"I TEST-miljø (THIS_ENV=TEST) hoppes nøkkelsjekk over for ipsok og programvare. "
		"Kontakt Kartotek-forvalter for API-nøkler – committ aldri nøkler til kildekode."
	),
	"error_403": '{"message": "Missing or wrong key. Supply HTTP header \'key\'", "data": null}',
}

LIMITATIONS = [
	{
		"title": "Ulikt responsformat",
		"description_no": "Endepunktene deler ikke samme JSON-wrapper som tjeneste-/systemoversikt-API-ene.",
	},
	{
		"title": "Sideeffekt på ipsok",
		"description_no": "Ved treff oppdateres eksternt_eksponert_dato på berørte CMDB-servere (markering som internett-eksponert).",
	},
	{
		"title": "known_exploited er kun POST",
		"description_no": "GET returnerer 405. Body må være Django serialisert JSON med modellsti vulnapp.exploitedvulnerability (erstattes internt).",
	},
	{
		"title": "programvare og «åpen»",
		"description_no": "API-oversikten beskriver endepunktet som åpent; i produksjon kreves likevel nøkkel med navn som starter på «vulnapp» (unntatt TEST).",
	},
	{
		"title": "Logging",
		"description_no": "Kall logges i ApplicationLog med klient-IP og hendelsestype.",
	},
]

FLOW_NOTES_NO = (
	"Sårbarhetsoversikten (VulnApp) henter programvareliste periodisk, slår opp IP-adresser mot CMDB "
	"ved behov, og pusher CISA Known Exploited Vulnerabilities til Kartoteket via POST."
)


def _curl_get(path, query=None):
	url = f"{BASE_URL}{path}"
	if query:
		url = f"{url}?{query}"
	return f'curl -s -H "key: <API_KEY>" "{url}"'


def _curl_post(path):
	return (
		f'curl -s -X POST -H "key: <API_KEY>" -H "Content-Type: application/json" '
		f'-d @known_exploited.json "{BASE_URL}{path}"'
	)


def _field(name, ftype, nullable, description_no):
	return {
		"name": name,
		"type": ftype,
		"nullable": nullable,
		"description_no": description_no,
	}


ENDPOINTS = [
	{
		"slug": "ipsok",
		"path": "/api/vulnapp/ipsok/",
		"name": "IP-oppslag",
		"view_name": "csirt_iplookup_api",
		"method": "GET",
		"api_class": None,
		"django_model": "NetworkIPAddress, DNSrecord, CMDBdevice",
		"auth_no": "Header «key» – APIKeys der navn starter med «vulnapp». Unntatt i THIS_ENV=TEST.",
		"beskrivelse_no": (
			"Oppslag av IP-adresse (og valgfritt port) mot CMDB. Returnerer DNS-treff, VIP-er, "
			"pool-medlemmer og VLAN-info. Ved treff markeres berørte servere som internett-eksponert."
		),
		"query_params": [
			{"name": "ip", "required": True, "description_no": "IPv4/IPv6-adresse som skal slås opp"},
			{"name": "port", "required": False, "description_no": "Portnummer – filtrerer VIP pool-medlemmer"},
		],
		"response_note_no": "Respons er flat JSON (ikke beskrivelse/antall/data-wrapper). Ved feil returneres {\"error\": \"...\"} med HTTP 200.",
		"fields": [
			_field("query_ip", "string", False, "IP-adressen som ble oppslagt"),
			_field("query_port", "string", False, "Port fra forespørsel (tom streng hvis ikke oppgitt)"),
			_field("dns_matches", "array of string", False, "DNS-navn knyttet til IP (eller «Flere enn 15»)"),
			_field("vip_matches", "array of string", False, "VIP-er på IP, format «vip port»"),
			_field("vip_pool_members", "array of object", False, "Servere bak VIP (se underfelter)"),
			_field("vip_pool_members[].server", "string", False, "CMDB comp_name"),
			_field("vip_pool_members[].host_ip", "string", False, "Serverens IP"),
			_field("vip_pool_members[].external_vip", "string", False, "Ekstern VIP og port"),
			_field("vip_pool_members[].server_vlan", "string", False, "Dominant VLAN for server"),
			_field("vip_pool_members[].bss", "array of string", False, "Service offering-navn"),
			_field("matching_vlans", "array of string", False, "VLAN/subnett knyttet til IP"),
		],
		"references": [],
		"side_effects_no": "Setter eksternt_eksponert_dato=now på servere funnet direkte på IP eller via VIP pool.",
		"curl_example": _curl_get("/api/vulnapp/ipsok/", "ip=192.0.2.1&port=443"),
		"example_json": """{
  "query_ip": "192.0.2.1",
  "query_port": "443",
  "dns_matches": ["example.oslo.kommune.no"],
  "vip_matches": ["203.0.113.10 port 443"],
  "vip_pool_members": [
    {
      "server": "srv-example-01",
      "host_ip": "10.0.0.5",
      "external_vip": "203.0.113.10 port 443",
      "server_vlan": "App VLAN (10.0.0.0/24)",
      "bss": ["Eksempel-tjeneste"]
    }
  ],
  "matching_vlans": ["10.0.0.0 subnet /24: App VLAN"]
}""",
	},
	{
		"slug": "programvare",
		"path": "/api/vulnapp/programvare/",
		"name": "Programvareliste",
		"view_name": "api_programvare_vulnapp",
		"method": "GET",
		"api_class": None,
		"django_model": "Programvare, Leverandor",
		"auth_no": "Header «key» – APIKeys der navn starter med «vulnapp». Unntatt i THIS_ENV=TEST. Beskrevet som «åpen» i API-oversikten.",
		"beskrivelse_no": (
			"Returnerer programvarenavn og leverandørnavn for programvare merket "
			"til_cveoversikt_og_nyheter=True i Kartoteket. Brukes av sårbarhetsoversikten for CVE-overvåking."
		),
		"query_params": [],
		"response_note_no": "Flat JSON med to lister – ingen wrapper.",
		"fields": [
			_field("programvare", "array of string", False, "Distinct programvarenavn (til_cveoversikt_og_nyheter=True)"),
			_field("programvarelev", "array of string", False, "Distinct leverandørnavn for samme programvare-sett"),
		],
		"references": [],
		"side_effects_no": None,
		"curl_example": _curl_get("/api/vulnapp/programvare/"),
		"example_json": """{
  "programvare": ["Apache Tomcat", "Microsoft Exchange"],
  "programvarelev": ["Apache Software Foundation", "Microsoft"]
}""",
	},
	{
		"slug": "known_exploited",
		"path": "/api/vulnapp/known_exploited/",
		"name": "Known Exploited (CISA)",
		"view_name": "api_known_exploited",
		"method": "POST",
		"api_class": "ExploitedVulnerability",
		"django_model": "ExploitedVulnerability",
		"auth_no": "Header «key» – APIKeys der navn starter med «vulnapp_knownex». Unntatt i THIS_ENV=TEST.",
		"beskrivelse_no": (
			"Mottar CISA Known Exploited Vulnerabilities som Django-serialisert JSON og lagrer/oppdaterer "
			"ExploitedVulnerability-rader i Kartoteket. csrf_exempt – brukes server-til-server."
		),
		"query_params": [],
		"response_note_no": "Ved suksess: {\"message\": \"Thanks for the update!\"}. Ugyldig JSON → 400. Feil metode → 405.",
		"request_body_no": (
			"JSON-streng (i request.body) med Django serialize-format. Modellsti «vulnapp.exploitedvulnerability» "
			"erstattes internt med «systemoversikt.exploitedvulnerability» før deserialisering."
		),
		"fields": [
			_field("cve_id", "string (PK)", False, "CVE-identifikator"),
			_field("vendor_project", "string", False, "Leverandør/prosjekt"),
			_field("product", "string", False, "Produkt"),
			_field("vulnerability_name", "string", False, "Navn på sårbarhet"),
			_field("date_added", "date", False, "Dato lagt til CISA-listen"),
			_field("short_description", "string", False, "Kort beskrivelse"),
			_field("required_action", "string", False, "Påkrevd tiltak"),
			_field("due_date", "date", False, "Frist"),
			_field("known_ransomware_campaign_use", "string", False, "Kjent bruk i ransomware-kampanjer"),
		],
		"references": [],
		"side_effects_no": "Oppretter/oppdaterer ExploitedVulnerability via Django deserializer.",
		"curl_example": _curl_post("/api/vulnapp/known_exploited/"),
		"example_json": """// Request body (Django serialized JSON – truncated example)
[
  {
    "model": "vulnapp.exploitedvulnerability",
    "pk": "CVE-2024-0001",
    "fields": {
      "vendor_project": "Example Vendor",
      "product": "Example Product",
      "vulnerability_name": "Example RCE",
      "date_added": "2024-01-01",
      "short_description": "...",
      "required_action": "Apply updates",
      "due_date": "2024-02-01",
      "known_ransomware_campaign_use": "Unknown"
    }
  }
]

// Response
{"message": "Thanks for the update!"}""",
	},
]

_GRAPH_NODES = [
	{"id": "VulnApp", "name": "VulnApp", "color": "#2A2859", "size": 70, "anchor": None},
	{"id": "ipsok", "name": "/ipsok/", "color": "#F9C66B", "size": 50, "anchor": "ipsok"},
	{"id": "programvare", "name": "/programvare/", "color": "#F9C66B", "size": 50, "anchor": "programvare"},
	{"id": "known_exploited", "name": "/known_exploited/", "color": "#F9C66B", "size": 50, "anchor": "known_exploited"},
	{"id": "CMDB", "name": "CMDB / Network", "color": "#28277e", "size": 55, "anchor": "ipsok"},
	{"id": "Programvare", "name": "Programvare", "color": "#28277e", "size": 50, "anchor": "programvare"},
	{"id": "ExploitedVulnerability", "name": "ExploitedVulnerability", "color": "#28277e", "size": 55, "anchor": "known_exploited"},
]

_GRAPH_EDGES = [
	("VulnApp", "ipsok", "GET"),
	("VulnApp", "programvare", "GET"),
	("VulnApp", "known_exploited", "POST"),
	("ipsok", "CMDB", "oppslag"),
	("programvare", "Programvare", "liste"),
	("known_exploited", "ExploitedVulnerability", "lagre"),
]


def build_entity_graph():
	nodes = []
	for n in _GRAPH_NODES:
		nodes.append(json.dumps({
			"data": {
				"id": n["id"],
				"name": n["name"],
				"shape": "ellipse",
				"color": n["color"],
				"size": n["size"],
				"href": f"#api-{n['anchor']}" if n["anchor"] else None,
			}
		}))
	edges = []
	for idx, (source, target, label) in enumerate(_GRAPH_EDGES):
		edges.append(json.dumps({
			"data": {
				"id": f"edge_{idx}",
				"source": source,
				"target": target,
				"label": label,
				"linestyle": "solid",
			}
		}))
	return {"nodes": nodes, "edges": edges}
