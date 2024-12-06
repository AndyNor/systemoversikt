# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from simple_history.models import HistoricalRecords
from django import forms
import json
import re
from django.db.models import Sum


# som standard vises bare "self.username". Vi ønsker også å vise fult navn.
def new_display_name(self):
	if self.profile.displayName:
		return(self.profile.displayName + " (" + self.username + ")")
	else:
		return(self.first_name + " " + self.last_name + " (" + self.username + ")")
User.add_to_class("__str__", new_display_name)


VALG_KLARGJORT_SIKKERHETSMODELL = (
	(None, "❔ Ikke vurdert"),
	(1, "🟢 Klargjort via Azure Web Application Proxy"),
	(2, "🟢 Klargjort som Citrix publisert applikasjon"),
	(3, "🟢 Direkteeksponert webtjeneste med Azure AD-pålogging"),
	(4, "🟢 Desktopapplikasjon uten avhengigheter, ferdig pakket"),
	(9, "🟢 Publisert på dedikerte AVD-maskiner"),
	(5, "🟡 Ikke klargjort, skal til Azure Web Application Proxy"),
	(9, "🟡 Ikke klargjort, skal direkteeksponeres og ha Azure AD autentisering"),
	(6, "🟡 Ikke klargjort, skal publiseres som Citrix strømmet app"),
	(7, "🟡 Ikke klargjort, skal kun pakkes som desktop applikasjon"),
	(10, "🟡 Ikke klargjort, skal til dedikerte AVD-maskiner"),
	(8, "🔴 Ingen løsning klar enda"),
)


class EntraIDConditionalAccessPolicies(models.Model):
	timestamp = models.DateTimeField(
			verbose_name="Lastet inn",
			auto_now=True,
		)
	json_policy = models.TextField(
			verbose_name="Policy raw JSON",
			blank=False,
			null=False,
		)
	modification = models.BooleanField(
			verbose_name="Endret siden sist?",
			default=False,
		)
	changes = models.TextField(
			verbose_name="Endringer siden sist",
			blank=True,
			null=True,
		)

	def __str__(self):
		return f"CA policy {self.timestamp}"

	class Meta:
		verbose_name_plural = "Azure: Conditional Access policyer"
		default_permissions = ('add', 'change', 'delete', 'view')


class CitrixPublication(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
		)
	sone = models.CharField(
			verbose_name="sone",
			blank=False,
			null=False,
			max_length=10,
		)
	publikasjon_json = models.TextField(
			verbose_name="Publikasjon JSON",
			blank=False,
			null=False,
		)
	publikasjon_UUID = models.CharField(
			verbose_name="Publikasjon UUID",
			blank=False,
			null=False,
			unique=True,
			max_length=40,
		)
	display_name = models.CharField(
			verbose_name="Visningsnavn",
			blank=True,
			null=True,
			max_length=300,
		)
	publikasjon_active = models.BooleanField(
			verbose_name="Aktiv",
			default=True,
		)
	cache_antall_publisert_til = models.IntegerField(
			verbose_name="Antall publisert til (cache)",
			null=True,
		)
	type_vApp = models.BooleanField(
			verbose_name="Er en vApp",
			default=False,
		)
	type_nettleser = models.BooleanField(
			verbose_name="Via nettleser",
			default=False,
		)
	type_remotedesktop = models.BooleanField(
			verbose_name="Er remote desktop",
			default=False,
		)
	type_produksjon = models.BooleanField(
			verbose_name="For produksjon",
			default=True,
		)
	type_medlemmer = models.BooleanField(
			verbose_name="Er publisert",
			default=True,
		)
	type_nhn = models.BooleanField(
			verbose_name="Norsk Helsenett-side",
			default=False,
		)
	type_executable = models.BooleanField(
			verbose_name="Executable file?",
			default=False,
		)
	type_vbs = models.BooleanField(
			verbose_name="VBS file?",
			default=False,
		)
	type_ps1 = models.BooleanField(
			verbose_name="PS1 file?",
			default=False,
		)
	type_bat = models.BooleanField(
			verbose_name="BAT file?",
			default=False,
		)
	type_cmd = models.BooleanField(
			verbose_name="BAT file?",
			default=False,
		)

	def __str__(self):
		return f"{self.display_name} {self.sone}"

	class Meta:
		verbose_name_plural = "CMDB: Citrixpublikasjoner"
		default_permissions = ('add', 'change', 'delete', 'view')


class Fellesinformasjon(models.Model):
	message = models.TextField(
			verbose_name="message",
			blank=False,
			null=False,
			)
	aktiv = models.BooleanField(
			verbose_name="Aktiv",
			default=True,
			help_text=u"",
			)
	def __str__(self):
		return u'%s' % (self.message)

	class Meta:
		verbose_name_plural = "System: Fellesinformasjon"
		default_permissions = ('view')


class UserChangeLog(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	event_type = models.CharField(
			verbose_name="event_type",
			max_length=30,
			blank=False,
			null=False,
			help_text=u"event_type",
			)
	message = models.TextField(
			verbose_name="message",
			blank=False,
			null=False,
			help_text=u"message",
			)
	def __str__(self):
		return u'%s %s' % (self.event_type, self.message)

	class Meta:
		verbose_name_plural = "System: Brukerendringer"
		default_permissions = ('add', 'change', 'delete', 'view')



class NyeFunksjoner(models.Model):
	tidspunkt = models.DateTimeField(
			verbose_name="Tidspunkt",
			null=False,
			blank=False,
			help_text=u"Kan dateres tilbake i tid.",
			)
	beskrivelse = models.TextField(
			verbose_name="Beskrivelse",
			blank=False,
			null=False,
			help_text=u"Hva får sluttbruker tilgang til å gjøre?",
			)
	reverse_url = models.CharField(
			verbose_name="URL-oppslagstekst",
			max_length=250,
			blank=True,
			null=True,
			help_text=u"URL-navnet som skal bli til en link.",
			)
	def __str__(self):
		return f'{self.beskrivelse}'

	class Meta:
		verbose_name_plural = "System: Nye funksjoner"
		default_permissions = ('add', 'change', 'delete', 'view')



class IntegrasjonKonfigurasjon(models.Model):
	kodeord = models.CharField(
		max_length=50,
		blank=False,
		null=False,
		unique=True,
	)
	kilde = models.CharField(
		max_length=100,
		blank=False,
		null=False,
	)
	protokoll = models.CharField(
		max_length=30,
		blank=False,
		null=False,
	)
	informasjon = models.CharField(
		max_length=250,
		blank=False,
		null=False,
	)
	sp_filnavn = models.CharField(
		verbose_name="Filnavn i SharePoint",
		max_length=500,
		blank=True,
		null=True,
		help_text=u"Kun relevant dersom hentet fra Kartotekets SharePoint-site.",
	)
	url = models.URLField(
		max_length=300,
		blank=True,
		null=True,
	)
	frekvensangivelse = models.CharField(
		max_length=300,
		blank=True,
		null=True,
	)
	dato_sist_oppdatert = models.DateTimeField(
		help_text=u"Settes automatisk basert på dato fra kilden. Dersom fra SharePoint, settes filens sist oppdaterte dato.",
		blank=True,
		null=True,
	)
	script_navn = models.CharField(
		max_length=400,
		blank=True,
		null=True,
		help_text=u"Settes automatisk når script kjører og oppdaterer sist oppdatert.",
	)
	log_event_type = models.CharField(
		max_length=300,
		blank=False,
		null=False,
	)
	sist_status = models.TextField(
		verbose_name="Sist status",
		blank=True,
		null=True,
	)

	def __str__(self):
		return f'{self.kilde} {self.protokoll} {self.informasjon}'

	def color(self):
		if self.dato_sist_oppdatert:
			from datetime import datetime, timedelta
			from django.utils import timezone
			today = timezone.now()
			difference = today - self.dato_sist_oppdatert
			if difference < timedelta(days=1):
				return "#b8e1ca"
			if difference < timedelta(days=28):
				return "#e1cfa3"
		return "#cf949a"


	class Meta:
		verbose_name_plural = "System: Integrasjonskonfigurasjoner"
		default_permissions = ('add', 'change', 'delete', 'view')


class APIKeys(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	key = models.CharField(
			verbose_name="Nøkkel / passord",
			max_length=256,
			blank=False,
			null=False,
			unique=False,
			)
	navn = models.CharField(
			verbose_name="Navn på nøkkel",
			blank=False,
			max_length=64,
			null=False,
			unique=True,
			)
	kommentar = models.TextField(
			verbose_name="Kommentar",
			blank=True,
			null=True,
			)
	def __str__(self):
		return u'%s (%s)' % (self.navn, self.kommentar)

	class Meta:
		verbose_name_plural = "System: API-nøkler"
		default_permissions = ('add', 'change', 'delete', 'view')




class ApplicationLog(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	event_type = models.CharField(
			verbose_name="event_type",
			max_length=30,
			blank=False,
			null=False,
			help_text=u"event_type",
			)
	message = models.TextField(
			verbose_name="message",
			blank=False,
			null=False,
			help_text=u"message",
			)
	def __str__(self):
		return u'%s %s %s' % (self.opprettet.strftime('%Y-%m-%d %H:%M:%S'), self.event_type, self.message)

	class Meta:
		verbose_name_plural = "System: Applikasjonslogger"
		default_permissions = ('add', 'change', 'delete', 'view')

class DefinisjonKontekster(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.TextField(
			verbose_name="Kontekstnavn",
			blank=True,
			null=True,
			help_text=u"Navn på kontekst som kan velges for defininsjoner",
			)

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Definisjoner: Definisjonskontekster"
		default_permissions = ('add', 'change', 'delete', 'view')


DEFINISJON_STATUS_VALG = (
	(0, 'Forslag'),
	(1, 'Aktiv'),
	(2, 'Utfaset'),
)

class Definisjon(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	status = models.IntegerField(
			choices=DEFINISJON_STATUS_VALG,
			verbose_name="Status på definisjon",
			blank=False,
			null=False,
			default=0,
			help_text=u"Livsløp på definisjonen",
			)
	begrep = models.CharField(
			verbose_name="Begrep / term",
			max_length=300,
			blank=False,
			null=False,
			help_text=u"",
			)
	kontekst_ref = models.ForeignKey(
			to=DefinisjonKontekster,
			related_name='defininsjon_kontekst_ref',
			verbose_name="Definisjonens kontekst (valgmeny)",
			blank=True,
			null=True,
			on_delete=models.PROTECT,
			help_text=u"Konteksten eller domenet definisjonen angår",
			)
	engelsk_begrep = models.CharField(
			verbose_name="Engelsk begrep / term",
			max_length=300,
			blank=True,
			null=True,
			help_text=u"",
			)
	ansvarlig = models.ForeignKey(
			to="Ansvarlig",
			related_name='definisjon_ansvarlig',
			null=True,
			blank=True,
			on_delete=models.PROTECT,
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=False,
			null=False,
			help_text=u"Definisjon slik folk flest kan forstå den",
			)
	eksempel = models.TextField(
			verbose_name="Eksempel",
			blank=True,
			null=True,
			help_text=u"Eksemplifiser definisjonen dersom mulig.",
			)
	legaldefinisjon = models.TextField(
			verbose_name="Legaldefinisjon",
			blank=True,
			null=True,
			help_text=u"Formell/legal definisjonstekst",
			)
	kilde = models.URLField(
			verbose_name="Kilde eller opphav (URL)",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"En URI til original definisjon.",
			)
	kontekst = models.TextField(
			verbose_name="Gammel kontekst (fases ut)",
			blank=True,
			null=True,
			help_text=u"Konteksten eller domenet definisjonen angår",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.begrep)

	class Meta:
		verbose_name_plural = "Definisjoner: Definisjoner"
		default_permissions = ('add', 'change', 'delete', 'view')

class Ansvarlig(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	brukernavn = models.OneToOneField(
			to=User,
			related_name="ansvarlig_brukernavn",
			on_delete=models.PROTECT,
			blank=False,
			null=False,
			help_text=u"Her kan du søke på fornavn og/eller etternavn.",
			)
	telefon = models.CharField(
			verbose_name="Primærtelefon (mobil)",
			max_length=30,
			blank=True,
			null=True,
			help_text=u"Nummer personen/rollen kan nås på i jobbsammenheng. Må kunne motta SMS.",
			)
	fdato = models.CharField(
			verbose_name="Fødselsdato",
			max_length=6,
			blank=True,
			null=True,
			help_text=u"Dag, måned, år, f.eks. 100575 (10.mai 1975). Dette feltet fyller du bare ut dersom personen har en rolle innen sertifikatgodkjenning.",
			)
	kommentar = models.TextField(
			verbose_name="Kommentar (fases ut)",
			blank=True,
			null=True,
			help_text=u"Fritekst",
			)
	vil_motta_epost_varsler = models.BooleanField(
			verbose_name="Ønsker du å motta e-postvarsler?",
			default=False,
			help_text=u"",
			)
	cache_seksjon = models.ForeignKey(
			to='HRorg',
			related_name='ansvarlig',
			verbose_name="Seksjon (cache)",
			blank=True,
			null=True,
			on_delete=models.SET_NULL,
			help_text=u"Seksjon ansvarlige sist ble sett knyttet til",
			)
	history = HistoricalRecords()


	def org_tilhorighet(self):
		try:
			enhet = self.brukernavn.profile.org_unit
			enhet_str = "%s" % (enhet)
			current_level = enhet.level
			while current_level > 3:  # level 2 er virksomheter, så vi ønsket et nivå ned (en verdi opp).
				mor_enhet = enhet.direkte_mor
				enhet_str = "%s - %s" % (mor_enhet, enhet_str)
				mor_level = mor_enhet.level
				if current_level > mor_level:
					enhet = mor_enhet
					current_level = mor_level
				else:
					break
			return enhet_str
		except:
			return "Ukjent tilhørighet"


	def __str__(self):
		if self.brukernavn:
			if self.brukernavn.profile.virksomhet:
				return u'%s %s (%s)' % (self.brukernavn.first_name, self.brukernavn.last_name, self.brukernavn.profile.virksomhet.virksomhetsforkortelse)
			else:
				return u'%s %s (%s)' % (self.brukernavn.first_name, self.brukernavn.last_name, "?")
		else:
			return u'%s (tastet inn)' % (self.navn)

	class Meta:
		verbose_name_plural = "Organisasjon: Ansvarlige"
		default_permissions = ('add', 'change', 'delete', 'view')


class AutorisertBestiller(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	person = models.ForeignKey(
			to=Ansvarlig,
			related_name='autorisertbestiller_person',
			verbose_name="Autoriserte sertifikatbestillere",
			blank=True,
			on_delete=models.PROTECT,
			help_text=u"Personer i virksomheten som er autorisert til å bestille sertifikater via UKE. Det må da foreligge en fullmakt gitt til UKEs driftsleverandør.",
			)
	dato_fullmakt = models.DateField(
			verbose_name="Dato fullmakt gitt",
			blank=False,
			null=False,
			help_text=u"Dato fra fullmaktskjema.",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.person)

	class Meta:
		verbose_name_plural = "Organisasjon: Autoriserte sertifikatbestillere"
		default_permissions = ('add', 'change', 'delete', 'view')


RESULTATENHET_VALG = (
	('OF', 'Felles IKT-plattform'),
	('Egen', 'Egen drift'),
)

OFFICE365_VALG = (
	(1, 'Felles tenant'),
	(2, 'Felles tenant med egen klientdrift'),
	(3, 'Egen tenant'),
)


class Virksomhet(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	ordinar_virksomhet = models.BooleanField(
			verbose_name="Er dette en ordinær virksomhet?",
			default=True,
			help_text=u'Hvis du tar bort dette valget, vises ikke virksomheten i virksomhetsoversikten eller i dashboard. Brukes i forbindelse med import av driftsbrukere og i forbindelse med forvaltning av sertifikater.',
			)
	virksomhetsforkortelse = models.CharField(
			unique=True,
			verbose_name="Virksomhetsforkortelse",
			blank=True,
			null=True,
			max_length=10,
			help_text=u"Dette feltet brukes som standard visningsnavn, og brukes for å koble brukeridenter til virksomheten.",
			)
	gamle_virksomhetsforkortelser = models.CharField(
			verbose_name="Alternative virksomhetsforkortelse",
			blank=True,
			null=True,
			max_length=100,
			help_text=u"Alternative/gamle forkortelser. Bruk mellomrom dersom flere. Brukes ved tildeling av WAN-lokasjoner og for filtrering av brukeridenter.",
			)

	virksomhetsnavn = models.CharField(
			unique=True,
			verbose_name="Virksomhetsnavn",
			max_length=250,
			help_text=u"Fult navn på virksomheten. En virksomhet er ment å modellere en entitet med eget organisasjonsnummer.",
			)
	overordnede_virksomheter = models.ManyToManyField(
			to="Virksomhet",
			related_name='virksomhet_overordnede_virksomheter',
			verbose_name="Tilhører byrådsavdeling",
			blank=True,
			help_text=u'Dersom aktuelt kan en annen virksomhet angis som overornet denne.',
			)
	kan_representeres = models.BooleanField(
			verbose_name="Kan representeres",
			default=False,
			help_text=u'Den overordnede virksomheten kan representere ("bytte til") den underordnede dersom det krysses av her.',
			)
	resultatenhet = models.CharField(
			choices=RESULTATENHET_VALG,
			verbose_name="Driftsmodell for klientflate",
			max_length=30,
			blank=True,
			null=True,
			default='',
			help_text=u"Dette feltet brukes for å angi om virksomheten er på sentral klientplattform, eller har lokal drift.",
			)
	uke_kam_referanse = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_uke_kam',
			verbose_name='Kundeansvarlig fra intern tjenesteleverandør',
			blank=True,
			help_text=u"Dette feltet oppdateres av intern tjenesteleverandør.",
			)
	intranett_url = models.URLField(
			verbose_name="På intranett (internt)",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Her oppgir du link til virksomhetens interne intranettside.",
			)
	www_url = models.URLField(
			verbose_name="Hjemmeområde web",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Her oppgir du link til virksomhetens hjemmeområde på de åpne nettsidene.",
			)
	ikt_kontakt = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_ikt_kontakt',
			verbose_name='IKT-hovedkontakter',
			blank=True,
			help_text=u"Virksomhetens kontaktpunkt for IKT.",
			)
	autoriserte_bestillere_tjenester = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_autoriserte_bestillere_tjenester',
			verbose_name='Autoriserte bestillere i InfoTorg',
			blank=True,
			help_text=u"En autorisert bestiller InfoTorg er en person virksomheten har autorisert til å bestille brukere til data fra det sentrale folkeregistret.",
			)
	autoriserte_bestillere_tjenester_uke = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_autoriserte_bestillere_tjenester_uke',
			verbose_name='Autoriserte bestillere av tjenester fra intern tjenesteleverandør.',
			blank=True,
			help_text=u"En autorisert bestiller er en person virksomheten har autorisert til å bestille tjenester via selvbetjeningsportalen (kundeportalen).",
			)
	orgnummer = models.CharField(
			verbose_name="Vårt organisasjonsnummer",
			max_length=30,
			blank=True,
			null=True,
			help_text=u"9 siffer uten mellomrom.",
			)
	leder = models.ManyToManyField(Ansvarlig, related_name='virksomhet_leder',
			verbose_name="Vår virksomhetsleder",
			blank=True,
			help_text=u"Angi hvem som er virksomhetsleder. Dette feltet benyttes bare dersom HR ikke har informasjon om leder.",
			)
	autoriserte_bestillere_sertifikater = models.ManyToManyField(
			to=AutorisertBestiller,
			related_name='virksomhet_autoriserte_bestillere_sertifikater',
			verbose_name="Autoriserte sertifikatbestillere",
			blank=True,
			help_text=u"Personer som kan godkjenne utstedelse av nye websertifikater og virksomhetssertifikater.",
			)
	sertifikatfullmakt_avgitt_web = models.BooleanField(
			verbose_name="Avgitt sertifikatfullmakt til Buypass?",
			blank=True,
			null=True,
			default=False,
			help_text=u"Krysses av dersom virksomhet har avgitt fullmakt til driftsleverandør for å utstede digitale sertifikater sitt org.nummer.",
			)
	rutine_tilgangskontroll = models.URLField(
			verbose_name="Rutiner for tilgangskontroll",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til dokument i virksomhetens styringssystem.",
			)
	rutine_behandling_personopplysninger = models.URLField(
			verbose_name="Rutiner for behandling av personopplysninger",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til dokument i virksomhetens styringssystem",
			)
	rutine_klage_behandling = models.URLField(
			verbose_name="Rutine for behandling av klage på behandling",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til dokument i virksomhetens styringssystem",
			)
	personvernkoordinator = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_personvernkoordinator',
			verbose_name='Personvernkoordinator (PKO)',
			blank=True,
			help_text=u"Person(er) i rollen som personvernkoordinator.",
			)
	informasjonssikkerhetskoordinator = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_informasjonssikkerhetskoordinator',
			verbose_name='Informasjonssikkerhetskoordinator (ISK)',
			blank=True,
			help_text=u"Person(er) i rollen som informasjonssikkerhetskoordinator.",
			)
	odepartmentnumber = models.IntegerField(
			verbose_name="Organisasjonens department-nummer",
			blank=True,
			null=True,
			help_text=u"Settes automatisk fra PRK/HR-import",
			)
	styringssystem = models.URLField(
			verbose_name="Styringssystem (URL)",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Her oppgir du link til virksomhetens styringssystem.",
			)
	arkitekturkontakter = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_arkitekturkontakter',
			verbose_name='Arkitekturkontakter',
			blank=True,
			help_text=u"Personer som jobber med overordnet arkitektur knyttet til virksomhetens ibruktakelse av IKT",
			)
	office365 = models.IntegerField(
		choices=OFFICE365_VALG,
			verbose_name="Modell for kontorstøtte",
			blank=True,
			null=True,
			default=1,
			help_text=u"Dette feltet brukes for å angi virksomhetens valg knyttet til office365",
			)
	ks_fiks_admin_ref = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_ks_fiks_ansvarlig',
			verbose_name='Administrator for søk i KS Fiks folkeregister portal',
			blank=True,
			help_text=u"KS Fiks folkeregister er valgt som ny standard tjeneste for modernisert folkeregister, og KS har en webportal for søk i folkeregisteret (forvaltning.fiks.ks.no). Her kan du føre opp hvem som er lokale administratorer.",
			)
	history = HistoricalRecords()

	def leder_hr(self):
		try:
			return HRorg.objects.filter(virksomhet_mor=self.pk).filter(level=2)[0].leder
		except:
			return None

	def antall_lokasjoner(self):
		return WANLokasjon.objects.filter(virksomhet=self).count()

	def antall_klienter(self):
		from django.db.models import Q
		return CMDBdevice.objects.filter(client_virksomhet=self).count()

	def antall_brukeridenter(self):
		return Profile.objects.filter(virksomhet=self).count()

	def __str__(self):
		return u'%s (%s)' % (self.virksomhetsnavn, self.virksomhetsforkortelse)

	class Meta:
		verbose_name_plural = "Organisasjon: Virksomheter"
		default_permissions = ('add', 'change', 'delete', 'view')


class AnsattID(models.Model):
	ansattnr = models.IntegerField()

	def __str__(self):
		return u'%s' % (self.ansattnr)

	class Meta:
		verbose_name_plural = "Organisasjon: Ansattnummer"
		default_permissions = ('add', 'change', 'delete', 'view')


LISENCE_VALG = (
	(0, 'Ingen'),
	(1, 'G1 E3 (Tykklient)'),
	(2, 'G2 F3 (Flerbruker)'),
	(3, 'G3 F1 (Ingen epost)'),
	(4, 'G4 A3 (Education)'),
)

PRIVELIGERTE_GRUPPER = [
	"Access Control Assistance Operators",
	"Account Operators",
	"Administrators",
	"Allowed RODC Password Replication",
	"Backup Operators",
	"Certificate Service DCOM Access",
	"Cert Publishers",
	"Cloneable Domain Controllers",
	"Cryptographic Operators",
	"Denied RODC Password Replication",
	"Device Owners",
	"DHCP Administrators",
	"DHCP Users",
	"Distributed COM Users",
	"DnsUpdateProxy",
	"DnsAdmins",
	"Domain Admins",
	"Domain Computers",
	"Domain Controllers",
	"Enterprise Admins",
	"Enterprise Key Admins",
	"Enterprise Read-only Domain Controllers",
	"Event Log Readers",
	"Group Policy Creator Owners",
	"Hyper-V Administrators",
	"IIS_IUSRS",
	"Incoming Forest Trust Builders",
	"Key Admins",
	"Network Configuration Operators",
	"Performance Log Users",
	"Performance Monitor Users",
	"Pre–Windows 2000 Compatible Access",
	"Print Operators",
	"Protected Users",
	"RAS and IAS Servers",
	"RDS Endpoint Servers",
	"RDS Management Servers",
	"RDS Remote Access Servers",
	"Read-only Domain Controllers",
	"Remote Desktop Users",
	"Remote Management Users",
	"Replicator",
	"Schema Admins",
	"Server Operators",
	"Storage Replica Administrators",
	"System Managed Accounts",
	"Terminal Server License Servers",
	"Windows Authorization Access",
	"WinRMRemoteWMIUsers_",
	# server admins
	"GS-OpsRole-ErgoGroup-AdminAlleMemberServere",
	"GS-OpsRole-Ergogroup-ServerAdmins",
	"Task-OF2-ServerAdmin-AllMemberServers",
	"Role-OF2-Admin-Citrix Services",
	"DS-MemberServer-Admin-AlleManagementServere",
	"DS-MemberServer-Admin-AlleManagementServere",
	"DS-DRIFT_DRIFTSPERSONELL_SERVERMGMT_SERVERADMIN",
	"Role-OF2-AdminAlleMemberServere",
	# domain admins
	"Role-Domain-Admins-UVA",
	"On-Prem Enterprise Admins",
	"On-Prem Domain Admins",
	# PRK admins
	"DS-GKAT_BRGR_SYSADM",
	"DS-GKAT_ADMSENTRALESKJEMA_ALLE",
	"DS-GKAT_ADMSENTRALESKJEMA_KOKS",
	"DS-GKAT_IMPSKJEMA_TIGIMP",
	"DS-GKAT_IMPSKJEMA_TSIMP",
	"DS-GKAT_MODULER_GLOBAL_ADMINISTRASJON",
	"DS-GKAT_DSGLOKALESKJEMA_ALLE",
	"DS-GKAT_DSGLOKALESKJEMA_INFOCARE",
	"DS-GKAT_DSGLOKALESKJEMA_OPPRETTE",
	"DS-GKAT_DSGSENTRALESKJEMA_ALLE",
	"DS-GKAT_DSGSENTRALESKJEMA_OPPRETTE",
	"DS-GKAT_ADMLOKALESKJEMA_ALLE",
	"DS-GKAT_ADMLOKALESKJEMA_APPLIKASJON",
	# SQL admins
	"GS-UKE-MSSQL-DBA",
	"DS-OF2-SQL-SYSADMIN",
	"DS-DRIFT_DRIFTSPERSONELL_DATABASE_SQL",
	"GS-Role-MSSQL-DBA",
	"GS-UKE-MSSQL-DBA",
	"DS-Role-MSSQL-DBA",
	"DS-DRIFT_DRIFTSPERSONELL_DATABASE_ORACLE",
	"DS-OF2-TASK-SQLCluster",
	# Citrix admins
	"Task-OF2-Admin-Citrix XenApp",
	"DS-DRIFT_DRIFTSPERSONELL_REMOTE_CITRIXDIRECTOR",
	"DS-DRIFT_DRIFTSPERSONELL_CITRIX_APPV_ADMIN",
	"DS-DRIFT_DRIFTSPERSONELL_CITRIX_CITRIX_NETSCALER_ADM",
	"DS-DRIFT_DRIFTSPERSONELL_CITRIX_ADMINISTRATOR",
	"DS-DRIFT_DRIFTSPERSONELL_CITRIX_DRIFT",
	# annet
	"DS-DRIFT_DRIFTSPERSONELL_SERVERMGMT_ADMINDC",
	"DS-DRIFT_DRIFTSPERSONELL_MAIL_EXH_FULL_ADMINISTRATOR",
	"DS-DRIFT_DRIFTSPERSONELL_ACCESSMGMT_OVERGREPSMOTTAKET",
	"Steria Admin",
	"GS-SAM-SharepointAdmin_IS",
	"GS-NAE-EQUITRAC_ADMIN",
	"Task-OF2-EGE-JumpserverAdmin",
]

