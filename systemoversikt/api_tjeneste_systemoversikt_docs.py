# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: Developer docs reminder – keep ENDPOINTS in sync when API/model output changes (url name: api_tjeneste_systemoversikt_docs).
# 2026-06-23: API documentation metadata for Tjeneste- og systemoversikt developer page.
import json

BASE_URL = "https://kartoteket.oslo.kommune.no"

AUTH_INFO = {
	"header_name": "key",
	"api_key_name": "tjenester_og_systemer",
	"description_no": (
		"Alle endepunktene krever HTTP-header «key» med en API-nøkkel registrert i Kartoteket "
		"(APIKeys der navn er «tjenester_og_systemer»). Kontakt Kartotek-forvalter for å få utstedt nøkkel. "
		"Nøkkelen skal aldri committes til kildekode eller deles i dokumentasjon."
	),
	"error_403": '{"message": "Missing or wrong key. Supply HTTP header \'key\'", "data": null}',
}

RESPONSE_WRAPPER = {
	"beskrivelse": "string – kort beskrivelse av endepunktet",
	"antall": "integer – antall objekter i data",
	"kjoretid": "string – server-side kjøretid i sekunder",
	"data": "array – liste med objekter (se felttabell per endepunkt)",
}

REFERENCE_PATTERN = {
	"class": "string – klassenavn i API-et",
	"id": "integer – primærnøkkel i Kartoteket",
}


def _curl(path):
	return (
		f'curl -s -H "key: <API_KEY>" "{BASE_URL}{path}"'
	)


def _field(name, ftype, nullable, description_no):
	return {
		"name": name,
		"type": ftype,
		"nullable": nullable,
		"description_no": description_no,
	}


# Sync order matches dependency chain for initial import.
SYNC_GUIDE = [
	{
		"step": 1,
		"path": "/api/virksomheter/",
		"description_no": "Grunnleggende organisasjonsenheter. Selv-refererende hierarki via overordnede_virksomheter.",
	},
	{
		"step": 2,
		"path": "/api/leverandorer/",
		"description_no": "Leverandører uten avhengigheter til andre API-klasser.",
	},
	{
		"step": 3,
		"path": "/api/systemtyper/",
		"description_no": "Klassifiseringstyper for systemer (M2M mot System).",
	},
	{
		"step": 4,
		"path": "/api/driftsplattformer/",
		"description_no": "Driftsplattformer (JSON-klasse Driftsmodell). Krever Virksomhet for eier_virksomhet.",
	},
	{
		"step": 5,
		"path": "/api/programvarer/",
		"description_no": "Programvarer. Resolve leverandor mot /api/leverandorer/.",
	},
	{
		"step": 6,
		"path": "/api/kritiske_funksjoner/",
		"description_no": "DSB kritiske funksjoner (forelder til KritiskKapabilitet).",
	},
	{
		"step": 7,
		"path": "/api/kritiske_kapabiliteter/",
		"description_no": "DSB kritiske kapabiliteter. Resolve funksjon mot forrige endepunkt.",
	},
	{
		"step": 8,
		"path": "/api/los/",
		"description_no": "LOS-begreper. Selv-refererende via ontologi og overordnede_begreper.",
	},
	{
		"step": 9,
		"path": "/api/systemer/",
		"description_no": "Sentral hub. Resolve alle {class, id}-referanser mot oppslagstabellene over.",
	},
	{
		"step": 10,
		"path": "/api/systembruk/",
		"description_no": "Kobling virksomhet ↔ system (kun ibruk=True). Krever System og Virksomhet.",
	},
	{
		"step": 11,
		"path": "/api/systemintegrasjoner/",
		"description_no": "Integrasjoner mellom systemer. Krever System for kilde og destinasjon.",
	},
]

SYNC_NOTES_NO = (
	"Bygg oppslagstabeller (dict keyed by (class, id)) mens du importerer. "
	"Referanse-felter i API-et inneholder kun class og id – full informasjon må hentes fra riktig endepunkt. "
	"Ved full reimport anbefales rekkefølgen over. Det finnes per i dag ingen delta-sync eller paginering."
)

