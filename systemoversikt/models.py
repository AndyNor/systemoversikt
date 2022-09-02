# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from simple_history.models import HistoricalRecords
from django import forms
import json
import re


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
	(2, "🟢 Klargjort via Citrix"),
	(3, "🟢 Skytjeneste med Azure AD-pålogging"),
	(4, "🟢 Desktopapplikasjon uten avhengigheter, ferdig pakket"),
	(5, "🟡 Ikke klargjort, skal til Azure Web Application Proxy"),
	(9, "🟡 Ikke klargjort, skytjeneste som skal til Azure AD"),
	(6, "🟡 Ikke klargjort, skal til Citrix"),
	(7, "🟡 Ikke klargjort, skal kun pakkes som desktop applikasjon"),
	(8, "🔴 Ingen løsning klar enda"),
)


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
		verbose_name_plural = "System: brukerendringer"
		default_permissions = ('view')




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
		verbose_name_plural = "System: applikasjonslogger"
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
		verbose_name_plural = "Definisjoner: definisjonskontekster"
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
		verbose_name_plural = "Definisjoner: definisjoner"
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
			verbose_name="Organisatorisk tilhørighet / rolle (fases ut)",
			blank=True,
			null=True,
			help_text=u"Fritekst",
			)
	vil_motta_epost_varsler = models.BooleanField(
			verbose_name="Ønsker du å motta e-postvarsler?",
			default=False,
			help_text=u"",
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
		verbose_name_plural = "System: ansvarlige"
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
		verbose_name_plural = "System: autoriserte bestillere av sertifikater"
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
			help_text=u"Dette feltet brukes som standard visningsnavn.",
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
			verbose_name="Overordnede virksomheter",
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
	ansatte = models.IntegerField(
			verbose_name="Antall ansatte",
			blank=True,
			null=True,
			help_text=u"Her kan antall ansatte i virksomheten angis.",
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
			verbose_name='Vår IKT-hovedkontakt',
			blank=True,
			help_text=u"Virksomhetens kontaktpunkt for IKT.",
			)
	autoriserte_bestillere_tjenester = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_autoriserte_bestillere_tjenester',
			verbose_name='Autoriserte bestillere InfoTorg',
			blank=True,
			help_text=u"En autorisert bestiller InfoTorg er en person virksomheten har autorisert til å bestille brukere til data fra det sentrale folkeregistret.",
			)
	autoriserte_bestillere_tjenester_uke = models.ManyToManyField(
			to=Ansvarlig,
			related_name='virksomhet_autoriserte_bestillere_tjenester_uke',
			verbose_name='Autoriserte bestillere av tjenester fra intern tjenesteleverandør.',
			blank=True,
			help_text=u"En autorisert bestiller er en person virksomheten har autorisert til å bestille tjenester via den selvbetjeningsportalen (kundeportalen).",
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
			help_text=u"Fylles ut dersom virksomhetsleder har avgitt fullmakt for ustedelse av websertifikater og/eller virksomhetssertifikater.",
			)
	sertifikatfullmakt_avgitt_web = models.BooleanField(
			verbose_name="Avgitt fullmakt for websertifikater?",
			blank=True,
			null=True,
			default=False,
			help_text=u"Krysses av dersom virksomhet har avgitt fullmakt til driftsleverandør for utstedelse av websertifikater for sitt org.nummer.",
			)
	sertifikatfullmakt_avgitt_virksomhet = models.BooleanField(
			verbose_name="Avgitt fullmakt for virksomhetssertifikater?",
			blank=True,
			null=True,
			default=False,
			help_text=u"Krysses av dersom virksomhet har avgitt fullmakt til driftsleverandør for utstedelse av virksomhetssertifikater for sitt org.nummer.",
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
			verbose_name='Arkitekturkontakter i vår virksomhet',
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

	def antall_klienter(self):
		from django.db.models import Q
		#return CMDBdevice.objects.filter(maskinadm_virksomhet=self).filter(~(Q(maskinadm_status__in=["UTMELDT", "SLETTET"]) and Q(landesk_login=None))).count()
		return CMDBdevice.objects.filter(maskinadm_virksomhet=self).filter(device_active=True).count()

	def __str__(self):
		return u'%s (%s)' % (self.virksomhetsnavn, self.virksomhetsforkortelse)

	class Meta:
		verbose_name_plural = "Virksomheter: virksomheter"
		default_permissions = ('add', 'change', 'delete', 'view')

"""
class ADUser(models.Model):
	sAMAccountName = models.CharField(
			verbose_name="sAMAccountName",
			max_length=100,
			blank=True, null=True,
			help_text=u"importert",
			)
	distinguishedname = models.TextField(
			verbose_name="distinguishedname",
			unique=True,
			help_text=u"importert",
			)
	userAccountControl = models.TextField(
			verbose_name="userAccountControl",
			blank=True, null=True,
			help_text=u"importert",
			)
	description = models.TextField(
			verbose_name="description",
			blank=True, null=True,
			help_text=u"importert",
			)
	displayName = models.CharField(
			verbose_name="displayName",
			max_length=300,
			blank=True, null=True,
			help_text=u"importert",
			)
	etternavn = models.CharField(
			verbose_name="etternavn",
			max_length=100,
			blank=True, null=True,
			help_text=u"importert",
			)
	fornavn = models.CharField(
			verbose_name="fornavn",
			max_length=100,
			blank=True, null=True,
			help_text=u"importert",
			)
	lastLogonTimestamp = models.DateTimeField(
			verbose_name="lastLogonTimestamp",
			null=True, blank=True,
			help_text=u"importert",
			)
	from_prk = models.BooleanField(
			verbose_name="Bruker fra PRK?",
			default=False,
			help_text="Importeres",
			)
	# med vilje er det ikke HistoricalRecords() på denne

	def __str__(self):
		return u'%s' % (self.sAMAccountName)

	class Meta:
		verbose_name_plural = "AD brukere (utenfor PRK)"
"""

class Profile(models.Model): # brukes for å knytte innlogget bruker med tilhørende virksomhet. Vurderer å fjerne denne.
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
	# med vilje er det ikke HistoricalRecords() på denne

	def __str__(self):
		return u'%s' % (self.user)

	class Meta:
		verbose_name_plural = "System: brukerprofiler"

	@receiver(post_save, sender=User)
	def create_user_profile(sender, instance, created, **kwargs):
		if created:
			Profile.objects.create(user=instance)

	@receiver(post_save, sender=User)
	def save_user_profile(sender, instance, **kwargs):
		instance.profile.save()

	def kopiav(self):
		if self.user.username.startswith("t-"):
			try:
				username = self.user.username.replace("t-","")
				return User.objects.get(username=username)
			except:
				pass
		return "Ukjent"

	def org_tilhorighet(self):
		try:
			enhet = self.org_unit
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
	def ou_lesbar(self):
		#if self.ou:
		#	try:
		#		return self.ou.distinguishedname.split(",")[1:-4]
		#	except:
		#		return self.ou.distinguishedname
		return self.distinguishedname.split(",")[1:-4]

"""
class Klientutstyr(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	maskinadm_wsnummer = models.CharField(
			verbose_name="WS-nummer",
			max_length=20,
			blank=True,
			null=True,
			)
	maskinadm_virksomhet = models.ForeignKey(
			to="Virksomhet",
			on_delete=models.SET_NULL,
			verbose_name="Tilhører virksomhet",
			related_name='klientutstyr_virksomhet',
			null=True,
			blank=True,
			)
	maskinadm_virksomhet_str = models.CharField(
			verbose_name="Virksomhet (tekst)",
			max_length=30,
			blank=True,
			null=True,
			)
	maskinadm_klienttype = models.CharField(
			verbose_name="Klienttype",
			max_length=12,
			blank=True,
			null=True,
			)
	maskinadm_sone = models.CharField(
			verbose_name="Sikkerhetssone",
			max_length=6,
			blank=True,
			null=True,
			)
	maskinadm_servicenivaa = models.CharField(
			verbose_name="Servicenivå",
			max_length=2,
			blank=True,
			null=True,
			)
	maskinadm_sist_oppdatert = models.DateTimeField(
			verbose_name="Maskinadm: sist_oppdatert",
			null=True,
			)

	def __str__(self):
		return u'%s' % (self.maskinadm_wsnummer)

	class Meta:
		verbose_name_plural = "PRK: klientutstyr"
		default_permissions = ('add', 'change', 'delete', 'view')
"""

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
		verbose_name_plural = "Leverandører: leverandører"
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
		verbose_name_plural = "Behandling: informasjonsklasser"
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
		verbose_name_plural = "Systemoversikt: systemkategorier"
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
		verbose_name_plural = "Systemoversikt: systemhovedkategorier"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['hovedkategorinavn']



MAALGRUPPE_VALG = (
	(1, 'Innbyggere'),
	(2, 'Ansatte'),
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

	def own_domain(self):
		# hardkodet her
		if "oslo.kommune.no" in self.domene:
			return True
		else:
			return False

	class Meta:
		verbose_name_plural = "Domener: URL-er"
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
		verbose_name_plural = "Behandling: personopplysningskategorier"
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
		verbose_name_plural = "Behandling: kategorier registrerte"
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
		verbose_name_plural = "Behandling: behandlingsgrunnlag"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['grunnlag']



CMDB_KRITIKALITET_VALG = (
	(1, '1 most critical (24/7/365)'),
	(2, '2 somewhat critical (07-20 alle dager)'),
	(3, '3 less critical (07-16 virkedager)'),
	(4, '4 not critical (best effort)'),
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

# dette er nye business service. Kobles mot System
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
	systemreferanse = models.OneToOneField(
			to="System",
			related_name="bs_system_referanse",
			verbose_name="Tilhørende system",
			blank=True,
			null=True,
			on_delete=models.SET_NULL,
			help_text=u"Settes av UKE IKT-plattformforvaltning",
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

	class Meta:
		verbose_name_plural = "CMDB: business services"
		verbose_name = "business service"
		default_permissions = ('add', 'change', 'delete', 'view')


# dette er business sub services. Kobles mot servere og databaser (endrer ikke navn nå)
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

	#hva brukes denne til? (ser ikke ut til å være i bruk lenger, til fordel for "operational_status")
	#aktiv = models.NullBooleanField(
	#		verbose_name="Er dette CMDB-innslaget fortsatt gyldig?",
	#		blank=True, null=True,
	#		help_text=u"Ja eller nei",
	#		)
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


	def u_service_availability_text(self):
		lookup = {
			"T1": "T1: 24/7/365, 99.9%",
			"T2": "T2: 07-20 alle dager, 99.5%",
			"T3": "T3: 07-16 virkedager, 99%",
			"T4": "T4: Best effort",
		}
		try:
			return lookup[self.u_service_availability]
		except:
			return self.u_service_availability


	def u_service_operation_factor_text(self):
		lookup = {
			"D1": "D1: Liv og helse",
			"D2": "D2: Virksomhetskritisk",
			"D3": "D3: Kritisk",
			"D4": "D4: Periodisk kritisk",
			"D5": "D5: Ikke kritisk",
		}
		try:
			return lookup[self.u_service_operation_factor]
		except:
			return self.u_service_operation_factor


	def u_service_complexity_text(self):
		lookup = {
			"K1": "K1: 0-100 brukere, enkelt omfang",
			"K2": "K2: 0-100 brukere, middels omfang",
			"K3": "K3: 0-100 brukere, høyt omfang",
			"K4": "K4: 100-1000 brukere, enkelt omfang",
			"K5": "K5: 100-1000 brukere, middels omfang",
			"K6": "K6: 100-1000 brukere, høyt omfang",
			"K7": "K7: 1000+ brukere, enkelt omfang",
			"K8": "K8: 1000+ brukere, middels omfang",
			"K9": "K9: 1000+ brukere, høyt omfang",
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

	#def system_mangler(self):
	#	if self.cmdb_type == 1 and self.system_cmdbref.count() < 1:
	#		return True
	#	else:
	#		return False

	def er_ukjent(self):
		if self.cmdb_type == 2:
			return True
		else:
			return False

	def ant_devices(self):
		return CMDBdevice.objects.filter(sub_name=self.pk, device_active=True).count()

	def ant_databaser(self):
		return CMDBdatabase.objects.filter(sub_name=self.pk, db_operational_status=True).count()

	def is_bss(self):
		if self.service_classification == "Business Service":
			return True
		else:
			return False

	class Meta:
		verbose_name_plural = "CMDB: business sub services"
		verbose_name = "sub service"
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
		verbose_name_plural = "CMDB: VIP-er"
		verbose_name = "VIP"
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
		verbose_name_plural = "CMDB: Network containers"
		verbose_name = "Network container"
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
	networkdevices = models.ManyToManyField(
		to='NetworkDevice',
		verbose_name="Kobling til nettverksenheter",
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




class DNSrecord(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	dns_name = models.CharField(
			max_length=500,
			unique=True,
			verbose_name="DNS name",
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
			max_length=50,
			null=True,
			verbose_name="DNS target (hvis CNAME)",
			)
	dns_domain = models.CharField(
			max_length=200,
			null=False,
			verbose_name="Domain",
			)

	def __str__(self):
		return u'%s: %s' % (self.dns_type, self.dns_name)

	def dns_full_name(self):
		return u'%s.%s' % (self.dns_name, self.dns_domain)

	class Meta:
		verbose_name_plural = "CMDB: DNS records"
		verbose_name = "DNS-record"
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
			verbose_name="db_status",
			blank=True,
			null=True,
			help_text=u"Importert: db_status",
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
		verbose_name_plural = "CMDB: databaser"
		verbose_name = "database"
		default_permissions = ('add', 'change', 'delete', 'view')


class NetworkDevice(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	name = models.CharField(
			max_length=200,
			unique=True,
			verbose_name="Enhetsnavn",
			)
	ip_address = models.GenericIPAddressField(
			null=False,
			verbose_name="IP-adresse",
			)
	model = models.CharField(
			max_length=200,
			null=True,
			verbose_name="Modell",
			)
	firmware = models.CharField(
			max_length=200,
			null=True,
			verbose_name="Firmware",
			)


class CMDBdevice(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	device_type = models.CharField(
			max_length=50,
			blank=False,
			null=True,
			verbose_name="Enhetstype",
			help_text="Settes automatisk ved import",
			)
	device_active = models.BooleanField(
			verbose_name="Aktiv",
			default=False, # dersom PRK-import oppretter enheter, skal de likevel ikke anses som aktive. Bare ekstra informasjon. Må eksplisitt settes til True
			help_text=u"",
			)
	model_id = models.CharField(
			verbose_name="Klientmodell",
			max_length=200,
			blank=True,
			null=True,
			)
	sist_sett = models.DateTimeField(
			verbose_name="Sist sett",
			null=True,
			blank=True,
			)
	last_loggedin_user = models.ForeignKey(
			to=User,
			on_delete=models.SET_NULL,
			related_name='client',
			verbose_name="Sist innloggede bruker",
			null=True,
			blank=True,
			)
	billable = models.BooleanField(
			verbose_name="Billable",
			default=False,
			)
	comp_name = models.CharField(
			unique=True,
			verbose_name="Computer name",
			max_length=600,
			blank=False,
			null=False,
			help_text=u"",
			db_index=True,
			)
	""" vi importerer bare sub service-nivået.
	bs_name = models.CharField( # foreign key
			verbose_name="Business Service",
			max_length=600,
			blank=True, null=True,
			help_text=u"",
			)
	"""
	comp_disk_space = models.IntegerField(  # lagres i antall GB
			verbose_name="Lagring",
			blank=True,
			null=True,
			help_text=u"",
			)
	#bs_u_service_portfolio = models.CharField(  # samme som "sub_u_service_portfolio"
	#		verbose_name="Business portfolio",
	#		max_length=600,
	#		blank=True, null=True,
	#		help_text=u"",
	#		)
	sub_name = models.ForeignKey(
			to=CMDBRef,
			related_name='cmdbdevice_sub_name',
			verbose_name="Business Sub Service",
			on_delete=models.CASCADE,
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_ip_address = models.CharField(
			verbose_name="IP-address",
			max_length=100,
			blank=True,
			null=True,
			help_text=u"",
			)
	comp_cpu_speed = models.IntegerField(
			verbose_name="CPU-hastighet (MHz?)",
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
	#comp_cpu_count = models.IntegerField(
	#		verbose_name="CPU count",
	#		blank=True,
	#		null=True,
	#		help_text=u"",
	#		)
	#comp_cpu_name = models.CharField(
	#		verbose_name="CPU name",
	#		max_length=200,
	#		blank=True,
	#		null=True,
	#		help_text=u"",
	#		)
	#comp_u_cpu_total = models.IntegerField(
	#		verbose_name="CPU total",
	#		blank=True,
	#		null=True,
	#		help_text=u"",
	#		)
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
	#comp_sys_id = models.CharField(
	#		verbose_name="Computer ID",
	#		max_length=200,
	#		blank=True,
	#		null=True,
	#		help_text=u"",
	#		)
	#dns = models.CharField(
	#		verbose_name="DNS",
	#		max_length=200,
	#		blank=True,
	#		null=True,
	#		help_text=u"",
	#		)
	#vlan = models.CharField(
	#		verbose_name="VLAN",
	#		max_length=200,
	#		blank=True,
	#		null=True,
	#		help_text=u"",
	#		)
	#nat = models.CharField(
	#		verbose_name="NAT",
	#		max_length=200,
	#		blank=True,
	#		null=True,
	#		help_text=u"",
	#		)
	#vip = models.CharField(
	#		verbose_name="VIP / BigIP",
	#		max_length=200,
	#		blank=True,
	#		null=True,
	#		help_text=u"",
	#		)
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
	kilde_cmdb = models.BooleanField(
			verbose_name="Kilde CMDB",
			default=False,
			)
	kilde_prk = models.BooleanField(
			verbose_name="Kilde PRK",
			default=False,
			)
	kilde_landesk = models.BooleanField(
			verbose_name="Kilde LanDesk",
			default=False,
			)
	maskinadm_virksomhet = models.ForeignKey(
			to="Virksomhet",
			on_delete=models.SET_NULL,
			verbose_name="PRK Virksomhet",
			related_name='cmdbdevice_virksomhet',
			null=True,
			blank=True,
			)
	maskinadm_virksomhet_str = models.CharField(
			verbose_name="PRK Virksomhet",
			max_length=300,
			blank=True,
			null=True,
			)
	maskinadm_lokasjon = models.CharField(
			verbose_name="Maskinadm: Lokasjon",
			max_length=300,
			blank=True,
			null=True,
			)
	maskinadm_klienttype = models.CharField(
			verbose_name="Maskinadm: Klienttype",
			max_length=200,
			blank=True,
			null=True,
			)
	maskinadm_status = models.CharField(
			verbose_name="PRK status",
			max_length=200,
			blank=True,
			null=True,
			)
	maskinadm_sone = models.CharField(
			verbose_name="Maskinadm: Sikkerhetssone",
			max_length=200,
			blank=True,
			null=True,
			)
	maskinadm_sist_oppdatert = models.DateTimeField( # ikke bruk denne lenger
			verbose_name="Maskinadm: Sist oppdatert",
			null=True,
			blank=True,
			)
	landesk_nic = models.CharField(
			verbose_name="Landesk: NIC",
			max_length=24,
			blank=True,
			null=True,
			)
	landesk_manufacturer = models.CharField(
			verbose_name="Landesk: Produsent",
			max_length=300,
			blank=True,
			null=True,
			)
	landesk_os_release = models.CharField(
			verbose_name="Landesk: OS release",
			max_length=100,
			blank=True,
			null=True,
			)
	landesk_sist_sett = models.DateTimeField( # felt som indikerer når maskin sist ble skannet
			verbose_name="Landesk: Sist sett",
			null=True,
			blank=True,
			)
	landesk_os = models.CharField(
			verbose_name="Landesk: OS",
			max_length=300,
			blank=True,
			null=True,
			)
	landesk_login = models.ForeignKey( # bruker sist logget på
			to=User,
			on_delete=models.SET_NULL,
			related_name='landesk_login',
			verbose_name="Landesk: Login name",
			null=True,
			blank=True,
			)

	# med vilje er det ikke HistoricalRecords() på denne da den importeres

	def __str__(self):
		return u'%s' % (self.comp_name)

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

	def vip(self):
		try:
			string = ""
			for pool in self.network_ip_address.all()[0].vip_pools.all():
				for vip in pool.vip.all():
					string += vip.vip_name
			return string
		except:
			return 'ingen data'


	def utdatert(self):
		versjon = int(self.landesk_os_release) if self.landesk_os_release else 0
		if versjon < 1909:
			return True
		return False

	class Meta:
		verbose_name_plural = "CMDB: maskiner"
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
			)
	backup_size_bytes = models.IntegerField(
			null=True,
			)
	export_date = models.DateTimeField(
			verbose_name="Dato uttrekk",
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
	# vurdere unique_together med device_str og device?

	class Meta:
		verbose_name_plural = "CMDB: Backup"
		verbose_name = "Backup"
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
		verbose_name_plural = "CMDB: disker"
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
		verbose_name_plural = "AD: organizational units"
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
	adgruppe = models.ForeignKey(
			to="ADgroup",
			related_name='leverandortilgang',
			verbose_name="AD-gruppeknytning",
			blank=False,
			null=True,
			help_text=u"Gis tilgang via følgende AD-gruppe",
			on_delete=models.SET_NULL,
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
			return u'Leverandørtilgang for %s' % (''.join(s.systemnavn for s in self.systemer.all()))
		except:
			return u'Leverandørtilgang %s' % self.pk

	def systemer_vis(self):
		return ", ".join([
			system.systemnavn for system in self.systemer.all()
		])
		systemer_vis.short_description = "Systemer"

	class Meta:
		verbose_name_plural = "Leverandørtilganger"
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
		verbose_name_plural = "AD: AD-grupper"
		verbose_name = "ADgruppe"
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
			help_text=u"Bruk dette feltet dersom denne avtalen spesifikt regulerer et tjenestekjøp eller 3.parts applikasjonsdrift. Dersom basisdrift og applikasjonsdrift/vedlikehold utføres av leverandøren tilhørende valgt driftsplattform lar du dette feltet stå tomt.",
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
		verbose_name_plural = "Avtaler"
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
			help_text=u"Brukes for å skjule systemet i visninger der infrastruktur ikke er relevant.",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.kategorinavn)

	class Meta:
		verbose_name_plural = "Systemoversikt: systemtyper"
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
	('TVERRSEKTORIELT', 'Tverrsektorielt'),
	('FELLESSYSTEM', 'Fellessystem'),
	('STOTTE', 'IKT-støttesystem'),
)

# må lage et script som inverterer verdiene i databasen 5 til 1 og 4 til 2 samtidig som disse inverteres.
VURDERINGER_SIKKERHET_VALG = (
	(1, '5 Svært alvorlig'),
	(2, '4 Alvorlig'),
	(3, '3 Moderat'),
	(4, '2 Lav'),
	(5, '1 Ubetydelig'),
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
	(1, 'Åpen'),
	(2, 'Intern'),
	(5, 'Beskyttet'),
	(3, 'Strengt beskyttet'),
	(4, 'Gradert')
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
		verbose_name_plural = "Behandling: regioner"
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
	programvarekategori = models.IntegerField(
			choices=PROGRAMVAREKATEGORI_VALG,
			verbose_name="Programvaretype",
			blank=True,
			null=True,
			help_text=u"",
			)
	programvaretyper = models.ManyToManyField(
			to=Systemtype,
			related_name='programvare_programvaretyper',
			verbose_name="Programvaretype(r)",
			blank=True,
			help_text=u"",
			)
	programvarebeskrivelse = models.TextField(
			verbose_name="Programvarebeskrivelse",
			blank=True,
			null=True,
			help_text=u"",
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
			verbose_name="Kategori(er)",
			blank=True,
			help_text=u"")
	kommentar = models.TextField(
			verbose_name="Kommentar (fritekst)",
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
			verbose_name="Status klargjort for ny sikkerhetsmodell",
			blank=True, null=True,
			help_text=u"Besnyttes av UKE for å kartlegge hvilke virksomheter som er klare for ny klientmodell uten permanent VPN.",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.programvarenavn)

	class Meta:
		verbose_name_plural = "Programvarer: programvarer"
		default_permissions = ('add', 'change', 'delete', 'view')


DRIFTSTYPE_VALG = (
	(0, 'Ukjent'),
	(1, 'Private cloud'),
	(2, 'Public cloud'),
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
	overordnet_plattform = models.ManyToManyField(
			to="Driftsmodell",
			related_name='driftsmodell_overordnet_plattform',
			verbose_name="Overordnet plattform",
			blank=True,
			help_text=u'Dersom dette er en "plattform på en plattform" kan du her henvise til hvilken plattform denne kjører på.',
			)
	history = HistoricalRecords()

	def __str__(self):
		if self.ansvarlig_virksomhet:
			return u'%s: %s' % (self.ansvarlig_virksomhet.virksomhetsforkortelse, self.navn)
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Systemoversikt: driftsmodeller"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['navn']

	def antall_systemer(self):
		return self.systemer.all().count()


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
		verbose_name_plural = "Systemoversikt: autorisasjonsmetoder"
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
		verbose_name_plural = "Systemoversikt: autentiseringsteknologi"
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
		verbose_name_plural = "Systemoversikt: autentiseringsmetoder"
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
		verbose_name_plural = "System: loggkategorier"
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
		verbose_name_plural = "System: dataoppdateringer"
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
		verbose_name_plural = "Systemoversikt: databasetyper"
		default_permissions = ('add', 'change', 'delete', 'view')


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
			help_text=u"Til informasjon. Ble tidligere benyttet for å skjule system fra noen visninger.",
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
			unique=True,
			max_length=100,
			blank=False,
			null=False,
			help_text=u"Se <a target='_blank' href='/definisjon/System/'>definisjon av system</a>. Undersøk om systemet er registrert før du eventuelt registrerer et nytt. Bruk \"(Felles)\" for fellessystemer, alternativt \"(<virksomhet>)\" for virksomhetsspesifikke systemer.",
			)
	alias = models.TextField(
			verbose_name="Alternative søkenavn (alias)",
			blank=True,
			null=True,
			help_text=u"Alternative navn på systemet for å avhjelpe søk. Kun enkeltord. Du kan skrive inn flere alias, gjerne separert med komma eller på hver sin linje.",
			)
	systembeskrivelse = models.TextField(
			verbose_name="Systembeskrivelse",
			blank=True,
			null=True,
			help_text=u"Tekstlig beskrivelse av hva systemet gjør/brukes til",
			)
	systemeier = models.ForeignKey(
			to=Virksomhet,
			related_name='systemer_systemeier',
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
			help_text=u"Person(er) med operativt systemeierskap.",
			)
	systemforvalter = models.ForeignKey(
			to=Virksomhet,
			related_name='systemer_systemforvalter',
			on_delete=models.SET_NULL,
			verbose_name="Organisatorisk systemforvalter",
			blank=True,
			null=True,
			help_text=u"Den virksomhet som har ansvar for forvaltning av systemet. Normalt en etat underlagt byrådsavdeling som har systemeierskapet",
			)
	systemforvalter_kontaktpersoner_referanse = models.ManyToManyField(
			to=Ansvarlig,
			related_name='system_systemforvalter_kontaktpersoner',
			verbose_name="Systemforvalter (personer)",
			blank=True,
			help_text=u"Person(er) med operativt forvalteransvar",
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
			help_text=u"Driftsplattform systemet kjører på. Merk at kommunen kan ha flere instanser av samme system driftet ulike steder.",
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
#	cmdbref_prod = models.ForeignKey(CMDBRef, related_name='system_cmdbref_prod',
#			on_delete=models.PROTECT,
#			verbose_name="Referanse til CMDB: Produksjon",
#			blank=True, null=True,
#			help_text=u"Kobling til Sopra Steria CMDB for Produksjon. Denne brukes for å vise tjenestenivå til systemet.",
#			)
#	cmdbref = models.ManyToManyField(CMDBRef, related_name='system_cmdbref',
#			verbose_name="Referanse til Sopra Steria CMDB",
#			blank=True,
#			help_text=u"Velg alle aktuelle med '(servergruppe)' bak navnet. Produksjon, test og annet.",
#			)
	sikkerhetsnivaa = models.IntegerField(
			choices=SIKKERHETSNIVAA_VALG,
			verbose_name="Konfidensialitetsnivå til systemet",
			blank=True,
			null=True,
			help_text=u'Sikkerhetsnivå for felles IKT-plattform i hht <a target="_blank" href="https://confluence.oslo.kommune.no/x/y8seAw">Informasjonstyper og behandlingskrav</a>',
			)
	programvarer = models.ManyToManyField(
			to=Programvare,
			related_name='system_programvarer',
			verbose_name="Programvarer benyttet",
			blank=True,
			help_text=u"Programvarer benyttet i systemet",
			)
	#database = models.IntegerField(
	#		verbose_name="Database (utfases, grunnet ny måte å registrere på)", choices=DB_VALG,
	#		blank=True, null=True,
	#		help_text=u"Dersom databasehotell, legg til databasehotellet som en teknisk avhengighet.",
	#		)
	avhengigheter = models.TextField(
			verbose_name="Utlevering og avhengigheter (fritekst)",
			blank=True,
			null=True,
			help_text=u"Her kan du gi utdypende beskrivelser til feltene som omhandler utlevering og systemtekniske avhengigeheter.",
			)
	avhengigheter_referanser = models.ManyToManyField(
			to="System",
			related_name='system_avhengigheter_referanser',
			verbose_name="Systemtekniske avhengigheter til andre systemer",
			blank=True,
			help_text=u"Her lister du opp andre systemer dette systemet er avhengig av, da utover at det overføres personopplysninger. F.eks. pålogginssystemer (AD, FEIDE, ID-porten..), databasehotell (Oracle, MSSQL..) eller RPA-prosesser.",
			)
	datautveksling_mottar_fra = models.ManyToManyField(
			to="System",
			related_name='system_datautveksling_mottar_fra',
			verbose_name="Mottar personopplysninger fra følgende systemer",
			blank=True,
			help_text=u"Her lister du opp systemer dette systemet mottar personopplysinger fra. Dersom overføringen skjer via en integrasjon, velges integrasjonen her. Valg her vises blant annet i systemets DPIA.",
			)
	datautveksling_avleverer_til = models.ManyToManyField(
			to="System",
			related_name='system_datautveksling_avleverer_til',
			verbose_name="Avleverer personopplysninger til følgende systemer",
			blank=True,
			help_text=u"Her lister du opp systemer dette systemet avleverer personopplysinger til. Dersom overføringen skjer via en integrasjon, velges integrasjonen her. Valg her vises blant annet i systemets DPIA.",
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
			verbose_name="Systemtype / menneskelig grensesnitt",
			blank=True,
			help_text=u"Her beskriver hva slags type system dette er. Merk særlig dette feltet dersom systemet er en integrasjon eller infrastrukturkomponent.",
			)
	systemkategorier = models.ManyToManyField(
			to=SystemKategori,
			related_name='system_systemkategorier',
			verbose_name="Systemkategori(er)",
			blank=True,
			help_text=u"Dette er et sett med kategorier som forvaltes av UKE ved seksjon for information management (IM). Velg det som passer best.",
			)
	systemurl = models.ManyToManyField(
			to=SystemUrl,
			related_name='system_systemurl',
			verbose_name="URL (dersom webapplikasjon)",
			blank=True,
			default=None,
			help_text=u"Adressen systemet nås på via nettleser",
			)
	systemleverandor_vedlikeholdsavtale = models.BooleanField(
			verbose_name="Aktiv vedlikeholdsavtale med systemleverandør?",
			default=None,
			null=True,
			help_text=u"Kan settes til ja, nei eller ukjent. Standard er ukjent.",
			)
	systemleverandor = models.ManyToManyField(
			to=Leverandor,
			related_name='system_systemleverandor',
			verbose_name="Systemleverandør (tjenesteleverandør)",
			blank=True,
			help_text=u"Her fyller du ut leverandør som har utviklet systemet. I noen situasjoner kjøpes systemet som en tjeneste (SaaS), og i andre tilfeller er serverkapasitet og applikasjonsdrift utført av en tredjepartsleverandør. Fyll da inn feltene under.",
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
			help_text=u"Om systemet er nytt, moderne eller skal fases ut. Setter du status 5 eller 6 vil systemet havne på 'End of life (EOL)'-listen.",
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
	konfidensialitetsvurdering = models.IntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Oppsummert konfidensialitetsvurdering (utfases)",
			blank=True,
			null=True,
			help_text=u"Oppsummert: Hvor sensitive er opplysningene?",
			)
	integritetsvurdering = models.IntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Oppsummert integritetsvurdering",
			blank=True,
			null=True,
			help_text=u"Oppsummert: Hvor kritisk er det at opplysningene stemmer?",
			)
	tilgjengelighetsvurdering = models.IntegerField(
			choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Oppsummert tilgjengelighetsvurdering",
			blank=True,
			null=True,
			help_text=u"Oppsummert: Hvor kritisk er det om systemet ikke virker?",
			)
	tilgjengelighet_kritiske_perioder = models.TextField(
			verbose_name="Utdypning tilgjengelighet: Kritiske perioder og konsekvenser ved nedetid",
			blank=True,
			null=True,
			help_text=u"Her legger du inn perioder av året hvor det er særskilt behov for at systemet er tilgjengelig. F.eks. knyttet til frister som eiendomsskatt, barnehageopptak eller lønnskjøring.",
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
	#autorisasjonsalternativer = models.ManyToManyField(Autorisasjonsmetode,
	#		verbose_name="Tilgangsteknologi", related_name='system_autorisasjonsalternativer',
	#		blank=True,
	#		help_text=u"Hvordan får bruker tilgang til informasjon i systemet?",
	#		)
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
			help_text=u"Person som kan kontaktes for å undersøke om det er personopplysninger i systemet knyttet til en innsynsbegjæring.",
			)
	innsyn_innbygger = models.BooleanField(
			verbose_name="Innsyn relevant for innbygger?",
			default=True,
			help_text=u"Krysses av dersom det er aktuelt å søke igjennom dette systemet etter personopplysninger ved innsynsbegjæring fra en innbygger.",
			)
	innsyn_ansatt = models.BooleanField(
			verbose_name="Innsyn relevant for (tidligere) ansatt?",
			default=True,
			help_text=u"Krysses av dersom det er aktuelt å søke igjennom dette systemet etter personopplysninger ved innsynsbegjæring fra en ansatt",
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
			verbose_name="Andre godkjente bestillere (Kompass)",
			blank=True,
			help_text=u"Forvaltere er autorisert til å bestille endringer på systemet i Kompass. Disse personene er også autorisert for å bestille endringer.",
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
			help_text=u'Velg en eller flere sikkerhetsgrupper i AD tilhørende systemet.',
			)
	legacy_klient_krever_smb = models.BooleanField(
			verbose_name="Direkte kommunikasjon med filområde.",
			blank=True,
			null=True,
			help_text=u"Settes dersom systemets klient må kommunisere direkte med on-prem filområder. OneDrive er ikke on-prem og er derfor ikke en grunnlag for å sette 'ja' på denne. Settes til 'ja' dersom minst ét av grensesnittene krever on-prem filområdetilgang.",
			)
	legacy_klient_krever_direkte_db = models.BooleanField(
			verbose_name="Direkte kommunikasjon med databaseserver fra klient.",
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
			blank=True,
			)
	LOSref = models.ManyToManyField(
			to="LOS",
			related_name='systemer',
			verbose_name="Begrepstagging (LOS)",
			blank=True,
			help_text=u"Tagg systemet med behandlinger / kommunale områder.",
			)
	klargjort_ny_sikkerhetsmodell = models.IntegerField(
			choices=VALG_KLARGJORT_SIKKERHETSMODELL,
			verbose_name="Status klargjort for ny sikkerhetsmodell",
			blank=True, null=True,
			help_text=u"Besnyttes av UKE for å kartlegge hvilke virksomheter som er klare for ny klientmodell uten permanent VPN.",
			)
	history = HistoricalRecords()

	def __str__(self):
		if self.ibruk == False:
			return u'%s (%s)' % (self.systemnavn, "avviklet")
		else:
			return u'%s' % (self.systemnavn)

	def alias_oppdelt(self):
		return self.alias.split()

	def unike_server_os(self):
		server_os = []
		try:
			for bss in self.bs_system_referanse.cmdb_bss_to_bs.all():
				for server in bss.cmdbdevice_sub_name.all():
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
		alle_bss = self.bs_system_referanse.cmdb_bss_to_bs.all()
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
		alle_bss = self.bs_system_referanse.cmdb_bss_to_bs.all()
		for bss in alle_bss:
			servere = CMDBdevice.objects.filter(sub_name=bss)
			for s in servere:
				serveros.append("%s %s" % (s.comp_os, s.comp_os_version))
		return ', '.join([os for os in set(serveros)])

	def er_infrastruktur(self):
		for stype in self.systemtyper.all():
			if stype.er_infrastruktur:
				return True
		else:
			return False

	def forventet_url(self):
		for systemtype in self.systemtyper.all():
			if systemtype.har_url:
				return True
		return False

	def antall_avhengigheter(self):
		return len(self.datautveksling_mottar_fra.all()) + len(self.datautveksling_avleverer_til.all()) + len(self.avhengigheter_referanser.all())

	def antall_bruk(self):
		bruk = SystemBruk.objects.filter(system=self.pk)
		return bruk.count()

	def er_ibruk(self):
		if self.livslop_status in [1,6,7]:
			return False
		return True




	# brukes bare av dashboard, flyttes dit? ("def statusTjenestenivaa(systemer)")
	def fip_kritikalitet(self):
		if hasattr(self, 'bs_system_referanse'):
			kritikalitet = []
			for ref in self.bs_system_referanse.cmdb_bss_to_bs.all():
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
			for ref in self.bs_system_referanse.cmdb_bss_to_bs.all():
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


	class Meta:
		verbose_name_plural = "Systemoversikt: systemer"
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
		verbose_name_plural = "Domener: sikkerhetstester"
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
		verbose_name_plural = "Programvarer: programvarebruk"
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
			help_text=u"Dersom fellesløsning på applikasjonshotell, hvilke roller/personer fyller rollen som forvalter?",
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
		verbose_name_plural = "Systemoversikt: systembruk"
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
		verbose_name_plural = "Behandling: informeringsvalg"
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
		verbose_name_plural = "Behandling: klasser av registrerte"
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
		verbose_name_plural = "Behandling: registrerts relasjoner"
		default_permissions = ('add', 'change', 'delete', 'view')


BEHANDLING_VALGFRIHET = (
	(1, 'Stor valgfrihet'),
	(2, 'Middels valgfrihet'),
	(3, 'Ingen valgfrihet'),
)


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
			help_text=u'Sikkerhetsnivå for felles IKT-plattform i hht <a target="_blank" href="https://confluence.oslo.kommune.no/x/y8seAw">Informasjonstyper og behandlingskrav</a>',
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
		verbose_name_plural = "Behandling: behandlinger (protokoll)"
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
		verbose_name_plural = "PRK: HR-organisasjoner"
		verbose_name  = "HR-organization"
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
			unique=True,
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

	def __str__(self):
		return u'%s' % (self.display_name)

	class Meta:
		verbose_name_plural = "Azure application keys"
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
		verbose_name="Vurdering av risiko",
		default=0,
		blank=False,
		null=False,
		help_text=u"Beholdes ved synkronisering mot Azure som skjer hver natt",
		)

	def __str__(self):
		return u'%s' % (self.displayName)

	def antall_application_permissions(self):
		return AzurePublishedPermissionScopes.objects.filter(azure_applications=self.id).filter(permission_type="Application").count()

	class Meta:
		verbose_name_plural = "Azure applications"
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
		null=False,
		)
	grant_type = models.TextField(
		# ment å holde en liste (array)
		# for å oppbevare permissionScope["type"] eller role["allowedMemberTypes"]
		null=False,
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
		if self.permission_type == "Application":
			return True
		if "full access" in self.adminConsentDisplayName:
			return True
		if "ReadWrite.All" in self.value:
			return True
		if "Mail.ReadWrite" in self.value:
			return True
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
		if "Group.Read.All" in self.value:
			return True
		return False

	class Meta:
		verbose_name_plural = "Azure permission scopes"
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
		on_delete=models.CASCADE,
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
		verbose_name="Faktisk periode påløpt",
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
		on_delete=models.PROTECT,
		verbose_name="Type / kategori",
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
		verbose_name="Faktisk periode påløpt",
		null=False, blank=False,
		)
	kategori = models.ForeignKey(
		to="UBWFakturaKategori",
		on_delete=models.PROTECT,
		verbose_name="Type / kategori",
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


	def __str__(self):
		return u'%s' % (self.verdi)

	class Meta:
		verbose_name_plural = "LOS fellesbegreper"
		default_permissions = ('add', 'change', 'delete', 'view')



"""
class PRKuser(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	username = models.CharField(
			verbose_name="Brukernavn",
			max_length=20,
			unique=True,
			help_text=u"Importert",
			)
	usertype = models.CharField(
			verbose_name="Brukernavn",
			max_length=20,
			null=False, blank=False,
			help_text=u"Importert",
			)
	#ikke behov for historikk
	def __str__(self):
		return u'%s (%s)' % (self.username, self.usertype)

	class Meta:
		verbose_name_plural = "PRK brukere"
		default_permissions = ('add', 'change', 'delete', 'view')
"""

"""
LIVSSYKLUS_VALG = (
	(1, '1 valg 1'),
	(2, '2 valg 2'),
	(3, '3 valg 3'),
)

class Tjeneste(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	tjenesteleverandor = models.ForeignKey(Virksomhet,
			on_delete=models.PROTECT,
			verbose_name="Virksomhet som leverer tjenesten",
			related_name="tjeneste_tjenesteleverandor",
			blank=True,
			null=True,
			help_text="Den virksomhet du kan ta kontakt med for å be om tjenesten.",
			)
	tjenestenavn = models.CharField(unique=True,
			verbose_name="Navn på tjeneste",
			max_length=150,
			blank=False, null=False,
			help_text=u"",
			)
	beskrivelse = models.TextField(
			verbose_name="Beskrivelse av tjenesten",
			blank=True, null=True,
			help_text=u"Hva får virksomheten ved å ta i bruk denne tjenesten?",
			)
	systemer = models.ManyToManyField(System, related_name='tjeneste_systemer',
			verbose_name="Kjernesystem(er): Hvilke systemer som inngår i tjenesten",
			blank=True,
			)
	tjenesteleder = models.ManyToManyField(Ansvarlig, related_name='tjeneste_tjenesteleder',
			verbose_name="Tjenesteleder",
			blank=True,
			)
	tjenesteforvalter = models.ManyToManyField(Ansvarlig, related_name='tjeneste_tjenesteforvalter',
			verbose_name="Tjenesteforvalter",
			blank=True,
			)
	livssyklus = models.IntegerField(choices=LIVSSYKLUS_VALG,
			verbose_name="Status på livssyklus",
			blank=True, null=True,
			help_text=u"",
			)
	etablering = models.IntegerField(choices=LIVSSYKLUS_VALG,
			verbose_name="Status på etablering",
			blank=True, null=True,
			help_text=u"",
			)
	tjenesteleveranse = models.IntegerField(choices=LIVSSYKLUS_VALG,
			verbose_name="Status på tjenesteleveranse",
			blank=True, null=True,
			help_text=u"",
			)
	faglig_ansvar = models.TextField(
			verbose_name="Faglig ansvar",
			blank=True, null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.tjenestenavn)

	class Meta:
		verbose_name_plural = "Tjenester"
		default_permissions = ('add', 'change', 'delete', 'view')
"""