class Profile(models.Model):
	#https://simpleisbetterthancomplex.com/tutorial/2016/07/22/how-to-extend-django-user-model.html
	user = models.OneToOneField(
			to=User,
			on_delete=models.CASCADE,  # slett profilen når brukeren slettes
			)
	distinguishedname = models.TextField(
			verbose_name="Distinguishedname (AD)",
			blank=True,
			null=True,
			)
	ou = models.ForeignKey(
			to="ADOrgUnit",
			related_name='profile_ou',
			on_delete=models.PROTECT,
			verbose_name="OU-parent",
			blank=True,
			null=True,
			)
	displayName = models.CharField(
			verbose_name="Visningsnavn (AD)",
			max_length=300,
			blank=True,
			null=True,
			)
	lastLogonTimestamp = models.DateTimeField(
			verbose_name="Sist innlogget (AD)",
			null=True,
			blank=True,
			)
	userPasswordExpiry = models.DateTimeField(
			verbose_name="Dato neste passordbytte",
			null=True,
			blank=True,
			)
	whenCreated = models.DateTimeField(
			verbose_name="Bruker opprettet",
			null=True,
			blank=True,
			)
	pwdLastSet = models.DateTimeField(
			verbose_name="Passord sist endret",
			null=True,
			blank=True,
			)
	virksomhet = models.ForeignKey(
			to=Virksomhet,
			related_name='brukers_virksomhet',
			on_delete=models.SET_NULL,
			verbose_name="Virksomhet / Etat: Representerer",
			blank=True,
			null=True,
			)
	virksomhet_innlogget_som = models.ForeignKey(
			to=Virksomhet,
			related_name='brukers_virksomhet_innlogget_som',
			on_delete=models.SET_NULL,
			verbose_name="Virksomhet / Etat: Innlogget som",
			blank=True,
			null=True,
			)
	from_prk = models.BooleanField(
			verbose_name="Fra PRK?",
			default=False,
			)
	ekstern_ressurs = models.BooleanField(
			verbose_name="Ekstern ressurs? (AD)",
			null=True,
			blank=True,
			default=None,
			)
	usertype = models.CharField(
			verbose_name="Brukertype (PRK)",
			max_length=20,
			null=True,
			blank=True,
			)
	account_type = models.CharField(
			verbose_name="Brukertype (AD)",
			max_length=30,
			null=True,
			blank=True,
			)
	description = models.TextField(
			verbose_name="Beskrivelse (AD)",
			blank=True,
			null=True,
			)
	userAccountControl = models.TextField(
			verbose_name="User Account Control (AD)",
			blank=True,
			null=True,
			)
	accountdisable = models.BooleanField(
			verbose_name="Account disable (AD)",
			default=False,
			help_text="Importeres fra AD",
			)
	lockout = models.BooleanField(
			verbose_name="Lockout (AD)",
			default=False,
			)
	passwd_notreqd = models.BooleanField(
			verbose_name="Passwd notreqd (AD)",
			default=False,
			)
	dont_expire_password = models.BooleanField(
			verbose_name="Dont expire password (AD)",
			default=False,
			)
	password_expired = models.BooleanField(
			verbose_name="Password expired (AD)",
			default=False,
			)
	org_unit = models.ForeignKey(
			to='HRorg',
			related_name='profile_org_unit',
			on_delete=models.PROTECT,
			verbose_name='Organisatorisk tilhørighet (PRK)',
			null=True,
			blank=True,
			)
	ansattnr = models.IntegerField(
			verbose_name="Ansattnr (PRK)",
			blank=True,
			null=True,
			)
	ansattnr_ref = models.ForeignKey(
			to="AnsattID",
			related_name='userprofile',
			on_delete=models.SET_NULL,
			null=True,
			blank=True,
			)
	ansattnr_antall = models.IntegerField(
			verbose_name="Antall koblede kontoer",
			blank=True,
			null=True,
			)
	adgrupper = models.ManyToManyField(
			to="ADgroup",
			related_name='user',
			verbose_name="Medlemskap i grupper (AD)",
			blank=True,
			help_text=u'Settes via automatiske jobber',
			)
	adgrupper_antall = models.IntegerField(
			verbose_name="Antall gruppemedlemskap",
			blank=True,
			null=True,
			help_text=u'Settes via automatiske jobber',
			)
	trusted_for_delegation = models.BooleanField(
			verbose_name="trusted_for_delegation",
			blank=True,
			null=True,
			default=False,
			)
	trusted_to_auth_for_delegation = models.BooleanField(
			verbose_name="trusted_for_delegation",
			blank=True,
			null=True,
			default=False,
			)
	not_delegated = models.BooleanField(
			verbose_name="not_delegated",
			blank=True,
			null=True,
			)
	dont_req_preauth = models.BooleanField(
			verbose_name="dont_req_preauth",
			blank=True,
			null=True,
			)
	o365lisence = models.IntegerField(
			choices=LISENCE_VALG,
			verbose_name="Lisenser Office365",
			blank=True,
			default=0,
			help_text=u'Settes automatisk',
			)
	service_principal_name = models.CharField(
			verbose_name="Service Principal Name (AD)",
			max_length=256,
			blank=True,
			null=True,
			)
	object_sid = models.CharField(
			verbose_name="Object SID",
			max_length=128,
			blank=True,
			null=True,
			db_index=True,
			)
	# med vilje er det ikke HistoricalRecords() på denne

	def __str__(self):
		return u'%s' % (self.user)

	class Meta:
		verbose_name_plural = "System: Brukerprofiler"

	@receiver(post_save, sender=User)
	def create_user_profile(sender, instance, created, **kwargs):
		if created:
			Profile.objects.create(user=instance)

	@receiver(post_save, sender=User)
	def save_user_profile(sender, instance, **kwargs):
		instance.profile.save()


	def levtilgangprofil(self):
		alle_levprofiler = Leverandortilgang.objects.all()
		alle_grupper = self.adgrupper.all()
		systemer = list()

		for levprofile in alle_levprofiler:
			for adgrp in levprofile.adgrupper.all():
				if adgrp in alle_grupper:
					systemer.extend(levprofile.systemer.all())

		return [system.systemnavn for system in systemer]


	def kopiav(self):
		username = self.user.username.lower()
		if username.startswith("t-"):
			try:
				username = username.replace("t-","")
				return User.objects.get(username=username)
			except:
				pass
		if username.startswith("t_"):
			try:
				username = username.replace("t_","")
				return User.objects.get(username=username)
			except:
				pass
		if "_t" in username:
			try:
				username = username.split("_t")[0]
				return User.objects.get(username=username)
			except:
				pass
		return "Ukjent"

	def org_tilhorighet(self):
		try:
			enhet = self.org_unit
			enhet_str = "%s" % (enhet)
			current_level = enhet.level
			while current_level > 3:  # level 2 er virksomheter, så vi ønsket et nivå over
				mor_enhet = enhet.direkte_mor
				enhet_str = "%s - %s" % (mor_enhet, enhet_str)
				mor_level = mor_enhet.level
				if current_level > mor_level:
					enhet = mor_enhet
					current_level = mor_level
				else:
					break
			return enhet_str
		except:
			return "Ukjent tilhørighet"

	def avdeling(self):
		try:
			enhet = self.org_unit
			current_level = enhet.level
			while current_level > 3:  # level 2 er virksomheter, så vi ønsket et nivå over
				mor_enhet = enhet.direkte_mor
				mor_level = mor_enhet.level
				if current_level > mor_level:
					enhet = mor_enhet
					current_level = mor_level
				else:
					break
			return enhet
		except:
			return None

	def ou_lesbar(self):
		if self.distinguishedname != None:
			return self.distinguishedname.split(",")[1:-4]
		return ""


	def ad_grp_lookup(self):
		try:
			from systemoversikt.views import ldap_users_securitygroups, convert_distinguishedname_cn
			return sorted(convert_distinguishedname_cn(ldap_users_securitygroups(self.user.username)))
		except:
			return  ["AD ikke tilgjengelig"]

	def priveligert_bruker(self):
		for gruppe in self.adgrupper.all():
			if any(pg.lower() in gruppe.common_name.lower() for pg in PRIVELIGERTE_GRUPPER):
				return "Ja"
		return "Nei"