LIMITATIONS = [
	{
		"title": "Ingen paginering eller filtrering",
		"description_no": "Alle endepunkter returnerer full dump. /api/systemer/ kan bli tung og ta flere sekunder.",
	},
	{
		"title": "Ingen inkrementell sync",
		"description_no": "sist_oppdatert finnes på enkelte objekter, men det finnes ingen query-param for delta-henting.",
	},
	{
		"title": "Navneinkonsistens Driftsplattform / Driftsmodell",
		"description_no": "URL er /api/driftsplattformer/, JSON-klassen er Driftsmodell, mens System.driftsplattform.class er Driftsplattform.",
	},
	{
		"title": "Kun aktive systembruk",
		"description_no": "/api/systembruk/ filtrerer ibruk=True. Avviklede bruk returneres ikke.",
	},
	{
		"title": "Referanse-oppslag kreves",
		"description_no": "Klienten må cache alle oppslagstabeller og joine på {class, id}.",
	},
	{
		"title": "N+1 i enkelte endepunkter",
		"description_no": "api_programvarer, api_los og api_virksomheter gjør DB-kall per rad (ikke optimalisert som api_systemer_optimized).",
	},
	{
		"title": "Kjent feil: overordnede_virksomheter",
		"description_no": "/api/virksomheter/ returnerer feil id i overordnede_virksomheter (bruker egen pk i stedet for forelder). Verifiser mot Kartotek-UI inntil fikset.",
	},
	{
		"title": "service_offerings",
		"description_no": "Eksponeres som lister på System (service_offerings_external_id, service_offerings_navn), men finnes ikke som eget endepunkt.",
	},
	{
		"title": "Logging",
		"description_no": "Alle kall logges i ApplicationLog med klient-IP og kjøretid.",
	},
	{
		"title": "Eldre API",
		"description_no": "/systemer/api/ (nøkkel api_systemer) er forenklet og bør ikke brukes til ny løsning.",
	},
]

REF = "object {class, id} eller null"
REF_LIST = "array of {class, id}"
REF_VIRKSOMHET = f"{REF} → oppslag i /api/virksomheter/"
REF_SYSTEM = f"{REF} → oppslag i /api/systemer/"
REF_LEVERANDOR = f"{REF_LIST} → oppslag i /api/leverandorer/"
REF_DRIFTSMODELL = f"{REF} → oppslag i /api/driftsplattformer/ (class Driftsmodell)"
REF_SYSTEMTYPE = f"{REF_LIST} → oppslag i /api/systemtyper/"
REF_PROGRAMVARE = f"{REF_LIST} → oppslag i /api/programvarer/"
REF_LOS = f"{REF_LIST} → oppslag i /api/los/"
REF_KRITISK_KAP = f"{REF_LIST} → oppslag i /api/kritiske_kapabiliteter/"
REF_KRITISK_FUNKSJON = f"{REF} → oppslag i /api/kritiske_funksjoner/"

