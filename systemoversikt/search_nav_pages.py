# -*- coding: utf-8 -*-
# Change log:
# 2026-06-24: Risiko nav search – view_qualysvuln fallback (same as views_risiko / BloodHound).
# 2026-06-24: Risikovurderinger list open to all users (no permission filter).
# 2026-06-24: Navigation search – risikovurderinger links (view_riskscope).
# 2026-06-23: Navigation page registry for global search – CA overview graph link.
# 2026-06-23: BloodHound nav entries require view_qualysvuln (same as vulnstats).
# 2026-06-23: Navigation page registry for global search – BloodHound findings link.
# 2026-06-23: Navigation page registry for global search – BloodHound status link.
# 2026-06-23: Navigation page registry for global search – theme/report links before entity hits.
#
# Keep in sync with sidemeny templates: system_index, sikkerhet_index, brukere_index,
# cmdb_index, virksomhet_index, rapport_index.

from django.urls import NoReverseMatch, reverse

DEFAULT_PERMISSIONS = ['systemoversikt.view_system']


def _url_kwargs_var_systembruk(user):
	try:
		virksomhet = user.profile.virksomhet
		if virksomhet:
			return {'pk': virksomhet.pk}
	except Exception:
		pass
	return None


def _entry(label, url_name, section, keywords=None, permissions=None, url_kwargs=None, url_for_user=None, test_url_kwargs=None):
	item = {
		'label': label,
		'url_name': url_name,
		'section': section,
		'keywords': keywords or [],
	}
	if permissions is not None:
		item['permissions'] = permissions
	if url_kwargs is not None:
		item['url_kwargs'] = url_kwargs
	if url_for_user is not None:
		item['url_for_user'] = url_for_user
	if test_url_kwargs is not None:
		item['test_url_kwargs'] = test_url_kwargs
	return item


