# -*- coding: utf-8 -*-
# Change log:
# 2026-06-23: BH_CHECK_META – beskrivelser av hva hver sjekk ser etter og risiko.
# 2026-06-23: BloodHound preventive check constants (BH-01–BH-07).
from systemoversikt.models import PRIVILEGERTE_GRUPPER_AD

DCSYNC_RIGHTS = frozenset({'GetChanges', 'GetChangesAll'})
DANGEROUS_DOMAIN_RIGHTS = frozenset({'GenericAll', 'WriteDacl', 'WriteOwner'})

DANGEROUS_ACL_RIGHTS = frozenset({
	'GenericAll',
	'WriteOwner',
	'WriteDacl',
	'AddMember',
	'ForceChangePassword',
	'AllExtendedRights',
})

GPO_WRITE_RIGHTS = frozenset({'GenericAll', 'WriteOwner', 'WriteDacl'})

EXTRA_PRIVILEGED_GROUPS = frozenset({
	'Domain Admins',
	'Enterprise Admins',
	'Schema Admins',
	'Administrators',
})

BH_CHECK_META = {
	'BH-01': {
		'title': 'DCSync-rettighet',
		'severity': 'critical',
		'looks_for': (
			'Kontoer eller grupper med replicating directory changes-rettigheter på domenet: '
			'<code>GetChanges</code> eller <code>GetChangesAll</code>. '
			'Rapporterer også <code>GenericAll</code>, <code>WriteDacl</code> og <code>WriteOwner</code> '
			'direkte på domenobjektet, som kan brukes til å gi seg selv DCSync.'
		),
		'risk': (
			'DCSync lar en angriper etterligne en domenekontroller og hente passordhash for alle brukere '
			'(inkludert kradmin og servicekontoer) uten å kompromittere en DC. '
			'Dette er en av de mest effektive veiene til full domeneovertagelse.'
		),
	},
	'BH-02': {
		'title': 'Farlig ACL på privilegert gruppe',
		'severity': 'critical',
		'looks_for': (
			'Farlige ACE-er på grupper som regnes som privilegerte i OK (bl.a. fra '
			'<code>PRIVILEGERTE_GRUPPER_AD</code>, samt Domain Admins, Enterprise Admins m.fl.): '
			'<code>GenericAll</code>, <code>WriteOwner</code>, <code>WriteDacl</code>, '
			'<code>AddMember</code>, <code>ForceChangePassword</code> eller <code>AllExtendedRights</code>. '
			'Sjekkes på alle objekttyper der gruppen er mål.'
		),
		'risk': (
			'Skriverettigheter på en privilegert gruppe kan brukes til å legge seg selv (eller en kompromittert konto) '
			'inn i gruppen og arve alle tilhørende rettigheter – ofte domeneadmin eller tilsvarende. '
			'<code>AddMember</code> alene er nok til å eskalere privilegium.'
		),
	},
	'BH-03': {
		'title': 'Unconstrained delegation',
		'severity': 'high',
		'looks_for': (
			'Brukere og datamaskiner med <code>Trusted for delegation</code> uten begrensning '
			'(<code>msDS-AllowedToDelegateTo</code> tom / unconstrained delegation aktivert i BloodHound-data).'
		),
		'risk': (
			'En kompromittert maskin eller konto med unconstrained delegation kan fange opp TGT-er fra brukere '
			'som autentiserer seg mot den, og deretter utgi seg for disse brukerne mot andre tjenester. '
			'Klassisk angrepsvei når en server med denne innstillingen tas over.'
		),
	},
	'BH-04': {
		'title': 'Resource-based constrained delegation (RBCD)',
		'severity': 'high',
		'looks_for': (
			'Datamaskiner der <code>AllowedToAct</code> (msDS-AllowedToActOnBehalfOfOtherIdentity) '
			'ikke er tom – dvs. andre kontoer er eksplisitt tillatt å delegere til denne maskinen.'
		),
		'risk': (
			'Med skriverettighet på maskinobjektet kan en angriper konfigurere RBCD slik at en konto de kontrollerer '
			'kan utgi seg for privilegerte brukere mot den maskinen. Kombinert med svake ACL-er på computer-objekter '
			'kan dette føre til lateral movement og privilegieeskalering.'
		),
	},
	'BH-05': {
		'title': 'Kerberoastbar konto med privilegium',
		'severity': 'high',
		'looks_for': (
			'Brukere med SPN (<code>hasspn</code>) som er medlem av en privilegert AD-gruppe, '
			'direkte eller via ett nivå med nestet gruppemedlemskap.'
		),
		'risk': (
			'Kerberoasting lar en autentisert bruker be om et TGS for en SPN og knuse passordet offline. '
			'En svakt passord på en slik konto gir umiddelbar tilgang til privilegier knyttet til gruppen – '
			'ofte langt mer alvorlig enn en vanlig brukerkonto med SPN.'
		),
	},
	'BH-06': {
		'title': 'Skriverettighet på GPO',
		'severity': 'medium',
		'looks_for': (
			'Kontoer med <code>GenericAll</code>, <code>WriteOwner</code> eller <code>WriteDacl</code> '
			'på Group Policy-objekter (GPO-er).'
		),
		'risk': (
			'Skriverettighet på en GPO som kobles til mange maskiner (særlig domenekontrollere eller servere) '
			'kan brukes til å legge inn planlagte oppgaver, startup-skript eller annen policy som kjører med '
			'system-/domenerettigheter – effektiv vei til code execution i stor skala.'
		),
	},
	'BH-07': {
		'title': 'SID history på konto',
		'severity': 'medium',
		'looks_for': (
			'Brukere med ikke-tom <code>sidHistory</code> – typisk fra migrering eller sammenslåing av domener '
			'der gamle SID-er er beholdt på kontoen.'
		),
		'risk': (
			'Hvis en gammel SID i <code>sidHistory</code> tilhørte en privilegert gruppe i et tidligere domene, '
			'kan kontoen fortsatt arve rettigheter via SID-filtrering som ikke er stram nok. '
			'Kan gi uventet domeneadmin-tilgang etter migrering.'
		),
	},
}

BH_CHECK_ORDER = tuple(f'BH-{i:02d}' for i in range(1, 8))


def bh_check_catalog():
	"""Ordered list of check metadata for UI reference."""
	return [
		{'check_id': check_id, **BH_CHECK_META[check_id]}
		for check_id in BH_CHECK_ORDER
	]


def privileged_group_name_set():
	names = set()
	for name in PRIVILEGERTE_GRUPPER_AD:
		names.add(name.lower())
	for name in EXTRA_PRIVILEGED_GROUPS:
		names.add(name.lower())
	return names


def severity_for_bh02(right_name):
	if right_name in ('GenericAll', 'WriteOwner', 'WriteDacl', 'AllExtendedRights'):
		return 'critical'
	return 'high'