ENDPOINTS = [
	{
		"slug": "virksomheter",
		"path": "/api/virksomheter/",
		"name": "Virksomheter",
		"api_class": "Virksomhet",
		"django_model": "Virksomhet",
		"beskrivelse_no": (
			"Virksomhet-objekter fra Kartoteket. For oversikt over hvilke systemer en virksomhet bruker, "
			"se /api/systembruk/."
		),
		"fields": [
			_field("class", "string", False, "Alltid «Virksomhet»"),
			_field("id", "integer", False, "Primærnøkkel"),
			_field("opprettet", "datetime", True, "Opprettelsestidspunkt"),
			_field("sist_oppdatert", "datetime", False, "Sist endret"),
			_field("virksomhetsnavn", "string", False, "Fullt virksomhetsnavn"),
			_field("orgnummer", "string", True, "Organisasjonsnummer"),
			_field("virksomhetsforkortelse", "string", True, "Forkortelse (f.eks. BYR, FIN)"),
			_field("gamle_virksomhetsforkortelser", "string", True, "Historiske forkortelser"),
			_field("klientplattform", "string", True, "Resultatenhet (display-verdi)"),
			_field("office365_tenant", "string", True, "Office 365 tenant (display-verdi)"),
			_field("intranett_url", "string", True, "URL til intranett"),
			_field("www_url", "string", True, "URL til nettside"),
			_field("rolle_virksomhetsleder", "string (email)", True, "E-post virksomhetsleder fra HR"),
			_field("rolle_uke_hovedkontakt", "array of string (email)", False, "UKE hovedkontakter"),
			_field("rolle_ikt_kontakt", "array of string (email)", False, "IKT-kontakter"),
			_field("rolle_autoriserte_bestillere_infotorg", "array of string (email)", False, "Autoriserte bestillere Infotorg"),
			_field("rolle_autoriserte_bestillere_uketjenester", "array of string (email)", False, "Autoriserte bestillere UKE-tjenester"),
			_field("rolle_personvernkoordinator", "array of string (email)", False, "Personvernkoordinatorer"),
			_field("rolle_informasjonssikkerhetskoordinator", "array of string (email)", False, "Informasjonssikkerhetskoordinatorer"),
			_field("rolle_uke_kam", "array of string (email)", False, "UKE KAM-kontakter"),
			_field("rolle_arkitekturkontakter", "array of string (email)", False, "Arkitekturkontakter"),
			_field("rolle_ks_fiks_admins", "array of string (email)", False, "KS Fiks-administratorer"),
			_field("overordnede_virksomheter", REF_LIST, False, "Foreldre i virksomhetshierarki (se kjent feil)"),
		],
		"references": [
			"overordnede_virksomheter → /api/virksomheter/ (self-reference)",
		],
		"curl_example": _curl("/api/virksomheter/"),
		"example_json": """{
  "beskrivelse": "Virksomhet-objekter fra Kartoteket...",
  "antall": 42,
  "kjoretid": "0.312",
  "data": [
    {
      "class": "Virksomhet",
      "id": 1,
      "opprettet": "2020-01-15T10:00:00+01:00",
      "sist_oppdatert": "2025-06-01T08:30:00+02:00",
      "virksomhetsnavn": "Eksempel byråd",
      "orgnummer": "000000000",
      "virksomhetsforkortelse": "EKB",
      "gamle_virksomhetsforkortelser": null,
      "klientplattform": "UKE",
      "office365_tenant": "oslo.kommune.no",
      "intranett_url": "https://intranett.example.oslo.kommune.no",
      "www_url": "https://www.example.oslo.kommune.no",
      "rolle_virksomhetsleder": "leder@example.oslo.kommune.no",
      "rolle_uke_hovedkontakt": ["kontakt@example.oslo.kommune.no"],
      "rolle_ikt_kontakt": [],
      "overordnede_virksomheter": [{"class": "Virksomhet", "id": 2}]
    }
  ]
}""",
	},
	{
		"slug": "leverandorer",
		"path": "/api/leverandorer/",
		"name": "Leverandører",
		"api_class": "Leverandor",
		"django_model": "Leverandor",
		"beskrivelse_no": "Leverandør-objekter fra Kartoteket.",
		"fields": [
			_field("class", "string", False, "Alltid «Leverandor»"),
			_field("id", "integer", False, "Primærnøkkel"),
			_field("opprettet", "null", True, "Alltid null i API-et"),
			_field("sist_oppdatert", "datetime", False, "Sist endret"),
			_field("navn", "string", False, "Leverandørnavn"),
			_field("kontaktinfo", "string", True, "Kontaktinformasjon (fritekst)"),
			_field("orgnummer", "string", True, "Organisasjonsnummer"),
			_field("notater", "string", True, "Notater"),
		],
		"references": [],
		"curl_example": _curl("/api/leverandorer/"),
		"example_json": """{
  "beskrivelse": "Leverandør-objekter fra Karoteket.",
  "antall": 100,
  "kjoretid": "0.05",
  "data": [
    {
      "class": "Leverandor",
      "id": 10,
      "opprettet": null,
      "sist_oppdatert": "2024-03-01T12:00:00+01:00",
      "navn": "Eksempel AS",
      "kontaktinfo": "support@example.com",
      "orgnummer": "999999999",
      "notater": null
    }
  ]
}""",
	},
	{
		"slug": "systemtyper",
		"path": "/api/systemtyper/",
		"name": "Systemtyper",
		"api_class": "Systemtype",
		"django_model": "Systemtype",
		"beskrivelse_no": (
			"Systemtype-objekter fra Kartoteket. Angir hva slags egenskaper systemer har. "
			"Mange-til-mange mot System."
		),
		"fields": [
			_field("class", "string", False, "Alltid «Systemtype»"),
			_field("id", "integer", False, "Primærnøkkel"),
			_field("opprettet", "null", True, "Alltid null"),
			_field("sist_oppdatert", "datetime", False, "Sist endret"),
			_field("navn", "string", False, "Kategorinavn"),
			_field("definisjon", "string", True, "Tekstlig definisjon"),
			_field("bool_har_url", "boolean", False, "Typen forutsetter URL på system"),
			_field("bool_er_infrastruktur", "boolean", False, "Er infrastrukturtype"),
			_field("bool_er_integrasjon", "boolean", False, "Er integrasjonstype"),
		],
		"references": [],
		"curl_example": _curl("/api/systemtyper/"),
		"example_json": """{
  "antall": 15,
  "kjoretid": "0.01",
  "data": [
    {
      "class": "Systemtype",
      "id": 3,
      "opprettet": null,
      "sist_oppdatert": "2023-01-01T00:00:00+01:00",
      "navn": "Forretningsapplikasjon",
      "definisjon": "Applikasjon som støtter forretningsprosesser",
      "bool_har_url": true,
      "bool_er_infrastruktur": false,
      "bool_er_integrasjon": false
    }
  ]
}""",
	},
	{
		"slug": "driftsplattformer",
		"path": "/api/driftsplattformer/",
		"name": "Driftsplattformer",
		"api_class": "Driftsmodell",
		"django_model": "Driftsmodell",
		"beskrivelse_no": (
			"Driftsplattform-objekter fra Kartoteket (JSON-klasse Driftsmodell). "
			"Systemer kan bare være koblet til én driftsplattform."
		),
		"fields": [
			_field("class", "string", False, "Alltid «Driftsmodell» (merk: URL sier driftsplattformer)"),
			_field("id", "integer", False, "Primærnøkkel"),
			_field("opprettet", "null", True, "Alltid null"),
			_field("sist_oppdatert", "datetime", False, "Sist endret"),
			_field("navn", "string", False, "Plattformnavn"),
			_field("eier_virksomhet", REF, True, REF_VIRKSOMHET),
			_field("kommentar", "string", True, "Kommentar"),
			_field("plattformklassifisering", "object {id, navn}", False, "Type plattform (display)"),
			_field("overordnet_plattform", REF, True, "Foreldreplattform (self-reference, class Driftsmodell)"),
			_field("bool_utviklingsplattform", "boolean", False, "Er utviklingsplattform"),
			_field("bool_samarbeidspartner", "boolean", False, "Er samarbeidspartner"),
			_field("bool_er_saas", "boolean", False, "Er SaaS"),
		],
		"references": [
			"eier_virksomhet → /api/virksomheter/",
			"overordnet_plattform → /api/driftsplattformer/",
		],
		"curl_example": _curl("/api/driftsplattformer/"),
		"example_json": """{
  "data": [
    {
      "class": "Driftsmodell",
      "id": 5,
      "navn": "Azure Public",
      "eier_virksomhet": {"class": "Virksomhet", "id": 1},
      "plattformklassifisering": {"id": 2, "navn": "Offentlig sky"},
      "overordnet_plattform": null,
      "bool_utviklingsplattform": false,
      "bool_samarbeidspartner": false,
      "bool_er_saas": false
    }
  ]
}""",
	},
	{
		"slug": "programvarer",
		"path": "/api/programvarer/",
		"name": "Programvarer",
		"api_class": "Programvare",
		"django_model": "Programvare",
		"beskrivelse_no": "Programvare-objekter fra Kartoteket. Et system kan bestå av flere programvarer.",
		"fields": [
			_field("class", "string", False, "Alltid «Programvare»"),
			_field("id", "integer", False, "Primærnøkkel"),
			_field("opprettet", "null", True, "Alltid null"),
			_field("sist_oppdatert", "datetime", False, "Sist endret"),
			_field("navn", "string", False, "Programvarenavn"),
			_field("alias", "string", True, "Alternative navn"),
			_field("beskrivelse", "string", True, "Beskrivelse"),
			_field("leverandor", REF_LIST, False, REF_LEVERANDOR),
		],
		"references": ["leverandor → /api/leverandorer/"],
		"curl_example": _curl("/api/programvarer/"),
		"example_json": """{
  "data": [
    {
      "class": "Programvare",
      "id": 20,
      "navn": "PostgreSQL",
      "alias": "postgres",
      "beskrivelse": "Relasjonsdatabase",
      "leverandor": [{"class": "Leverandor", "id": 10}]
    }
  ]
}""",
	},
	{
		"slug": "kritiske_funksjoner",
		"path": "/api/kritiske_funksjoner/",
		"name": "Kritiske funksjoner",
		"api_class": "KritiskFunksjon",
		"django_model": "KritiskFunksjon",
		"beskrivelse_no": (
			"Kritisk funksjon-objekter fra DSB-rammeverk, manuelt registrert i Kartoteket. "
			"Forelder til KritiskKapabilitet."
		),
		"fields": [
			_field("class", "string", False, "Alltid «KritiskFunksjon»"),
			_field("id", "integer", False, "Primærnøkkel"),
			_field("opprettet", "null", True, "Alltid null"),
			_field("sist_oppdatert", "null", True, "Alltid null"),
			_field("navn", "string", False, "Funksjonsnavn"),
			_field("kategori", "string", True, "Kategori (display-verdi)"),
		],
		"references": [],
		"curl_example": _curl("/api/kritiske_funksjoner/"),
		"example_json": """{
  "data": [
    {
      "class": "KritiskFunksjon",
      "id": 1,
      "opprettet": null,
      "sist_oppdatert": null,
      "navn": "Ledelse og styring",
      "kategori": "Samfunnsfunksjon"
    }
  ]
}""",
	},
	{
		"slug": "kritiske_kapabiliteter",
		"path": "/api/kritiske_kapabiliteter/",
		"name": "Kritiske kapabiliteter",
		"api_class": "KritiskKapabilitet",
		"django_model": "KritiskKapabilitet",
		"beskrivelse_no": (
			"Kritisk kapabilitet-objekter fra DSB-rammeverk. Kobles til System via dsb_kapabilitet."
		),
		"fields": [
			_field("class", "string", False, "Alltid «KritiskKapabilitet»"),
			_field("id", "integer", False, "Primærnøkkel"),
			_field("opprettet", "null", True, "Alltid null"),
			_field("sist_oppdatert", "null", True, "Alltid null"),
			_field("navn", "string", False, "Kapabilitetsnavn"),
			_field("funksjon", REF, True, REF_KRITISK_FUNKSJON),
			_field("kategori", "string", True, "Beskrivelse/kategori (fra model.beskrivelse)"),
		],
		"references": ["funksjon → /api/kritiske_funksjoner/"],
		"curl_example": _curl("/api/kritiske_kapabiliteter/"),
		"example_json": """{
  "data": [
    {
      "class": "KritiskKapabilitet",
      "id": 7,
      "navn": "Beslutningsstøtte",
      "funksjon": {"class": "KritiskFunksjon", "id": 1},
      "kategori": "Underfunksjon X"
    }
  ]
}""",
	},
	{
		"slug": "los",
		"path": "/api/los/",
		"name": "LOS",
		"api_class": "LOS",
		"django_model": "LOS",
		"beskrivelse_no": (
			"LOS rammeverk-objekter fra Kartoteket (DigDir felles vokabular). "
			"Se digdir.no for offisiell dokumentasjon av LOS."
		),
		"fields": [
			_field("class", "string", False, "Alltid «LOS»"),
			_field("id", "integer", False, "Primærnøkkel i Kartoteket"),
			_field("opprettet", "null", True, "Alltid null"),
			_field("sist_oppdatert", "datetime", False, "Sist endret"),
			_field("los_external_id", "string", True, "Unik LOS-id (unik_id)"),
			_field("begrep", "string", False, "Begrep/verdi"),
			_field("ontologi", REF, True, "Kategori/ontologi (self-reference)"),
			_field("overordnede_begreper", REF_LIST, False, "Foreldrebegreper i hierarkiet"),
			_field("bool_active", "boolean", False, "Er aktiv"),
		],
		"references": [
			"ontologi → /api/los/",
			"overordnede_begreper → /api/los/",
		],
		"curl_example": _curl("/api/los/"),
		"example_json": """{
  "data": [
    {
      "class": "LOS",
      "id": 100,
      "los_external_id": "http://example.los/id/123",
      "begrep": "Skole og utdanning",
      "ontologi": {"class": "LOS", "id": 50},
      "overordnede_begreper": [{"class": "LOS", "id": 49}],
      "bool_active": true
    }
  ]
}""",
	},
	{
		"slug": "systemer",
		"path": "/api/systemer/",
		"name": "Systemer",
		"api_class": "System",
		"django_model": "System",
		"beskrivelse_no": (
			"System-objekter fra Kartoteket. For oversikt over virksomheter som bruker systemet, "
			"se /api/systembruk/. systemforvalter_orgenhet_ouid er ID fra HR – hr_navn kan ignoreres "
			"ved integrasjon mot HR direkte."
		),
		"fields": [
			_field("class", "string", False, "Alltid «System»"),
			_field("id", "integer", False, "Primærnøkkel"),
			_field("kartotek_url", "string", False, "Dyp lenke til systemdetalj i Kartoteket"),
			_field("opprettet", "datetime", True, "Opprettelsestidspunkt"),
			_field("sist_oppdatert", "datetime", False, "Sist endret"),
			_field("navn", "string", False, "Systemnavn"),
			_field("visningsnavn", "string", False, "Visningsnavn (inkl. ev. virksomhetsforkortelse)"),
			_field("alias", "string", True, "Alternative navn"),
			_field("beskrivelse", "string", True, "Systembeskrivelse"),
			_field("livslop_status", "string", True, "Livsløpstatus (display)"),
			_field("ibruk", "boolean", False, "Er systemet i bruk (beregnet)"),
			_field("urler", "array of string", False, "Domener/URL-er"),
			_field("systemtyper", REF_LIST, False, REF_SYSTEMTYPE),
			_field("programvarer", REF_LIST, False, REF_PROGRAMVARE),
			_field("eierskapsmodell", "string", True, "Systemeierskapsmodell (display)"),
			_field("systemeier_virksomhet", REF, True, REF_VIRKSOMHET),
			_field("systemeier_kontaktpersoner", "array of string (email)", False, "Systemeier-kontakter"),
			_field("systemforvalter_virksomhet", REF, True, REF_VIRKSOMHET),
			_field("systemforvalter_kontaktpersoner", "array of string (email)", False, "Systemforvalter-kontakter"),
			_field("systemforvalter_orgenhet_ouid", "object {prk_ouid, hr_navn, hr_ouid}", True, "HR orgenhet for forvalter"),
			_field("forvaltning_epost", "string", True, "Fellesspost for forvaltergruppe"),
			_field("superbrukere", "string", True, "Superbrukere (fritekst)"),
			_field("nokkelpersonell", "string", True, "Nøkkelpersonell (fritekst)"),
			_field("driftsplattform", "object {class, id}", True, "Referanse (class Driftsplattform) → /api/driftsplattformer/"),
			_field("bool_egenutviklet", "boolean", False, "Er egenutviklet"),
			_field("bool_saas", "boolean", False, "Er SaaS (fra driftsplattform)"),
			_field("plattformklassifisering", "object {id, navn}", True, "Plattformtype"),
			_field("konfidensialitet", "string", True, "Konfidensialitetsvurdering"),
			_field("tilgjengelighet", "string", True, "Tilgjengelighetsvurdering"),
			_field("integritetsvurdering", "string", True, "Integritetsvurdering"),
			_field("teknisk_egnethet", "string", True, "Teknisk egnethet (display)"),
			_field("strategisk_egnethet", "string", True, "Strategisk egnethet (display)"),
			_field("funksjonell_egnethet", "string", True, "Funksjonell egnethet (display)"),
			_field("kommune_los", REF_LIST, False, REF_LOS),
			_field("dsb_kapabilitet", REF_LIST, False, REF_KRITISK_KAP),
			_field("systemleverandor", REF_LIST, False, REF_LEVERANDOR),
			_field("basisdriftleverandor", REF_LIST, False, REF_LEVERANDOR),
			_field("applikasjonsdriftleverandor", REF_LIST, False, REF_LEVERANDOR),
			_field("service_offerings_external_id", "array of string", False, "CMDB BSS external ref (ingen eget endepunkt)"),
			_field("service_offerings_navn", "array of string", False, "CMDB service offering navn"),
		],
		"references": [
			"systemeier_virksomhet, systemforvalter_virksomhet → /api/virksomheter/",
			"driftsplattform → /api/driftsplattformer/ (class i System er Driftsplattform, oppslag class Driftsmodell)",
			"systemtyper → /api/systemtyper/",
			"programvarer → /api/programvarer/",
			"kommune_los → /api/los/",
			"dsb_kapabilitet → /api/kritiske_kapabiliteter/",
			"systemleverandor, basisdriftleverandor, applikasjonsdriftleverandor → /api/leverandorer/",
		],
		"curl_example": _curl("/api/systemer/"),
		"example_json": """{
  "beskrivelse": "System-objekter fra Kartoteket...",
  "antall": 500,
  "kjoretid": "2.145",
  "data": [
    {
      "class": "System",
      "id": 42,
      "kartotek_url": "https://kartoteket.oslo.kommune.no/systemer/detaljer/42/",
      "navn": "Eksempelsystem",
      "visningsnavn": "EKS (Eksempelsystem)",
      "ibruk": true,
      "systemtyper": [{"class": "Systemtype", "id": 3}],
      "systemeier_virksomhet": {"class": "Virksomhet", "id": 1},
      "systemforvalter_virksomhet": {"class": "Virksomhet", "id": 1},
      "driftsplattform": {"class": "Driftsplattform", "id": 5},
      "kommune_los": [{"class": "LOS", "id": 100}],
      "dsb_kapabilitet": [{"class": "KritiskKapabilitet", "id": 7}]
    }
  ]
}""",
	},
	{
		"slug": "systembruk",
		"path": "/api/systembruk/",
		"name": "Systembruk",
		"api_class": "SystemBruk",
		"django_model": "SystemBruk",
		"beskrivelse_no": (
			"SystemBruk-objekter fra Kartoteket – kobling mellom virksomhet (brukergruppe) og system. "
			"Kun rader der ibruk=True returneres."
		),
		"fields": [
			_field("class", "string", False, "Alltid «SystemBruk»"),
			_field("id", "integer", False, "Primærnøkkel"),
			_field("kommentar", "string", True, "Kommentar til bruken"),
			_field("antall_brukere", "integer", True, "Antall brukere"),
			_field("system", REF, False, REF_SYSTEM),
			_field("virksomhet", REF, False, "Brukergruppe → /api/virksomheter/"),
			_field("lokal_konfidensialitetsvurdering", "string", True, "Lokal ROS – konfidensialitet"),
			_field("lokal_integritetsvurdering", "string", True, "Lokal ROS – integritet"),
			_field("lokal_tilgjengelighetsvurdering", "string", True, "Lokal ROS – tilgjengelighet"),
			_field("lokal_systemforvalter_virksomhet", REF, True, REF_VIRKSOMHET),
			_field("lokal_systemforvalter_kontaktpersoner", "array of string (email)", False, "Lokal forvalter (personer)"),
			_field("lokal_systemeier_kontaktpersoner", "array of string (email)", False, "Lokal eier (personer)"),
		],
		"references": [
			"system → /api/systemer/",
			"virksomhet, lokal_systemforvalter_virksomhet → /api/virksomheter/",
		],
		"curl_example": _curl("/api/systembruk/"),
		"example_json": """{
  "data": [
    {
      "class": "SystemBruk",
      "id": 200,
      "kommentar": "Brukes til saksbehandling",
      "antall_brukere": 50,
      "system": {"class": "System", "id": 42},
      "virksomhet": {"class": "Virksomhet", "id": 3},
      "lokal_konfidensialitetsvurdering": "Begrenset",
      "lokal_systemforvalter_virksomhet": {"class": "Virksomhet", "id": 3},
      "lokal_systemforvalter_kontaktpersoner": ["forvalter@example.oslo.kommune.no"]
    }
  ]
}""",
	},
	{
		"slug": "systemintegrasjoner",
		"path": "/api/systemintegrasjoner/",
		"name": "Systemintegrasjoner",
		"api_class": "SystemIntegration",
		"django_model": "SystemIntegration",
		"beskrivelse_no": (
			"Systemintegrasjon-objekter fra Kartoteket. Beskriver avhengigheter mellom to systemer."
		),
		"fields": [
			_field("class", "string", False, "Alltid «SystemIntegration»"),
			_field("id", "integer", False, "Primærnøkkel"),
			_field("opprettet", "datetime", True, "Opprettelsestidspunkt"),
			_field("sist_oppdatert", "datetime", False, "Sist endret"),
			_field("system_kilde", REF, False, REF_SYSTEM),
			_field("system_destinasjon", REF, False, REF_SYSTEM),
			_field("integrasjonstype", "object {id, navn}", False, "Type integrasjon"),
			_field("bool_personopplysninger", "boolean", False, "Overfører personopplysninger"),
			_field("beskrivelse", "string", True, "Beskrivelse av integrasjonen"),
		],
		"references": [
			"system_kilde, system_destinasjon → /api/systemer/",
		],
		"curl_example": _curl("/api/systemintegrasjoner/"),
		"example_json": """{
  "data": [
    {
      "class": "SystemIntegration",
      "id": 300,
      "system_kilde": {"class": "System", "id": 42},
      "system_destinasjon": {"class": "System", "id": 43},
      "integrasjonstype": {"id": 1, "navn": "API"},
      "bool_personopplysninger": true,
      "beskrivelse": "Overføring av saksdata"
    }
  ]
}""",
	},
]