NAV_PAGES = [
	# --- System (system_index.html) ---
	_entry('Alle tjenesteområder', 'tjenester_oversikt', 'System', ['tjenesteområder', 'tjenesteomrade', 'tjenester']),
	_entry('Alle systemer', 'systemer_vis_alle', 'System', ['alle systemer', 'systemoversikt']),
	_entry('Alle driftsplattformer', 'alle_driftsmodeller', 'System', ['driftsplattformer', 'driftsmiljø', 'driftsmiljo', 'driftsmodell']),
	_entry('Alle leverandører', 'alle_leverandorer', 'System', ['alle leverandører', 'leverandøroversikt']),
	_entry('All programvare', 'alle_programvarer', 'System', ['all programvare', 'alle programvare', 'programvareoversikt']),
	_entry('Alle URLer', 'alle_systemurler', 'System', ['alle urler', 'url-oversikt', 'systemurler']),
	_entry('Min virksomhet', 'min_virksomhet', 'System', ['min virksomhet'], permissions=[]),
	_entry(
		'Vår systembruk', 'all_bruk_for_virksomhet', 'System',
		['vår systembruk', 'var systembruk', 'systembruk virksomhet'],
		url_for_user=_url_kwargs_var_systembruk,
		test_url_kwargs={'pk': 1},
	),
	_entry('Leverandørland', 'rapport_systemer_leverandor_land', 'System', ['leverandørland', 'leverandorland']),
	_entry('Fellessystemer', 'systemklassifisering_tom', 'System', ['fellessystemer', 'felles systemer']),
	_entry('Bydelsbruk', 'systembruk_bydeler', 'System', ['bydelsbruk', 'bydel']),
	_entry('End of life', 'systemer_EOL', 'System', ['end of life', 'eol']),
	_entry('Systemprioriteringer', 'rapport_prioriteringer', 'System', ['prioriteringer', 'systemprioriteringer', 'kontinuitet', 'beredskap']),
	_entry('Utfasede systemer', 'systemer_utfaset', 'System', ['utfasede systemer', 'utfaset']),
	_entry('Forsømte systemer', 'rapport_systemer_forsomt', 'System', ['forsømte systemer', 'forsomte']),
	_entry('Systemer på Citrix', 'systemer_citrix', 'System', ['systemer på citrix', 'systemer citrix']),
	_entry('Systemer uten driftsmiljø', 'systemer_uten_driftsmodell', 'System', ['uten driftsmiljø', 'uten driftsmiljo']),
	_entry('Systemkategorier', 'alle_hovedkategorier', 'System', ['systemkategorier', 'hovedkategorier']),
	_entry('Samlede kontaktpersoner', 'alle_systemer_forvaltere', 'System', ['kontaktpersoner', 'forvaltere', 'systemforvaltere']),
	_entry('Informasjonsklassifisering', 'system_informasjonsbehandling', 'System', ['informasjonsklassifisering', 'informasjonsbehandling']),
	_entry('Samlede systemvurderinger', 'systemer_vurderinger', 'System', ['systemvurderinger', 'vurderinger samlet']),

	# --- Sikkerhet (sikkerhet_index.html) ---
	_entry('Qualys: sårbarheter', 'vulnstats', 'Sikkerhet', ['qualys', 'sårbarheter', 'sarbarheter', 'cve'], permissions=['systemoversikt.view_qualysvuln']),
	_entry('Azure: sårbarheter', 'azure_vulnstats', 'Sikkerhet', ['azure sårbarheter', 'defender'], permissions=['systemoversikt.view_qualysvuln']),
	_entry('Qualys vs Defender', 'azure_vulnstats_qualys_compare', 'Sikkerhet', ['qualys vs defender', 'defender compare'], permissions=['systemoversikt.view_qualysvuln']),
	_entry('Gjennomførte pentester', 'rapport_sikkerhetstester', 'Sikkerhet', ['pentester', 'pentest', 'sikkerhetstester']),
	_entry('Risikovurderinger', 'risiko_scope_list', 'Sikkerhet', ['risiko', 'risikovurdering', 'risikomatrise'], permissions=[]),
	_entry('Ny risikosamling', 'risiko_scope_create', 'Sikkerhet', ['ny risikosamling', 'risiko opprett'], permissions=['systemoversikt.add_riskscope', 'systemoversikt.view_qualysvuln']),
	_entry('Importer risikomatrise', 'risiko_import', 'Sikkerhet', ['risiko import', 'risikomatrise import'], permissions=['systemoversikt.add_riskscope', 'systemoversikt.view_qualysvuln']),
	_entry('ADCS certifikatmaler', 'cmdb_adcs_index', 'Sikkerhet', ['adcs', 'certifikatmaler'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('AD: BloodHound-status', 'sikkerhet_bloodhound_status', 'Sikkerhet', ['bloodhound', 'ad attack paths'], permissions=['systemoversikt.view_qualysvuln']),
	_entry('AD: BloodHound-funn', 'sikkerhet_bloodhound_findings', 'Sikkerhet', ['bloodhound funn', 'bloodhound findings', 'dcsync', 'kerberoast'], permissions=['systemoversikt.view_qualysvuln']),
	_entry('Device code-innlogginger', 'sikkerhet_device_code_logins', 'Sikkerhet', ['device code', 'devicecode'], permissions=['systemoversikt.view_qualysvuln']),
	_entry('Device code-innlogginger (sanntid)', 'sikkerhet_device_code_logins_sanntid', 'Sikkerhet', ['device code sanntid', 'devicecode live'], permissions=['systemoversikt.view_qualysvuln']),
	_entry('Varsling til virksomheter', 'sikkerhet_varsling_virksomheter', 'Sikkerhet', ['varsling virksomheter', 'csirt varsling']),
	_entry('Kontoer utenfor OK', 'rapport_ukjente_identer', 'Sikkerhet', ['utenfor ok', 'ukjente identer'], permissions=['auth.view_user']),
	_entry('Kontoer med SPN', 'alle_spn', 'Sikkerhet', ['spn', 'service principal name'], permissions=['auth.view_user']),
	_entry('Delegerte kontoer', 'rapport_trusted_delegation', 'Sikkerhet', ['delegerte kontoer', 'trusted delegation'], permissions=['auth.view_user']),
	_entry('Manuelt opprettede brukere', 'rapport_ad_ukjente_brukere', 'Sikkerhet', ['manuelt opprettede', 'ukjente brukere'], permissions=['auth.view_user']),
	_entry('Sikkerhetsunntak', 'o365_avvik', 'Sikkerhet', ['sikkerhetsunntak', 'o365 avvik']),
	_entry('Kritiske samfunnsfunksjoner', 'system_kritisk_funksjon', 'Sikkerhet', ['kritiske samfunnsfunksjoner', 'samfunnsfunksjoner']),
	_entry('ISK per system', 'isk_ansvarlig_for_system', 'Sikkerhet', ['isk per system', 'informasjonssikkerhet system']),
	_entry('KIT-vurderinger samlet', 'rapport_kit_vurderinger_samlet', 'Sikkerhet', ['kit-vurderinger', 'kit vurderinger']),
	_entry('Leverandørtilgang', 'leverandortilgang', 'Sikkerhet', ['leverandørtilgang', 'leverandortilgang'], permissions=['auth.view_user']),
	_entry('Drift-brukere', 'rapport_ad_driftbrukere', 'Sikkerhet', ['drift-brukere', 'driftbrukere'], permissions=['auth.view_user']),
	_entry('Servicekontoer', 'rapport_servicekontoer', 'Sikkerhet', ['servicekontoer'], permissions=['auth.view_user']),
	_entry('Testkontoer', 'rapport_ad_testbrukere', 'Sikkerhet', ['testkontoer', 'test-brukere'], permissions=['auth.view_user']),

	# --- Brukere (brukere_index.html) ---
	_entry('HR-organisasjon', 'virksomhet_enhetsok', 'Brukere', ['hr-organisasjon', 'enhetsøk', 'enhetsok'], permissions=['auth.view_user']),
	_entry('Brukersøk AD', 'bruker_sok', 'Brukere', ['brukersøk ad', 'brukersok ad', 'brukersøk'], permissions=['auth.view_user']),
	_entry('Brukersøk Entra ID', 'entra_id_oppslag', 'Brukere', ['brukersøk entra', 'entra id oppslag', 'entra oppslag'], permissions=['auth.view_user']),
	_entry('Listesøk (eksakt)', 'cmdb_ad_brukerlistesok', 'Brukere', ['listesøk', 'listesok', 'brukerlistesøk'], permissions=['auth.view_user']),
	_entry('OU-strukturen', 'adorgunit_detaljer', 'Brukere', ['ou-struktur', 'organizational unit'], permissions=['auth.view_user']),
	_entry('Tilgangsgrupper', 'alle_adgrupper', 'Brukere', ['tilgangsgrupper oversikt', 'alle tilgangsgrupper'], permissions=['auth.view_user']),
	_entry('Gruppeanalyse', 'ad_gruppeanalyse', 'Brukere', ['gruppeanalyse'], permissions=['auth.view_user']),
	_entry('Kopibrukere', 'tbrukere', 'Brukere', ['kopibrukere', 'tb-brukere'], permissions=['auth.view_user']),
	_entry('Brukere uten e-post', 'cmdb_uten_epost_stat', 'Brukere', ['uten e-post', 'uten epost'], permissions=['auth.view_user']),
	_entry('Personer med flere identer', 'cmdb_ad_flere_brukeridenter', 'Brukere', ['flere identer', 'duplikat identer'], permissions=['auth.view_user']),
	_entry('Entra ID MFA', 'rapport_entra_id_auth', 'Brukere', ['entra mfa', 'mfa'], permissions=['auth.view_user']),
	_entry('Tomme tilgangsgrupper', 'ad_analyse', 'Brukere', ['tomme tilgangsgrupper', 'tomme grupper'], permissions=['auth.view_user']),
	_entry('M365-lisenser', 'o365_lisenser', 'Brukere', ['m365-lisenser', 'lisenser', 'office 365 lisenser'], permissions=['auth.view_user']),
	_entry('AD-identnedbryting', 'rapport_ad_identer', 'Brukere', ['identnedbryting'], permissions=['auth.view_user']),
	_entry('Grupper over tid', 'rapport_ad_adgrupper', 'Brukere', ['grupper over tid'], permissions=['auth.view_user']),

	# --- CMDB (cmdb_index.html) ---
	_entry('Statistikk', 'cmdb_statistikk', 'CMDB', ['cmdb statistikk'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Business services', 'cmdb_bs_detaljer', 'CMDB', ['business services', 'bss'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Offerings uten kobling', 'cmdb_bs_mangler_kobling', 'CMDB', ['offerings uten kobling'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Feilkoblet', 'cmdb_bs_aktuelle_ikke_koblet', 'CMDB', ['feilkoblet', 'ikke koblet'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Utfaset miljø', 'cmdb_bskobling_utfaset', 'CMDB', ['utfaset miljø bs', 'bs utfaset'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Koblet mangler landingssone', 'cmdb_bs_koblet_ukjent_plattform', 'CMDB', ['mangler landingssone', 'ukjent plattform'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Skjult ikke tom', 'cmdb_bs_skjult_relevant', 'CMDB', ['skjult ikke tom'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Servere flere offerings', 'cmdb_servere_flere_offerings', 'CMDB', ['flere offerings'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Tjenester per virksomhet', 'cmdb_per_virksomhet', 'CMDB', ['tjenester per virksomhet', 'cmdb virksomhet'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Servere', 'alle_servere', 'CMDB', ['alle servere', 'serveroversikt'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Servere minnebruk', 'cmdb_minne_index', 'CMDB', ['servere minnebruk', 'minnebruk'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Servere massesøk', 'maskin_sok', 'CMDB', ['massesøk servere', 'maskinsøk', 'maskinsok'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Servere internetteksponerte', 'cmdb_internetteksponerte_servere', 'CMDB', ['internetteksponerte', 'eksponerte servere'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Klienter', 'alle_klienter', 'CMDB', ['alle klienter', 'klientoversikt'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Oracle programvare', 'cmdb_installert_programvare', 'CMDB', ['oracle programvare', 'installert programvare'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Databaser', 'alle_databaser', 'CMDB', ['alle databaser', 'databaseoversikt'], permissions=['systemoversikt.view_cmdbdatabase']),
	_entry('Backup', 'cmdb_backup_index', 'CMDB', ['backup oversikt', 'cmdb backup'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Servere uten backup', 'cmdb_uten_backup', 'CMDB', ['uten backup'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Lagring', 'cmdb_lagring_index', 'CMDB', ['lagring oversikt', 'cmdb lagring'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Citrix apper', 'alle_citrixpub', 'CMDB', ['citrix apper', 'citrix publisering'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Citrix bruk', 'alle_citrixpub_bruk', 'CMDB', ['citrix bruk'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Citrix-mappinger', 'citrix_mappings', 'CMDB', ['citrix-mappinger', 'citrix mapping'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('BigIP / VIP', 'alle_vip', 'CMDB', ['bigip', 'vip', 'load balancer'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('DNS', 'alle_dns', 'CMDB', ['dns oversikt', 'alle dns'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('VLAN / Nettverk', 'alle_nettverk', 'CMDB', ['vlan', 'nettverk oversikt'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Brannmur', 'cmdb_firewall', 'CMDB', ['brannmur', 'firewall'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Nettverksenheter', 'alle_nettverksenheter', 'CMDB', ['nettverksenheter'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('IP-søk', 'alle_ip', 'CMDB', ['ip-søk', 'ip søk', 'ip oversikt'], permissions=['systemoversikt.view_cmdbdevice']),

	# --- Virksomhet (virksomhet_index.html) ---
	_entry('Alle virksomheter', 'alle_virksomheter_sidemeny', 'Virksomhet', ['alle virksomheter', 'virksomhetsoversikt'], permissions=[]),
	_entry('Vis kontaktinfo ISK/PSK', 'alle_virksomheter_kontaktinfo', 'Virksomhet', ['kontaktinfo isk', 'isk psk', 'kontaktinfo'], permissions=[]),
	_entry('Vis sertifikatfullmakter', 'sertifikatmyndighet', 'Virksomhet', ['sertifikatfullmakter', 'sertifikatmyndighet'], permissions=['systemoversikt.view_virksomhet']),

	# --- Rapport (rapport_index.html) ---
	_entry('Gule og rød land', 'rapport_named_locations', 'Rapport', ['gule land', 'rød land', 'named locations'], permissions=[]),
	_entry('Service principals', 'azure_applications', 'Rapport', ['service principals', 'enterprise applications'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('User consents', 'azure_user_consents', 'Rapport', ['user consents', 'samtykker'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Nøkler utgått', 'azure_application_keys_expired', 'Rapport', ['nøkler utgått', 'nokler utgatt'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Nøkler snart utgår', 'azure_application_keys_soon', 'Rapport', ['nøkler snart', 'nokler snart'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('Aktive nøkler', 'azure_application_keys_active', 'Rapport', ['aktive nøkler', 'aktive nokler'], permissions=['systemoversikt.view_cmdbdevice']),
	_entry('CA-regler', 'rapport_conditional_access_rules', 'Rapport', ['ca-regler', 'conditional access'], permissions=['systemoversikt.view_entraidconditionalaccesspolicies']),
	_entry('CA-oversikt', 'rapport_conditional_access_overview', 'Rapport', ['ca-oversikt', 'conditional access oversikt', 'ca fliser'], permissions=['systemoversikt.view_entraidconditionalaccesspolicies']),
	_entry('CA-endringer', 'rapport_conditional_access_changes', 'Rapport', ['ca-endringer', 'conditional access endringer'], permissions=['systemoversikt.view_entraidconditionalaccesspolicies']),
]


def _keywords_for_entry(entry):
	keywords = [entry['label'].lower()]
	for kw in entry.get('keywords', []):
		normalized = kw.lower().strip()
		if normalized and normalized not in keywords:
			keywords.append(normalized)
	return keywords


def _match_score(term, keywords):
	best = 0
	for kw in keywords:
		if term == kw:
			best = max(best, 100)
		elif kw.startswith(term) or term.startswith(kw):
			best = max(best, 80)
		elif term in kw or kw in term:
			best = max(best, 60)
	return best


def _user_has_permissions(user, permissions):
	if permissions is None:
		permissions = DEFAULT_PERMISSIONS
	if not permissions:
		return True
	return any(user.has_perm(permission) for permission in permissions)


def _resolve_url(entry, user):
	url_kwargs = entry.get('url_kwargs')
	if 'url_for_user' in entry:
		url_kwargs = entry['url_for_user'](user)
		if url_kwargs is None:
			return None
	try:
		return reverse(entry['url_name'], kwargs=url_kwargs or {})
	except NoReverseMatch:
		return None


def match_nav_pages(search_term, user):
	term = search_term.strip().lower()
	if len(term) <= 1:
		return []

	results = []
	for entry in NAV_PAGES:
		if not _user_has_permissions(user, entry.get('permissions', DEFAULT_PERMISSIONS)):
			continue

		score = _match_score(term, _keywords_for_entry(entry))
		if score == 0:
			continue

		url = _resolve_url(entry, user)
		if not url:
			continue

		results.append({
			'label': entry['label'],
			'url': url,
			'section': entry.get('section', ''),
			'_score': score,
		})

	results.sort(key=lambda item: (-item['_score'], item['label'].lower()))
	for item in results:
		del item['_score']
	return results


def reverse_kwargs_for_test(entry):
	if 'test_url_kwargs' in entry:
		return entry['test_url_kwargs']
	if 'url_kwargs' in entry:
		return entry['url_kwargs']
	return {}