class Leverandor(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	leverandor_navn = models.CharField(
			unique=True,
			verbose_name="Leverandørens navn",
			max_length=350,
			help_text=u"",
			)
	kontaktpersoner = models.TextField(
			verbose_name="Adresse og kontaktpersoner",
			blank=True,
			null=True,
			help_text=u"",
			)
	orgnummer = models.CharField(
			verbose_name="Organisasjonsnummer",
			max_length=30,
			blank=True,
			null=True,
			help_text=u"",
			)
	notater = models.TextField(
			verbose_name="Notater",
			blank=True,
			null=True,
			help_text=u"",
			)
	godkjent_opptaks_sertifiseringsordning = models.TextField(
			verbose_name="Er leverandørene registrert på en godkjent opptaks- eller sertifiseringsordning? Beskriv hvilke.",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.leverandor_navn)

	class Meta:
		verbose_name_plural = "Organisasjon: Leverandører"
		default_permissions = ('add', 'change', 'delete', 'view')





class InformasjonsKlasse(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.TextField(
			verbose_name="Navn på klasse",
			blank=True,
			null=True,
			help_text=u"",
			)
	beskrivelse = models.TextField(
			verbose_name="Beskrivelse av informasjonsklassen",
			blank=True,
			null=True,
			help_text=u"F.eks. henvisning til lover som gjelder",
			)

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Behandling: Informasjonsklasser"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['navn']

class SystemKategori(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	kategorinavn = models.CharField(
			unique=True,
			verbose_name="Kategorinavn",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"",
			)
	hovedkategori = models.ForeignKey(
			to="SystemHovedKategori",
			related_name='systemkategori_hovedkategori',
			on_delete=models.PROTECT,
			verbose_name="Hovedkategori",
			null=True,
			blank=True,
			help_text=u'Velg en hovedkategori denne kategorien skal tilhøre.',
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"Slik at andre kan vurdere passende kategorier",
			)
	history = HistoricalRecords()

	def __str__(self):
		if len(self.systemhovedkategori_systemkategorier.all()) > 0:
			# hvis flere, tar vi den første. Det skal ikke være flere, men det er litt knotete å endre til foreignkey-relasjon
			return u'%s (%s)' % (self.kategorinavn, self.systemhovedkategori_systemkategorier.all()[0].hovedkategorinavn)
		else:
			return u'%s' % (self.kategorinavn)

	class Meta:
		verbose_name_plural = "Systemkategori: Systemkategorier"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['kategorinavn']



class SystemHovedKategori(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	hovedkategorinavn = models.CharField(
			unique=True,
			verbose_name="Kategorinavn",
			max_length=30,
			blank=False,
			null=False,
			help_text=u"",
			)
	definisjon = models.CharField(
			verbose_name="Definisjon",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Slik at andre kan vurdere passende kategorier",
			)
	subkategorier = models.ManyToManyField(
			to=SystemKategori,
			related_name='systemhovedkategori_systemkategorier',
			verbose_name="Subkategorier",
			blank=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.hovedkategorinavn)

	class Meta:
		verbose_name_plural = "Systemkategori: Systemhovedkategorier"
		verbose_name = "systemhovedkategori"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['hovedkategorinavn']



MAALGRUPPE_VALG = (
	(1, 'Innbyggere'),
	(2, 'Ansatte'),
	(3, 'Leverandører'),
)

SIKKERHETSTESTING_VALG = (
	(1, "1 Svært lite aktuelt"),
	(2, "2 Lite aktuelt"),
	(3, "3 Kan vurderes"),
	(4, "4 Aktuelt"),
	(5, "5 Meget aktuelt"),
)

class SystemUrl(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	domene = models.URLField(
			unique=True,
			verbose_name="Domene",
			max_length=600,
			blank=False,
			null=False,
			help_text=u"",
			)
	https = models.BooleanField(
			verbose_name="Sikret med https?",
			blank=True,
			null=True,
			default=None,
			help_text=u"",
			)
	maalgruppe = models.IntegerField(
			choices=MAALGRUPPE_VALG,
			verbose_name="Målgruppe",
			blank=True,
			null=True,
			help_text=u'Hvem kan bruke / nå tjenesten på denne URL-en?',
			)
	vurdering_sikkerhetstest = models.IntegerField(
			choices=SIKKERHETSTESTING_VALG,
			verbose_name="Vurdering sikkerhetstest",
			blank=True,
			null=True,
			help_text=u'Hvor aktuelt er det å sikkerhetsteste denne tjenesten?',
			)
	registrar = models.ForeignKey(
			to=Leverandor,
			related_name='systemurl_registrar',
			on_delete=models.PROTECT,
			verbose_name="Domeneregistrar",
			null=True,
			blank=True,
			help_text=u'Leverandør som domenet er registrert hos',
			)
	eier = models.ForeignKey(
			to=Virksomhet,
			on_delete=models.PROTECT,
			verbose_name="Eier av domenet",
			related_name='systemurl_eier',
			null=True,
			blank=True,
			help_text=u'Virksomheten som eier domenet',
			)
	kommentar = models.TextField(
			verbose_name="Kommentar (fritekst)",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.domene)

	def vis_registrar(self):
		if "oslo.kommune.no" in self.domene:
			return "Oslo kommune"
		return self.registrar

	def own_domain(self):
		# hardkodet her
		if "oslo.kommune.no" in self.domene:
			return True
		else:
			return False

	class Meta:
		verbose_name_plural = "Systemoversikt: URL-er"
		verbose_name = "URL"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['domene']



class Personsonopplysningskategori(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.CharField(
			unique=True,
			verbose_name="Kategorinavn",
			max_length=600,
			blank=False,
			null=False,
			help_text=u"",
			)
	artikkel = models.IntegerField(
			verbose_name="Artikkelreferanse",
			blank=True,
			null=True,
			default=None,
			help_text=u"",
			)
	hovedkategori = models.CharField(
			verbose_name="Hovedkategori",
			blank=False,
			null=False,
			max_length=600,
			help_text=u"",
			)
	eksempler = models.TextField(
			verbose_name="Eksempler",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Behandling: Personopplysningskategorier"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['navn']



class Registrerte(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	kategorinavn = models.CharField(
			unique=True,
			verbose_name="Kategorinavn",
			max_length=600,
			blank=False,
			null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"Beskrivelse av kategori og noen eksempler.",
			)
	saarbar_gruppe = models.BooleanField(
			verbose_name="Sårbar gruppe?",
			default=False,
			blank=True,
			null=True,
			help_text=u"",
			)

	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.kategorinavn)

	class Meta:
		verbose_name_plural = "Behandling: Kategorier registrerte"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['kategorinavn']



class Behandlingsgrunnlag(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	grunnlag = models.CharField(
			unique=True,
			verbose_name="Behandlingsgrunnlag",
			max_length=600,
			blank=False,
			null=False,
			help_text=u"Forkortet tittel på formålet",
			)
	lovparagraf = models.CharField(
			unique=False,
			verbose_name="Paragrafhenvisning",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Paragraf i loven",
			)
	lov = models.CharField(
			unique=False,
			verbose_name="Lovhenvisning",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Navnet på loven",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s (%s)' % (self.grunnlag, self.lovparagraf)

	class Meta:
		verbose_name_plural = "Behandling: Behandlingsgrunnlag"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['grunnlag']



CMDB_KRITIKALITET_VALG = (
	(1, '1: most critical'),
	(2, '2: somewhat critical'),
	(3, '3: less critical'),
	(4, '4: not critical'),
)

CMDB_TYPE_VALG = (
	(1, 'Et system'),
	(2, 'Ukjent'),
	(3, 'En infrastrukturkomponent'),
	(4, 'En samlekategori (BusinessService)'),
	(5, 'For fakturering'),
	(6, 'Tom / ikke i bruk'),
)

CMDB_ENV_VALG = (
	(1, 'Produksjon'),
	(2, 'Test/demonstration'),
	(3, 'Utvikling'),
	(4, 'Kurs'),
	(5, 'Referansemiljø'),
	(6, 'Staging'),
	(7, 'QA'),
	(8, 'Ukjent'),
	(9, "Disaster recovery"),
)

CMDB_OPERATIONAL_STATUS = (
	(1, 'Operational'),
	(0, 'Not operational'),
)

# Dette er nivå 1 av CMDB-modellen, såkalt "business Service" i Service Now Common Service Data Model
class CMDBbs(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.CharField(
			verbose_name="CMDB-navn",
			max_length=600,
			blank=False,
			null=False,
			help_text=u"Importert",
			)
	bs_external_ref = models.CharField(
			unique=True,
			verbose_name="ForeignKey mot ServiceNow",
			max_length=64,
			blank=False,
			null=True,
			help_text=u"Importert",
			)
	operational_status = models.BooleanField(
			verbose_name="I bruk i ServiceNow",
			default=True,
			)
	eksponert_for_bruker = models.BooleanField(
			verbose_name="Eksponert mot bruker",
			default=True,
			)
	# med vilje er det ikke HistoricalRecords() på denne da den importeres regelmessig

	def __str__(self):
		return u'%s' % (self.navn)

	def backup_size(self):
		total = 0
		for bss in self.cmdb_bss_to_bs.all():
			total += bss.backup_size()
		return total

	def san_used(self):
		total = 0
		for bss in self.cmdb_bss_to_bs.all():
			total += bss.san_used()
		return total

	def san_allocated(self):
		total = 0
		for bss in self.cmdb_bss_to_bs.all():
			total += bss.san_allocated()
		return total

	def san_unallocated(self):
		total = 0
		for bss in self.cmdb_bss_to_bs.all():
			total += bss.san_unallocated()
		return total

	def san_used_pct(self):
		if self.san_allocated() != 0:
			return int(self.san_used() / self.san_allocated() * 100)
		return "NaN"

	def ram_allocated(self):
		total = 0
		for bss in self.cmdb_bss_to_bs.all():
			total += bss.ram_allocated()
		return total

	def ant_bss(self):
		return self.cmdb_bss_to_bs.all().count()

	def ant_devices(self):
		counter = 0
		for bss in self.cmdb_bss_to_bs.all():
			counter += bss.ant_devices()
		return counter

	def ant_databaser(self):
		counter = 0
		for bss in self.cmdb_bss_to_bs.all():
			counter += bss.ant_databaser()
		return counter

	def most_common_child_service_classification(self):
		import collections
		own_sub_services = self.cmdb_bss_to_bs.all()
		service_classifications = [bss.service_classification for bss in own_sub_services]
		counter = collections.Counter(service_classifications)
		most_common = counter.most_common(1)
		try:
			return(most_common[0][0])
		except:
			return("Ikke mulig å identifisere")

	class Meta:
		verbose_name_plural = "CMDB: Business services"
		verbose_name = "business service"
		default_permissions = ('add', 'change', 'delete', 'view')



# Dette er nivå 2 av CMDB-modellen, såkalt "Business Service Offering" i Service Now Common Service Data Model
# Er koblet til nivå 1, men nivå 1 er bare en "sekkepost" eller kategori, og er derfor ikke nyttig.
# Det er under disse servere og databaser modelleres inn.
# Systemer har kobling til 0, 1 eller flere slike nivå2 offerings.
class CMDBRef(models.Model): # BSS
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.CharField(
			unique=False, # eksporter fra cmdb er ikke konsistente desverre..
			verbose_name="Sub service navn",
			max_length=600,
			blank=False,
			null=False,
			help_text=u"Importert",
			db_index=True,
			)
	operational_status = models.IntegerField(
			choices=CMDB_OPERATIONAL_STATUS,
			verbose_name="Operational status",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	parent_ref = models.ForeignKey(
			to=CMDBbs,
			related_name='cmdb_bss_to_bs',
			on_delete=models.CASCADE,
			blank=True,
			null=True,
			verbose_name="Tilhørerende Business service",
			help_text=u"Importert",
			)
	environment = models.IntegerField(
			choices=CMDB_ENV_VALG,
			verbose_name="Miljø",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	kritikalitet = models.IntegerField(
			choices=CMDB_KRITIKALITET_VALG,
			verbose_name="Busines criticality (SLA)",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	u_service_availability = models.CharField(
			max_length=50,
			verbose_name="Availability",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	u_service_operation_factor = models.CharField(
			max_length=50,
			verbose_name="operation factor",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	u_service_complexity = models.CharField(
			max_length=50,
			verbose_name="Complexity",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	u_service_billable = models.BooleanField(
			verbose_name="Billable?",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	service_classification = models.CharField(
			max_length=150,
			verbose_name="service classification",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	comments = models.TextField(
			verbose_name="Kommentar",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	bss_external_ref = models.CharField(
			unique=True,
			verbose_name="ForeignKey mot ServiceNow",
			max_length=64,
			blank=False,
			null=True,
			help_text=u"Importert",
			)
	# med vilje er det ikke HistoricalRecords() på denne da den importeres regelmessig

	def __str__(self):
		if self.is_bss():
			return u'%s' % (self.navn)
		else:
			return u'%s (servergruppe)' % (self.navn)

	def er_produksjon(self):
		if self.environment == 1:
			return True
		return False

	def alle_dns(self):
		dnsrecords = set()
		for server in self.servers.all():
			# direkte dns-navn mot server
			for netaddr in server.network_ip_address.all():
				for dnsrec in netaddr.dns.all():
					dnsrecords.add(dnsrec)

			# indirekte dns-navn mot vip knyttet mot pool som server er medlem i
			for pool in server.vip_pool.all():
				#print("0", pool)
				for vip in pool.vip.all():
					#print("1",vip)
					for netaddr in vip.network_ip_address.all():
						#print("2",netaddr)
						for dnsrec in netaddr.dns.all():
							dnsrecords.add(dnsrec)
							#print("3",dnsrec)

		return dnsrecords

	def antall_dns_rec(self):
		return len(self.alle_dns())


	def backup_size(self):
		total = CMDBbackup.objects.filter(device__service_offerings=self).aggregate(Sum('backup_size_bytes'))["backup_size_bytes__sum"]
		if total == None:
			return 0
		return total

	def san_used(self):
		total = CMDBdevice.objects.filter(service_offerings=self).aggregate(Sum('vm_disk_usage'))["vm_disk_usage__sum"]
		if total == None:
			return 0
		return total

	def san_allocated(self):
		total = CMDBdevice.objects.filter(service_offerings=self).aggregate(Sum('vm_disk_allocation'))["vm_disk_allocation__sum"]
		if total == None:
			return 0
		return total

	def san_unallocated(self):
		return self.san_allocated() - self.san_used()

	def san_used_pct(self):
		if self.san_allocated() != 0:
			return int(self.san_used() / self.san_allocated() * 100)
		return "NaN"

	def ram_allocated(self):
		total = CMDBdevice.objects.filter(service_offerings=self).aggregate(Sum('comp_ram'))["comp_ram__sum"]
		if total == None:
			return 0
		return total * 1000**2 # MB til bytes

	def u_service_availability_text(self):
		lookup = {
			"T1": "T1🟢: 24/7/365, 99.9%",
			"T2": "T2🟢: 07-20 alle dager, 99.5%",
			"T3": "T3🟡: 07-16 virkedager, 99%",
			"T4": "T4🔴: Best effort",
			"E1": "E1🟡: Egendrift",
		}
		try:
			return lookup[self.u_service_availability]
		except:
			return self.u_service_availability


	def u_service_operation_factor_text(self):
		lookup = {
			"D1": "D1🔴: Liv og helse",
			"D2": "D2🔴: Virksomhetskritisk",
			"D3": "D3🟡: Kritisk",
			"D4": "D4🟡: Periodisk kritisk",
			"D5": "D5🟢: Ikke kritisk",
		}
		try:
			return lookup[self.u_service_operation_factor]
		except:
			return self.u_service_operation_factor


	def u_service_complexity_text(self):
		lookup = {
			"K1": "K1 🟢: 0-100 brukere, enkelt omfang",
			"K2": "K2 🟡: 0-100 brukere, middels omfang",
			"K3": "K3 🔴: 0-100 brukere, høyt omfang",
			"K4": "K4 🟡: 100-1000 brukere, enkelt omfang",
			"K5": "K5 🟡: 100-1000 brukere, middels omfang",
			"K6": "K6 🔴: 100-1000 brukere, høyt omfang",
			"K7": "K7 🟡: 1000+ brukere, enkelt omfang",
			"K8": "K8 🔴: 1000+ brukere, middels omfang",
			"K9": "K9 🔴: 1000+ brukere, høyt omfang",
		}
		try:
			return lookup[self.u_service_complexity]
		except:
			return self.u_service_complexity

	def er_infrastruktur_tom_bs(self):
		if self.cmdb_type in [3, 4, 6]:
			return True
		else:
			return False

	def er_ukjent(self):
		if self.cmdb_type == 2:
			return True
		else:
			return False

	def ant_devices(self):
		return CMDBdevice.objects.filter(service_offerings=self.pk).count()

	def ant_databaser(self):
		return CMDBdatabase.objects.filter(sub_name=self.pk, db_operational_status=True).count()

	def is_bss(self):
		if self.service_classification == "Business Service":
			return True
		else:
			return False

	def vlan(self):
		alle_vlan = set()
		for server in CMDBdevice.objects.filter(service_offerings=self.pk):
			for ipaddr in server.network_ip_address.all():
				for vlan in ipaddr.vlan.all():
					alle_vlan.add(vlan)


		for database in CMDBdatabase.objects.filter(sub_name=self.pk, db_operational_status=True):
			dbserver = CMDBdevice.objects.get(comp_name=database.db_server)
			for ipaddr in dbserver.network_ip_address.all():
				for vlan in ipaddr.vlan.all():
					alle_vlan.add(vlan)

		return list(alle_vlan)


	class Meta:
		verbose_name_plural = "CMDB: Business service offerings"
		verbose_name = "service offering"
		default_permissions = ('add', 'change', 'delete', 'view')



class virtualIP(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	vip_name = models.CharField(
			max_length=200,
			null=True,
			unique=True,
			verbose_name="VIP name",
			)
	pool_name =models.CharField(
			max_length=200,
			null=True,
			verbose_name="Pool name",
			)
	ip_address = models.GenericIPAddressField(
			null=False,
			verbose_name="IP-adresse",
			)
	port = models.IntegerField(
			null=False,
			verbose_name="Port",
			)
	hitcount = models.IntegerField(
			null=False,
			verbose_name="Hitcount",
			)

	def __str__(self):
		return self.vip_name

	class Meta:
		verbose_name_plural = "CMDB: Virtual IPs"
		verbose_name = "virtual IP"
		default_permissions = ('add', 'change', 'delete', 'view')

	def nested_pool_members(self):
		members = []
		candidates = list(self.pool_members.all())
		already_seen = []

		while candidates:
			current_candidate = candidates.pop()
			already_seen.append(current_candidate)
			#print(current_candidate)
			if current_candidate.server:
				members.append(current_candidate)
				continue

			new_candidates = list(current_candidate.indirect_pool_members())
			for candidate in new_candidates:
				if candidate not in candidates and candidate not in already_seen:
					candidates.append(candidate)

		return members


class IpProtocol(models.Model):
	port = models.IntegerField(
		null=False,
		)
	protocol = models.CharField(
		max_length=10,
		null=False,
		)
	description = models.TextField(
		null=True,
		)

	def __str__(self):
		return f"IP protokoll {self.protocol} {self.port}"

	class Meta:
		verbose_name_plural = "CMDB: IP-protokoller"
		default_permissions = ('add', 'change', 'delete', 'view')



class VirtualIPPool(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	pool_name = models.CharField(
			max_length=200,
			null=False,
			verbose_name="Pool name",
			)
	ip_address = models.GenericIPAddressField(
			null=False,
			verbose_name="IP-adresse",
			)
	port = models.IntegerField(
			null=False,
			verbose_name="Port",
			)
	vip = models.ManyToManyField(
			to='virtualIP',
			related_name='pool_members',
			verbose_name="Tilhørende VIP",
			)
	server = models.ForeignKey(
			to='CMDBdevice',
			on_delete=models.SET_NULL,
			null=True,
			related_name='vip_pool',
			verbose_name="Server",
			)
	def __str__(self):
		return self.pool_name

	def indirect_pool_members(self):
		try:
			vip = virtualIP.objects.get(ip_address=self.ip_address, port=self.port)
			return vip.pool_members.all()
		except:
			return []


	class Meta:
		unique_together = ('pool_name', 'ip_address', 'port')
		verbose_name_plural = "CMDB: VIP pools"
		verbose_name = "VIP pool"
		default_permissions = ('add', 'change', 'delete', 'view')


class NetworkContainer(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	comment = models.CharField(
			max_length=200,
			null=True,
			verbose_name="Beskrivelse",
			)
	disabled = models.BooleanField(
			verbose_name="Deaktivert",
			default=False,
			)
	ip_address = models.GenericIPAddressField(
			null=False,
			verbose_name="IP-adresse",
			)
	subnet_mask = models.IntegerField(
			null=False,
			verbose_name="Netmask",
			)
	locationid = models.CharField(
			max_length=50,
			null=True,
			verbose_name="Location ID",
			)
	orgname = models.CharField(
			max_length=200,
			null=True,
			verbose_name="Org name",
			)
	vlanid = models.CharField(
			max_length=50,
			null=True,
			verbose_name="VLAN ID",
			)
	vrfname = models.CharField(
			max_length=200,
			null=True,
			verbose_name="VRF name",
			)
	netcategory = models.CharField(
			max_length=200,
			null=True,
			verbose_name="Kateogi",
			)
	network_zone = models.CharField(
			max_length=100,
			null=True,
			verbose_name="Nettverkssone",
			)
	network_zone_description = models.CharField(
			max_length=400,
			null=True,
			verbose_name="Nettverkssonebeskrivelse",
			)

	def __str__(self):
		return u'%s/%s' % (self.ip_address, self.subnet_mask)

	class Meta:
		unique_together = ("ip_address", "subnet_mask")
		verbose_name_plural = "CMDB: VLAN"
		verbose_name = "network container"
		default_permissions = ('add', 'change', 'delete', 'view')


class NetworkIPAddress(models.Model):
	ip_address = models.GenericIPAddressField(
		null=False,
		unique=True,
		verbose_name="IP-adresse",
	)
	ip_address_integer = models.IntegerField(
		verbose_name="IP-adresse heltall",
		null=True,
	)
	servere = models.ManyToManyField(
		to='CMDBdevice',
		verbose_name="Serverkobling",
		related_name='network_ip_address',
	)
	viper = models.ManyToManyField(
		to='virtualIP',
		verbose_name="Kobling til VIP-er",
		related_name='network_ip_address',
	)
	vip_pools = models.ManyToManyField(
		to='VirtualIPPool',
		verbose_name="Kobling til VIP pool-er",
		related_name='network_ip_address',
	)
	dns = models.ManyToManyField(
		to='DNSrecord',
		verbose_name="Kobling til DNS-records",
		related_name='network_ip_address',
	)
	vlan = models.ManyToManyField(
		to='NetworkContainer',
		verbose_name="Kobling til VLAN",
		related_name='network_ip_address',
	)

	class Meta:
		verbose_name_plural = "CMDB: Network IP-address"
		verbose_name = "IP-address"
		default_permissions = ('add', 'change', 'delete', 'view')

	def __str__(self):
		return u'%s' % self.ip_address

	def ant_servere(self):
		return self.servere.all().count()

	def ant_dns(self):
		return self.dns.all().count()

	def ant_vlan(self):
		return self.vlan.all().count()

	def ant_viper(self):
		return self.viper.all().count()

	def ant_pools(self):
		return self.vip_pools.all().count()

	def dominant_vlan(self):
		if self.ant_vlan() > 0:
			return self.vlan.all().order_by('-subnet_mask')[0]
		return []





class DNSrecord(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	dns_name = models.CharField(
			max_length=500,
			verbose_name="DNS name",
			)
	source = models.CharField(
			max_length=50,
			null=True,
			verbose_name="Kilde",
			)
	dns_type = models.CharField(
			max_length=50,
			null=True,
			verbose_name="DNS type",
			)
	ip_address = models.GenericIPAddressField(
			null=True,
			verbose_name="IP-adresse",
			)
	ttl = models.IntegerField(
			null=True,
			verbose_name="Time to live (TTL)",
			)
	dns_target = models.CharField(
			max_length=200,
			null=True,
			verbose_name="DNS target (hvis CNAME eller MX)",
			)
	dns_domain = models.CharField(
			max_length=200,
			null=False,
			verbose_name="Domain",
			)
	txt = models.TextField(
			verbose_name="txt-data",
			blank=True,
			null=True,
			help_text=u"DNS TXT",
			)
	unique_together = ('dns_name', 'dns_type', 'source')

	def __str__(self):
		return u'%s: %s' % (self.dns_type, self.dns_name)

	def dns_full_name(self):
		return u'%s.%s' % (self.dns_name, self.dns_domain)

	class Meta:
		verbose_name_plural = "CMDB: DNS records"
		verbose_name = "DNS-record"
		default_permissions = ('add', 'change', 'delete', 'view')


KRITISKE_KATEGORIER = (
	(1, 'Styringsevne og suvernitet'),
	(2, 'Befolkningens sikkerhet'),
	(3, 'Samfunnets funksjonalitet'),
)


class KritiskFunksjon(models.Model):
	navn = models.CharField(
			max_length=150,
			null=False,
			verbose_name="Funksjon",
			)
	kategori = models.IntegerField(
			choices=KRITISKE_KATEGORIER,
			verbose_name="Hovedkategori",
			blank=False, null=False,
			)
	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemkategori: Kritiske funksjoner"
		verbose_name = "kritisk funksjon"
		default_permissions = ('add', 'change', 'delete', 'view')

	def systemer(self):
		systemer = set()
		for kapabilitet in self.funksjoner.all():
			for system in kapabilitet.systemer.all():
				systemer.add(system)
		return list(systemer)


class KritiskKapabilitet(models.Model):
	navn = models.CharField(
			max_length=150,
			null=False,
			verbose_name="Kapabilitet",
			)
	funksjon = models.ForeignKey(
			to=KritiskFunksjon,
			related_name='funksjoner',
			verbose_name="Tilhørende funksjon",
			on_delete=models.CASCADE,
			blank=False,
			null=False,
		)
	beskrivelse = models.TextField(
			verbose_name="Beskrivelse",
			blank=True,
			null=True,
			)
	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemkategori: Kritiske kapabiliteter"
		verbose_name = "kritisk kapabilitet"
		default_permissions = ('add', 'change', 'delete', 'view')



class CMDBdatabase(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	db_operational_status = models.BooleanField(
			verbose_name="db_operational_status",
			default=True,
			)
	db_version = models.TextField(
			verbose_name="db_version",
			blank=True,
			null=True,
			help_text=u"Importert: db_version",
			)
	billable = models.BooleanField(
			verbose_name="Billable",
			default=False,
			)
	db_u_datafilessizekb = models.IntegerField( ### Det er faktisk bytes som skrives til denne. Gammelt navn fra CMDB-rapport.
			verbose_name="db_u_datafilessizekb",
			blank=True,
			null=False,
			default=0,
			help_text=u"Størrelse på database i Bytes",
			)
	db_database = models.TextField(
			verbose_name="db_database",
			blank=True,
			null=True,  # importscriptet vil ikke tillate dette, men datamodellen bryr seg ikke
			help_text=u"Importert: db_database",
			)
	db_server = models.TextField(
			verbose_name="db_server",
			blank=True,
			null=True,  # importscriptet vil ikke tillate dette, men datamodellen bryr seg ikke
			help_text=u"Importert: db_server",
			)
	db_server_modelref = models.ForeignKey(
			to="CMDBdevice",
			related_name='database_server',
			verbose_name="Referanse til server",
			on_delete=models.CASCADE,
			blank=True,
			null=True,
			help_text=u"Slått opp basert på kommentarfelt med maskinnavn",
			)
	db_used_for = models.TextField(
			verbose_name="db_used_for",
			blank=True,
			null=True,
			help_text=u"Importert: db_used_for",
			)
	db_comments = models.TextField(
			verbose_name="db_comments",
			blank=True,
			null=True,
			help_text=u"Importert: db_comments",
			)
	db_status = models.TextField(
			verbose_name="Install status",
			blank=True,
			null=True,
			help_text=u"Importert: (tidligere db_status)",
			)
	sub_name = models.ForeignKey(
			to=CMDBRef,
			related_name='cmdbdatabase_sub_name',
			verbose_name="Business Sub Service",
			on_delete=models.CASCADE,
			blank=True,
			null=True,
			help_text=u"Slått opp basert på comment-felt",
			)
	unique_together = ('db_database', 'db_server')
	# med vilje er det ikke HistoricalRecords() på denne da den importeres regelmessig

	def __str__(self):
		return u'%s' % (self.db_database)

	class Meta:
		verbose_name_plural = "CMDB: Databaser"
		verbose_name = "database"
		default_permissions = ('add', 'change', 'delete', 'view')


class QualysVuln(models.Model):
	source = models.TextField()
	server = models.ForeignKey(
			to="CMDBdevice",
			on_delete=models.SET_NULL,
			related_name='qualys_vulnerabilities',
			null=True
			)
	title = models.TextField()
	severity = models.IntegerField()
	known_exploited = models.BooleanField(default=False)
	first_seen = models.DateTimeField(null=True)
	last_seen = models.DateTimeField(null=True)
	public_facing = models.BooleanField()
	cve_info = models.TextField()
	result = models.TextField()
	os = models.TextField()
	status = models.TextField(null=True)
	ansvar_basisdrift = models.BooleanField(default=False)

	def __str__(self):
		return f"{self.source} {self.title}"

	def known_exploited_info(self):
		try:
			cves = self.cve_info.split(",")
			exploited = ExploitedVulnerability.objects.filter(cve_id__in=cves)
			return ", ".join(f"{e.cve_id}" for e in exploited)
		except:
			return f"known_exploited_info() feilet"

	class Meta:
		verbose_name_plural = "Qualys: Sårbarheter"
		verbose_name = "sårbarhet"
		default_permissions = ('add', 'change', 'delete', 'view')



class CMDBdevice(models.Model):
	opprettet = models.DateTimeField( # system
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField( # system
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	device_type = models.CharField( # SERVER, CLIENT, NETWORK
			max_length=50,
			blank=False,
			null=True,
			verbose_name="Enhetstype",
			help_text="Settes automatisk ved import",
			)
	client_model_id = models.CharField( # egen fil med detaljer som lastes etter computers-filen. Bare for klienter.
			verbose_name="Klientmodell",
			max_length=200,
			blank=True,
			null=True,
			)
	client_sist_sett = models.DateTimeField( # INGEN KILDE LENGER?
			verbose_name="Sist sett",
			null=True,
			blank=True,
			)
	client_last_loggedin_user = models.ForeignKey( # INGEN KILDE LENGER?
			to=User,
			on_delete=models.SET_NULL,
			related_name='client',
			verbose_name="Sist innloggede bruker",
			null=True,
			blank=True,
			)
	billable = models.BooleanField( # Fra CMDB computers
			verbose_name="Billable",
			default=False,
			)
	comp_name = models.CharField( # Unikt navn på server.
			unique=True,
			verbose_name="Computer name",
			max_length=600,
			blank=False,
			null=False,
			help_text=u"",
			db_index=True,
			)
	comp_disk_space = models.IntegerField(  # lagres i bytes
			verbose_name="Lagring",
			blank=True,
			null=True,
			help_text=u"",
			)
	service_offerings = models.ManyToManyField(
			to=CMDBRef,
			related_name='servers',
			verbose_name="Service Offerings",
			blank=True,
			)
	comp_ip_address = models.CharField(
			verbose_name="IP-address",
			max_length=100,
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_os = models.CharField(
			verbose_name="Operativsystem",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_os_version = models.CharField(
			verbose_name="OS versjon",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_os_readable = models.CharField(
			verbose_name="OS readable",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_os_service_pack = models.CharField(
			verbose_name="OS service pack",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_cpu_core_count = models.IntegerField(
			verbose_name="CPU core count",
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_ram = models.IntegerField(  # lagres i antall MB
			verbose_name="RAM",
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_location = models.CharField(
			verbose_name="Datasenter",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	comments = models.TextField(
			verbose_name="Comments",
			unique=False,
			null=True,
			blank=True,
			)
	description = models.TextField(
			verbose_name="Description",
			unique=False,
			null=True,
			blank=True,
			)
	client_virksomhet = models.ForeignKey(
			to="Virksomhet",
			on_delete=models.SET_NULL,
			verbose_name="Klientens tilhørende virksomhet",
			related_name='cmdbdevice_virksomhet',
			null=True,
			blank=True,
			)
	vm_disk_allocation = models.FloatField( # denne verdien resettes hver gang vmwaredata importeres, og kan brukes for å summere opp faktisk allokert disk for maskiner som er "deaktivert"
			verbose_name="VM: Disk allokert",
			null=True, blank=True,
			)
	vm_disk_usage = models.FloatField(
			verbose_name="VM: Disk i bruk",
			null=True, blank=True,
			)
	vm_disk_tier = models.CharField(
			verbose_name="VM: Disk tier",
			max_length=300,
			null=True, blank=True,
			)
	eksternt_eksponert_dato = models.DateTimeField( # settes av csirt_iplookup_api()
			verbose_name="Sist eksponert mot Internett dato",
			null=True, blank=True,
			)
	citrix_desktop_group = models.CharField(
			verbose_name="Citrix-import: desktop group name",
			max_length=500,
			null=True, blank=True,
			)
	derived_os_endoflife = models.BooleanField(default=False)
	power = models.FloatField(
			verbose_name="Kwh",
			null=True, blank=True,
			)
	# med vilje er det ikke HistoricalRecords() på denne da den importeres



	def __str__(self):
		return u'%s' % (self.comp_name)

	def disk_usage_free(self):
		if self.vm_disk_usage != None and self.vm_disk_allocation not in [None, 0]:
			return 100 - int(self.vm_disk_usage / self.vm_disk_allocation * 100)
		return "? "

	def comp_ram_byes(self):
		if self.comp_ram != None:
			return self.comp_ram * 1000**2
		return "? "

	def nat(self):
		return 'ikke implementert'

	def vlan(self):
		try:
			return ', '.join([vlan.comment for vlan in self.network_ip_address.all()[0].vlan.all()])
		except:
			return 'ingen data'

	def dns(self):
		try:
			return ', '.join([dns.dns_full_name() for dns in self.network_ip_address.all()[0].dns.all()])
		except:
			return 'ingen data'

	def backup_size(self):
		if self.backup:
			return [b.backup_size_bytes for b in self.backup.all()]
		else:
			return None

	def ratio_backup_disk(self):
		backupsize = self.backup_size() # det vil i praksis aldri være flere verdier selv om det per datamodell er mulig
		vm_disk_usage = self.vm_disk_usage
		try:
			return round(backupsize[0] / vm_disk_usage) # begge er bytes
		except:
			return "error"

	def vip(self):
		try:
			vip_names = []
			for pool in self.network_ip_address.all()[0].vip_pools.all():
				for vip in pool.vip.all():
					vip_names.append(vip)
			return ', '.join([vip.vip_name for vip in vip_names])
		except:
			return 'ingen data'


	class Meta:
		verbose_name_plural = "CMDB: Enheter"
		verbose_name = "maskin"
		default_permissions = ('add', 'change', 'delete', 'view')


class CMDBbackup(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	device_str = models.CharField(
			verbose_name="Device string",
			max_length=200,
			blank=True,
			null=True,
			)
	device = models.ForeignKey(
			to="CMDBdevice",
			related_name='backup',
			on_delete=models.CASCADE,
			verbose_name="Backup av",
			null=True,
			)
	source_type = models.CharField(
			verbose_name="Source type",
			max_length=15,
			blank=True,
			null=True,
			)
	backup_size_bytes = models.IntegerField(
			null=True,
			)
	#tas vekk 23.01.2023 da den ikke ligger i powerBI-dashboardet
	#export_date = models.DateTimeField(
	#		verbose_name="Dato uttrekk",
	#		null=True,
	#		)

	# fjernet fordi den nå har blitt mange til mange, og vi følger heller kobling fra server.
	# reintrodusert
	storage_size_bytes = models.IntegerField(
			null=True,
			)
	bss = models.ForeignKey(
			to=CMDBRef,
			related_name='backup',
			verbose_name="Business Sub Service",
			on_delete=models.CASCADE,
			blank=True,
			null=True,
			help_text=u"",
			)
	backup_frequency = models.CharField(
			verbose_name="Backup frequency",
			max_length=10,
			blank=True,
			null=True,
			)
	storage_policy = models.CharField(
			verbose_name="Storage Policy",
			max_length=100,
			blank=True,
			null=True,
			)
	environment = models.IntegerField(
			choices=CMDB_ENV_VALG,
			verbose_name="Miljø",
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	# vurdere unique_together med device_str og device?

	class Meta:
		verbose_name_plural = "CMDB: Sikkerhetskopier"
		verbose_name = "sikkerhetskopi"
		default_permissions = ('add', 'change', 'delete', 'view')

	def __str__(self):
		return u'%s %s' % (self.device, self.backup_size_bytes)



class CMDBDisk(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	operational_status = models.BooleanField(
			verbose_name="operational_status",
			default=False,
			)
	size_bytes = models.IntegerField(
			verbose_name="Size in bytes",
			blank=True,
			null=True,
			)
	#capacity = models.IntegerField(
	#		verbose_name="capacity",
	#		blank=True, null=True,
	#		)
	name = models.TextField(
			verbose_name="Name",
			unique=False,
			null=True
			)
	mount_point = models.TextField(
			verbose_name="mount_point",
			unique=False,
			null=True
			)
	#available_space = models.IntegerField(
	#		verbose_name="available_space",
	#		blank=True, null=True,
	#		)
	file_system = models.TextField(
			verbose_name="file_system",
			unique=False,
			null=True
			)
	free_space_bytes = models.IntegerField(
			verbose_name="free_space_bytes",
			blank=True,
			null=True,
			)
	computer = models.CharField(
			verbose_name="Computer ID",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	computer_ref = models.ForeignKey(
			to="CMDBdevice",
			related_name='cmdbdisk_computer',
			on_delete=models.CASCADE,
			verbose_name="Computer ref",
			blank=False,
			null=True,
			help_text=u"Mor-gruppe (importert)",
			)
	unique_together = ('computer_ref', 'mount_point')
	# med vilje er det ikke HistoricalRecords() på denne da den importeres

	def __str__(self):
		return u'%s' % (self.size_bytes)

	class Meta:
		verbose_name_plural = "CMDB: Serverdisker"
		verbose_name = "disk"
		default_permissions = ('add', 'change', 'delete', 'view')



class ADOrgUnit(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	distinguishedname = models.TextField(
			verbose_name="Fully Distinguished Name",
			unique=True,
			null=False
			)
	ou = models.CharField(
			verbose_name="Name",
			max_length=200,
			blank=True,
			null=True,
			help_text=u"",
			)
	when_created = models.CharField(
			verbose_name="When created",
			max_length=30,
			blank=True,
			null=True,
			help_text=u"",
			)
	parent = models.ForeignKey(
			to="ADOrgUnit",
			related_name='adorgunit_parent',
			on_delete=models.CASCADE,
			verbose_name="Parent",
			blank=True,
			null=True,
			help_text=u"Mor-gruppe (importert)",
			)
	# med vilje er det ikke HistoricalRecords() på denne da den importeres

	def __str__(self):
		return u'%s' % (self.distinguishedname)

	class Meta:
		verbose_name_plural = "Active Directory: OU-er"
		verbose_name = "OU"
		default_permissions = ('add', 'change', 'delete', 'view')

	def cn(self):
		if len(self.distinguishedname) > 39:
			return self.distinguishedname[0:-39]
		else:
			return self.distinguishedname


class Leverandortilgang(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.CharField(
			verbose_name="Visningsnavn",
			help_text="Valgfritt å fylle ut",
			blank=True,
			null=True,
			max_length=100,
			)
	systemer = models.ManyToManyField(
			to='System',
			related_name='leverandortilgang',
			verbose_name="Systemtilknytning",
			blank=False,
			help_text=u"Brukes for tilgang til følgende systemer",
			)
	adgrupper = models.ManyToManyField(
			to='ADgroup',
			related_name='leverandortilganger',
			verbose_name="AD-gruppeknytninger",
			blank=False,
			help_text=u"Gis tilgang via følgende AD-gruppe",
			)
	kommentar = models.TextField(
			verbose_name="Kommentar",
			help_text=u"Utdypende detaljer",
			blank=True,
			null=True,
			)
	history = HistoricalRecords()

	def __str__(self):
		if self.navn != None:
			return u'%s' % (self.navn)
		try:
			return u'Leverandørtilgang for %s' % (', '.join(s.systemnavn for s in self.systemer.all()))
		except:
			return u'Leverandørtilgang %s' % self.pk

	def systemer_vis(self):
		return ", ".join([
			system.systemnavn for system in self.systemer.all()
		])
		systemer_vis.short_description = "Systemer"

	class Meta:
		verbose_name_plural = "Systemoversikt: Leverandørtilganger"
		default_permissions = ('add', 'change', 'delete', 'view')


class ADgroup(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	distinguishedname = models.TextField(
			verbose_name="Fully Distinguished Name",
			unique=True,
			db_index=True,
			)
	display_name = models.TextField(
			verbose_name="Display Name",
			unique=False,
			null=True,
			)
	common_name = models.TextField(
			verbose_name="Common Name",
			db_index=True,
			null=True,
			)
	member = models.TextField(
			verbose_name="Medlemmer",
			blank=True,
			null=True,
			)
	membercount = models.IntegerField(
			verbose_name="Antall medlemmer",
			blank=True,
			null=True,
			)
	memberof = models.TextField(
			verbose_name="Er medlem av",
			blank=True,
			null=True,
			)
	memberofcount = models.IntegerField(
			verbose_name="Antall medlem av",
			blank=True,
			null=True,
			)
	description = models.TextField(
			verbose_name="Beskrivelse",
			blank=True,
			null=True,
			)
	from_prk = models.BooleanField(
			verbose_name="Finnes i PRK?",
			default=False,
			help_text=u"Slås opp mot 'PRKvalg' automatisk",
			)
	mail = models.TextField(
			verbose_name="Mail",
			blank=True,
			null=True,
			)
	parent = models.ForeignKey(
			to=ADOrgUnit,
			related_name='adgroup_parent',
			on_delete=models.CASCADE,
			verbose_name="Parent",
			blank=True,
			null=True,
			help_text=u"Mor-gruppe (importert)",
			)
	systemer = models.ManyToManyField(
			to="System",
			related_name='adgrupper',
			verbose_name="Systemer basert på navneoppslag",
			)
	# med vilje er det ikke HistoricalRecords() på denne da den importeres

	def __str__(self):
		if self.display_name == "" or self.display_name == None:
			return u'%s' % (self.common_name)
		return u'%s' % (self.display_name)

	class Meta:
		verbose_name_plural = "Active Directory: AD-grupper"
		verbose_name = "AD-gruppe"
		default_permissions = ('add', 'change', 'delete', 'view')

	def cn(self):
		if len(self.distinguishedname) > 39:
			return self.distinguishedname[0:-39]
		else:
			return self.distinguishedname

	def short(self):
		return self.distinguishedname[3:].split(",")[0]  # fjerner cn= og alt etter komma


	def brukere_for_virksomhet(self, virksomhet):
		try:
			alle_brukere = json.loads(self.member)
			matchede_brukere = []
			for bruker in alle_brukere:
				brukernavn = re.search(r'cn=([^\,]*)', bruker, re.I).groups()[0]
				if brukernavn.startswith(virksomhet.virksomhetsforkortelse):
					matchede_brukere.append(brukernavn)
			return len(matchede_brukere)
		except:
			return "error"

	def antall_underliggende_medlemmer(self):
		from systemoversikt.views import adgruppe_utnosting
		underliggende_grupper = adgruppe_utnosting(self)
		antall = 0
		for g in underliggende_grupper:
			antall += g.membercount
		return antall - (len(underliggende_grupper) - 1) # det er alltid én gruppe om det ikke er undergrupper


AVTALETYPE_VALG = (
	(1, 'Databehandleravtale'),
	(2, 'Driftsavtale (SSA-D)'),
	(3, 'Vedlikeholdsavtale (SSA-V)'),
	(4, 'Bistandsavtale (SSA-B)'),
	(5, 'Løpende tjenestekjøpsavtale (SSA-L)'),
	(6, 'Kjøpsavtale (SSA-K)'),
	(7, 'Forvaltningsavtale'),
	(8, 'Tjenesteavtale'),
)



class Avtale(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	avtaletype = models.IntegerField(
			choices=AVTALETYPE_VALG,
			verbose_name="Avtaletype",
			blank=True,
			null=True,
			help_text=u"Hva slags kategori avtale er dette?",
			)
	intern_avtalereferanse = models.ManyToManyField(
			to="Avtale",
			related_name='avtale_intern_avtalereferanse',
			verbose_name="Intern avtaleavhengighet",
			blank=True,
			help_text=u"Databehandleravtaler er ofte forankret i SSA-avtaler.",
			)
	kortnavn = models.CharField(
			unique=True,
			verbose_name="Kortnavn på avtale",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"Noe som er lett å søke opp. Maks 100 tegn. Må være unik",
			)
	for_system = models.ManyToManyField(
			to="System",
			related_name="avtale_for_system",
			verbose_name="Gjelder for følgende systemer",
			blank=True,
			help_text=u"For å angi system avtalen gjelder for",
			)
	for_driftsmodell = models.ManyToManyField(
			to="Driftsmodell",
			related_name="avtale",
			verbose_name="Gjelder for platformene",
			blank=True,
			help_text=u"For å angi plattform avtalen gjelder for",
			)
	beskrivelse = models.TextField(
			verbose_name="Detaljer om avtalen (fritekst)",
			blank=True,
			null=True,
			help_text=u"Her kan du utdype det du ønsker om avtalen",
			)
	virksomhet = models.ForeignKey(
			to=Virksomhet,
			related_name='databehandleravtale_virksomhet',
			on_delete=models.PROTECT,
			verbose_name="Avtalepart Oslo kommune (virksomhet)",
			blank=False,
			null=False,
			help_text=u"Den virksomhet som eier avtalen.",
			)
	avtaleansvarlig = models.ManyToManyField(
			to=Ansvarlig,
			related_name='databehandleravtale_avtaleansvarlig',
			verbose_name="Avtaleforvalter",
			blank=True,
			help_text=u"Den person (rolle) som forvalter avtalen.",
			)
	avtaleansvarlig_seksjon = models.ForeignKey(
			to='HRorg',
			related_name='avtale',
			on_delete=models.SET_NULL,
			verbose_name='Ansvarlig seksjon',
			null=True,
			blank=True,
			)
	leverandor = models.ForeignKey(
			to=Leverandor,
			related_name='databehandleravtale_leverandor',
			on_delete=models.PROTECT,
			verbose_name="Avtalepart ekstern leverandør",
			blank=True,
			null=True,
			help_text=u"Brukes dersom avtalepart er en ekstern leverandør.",
			)
	leverandor_intern = models.ForeignKey(
			to=Virksomhet,
			related_name='databehandleravtale_leverandor_intern',
			on_delete=models.PROTECT,
			verbose_name="Avtalepart intern leverandør",
			blank=True,
			null=True,
			help_text=u"Brukes dersom avtalepart er en annen virksomhet i Oslo kommune.",
			)
	avtalereferanse = models.CharField(
			verbose_name="Avtalereferanse",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Avtalereferanse, helst referanse fra et arkivsystem. Referansen bør være unik i Oslo kommune.",
			)
	dokumenturl = models.URLField(
			verbose_name="Dokument-URL",
			max_length=400,
			blank=True,
			null=True,
			help_text=u"En URL til et annet system der avtalen kan leses.",
			)
	fornying_dato = models.DateField(
			verbose_name="Dato for fornying",
			null=True,
			blank=True,
			)
	dato_signert = models.DateField(
			verbose_name="Signert dato",
			null=True,
			blank=True,
			)
	fornying_varsling_valg = models.BooleanField(
			verbose_name="Aktiver varsling",
			default=False,
			help_text=u"Denne varslingen går til avtaleforvalter. Du kan angi flere mottakere under.",
			)
	fornying_ekstra_varsling = models.ManyToManyField(
			to=Ansvarlig,
			related_name='avtale_ekstra_varsling_utlop',
			verbose_name="Andre som skal varsles før utløp",
			help_text=u"",
			blank=True,
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s med %s (%s)' % (self.kortnavn, self.leverandor, self.get_avtaletype_display())

	class Meta:
		verbose_name_plural = "Organisasjon: Avtaler"
		default_permissions = ('add', 'change', 'delete', 'view')



class Systemtype(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	kategorinavn = models.CharField(
			unique=True,
			verbose_name="Systemtypenavn",
			max_length=50,
			blank=False,
			null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"Beskrivelse av kategori og noen eksempler.",
			)
	har_url = models.BooleanField(
			verbose_name="Har slike systemer en URL?",
			default=False,
			help_text=u"Krysses av dersom det er forventet at systemer i denne kategorien har en URL.",
			)
	er_infrastruktur = models.BooleanField(
			verbose_name="Er denne kategorien infrastruktur?",
			default=False,
			help_text=u"Brukes for å identifisere systemet som er infrastruktur.",
			)
	er_integrasjon = models.BooleanField(
			verbose_name="Er denne kategorien en integrasjon?",
			default=False,
			help_text=u"Brukes for å identifisere systemet som er integrasjoner.",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.kategorinavn)

	class Meta:
		verbose_name_plural = "Systemkategori: Systemtyper"
		default_permissions = ('add', 'change', 'delete', 'view')



"""
SYSTEMTYPE_VALG = (
	('STANDALONE', 'Selvstendig klientapplikasjon'),
	('SERVERCLIENT', 'Serer-klientapplikasjon'),
	('WEB', 'Webbasert applikasjon'),
	('IOSAPP', 'iOS-App'),
	('ANDROIDAPP', 'Android-App'),
)
"""

TJENESTENIVAA_VALG = (
	('GULL', 'Gull'),
	('SOLV', 'Sølv'),
	('BRONSE', 'Bronse'),
	('AVTALE', 'Egen avtale'),
	('KAPASITET', 'Kapasitet'),
	('SERVERDRIFT', 'Serverdrift'),
	('INGEN AVTALE', 'Ingen avtale'),
	('', 'Ukjent'),
)

SYSTEMEIERSKAPSMODELL_VALG = (
	('VIRKSOMHETSSYSTEM', 'Virksomhetssystem'),
	('SEKTORSYSTEM', 'Sektorsystem'),
	('TVERRSEKTORIELT', 'Tverrsektorielt system'),
	('FELLESSYSTEM', 'Fellessystem (valgfritt)'),
	('FELLESSYSTEM_OBLIGATORISK', 'Fellessystem (obligatorisk)'),
	('STOTTE', 'IKT-støttesystem'),
)

# må lage et script som inverterer verdiene i databasen 5 til 1 og 4 til 2 samtidig som disse inverteres.
VURDERINGER_SIKKERHET_VALG = (
	(1, '🔴5 Svært alvorlig'),
	(2, '🔴4 Alvorlig'),
	(3, '🟡3 Moderat'),
	(4, '🟢2 Lav'),
	(5, '🟢1 Ubetydelig'),
	(6, '0 Ikke vurdert'),
)

#☹ 😕 😐 🙂 😃

VURDERINGER_TEKNISK_VALG = (
	(1, '1 💔 Ingen'),
	(2, '2 🧡 Delvis'),
	(3, '3 💛 Akseptabel'),
	(4, '4 💚 God'),
	(5, '5 💙 Meget god'),
)

VURDERINGER_STRATEGISK_VALG = (
	(1, '1 💔 Ingen'),
	(2, '2 🧡 Delvis'),
	(3, '3 💛 God knytning'),
	(4, '4 💚 Tydelig knytning'),
	(5, '5 💙 Sterk knytning'),
)

VURDERINGER_FUNKSJONELL_VALG = (
	(1, '1 💔 Ikke akseptabel'),
	(2, '2 🧡 Store mangler'),
	(3, '3 💛 Akseptabelt'),
	(4, '4 💚 Godt egnet'),
	(5, '5 💙 Meget godt egnet'),
)

PROGRAMVAREKATEGORI_VALG = (
	(1, 'Hyllevare'),
	(2, 'Tilpasset hyllevare'),
	(3, 'Egenutviklet'),
	(4, 'Skreddersøm'),
)

LIVSLOEP_VALG = (
	(None, '0 Ikke vurdert'),
	(1, '1 💡 Under anskaffelse/utvikling'),
	(2, '2 🤞 Nytt og moderne, men fortsatt litt umodent'),
	(3, '3 👌 Moderne og modent'),
	(4, '4 👍 Modent, men ikke lengre moderne'),
	(5, '5 ☢️ Bør/skal byttes ut'),
	(6, '6 💾 Ute av bruk, men tilgjengelig'),
	(7, '7 ❌ Fullstendig avviklet'),
	(8, '8 ❓ Ukjent'),
)

SELVBETJENING_VALG = (
	(1, 'Ja'),
	(2, 'Nei'),
	(3, 'Planlagt'),
)

SIKKERHETSNIVAA_VALG = (
	(1, '🟢 Åpen'),
	(2, '🟡 Intern'),
	(5, '🔴 Beskyttet'),
	(3, '🔴 Strengt beskyttet'),
	(4, '🔴 Gradert')
)

LEVERANSEMODELL_VALG = (
	(0, 'Vet ikke'),
	(1, 'Applikasjonsdrift'),
	(2, 'Basisdrift'),
	(3, 'Nettverksdrift'),
	(4, 'App-V'),
	(5, 'LANDesk/image'),
	(6, 'Snarvei')
)

class Region(models.Model):
	navn = models.CharField(
			unique=True,
			verbose_name="Navn på region",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"F.eks. Norge, Norden, Europa/EØS, USA, Resten av verden",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Behandling: Regioner"
		default_permissions = ('add', 'change', 'delete', 'view')


class Programvare(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	programvarenavn = models.CharField(
			unique=True,
			verbose_name="Programvarenavn",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"",
			)
	alias = models.TextField(
			verbose_name="Alias",
			blank=True,
			null=True,
			help_text=u"Alternative navn på programvaren for å avhjelpe søk. Kun enkeltord. Du kan skrive inn flere alias, gjerne separert med komma eller på hver sin linje. Disse alias brukes også for å søke opp tilgangsgrupper tilhørende systemet.",
			)
	programvarekategori = models.IntegerField(
			choices=PROGRAMVAREKATEGORI_VALG,
			verbose_name="Tilpassing",
			blank=True,
			null=True,
			help_text=u"Er programvaren spesialtilpasset våre behov?",
			)
	programvaretyper = models.ManyToManyField(
			to=Systemtype,
			related_name='programvare_programvaretyper',
			verbose_name="Programvaretype",
			blank=True,
			help_text=u"Kategori programvare?",
			)
	programvarebeskrivelse = models.TextField(
			verbose_name="Programvarebeskrivelse",
			blank=True,
			null=True,
			help_text=u"Beskriv gjerne lisensmodell og hvilken periode lisens er skaffet for. Kommenter gjerne også om det er noe spesielt med måten applikasjonen er publisert på.",
			)
	programvareleverandor = models.ManyToManyField(
			to=Leverandor,
			related_name='programvare_programvareleverandor',
			verbose_name="Programvareleverandør",
			blank=True,
			help_text=u"Leverandør av programvaren. Det vil ofte være en SSA-V (vedlikeholdsavtale) eller en SSA-B (bistandsavtale) knyttet til programvaren, men det kan også være en SSA-K (kjøpsavtale).",
			)
	kategorier = models.ManyToManyField(
			to=SystemKategori,
			related_name='programvare_systemkategorier',
			verbose_name="Kategorier",
			blank=True,
			help_text=u"")
	kommentar = models.TextField(
			verbose_name="Kommentar (ikke bruk)",
			blank=True,
			null=True,
			help_text=u"",
			)
	strategisk_egnethet = models.IntegerField(
			choices=VURDERINGER_STRATEGISK_VALG,
			verbose_name="Strategisk egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	funksjonell_egnethet = models.IntegerField(
			choices=VURDERINGER_FUNKSJONELL_VALG,
			verbose_name="Funksjonell egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	teknisk_egnethet = models.IntegerField(
			choices=VURDERINGER_TEKNISK_VALG,
			verbose_name="Teknisk egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	selvbetjening = models.IntegerField(
			choices=SELVBETJENING_VALG,
			verbose_name="Selvbetjening",
			blank=True,
			null=True,
			help_text=u"Dersom ja betyr dette at systemet har et brukergrensesnitt der brukere selv kan registrere nødvendig informasjon i systemet.",
			)
	livslop_status = models.IntegerField(
			choices=LIVSLOEP_VALG,
			verbose_name="Livsløpstatus",
			blank=True,
			null=True,
			help_text=u"",
			)
	klargjort_ny_sikkerhetsmodell = models.IntegerField(
			choices=VALG_KLARGJORT_SIKKERHETSMODELL,
			verbose_name="Status SMART-klienter",
			blank=True, null=True,
			help_text=u"Besnyttes for å kartlegge hvilke virksomheter som er klare for ny klientmodell uten permanent VPN.",
			)
	systemdokumentasjon_url = models.URLField(
			verbose_name="Systemdokumentasjon",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"URL til systemdokumentasjon",
			)
	til_cveoversikt_og_nyheter = models.BooleanField(
			verbose_name="Overføres til sårbarhetsoversikten (CVE/nyheter)",
			default=True,
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.programvarenavn)

	def alias_oppdelt(self):
		if self.alias == None:
			return []
		return self.alias.split()

	class Meta:
		verbose_name_plural = "Systemoversikt: Programvarer"
		default_permissions = ('add', 'change', 'delete', 'view')


DRIFTSTYPE_VALG = (
	(0, 'Ukjent'),
	(1, 'Privat datasenter'),
	(2, 'Offentlig sky'),
)


class Driftsmodell(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.CharField(
			verbose_name="Navn på driftsmodell",
			unique=True,
			max_length=100,
			blank=False,
			null=False,
			help_text=u"",
			)
	ansvarlig_virksomhet = models.ForeignKey(
			to=Virksomhet,
			related_name='driftsmodell_ansvarlig_virksomhet',
			on_delete=models.PROTECT,
			verbose_name="Forvalter (virksomhet)",
			blank=True,
			null=True,
			help_text=u"",
			)
	kommentar = models.TextField(
			verbose_name="Kommentarer til modellen",
			blank=True,
			null=True,
			help_text=u"Notater",
			)
	leverandor = models.ManyToManyField(
			to=Leverandor,
			related_name='driftsmodell_leverandor',
			verbose_name="Driftsleverandør",
			blank=True,
			)
	underleverandorer = models.ManyToManyField(
			to=Leverandor,
			related_name='driftsmodell_underleverandorer',
			verbose_name="Underleverandører av driftsleverandør",
			blank=True,
			)
	avtaler = models.ManyToManyField(
			to=Avtale,
			related_name='driftsmodell_avtaler',
			verbose_name="Avtalereferanser",
			blank=True,
			)
	databehandleravtale_notater = models.TextField(
			verbose_name="Status databehandleravtale",
			blank=True,
			null=True,
			help_text=u"Tilleggsinformasjon databehandleravtale, inkludert beskrivelse av eventuelle avvik fra Oslo kommunes standard databehandleravtale.",
			)
	risikovurdering = models.URLField(
			verbose_name="Link til risikovurdering",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"",
			)
	sikkerhetsnivaa = models.IntegerField(
			choices=SIKKERHETSNIVAA_VALG,
			verbose_name="Høyeste tillate sikkerhetsnivå",
			blank=True,
			null=True,
			help_text=u'Det høyeste sikkerhetsnivået modellen er godkjent for i hht <a target="_blank" href="https://confluence.oslo.kommune.no/x/y8seAw">Informasjonstyper og behandlingskrav</a>',
			)
	Tilgangsstyring_driftspersonell = models.TextField(
			verbose_name="Tilgangsstyring for driftspersonell og utviklere",
			blank=True,
			null=True,
			help_text=u"",
			)
	lokasjon_lagring_valgmeny = models.ManyToManyField(
			to=Region,
			related_name='driftsmodell_lokasjon_lagring_valgmeny',
			verbose_name="Lokasjon for lagring (valg)",
			blank=True,
			)
	lokasjon_lagring = models.TextField(
			verbose_name="Lokasjon for prosessering og lagring (utdyping)",
			blank=True,
			null=True,
			help_text=u"Hvilke land og soner prosessering og lagring finner sted.",
			)
	nettverk_segmentering = models.TextField(
			verbose_name="Designprinsipper for nettverkssegmentering",
			blank=True,
			null=True,
			help_text=u"Typisk ulike sikkerhetsnivå med regler for informasjonsflyt.",
			)
	nettverk_sammenkobling_fip = models.TextField(
			verbose_name="Kobling mot felles IKT-plattform",
			blank=True,
			null=True,
			help_text=u"Hvordan trafikk rutes backend fra plattformen til andre tjenester på felles IKT-plattform.",
			)
	sikkerhet_patching = models.TextField(
			verbose_name="Designprinsipper for patching",
			blank=True,
			null=True,
			help_text=u"Der aktuelt",
			)
	sikkerhet_antiskadevare = models.TextField(
			verbose_name="Designprinsipper for anti-skadevare (antivirus)",
			blank=True,
			null=True,
			help_text=u"Der aktuelt",
			)
	sikkerhet_backup = models.TextField(
			verbose_name="Designprinsipper for sikkerhetskopiering",
			blank=True,
			null=True,
			help_text=u"Der aktuelt",
			)
	sikkerhet_logging = models.TextField(
			verbose_name="Designprinsipper for logginnsamling",
			blank=True,
			null=True,
			help_text=u"",
			)
	sikkerhet_fysisk_sikring = models.TextField(
			verbose_name="Fysiske sikringstiltak",
			blank=True,
			null=True,
			help_text=u"Beskyttelse mot innbrudd, brann, oversvømmelse..",
			)
	anbefalte_kategorier_personopplysninger = models.ManyToManyField(
			to=Personsonopplysningskategori,
			related_name='driftsmodell_anbefalte_kategorier_personopplysninger',
			verbose_name="Kategorier personopplysninger tillat på plattformen",
			blank=True,
			help_text=u"",
			)
	type_plattform = models.IntegerField(
			choices=DRIFTSTYPE_VALG,
			verbose_name="Type driftsmiljø",
			default=0,
			blank=False,
			null=False,
			help_text=u'',
			)
	overordnet_plattform = models.ForeignKey(
			to="Driftsmodell",
			related_name='driftsmodell_overordnet_plattform',
			verbose_name="Overordnet plattform",
			blank=True,
			null=True,
			on_delete=models.PROTECT,
			help_text=u'Dersom dette er en "plattform på en plattform" kan du her henvise til hvilken plattform denne kjører på.',
			)
	utviklingsplattform = models.BooleanField(
			verbose_name="Er utviklingsplattform?",
			blank=True, null=False,
			default=False,
			help_text=u"For å vise systemer som er selvutviklet",
			)
	samarbeidspartner = models.BooleanField(
			verbose_name="Er samarbeidspartner?",
			blank=True, null=False,
			default=False,
			help_text=u"For å vise systemer som er fra samarbeidspartnere",
			)
	sort_order = models.IntegerField(
			verbose_name="Sorteringsrekkefølge",
			default=3,
			blank=False,
			null=False,
			help_text=u'Lavere tall vises først.',
			)
	history = HistoricalRecords()

	def __str__(self):
		if self.ansvarlig_virksomhet:
			return u'%s (%s)' % (self.navn, self.ansvarlig_virksomhet.virksomhetsforkortelse)
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemoversikt: Driftsplattformer"
		verbose_name = "driftsplattform"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['navn']

	def antall_systemer(self):
		return self.systemer.all().count()

	def plattform_nivaa(self):
		if self.overordnet_plattform == None:
			return 1

		seen = []
		level = 1
		while self.overordnet_plattform != None:
			if self.overordnet_plattform in seen:
				return level
			seen.append(self.overordnet_plattform)
			level += 1
		return level


class Autorisasjonsmetode(models.Model):
	navn = models.CharField(
			verbose_name="Navn på metode",
			unique=True,
			max_length=100,
			blank=False,
			null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemkategori: Autorisasjonsmetoder"
		default_permissions = ('add', 'change', 'delete', 'view')



class Autentiseringsteknologi(models.Model):
	navn = models.CharField(
			verbose_name="Autentiseringsteknologi",
			unique=True,
			max_length=100,
			blank=False,
			null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemkategori: Autentiseringsteknologi"
		default_permissions = ('add', 'change', 'delete', 'view')


class Autentiseringsmetode(models.Model):
	navn = models.CharField(
			verbose_name="Autentiseringsnivå",
			unique=True,
			max_length=100,
			blank=False,
			null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemkategori: Autentiseringsmetoder"
		default_permissions = ('add', 'change', 'delete', 'view')


class Loggkategori(models.Model):
	navn = models.CharField(
			verbose_name="Loggtype", unique=True,
			max_length=100,
			blank=False,
			null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "System: Loggkategorier"
		default_permissions = ('add', 'change', 'delete', 'view')


DB_VALG = (
	(1, 'MSSQL: Hotell på felles IKT-plattform'),
	(2, 'MSSQL: Annen drift'),
	(3, 'Oracle: Hotell på felles IKT-plattform'),
	(4, 'Oracle: Annen drift'),
	(5, 'SQLite'),
	(6, 'PostgreSQL'),
	(7, 'MySQL'),
	(8, 'Firebird'),
)

VALG_RISIKOVURDERING_BEHOVSVURDERING = (
	(0, 'Ikke behov / inngår i annet systems risikovurdering'),
	(1, 'Bør utføres, men ikke høyt prioritert'),
	(2, 'Må utføres, prioritert'),
)



class RapportGruppemedlemskaper(models.Model):
	opprettet = models.DateTimeField(
			auto_now_add=True,
			null=True,
			)
	kategori = models.CharField(
			max_length=100,
			blank=False,
			null=False,
			)
	beskrivelse = models.CharField(
			max_length=250,
			blank=False,
			null=False,
			)
	kommentar = models.CharField(
			max_length=250,
			blank=True,
			null=True,
			)
	grupper = models.ManyToManyField(
			to=ADgroup,
			related_name='rapport_enkel',
			)
	AND_grupper = models.ManyToManyField(
			to=ADgroup,
			related_name='rapport_kombinasjon',
			blank=True,
			)
	tidslinjedata = models.TextField(
			blank=True,
			null=True,
			)

	def __str__(self):
		return f'{self.kategori} {self.beskrivelse}'

	class Meta:
		verbose_name_plural = "Rapport: Innhentingsbehov AD-grupper"
		default_permissions = ('add', 'change', 'delete', 'view')



class Oppdatering(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	tidspunkt = models.DateTimeField(
			verbose_name="Tidspunkt",
			blank=True,
			null=True,
			help_text=u"YYYY-MM-DD eksempel 2019-05-05 (tidspunkt er påkrevet - sett 'Nå')",
			)
	kommentar = models.CharField(
			verbose_name="Kort kommentar",
			max_length=200,
			blank=False, null=False,
			help_text=u""
			)
	user = models.OneToOneField(
			to=User,
			on_delete=models.PROTECT,
			)

	def __str__(self):
		return u'Oppdatering %s' % (self.pk)

	class Meta:
		verbose_name_plural = "System: Dataoppdateringer"
		default_permissions = ('add', 'change', 'delete', 'view')


class Database(models.Model):
	navn = models.CharField(
			verbose_name="Navn",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"Navn på databasetype"
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemkategori: Databasetyper"
		verbose_name = "databasetype"
		default_permissions = ('add', 'change', 'delete', 'view')



SYSTEM_COLORS = {
	"samarbeidspartner": "#FFCA28",
	"ukjent": '#E0E0E0',
	"saas": '#81C784',
	"drift_uke_privat": '#E57373',
	"drift_uke_sky": '#FFCDD2',
	"drift_virksomhet_privat": '#64B5F6',
	"drift_virksomhet_sky": '#BBDEFB',
	"infrastruktur": '#d2b5d9',
	"integrasjon": '#b189bb',
	"egenutviklet": '#e3b27f',
}


VALG_SYSTEM_INTEGRATION_DIRECTION = (
	("RECIEVE", "Mottar opplysninger fra destinasjon"),
	("DELIVER", "Avleverer opplysninger til destinasjon"),
	("BOTH", "Overføring av opplysninger begge retninger"),
)

VALG_SYSTEM_INTEGRATION_TYPE = (
	("INTEGRATION", "Informasjonsoverføring"),
	("AUTHENTICATION", "Federert pålogging"),
	("PUBLICATION", "Applikasjonspublisering"),
	("COMPONENT", "Tilhørende systemkomponent"),
)


class SystemIntegration(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	source_system = models.ForeignKey(
			to='System',
			related_name='system_integration_source',
			on_delete=models.CASCADE,
			verbose_name="Kildesystem",
			blank=False,
			null=False,
			)
	destination_system = models.ForeignKey(
			to='System',
			related_name='system_integration_destination',
			on_delete=models.CASCADE,
			verbose_name="Destinasjonssystem",
			blank=False,
			null=False,
			)
	integration_type = models.CharField(
			choices=VALG_SYSTEM_INTEGRATION_TYPE,
			verbose_name="Type avhengighet",
			max_length=50,
			blank=False,
			null=False,
		)
	personopplysninger = models.BooleanField(
			verbose_name="Overføres personopplysninger?",
			blank=True,
			null=True,
			)
	description = models.TextField(
			verbose_name="Tekstlig beskrivelse",
			blank=True,
			null=True,
			help_text=u"Relevant informasjon om integrasjonen. F.eks. hva som overføres av informasjon, frekvens og protokoll.",
			)
	history = HistoricalRecords()

	unique_together = ('source_system', 'destination_system', 'integration_type')



	def __str__(self):
		return f'{self.integration_type} fra {self.source_system} til {self.destination_system}'

	class Meta:
		verbose_name_plural = "Systemoversikt: Systemavhengigheter"
		verbose_name = "systemintegrasjon"
		default_permissions = ('add', 'change', 'delete', 'view')

	def color(self):
		if self.integration_type == "INTEGRATION":
			return "#A6B4F3"
		if self.integration_type == "AUTHENTICATION":
			return "#DCA7A7"
		if self.integration_type == "PUBLICATION":
			return "#A7BD64"
		if self.integration_type == "COMPONENT":
			return "#C6C6C6"

		return "black"



class System(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	ibruk = models.BooleanField(
			verbose_name="Er systemet i bruk?",
			blank=True,
			null=False,
			default=True,
			help_text=u"Ble tidligere benyttet for å skjule system fra noen visninger. Bruk heller Livsløpstatus-feltet.",
			)
	kvalitetssikret = models.OneToOneField(
			to=Oppdatering,
			related_name='system_kvalitetssikret',
			verbose_name="Kvalitetssikret",
			blank=True,
			null=True,
			on_delete=models.PROTECT,
			help_text=u"Tidspunkt informasjonen er kvalitetssikret.",
			)
	informasjon_kvalitetssikret = models.BooleanField(
			verbose_name="Er informasjonen kvalitetssikret av forvalter?",
			default=False,
			help_text=u"Krysses av når ansvarlig har kontrollert at opplysningene oppgitt for dette systemet stemmer. Obligatoriske felter er de som automatisk er ekspandert. Det er foreslått at denne verdien settes tilbake til 'nei' etter en viss tid, men per nå er ikke dette implementert.",
			)
	systemnavn = models.CharField(
			verbose_name="Systemnavn",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"Se <a target='_blank' href='/definisjon/System/'>definisjon av system</a>. Undersøk om systemet er registrert før du eventuelt registrerer et nytt. Tidligere navn angis under Alias. Virksomhetsforkortelse til forvalter blir lagt til automatisk i visninger. Merk at programvare som kjører på en klient skal registrers som <a target='_blank' href='/admin/systemoversikt/programvare/add/'>programvare</a>.",
			)
	alias = models.TextField(
			verbose_name="Alias",
			blank=True,
			null=True,
			help_text=u"Alternative navn på systemet for å avhjelpe søk. Kun enkeltord. Du kan skrive inn flere alias, gjerne separert med komma eller på hver sin linje. Disse alias brukes også for å søke opp tilgangsgrupper tilhørende systemet.",
			)
	systembeskrivelse = models.TextField(
			verbose_name="Systembeskrivelse",
			blank=True,
			null=True,
			help_text=u"Tekstlig beskrivelse av hva systemet gjør/brukes til",
			)
	systemeier = models.ForeignKey(
			to=Virksomhet,
			related_name='systemer_eier',
			on_delete=models.SET_NULL,
			verbose_name="Organisatorisk systemeier",
			blank=True,
			null=True,
			help_text=u"For fellessystemer er dette normalt FIN. For sektorsystemer tilhører de nærmeste byrådsavdeling. For virksomhetssystemer typisk en konkret virksomhet.",
			)
	systemeier_kontaktpersoner_referanse = models.ManyToManyField(
			to=Ansvarlig,
			related_name='system_systemeier_kontaktpersoner',
			verbose_name="Systemeier (personer)",
			blank=True,
			help_text=u"Person(er) med operativt systemeierskap. Hvis du ikke finner personen du leter etter, kan du legge til med +-tegnet.",
			)
	systemforvalter = models.ForeignKey(
			to=Virksomhet,
			related_name='systemer_systemforvalter',
			on_delete=models.PROTECT,
			verbose_name="Organisatorisk systemforvalter",
			blank=False,
			null=False,
			help_text=u"Den virksomhet som har ansvar for forvaltning av systemet. Normalt en etat underlagt byrådsavdeling som har systemeierskapet",
			)
	systemforvalter_kontaktpersoner_referanse = models.ManyToManyField(
			to=Ansvarlig,
			related_name='system_systemforvalter_kontaktpersoner',
			verbose_name="Systemforvalter (personer)",
			blank=True,
			help_text=u"Person(er) med operativt forvalteransvar. Hvis du ikke finner personen du leter etter, kan du legge til med +-tegnet.",
			)
	systemforvalter_avdeling_referanse = models.ForeignKey(
			to='HRorg',
			related_name='system_systemforvalter_avdeling_referanse',
			verbose_name="Systemforvalter (avdeling)",
			blank=True,
			null=True,
			on_delete=models.SET_NULL,
			help_text=u"Seksjon forvaltning er plassert til.",
			)
	forvaltning_epost = models.EmailField(
			verbose_name="E-post til forvaltergruppen",
			blank=True,
			null=True,
			help_text=u"Fylles ut dersom forvaltergruppen har en dedikert fellespostboks.",

			)
	superbrukere = models.TextField(
			verbose_name="Superbrukere",
			blank=True,
			null=True,
			help_text=u"Personer som kjenner systemet godt. I mange tilfeller har disse administratortilganger. Dette er personer som egner seg godt når systemet må testes grunnet endringer.",
			)
	nokkelpersonell = models.TextField(
			verbose_name="Nøkkelpersonell",
			blank=True,
			null=True,
			help_text=u"Viktige personer fra leverandører og tilsvarende",
			)
	driftsmodell_foreignkey = models.ForeignKey(
			to=Driftsmodell,
			related_name='systemer',
			on_delete=models.PROTECT,
			verbose_name="Driftsplattform",
			blank=True,
			null=True,
			help_text=u"Driftsplattform systemet kjører på. Brukes blant annet for å tegne opp avhengighetsfiguren. Merk at kommunen kan ha flere instanser av samme system driftet ulike steder. Det er derfor svært viktig at denne blir satt riktig.",
			)
	leveransemodell_fip = models.IntegerField(
			choices=LEVERANSEMODELL_VALG,
			verbose_name="Leveransemodell (for felles IKT-plattform)",
			blank=True,
			null=True,
			help_text=u'Brukes ifm migreringsprosjektet. Dette datafeltet bør splittes og brukes ned mot programvare.',
			)
	tjenestenivaa = models.CharField(
			verbose_name="Tjenestenivå med UKE (gamle tjenesteavtaler)",
			choices=TJENESTENIVAA_VALG,
			max_length=50,
			blank=True,
			null=True,
			help_text=u"Gammelt nivå for oppetidsgaranti (gull, sølv og brosje)",
			)
	service_offerings = models.ManyToManyField(
			to=CMDBRef,
			related_name='system',
			verbose_name="service offerings (CMDB)",
			blank=True,
			help_text=u"Her velger du alle service offerings knyttet til dette systemet. Ta kontakt med UKE om du trenger hjelp med denne koblingen.",
			)
	sikkerhetsnivaa = models.IntegerField(
			choices=SIKKERHETSNIVAA_VALG,
			verbose_name="Konfidensialitetsnivå",
			blank=True,
			null=True,
			help_text=u'Sikkerhetsnivå for felles IKT-plattform i hht <a target="_blank" href="https://confluence.oslo.kommune.no/x/y8seAw">Informasjonstyper og behandlingskrav</a>',
			)
	programvarer = models.ManyToManyField(
			to=Programvare,
			related_name='systemer',
			verbose_name="Tilknyttet programvare",
			blank=True,
			help_text=u"Programvare benyttet av- eller knyttet til systemet. Her fører du opp navn på programvaren systemet er bygget opp av.",
			)
	avhengigheter = models.TextField(
			verbose_name="Beskrivelse av avhengigheter (fritekst)",
			blank=True,
			null=True,
			help_text=u"Her kan du gi utdypende beskrivelse knyttet til systemtekniske avhengigeheter.",
			)
	avhengigheter_referanser = models.ManyToManyField(
			to="System",
			related_name='system_avhengigheter_referanser',
			verbose_name="Systemtekniske avhengigheter til andre systemer",
			blank=True,
			help_text=u"Her lister du opp andre systemer dette systemet er avhengig av. brukes blant annet for opptegning av avhengighetsfiguren. Kan F.eks. være påloggingsportaler (AD, FEIDE, ID-porten), databasehotell (Oracle, MSSQL..), RPA-prosesser, integrasjoner osv.",
			)
	datautveksling_mottar_fra = models.ManyToManyField(
			to="System",
			related_name='system_datautveksling_mottar_fra',
			verbose_name="Mottar personopplysninger fra følgende systemer",
			blank=True,
			help_text=u"Her lister du opp systemer dette systemet mottar personopplysinger fra. Dersom overføringen skjer via en integrasjon, velges integrasjonen her.",
			)
	datautveksling_avleverer_til = models.ManyToManyField(
			to="System",
			related_name='system_datautveksling_avleverer_til',
			verbose_name="Avleverer personopplysninger til følgende systemer",
			blank=True,
			help_text=u"Her lister du opp systemer dette systemet avleverer personopplysinger til. Dersom overføringen skjer via en integrasjon, velges integrasjonen her.",
			)
	systemeierskapsmodell = models.CharField(
			choices=SYSTEMEIERSKAPSMODELL_VALG,
			verbose_name="Systemklassifisering",
			max_length=50,
			blank=True,
			null=True,
			help_text=u"I henhold til Oslo kommunes IKT-reglement.",
			)
	programvarekategori = models.IntegerField(
			choices=PROGRAMVAREKATEGORI_VALG,
			verbose_name="Programvaretype (flyttet til programvare)",
			blank=True,
			null=True,
			help_text=u"Anbefaler at du heller registrerer programvare og knytter programvaren til systemet.",
			)
	systemtyper = models.ManyToManyField(
			to=Systemtype,
			related_name='system_systemtyper',
			verbose_name="Grensesnitt",
			blank=True,
			help_text=u"Her beskriver hva slags type funksjon systemet har. Systmer merket med integrasjonskomponent eller infrastrukturkomponent blir skjult i en del visninger",
			)
	systemkategorier = models.ManyToManyField(
			to=SystemKategori,
			related_name='system_systemkategorier',
			verbose_name="Systemkategorier",
			blank=True,
			help_text=u"Dette er et sett med kategorier som forvaltes av UKE ved seksjon for information management (IM). Velg det som passer best.",
			)
	systemurl = models.ManyToManyField(
			to=SystemUrl,
			related_name='system_systemurl',
			verbose_name="URL",
			blank=True,
			default=None,
			help_text=u"Fylles ut dersom systemet har en web-frontend. Adressen systemet nås på via nettleser. Hvis du ikke finner adressen i listen må du opprette ny med +-tegnet.",
			)
	systemleverandor_vedlikeholdsavtale = models.BooleanField(
			verbose_name="Aktiv vedlikeholdsavtale med systemleverandør?",
			default=None,
			null=True,
			help_text=u"",
			)
	systemleverandor = models.ManyToManyField(
			to=Leverandor,
			related_name='system_systemleverandor',
			verbose_name="Systemleverandør (tjenesteleverandør)",
			blank=True,
			help_text=u"Leverandør som har utviklet systemet.",
			)
	basisdriftleverandor = models.ManyToManyField(
			to=Leverandor,
			related_name='system_driftsleverandor',
			verbose_name="Leverandør av basisdrift",
			blank=True,
			help_text=u"Leverandør som drifter maskinparken systmet kjører på.",
			)
	applikasjonsdriftleverandor = models.ManyToManyField(
			to=Leverandor,
			related_name='system_applikasjonsdriftleverandor',
			verbose_name="Leverandør av applikasjonsdrift",
			blank=True,
			help_text=u"Leverandør som sørger for at systemet fungerer som det skal.",
			)
	applikasjonsdrift_behov_databehandleravtale = models.BooleanField(
			verbose_name="Behov for (egen) DBA mot applikasjonsdriftsleverandør?",
			default=True,
			help_text=u"Krysses av dersom det er aktuelt å ha databehandleravtale med applikasjonsdriftsleverandør. Er f.eks. ikke nødvendig når det er samme leverandør som for basisdrift og det er etablert DBA mot denne.",
			)
	datamodell_url = models.URLField(
			verbose_name="Datamodell",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til beskrivelse av datamodell",
			)
	datasett_url = models.URLField(
			verbose_name="Datasett",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til beskrivelse av datasett",
			)
	api_url = models.URLField(
			verbose_name="API",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til beskrivelse av API",
			)
	kildekode_url = models.URLField(
			verbose_name="Kildekode",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til kildekode",
			)
	kontaktgruppe_url = models.URLField(
			verbose_name="Brukerstøttegruppe",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til gruppe på workplace eller f.eks. en intranettside.",
			)
	high_level_design_url = models.URLField(
			verbose_name="Systemdokumentasjon",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"High level design",
			)
	low_level_design_url = models.URLField(
			verbose_name="Driftsdokumentasjon",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Low level design",
			)
	brukerdokumentasjon_url = models.URLField(
			verbose_name="Brukerdokumentasjon",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Link til brukerdokumentasjon",
			)
	kommentar = models.TextField(
			verbose_name="Kommentar (fritekst) (fases ut)",
			blank=True,
			null=True,
			help_text=u"Ikke bruk dette feltet",
			)
	selvbetjening = models.IntegerField(
			choices=SELVBETJENING_VALG,
			verbose_name="Selvbetjening (fases ut)",
			blank=True,
			null=True,
			help_text=u"Dersom ja betyr dette at systemet har et brukergrensesnitt der brukere selv kan registrere nødvendig informasjon i systemet.",
			)
	livslop_status = models.IntegerField(
			choices=LIVSLOEP_VALG,
			verbose_name="Livsløpstatus",
			blank=True,
			null=True,
			help_text=u"Setter du 1 under anskaffelse vil systemet anses som ikke i bruk (enda). Setter du status 5 eller 6 vil systemet havne på 'End of life (EOL)'-listen.",
			)
	strategisk_egnethet = models.IntegerField(
			choices=VURDERINGER_STRATEGISK_VALG,
			verbose_name="Strategisk egnethet (fases ut)",
			blank=True,
			null=True,
			help_text=u"Hvor viktig systemet er opp mot virksomhetens oppdrag",
			)
	funksjonell_egnethet = models.IntegerField(
			choices=VURDERINGER_FUNKSJONELL_VALG,
			verbose_name="Funksjonell egnethet",
			blank=True,
			null=True,
			help_text=u"Hvor godt systemet løser behovet",
			)
	teknisk_egnethet = models.IntegerField(
			choices=VURDERINGER_TEKNISK_VALG,
			verbose_name="Teknisk egnethet",
			blank=True,
			null=True,
			help_text=u"Moderne teknologi eller masse teknisk gjeld?",
			)


	#### DENNE BRUKES IKKE??
	konfidensialitetsvurdering = models.IntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Oppsummert konfidensialitetsvurdering (utfases)",
			blank=True,
			null=True,
			help_text=u"Hvor sensitive er opplysningene?",
			)



	integritetsvurdering = models.IntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Integritetsvurdering",
			blank=True,
			null=True,
			help_text=u"Hvor kritisk er det at opplysningene stemmer?",
			)
	tilgjengelighetsvurdering = models.IntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Tilgjengelighetsvurdering",
			blank=True,
			null=True,
			default=6,
			help_text=u"Hvor kritisk er det at systemet virker?",
			)
	tilgjengelighet_kritiske_perioder = models.TextField(
			verbose_name="Kritiske perioder og konsekvenser ved nedetid",
			blank=True,
			null=True,
			help_text=u"Her begrunner du hvorfor systemet er kritisk, samt dokumenterer perioder av året hvor det er særskilt behov for at systemet er tilgjengelig. F.eks. knyttet til frister som eiendomsskatt, barnehageopptak eller lønnskjøring.",
			)
	tilgjengelighet_periodisk_kritisk = models.BooleanField(
			verbose_name="Kritisk kun i perioder?",
			default=False,
			help_text=u"Kryss av dersom systemet kun er kritisk i visse perioder i løpet av måneden eller året.",
			)
	tilgjengelighet_timer_til_kritisk = models.IntegerField(
			verbose_name="Timer til kritisk",
			blank=True,
			null=True,
			help_text=u"Hvor mange timer tar det fra systemet blir utilgjengelig til det er kritisk?",
			)
	risikovurdering_behovsvurdering = models.IntegerField(
			choices=VALG_RISIKOVURDERING_BEHOVSVURDERING,
			verbose_name="Behov for risikovurdering?",
			blank=False, null=False, default=2, # 2: Prioriteres
			help_text=u"Brukes i grafisk fremvisning av RoS-status, samt ved utsending av varsel om utdatert risikovurdering.",
			)
	url_risikovurdering = models.URLField(
			verbose_name="Risikovurdering (URL)",
			blank=True,
			null=True,
			help_text=u"URL-referanse dersom det finnes. Om ikke kan fritekstfeltet benyttes.",
			)
	risikovurdering_tekst = models.TextField(
			verbose_name="Risikovurdering fritekst",
			blank=True,
			null=True,
			help_text=u"Ytterligere detaljer knyttet til gjennomføringen av risikovurdering for systemet.",
			)
	dato_sist_ros = models.DateTimeField(
			verbose_name="Dato sist gjennomførte risikovurdering",
			blank=True,
			null=True,
			help_text=u"YYYY-MM-DD eksempel 2019-05-05 (tidspunkt er påkrevet - sett 'Nå')",
			)
	systemtekniske_sikkerhetstiltak = models.TextField(
			verbose_name="Systemtekniske sikkerhetstiltak (oppsummering)",
			blank=True,
			null=True,
			help_text=u"fases ut til fordel for mer detaljerte spørsmål under.",
			)
	autentiseringsalternativer = models.ManyToManyField(
			to=Autentiseringsmetode,
			related_name='system_autentiseringsalternativer',
			verbose_name="Identifiseringsnivå",
			blank=True,
			help_text=u"Sikkerhetsnivå på innloggingen?",
			)
	autentiseringsteknologi = models.ManyToManyField(
			to=Autentiseringsteknologi,
			related_name='system_autentiseringsalternativer',
			verbose_name="Påloggingstjeneste",
			blank=True,
			help_text=u"Hvordan logger bruker på? Husk også å legge til systemavhengighet dersom AD/LDAP/SAML/OIDC. (Henger sammen med hvordan brukere opprettes)",
			)
	loggingalternativer = models.ManyToManyField(
			to=Loggkategori,
			related_name='system_loggingalternativer',
			verbose_name="Etablerte logger i systemet",
			blank=True,
			help_text=u"Nivå av logging etablert i systemet",
			)
	autorisasjon_differensiering_beskrivelse = models.TextField(
			verbose_name="Differensiering av tilganger med bakgrunn i roller/identitet",
			blank=True,
			null=True,
			help_text=u"Beskriv mulighetene for å differensiere tilganger med bakgrunn i roller/identitet.",
			)
	autorisasjon_differensiering_saksalder = models.TextField(
			verbose_name="Differensiering av tilganger med bakgrunn i sakenes alder",
			blank=True,
			null=True,
			help_text=u"Beskriv mulighetene for å differensiere tilganger med bakgrunn i sakenes alder ",
			)
	dataminimalisering = models.TextField(
			verbose_name="Dataminimalisering",
			blank=True,
			null=True,
			help_text=u"Beskriv systemets funksjonalitet for å sikre dataminimalisering",
			)
	sletting_av_personopplysninger = models.TextField(
			verbose_name="Sletting av personopplysninger",
			blank=True,
			null=True,
			help_text=u"(Redundant med felt på behandling) Beskriv systemets funksjonalitet for sletting av personopplysninger",
			)
	funksjonalitet_kryptering = models.TextField(
			verbose_name="Funksjonalitet for kryptering",
			blank=True,
			null=True,
			help_text=u"Beskriv funksjonalitet for kryptering (hva krypteres og hvordan, både for transport/overføring og ved lagring)",
			)
	anonymisering_pseudonymisering = models.TextField(
			verbose_name="Anonymisering og pseudonymisering",
			blank=True,
			null=True,
			help_text=u"(Redundant med felt på behandling) Beskriv funksjonalitet for anonymisering / pseudonymisering ved bruk av personopplysninger til andre formål ",
			)
	sikkerhetsmessig_overvaaking = models.TextField(
			verbose_name="Sikkerhetsovervåking",
			blank=True,
			null=True,
			help_text=u"Beskriv hva slags aktiv overvåking av logger og hendelser som gjelder for systemet. Hvem utfører dette og hvor ofte?",
			)
	kontaktperson_innsyn = models.ManyToManyField(
			to=Ansvarlig,
			related_name='system_kontaktperson_innsyn',
			verbose_name="Kontaktperson innsyn",
			blank=True,
			help_text=u"Person som kan kontaktes for å undersøke om det er personopplysninger i systemet knyttet til en innsynsbegjæring. Dersom du ikke finner personen du leter etter kan du legge til ny med +-tegnet.",
			)
	innsyn_innbygger = models.BooleanField(
			verbose_name="Innsyn relevant for innbyggere?",
			default=True,
			help_text=u"Er det aktuelt å søke igjennom dette systemet etter personopplysninger ved innsynsbegjæring fra en innbygger.",
			)
	innsyn_ansatt = models.BooleanField(
			verbose_name="Innsyn relevant for ansatte?",
			default=True,
			help_text=u"Er det aktuelt å søke igjennom dette systemet etter personopplysninger ved innsynsbegjæring fra en ansatt",
			)
	kjente_mangler = models.TextField(
			verbose_name="Kjente mangler i systemet",
			blank=True,
			null=True,
			help_text=u"Felt forvalter kan benytte for å notere ned kjente mangler.",
			)
	informasjonsklassifisering = models.ManyToManyField(
			to=InformasjonsKlasse,
			related_name='system_informasjonsklassifisering',
			verbose_name="Informasjonsklassifisering",
			blank=True,
			help_text=u"Velg de kategorier som er aktuelle.",
			)
	isolert_drift = models.BooleanField(
			verbose_name="På Tilpasset drift (felles IKT-plattform)",
			default=False,
			help_text=u"Krysses av dersom systemet ikke kan oppgraderes og derfor er spesielt adskilt fra andre systemer på plattformen.",
			)
	database_supported = models.ManyToManyField(
			to='Database',
			related_name='system_database_supported',
			verbose_name="Støttede databaser",
			blank=True,
			help_text=u"Legg til alle typer databaser som støttes av systemet.",
			)
	database_in_use = models.ManyToManyField(
			to='Database',
			related_name='system_database_in_use',
			verbose_name="Databasetype i bruk",
			blank=True,
			help_text=u"Legg til alle typer databaser er i bruk for dette systemet.",
			)
	godkjente_bestillere = models.ManyToManyField(
			to=Ansvarlig,
			related_name='system_godkjente_bestillere',
			verbose_name="Godkjente Kompass-bestillere",
			blank=True,
			help_text=u"Forvaltere er autorisert til å bestille endringer på systemet i Kompass. I tillegg er disse personene autorisert for å bestille endringer på systemet. Hvis du ikke finner personen du leter etter, kan du legge til med +-tegnet.",
			)
	er_arkiv = models.BooleanField(
			verbose_name="Er systemet et arkiv?",
			default=False,
			help_text=u"Krysses av dersom systemet er et arkivsystem i henhold til arkivlovverk.",
			)
	antall_brukere = models.IntegerField(
			verbose_name="Antall brukere",
			blank=True,
			null=True,
			help_text=u"Ca hvor mange bruker systemet totalt?",
			)
	tilgangsgrupper_ad = models.ManyToManyField(
			to=ADgroup,
			related_name='system_referanse',
			verbose_name="Tilhørende tilgangsgrupper (AD)",
			blank=True,
			help_text=u'Velg en eller flere sikkerhetsgrupper i AD tilhørende systemet. Brukes for å linke opp grupper og personer med tilgang.',
			)
	legacy_klient_krever_smb = models.BooleanField(
			verbose_name="Direkte kommunikasjon med filområder?",
			blank=True,
			null=True,
			help_text=u"Settes dersom systemets klient må kommunisere direkte med on-prem filområder. OneDrive er ikke on-prem og er derfor ikke en grunnlag for å sette 'ja' på denne. Settes til 'ja' dersom minst ét av grensesnittene krever on-prem filområdetilgang.",
			)
	legacy_klient_krever_direkte_db = models.BooleanField(
			verbose_name="Direkte kommunikasjon med databaseserver fra klient?",
			blank=True,
			null=True,
			help_text=u"Settes dersom systemets klient må kommunisere direkte med databaser. Settes til 'ja' dersom minst ét av grensesnittene krever dette.",
			)
	legacy_klient_krever_onprem_lisensserver = models.BooleanField(
			verbose_name="Legacy: Krever on-prem lisensserver?",
			blank=True,
			null=True,
			help_text=u"Settes dersom systemet krever at klient har direktekontakt med on-prem lisensserver.",
			)
	legacy_klient_autentisering = models.BooleanField(
			verbose_name="Legacy klientautentisering?",
			blank=True,
			null=True,
			help_text=u"Settes dersom systemet ikke støtter moderne autentisering (SAML/OIDC)",
			)
	enterprise_applicatons = models.ManyToManyField(
			to="AzureApplication",
			related_name='systemreferanse',
			verbose_name="Tilhørende Microsoft enterprise application",
			help_text=u"Brukes for å koble systemet til Microsoft enterprise applications (pålogging med Azure AD og andre MS Graph-tilganger).",
			blank=True,
			)
	LOSref = models.ManyToManyField(
			to="LOS",
			related_name='systemer',
			verbose_name="Begrepstagging (LOS)",
			blank=True,
			help_text=u"Her kan du tagge systemet med informasjonsområder (kommunale områder) standardiserte LOS-begreper forvaltet av DigDir. Du finner både tema og ord i listen. Anbefaler at du primært velger tema fra listen og sekundært andre ord som supplerer. Ord kan være knyttet til flere tema, så det er ikke mulig å entydig automatisk velge riktig tema basert på ord. Oversikten over behandlinger hensyntar bare på koblinger mot tema.",
			)
	klargjort_ny_sikkerhetsmodell = models.IntegerField(
			choices=VALG_KLARGJORT_SIKKERHETSMODELL,
			verbose_name="Status klargjort for ny sikkerhetsmodell",
			blank=True, null=True,
			help_text=u"Besnyttes av UKE for å kartlegge hvilke virksomheter som er klare for ny klientmodell uten permanent VPN.",
			)
	kritisk_kapabilitet = models.ManyToManyField(
			to=KritiskKapabilitet,
			related_name="systemer",
			verbose_name="Kritisk kapabilitet",
			blank=True,
			help_text=u"Understøtter systemet en kritisk funksjon? Kategorier basert på rammeverket fra DSB."
			)
	inv_konklusjon = models.CharField(
			verbose_name="Konklusjon modernisering",
			max_length=250,
			blank=True,
			null=True,
			)
	inv_konklusjon_beskrivelse = models.TextField(
			verbose_name="Detaljert konklusjon modernisering",
			blank=True,
			null=True,
			)
	dato_etablert = models.DateField(
			verbose_name="Dato systemet ble tatt i bruk",
			null=True,
			blank=True,
			)
	dato_end_of_life = models.DateField(
			verbose_name="Dato systemet skal fases ut eller ble faset ut",
			null=True,
			blank=True,
			)
	arkivkommentar = models.TextField(
			verbose_name="Arkivars kommentarer til systemet",
			blank=True,
			null=True,
			)
	cache_systemprioritet = models.IntegerField(
			default=240,
			) # Denne blir kalkulert ved hver visning
	citrix_publications = models.ManyToManyField(
			to="CitrixPublication",
			related_name="systemer",
			verbose_name="Tilkoblede citrixpubliseringer",
			blank=True,
		)
	history = HistoricalRecords()

	unique_together = ('systemnavn', 'systemforvalter')

	def __str__(self):
		try:
			return f'{self.systemnavn} ({self.systemforvalter.virksomhetsforkortelse})'
		except:
			return f'{self.systemnavn}'

	def los_ord(self):
		words = list()
		for word in self.LOSref.all():
			if not word.er_tema():
				words.append(word)
		return words

	def alias_oppdelt(self):
		if self.alias == None:
			return []
		return self.alias.split()

	def unike_server_os(self):
		server_os = []
		try:
			for bss in self.service_offerings.all():
				for server in bss.servers.all():
						server_os.append("%s %s" % (server.comp_os, server.comp_os_version))
		except:
			pass
		return list(set(server_os))

	def save(self, *args, **kwargs):
		self.ibruk = self.er_ibruk()
		super(System, self).save(*args, **kwargs)

	def felles_sektorsystem(self):
		if self.systemeierskapsmodell in ("FELLESSYSTEM", "SEKTORSYSTEM", "TVERRSEKTORIELT"):
			return True
		else:
			return False

	def databaseplattform(self):
		databaser = []
		alle_bss = self.service_offerings.all()
		for bss in alle_bss:
			alle_db = CMDBdatabase.objects.filter(sub_name=bss)
			for db in alle_db:
				databaser.append("%s" % (db.db_version))
		if len(databaser) > 0:
			return ', '.join([db for db in set(databaser)])
		#fallback to manual field
		return ', '.join([db.navn for db in self.database_in_use.all()])

	def serverplattform(self):
		serveros = []
		alle_bss = self.service_offerings.all()
		for bss in alle_bss:
			servere = CMDBdevice.objects.filter(service_offerings=bss)
			for s in servere:
				serveros.append("%s %s" % (s.comp_os, s.comp_os_version))
		return ', '.join([os for os in set(serveros)])

	def er_infrastruktur(self):
		for stype in self.systemtyper.all():
			if stype.er_infrastruktur:
				return True
		else:
			return False

	def er_integrasjon(self):
		for stype in self.systemtyper.all():
			if stype.er_integrasjon:
				return True
		else:
			return False

	def er_selvutviklet(self):
		try:
			if self.driftsmodell_foreignkey.utviklingsplattform:
				return True
		except:
			pass

		return False

	def er_samarbeidspartner(self):
		try:
			if self.driftsmodell_foreignkey.samarbeidspartner:
				return True
		except:
			pass

		return False

	def er_privat_sky(self):
		try:
			if self.driftsmodell_foreignkey.type_plattform == 1:
				return True
		except:
			return False

	def mangler_driftsmodell(self):
		if self.driftsmodell_foreignkey == None:
			return True

	def driftes_av_uke(self):
		try:
			if self.driftsmodell_foreignkey.ansvarlig_virksomhet.pk == 163:
				return True
		except:
			return False

	def er_saas(self):
		try:
			if self.driftsmodell_foreignkey.pk == 2:
				return True
		except:
			return False

	def forventet_url(self):
		for systemtype in self.systemtyper.all():
			if systemtype.har_url:
				return True
		return False

	def antall_avhengigheter(self): # SER IKKE UT TIL Å VÆRE I BRUK
		return len(self.system_integration_source.all()) + len(self.system_integration_destination.all())

	def antall_bruk(self):
		bruk = SystemBruk.objects.filter(system=self.pk)
		return bruk.count()

	def er_ibruk(self):
		if self.livslop_status in [1,6,7]:
			return False
		return True

	def color(self):

		if self.mangler_driftsmodell():
			return SYSTEM_COLORS["ukjent"]

		if self.er_samarbeidspartner():
			return SYSTEM_COLORS["samarbeidspartner"]

		if self.er_saas():
			return SYSTEM_COLORS["saas"]

		if self.er_privat_sky():
			if self.driftes_av_uke():
				return SYSTEM_COLORS["drift_uke_privat"]
			return SYSTEM_COLORS["drift_virksomhet_privat"]

		else: # er ikke privat sky
			if self.driftes_av_uke():
				return SYSTEM_COLORS["drift_uke_sky"]
			return SYSTEM_COLORS["drift_virksomhet_sky"]


	# brukes bare av dashboard, flyttes dit? ("def statusTjenestenivaa(systemer)")
	def fip_kritikalitet(self):
		if hasattr(self, 'bs_system_referanse'):
			kritikalitet = []
			for ref in self.service_offerings.all():
				if ref.environment == 1: # 1 er produksjon
					kritikalitet.append(ref.kritikalitet)

			if len(kritikalitet) == 1:
				return kritikalitet[0] # alt OK, bare én prod valgt
			else:
				return None
		else:
			return None

	def fip_kritikalitet_text(self):
		if hasattr(self, 'bs_system_referanse'):
			prod_referanser = []
			for ref in self.system.all():
				if ref.environment == 1: # 1 er produksjon
					prod_referanser.append(ref)
			if len(prod_referanser) == 1:
				return prod_referanser[0].get_kritikalitet_display()
			else:
				return("Uklart, flere PROD-koblinger")
		else:
			return None

	def sist_endret_av(self):
		from django.contrib.contenttypes.models import ContentType
		from django.contrib.admin.models import LogEntry
		system_content_type = ContentType.objects.get_for_model(self)
		try:
			return LogEntry.objects.filter(content_type=system_content_type).filter(object_id=self.pk).order_by('-action_time')[0]
		except:
			return None

	def antall_behandlinger(self):
		behandlinger = BehandlingerPersonopplysninger.objects.filter(systemer=self.pk)
		return behandlinger.count()

	def databehandleravtaler_system(self):
		from systemoversikt.models import Avtale
		try:
			return Avtale.objects.filter(for_system=self.pk).filter(avtaletype=1) #1=databehandleravtale
		except:
			return None

	def databehandleravtaler_drift(self):
		try:
			avtaler = self.driftsmodell_foreignkey.avtaler.all()
		except:
			return None
		databehandleravtaler = []
		for avtale in avtaler:
			if avtale.avtaletype == 1: #1=databehandleravtale
				databehandleravtaler.append(avtale)
		return databehandleravtaler

	def systemprioritet(self):
		import re
		tilgjengelighet = self.tilgjengelighetsvurdering
		if tilgjengelighet == None:
			tilgjengelighet = 5


		if self.service_offerings != None:

			tjenestenivaa = 4
			for bss in self.service_offerings.all():
				if bss.operational_status == 1:# and bss.er_produksjon:
					try:
						bss_tjenestenivaa = int(re.findall(r'T(\d+)', bss.u_service_availability)[0])
						if bss_tjenestenivaa < tjenestenivaa:
							tjenestenivaa = bss_tjenestenivaa
					except:
						pass

			kritikalitet = 5
			for bss in self.service_offerings.all():
				if bss.operational_status == 1:# and bss.er_produksjon:
					try:
						bss_kritikalitet = int(re.findall(r'\d+', bss.u_service_operation_factor)[0])
						if bss_kritikalitet < kritikalitet:
							kritikalitet = bss_kritikalitet
					except:
						pass

		else: # ingen CMDB-kobling finnes
			tjenestenivaa = 2
			kritikalitet = 2 # balanse mellom å la ikke-kritiske systemer havne for høyt på prioritet og at kritiske systemer havner for langt ned på listen dersom ikke koblet til tjeneste

		sammfunnskritisk = 2
		if len(self.kritisk_kapabilitet.all()) > 0:
			sammfunnskritisk = 1

		score = tilgjengelighet * tjenestenivaa * kritikalitet * sammfunnskritisk

		if self.cache_systemprioritet != score:
			#print(f"{self} cache {self.cache_systemprioritet} var ikke lik score {score}, oppdaterer..")
			self.cache_systemprioritet = score
			self.save()

		tekst = f"{tilgjengelighet}*{tjenestenivaa}*{kritikalitet}*{sammfunnskritisk}={score}"
		return tekst

	def citrix_publiseringer_pk(self):
		navn = self.systemnavn.split()
		#print(navn)
		alias = self.alias_oppdelt()
		#print(alias)
		words = navn + alias
		#print(words)
		hits = []
		for w in words:
			if len(w) > 2:
				hits.extend((list(CitrixPublication.objects.filter(publikasjon_json__icontains=w))))
		return hits

	def citrix_publiseringer(self):
		hits = self.citrix_publiseringer_pk()

		if hits:
			for t in hits:
				t.publikasjon_json = json.loads(t.publikasjon_json)
			return hits
		else:
			return None

	def vis_autentisering(self):
		relevante_integrasjoner = SystemIntegration.objects.filter(source_system=self).filter(integration_type="AUTHENTICATION")
		if len(relevante_integrasjoner) > 0:
			return [i.destination_system for i in relevante_integrasjoner]
		else:
			return self.autentiseringsteknologi.all()

	def eiere(self):
		brukernavn = set()
		forvaltere = [ansvarlig.brukernavn.username for ansvarlig in self.systemforvalter_kontaktpersoner_referanse.all()]
		eiere = [ansvarlig.brukernavn.username for ansvarlig in self.systemeier_kontaktpersoner_referanse.all()]
		brukernavn.update(forvaltere)
		brukernavn.update(eiere)
		#print(f"{forvaltere} og {eiere} og unike brukernavn {brukernavn}")
		return brukernavn

	def vulnerabilities(self):
		connected_vulns = set()
		for service_offering in self.service_offerings.all():
			#print(service_offering)
			for server in service_offering.servers.all():
				#print(server)
				for vuln in server.qualys_vulnerabilities.all():
					if vuln.severity in [4,5]:
						vuln.tmp_offering = service_offering # brukes kun i template
						connected_vulns.add(vuln)
		#print(connected_vulns)
		return list(connected_vulns)

	class Meta:
		verbose_name_plural = "Systemoversikt: Systemer"
		default_permissions = ('add', 'change', 'delete', 'view')



TYPE_SIKKERHETSTEST = (
	(1, 'Intern infrastrukturtesting'),
	(2, 'Ekstern infrastrukturtesting'),
	(3, 'Web-applikasjonstesting'),
	(4, 'Kildekodegjennomgang'),
	(5, 'Mobile applikasjoner'),
	(6, 'Konfigurasjonsgjennomgang'),
	(7, 'Sosial manipulering'),
)

class Sikkerhetstester(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	systemer = models.ManyToManyField(
			to=System,
			related_name='sikkerhetstest_systemer',
			verbose_name="Systemer testet",
			blank=False,
			)
	type_test = models.IntegerField(
			choices=TYPE_SIKKERHETSTEST,
			verbose_name="Type sikkerhetstest",
			blank=False, null=True,
			help_text=u"Velg mest aktuelle som definert på <a href='https://confluence.oslo.kommune.no/x/eww4B'>Confluence</a>",
			)
	rapport = models.URLField(
			verbose_name="Link til rapport",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"F.eks. på confluence eller til et arkivsystem",
			)
	dato_rapport = models.DateTimeField(
			verbose_name="Dato for sluttføring av rapport",
			blank=False,
			null=True,
			help_text=u"(tidspunkt er påkrevet - sett 'Nå')"
			)
	testet_av = models.ForeignKey(
			to=Leverandor,
			related_name='sikkerhetstest_testet_av',
			on_delete=models.PROTECT,
			verbose_name="Testet av (leverandør)",
			null=True,
			blank=True,
			help_text=u'Leverandør som har utført testen',
			)
	notater = models.TextField(
			verbose_name="Omfang av test og andre notater",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s: %s' % (self.testet_av, self.dato_rapport)

	class Meta:
		verbose_name_plural = "Systemoversikt: Sikkerhetstester"
		verbose_name = "sikkerhetstest"
		default_permissions = ('add', 'change', 'delete', 'view')


class DPIA(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	informasjon_kvalitetssikret = models.BooleanField(
			verbose_name="Er informasjonen kvalitetssikret av behandlingsansvarlig?",
			default=False,
			help_text=u"Krysses av når denne personvernvurderingen er klar i første versjon.",
			)
	for_system = models.OneToOneField(
			to=System,
			related_name='DPIA_for_system',
			on_delete=models.PROTECT,
			verbose_name="DPIA for system (personvernvurderinger)",
			blank=False,
			null=True,
			)
	sist_gjennomforing_dpia = models.DateTimeField(
			verbose_name="Dato siste vurdering",
			blank=True,
			null=True,
			help_text=u"Når ble personvernkonsekvenser for systemet sist vurdert (tidspunkt er påkrevet - sett 'Nå')",
			)
	url_dpia = models.URLField(
			verbose_name="Arkivlink til godkjenningen av DPIA for dette systemet",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Oppbevares i et arkivsystem eller annet egnet sted",
			)
	kommentar = models.TextField(
			verbose_name="Arbeidsnotater til DPIA-arbeidet",
			blank=True,
			null=True,
			help_text=u"",
			)
	#trinn 2
	knyttning_identifiserbare_personer = models.TextField(
			verbose_name="Kan informasjonen på noen måte knyttes til identifiserbare personer (enten direkte eller via personnummer eller andre identifikatorer)?",
			blank=True,
			null=True,
			help_text=u"",
			)
	innhentet_dpia = models.TextField(
			verbose_name="Er det innhentet DPIA for mottakende systemer? Beskriv hvilke som er gjennomgått.",
			blank=True,
			null=True,
			help_text=u"",
			)
	teknologi = models.TextField(
			verbose_name="Hva slags teknologi skal benyttes?",
			blank=True,
			null=True,
			help_text=u"",
			)
	ny_endret_teknologi = models.TextField(
			verbose_name="Innebærer behandlingen på noen måte bruk av ny/endret teknologi?",
			blank=True,
			null=True,
			help_text=u"",
			)
	kjente_problemer_teknologien = models.TextField(
			verbose_name="Er det noen offentlig kjente problemer med teknologien det bør tas hensyn til?",
			blank=True,
			null=True,
			help_text=u"",
			)
	#trinn 3
	konsultasjon_registrerte = models.TextField(
			verbose_name="Har det vært en konsultasjonsprosess med de registrerte/de registreres interesseorganisasjoner? f.eks. fagforeninger, brukergrupper, pasientorganisasjoner. Hvordan og når ble konsultasjonen med de registrerte/de registreres interesseorganisasjoner gjennomført? Hvis NEI, må dette begrunnes nærmere.",
			blank=True,
			null=True,
			help_text=u"",
			)
	konsultasjon_registrerte_oppsummering = models.TextField(
			verbose_name="Oppsummering av de råd m.m. som kom etter konsultasjoner med de registrerte / interessegrupper som representerer de registrerte.",
			blank=True,
			null=True,
			help_text=u"",
			)
	konsultasjon_internt = models.TextField(
			verbose_name="Hvem internt er konsultert/involvert i planleggingen (IKT, jurister, fagpersoner, m.m.)?",
			blank=True,
			null=True,
			help_text=u"",
			)
	konsultasjon_internt_oppsummering = models.TextField(
			verbose_name="Oppsummering av de råd m.m. som kom etter konsultasjoner av interne ressurser:",
			blank=True,
			null=True,
			help_text=u"",
			)
	konsultasjon_databehandlere = models.TextField(
			verbose_name="Er databehandlere konsultert/involvert i planleggingen?",
			blank=True,
			null=True,
			help_text=u"",
			)
	konsultasjon_databehandlere_oppsummering = models.TextField(
			verbose_name="Oppsummering av de råd m.m. som kom etter konsultasjoner av databehandler.",
			blank=True,
			null=True,
			help_text=u"",
			)
	konsultasjon_eksterne = models.TextField(
			verbose_name="Er løsningen gjennomgått av eksterne eksperter (f.eks. eksperter på informasjonssikkerhet, jurister, fagpersoner)?",
			blank=True,
			null=True,
			help_text=u"",
			)
	konsultasjon_eksterne_oppsummering = models.TextField(
			verbose_name="Oppsummering av de råd m.m. som kom etter konsultasjoner av eksterne resurser.",
			blank=True,
			null=True,
			help_text=u"",
			)
	#trinn 4
	hoveddatabehandler = models.TextField(
			verbose_name="Hvem er hoveddatabehandler?",
			blank=True,
			null=True,
			help_text=u"",
			)
	#trinn 5
	personvern_i_risikovurdering = models.TextField(
			verbose_name="Er risikoen til individet beskrivet/ivaretatt i systemets risikovurdering?",
			blank=True,
			null=True,
			help_text=u"Ja/Nei-felt?",
			)

	#trinn 6
	tiltak_innledende_ros = models.TextField(
			verbose_name="Oppsummering av resultat av innledende risikovurdering.",
			blank=True,
			null=True,
			help_text=u"",
			)
	tiltak_etter_ytterligere_tiltak = models.TextField(
			verbose_name="Oppsummering av risikovurdering etter ytterligere risikovurderende tiltak.",
			blank=True,
			null=True,
			help_text=u"",
			)
	tiltak_forhandsdroftelser = models.TextField(
			verbose_name="Oppsummering av resultatet av forhåndsdrøftelse med Datatilsynet.",
			blank=True,
			null=True,
			help_text=u"",
			)

	#trinn 7
	godkjenning_personvernombudets_raad = models.TextField(
			verbose_name="Personvernombudets råd er innhentet (oppsummering av råd).",
			blank=True,
			null=True,
			help_text=u"Bør dette punktet inn under trinn 3?",
			)
	godkjenning_tiltak_restrisiko = models.TextField(
			verbose_name="Anbefalte tiltak og restrisiko godkjent (av hvem og når).",
			blank=True,
			null=True,
			help_text=u"",
			)
	godkjenning_datatilsynet = models.URLField(
			verbose_name="Datatilsynets godkjennelse ved «Uakseptabel» restrisiko (link).",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()


	def __str__(self):
		return u'DPIA for %s' % (self.for_system)

	class Meta:
		verbose_name_plural = "Behandling: DPIA-er"
		default_permissions = ('add', 'change', 'delete', 'view')



VURDERING_AVTALESTATUS_VALG = (
	(1, "1 Dårlig"),
	(2, "2 Store mangler"),
	(3, "3 Akseptbel"),
	(4, "4 God"),
	(5, "5 Meget god"),
)

IBRUK_VALG = (
	(1, "Ja"),
	(2, "Nei"),
	(3, "Kanskje"),
	(4, "Planlagt"),
)



class ProgramvareBruk(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	brukergruppe = models.ForeignKey(
			to=Virksomhet,
			on_delete=models.PROTECT,
			blank=False, null=False,
			related_name='programvarebruk_brukergruppe',
			)
	programvare = models.ForeignKey(
			to=Programvare,
			on_delete=models.PROTECT,  # slett ProgramvareBruken når Programvaren slettes
			related_name='programvarebruk_programvare',
			blank=False, null=False,
			)
	ibruk = models.BooleanField(
			verbose_name="Er programvaren i bruk?",
			blank=False,
			null=False,
			default=True,
			help_text=u"Er i bruk ved kryss, og 'ikke i bruk' når kryss fjernes. Kan fjernes i stedet for å slette koblingen og lokale vurderinger.",
			)
	livslop_status = models.IntegerField(
			choices=LIVSLOEP_VALG,
			verbose_name="Livsløpstatus",
			blank=True,
			null=True,
			help_text=u"",
			)
	kommentar = models.TextField(
			verbose_name="Kommentarer til denne bruken",
			blank=True,
			null=True,
			help_text=u"Utdyp hva programvaren brukes til hos din virksomhet.",
			)
	programvareeierskap = models.TextField(
			verbose_name="Programvareeierskap (fritekst)",
			blank=True,
			null=True,
			help_text=u"",
			)
	antall_brukere = models.IntegerField(
			verbose_name="Antall brukere",
			blank=True,
			null=True,
			help_text=u"Hvor mange bruker programvaren hos dere? (fylles ut dersom relevant)",
			)
	avtaletype = models.CharField(
			verbose_name="Avtaletype",
			max_length=250,
			blank=True,
			null=True,
			help_text=u"",
			)
	avtalestatus = models.IntegerField(
			choices=VURDERING_AVTALESTATUS_VALG,
			verbose_name="Avtalestatus",
			blank=True,
			null=True,
			help_text=u"",
			)
	avtale_kan_avropes = models.BooleanField(
			verbose_name="Avtale kan avropes av andre virksomheter",
			blank=True,
			null=True,
			help_text=u"",
			)
	borger = models.IntegerField(
			choices=IBRUK_VALG,
			verbose_name="For borger?",
			blank=True,
			null=True,
			help_text=u"",
			)
	kostnader = models.IntegerField(
			verbose_name="Kostnader for programvaren",
			blank=True,
			null=True,
			help_text=u"",
			)
	strategisk_egnethet = models.IntegerField(
			choices=VURDERINGER_STRATEGISK_VALG,
			verbose_name="Strategisk egnethet",
			blank=True, null=True,
			help_text=u"",
			)
	funksjonell_egnethet = models.IntegerField(
			choices=VURDERINGER_FUNKSJONELL_VALG,
			verbose_name="Funksjonell egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	teknisk_egnethet = models.IntegerField(
			choices=VURDERINGER_TEKNISK_VALG,
			verbose_name="Teknisk egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	programvareleverandor = models.ManyToManyField(
			to=Leverandor,
			related_name='programvarebruk_programvareleverandor',
			verbose_name="Programvareleverandør",
			blank=True,
			)
	lokal_kontakt = models.ManyToManyField(
			to=Ansvarlig,
			related_name='programvarebruk_lokal_kontakt',
			verbose_name="Lokal kontakt",
			blank=True,
			help_text=u"Kontaktperson for virksomhetens bruk av programvaren",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s - %s' % (self.programvare, self.brukergruppe)

	class Meta:
		verbose_name_plural = "Organisasjon: Programvarebruk"
		unique_together = ('programvare', 'brukergruppe')
		default_permissions = ('add', 'change', 'delete', 'view')



class SystemBruk(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	brukergruppe = models.ForeignKey(
			to=Virksomhet,
			related_name='systembruk_brukergruppe',
			verbose_name="Brukergruppe",
			on_delete=models.PROTECT,
			blank=False,
			null=False,
			)
	system = models.ForeignKey(
			to=System,
			related_name='systembruk_system',
			verbose_name="System som brukes",
			blank=False,
			null=False,
			on_delete=models.PROTECT,  # slett SystemBruken når Systemet slettes
			)
	ibruk = models.BooleanField(
			verbose_name="Er systemet i bruk?",
			blank=False,
			null=False,
			default=True,
			help_text=u"Er i bruk ved kryss, og 'ikke i bruk' når kryss fjernes. Kan fjernes i stedet for å slette koblingen og lokale vurderinger.",
			)
	del_behandlinger = models.BooleanField(
			verbose_name="Abonner på felles behandlinger i systemet",
			blank=True,
			default=False,
			help_text=u"Krysser du av på denne, vil alle felles behandlinger for systemet havne i din behandlingsprotokoll",
			)
	systemforvalter = models.ForeignKey(
			to=Virksomhet,
			related_name='systembruk_systemforvalter',
			on_delete=models.SET_NULL,
			verbose_name="Lokal kontaktperson",
			blank=True,
			null=True,
			help_text=u"Lokal kontaktperson for virksomhets bruk av systemet",
			)
	systemforvalter_kontaktpersoner_referanse = models.ManyToManyField(
			to=Ansvarlig,
			related_name='systembruk_systemforvalter_kontaktpersoner',
			verbose_name="Lokal forvalter (person)",
			blank=True,
			help_text=u"Dersom fellesløsning på applikasjonshotell, hvilke roller/personer fyller rollen som lokal forvalter?",
			)
	systemeier_kontaktpersoner_referanse = models.ManyToManyField(
			to=Ansvarlig,
			related_name='systembruk_systemeier_kontaktpersoner',
			verbose_name="Lokal eier (person)",
			blank=True,
			help_text=u"Dersom fellesløsning på applikasjonshotell, hvilke roller/personer fyller rollen som lokal eier?",
			)
	livslop_status = models.IntegerField(
			choices=LIVSLOEP_VALG,
			verbose_name="Livsløpstatus",
			blank=True,
			null=True,
			help_text=u"",
			)
	avhengigheter_referanser = models.ManyToManyField(
			to="System",
			related_name='systembruk_avhengigheter_referanser',
			verbose_name="Systemtekniske avhengigheter til andre systemer",
			blank=True,
			help_text=u"Andre systemer dette systemet har systemtekniske avhengigheter til.",
			)
	avhengigheter = models.TextField(
			verbose_name="Avhengigheter (fritekst)",
			blank=True,
			null=True,
			help_text=u"Moduler og eksterne/interne integrasjoner som er i bruk",
			)
	kommentar = models.TextField(
			verbose_name="Kommentarer til denne bruken",
			blank=True,
			null=True,
			help_text=u"Utdyp hva systemet brukes til hos din virksomhet.",
			)
	systemeierskap = models.TextField(
			verbose_name="Systemeierskap (fritekst)",
			blank=True,
			null=True,
			help_text=u"Hvis det er behov for å presisere eierskapet utover det som står på systemsiden.")
	#systemleverandor = models.ManyToManyField(Leverandor, related_name='systembruk_systemleverandor',
	#		verbose_name="Systemleverandør",
	#		blank=True,
	#		)
	driftsmodell_foreignkey = models.ForeignKey(
			to=Driftsmodell,
			related_name='systembruk_driftsmodell',
			on_delete=models.SET_NULL,
			verbose_name="Driftsmodell / plattform (for denne bruken)",
			blank=True,
			null=True,
			help_text=u"Dette feltet blir faset ut. Dette er spesifisert på systemet.",
			)
	antall_brukere = models.IntegerField(  #reintrodusert 31.08.2020
			verbose_name="Antall brukere?",
			blank=True,
			null=True,
			help_text=u"Ca hvor mange bruker systemet hos dere? (fylles ut dersom relevant)",
			)
	konfidensialitetsvurdering = models.IntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Konfidensialitetsvurdering",
			blank=True,
			null=True,
			help_text=u"Hvor sensitive er opplysningene?",
			)
	integritetsvurdering = models.IntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Integritetsvurdering",
			blank=True,
			null=True,
			help_text=u"Hvor kritisk er det at opplysningene stemmer?",
			)
	tilgjengelighetsvurdering = models.IntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Tilgjengelighetsvurdering",
			blank=True,
			null=True,
			help_text=u"Hvor kritisk er det om systemet ikke virker?",
			)
	avtaletype = models.CharField(
			verbose_name="Avtaletype (fritekst)",
			max_length=250,
			blank=True,
			null=True,
			help_text=u"",
			)
	avtalestatus = models.IntegerField(
			choices=VURDERING_AVTALESTATUS_VALG,
			verbose_name="Avtalestatus",
			blank=True,
			null=True,
			help_text=u"",
			)
	avtale_kan_avropes = models.BooleanField(
			verbose_name="Avtale kan avropes av andre virksomheter",
			blank=True,
			null=True,
			help_text=u"",
			)
	#borger = models.IntegerField(blank=True, null=True, choices=IBRUK_VALG,
	#		verbose_name="For borger?",
	#		help_text=u"",
	#		)
	kostnadersystem = models.IntegerField(
			verbose_name="Kostnader for system",
			blank=True,
			null=True, help_text=u"",
			)
	systemeierskapsmodell = models.CharField(
			choices=SYSTEMEIERSKAPSMODELL_VALG,
			verbose_name="Systemeierskapsmodell",
			max_length=30,
			blank=True,
			null=True,
			help_text=u"Feltet skal avvikles da dette settes på systemet, ikke bruken",
			)
	programvarekategori = models.IntegerField(
			choices=PROGRAMVAREKATEGORI_VALG,
			verbose_name="Programvarekategori",
			blank=True,
			null=True,
			help_text=u"Feltet skal avvikles. Har ikke noe her å gjøre.",
			)
	strategisk_egnethet = models.IntegerField(
			choices=VURDERINGER_STRATEGISK_VALG,
			verbose_name="Strategisk egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	funksjonell_egnethet = models.IntegerField(
			choices=VURDERINGER_FUNKSJONELL_VALG,
			verbose_name="Funksjonell egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	teknisk_egnethet = models.IntegerField(
			choices=VURDERINGER_TEKNISK_VALG,
			verbose_name="Teknisk egnethet",
			blank=True,
			null=True,
			help_text=u"",
			)
	url_risikovurdering = models.URLField(
			verbose_name="Risikovurdering (URL)",
			blank=True,
			null=True,
			help_text=u"URL-referanse dersom det finnes. Om ikke kan fritekstfeltet under benyttes.",
			)
	risikovurdering_tekst = models.TextField(
			verbose_name="Risikovurdering fritekst",
			blank=True,
			null=True,
			help_text=u"Ytterligere detaljer knyttet til gjennomføringen av risikovurdering for systemet.",
			)
	dato_sist_ros = models.DateTimeField(
			verbose_name="Dato sist gjennomførte risikovurdering",
			blank=True,
			null=True,
			help_text=u"(tidspunkt er påkrevet - sett 'Nå')",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s - %s' % (self.system, self.brukergruppe)

	class Meta:
		verbose_name_plural = "Organisasjon: Systembruk"
		unique_together = ('system', 'brukergruppe')
		default_permissions = ('add', 'change', 'delete', 'view')

	#def antall_behandlinger_virksomhet(self):
	# må generalisere denne fuksjonen..
	#	return BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=self.virksomhet_pk).filter(systemer=bruk.system.pk).count()

class BehandlingInformering(models.Model):
	navn = models.CharField(
			unique=True,
			verbose_name="Informeringsnavn",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"Tekst til valgmeny",
			)
	beskrivelse = models.TextField(
			verbose_name="Beskrivelse",
			blank=True,
			null=True,
			help_text=u"",
			)

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Behandling: Informeringsvalg"
		default_permissions = ('add', 'change', 'delete', 'view')


class RegistrertKlassifisering(models.Model):
	navn = models.CharField(
			unique=True,
			verbose_name="Klassifikasjon",
			max_length=100,
			blank=False,
			null=False,
			help_text=u"F.eks. \"Særlige sårbare personer\", \"Vanlige personer\" og \"Profesjonelle aktører\".",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True,
			null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Behandling: Klasser av registrerte"
		default_permissions = ('add', 'change', 'delete', 'view')


class WANLokasjon(models.Model):
	lokasjons_id = models.CharField(
			unique=True,
			verbose_name="Lokasjons ID",
			blank=False,
			null=False,
			max_length=15,
			)
	virksomhet = models.ForeignKey(
			to=Virksomhet,
			on_delete=models.SET_NULL,
			verbose_name="Virksomhetstilhørighet",
			blank=True,
			null=True,
			)
	aksess_type = models.TextField(
			verbose_name="Aksesstype",
			blank=True,
			null=True,
			)
	adresse = models.TextField(
			verbose_name="Lokasjonsadresse",
			blank=True,
			null=True,
		)
	beskrivelse = models.TextField(
			verbose_name="Beskrivelse",
			blank=False,
			null=False,
			)

	def __str__(self):
		return u'%s' % (self.lokasjons_id)

	class Meta:
		verbose_name_plural = "CMDB: WAN Lokasjoner"
		default_permissions = ('add', 'change', 'delete', 'view')



class RelasjonRegistrert(models.Model):
	navn = models.CharField(
			unique=True,
			verbose_name="Navn på valg",
			max_length=150,
			blank=False, null=False,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Behandling: Registrerts relasjoner"
		default_permissions = ('add', 'change', 'delete', 'view')


BEHANDLING_VALGFRIHET = (
	(1, 'Stor valgfrihet'),
	(2, 'Middels valgfrihet'),
	(3, 'Ingen valgfrihet'),
)


class AzureNamedLocations(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	active = models.BooleanField(
			verbose_name="Aktiv",
			default=True,
			)
	ipNamedLocation_id = models.CharField(
			unique=True,
			verbose_name="Named Location ID",
			blank=False,
			null=False,
			max_length=256,
			)
	displayName = models.CharField(
			unique=True,
			verbose_name="Display Name",
			blank=True,
			null=True,
			max_length=512,
			)
	sist_endret = models.DateTimeField(
			verbose_name="Sist endret",
			blank=True,
			null=True,
			)
	isTrusted = models.BooleanField(
			verbose_name="Trygg gruppe (Is trusted)",
			default=False,
			)
	ipRanges = models.TextField(
			verbose_name="IP-ranges (subnet)",
			blank=True,
			null=True,
		)
	countriesAndRegions = models.TextField(
			verbose_name="Land og regioner",
			blank=True,
			null=True,
			)

	def __str__(self):
		return u'%s' % (self.displayName)

	class Meta:
		verbose_name_plural = "Azure: Named locations"
		default_permissions = ('add', 'change', 'delete', 'view')


class BehandlingerPersonopplysninger(models.Model):
	# Draftit - Records, kalles der en "behandllingsaktivitet"
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
			#draftit: metafelt, har dette
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
			#draftit: metafelt, har dette
	kvalitetssikret = models.OneToOneField(
			to=Oppdatering,
			related_name='behandling_kvalitetssikret',
			verbose_name="Kvalitetssikret",
			blank=True,
			null=True,
			on_delete=models.PROTECT,
			help_text=u"Tidspunkt informasjonen er kvalitetssikret.",
			)
	informasjon_kvalitetssikret = models.BooleanField(
			verbose_name="Er informasjonen kvalitetssikret av behandlingsansvarlig?",
			default=False,
			help_text=u"Krysses av når denne behandlingen er klar i første versjon.",
			)
			#draftit: har ikke dette nå
	oppdateringsansvarlig = models.ManyToManyField(
			to=Ansvarlig,
			related_name='behandling_kontaktperson',
			verbose_name="Oppdateringsansvarlig",
			blank=False,
			help_text=u"Denne personen er ansvarlig for å holde denne behandlingen oppdatert. Dersom du ikke finner personen du leter etter i listen kan du opprette en ny ansvarlig ved å trykke på +-tegnet til høyre for boksen.",
			)
			#draftit: ansvarlig (epost til den som redigerer)
	fellesbehandling = models.BooleanField(
			verbose_name="Fellesbehandling?",
			default=False,
			help_text="Dersom denne behandlingen gjelder et system mange virksomheter bruker kan du krysse av for denne. Virksomheter som velger å abonnere på delte behandlinger (under sin systembruk) vil da få opp denne i sin behandlingsprotokoll.",
			)
			#draftit: ingen tilsvarende
	krav_sikkerhetsnivaa  = models.IntegerField(
			choices=SIKKERHETSNIVAA_VALG,
			verbose_name="Krav til sikkerhetsnivå",
			blank=True,
			null=True,
			help_text=u'Sensitiviteten til opplysninger i systemet. Se <a target="_blank" href="https://confluence.oslo.kommune.no/x/y8seAw">Informasjonstyper og behandlingskrav</a>',
			)
			#draftit: ingen tilsvarende
	dpia_tidligere_bekymringer_risikoer = models.TextField(
			verbose_name="Er det tidligere avdekket risikoer/bekymringer over denne typen behandling?",
			blank=True,
			null=True,
			help_text=u"",
			)
			#draftit: ingen tilsvarende #draftit: dpia-modul
	dpia_tidligere_avdekket_sikkerhetsbrudd = models.TextField(
			verbose_name="Er det tidligere avdekket sikkerhetsbrudd i fm. tilsvarende behandling?",
			blank=True,
			null=True,
			help_text=u"",
			)
			#draftit: avvik (ja/nei + forklaring av avvik) #draftit: dpia-modul
	behandlingsansvarlig = models.ForeignKey(
			to=Virksomhet,
			related_name='behandling_behandlingsansvarlig',
			verbose_name="Registrert av",
			on_delete=models.PROTECT,
			help_text=u"Den virksomhet som eier denne behandlingen. Må ikke forveksles med behandlingsansvarlig.",
			)
			#draftit: behandlingsansvarlig.


	#behandlingsansvarlig_representant = models.ForeignKey(Ansvarlig, related_name='behandling_behandlingsansvarlig_representant',
	#		verbose_name="Ansvarlig person",
	#		blank=True, null=True,
	#		on_delete=models.PROTECT,
	#		help_text=u"Den person som er ansvarlig for å holde denne behandlingen oppdatert.",
	#		)
	internt_ansvarlig = models.CharField(
			verbose_name="Ansvarlig avdeling/enhet",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Angi hvem som er internt ansvarlig (dataansvarlig) eller avdeling. Eksempler: Personaladministrasjon (HR), Skoleadministrasjon",
			)
			#draftit: enhet som en objektreferanse.
	funksjonsomraade = models.CharField(
			verbose_name="Hovedoppgave / Hovedformål",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Hvilket overordnet funksjons-eller virksomhetsområde faller behandlingen under? Angi eventuell hovedoppgave eller hovedformål.Eksempler: HR-prosesser, Oppfølging av pasient, Regnskap",
			)
			#draftit: enhet er det som brukes her. Må finne en mapping.
			#trenger vi to?
	behandlingen = models.TextField(
			verbose_name="Kort setning som oppsummerer behandlingen.",
			max_length=80,
			blank=False,
			null=False,
			help_text=u"Beskriv kort hva som skjer i prosessen. Denne brukes for hurtigvisning. Det skal kun være noen få ord som beskriver hva behandlingen av personopplysninger innebærer. Eksempler: Personaladministrasjon (HR), Besøksregistrering, Bakgrunnssjekk av ansatte, Saksbehandling, Oppfølging av sykefravær",
			)
			#dradtit: behandlingsaktivitet (tekst)
	ny_endret_prosess = models.TextField(
			verbose_name="Innebærer behandlingen på noen måte ny/endret prosess?",
			blank=True,
			null=True,
			help_text=u""
			)
			#draftit: dpia-modul
	dpia_dekker_formal = models.TextField(
			verbose_name="Dekker behandlingsprosessen det faktiske formålet, og er det andre måter å oppnå det samme resultatet?",
			blank=True,
			null=True,
			help_text=u"Noe tilsvarende dataminimering, ikke sant?",
			)
			#draftit: dpia-modul
	formaal = models.TextField(
			verbose_name="Hva er formålene med behandlingen?",
			blank=False,
			null=True,
			help_text=u"Angi hva som er formålene med behandlingen, inkludert hvorfor opplysningene blir samlet inn. Forklaringen skal være slik at alle berørte har en felles forståelse av hva opplysningene brukes til. Om behandlingen dekker flere formål kan det være nyttig å dele inn beskrivelsen i flere delområder slik at fokus settes på formålet med behandlingen. HR/personal vil for eksempel ha flere formål med å samle inn personopplysninger om ansatte; f.eks. utbetale lønn, personal-administrasjon, kompetanseoversikt mv. Eksempler: Rekruttere ansatte basert på riktig erfaring og utdanning, Utbetale lønn til de ansatte, Sikre identifisering før tilgang blir gitt.",
			)
			#draftit: "formål"
	dpia_effekt_enkelte = models.TextField(
			verbose_name="Effekt for de registrerte?",
			blank=True,
			null=True,
			help_text=u"Beskriv den påtenkte effekten - positiv og negativ - på enkeltpersoner som blir omfattet av behandlingen",
			)
			#draftit: dpia-modul
	dpia_effekt_samfunnet = models.TextField(
			verbose_name="Formål som realiseres for samfunnet?",
			blank=True,
			null=True,
			help_text=u"Beskriv hvilke positive effekter behandlingen har for samfunnet / Virksomheten og evt. hvilken ulempe det innebærer hvis behandlingen ikke kan gjennomføres",
			)
			#draftit: dpia-modul
	dpia_proporsjonalitet_enkelte_samfunnet = models.TextField(
			verbose_name="Beskriv vurderingen som er foretatt av proporsjonalitet mellom samfunnsgevinst ved behandlingen og potensiell risiko for de registrerte",
			blank=True,
			null=True,
			help_text=u"",
			)
			#draftit: dpia-modul
	kategorier_personopplysninger = models.ManyToManyField(
			to=Personsonopplysningskategori,
			related_name='behandling_kategorier_personopplysninger',
			verbose_name="Kategorier personopplysninger som behandles",
			blank=False,
			help_text=u"",
			)
			#draftit: to spørsmål: "identitetsopplysninger" og "kontaktopplysnigner" og "sensitive personopplysninger".
			# mot kartoteket slår vi dem sammen og oppretter Personsonopplysningskategori ved behov.
	personopplysninger_utdyping = models.TextField(
			verbose_name="Utdyping av personopplysninger som behandles",
			blank=True,
			null=True,
			help_text=u"Kontaktopplysninger, Søknad/CV, skatt og arbeidsgiveravgift",
			)
			# draftit: ser ikke behovet.
	den_registrerte = models.ManyToManyField(
			to=Registrerte,
			related_name='behandling_den_registrerte',
			verbose_name="Hvem er den registrerte? (grupper)",
			blank=False,
			help_text=u"",
			)
			#draftit: "kartegori registrerte", valgmeny
	relasjon_registrerte = models.ManyToManyField(
			to=RelasjonRegistrert,
			verbose_name="Hvilken relasjon har virksomheten til de registrerte?",
			blank=True,
			help_text=u"",
			)
	#burde vært rettet opp til valgfrihet
	valgfriget_registrerte = models.IntegerField(
			choices=BEHANDLING_VALGFRIHET,
			verbose_name="Hvor mye kontroll vil de registrerte ha på den behandlingen som foretas?",
			blank=True,
			null=True,
			help_text=u''
			)
			#draftit: har ikke
			# DPIA-relatert, Trenger vi dette feltet?
	den_registrerte_sarbare_grupper = models.BooleanField(
			verbose_name="Inkluderer behandlingen barn eller andre sårbare grupper (f.eks. uføre, eldre, syke)?",
			blank=True,
			null=True,
			help_text=u"",
			)
			# draftit: har spørsmålet under "registreres opplyninger om barn" - men ikke noe eget for eldre.
			# dpia-relatert.
	forventet_bruk = models.TextField(
			verbose_name="Vil de registrerte forvente at personopplysninger om dem brukes på denne måten?",
			blank=True,
			null=True,
			help_text=u"",
			)
			# draftit: ikke noe tilsvarende
	den_registrerte_hovedkateogi = models.ManyToManyField(
			to=RegistrertKlassifisering,
			related_name='behandling_den_registrerte_hovedkateogi',
			verbose_name="Hvem er den registrerte? (klassifisering)",
			blank=True,
			help_text=u"",
			)
			# draftit: nei
			# trenger vi denne?
	den_registrerte_detaljer = models.TextField(
			verbose_name="Ytdyping av de registrerte. F.eks. i hvilket geografisk område befinner de registrerte seg?",
			blank=True,
			null=True,
			help_text=u"Utdypning om hvem det behandles opplysninger om.",
			)
			# draftit: ikke noe felt om dette
			# trenger vi denne?
	antall_registrerte = models.TextField(
			verbose_name="Antall registrerte i behandlingsprosessen.",
			blank=True,
			null=True,
			help_text=u"En tekstlig beskrivelse av omfanget av de registrerte. Gjerne begrenset til en aldersgruppe og geografisk område.",
			)
			# draftit: hvor mange er registrert i behandlingen (intervaller)
			# dpia-relatert.
	tilgang_opplysninger = models.TextField(
			verbose_name="Brukergrupper med tilgang til personopplysningene i behandlingsprosessen",
			blank=True,
			null=True,
			help_text=u"Beskriv hvor mange / hvem som vil få tilgang til opplysnignene internt.",
			)
			#draftit: "hvilke enheter har tilgang til opplysningene" med valgmeny
	behandlingsgrunnlag_valg = models.ManyToManyField(
			to=Behandlingsgrunnlag,
			related_name='behandling_behandlingsgrunnlag_valg',
			verbose_name="Hva er grunnlaget (hjemmel) for denne behandlingsprosessen (behandlingen)?",
			blank=True,
			help_text=u"Her må hjemmel i så vel i personopplysnings-loven som i aktuelle særlov f.eks. barnevernloven beskrives",
			)
			#draftit: behandlingsgrunnlag
	behandlingsgrunnlag_utdyping = models.TextField(
			verbose_name="Utdyping av rettslig forpliktelse, berettighet interesse mv",
			blank=True,
			null=True,
			help_text=u"F.eks. Skattebetalingsloven, A-meldingsloven",
			)
			#draftit: "begrunn valgt behandlingsgrunnlag" (tekst) (vedlegg - trenger vi ikke)
	behandlingsgrunnlag_saerlige_kategorier = models.TextField(
			verbose_name="Utdyping av behandlingsgrunnlag dersom særskilte kategorier personopplysninger",
			null=True,
			blank=True,
			help_text=u"Behandlingsgrunnlag etter artikkel 9 eller 10, Med ev henvisning også til annen lovgivning dersom relevant",
			)
			#draftit: ikke eget felt for dette
			#trenger vi denne? slå sammen.
	opplysningskilde = models.TextField(
			verbose_name="Hvor er opplysningene innsamlet fra?",
			blank=True,
			null=True,
			help_text=u"Den registrerte, egen virksomhet, adressemekler",
			)
			#draftit: informasjonsplikt: "kilder opplysningene hentes fra" (valg)
			# burde det vært valg?
	frekvens_automatisert_innsamling = models.TextField(
			verbose_name="Hvor ofte foretas automatisert elektronisk innsamling?",
			blank=True,
			null=True,
			help_text=u"Hva trigger ny innhenting?",
			)
			# draftit: har ikke dette
	frekvens_innsamling_manuelt = models.TextField(
			verbose_name="Hvor ofte mottas personopplysninger som følge av aktive skritt fra de registrerte, ansatte eller tredjepart?",
			blank=True,
			null=True,
			help_text=u"",
			)
			# draftit: har ikke dette
	systemer = models.ManyToManyField(
			to=System,
			related_name='behandling_systemer',
			verbose_name="Systemer som benyttes i behandlingen",
			blank=False,
			help_text=u"For fellessystemer anbefales det splitte opp behandlinger per system, slik at det i praksis bare er ét system i denne listen.",
			)
			# draftit: system: liste over systemer, må vi få synkronisert.
	programvarer = models.ManyToManyField(
			to=Programvare,
			related_name='behandling_programvarer',
			verbose_name="Programvarer som benyttes i behandlingen",
			blank=True,
			help_text=u"Programvarer benyttet i behandlingen",
			)
			#draftit: ikke eget felt, bruker system.
	oppbevaringsplikt = models.TextField(
			verbose_name="Finnes det oppbevaringsplikt for behandlingen?",
			blank=True,
			null=True,
			help_text=u"Andre krav til lagring ut fra andre behandlingsgrunnlag f.eks. oppbevaringsplikt i bokføringsloven, behov for bevissikring, arkivplikt m.m. for behandlingen (hjemmel)",
			)
			#deraftit: har ikke noe konkret her
	sikre_dataminimalisering = models.TextField(
			verbose_name="Tiltak for dataminimalisering",
			blank=True,
			null=True,
			help_text=u"Beskriv tiltak som er gjennomført for å sikre dataminimalisering. Det å unngå å oppbevare informasjon som ikke er nødvendig.",
			)
			#draftit: ikke noe konkret felt.
	krav_slettefrister = models.TextField(
			verbose_name="Krav til sletting?",
			blank=True,
			null=True,
			help_text=u"Hva er krav til tidsfrister for sletting ut fra opprinnelig behandlingsgrunnlag?<br>Hva er krav til tidsfrister for sletting ut fra andre behandlingsgrunnlag f.eks. oppbevaringsplikt i bokføringsloven, behov for bevissikring, arkivplikt m.m. for behandlingen (lagringstid)?",
			)
			# draftit: "Hvilken tidsfrist finnes for sletting" (tekst)
	planlagte_slettefrister = models.TextField(
			verbose_name="Hva er gjeldende prosedyre for sletting?",
			blank=True,
			null=True,
			help_text=u"Et viktig prinsipp er at personopplysninger skal slettes når det ikke lenger er saklig behov for dem. Fylles ut dersom mulig. F.eks. x måneder/år etter hendelse/prosess",
			)
			#draftit: "finnes det skriftelige rutiner" (med vedlegg)
			#slå sammen? valg?
	begrensning_tilgang = models.TextField(
			verbose_name="Begrensning av tilganger",
			blank=True,
			null=True,
			help_text=u"I henhold til Artikkel 18. Hvilken gruppe saksbehandlere skal ha tilgang etter avsluttet saksbehandling hvis det foreligger oppbevaringsplikt / tidsintervall p.r. gruppe? (Tilgangsbegrensning basert på hvem som har tjenstlig behov i hvilke tidsintervaller)",
			)
			# draftit: ikke noe felt på dette
	navn_databehandler = models.ManyToManyField(
			to=Leverandor,
			related_name='behandling_navn_databehandler',
			verbose_name="Eksterne databehandlere",
			blank=True,
			help_text=u"Ved bruk av databehandlere (ekstern leverandør), angi hvilke dette er. Underleverandører er også databehandlere.",
			)
			#draftit: "databehandler" () (men har også et valg: er det ekstern databehandler?)
	dpia_prosess_godkjenne_underleverandor = models.TextField(
			verbose_name="Hvilken prosess for godkjennelse av underleverandører er etablert (ved avtaleinngåelse og ved bruk av nye underleverandører i avtaleperioden)?",
			blank=True,
			null=True,
			help_text=u"",
			)
			#draftit: i dpia
	databehandleravtale_status = models.TextField(
			verbose_name="Er det inngått databehandleravtale med tredjepart(er)?",
			blank=True,
			null=True,
			help_text=u"Utdyp",
			)
			#draftit: "er det inngått skriftelig avtale" (boolean)
	databehandleravtale_status_boolean = models.BooleanField(
			verbose_name="Er det inngått databehandleravtale med alle?",
			blank=True,
			null=True,
			help_text=u"",
			)
			#draftit: ikke eget felt.
	dpia_dba_ivaretakelse_sikkerhet = models.TextField(
			verbose_name="Hvilke krav er stilt til leverandøren(e) til ivaretakelse av personvern og informasjonssikkerhet?",
			blank=True,
			null=True,
			help_text=u"",
			)
			#draftit: har noe tilsvarende i dpia-modulen.
	kommunens_maler = models.BooleanField(
			verbose_name="Er Oslo kommunes maler for databehandleravtaler benyttet i avtale(ne) med leverandøren(e)?",
			blank=True,
			null=True,
			help_text=u"",
			)
	kommunens_maler_hvis_nei = models.TextField(
			verbose_name="Hvis Oslo kommunes maler for databehandleravtaler ikke er benyttet, er avtalen gjennomgått av jurist og informasjonssikkerhetsansvarlig i virksomheten? Beskrive resultatet av gjennomgangen.",
			blank=True,
			null=True,
			help_text=u"",
			)
	utlevering_ekstern_myndighet = models.BooleanField(
			verbose_name="Utleveres opplysninger til eksterne aktører?",
			blank=True,
			null=True,
			help_text=u"F.eks. eksterne myndigheter eller liknende.",
			)
	utlevering_ekstern_myndighet_utdyping = models.TextField(
			verbose_name="Utdyp utlevering til tredjeparter",
			blank=True,
			null=True,
			help_text=u"Henvis til hjemmel i lov",
			)
	innhenting_ekstern_myndighet = models.BooleanField(
			verbose_name="Innhentes opplysninger fra eksterne aktører?",
			blank=True,
			null=True,
			help_text=u"F.eks. eksterne myndigheter eller liknende.",
			)
	innhenting_ekstern_myndighet_utdyping = models.TextField(
			verbose_name="Utdyp innhenting fra tredjeparter",
			blank=True,
			null=True,
			help_text=u"Henvis til hjemmel i lov",
			)
	utlevering_registrerte_samtykke = models.BooleanField(
			verbose_name="Utleveres opplysningene til pårørende e.l. ved bruk av samtykke?",
			blank=False,
			null=True,
			help_text=u"",
			)
	utlevering_registrerte_samtykke_utdyping = models.TextField(
			verbose_name="Utdyp utlevering basert på samtykke",
			blank=True,
			null=True,
			help_text=u"",
			)
	tjenesteleveranse_land = models.TextField(
			verbose_name="Fra hvilke land leverer leverandører og underleverandører tjenester m.m. som inngår i avtalen?",
			blank=True,
			null=True,
			help_text=u"",
			)
	utlevering_utenfor_EU = models.BooleanField(
			verbose_name="Skjer det en overføring av opplysninger til land utenfor EU/EØS?",
			blank=False,
			null=True,
			help_text=u"",
			)
	garantier_overforing = models.TextField(
			verbose_name="Utdyp utlevering utenfor EU. Er det inngått EU Model Clause eller på annen måte sikret hjemmel for eksport av data ut av EØS området?",
			blank=True,
			null=True,
			help_text=u"Nødvendige garantier ved overføring til tredjeland eller internasjonale organisasjoner",
			)
	informering_til_registrerte = models.TextField(
			verbose_name="Hvilken informasjon gis til den registrerte om behandlingen?",
			blank=True,
			null=True,
			help_text=u"Beskriv tiltak som er gjennomført for at de registrerte får vite hva opplysningene om dem brukes til (f.eks. personvernerklæring). Hvilke tiltak er iverksatt for å hjelpe den registrerte til å kunne gjøre bruk av sine rettigheter etter personopplysningsloven (f.eks. informasjonsskriv om rettigheter, etablering av portal som kan håndtere henvendelse m.m.)?",
			)
			#draftit: Informasjonsplikt --> "på hvilkemn måte.." (valg) og "hva har registrerte mottatt informasjon om" (valg)
			#burde vi ha valg?
			#hjelpeteksten bør forbedres.
	innsyn_egenkontroll = models.TextField(
			verbose_name="Registrertes mulighet for innsyn og kontroll?",
			blank=True,
			null=True,
			help_text=u"Beskriv tiltak som er gjennomført for at de registrerte får innsyn i og kan kontrollere opplysningene registrert om dem",
			)
	rette_opplysninger = models.TextField(
			verbose_name="Hvordan kan den registrerte rette egne opplysninger?",
			blank=True,
			null=True,
			help_text=u"Beskriv tiltak som er gjennomført for at de registrerte kan rette sine opplysninger",
			)
	hoy_personvernrisiko = models.BooleanField(
			verbose_name="UTFASES! Høy personvernrisiko? Er det behov for å vurdere personvernkonsekvenser (DPIA)?",
			default=None,
			null=True,
			help_text="UTFASES! Se veiledningen <a target=\"_blank\" href=\"https://confluence.oslo.kommune.no/pages/viewpage.action?pageId=86934676\">Vurdering av om «høy risiko» foreligger</a>.",
			)
	dpia_unnga_hoy_risiko = models.BooleanField(
			verbose_name="Er det mulig å unngå 'høy risiko' for de registrerte?",
			default=None,
			null=True,
			help_text="",
			)
	sikkerhetstiltak = models.TextField(
			verbose_name="Hvilke organisatoriske tiltak for informasjonssikkerhet er gjennomført? ",
			blank=True,
			null=True,
			help_text=u"Manuelle rutiner som f.eks. autorisering av personell, gjennomgang av logger, revisjoner og regelmessig sletting. De tekniske tiltakene er beskrevet under det enkelte system.",
			)
	virksomhet_blacklist = models.ManyToManyField(
			to=Virksomhet,
			verbose_name="Ekskluderingsliste for fellesbehandling (ikke i bruk)",
			related_name="behandling_virksomhet_blacklist",
			blank=True,
			help_text="Behandlingen vises ikke i behandlingsoversikten for disse virksomhetene. Dette feltet er utfaset.",
			)
	ekstern_DPIA_url = models.URLField(
			verbose_name="Link til DPIA-vurdering",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Dersom det er behov for DPIA, kan du legge inn full URL til dokumentet her.",
			)
	databehandleravtaler = models.ManyToManyField(
			to=Avtale,
			related_name='behandling_databehandleravtaler',
			verbose_name="Databehandleravtaler knyttet til behandlingen",
			blank=True,
			help_text=u"Si noe om at normalt gjøres dette via kobling til system... TODO",
			)
	informering_til_registrerte_valg = models.ManyToManyField(
		to=BehandlingInformering,
		verbose_name="Informering til den registrerte",
		blank=True,
		help_text=u"Åpenhet om behandling er et viktig personvernsprinsipp. Hvordan informeres den registrete om hva som behandles, og hvilke rettigheter den registrerte har?",
		)

	history = HistoricalRecords()

	def __str__(self):
		return u'%s: %s' % (self.behandlingsansvarlig, self.behandlingen)

	class Meta:
		verbose_name_plural = "Behandling: Behandlingsprotokoller"
		default_permissions = ('add', 'change', 'delete', 'view')


BEHOV_FOR_DPIA_VALG = (
	(0, "Ikke vurdert"),
	(1, "Ja"),
	(2, "Nei"),
)


class BehovForDPIA(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	behandling = models.OneToOneField(
			to=BehandlingerPersonopplysninger,
			related_name="behandling_behovdpia",
			on_delete=models.PROTECT,
			blank=False,
			null=False,
			help_text=u"Behandlingen denne vurderingen gjelder for.",
			)
	evaluering_profilering = models.IntegerField(
			choices=BEHOV_FOR_DPIA_VALG,
			default=0,
			null=False,
			verbose_name="Evaluering eller poengsetting?",
			help_text=u'Innebærer behandlingen evaluering eller scoring / profilering i stor skala for å forutsi den registrertes antatte evner/egenskaper? (Inkludert profilering og forutsigelse, spesielt «aspekter som gjelder arbeidsprestasjoner, økonomisk situasjon, helse, personlige preferanser eller interesser, pålitelighet eller atferd, plassering eller bevegelser» (fortalepunkt 71 og 91).)',
			)
	automatiskbeslutning = models.IntegerField(
			choices=BEHOV_FOR_DPIA_VALG,
			default=0,
			null=False,
			verbose_name="Automatiske beslutninger med rettslig eller tilsvarende betydelig virkning?",
			help_text=u'Behandling som har som formål å ta beslutninger om den registrerte som har «rettsvirkning for den fysiske personen» eller «på lignende måte i betydelig grad påvirker den fysiske personen» (artikkel 35 nr. 3 a).',
			)
	systematiskmonitorering = models.IntegerField(
			choices=BEHOV_FOR_DPIA_VALG,
			default=0,
			null=False,
			verbose_name="Systematisk monitorering?",
			help_text=u'Behandlingsaktiviteter som brukes for å observere, overvåke eller kontrollere de registrerte, inkludert opplysninger som har blitt samlet inn gjennom nettverk eller «en systematisk overvåking i stor skala av et offentlig tilgjengelig område» (artikkel 35 nr. 3 c). ',
			)
	saerligekategorier = models.IntegerField(
			choices=BEHOV_FOR_DPIA_VALG,
			default=0,
			null=False,
			verbose_name="Særlige kategorier av personopplysninger eller opplysninger av svært personlig karakter ?",
			help_text=u'Dette omfatter særlige kategorier av personopplysninger (tidligere kalt sensitive personopplysninger) som er definert i artikkel 9 (for eksempel informasjon om enkeltpersoners politiske meninger), samt personopplysninger vedrørende straffedommer og lovovertredelser som definert i artikkel 10. ',
			)
	storskala = models.IntegerField(
			choices=BEHOV_FOR_DPIA_VALG,
			default=0,
			null=False,
			verbose_name="Personopplysninger behandles i stor skala?",
			help_text=u'Innebærer behandlingen evaluering eller scoring / profilering i stor skala for å forutsi den registrertes antatte evner/egenskaper?',
			)
	sammenstilling = models.IntegerField(
			choices=BEHOV_FOR_DPIA_VALG,
			default=0,
			null=False,
			verbose_name="Matching eller sammenstilling av datasett?",
			help_text=u'Dette kan for eksempel stamme fra to eller flere databehandlingsoperasjoner som gjennomføres med ulike formål og/eller av ulike behandlingsansvarlige på en måte som overstiger den registrertes rimelige forventninger.',
			)
	saarbare_registrerte = models.IntegerField(
			choices=BEHOV_FOR_DPIA_VALG,
			default=0,
			null=False,
			verbose_name="Personopplysninger om sårbare registrerte?",
			help_text=u'Behandling av denne typen av personopplysninger er et kriterium på grunn av den skjeve maktbalansen mellom de registrerte og den behandlingsansvarlige, som betyr at enkeltpersoner kan være ute av stand til, på en enkel måte, å gi sitt samtykke eller motsette seg behandlingen av sine personopplysninger eller utøve sine rettigheter. Sårbare registrerte kan omfatte barn (de kan anses å ikke være i stand til på en bevisst og gjennomtenkt måte å motsette seg eller gi samtykke til behandling av sine personopplysninger), arbeidstakere, mer sårbare befolkningsgrupper som behøver sosial beskyttelse (psykisk syke personer, asylsøkere, eldre personer, pasienter og så videre), samt i de situasjoner der det foreligger en ubalanse i forholdet mellom den registrerte og den behandlingsansvarlige.',
			)
	innovativ_anvendelse = models.IntegerField(
			choices=BEHOV_FOR_DPIA_VALG,
			default=0,
			null=False,
			verbose_name="Innovativ bruk eller anvendelse av ny teknologisk eller organisatorisk løsning?",
			help_text=u'Dette kan være en kombinasjon av fingeravtrykk og ansiktsgjenkjenning for en forbedret fysisk adgangskontroll og så videre. Det går klart frem av forordningen (artikkel 35 nr. 1 og fortalepunkt 89 og 91) at bruk av ny teknologi som defineres «i samsvar med det oppnådde nivået av teknisk kunnskap» (fortalepunkt 91), kan medføre behov for å gjennomføre en vurdering av personvernkonsekvenser. Grunnen til dette er at anvendelse av ny teknologi kan medføre nye former for innsamling og bruk av personopplysninger, eventuelt med høy risiko for den enkeltes rettigheter og friheter. De personlige og sosiale konsekvensene ved anvendelsen av ny teknologi kan være ukjente. En vurdering av personvernkonsekvenser hjelper den behandlingsansvarlige å forstå og håndtere slike risikoer. For eksempel kan visse «tingenes internett»-applikasjoner få betydelige konsekvenser for den enkeltes dagligliv og privatliv, og kan derfor kreve en vurdering av personvernkonsekvenser.',
			)
	hinder = models.IntegerField(
			choices=BEHOV_FOR_DPIA_VALG,
			default=0,
			null=False,
			verbose_name="Når behandlingen «hindrer de registrerte i å utøve en rettighet eller gjøre bruk av en tjeneste eller en avtale» (artikkel 22 og fortalepunkt 91)",
			help_text=u'Dette omfatter behandlinger som tar sikte på å tillate, endre eller nekte den registrerte tilgang til en tjeneste eller inngå en avtale. For eksempel når en bank kredittvurderer sine kunder mot en database for å avgjøre om de skal tilbys lån.',
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'Vurdering for %s' % (self.behandling)

	def behovforDPIA(self):
		kriterier = [self.evaluering_profilering, self.automatiskbeslutning, self.systematiskmonitorering, self.saerligekategorier, self.storskala, self.sammenstilling, self.saarbare_registrerte, self.innovativ_anvendelse, self.hinder]
		count = 0
		for k in kriterier:
			if k == 0:  # 0 represent "not evaluated"
				return "Ufullstendig utfylt"
			if k == 1:  # 1 represent "yes"
				count+= 1
		if count == 0:
			return "Nei"
		if count == 1:
			return "Kanskje"
		if count == 2:
			return "Trolig"
		if count > 2:
			return "Ja"


	class Meta:
		verbose_name_plural = "Behandling: DPIA-behovsvurderinger"
		default_permissions = ('add', 'change', 'delete', 'view')


class HRorg(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	active = models.BooleanField(
			verbose_name="Aktiv",
			default=True, # per definisjon
			help_text=u"Settes automatisk",
			)
	ouid = models.IntegerField(
			unique=True,
			verbose_name="OUID",
			null=False,
			help_text=u"Importert",
			)
	level = models.IntegerField(
			verbose_name="OULEVEL",
			null=True,
			help_text=u"Importert",
			)
	leder = models.ForeignKey(
			to=User,
			on_delete=models.PROTECT,
			related_name='hrorg_leder',
			verbose_name="Leder",
			null=True,
			help_text=u"Importert",
			)
	ou = models.CharField(
			verbose_name="OU",
			max_length=200,
			null=True,
			help_text=u"Importert",
			)
	virksomhet_mor = models.ForeignKey(
			to="Virksomhet",
			on_delete=models.SET_NULL,
			related_name='hrorg_virksomhet_mor',
			verbose_name="Overordnet virksomhet",
			null=True,
			help_text=u"Importert",
			)
	direkte_mor = models.ForeignKey(
			to="HRorg",
			on_delete=models.CASCADE,
			related_name='hrorg_direkte_mor',
			verbose_name="Overordnet enhet",
			null=True,
			help_text=u"Importert",
			)
	#ikke behov for historikk

	def __str__(self):
		if self.virksomhet_mor:
			return u'%s (%s)' % (self.ou, self.virksomhet_mor.virksomhetsforkortelse)
		else:
			return u'%s (ukjent)' % (self.ou)

	class Meta:
		verbose_name_plural = "Organisasjon: Organisasjonsledd"
		verbose_name  = "HR-organisasjonsledd"
		default_permissions = ('add', 'change', 'delete', 'view')


class PRKvalg(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	valgnavn = models.CharField(
			verbose_name="Valg",
			max_length=300,
			blank=False, null=False,
			help_text=u"Importert",
			db_index=True,
			)
	gruppenavn = models.CharField(
			unique=True,
			verbose_name="Gruppenavn i AD",
			max_length=1000,
			blank=False, null=False,
			help_text=u"Importert",
			db_index=True,
			)
	beskrivelse = models.CharField(
			verbose_name="Beskrivelse",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Importert",
			)
	virksomhet = models.ForeignKey(
			to=Virksomhet,
			related_name='prkvalg_virksomhet',
			verbose_name="Virksomhetstilknytning",
			null=True,
			on_delete=models.SET_NULL,
			help_text=u"Importert",
			)
	gruppering = models.ForeignKey(
			to="PRKgruppe",
			related_name='PRKvalg_gruppering',
			verbose_name="Gruppering",
			on_delete=models.PROTECT,
			help_text=u"Importert",
			)
	skjemanavn = models.ForeignKey(
			to="PRKskjema",
			related_name='PRKvalg_skjemanavn',
			verbose_name="Skjemanavn",
			on_delete=models.PROTECT,
			help_text=u"Importert",
			db_index=True,
			)
	ad_group_ref = models.ForeignKey(
			to="ADgroup",
			on_delete=models.CASCADE,
			related_name='prkvalg',
			verbose_name="Kobling PRK-valg mot AD gruppe",
			null=True,
			blank=True,
			help_text=u'Settes automatisk',
			)
	in_active_directory = models.BooleanField(
			verbose_name="Finnes i AD?",
			default=True, # per definisjon
			help_text=u"Settes automatisk",
			)
	systemer = models.ManyToManyField(
		to="System",
		related_name='prkvalg',
		verbose_name="Systemer basert på navneoppslag",
		)
	#ikke behov for historikk

	def __str__(self):
		return u'PRK-valg %s' % (self.valgnavn)

	def full_benevning(self):
		return u'Skjema %s, gruppering %s, valg %s' % (self.skjemanavn, self.gruppering, self.valgnavn)

	class Meta:
		verbose_name_plural = "PRK: PRK-valg"
		verbose_name = "PRK-valg"
		default_permissions = ('add', 'change', 'delete', 'view')


class PRKgruppe(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	feltnavn = models.CharField(
			unique=True,
			verbose_name="Feltnavn (PRK-gruppering)",
			max_length=200,
			blank=False, null=False,
			help_text=u"Importert",
			)
	#ikke behov for historikk

	def __str__(self):
		return u'%s' % (self.feltnavn)

	class Meta:
		verbose_name_plural = "PRK: PRK-grupper"
		default_permissions = ('add', 'change', 'delete', 'view')


class PRKskjema(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	skjemanavn = models.CharField(
			verbose_name="Skjemanavn",
			max_length=200,
			blank=False,
			null=False,
			help_text=u"Importert",
			)
	skjematype = models.CharField(
			verbose_name="Skjematype",
			max_length=200,
			blank=False,
			null=False,
			help_text=u"Importert",
			)
	er_lokalt = models.BooleanField(
			verbose_name="Er feltet lokalt?",
			default=None,
			null=True,
			help_text=u"Importert",
			)
	#ikke behov for historikk

	unique_together = ('skjemanavn', 'skjematype')

	def __str__(self):
		return u'%s (%s)' % (self.skjemanavn, self.skjematype)

	class Meta:
		verbose_name_plural = "PRK: PRK-skjemaer"
		default_permissions = ('add', 'change', 'delete', 'view')


RISIKO_VALG = (
	(0, '0 Ikke vurdert'),
	(1, '1 Lav'),
	(2, '2 Middels'),
	(3, '3 Høy'),
)


class AzureUserConsents(models.Model):
	userId = models.TextField(null=False)
	appId = models.TextField()
	scopes = models.TextField(null=False)
	userDisplayName = models.TextField()
	appDisplayName = models.TextField(null=False)

	def __str__(self):
		return f"{self.userId} {self.appDisplayName} {self.scopes}"
	class Meta:
		verbose_name_plural = "Azure: User Consents"


class AzureApplicationKeys(models.Model):
	applcaion_ref = models.ForeignKey(
			to="AzureApplication",
			related_name='keys',
			on_delete=models.CASCADE,
			null=False, blank=False,
			)
	key_id = models.CharField(
			max_length=200,
			null=False,
			blank=False,
			)
	display_name = models.CharField(
			max_length=400,
			null=True,
			blank=True,
			)
	key_type = models.CharField(
			max_length=200,
			null=True,
			blank=True,
			)
	key_usage = models.CharField(
			max_length=200,
			null=True,
			blank=True,
			)
	end_date_time = models.DateTimeField(
			null=False,
			blank=True,
			)
	hint = models.CharField(
			max_length=30,
			null=True,
			blank=True,
			)
	unique_together = ('applcaion_ref', 'key_id')

	def __str__(self):
		return u'%s' % (self.display_name)

	class Meta:
		verbose_name_plural = "Azure: Application keys"
		default_permissions = ('add', 'change', 'delete', 'view')

	def expire(self):
		from django.utils import timezone
		return timezone.now() > self.end_date_time

	def expire_soon(self):
		if self.expire():
			return False
		from django.utils import timezone
		from datetime import timedelta
		return (timezone.now() + timedelta(45)) > self.end_date_time


class AzureApplication(models.Model):
	opprettet = models.DateTimeField(
		verbose_name="Opprettet",
		auto_now_add=True,
		null=True,
		)
	active = models.BooleanField(
		default=True,
		)
	sist_oppdatert = models.DateTimeField(
		verbose_name="Sist oppdatert",
		auto_now=True,
		)
	appId = models.CharField(
		# Delegated or Application permission
		max_length=40,
		null=False,
		unique=True,
		)
	createdDateTime = models.DateTimeField(
		null=True,
		blank=True,
		)
	displayName = models.CharField(
		# Delegated or Application permission
		max_length=200,
		null=True,
		blank=True,
		)
	requiredResourceAccess = models.ManyToManyField(
		to="AzurePublishedPermissionScopes",
		related_name='azure_applications',
		verbose_name="Rettigheter",
		blank=True,
		)
	vurdering = models.TextField(
		verbose_name="Tekstlig vurdering",
		null=True,
		blank=True,
		help_text=u"Beholdes ved synkronisering mot Azure som skjer hver natt",
		)
	risikonivaa = models.IntegerField(choices=RISIKO_VALG,
		verbose_name="UTFASET Vurdering av risiko",
		default=0,
		blank=False,
		null=False,
		help_text=u"Beholdes ved synkronisering mot Azure som skjer hver natt",
		)
	homepageUrl = models.TextField(null=True)
	servicePrincipalType = models.CharField(max_length=100,null=True, blank=True)
	tags = models.TextField(null=True)
	#applicationVisibility = models.CharField(max_length=25, null=True, blank=True)
	#isAppProxy = models.BooleanField(null=True)
	notes = models.TextField(null=True)
	from_applications = models.BooleanField(default=False)
	publisherName = models.CharField(max_length=300, null=True, blank=True)


	def __str__(self):
		return u'%s' % (self.displayName)

	def antall_application_permissions(self):
		return AzurePublishedPermissionScopes.objects.filter(azure_applications=self.id).filter(permission_type="Application").count()

	def antall_permissions(self):
		return AzurePublishedPermissionScopes.objects.filter(azure_applications=self.id).count()

	def risikonivaa_autofill(self):
		risk_level = 0
		for perm in self.requiredResourceAccess.all():
			this_risk_level = perm.risk_level()
			if this_risk_level > risk_level:
				risk_level = this_risk_level
		if risk_level == 3:
			return "3 Høy (auto)"
		if risk_level == 2:
			return "2 Middels (auto)"
		return "1 Lav (auto)"

	def er_enterprise_app(self):
		if self.tags != None:
			if "WindowsAzureActiveDirectoryIntegratedApp" in self.tags:
				return True
		return False


	class Meta:
		verbose_name_plural = "Azure: Service Principals"
		default_permissions = ('add', 'change', 'delete', 'view')


class AzurePublishedPermissionScopes(models.Model):
	opprettet = models.DateTimeField(
		verbose_name="Opprettet",
		auto_now_add=True,
		null=True,
		)
	sist_oppdatert = models.DateTimeField(
		verbose_name="Sist oppdatert",
		auto_now=True,
		)
	permission_type = models.CharField(
		# Delegated or Application permission
		max_length=20,
		null=True,
		)
	scope_id = models.CharField(
		max_length=40,
		null=False,
		unique=True,
		)
	isEnabled = models.BooleanField(
		null=True,
		)
	value = models.CharField(
		max_length=200,
		null=True,
		)
	grant_type = models.TextField(
		# ment å holde en liste (array)
		# for å oppbevare permissionScope["type"] eller role["allowedMemberTypes"]
		null=True, # resourceSpecificApplicationPermissions har ikke denne
		)
	adminConsentDescription = models.TextField(
		null=True,
		)
	adminConsentDisplayName = models.TextField(
		null=True,
		)
	userConsentDescription = models.TextField(
		null=True,
		)
	userConsentDisplayName = models.TextField(
		null=True,
		)
	resourceAppId = models.CharField(
		max_length=40,
		null=True,
		)
	resourceAppStr = models.CharField(
		max_length=200,
		null=True,
		)

	def __str__(self):
		return u'%s' % (self.value)

	def application_rights(self):
		if self.permission_type == "Application":
			return True
		return False


	def warning_permission(self):
		if "User.Read.All" in self.value:
			return False
		if "Sites.Selected" in self.value:
			return False
		if "Score.Read.All" in self.value:
			return False
		if "Place.Read.All" in self.value:
			return False
		if "AdministrativeUnit.Read.All" in self.value:
			return False
		if "Policy.Read.All" in self.value:
			return False
		if "Group.Read.All" in self.value:
			return False

		if self.permission_type == "Application":
			return True
		#if "full access" in self.adminConsentDisplayName:
		#	return True
		#if "ReadWrite.All" in self.value:
		#	return True
		#if "Mail.ReadWrite" in self.value:
		#	return True
		return False # default

	def safe_permission(self):
		if "Sign in" in self.adminConsentDisplayName:
			return True
		if "View users' email" in self.adminConsentDisplayName:
			return True
		if "basic profiles" in self.adminConsentDisplayName:
			return True
		if "openid" in self.value:
			return True
		if "profile" in self.value:
			return True
		if "GroupMember.Read.All" in self.value:
			return True
		if "MailboxSettings.Read" in self.value:
			return True
		return False
		# "Access selected site collections"

	def risk_level(self):
		if self.safe_permission():
			return 1 # low
		if self.warning_permission():
			return 3 # high
		return 2 # medium

	def risk_color(self):
		if self.safe_permission():
			return "#00b92a" # low
		if self.warning_permission():
			return "#dc3545" # high
		return "#bd8e00" # medium


	class Meta:
		verbose_name_plural = "Azure: Permission scopes"
		default_permissions = ('add', 'change', 'delete', 'view')





class UBWRapporteringsenhet(models.Model):
	users = models.ManyToManyField(
		to=User,
		related_name='okonomi_rapporteringsenhet_users',
		verbose_name="Tilgang for",
		help_text=u"Personer med tilgang til å se alle data for enheten",
		)
	name = models.CharField(
		verbose_name="Navn på enhet",
		max_length=150,
		blank=False,
		null=False,
		help_text=u"",
		)
	api_key = models.CharField(
		verbose_name="Nøkkel / passord",
		max_length=256,
		blank=True,
		null=True,
		)

	def __str__(self):
		return u'%s' % (self.name)

	class Meta:
		verbose_name_plural = "UBW: rapporteringsenheter"
		default_permissions = ('add', 'change', 'delete', 'view')


class UBWFakturaKategori(models.Model):
	name = models.CharField(
		verbose_name="Kategorinavn",
		max_length=50,
		blank=False, null=False,
		help_text=u"",
		)
	belongs_to = models.ForeignKey(
		to="UBWRapporteringsenhet",
		on_delete=models.PROTECT,
		verbose_name="Tilhører",
		null=False, blank=False,
		)
	def __str__(self):
		return u'%s' % (self.name)
	class Meta:
		verbose_name_plural = "UBW: fakturakategorier"
		default_permissions = ('add', 'change', 'delete', 'view')


class UBWEnhetForm(forms.ModelForm):
	class Meta:
		model = UBWRapporteringsenhet
		exclude = ('users',)


class UBWFakturaKategoriForm(forms.ModelForm):
	class Meta:
		model = UBWFakturaKategori
		exclude = ('belongs_to',)


class UBWMetode(models.Model):
	name = models.CharField(
		verbose_name="Navn på enhet",
		max_length=150,
		blank=False,
		null=False,
		help_text=u"",
		)
	belongs_to = models.ForeignKey(
		to="UBWRapporteringsenhet",
		on_delete=models.CASCADE,
		verbose_name="Tilhører",
		null=False,
		blank=False,
		)
	def __str__(self):
		return u'%s' % (self.name)
	class Meta:
		verbose_name_plural = "UBW: metoder"
		default_permissions = ('add', 'change', 'delete', 'view')



class UBWFaktura(models.Model):
	belongs_to = models.ForeignKey(
		to="UBWRapporteringsenhet",
		on_delete=models.CASCADE,
		verbose_name="Tilhører",
		null=False,
		blank=False,
		)
	ubw_tab = models.CharField(
		verbose_name="UBW tab",
		null=True,
		blank=True,
		max_length=100,
		)
	ubw_account = models.IntegerField(
		verbose_name="UBW Kontonr",
		null=True,
		blank=True,
		)
	ubw_xaccount = models.CharField(
		verbose_name="UBW Kontonavn",
		null=True,
		blank=True,
		max_length=200,
		)
	ubw_period = models.IntegerField(
		verbose_name="UBW-periode (YYYYmm)",
		null=True,
		blank=True,
		)
	ubw_dim_1 = models.IntegerField(
		verbose_name="UBW Koststednr",
		null=True,
		blank=True,
		)
	ubw_xdim_1 = models.CharField(
		verbose_name="Koststednavn",
		null=True,
		blank=True,
		max_length=300,
		)
	ubw_dim_4 = models.IntegerField(
		verbose_name="UBW prosjektnr",
		null=True,
		blank=True,
		)
	ubw_xdim_4 = models.CharField(
		verbose_name="UBW prosjektnavn",
		null=True,
		blank=True,
		max_length=200,
		)
	ubw_voucher_type = models.CharField(
		verbose_name="UBW voucher_type",
		null=True,
		blank=True,
		max_length=10,
		)
	ubw_voucher_no = models.IntegerField(
		verbose_name="UBW voucher_no",
		null=True,
		blank=True,
		)
	ubw_sequence_no	= models.IntegerField(
		verbose_name="UBW sequence_no",
		null=True,
		blank=True,
		)
	ubw_voucher_date = models.DateField(
		verbose_name="UBW bilagsdato",
		null=True,
		blank=True,
		)
	ubw_order_id = models.IntegerField(
		verbose_name="UBW order_id",
		null=True,
		blank=True,
		)
	ubw_apar_id	= models.IntegerField(
		verbose_name="UBW leverandørnr",
		null=True,
		blank=True,
		)
	ubw_xapar_id = models.CharField(
		verbose_name="UBW leverandørnavn",
		null=True,
		blank=True,
		max_length=200,
		)
	ubw_description = models.TextField(
		verbose_name="UBW beskrivelse",
		null=True,
		blank=True,
		)
	ubw_amount = models.DecimalField(
		verbose_name="UBW beløp",
		max_digits=20, #10^(20-2), bør holde en stund..
		decimal_places=2,
		null=True,
		blank=True,
		)
	ubw_apar_type = models.CharField(
		verbose_name="UBW apar_type",
		null=True,
		blank=True,
		max_length=10,
		)
	ubw_att_1_id = models.CharField(
		verbose_name="UBW att_1_id",
		null=True,
		blank=True,
		max_length=10,
		)
	ubw_att_4_id = models.CharField(
		verbose_name="UBW att_4_id",
		null=True,
		blank=True,
		max_length=10,
		)
	ubw_client = models.IntegerField(
		verbose_name="UBW Virksomhets-ID",
		null=True,
		blank=True,
		)
	ubw_last_update = models.DateField(
		verbose_name="UBW sist oppdatert",
		null=True,
		blank=True,
		)
	ubw_artsgr2 = models.CharField(
		verbose_name="UWB Artsgruppe",
		null=True,
		blank=True,
		max_length=5,
		)
	ubw_artsgr2_text = models.CharField(
		verbose_name="UWB Artsgruppe (tekst)",
		null=True,
		blank=True,
		max_length=300,
		)
	ubw_kategori = models.IntegerField(
		verbose_name="UWB Kategori",
		null=True,
		blank=True,
		)
	ubw_kategori_text = models.CharField(
		verbose_name="UWB Kategori (tekst)",
		null=True,
		blank=True,
		max_length=300,
		)
	#history = HistoricalRecords()
	unique_together = ('ubw_voucher_no', 'ubw_sequence_no')

	def ubw_tab_repr(self):
		oppslag = {
			"A": "Ikke bokført",
			"B": "Bokført",
			"C": "Historisk hovedbok",
		}
		try:
			return oppslag[self.ubw_tab]
		except:
			return self.ubw_tab

	def __str__(self):
		return u'%s-%s (%s %s)' % (self.ubw_voucher_no, self.ubw_sequence_no, self.ubw_amount, self.ubw_description)

	class Meta:
		verbose_name_plural = "UBW: faktura"
		default_permissions = ('add', 'change', 'delete', 'view')


class UBWMetadata(models.Model):
	belongs_to = models.OneToOneField(
		to="UBWFaktura",
		on_delete=models.CASCADE,
		related_name='metadata_reference',
		verbose_name="Tilhører faktura",
		null=False,
		blank=False,
		)
	periode_paalopt = models.DateField(
		verbose_name="Faktisk periode påløpt (yyyy-mm-dd)",
		null=False,
		blank=False,
		)
	budsjett_amount = models.DecimalField(
		verbose_name="Budsjettert beløp",
		max_digits=20, #10^(20-2), bør holde en stund..
		decimal_places=2,
		null=True,
		blank=True,
		)
	kategori = models.ForeignKey(
		to="UBWFakturaKategori",
		related_name="kategori",
		on_delete=models.PROTECT,
		verbose_name="Kategori 1",
		null=True,
		blank=True,
		)
	ekstra_kategori = models.ForeignKey(
		to="UBWFakturaKategori",
		related_name="ekstra_kategori",
		on_delete=models.PROTECT,
		verbose_name="Kategori 2",
		null=True,
		blank=True,
		)
	leverandor = models.CharField(
		verbose_name="Leverandør",
		null=True,
		blank=True,
		max_length=200,
		)
	kommentar = models.CharField(
		verbose_name="Kommentar",
		null=True,
		blank=True,
		max_length=256,
		)

	#history = HistoricalRecords()

	def __str__(self):
		return u'UBWMetadata %s %s %s' % (self.pk, self.belongs_to, self.kategori)

	class Meta:
		verbose_name_plural = "UBW: fakturametadata"
		default_permissions = ('add', 'change', 'delete', 'view')



def modify_formfields(form):
	formfield = form.formfield()
	if isinstance(form, models.DateField):
		formfield.widget.format = '%Y-%m-%d'
		formfield.widget.attrs.update({'class': 'datepicker'})

	return formfield


#https://stackoverflow.com/questions/24783275/django-form-with-choices-but-also-with-freetext-option
class ListTextWidget(forms.TextInput):
	def __init__(self, data_list, name, *args, **kwargs):
		super(ListTextWidget, self).__init__(*args, **kwargs)
		self._name = name
		self._list = data_list
		self.attrs.update({'list':'list__%s' % self._name})

	def render(self, name, value, attrs=None, renderer=None):
		text_html = super(ListTextWidget, self).render(name, value, attrs=attrs)
		data_list = '<datalist id="list__%s">' % self._name
		for item in self._list:
			if item[0]: # sjekk i tilfelle den er None
				data_list += '<option value="%s">%s</option>' % (item[0], item[1])
		data_list += '</datalist>'

		return (text_html + data_list)


class UBWMetadataForm(forms.ModelForm):
	class Meta:
		model = UBWMetadata
		exclude = ('belongs_to',)

	#formfield_callback = modify_formfields

	def __init__(self, *args, **kwargs):
		_belongs_to = kwargs.pop('belongs_to', None)
		_data_list = kwargs.pop('data_list', None)
		super(UBWMetadataForm, self).__init__(*args, **kwargs)

		if _data_list:
			for dl in _data_list:
				self.fields[dl['field']].widget = ListTextWidget(data_list=dl['choices'], name=dl['field'])

		self.fields['kategori'].queryset = UBWFakturaKategori.objects.filter(belongs_to=_belongs_to)


class UBWEstimat(models.Model):
	belongs_to = models.ForeignKey(
		to="UBWRapporteringsenhet",
		on_delete=models.CASCADE,
		verbose_name="Tilhører",
		null=False,
		blank=False,
		)
	aktiv = models.BooleanField(
		verbose_name="Aktiv?",
		default=True,
		)
	prognose_kategori = models.CharField(
		verbose_name="Prognosekategori",
		max_length=50,
		null=False,
		blank=False,
		)
	ubw_description = models.TextField(
		verbose_name="UBW beskrivelse",
		null=True,
		blank=True,
		)
	estimat_account = models.IntegerField(
		verbose_name="Estimat Kontonr",
		null=True,
		blank=True,
		)
	estimat_dim_1 = models.IntegerField(
		verbose_name="Estimat Koststednr",
		null=True,
		blank=True,
		)
	estimat_dim_4 = models.IntegerField(
		verbose_name="Estimat Prosjektnr",
		null=True,
		blank=True,
		)
	estimat_amount = models.DecimalField(
		verbose_name="Estimat beløp",
		max_digits=20, #10^(20-2), bør holde en stund..
		decimal_places=2,
		null=True,
		blank=True,
		)
	budsjett_amount = models.DecimalField(
		verbose_name="Budsjettert beløp",
		max_digits=20, #10^(20-2), bør holde en stund..
		decimal_places=2,
		null=True,
		blank=True,
		)
	periode_paalopt = models.DateField(
		verbose_name="Faktisk periode påløpt (yyyy-mm-dd)",
		null=False,
		blank=False,
		)
	kategori = models.ForeignKey(
		to="UBWFakturaKategori",
		related_name="estimat_kategori",
		on_delete=models.PROTECT,
		verbose_name="Kategori 1",
		null=True,
		blank=True,
		)
	ekstra_kategori = models.ForeignKey(
		to="UBWFakturaKategori",
		related_name="estimat_ekstra_kategori",
		on_delete=models.PROTECT,
		verbose_name="Kategori 2",
		null=True,
		blank=True,
		)
	leverandor = models.CharField(
		verbose_name="Leverandør",
		null=True, blank=True,
		max_length=200,
		)
	kommentar = models.CharField(
		verbose_name="Kommentar",
		null=True,
		blank=True,
		max_length=256,
		)
	ubw_artsgr2 = models.CharField(
		verbose_name="UWB Artsgruppe",
		null=True,
		blank=True,
		max_length=5,
		)
	ubw_kategori = models.IntegerField(
		verbose_name="UBW Kategori",
		null=True,
		blank=True,
		)

	def ubw_artsgr2_display(self):
		return UBWFaktura.objects.filter(belongs_to=self.belongs_to).filter(ubw_artsgr2=self.ubw_artsgr2)[:1].get().ubw_artsgr2_text

	def ubw_kategori_display(self):
		return UBWFaktura.objects.filter(belongs_to=self.belongs_to).filter(ubw_kategori=self.ubw_kategori)[:1].get().ubw_kategori_text

	def __str__(self):
		return u'%s' % (self.pk)

	class Meta:
		verbose_name_plural = "UBW: estimater"
		default_permissions = ('add', 'change', 'delete', 'view')


class UBWEstimatForm(forms.ModelForm):
	class Meta:
		model = UBWEstimat
		exclude = ('belongs_to',)
		widgets = {
			'ubw_description': forms.Textarea(attrs={'cols': 10, 'rows': 2}),
			'estimat_amount': forms.TextInput(),
			'budsjett_amount': forms.TextInput(),
		}

	def __init__(self, *args, **kwargs):
		_data_list = kwargs.pop('data_list', None)
		_belongs_to = kwargs.pop('belongs_to', None)
		super(UBWEstimatForm, self).__init__(*args, **kwargs)

		if _data_list:
			for dl in _data_list:
				self.fields[dl['field']].widget = ListTextWidget(data_list=dl['choices'], name=dl['field'])

		self.fields['kategori'].queryset = UBWFakturaKategori.objects.filter(belongs_to=_belongs_to)


class LOS(models.Model):
	sist_oppdatert = models.DateTimeField(
		verbose_name="Sist oppdatert",
		auto_now=True,
		)
	unik_id = models.URLField(
		verbose_name="Unik URL",
		max_length=300,
		blank=False,
		null=False,
		)
	verdi = models.CharField(
		verbose_name="Verdi",
		null=False,
		blank=False,
		max_length=300,
		)
	kategori_ref = models.ForeignKey(
		to="LOS",
		related_name='kategori',
		verbose_name="ConceptScheme",
		blank=True,
		null=True,
		on_delete=models.SET_NULL,
		)
	parent_id = models.ManyToManyField(
		to="LOS",
		related_name='children',
		verbose_name="Overordnet ord/tema",
		)
	active = models.BooleanField(
		verbose_name="I LOS?",
		default=True,
		)
	buffer_alle_tema = models.ManyToManyField(
		to="LOS",
		related_name='alle_tema_buffer',
		verbose_name="Alle tema (buffer)",
		)

	def __str__(self):
		if self.active:
			return u'%s (%s)' % (self.verdi, self.kategori_tekst())
		else:
			return u'%s (utfaset)' % (self.verdi)


	def er_tema(self):
		if self.kategori_ref:
			if self.kategori_ref.verdi == "Tema":
				return True
		return False


	def er_hovedtema(self):
		if self.kategori_ref.verdi == "Tema" and len(self.parent_id.all()) == 0:
			return True
		return False

	def kategori_tekst(self):
		if not self.er_tema(): # Ord
			return "Ord"
		if self.er_hovedtema():
			return "Hovedtema" # hovedtema
		return "Undertema" # undertema


	def color(self):
		if not self.er_tema(): # Ord
			return "#d9d7d7"
		if self.er_hovedtema():
			return "#343a40" # hovedtema
		return "#007bff" # undertema



	def badge(self):
		if not self.er_tema(): # Ord
			return "badge-light"
		if self.er_hovedtema():
			return "badge-dark" # hovedtema
		return "badge-primary" # undertema


	def alle_tema(self):
		if len(self.buffer_alle_tema.all()) > 0:
			return self.buffer_alle_tema.all()

		alle_tema = set()
		stack = []
		stack.extend(self.parent_id.all())
		while len(stack) > 0:
			item = stack.pop()
			#print(item)
			stack.extend(item.parent_id.all())
			if item.er_tema():
				alle_tema.add(item)

		for tema in alle_tema:
			self.buffer_alle_tema.add(tema)

		return self.buffer_alle_tema.all()


	def hovedtema(self):
		hovedtema = set()
		alle_tema = self.alle_tema()
		for tema in alle_tema:
			if tema.er_hovedtema():
				hovedtema.add(tema)
		return hovedtema

	def undertema(self):
		undertema = set()
		alle_tema = self.alle_tema()
		#print(alle_tema)
		for tema in alle_tema:
			if not tema.er_hovedtema():
				undertema.add(tema)
		return undertema


	class Meta:
		verbose_name_plural = "Systemkategori: LOS fellesbegreper"
		verbose_name = "LOS-begrep"
		default_permissions = ('add', 'change', 'delete', 'view')


class ExploitedVulnerability(models.Model):
	# Model to keep track of exploited vulnerabilities (CISA)
	cve_id = models.CharField(max_length=20, primary_key=True)
	vendor_project = models.CharField(max_length=255)
	product = models.CharField(max_length=255)
	vulnerability_name = models.CharField(max_length=255)
	date_added = models.DateField()
	short_description = models.TextField()
	required_action = models.TextField()
	due_date = models.DateField()
	known_ransomware_campaign_use = models.CharField(max_length=255)

	def __str__(self):
		return self.cve_id



class Nettverksgruppe(models.Model):
	name =models.CharField(
		verbose_name="Navn",
		null=False,
		blank=False,
		max_length=250,
		)
	members = models.TextField(
		verbose_name="Medlemmer (JSON)",
		blank=False,
		null=False,
		)

	def __str__(self):
		return u'%s' % (self.name)

	class Meta:
		verbose_name_plural = "CMDB: Navngitte nettverksalias"
		default_permissions = ('add', 'change', 'delete', 'view')

class Brannmurregel(models.Model):
	regel_id = models.CharField(
		verbose_name="Regel ID",
		null=False,
		blank=False,
		max_length=50,
		)
	brannmur = models.CharField(
		verbose_name="Virtuell brannmur",
		null=False,
		blank=False,
		max_length=50,
		)
	active = models.BooleanField(
		verbose_name="Regel aktiv?",
		blank=False,
		null=False,
		default=False,
		)
	permit = models.BooleanField(
		verbose_name="Tillat trafikk?",
		blank=False,
		null=False,
		default=False,
		)
	source = models.TextField(
		verbose_name="Kilde (JSON)",
		blank=False,
		null=False,
		)
	destination = models.TextField(
		verbose_name="Destinasjon (JSON)",
		blank=False,
		null=False,
		)
	protocol =  models.TextField(
		verbose_name="Port/protokoll (JSON)",
		blank=False,
		null=False,
		)
	comment =  models.TextField(
		verbose_name="Kommentar",
		blank=True,
		null=True,
		)
	ref_vip = models.ManyToManyField(
		to="virtualIP",
		related_name='firewall_rules',
		verbose_name="Tilknyttede VIP-er",
		)
	ref_server = models.ManyToManyField(
		to="CMDBdevice",
		related_name='firewall_rules',
		verbose_name="Tilknyttede servere",
		)
	ref_vlan = models.ManyToManyField(
		to="NetworkContainer",
		related_name='firewall_rules',
		verbose_name="Tilknyttede VLAN",
		)

	def __str__(self):
		return u'%s' % (self.regel_id)

	class Meta:
		verbose_name_plural = "CMDB: Brannmurregler"
		default_permissions = ('add', 'change', 'delete', 'view')

	def source_items(self):
		return json.loads(self.source)

	def destination_items(self):
		return json.loads(self.destination)

	def protocol_items(self):
		return json.loads(self.protocol)