# Cytoscape entity-relationship graph (static).
_GRAPH_NODES = [
	{"id": "System", "name": "System", "color": "#2A2859", "size": 80, "anchor": "systemer"},
	{"id": "Virksomhet", "name": "Virksomhet", "color": "#F9C66B", "size": 55, "anchor": "virksomheter"},
	{"id": "SystemBruk", "name": "SystemBruk", "color": "#FF8274", "size": 55, "anchor": "systembruk"},
	{"id": "Systemtype", "name": "Systemtype", "color": "#acacbf", "size": 45, "anchor": "systemtyper"},
	{"id": "Programvare", "name": "Programvare", "color": "#acacbf", "size": 45, "anchor": "programvarer"},
	{"id": "Driftsmodell", "name": "Driftsmodell", "color": "#28277e", "size": 50, "anchor": "driftsplattformer"},
	{"id": "Leverandor", "name": "Leverandor", "color": "#acacbf", "size": 45, "anchor": "leverandorer"},
	{"id": "SystemIntegration", "name": "SystemIntegration", "color": "#FF8274", "size": 50, "anchor": "systemintegrasjoner"},
	{"id": "LOS", "name": "LOS", "color": "#acacbf", "size": 45, "anchor": "los"},
	{"id": "KritiskFunksjon", "name": "KritiskFunksjon", "color": "#acacbf", "size": 45, "anchor": "kritiske_funksjoner"},
	{"id": "KritiskKapabilitet", "name": "KritiskKapabilitet", "color": "#acacbf", "size": 45, "anchor": "kritiske_kapabiliteter"},
]

