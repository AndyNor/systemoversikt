# -*- coding: utf-8 -*-
# Change log:
# 2026-07-06: Seed IT-plattform risk framework – 8 categories and 24 subcategories for aggregation layer.

from django.core.management.base import BaseCommand
from django.db import transaction

from systemoversikt.models import (
	RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
	RiskFramework,
	RiskFrameworkNode,
)

IT_PLATTFORM_TAXONOMY = [
	{
		'nummer': 1,
		'title': 'Svikt i identitets- og tilgangsstyring (IAM & PAM)',
		'forklaring': (
			'Dette handler om hvem (mennesker eller maskiner) som har tilgang, hvordan identiteter beskyttes, '
			'og hva som skjer hvis de kompromitteres.'
		),
		'children': [
			{
				'nummer': 1,
				'title': 'Kapring av brukerkontoer',
				'forklaring': (
					'Herunder kontoovertakelse via sosial manipulering (phishing, direktørsvindel), lekkede passord, '
					'session hijacking eller manglende flerfaktorautentisering (MFA).'
				),
			},
			{
				'nummer': 2,
				'title': 'Manglende kontroll på ordinære brukere og brukertilganger',
				'forklaring': (
					'Risiko for uautorisert informasjonstilgang (ansatte med utdaterte tilganger, manglende etterlevelse '
					'av "least privilege"-prinsippet).'
				),
			},
			{
				'nummer': 3,
				'title': 'Manglende kontroll på driftspersonell og privilegerte tilganger',
				'forklaring': (
					'Risiko for misbruk, innside-sabotasje eller kritiske "blast radius"-angrep hvis en administratorkonto '
					'eller tjenestebruker (service account) kapres.'
				),
			},
			{
				'nummer': 4,
				'title': 'Manglende segmentering mellom brukere og systemer',
				'forklaring': (
					'At en kompromittert konto gir umiddelbar tilgang til å flytte seg fritt på tvers av hele organisasjonen '
					'(lateral movement mellom klienter, servere og soner).'
				),
			},
		],
	},
	{
		'nummer': 2,
		'title': 'Uforutsigbar sårbarhetsflate, teknisk gjeld og endringsrisiko',
		'forklaring': (
			'Dette handler om manglende kontroll på livssyklusen, konfigurasjonen og stabiliteten til teknologi – '
			'fra innføring til utfasing, uavhengig av om det kjøres lokalt, i skyen eller som en tjeneste.'
		),
		'children': [
			{
				'nummer': 1,
				'title': 'Mangelfull kontroll på systemer, enhetstyper og dataflyt',
				'forklaring': (
					'Inkluderer uautoriserte systemer ("skygge-IT"), ukjente enheter på nettet, og manglende oversikt '
					'over hvor data lagres eller sendes.'
				),
			},
			{
				'nummer': 2,
				'title': 'Manglende evne til å avdekke og tette sårbarheter',
				'forklaring': (
					'Svikt i sårbarhetshåndtering, mangelfull sikkerhetstesting ved innføring av nye løsninger, '
					'eller feilkonfigurerte systemer (f.eks. åpne lagringsbøtter eller ubeskyttede API-er).'
				),
			},
			{
				'nummer': 3,
				'title': 'Utilsiktede feil og ustabilitet ved endringer (Change Management)',
				'forklaring': (
					'Risiko for at oppdateringer, feilkonfigurasjoner eller arkitekturendringer introduserer nye sårbarheter '
					'eller utilsiktet river ned kritiske avhengigheter i andre systemer.'
				),
			},
			{
				'nummer': 4,
				'title': 'Driftsforstyrrelser tilknyttet aldrende plattform og systemportefølje',
				'forklaring': (
					'Teknisk gjeld og systemer som har nådd "end-of-life", hvor det ikke lenger finnes sikkerhetsoppdateringer, '
					'support eller kompatibel maskinvare.'
				),
			},
		],
	},
	{
		'nummer': 3,
		'title': 'Kompromittering av nettverksinfrastruktur og tekniske soner',
		'forklaring': (
			'Dette handler om den fysiske og logiske infrastrukturen som transporterer data og holder tjenestene tilgjengelige.'
		),
		'children': [
			{
				'nummer': 1,
				'title': 'Uvedkommende får tilgang til utstyr på tekniske nett',
				'forklaring': (
					'Fysisk eller logisk inntrenging i lukkede eller sensitive nettverkssoner '
					'(f.eks. produksjonsnett, OT/automasjon, tingenes internett).'
				),
			},
			{
				'nummer': 2,
				'title': 'Publikumstjenester utilgjengelig grunnet tjenestenektangrep (DDoS)',
				'forklaring': (
					'Angrep som overbelaster nettverkskapasitet, brannmurer eller applikasjonslag for å stanse ordinær drift '
					'eller digitale brukertjenester.'
				),
			},
			{
				'nummer': 3,
				'title': 'Plattform blir utilgjengelig grunnet sabotasjeangrep',
				'forklaring': (
					'Målrettede ødeleggelser av kjerneinfrastruktur (f.eks. sabotasje av rutingtabeller, sletting av '
					'Active Directory/katalogtjenester eller endring av DNS).'
				),
			},
		],
	},
	{
		'nummer': 4,
		'title': 'Uautorisert eksponering eller lekkasje av sensitive data',
		'forklaring': (
			'Dette handler om brudd på konfidensialitet for selve informasjonsverdien, uavhengig av hvilken kanal '
			'eller plattform dataene ligger på.'
		),
		'children': [
			{
				'nummer': 1,
				'title': 'Sensitiv informasjon på avveie via ekstern exfiltrering',
				'forklaring': (
					'Angripere som bryter seg inn og stjeler data (for løsepenger/dobbel utpressing, industrispionasje eller sabotasje).'
				),
			},
			{
				'nummer': 2,
				'title': 'Sensitiv informasjon på avveie via utilsiktet eksponering',
				'forklaring': (
					'Ansatte som lagrer sensitive data på feil sted, eller grov uaktsomhet ved bruk av eksterne verktøy. '
					'Eksempelvis innlasting av åndsverk og personopplysninger i kommersielle KI-tjenester, åpne online '
					'PDF-verktøy, eller ubeskyttede fildelingstjenester.'
				),
			},
			{
				'nummer': 3,
				'title': 'Bevisst datatyveri fra innsidere',
				'forklaring': (
					'Betrodde personer (ansatte eller konsulenter) som kopierer ut sensitiv informasjon eller immaterielle '
					'verdier (IP) for egen vinning, ny arbeidsgiver eller overlevering til tredjepart.'
				),
			},
		],
	},
	{
		'nummer': 5,
		'title': 'Leverandørkjede- og tredjepartsrisiko',
		'forklaring': (
			'Dette handler om risikoen dere arver fordi dere er en del av et digitalt økosystem og er operasjonelt '
			'avhengige av eksterne aktører.'
		),
		'children': [
			{
				'nummer': 1,
				'title': 'Kompromittering av eksterne leverandørers tilganger',
				'forklaring': (
					'Angripere som bruker en godkjent driftsleverandør, ekstern konsulent eller en betrodd tredjeparts '
					'API-integrasjon som hoppebrett inn i deres infrastruktur.'
				),
			},
			{
				'nummer': 2,
				'title': 'Driftsstans eller dataverditap hos kritiske underleverandører',
				'forklaring': (
					'At en sårbarhet eller et angrep hos en systemleverandør, ASP-partner eller databehandler gjør at dere '
					'mister kritiske kapabiliteter eller får slettet data.'
				),
			},
			{
				'nummer': 3,
				'title': 'Bortfall av internettbaserte tjenester og infrastruktur',
				'forklaring': (
					'Driftsforstyrrelser eller utilgjengelighet fordi basistjenester utenfor egen kontroll faller bort '
					'(internettforbindelse, skytjenester, telekom eller felles identitetsløsninger som BankID/ID-porten).'
				),
			},
		],
	},
	{
		'nummer': 6,
		'title': 'Geopolitisk, regulatorisk og suverenitetsrisiko',
		'forklaring': (
			'Dette handler om risiko knyttet til juss, etterlevelse, politisk ustabilitet og manglende nasjonal eller '
			'organisatorisk eierskap til egne data.'
		),
		'children': [
			{
				'nummer': 1,
				'title': 'Brudd på personvern og regulatoriske krav (f.eks. GDPR/NIS2)',
				'forklaring': (
					'Risiko for sanksjoner, millionbøter og omdømmetap som følge av mangelfull etterlevelse av '
					'sikkerhetslovgivning eller ulovlig overføring av data til tredjeland.'
				),
			},
			{
				'nummer': 2,
				'title': 'Politisk risiko knyttet til leverandørtilhørighet',
				'forklaring': (
					'Risiko for tvungen utskifting av kritisk teknologi, sanksjoner, eller tap av support fordi en leverandør '
					'er underlagt jurisdiksjonen til stater vi ikke har et sikkerhetssamarbeid med.'
				),
			},
			{
				'nummer': 3,
				'title': 'Manglende digital suverenitet',
				'forklaring': (
					'Risiko for å miste kontroll over eller tilgang til samfunnskritiske data og systemer fordi de driftes '
					'i jurisdiksjoner der utenlandske myndigheter kan kreve innsyn eller stanse tjenesten (Cloud Act, endrede eksportlisenser).'
				),
			},
		],
	},
	{
		'nummer': 7,
		'title': 'Svikt i sikkerhetsovervåking og deteksjonsevne',
		'forklaring': (
			'Dette handler om organisasjonens evne til å fange opp unormale hendelser før de eskalerer til en krise.'
		),
		'children': [
			{
				'nummer': 1,
				'title': 'Mangler i sikkerhetsovervåkningen',
				'forklaring': (
					'At pågående angrep, unormal dataflyt, skadevare eller mistenkelig kontoaktivitet ikke fanges opp '
					'fordi man mangler logger, sikt (visibility) eller alarmsystemer.'
				),
			},
			{
				'nummer': 2,
				'title': 'For sen eller mangelfull triagering av sikkerhetsvarsler',
				'forklaring': (
					'At kritiske alarmer drukner i "støy" (false positives), eller at organisasjonen mangler kapasitet til '
					'å analysere og reagere på indikasjoner på et pågående angrep.'
				),
			},
		],
	},
	{
		'nummer': 8,
		'title': 'Svikt i responskapasitet, krisehåndtering og gjenoppretting',
		'forklaring': (
			'Dette handler om organisasjonens evne til å begrense skadeomfanget og redde stumpene når det uunngåelige først har skjedd.'
		),
		'children': [
			{
				'nummer': 1,
				'title': 'Manglende evne til å håndtere hendelser (Incident Response)',
				'forklaring': (
					'Uklar ansvarsfordeling, utdaterte beredskapsplaner eller manglende verktøy som gjør at et isolert angrep '
					'får eskalere unødvendig.'
				),
			},
			{
				'nummer': 2,
				'title': 'Mangelfull evne til gjenoppretting (Disaster Recovery)',
				'forklaring': (
					'Svikt i backup-rutiner, manglende offline/skrivebeskyttede kopier (som beskytter mot ransomware) eller '
					'utestede rutiner som fører til langvarig nedetid og permanent tap av forretningsdata.'
				),
			},
		],
	},
]


class Command(BaseCommand):
	help = 'Seed or update the IT-plattform risk framework taxonomy (8+24 nodes).'

	def handle(self, *args, **options):
		with transaction.atomic():
			framework, created = RiskFramework.objects.update_or_create(
				slug='it-plattform',
				defaults={
					'title': 'IT-plattform',
					'beskrivelse': (
						'Høynivå risikoscenarioer for IT-plattformen – brukes til å aggregere operative '
						'risikovurderinger opp mot ledelsen.'
					),
					'is_active': True,
				},
			)
			action = 'Created' if created else 'Updated'
			self.stdout.write('%s framework: %s' % (action, framework.title))

			for cat_data in IT_PLATTFORM_TAXONOMY:
				category, _ = RiskFrameworkNode.objects.update_or_create(
					framework=framework,
					parent=None,
					nummer=cat_data['nummer'],
					defaults={
						'title': cat_data['title'],
						'forklaring': cat_data['forklaring'],
						'status': RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
						'rekkefolge': cat_data['nummer'],
					},
				)
				for child_data in cat_data['children']:
					RiskFrameworkNode.objects.update_or_create(
						framework=framework,
						parent=category,
						nummer=child_data['nummer'],
						defaults={
							'title': child_data['title'],
							'forklaring': child_data['forklaring'],
							'status': RISK_FRAMEWORK_NODE_STATUS_ACTIVE,
							'rekkefolge': child_data['nummer'],
						},
					)

		self.stdout.write(self.style.SUCCESS('IT-plattform taxonomy seeded (%d categories).' % len(IT_PLATTFORM_TAXONOMY)))