_GRAPH_EDGES = [
	("System", "Virksomhet", "eier/forvalter"),
	("System", "Driftsmodell", "driftsplattform"),
	("System", "Systemtype", "M2M"),
	("System", "Programvare", "M2M"),
	("System", "LOS", "M2M"),
	("System", "KritiskKapabilitet", "M2M"),
	("System", "Leverandor", "leverandør"),
	("SystemBruk", "System", "FK"),
	("SystemBruk", "Virksomhet", "brukergruppe"),
	("SystemIntegration", "System", "kilde/dest"),
	("Programvare", "Leverandor", "M2M"),
	("Driftsmodell", "Virksomhet", "eier"),
	("Driftsmodell", "Driftsmodell", "overordnet"),
	("KritiskKapabilitet", "KritiskFunksjon", "FK"),
	("LOS", "LOS", "hierarki"),
	("Virksomhet", "Virksomhet", "overordnet"),
]


def build_entity_graph():
	"""Return cytoscape-ready node/edge JSON strings for the template."""
	nodes = []
	for n in _GRAPH_NODES:
		nodes.append(json.dumps({
			"data": {
				"id": n["id"],
				"name": n["name"],
				"shape": "ellipse",
				"color": n["color"],
				"size": n["size"],
				"href": f"#api-{n['anchor']}",
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
