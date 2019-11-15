# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from simple_history.models import HistoricalRecords

RESULTATENHET_VALG = (
	('OF', 'Felles IKT-plattform'),
	('Egen', 'Egen drift'),
)


# som standard vises bare "self.username". Vi ønsker også å vise fult navn.
def new_display_name(self):
	return(self.first_name + " " + self.last_name + " (" + self.username + ")")
User.add_to_class("__str__", new_display_name)


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
			blank=False, null=False,
			help_text=u"event_type",
			)
	message = models.TextField(
			verbose_name="message",
			blank=False, null=False,
			help_text=u"message",
			)
	def __str__(self):
		return u'%s %s %s' % (self.opprettet.strftime('%Y-%m-%d %H:%M:%S'), self.event_type, self.message)

	class Meta:
		verbose_name_plural = "Applikasjonslogger"
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
			blank=True, null=True,
			help_text=u"Navn på kontekst som kan velges for defininsjoner",
			)

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Definisjonskontekster"
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
	status = models.IntegerField(choices=DEFINISJON_STATUS_VALG,
			verbose_name="Status på definisjon",
			blank=False, null=False,
			default=0,
			help_text=u"Livsløp på definisjonen",
			)
	begrep = models.CharField(
			verbose_name="Begrep / term",
			max_length=300,
			blank=False, null=False,
			help_text=u"",
			)
	kontekst_ref = models.ForeignKey(DefinisjonKontekster, related_name='defininsjon_kontekst_ref',
			verbose_name="Definisjonens kontekst (valgmeny)",
			blank=True, null=True,
			on_delete=models.PROTECT,
			help_text=u"Konteksten eller domenet definisjonen angår",
			)
	engelsk_begrep = models.CharField(
			verbose_name="Engelsk begrep / term",
			max_length=300,
			blank=True, null=True,
			help_text=u"",
			)
	ansvarlig = models.ForeignKey("Ansvarlig",
			null=True, blank=True,
			on_delete=models.PROTECT,
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=False, null=False,
			help_text=u"Definisjon slik folk flest kan forstå den",
			)
	eksempel = models.TextField(
			verbose_name="Eksempel",
			blank=True, null=True,
			help_text=u"Eksemplifiser definisjonen dersom mulig.",
			)
	legaldefinisjon = models.TextField(
			verbose_name="Legaldefinisjon",
			blank=True, null=True,
			help_text=u"Formell/legal definisjonstekst",
			)
	kilde = models.URLField(
			verbose_name="Kilde eller opphav (URL)",
			max_length=600,
			blank=True, null=True,
			help_text=u"En URI til original definisjon.",
			)
	kontekst = models.TextField(
			verbose_name="Gammel kontekst (fases ut)",
			blank=True, null=True,
			help_text=u"Konteksten eller domenet definisjonen angår",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.begrep)

	class Meta:
		verbose_name_plural = "Definisjoner"
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
	brukernavn = models.OneToOneField(User, related_name="ansvarlig_brukernavn",
			on_delete=models.PROTECT,
			blank=False, null=False,
			help_text=u"Her kan du søke på fornavn og/eller etternavn.",
			)
	telefon = models.CharField(
			verbose_name="Primærtelefon (mobil)",
			max_length=30,
			blank=True, null=True,
			help_text=u"Nummer personen/rollen kan nås på i jobbsammenheng. Må kunne motta SMS.",
			)
	fdato = models.CharField(
			verbose_name="Fødselsdato",
			max_length=6,
			blank=True, null=True,
			help_text=u"Dag, måned, år, f.eks. 100575 (10.mai 1975). Dette feltet fyller du bare ut dersom personen har en rolle innen sertifikatgodkjenning.",
			)
	kommentar = models.TextField(
			verbose_name="Organisatorisk tilhørighet / rolle",
			blank=True, null=True,
			help_text=u"Fritekst",
			)
	vil_motta_epost_varsler = models.BooleanField(
			verbose_name="Ønsker å motta e-postvarsler?",
			default=False,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		if self.brukernavn:
			if self.brukernavn.profile.virksomhet:
				return u'%s %s (%s)' % (self.brukernavn.first_name, self.brukernavn.last_name, self.brukernavn.profile.virksomhet.virksomhetsforkortelse)
			else:
				return u'%s %s (%s)' % (self.brukernavn.first_name, self.brukernavn.last_name, "?")
		else:
			return u'%s (tastet inn)' % (self.navn)

	class Meta:
		verbose_name_plural = "Ansvarlige"
		default_permissions = ('add', 'change', 'delete', 'view')


class AutorisertBestiller(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	person = models.ForeignKey(Ansvarlig, related_name='autorisertbestiller_person',
			verbose_name="Autoriserte sertifikatbestillere",
			blank=True,
			on_delete=models.PROTECT,
			help_text=u"Personer i virksomheten som er autorisert til å bestille sertifikater via UKE. Det må da foreligge en fullmakt gitt til UKEs driftsleverandør.",
			)
	dato_fullmakt = models.DateField(
			verbose_name="Dato fullmakt gitt",
			blank=False, null=False,
			help_text=u"Dato fra fullmaktskjema.",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.person)

	class Meta:
		verbose_name_plural = "Antoriserte bestillere"
		default_permissions = ('add', 'change', 'delete', 'view')



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
	virksomhetsforkortelse = models.CharField(unique=True,
			verbose_name="Virksomhetsforkortelse",
			blank=True, null=True,
			max_length=3,
			help_text=u"",
			)
	virksomhetsnavn = models.CharField(unique=True,
			verbose_name="Virksomhetsnavn",
			max_length=250,
			help_text=u"",
			)
	overordnede_virksomheter = models.ManyToManyField("Virksomhet", related_name='virksomhet_overordnede_virksomheter',
			verbose_name="Overordnede virksomheter",
			blank=True,
			help_text=u"Brukes for å kunne representere underordnede virksomheter",
			)
	kan_representeres = models.BooleanField(
			verbose_name="Kan representeres",
			default=False,
			help_text=u"Settes dersom det skal være mulig for overordnet virksomhet å bytte rolle til underordnet virksomhet",
			)
	resultatenhet = models.CharField(choices=RESULTATENHET_VALG,
			verbose_name="Driftsmodell e-post, kalender og arbeidsflate",
			max_length=30,
			blank=True, null=True,
			default='',
			help_text=u"",
			)
	uke_kam_referanse = models.ManyToManyField(Ansvarlig, related_name='virksomhet_uke_kam',
			verbose_name='Kundeansvarlig hos UKE',
			blank=True,
			help_text=u"",
			)
	ansatte = models.IntegerField(
			verbose_name="Antall ansatte",
			blank=True, null=True,
			help_text=u"",
			)
	intranett_url = models.URLField(
			verbose_name="Link til intranett",
			max_length=600,
			blank=True, null=True,
			help_text=u"",
			)
	www_url = models.URLField(
			verbose_name="Link til oslo.kommune.no",
			max_length=600,
			blank=True, null=True,
			help_text=u"",
			)
	ikt_kontakt = models.ManyToManyField(Ansvarlig, related_name='virksomhet_ikt_kontakt',
			verbose_name='IKT-hovedkontakt',
			blank=True,
			help_text=u"Koordineringsledd mellom UKE og virksomheten.",
			)
	autoriserte_bestillere_tjenester = models.ManyToManyField(Ansvarlig, related_name='virksomhet_autoriserte_bestillere_tjenester',
			verbose_name='Autoriserte bestillere InfoTorg',
			blank=True,
			help_text=u"En autorisert bestiller InfoTorg er en person virksomheten har autorisert til å bestille brukere til data fra det sentrale folkeregistret.",
			)
	autoriserte_bestillere_tjenester_uke = models.ManyToManyField(Ansvarlig, related_name='virksomhet_autoriserte_bestillere_tjenester_uke',
			verbose_name='Autoriserte bestillere tjenester UKE',
			blank=True,
			help_text=u"En autorisert bestiller er en person virksomheten har autorisert til å bestille tjenester av UKE via den nye kundeportalen som snart kommer. Det kan angis flere i dette feltet.",
			)
	orgnummer = models.CharField(
			verbose_name="Organisasjonsnummer",
			max_length=30,
			blank=True, null=True,
			help_text=u"",
			)
	leder = models.ManyToManyField(Ansvarlig, related_name='virksomhet_leder',
			verbose_name="Virksomhetsleder",
			blank=True,
			help_text=u"",
			)
	autoriserte_bestillere_sertifikater = models.ManyToManyField(AutorisertBestiller, related_name='virksomhet_autoriserte_bestillere_sertifikater',
			verbose_name="Autoriserte bestillere (sertifikater)",
			blank=True,
			help_text=u"Fylles ut dersom virksomhetsleder har avgitt fullmakt for ustedelse av websertifikater og/eller virksomhetssertifikater.",
			)
	sertifikatfullmakt_avgitt_web = models.NullBooleanField(
			verbose_name="Gitt fullmakt websertifikater?",
			blank=True, null=True,
			default=False,
			help_text=u"Har avgitt fullmakt til driftsleverandør for utstedelse av websertifikater for sitt orgnummer.",
			)
	sertifikatfullmakt_avgitt_virksomhet = models.NullBooleanField(
			verbose_name="Gitt fullmakt virksomhetssertifikater?",
			blank=True, null=True,
			default=False,
			help_text=u"Har avgitt fullmakt til driftsleverandør for utstedelse av virksomhetssertifikater for sitt orgnummer.",
			)
	rutine_tilgangskontroll = models.URLField(
			verbose_name="Link til rutiner for tilgangskontroll",
			max_length=600,
			blank=True, null=True,
			help_text=u"Link til dokument i virksomhetens styringssystem",
			)
	rutine_behandling_personopplysninger = models.URLField(
			verbose_name="Link til rutiner for behandling av personopplysninger",
			max_length=600,
			blank=True, null=True,
			help_text=u"Link til dokument i virksomhetens styringssystem",
			)
	rutine_klage_behandling = models.URLField(
			verbose_name="Link til rutine for behandling av klage på behandling",
			max_length=600,
			blank=True, null=True,
			help_text=u"Link til dokument i virksomhetens styringssystem",
			)
	personvernkoordinator = models.ManyToManyField(Ansvarlig, related_name='virksomhet_personvernkoordinator',
			verbose_name='Personvernkoordinator',
			blank=True,
			help_text=u"Personvernkoordinator.",
			)
	informasjonssikkerhetskoordinator = models.ManyToManyField(Ansvarlig, related_name='virksomhet_informasjonssikkerhetskoordinator',
			verbose_name='Informasjonssikkerhetskoordinator',
			blank=True,
			help_text=u"Informasjonssikkerhetskoordinator.",
			)
	history = HistoricalRecords()


	def __str__(self):
		return u'%s (%s)' % (self.virksomhetsnavn, self.virksomhetsforkortelse)

	class Meta:
		verbose_name_plural = "Virksomheter"
		default_permissions = ('add', 'change', 'delete', 'view')



class Profile(models.Model): # brukes for å knytte innlogget bruker med tilhørende virksomhet. Vurderer å fjerne denne.
	#https://simpleisbetterthancomplex.com/tutorial/2016/07/22/how-to-extend-django-user-model.html
	user = models.OneToOneField(User,
			on_delete=models.CASCADE,  # slett profilen når brukeren slettes
			)
	virksomhet = models.ForeignKey(Virksomhet, related_name='brukers_virksomhet',
			on_delete=models.PROTECT,
			verbose_name="Virksomhet / Etat: Representerer",
			blank=True, null=True,
			)
	virksomhet_innlogget_som = models.ForeignKey(Virksomhet, related_name='brukers_virksomhet_innlogget_som',
			on_delete=models.PROTECT,
			verbose_name="Virksomhet / Etat: Innlogget som",
			blank=True, null=True,
			)
	accountdisable = models.BooleanField(
			verbose_name="AD: accountdisable",
			default=False,
			help_text="Importeres.",
			)
	lockout = models.BooleanField(
			verbose_name="AD: lockout",
			default=False,
			help_text="Importeres.",
			)
	passwd_notreqd = models.BooleanField(
			verbose_name="AD: passwd_notreqd",
			default=False,
			help_text="Importeres.",
			)
	dont_expire_password = models.BooleanField(
			verbose_name="AD: dont_expire_password",
			default=False,
			help_text="Importeres.",
			)
	password_expired = models.BooleanField(
			verbose_name="AD: password_expired",
			default=False,
			help_text="Importeres.",
			)
	ekstern_ressurs = models.BooleanField(
			verbose_name="Ekstern ressurs",
			default=False,
			help_text="Settes dersom bruker ligger under OU=Eksterne brukere.",
			)
	# med vilje er det ikke HistoricalRecords() på denne

	def __str__(self):
		return u'%s' % (self.user)

	class Meta:
		verbose_name_plural = "Profiler"

	@receiver(post_save, sender=User)
	def create_user_profile(sender, instance, created, **kwargs):
		if created:
			Profile.objects.create(user=instance)

	@receiver(post_save, sender=User)
	def save_user_profile(sender, instance, **kwargs):
		instance.profile.save()



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
	leverandor_navn = models.CharField(unique=True,
			verbose_name="Leverandørens navn",
			max_length=350,
			help_text=u"",
			)
	kontaktpersoner = models.TextField(
			verbose_name="Adresse og kontaktpersoner",
			blank=True, null=True,
			help_text=u"",
			)
	orgnummer = models.CharField(
			verbose_name="Organisasjonsnummer",
			max_length=30,
			blank=True, null=True,
			help_text=u"",
			)
	notater = models.TextField(
			verbose_name="Notater",
			blank=True, null=True,
			help_text=u"",
			)
	godkjent_opptaks_sertifiseringsordning = models.TextField(
			verbose_name="Er leverandørene registrert på en godkjent opptaks- eller sertifiseringsordning? Beskriv hvilke.",
			blank=True, null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.leverandor_navn)

	class Meta:
		verbose_name_plural = "Leverandører"
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
			blank=True, null=True,
			help_text=u"",
			)
	beskrivelse = models.TextField(
			verbose_name="Beskrivelse av informasjonsklassen",
			blank=True, null=True,
			help_text=u"F.eks. henvisning til lover som gjelder",
			)

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Informasjonsklasser"
		default_permissions = ('add', 'change', 'delete', 'view')
		ordering = ['navn']

class SystemKategori(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	kategorinavn = models.CharField(unique=True,
			verbose_name="Kategorinavn",
			max_length=100,
			blank=False, null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True, null=True,
			help_text=u"Slik at andre kan vurdere passende kategorier",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.kategorinavn)

	class Meta:
		verbose_name_plural = "Systemkategorier"
		default_permissions = ('add', 'change', 'delete', 'view')



class SystemHovedKategori(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	hovedkategorinavn = models.CharField(unique=True,
			verbose_name="Kategorinavn",
			max_length=30,
			blank=False, null=False,
			help_text=u"",
			)
	definisjon = models.CharField(
			verbose_name="Definisjon",
			max_length=600,
			blank=True,
			null=True,
			help_text=u"Slik at andre kan vurdere passende kategorier",
			)
	subkategorier = models.ManyToManyField(SystemKategori, related_name='systemhovedkategori_systemkategorier',
			verbose_name="Subkategorier",
			blank=True, help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.hovedkategorinavn)

	class Meta:
		verbose_name_plural = "Systemhovedkategorier"
		default_permissions = ('add', 'change', 'delete', 'view')



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
	domene = models.URLField(unique=True,
			verbose_name="Domene",
			max_length=600,
			blank=False, null=False,
			help_text=u"",
			)
	https = models.NullBooleanField(
			verbose_name="Sikret med https?",
			blank=True, null=True,
			default=None,
			help_text=u"",
			)
	maalgruppe = models.IntegerField(choices=MAALGRUPPE_VALG,
			verbose_name="Målgruppe",
			blank=True, null=True,
			help_text=u'Hvem kan bruke / nå tjenesten på denne URL-en?',
			)
	vurdering_sikkerhetstest = models.IntegerField(choices=SIKKERHETSTESTING_VALG,
			verbose_name="Vurdering sikkerhetstest",
			blank=True, null=True,
			help_text=u'Hvor aktuelt er det å sikkerhetsteste denne tjenesten?',
			)
	registrar = models.ForeignKey(Leverandor, related_name='systemurl_registrar',
			on_delete=models.PROTECT,
			verbose_name="Domeneregistrar",
			null=True, blank=True,
			help_text=u'Leverandør som domenet er registrert hos',
			)
	eier = models.ForeignKey(Virksomhet,
			on_delete=models.PROTECT,
			verbose_name="Eier av domenet",
			related_name='systemurl_eier',
			null=True, blank=True,
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
		verbose_name_plural = "System-URL-er"
		default_permissions = ('add', 'change', 'delete', 'view')



class Personsonopplysningskategori(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.CharField(unique=True,
			verbose_name="Kategorinavn",
			max_length=600,
			blank=False, null=False,
			help_text=u"",
			)
	artikkel = models.IntegerField(
			verbose_name="Artikkelreferanse",
			blank=True, null=True,
			default=None,
			help_text=u"",
			)
	hovedkategori = models.CharField(
			verbose_name="Hovedkategori",
			blank=False, null=False,
			max_length=600,
			help_text=u"",
			)
	eksempler = models.TextField(
			verbose_name="Eksempler",
			blank=True, null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Behandling: Personopplysningskategorier"
		default_permissions = ('add', 'change', 'delete', 'view')



class Registrerte(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	kategorinavn = models.CharField(unique=True,
			verbose_name="Kategorinavn",
			max_length=600,
			blank=False, null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True, null=True,
			help_text=u"Beskrivelse av kategori og noen eksempler.",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.kategorinavn)

	class Meta:
		verbose_name_plural = "Behandling: Kategorier registrerte"
		default_permissions = ('add', 'change', 'delete', 'view')



class Behandlingsgrunnlag(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	grunnlag = models.CharField(unique=True,
			verbose_name="Behandlingsgrunnlag",
			max_length=600,
			blank=False, null=False,
			help_text=u"Forkortet tittel på formålet",
			)
	lovparagraf = models.CharField(unique=False,
			verbose_name="Paragrafhenvisning",
			max_length=600,
			blank=True, null=True,
			help_text=u"Paragraf i loven",
			)
	lov = models.CharField(unique=False,
			verbose_name="Lovhenvisning",
			max_length=600,
			blank=True, null=True,
			help_text=u"Navnet på loven",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s (%s)' % (self.grunnlag, self.lovparagraf)

	class Meta:
		verbose_name_plural = "Behandlingsgrunnlag"
		default_permissions = ('add', 'change', 'delete', 'view')



CMDB_KRITIKALITET_VALG = (
	(1, '1 most critical'),
	(2, '2 somewhat critical'),
	(3, '3 less critical'),
	(4, '4 not critical'),
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

class CMDBRef(models.Model):
	opprettet = models.DateTimeField(
			verbose_name="Opprettet",
			auto_now_add=True,
			null=True,
			)
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)

	#hva brukes denne til?
	aktiv = models.NullBooleanField(
			verbose_name="Er dette CMDB-innslaget fortsatt gyldig?",
			blank=True, null=True,
			help_text=u"Ja eller nei",
			)
	navn = models.CharField(unique=True,
			verbose_name="CMDB-navn",
			max_length=600,
			blank=False, null=False,
			help_text=u"Navn i CMDB. Maks 300 tegn. Må være unik.",
			)
	environment = models.IntegerField(choices=CMDB_ENV_VALG,
			verbose_name="Miljø",
			blank=True, null=True,
			help_text=u"Importert: environment",
			)
	kritikalitet = models.IntegerField(choices=CMDB_KRITIKALITET_VALG,
			verbose_name="Kritikaltiet / SLA",
			blank=True, null=True,
			help_text=u"Importert: Kritikalitet",
			)
	cmdb_type = models.IntegerField(choices=CMDB_TYPE_VALG,
			verbose_name="CMDB-type",
			blank=True, null=True,
			help_text=u"Manuelt satt",
			)
	comments = models.TextField(
			verbose_name="Brukes til",
			blank=True, null=True,
			help_text=u"Importert: Kommentarer",
			)
	operational_status = models.IntegerField(choices=CMDB_OPERATIONAL_STATUS,
			verbose_name="Operational status",
			blank=True, null=True,
			help_text=u"Importert: Operational status",
			)
	u_service_portfolio = models.TextField(
			verbose_name="Portfolio",
			blank=True, null=True,
			help_text=u"Importert: Service portfolio",
			)
	u_service_availability = models.TextField(
			verbose_name="Availability",
			blank=True, null=True,
			help_text=u"Importert: Service availability",
			)
	u_service_operation_factor = models.TextField(
			verbose_name="operation factor",
			blank=True, null=True,
			help_text=u"Importert: Service operation factor",
			)
	u_service_complexity = models.TextField(
			verbose_name="Complexity",
			blank=True, null=True,
			help_text=u"Importert: Service complexity",
			)
	# med vilje er det ikke HistoricalRecords() på denne da den importeres regelmessig

	def __str__(self):
		return u'%s' % (self.navn)

	def er_infrastruktur_tom_bs(self):
		if self.cmdb_type in [3, 4, 6]:
			return True
		else:
			return False

	def system_mangler(self):
		if self.cmdb_type == 1 and self.system_cmdbref.count() < 1:
			return True
		else:
			return False

	def er_ukjent(self):
		if self.cmdb_type == 2:
			return True
		else:
			return False

	class Meta:
		verbose_name_plural = "CMDB-referanser"
		default_permissions = ('add', 'change', 'delete', 'view')



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
	active = models.BooleanField(
			verbose_name="Er enheten aktiv i 2S CMDB?",
			default=True,
			help_text=u"",
			)
	comp_name = models.CharField(unique=True,
			verbose_name="Computer name",
			max_length=600,
			blank=False, null=False,
			help_text=u"",
			)
	""" vi importerer bare sub service-nivået.
	bs_name = models.CharField( # foreign key
			verbose_name="Business Service",
			max_length=600,
			blank=True, null=True,
			help_text=u"",
			)
	"""
	comp_disk_space = models.IntegerField(
			verbose_name="Lagring (GB?)",
			blank=True, null=True,
			help_text=u"",
			)
	bs_u_service_portfolio = models.CharField(  # samme som "sub_u_service_portfolio"
			verbose_name="Business portfolio",
			max_length=600,
			blank=True, null=True,
			help_text=u"",
			)
	sub_name = models.ManyToManyField(CMDBRef, related_name='cmdbdevice_sub_name',
			verbose_name="Business Sub Service",
			blank=True,
			help_text=u"",
			)
	comp_ip_address = models.CharField(
			verbose_name="IP-address",
			max_length=100,
			blank=True, null=True,
			help_text=u"",
			)
	comp_cpu_speed = models.IntegerField(
			verbose_name="CPU-hastighet (MHz?)",
			blank=True, null=True,
			help_text=u"",
			)
	comp_os = models.CharField(
			verbose_name="Operativsystem",
			max_length=200,
			blank=True, null=True,
			help_text=u"",
			)
	comp_os_version = models.CharField(
			verbose_name="OS versjon",
			max_length=200,
			blank=True, null=True,
			help_text=u"",
			)
	comp_os_service_pack = models.CharField(
			verbose_name="OS service pack",
			max_length=200,
			blank=True, null=True,
			help_text=u"",
			)
	# med vilje er det ikke HistoricalRecords() på denne da den importeres

	def __str__(self):
		return u'%s' % (self.comp_name)

	class Meta:
		verbose_name_plural = "CMDB-enhet"
		default_permissions = ('add', 'change', 'delete', 'view')






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
	avtaletype = models.IntegerField(choices=AVTALETYPE_VALG,
			verbose_name="Avtaletype",
			blank=True, null=True,
			help_text=u"Hva slags kategori avtale er dette?",
			)
	intern_avtalereferanse = models.ManyToManyField("Avtale", related_name='avtale_intern_avtalereferanse',
			verbose_name="Intern avtaleavhengighet",
			blank=True,
			help_text=u"Databehandleravtaler er ofte forankret i SSA-avtaler.",
			)
	kortnavn = models.CharField(unique=True,
			verbose_name="Kortnavn på avtale",
			max_length=100,
			blank=False, null=False,
			help_text=u"Noe som er lett å søke opp. Maks 100 tegn. Må være unik",
			)
	for_system = models.ManyToManyField("System", related_name="avtale_for_system",
			verbose_name="Gjelder for følgende systemer",
			blank=True,
			help_text=u"Bruk dette feltet dersom denne avtalen spesifikt regulerer et tjenestekjøp eller 3.parts applikasjonsdrift. Dersom basisdrift og applikasjonsdrift/vedlikehold utføres av leverandøren tilhørende valgt driftsplattform lar du dette feltet stå tomt.",
			)
	beskrivelse = models.TextField(
			verbose_name="Detaljer om avtalen (fritekst)",
			blank=True, null=True,
			help_text=u"Her kan du utdype det du ønsker om avtalen",
			)
	virksomhet = models.ForeignKey(Virksomhet, related_name='databehandleravtale_virksomhet',
			on_delete=models.PROTECT,
			verbose_name="Avtalepart Oslo kommune (virksomhet)",
			blank=False, null=False,
			help_text=u"Den virksomhet som eier avtalen.",
			)
	avtaleansvarlig = models.ManyToManyField(Ansvarlig, related_name='databehandleravtale_avtaleansvarlig',
			verbose_name="Avtaleforvalter",
			blank=True,
			help_text=u"Den person (rolle) som forvalter avtalen.",
			)
	leverandor = models.ForeignKey(Leverandor, related_name='databehandleravtale_leverandor',
			on_delete=models.PROTECT,
			verbose_name="Avtalepart ekstern leverandør",
			blank=True, null=True,
			help_text=u"Brukes dersom avtalepart er en ekstern leverandør.",
			)
	leverandor_intern = models.ForeignKey(Virksomhet, related_name='databehandleravtale_leverandor_intern',
			on_delete=models.PROTECT,
			verbose_name="Avtalepart intern leverandør",
			blank=True, null=True,
			help_text=u"Brukes dersom avtalepart er en annen virksomhet i Oslo kommune.",
			)
	avtalereferanse = models.CharField(
			verbose_name="Avtalereferanse",
			max_length=600,
			blank=True, null=True,
			help_text=u"Avtalereferanse, helst referanse fra et arkivsystem. Referansen bør være unik i Oslo kommune.",
			)
	dokumenturl = models.URLField(
			verbose_name="Dokument-URL",
			max_length=400,
			blank=True, null=True,
			help_text=u"En URL til et annet system der avtalen kan leses.",
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
	kategorinavn = models.CharField(unique=True,
			verbose_name="Systemtypenavn",
			max_length=50,
			blank=False, null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True, null=True,
			help_text=u"Beskrivelse av kategori og noen eksempler.",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.kategorinavn)

	class Meta:
		verbose_name_plural = "Systemtyper"
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
	('FELLESSYSTEM', 'Fellessystem'),
	('FELLESSYSTEM-KANDIDAT', 'Fellessystemkandidat'),
	('SEKTORSYSTEM', 'Sektorsystem'),
	('VIRKSOMHETSSYSTEM', 'Virksomhetssystem'),
	('TVERRSEKTORIELT', 'Tverrsektorielt'),
	('FELLESREGISTER', 'Fellesregister (ikke bruk)'),
)

# må lage et script som inverterer verdiene i databasen 5 til 1 og 4 til 2 samtidig som disse inverteres.
VURDERINGER_SIKKERHET_VALG = (
	(1, '5 Svært alvorlig'),
	(2, '4 Alvorlig'),
	(3, '3 Moderat'),
	(4, '2 Lav'),
	(5, '1 Ubetydelig'),
)

VURDERINGER_TEKNISK_VALG = (
	(1, '1 Ingen'),
	(2, '2 Delvis'),
	(3, '3 Akseptabel'),
	(4, '4 God'),
	(5, '5 Meget god'),
)

VURDERINGER_STRATEGISK_VALG = (
	(1, '1 Ingen'),
	(2, '2 Delvis'),
	(3, '3 God knytning'),
	(4, '4 Tydelig knytning'),
	(5, '5 Sterk knytning'),
)

VURDERINGER_FUNKSJONELL_VALG = (
	(1, '1 Ikke akseptabel'),
	(2, '2 Store mangler'),
	(3, '3 Akseptabelt'),
	(4, '4 Godt egnet'),
	(5, '5 Meget godt egnet'),
)

PROGRAMVAREKATEGORI_VALG = (
	(1, 'Hyllevare'),
	(2, 'Tilpasset hyllevare'),
	(3, 'Egenutviklet'),
	(4, 'Skreddersøm'),
)

LIVSLOEP_VALG = (
	(1, '1 Under anskaffelse/utvikling'),
	(2, '2 Nytt og moderne, men fortsatt litt umodent'),
	(3, '3 Moderne og modent'),
	(4, '4 Modent, men ikke lengre moderne'),
	(5, '5 Bør/skal byttes ut'),
)

SELVBETJENING_VALG = (
	(1, 'Ja'),
	(2, 'Nei'),
	(3, 'Planlagt'),
)

SIKKERHETSNIVAA_VALG = (
	(1, 'Åpent'),
	(2, 'Internt'),
	(3, 'Sikret'),
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
	navn = models.CharField(unique=True,
			verbose_name="Navn på region",
			max_length=100,
			blank=False, null=False,
			help_text=u"F.eks. Norge, Norden, Europa/EØS, USA, Resten av verden",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True, null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Regioner"
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
	programvarenavn = models.CharField(unique=True,
			verbose_name="Programvarenavn",
			max_length=100,
			blank=False, null=False,
			help_text=u"",
			)
	programvarekategori = models.IntegerField(choices=PROGRAMVAREKATEGORI_VALG,
			verbose_name="Programvaretype",
			blank=True, null=True,
			help_text=u"",
			)
	programvaretyper = models.ManyToManyField(Systemtype, related_name='programvare_programvaretyper',
			verbose_name="Programvaretype(r)",
			blank=True,
			help_text=u"",
			)
	programvarebeskrivelse = models.TextField(
			verbose_name="Programvarebeskrivelse",
			blank=True, null=True,
			help_text=u"",
			)
	programvareleverandor = models.ManyToManyField(Leverandor, related_name='programvare_programvareleverandor',
			verbose_name="Programvareleverandør",
			blank=True,
			help_text=u"Leverandør av programvaren. Det vil ofte være en SSA-V (vedlikeholdsavtale) eller en SSA-B (bistandsavtale) knyttet til programvaren, men det kan også være en SSA-K (kjøpsavtale).",
			)
	kategorier = models.ManyToManyField(SystemKategori, related_name='programvare_systemkategorier',
			verbose_name="Kategori(er)",
			blank=True,
			help_text=u"")
	kommentar = models.TextField(
			verbose_name="Kommentar (fritekst)",
			blank=True, null=True,
			help_text=u"",
			)
	strategisk_egnethet = models.IntegerField(choices=VURDERINGER_STRATEGISK_VALG,
			verbose_name="Strategisk egnethet",
			blank=True, null=True,
			help_text=u"",
			)
	funksjonell_egnethet = models.IntegerField(choices=VURDERINGER_FUNKSJONELL_VALG,
			verbose_name="Funksjonell egnethet",
			blank=True, null=True,
			help_text=u"",
			)
	teknisk_egnethet = models.IntegerField(choices=VURDERINGER_TEKNISK_VALG,
			verbose_name="Teknisk egnethet",
			blank=True, null=True,
			help_text=u"",
			)
	selvbetjening = models.IntegerField(choices=SELVBETJENING_VALG,
			verbose_name="Selvbetjening",
			blank=True, null=True,
			help_text=u"Dersom ja betyr dette at systemet har et brukergrensesnitt der brukere selv kan registrere nødvendig informasjon i systemet.",
			)
	livslop_status = models.IntegerField(choices=LIVSLOEP_VALG,
			verbose_name="Livsløpstatus",
			blank=True, null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.programvarenavn)

	class Meta:
		verbose_name_plural = "Programvarer"
		default_permissions = ('add', 'change', 'delete', 'view')

class Driftsmodell(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	navn = models.CharField(
			verbose_name="Navn på driftsmodell", unique=True,
			max_length=100,
			blank=False, null=False,
			help_text=u"",
			)
	ansvarlig_virksomhet = models.ForeignKey(Virksomhet, related_name='driftsmodell_ansvarlig_virksomhet',
			on_delete=models.PROTECT,
			verbose_name="Forvalter (virksomhet)",
			blank=True, null=True,
			help_text=u"",
			)
	kommentar = models.TextField(
			verbose_name="Kommentarer til modellen",
			blank=True, null=True,
			help_text=u"Notater",
			)
	leverandor = models.ManyToManyField(Leverandor, related_name='driftsmodell_leverandor',
			verbose_name="Driftsleverandør",
			blank=True,
			)
	underleverandorer = models.ManyToManyField(Leverandor, related_name='driftsmodell_underleverandorer',
			verbose_name="Underleverandører av driftsleverandør",
			blank=True,
			)
	avtaler = models.ManyToManyField(Avtale, related_name='driftsmodell_avtaler',
			verbose_name="Avtalereferanser",
			blank=True,
			)
	databehandleravtale_notater = models.TextField(
			verbose_name="Status om databehandleravtale",
			blank=True, null=True,
			help_text=u"Tilleggsinformasjon databehandleravtale, inkludert beskrivelse av eventuelle avvik fra Oslo kommunes standard databehandleravtale.",
			)
	risikovurdering = models.URLField(
			verbose_name="Link til risikovurdering",
			max_length=600,
			blank=True, null=True,
			help_text=u"",
			)
	sikkerhetsnivaa = models.IntegerField(choices=SIKKERHETSNIVAA_VALG,
			verbose_name="Høyeste tillate sikkerhetsnivå",
			blank=True, null=True,
			help_text=u'Det høyeste sikkerhetsnivået modellen er godkjent for i hht <a target="_blank" href="https://confluence.oslo.kommune.no/x/y8seAw">Informasjonstyper og behandlingskrav</a>',
			)
	Tilgangsstyring_driftspersonell = models.TextField(
			verbose_name="Tilgangsstyring for driftspersonell og utviklere",
			blank=True, null=True,
			help_text=u"",
			)
	lokasjon_lagring_valgmeny = models.ManyToManyField(Region, related_name='driftsmodell_lokasjon_lagring_valgmeny',
			verbose_name="Lokasjon for lagring (valg)",
			blank=True,
			)
	lokasjon_lagring = models.TextField(
			verbose_name="Lokasjon for prosessering og lagring (utdyping)",
			blank=True, null=True,
			help_text=u"Hvilke land og soner prosessering og lagring finner sted.",
			)
	nettverk_segmentering = models.TextField(
			verbose_name="Designprinsipper for nettverkssegmentering",
			blank=True, null=True,
			help_text=u"Typisk ulike sikkerhetsnivå med regler for informasjonsflyt.",
			)
	nettverk_sammenkobling_fip = models.TextField(
			verbose_name="Kobling mot felles IKT-plattform",
			blank=True, null=True,
			help_text=u"Hvordan trafikk rutes backend fra plattformen til andre tjenester på felles IKT-plattform.",
			)
	sikkerhet_patching = models.TextField(
			verbose_name="Designprinsipper for patching",
			blank=True, null=True,
			help_text=u"Der aktuelt",
			)
	sikkerhet_antiskadevare = models.TextField(
			verbose_name="Designprinsipper for anti-skadevare (antivirus)",
			blank=True, null=True,
			help_text=u"Der aktuelt",
			)
	sikkerhet_backup = models.TextField(
			verbose_name="Designprinsipper for sikkerhetskopiering",
			blank=True, null=True,
			help_text=u"Der aktuelt",
			)
	sikkerhet_logging = models.TextField(
			verbose_name="Designprinsipper for logginnsamling",
			blank=True, null=True,
			help_text=u"",
			)
	sikkerhet_fysisk_sikring = models.TextField(
			verbose_name="Fysiske sikringstiltak",
			blank=True, null=True,
			help_text=u"Beskyttelse mot innbrudd, brann, oversvømmelse..",
			)
	anbefalte_kategorier_personopplysninger = models.ManyToManyField(Personsonopplysningskategori, related_name='driftsmodell_anbefalte_kategorier_personopplysninger',
			verbose_name="Kategorier personopplysninger egnet på plattformen",
			blank=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Driftsmodeller"
		default_permissions = ('add', 'change', 'delete', 'view')


class Autentiseringsmetode(models.Model):
	navn = models.CharField(
			verbose_name="Autentiseringsnivå", unique=True,
			max_length=100,
			blank=False, null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True, null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Autentiseringsmetoder"
		default_permissions = ('add', 'change', 'delete', 'view')


class Loggkategori(models.Model):
	navn = models.CharField(
			verbose_name="Loggtype", unique=True,
			max_length=100,
			blank=False, null=False,
			help_text=u"",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True, null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Loggkategorier"
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
	ibruk = models.NullBooleanField(
			verbose_name="Er systemet i bruk?",
			blank=True, null=True,
			help_text=u"Det kan være greit å beholde systemer i oversikten for å kunne søke dem opp. Alternativet er å slette systemet fra oversikten.",
			)
	informasjon_kvalitetssikret = models.BooleanField(
			verbose_name="Er informasjonen kvalitetssikret av forvalter?",
			default=False,
			help_text=u"Krysses av når ansvarlig har kontrollert at opplysningene oppgitt for dette systemet stemmer. Obligatoriske felter er de som automatisk er ekspandert.",
			)
	systemnavn = models.CharField(
			verbose_name="Systemnavn", unique=True,
			max_length=100,
			blank=False, null=False,
			help_text=u"Se <a target='_blank' href='/definisjon/System/'>definisjon av system</a>. Bruk feltet systemtype for å presisere kategori system. Det kan tidvis være vanskelig vite hvordan integrasjoner skal beskrives. Et eksempel er SvarUt. Det er et system levert av KS. Det er også integrasjoner på integrasjonsplattformen ITAS. Her gir det mening å registrere både SvarUt og SvarUt-integrasjon da de har forskjellige forvaltere. KS er en ekstern aktør og SvarUt-integrasjon er forvaltet av Oslo kommune. Det er egne felter her for å registrere systemintegrasjoner/informasjonsflyt inn og ut. F.eks. leverer folkeregistret data til infotoget, og infotorget leverer til DSF-integrasjon, og ulike systemer får data fra DSF-integrasjon.",
			)
	systembeskrivelse = models.TextField(
			verbose_name="Systembeskrivelse",
			blank=True, null=True,
			help_text=u"Tekstlig beskrivelse av hva systemet gjør/brukes til",
			)
	systemeier = models.ForeignKey(Virksomhet, related_name='systemer_systemeier',
			on_delete=models.SET_NULL,
			verbose_name="Organisatorisk systemeier",
			blank=True, null=True,
			help_text=u"For fellessystemer er dette normalt FIN. For sektorsystemer tilhører de nærmeste byrådsavdeling. For virksomhetssystemer typisk en konkret virksomhet.",
			)
	systemeier_kontaktpersoner_referanse = models.ManyToManyField(Ansvarlig, related_name='system_systemeier_kontaktpersoner',
			verbose_name="Systemeier (personer)",
			blank=True,
			help_text=u"Person(er) med operativt systemeierskap",
			)
	systemforvalter = models.ForeignKey(Virksomhet, related_name='systemer_systemforvalter',
			on_delete=models.SET_NULL,
			verbose_name="Organisatorisk systemforvalter",
			blank=True, null=True,
			)
	systemforvalter_kontaktpersoner_referanse = models.ManyToManyField(Ansvarlig, related_name='system_systemforvalter_kontaktpersoner',
			verbose_name="Systemforvalter (personer)",
			blank=True,
			help_text=u"Person(er) med operativt forvalteransvar",
			)
	superbrukere = models.TextField(
			verbose_name="Superbrukere",
			blank=True, null=True,
			help_text=u"Personer som kjenner systemet godt. I mange tilfeller har disse administratortilganger. Dette er personer som egner seg godt når systemet må testes grunnet endringer.",
			)
	nokkelpersonell = models.TextField(
			verbose_name="Nøkkelpersonell",
			blank=True, null=True,
			help_text=u"Viktige personer fra leverandører og tilsvarende",
			)
	driftsmodell_foreignkey = models.ForeignKey(Driftsmodell, related_name='system_driftsmodell',
			on_delete=models.PROTECT,
			verbose_name="Driftsmodell / plattform",
			blank=True, null=True,
			help_text=u"Angivelse av driftsplattform systemet kjører på. Ved kjøp som tjeneste bruk SaaS.",
			)
	leveransemodell_fip = models.IntegerField(choices=LEVERANSEMODELL_VALG,
			verbose_name="Leveransemodell (for felles IKT-plattform)",
			blank=True, null=True,
			help_text=u'Brukes ifm migreringsprosjektet',
			)
	tjenestenivaa = models.CharField(
			verbose_name="Tjenestenivå med UKE (gamle tjenesteavtaler)", choices=TJENESTENIVAA_VALG,
			max_length=50,
			blank=True, null=True,
			help_text=u"Gammelt nivå for oppetidsgaranti (gull, sølv og brosje)",
			)
	cmdbref_prod = models.ForeignKey(CMDBRef, related_name='system_cmdbref_prod',
			on_delete=models.PROTECT,
			verbose_name="Referanse til CMDB: Produksjon",
			blank=True, null=True,
			help_text=u"Kobling til Sopra Steria CMDB for Produksjon. Denne brukes for å vise tjenestenivå til systemet.",
			)
	cmdbref = models.ManyToManyField(CMDBRef, related_name='system_cmdbref',
			verbose_name="Referanse til CMDB: Test og annet",
			blank=True,
			help_text=u"Kobling til Sopra Steria CMDB for test, kurs osv",
			)
	sikkerhetsnivaa = models.IntegerField(choices=SIKKERHETSNIVAA_VALG,
			verbose_name="Sikkerhetsnivå til systemet",
			blank=True, null=True,
			help_text=u'Sikkerhetsnivå for felles IKT-plattform i hht <a target="_blank" href="https://confluence.oslo.kommune.no/x/y8seAw">Informasjonstyper og behandlingskrav</a>',
			)
	programvarer = models.ManyToManyField(Programvare, related_name='system_programvarer',
			verbose_name="Programvarer benyttet",
			blank=True,
			help_text=u"Programvarer benyttet i systemet",
			)
	database = models.IntegerField(
			verbose_name="Database", choices=DB_VALG,
			blank=True, null=True,
			help_text=u"Ikke fyll ut denne, legg heller databasen som en teknisk avhengighet",
			)
	avhengigheter = models.TextField(
			verbose_name="Utlevering og avhengigheter (fritekst)",
			blank=True, null=True,
			help_text=u"Her kan du gi utdypende beskrivelser til feltene som omhandler utlevering og systemtekniske avhengigeheter.",
			)
	avhengigheter_referanser = models.ManyToManyField("System", related_name='system_avhengigheter_referanser',
			verbose_name="Systemtekniske avhengigheter til andre systemer",
			blank=True,
			help_text=u"Her lister du opp andre systemer dette systemet er avhengig av, da utover at det overføres personopplysninger. F.eks. pålogginssystemer (AD, FEIDE, ID-porten..), databasehotell (Oracle, MSSQL..) eller RPA-prosesser.",
			)
	datautveksling_mottar_fra = models.ManyToManyField("System", related_name='system_datautveksling_mottar_fra',
			verbose_name="Mottar personopplysninger fra følgende systemer",
			blank=True,
			help_text=u"Her lister du opp systemer dette systemet mottar personopplysinger fra. Dersom overføringen skjer via en integrasjon, velges integrasjonen her. Valg her vises blant annet i systemets DPIA.",
			)
	datautveksling_avleverer_til = models.ManyToManyField("System", related_name='system_datautveksling_avleverer_til',
			verbose_name="Avleverer personopplysninger til følgende systemer",
			blank=True,
			help_text=u"Her lister du opp systemer dette systemet avleverer personopplysinger til. Dersom overføringen skjer via en integrasjon, velges integrasjonen her. Valg her vises blant annet i systemets DPIA.",
			)
	systemeierskapsmodell = models.CharField(choices=SYSTEMEIERSKAPSMODELL_VALG,
			verbose_name="Systemklassifisering",
			max_length=50,
			blank=True, null=True,
			help_text=u"I henhold til Oslo kommunes IKT-reglement.",
			)
	programvarekategori = models.IntegerField(choices=PROGRAMVAREKATEGORI_VALG,
			verbose_name="Programvaretype (flyttet til programvare)",
			blank=True, null=True,
			help_text=u"Anbefaler at du heller registrerer programvare og knytter programvaren til systemet.",
			)
	systemtyper = models.ManyToManyField(Systemtype, related_name='system_systemtyper',
			verbose_name="Systemtype / menneskelig grensesnitt",
			blank=True,
			help_text=u"Her beskriver hva slags type system dette er. Merk særlig dette feltet dersom systemet er en integrasjon eller infrastrukturkomponent.",
			)
	systemkategorier = models.ManyToManyField(SystemKategori, related_name='system_systemkategorier',
			verbose_name="Systemkategori(er)",
			blank=True,
			help_text=u"Dette er et sett med kategorier som forvaltes av UKE ved seksjon for information management (IM). Velg det som passer best.",
			)
	systemurl = models.ManyToManyField(SystemUrl, related_name='system_systemurl',
			verbose_name="URL (dersom webtjeneste)",
			blank=True,
			default=None,
			help_text=u"Adressen systemet nås på via nettleser",
			)
	systemleverandor = models.ManyToManyField(Leverandor, related_name='system_systemleverandor',
			verbose_name="Tjeneste / systemleverandør",
			blank=True,
			help_text=u"Fylles ut når tjenesten kjøpes av en leverandør (SaaS). Tilsvarer typisk SSA-L (løpende tjenestekjøp). For systemer lagt inn tidlig i denne databasen er dette feltet benyttet tilsvarende \"programvareleverandør\". Programvareleverandør kan nå knyttes til systemet indirekte ved å registrere programvaren til systemet.",
			)
	basisdriftleverandor = models.ManyToManyField(Leverandor, related_name='system_driftsleverandor',
			verbose_name="Leverandør av basisdrift",
			blank=True,
			help_text=u"Leverandør som drifter maskinparken systmet kjører på. Tilsvarer typisk SSA-D. Trengs ikke fylles ut for systmer som kjøpes som en tjeneste av eksterne leverandører.",
			)
	applikasjonsdriftleverandor = models.ManyToManyField(Leverandor,
			verbose_name="Leverandør av applikasjonsdrift", related_name='system_applikasjonsdriftleverandor',
			blank=True,
			help_text=u"Leverandør som sørger for at systemet fungerer som det skal. Kan f.eks. være en leverandør på en SSA-D (driftsavtale) eller SSA-B (bistandsavtale). Bør ikke fylles ut for systemer som kjøpes som en tjeneste av eksterne leverandører.",
			)
	datamodell_url = models.URLField(
			verbose_name="Datamodell (link)",
			max_length=600,
			blank=True, null=True,
			help_text=u"Link til beskrivelse av datamodell",
			)
	datasett_url = models.URLField(
			verbose_name="Datasett (link)",
			max_length=600,
			blank=True, null=True,
			help_text=u"Link til beskrivelse av datasett",
			)
	api_url = models.URLField(
			verbose_name="API (link)",
			max_length=600,
			blank=True, null=True,
			help_text=u"Link til beskrivelse av API",
			)
	kildekode_url = models.URLField(
			verbose_name="Kildekode (link)",
			max_length=600,
			blank=True, null=True,
			help_text=u"Link til kildekode",
			)
	kontaktgruppe_url = models.URLField(
			verbose_name="Kontaktgruppe / Workplace",
			max_length=600,
			blank=True, null=True,
			help_text=u"Link til gruppe på workplace eller f.eks. en intranettside.",
			)
	high_level_design_url = models.URLField(
			verbose_name="Systemdokumentasjon (HighLevelDesign) (link)",
			max_length=600,
			blank=True, null=True,
			help_text=u"High level design",
			)
	low_level_design_url = models.URLField(
			verbose_name="Driftsdokumentasjon (LowLevelDesign) (link)",
			max_length=600,
			blank=True, null=True,
			help_text=u"Low level design",
			)
	brukerdokumentasjon_url = models.URLField(
			verbose_name="Brukerdokumentasjon (link)",
			max_length=600,
			blank=True, null=True,
			help_text=u"Link til brukerdokumentasjon",
			)
	kommentar = models.TextField(
			verbose_name="Kommentar (fritekst) (fases ut)",
			blank=True, null=True,
			help_text=u"Ikke bruk dette feltet",
			)
	selvbetjening = models.IntegerField(choices=SELVBETJENING_VALG,
			verbose_name="Selvbetjening (fases ut)",
			blank=True, null=True,
			help_text=u"Dersom ja betyr dette at systemet har et brukergrensesnitt der brukere selv kan registrere nødvendig informasjon i systemet.",
			)
	livslop_status = models.IntegerField(choices=LIVSLOEP_VALG,
			verbose_name="Livsløpstatus",
			blank=True, null=True,
			help_text=u"Om systemet er nytt, moderne eller skal fases ut",
			)
	strategisk_egnethet = models.IntegerField(choices=VURDERINGER_STRATEGISK_VALG,
			verbose_name="Strategisk egnethet (fases ut)",
			blank=True, null=True,
			help_text=u"Hvor viktig systemet er opp mot virksomhetens oppdrag",
			)
	funksjonell_egnethet = models.IntegerField(choices=VURDERINGER_FUNKSJONELL_VALG,
			verbose_name="Funksjonell egnethet",
			blank=True, null=True,
			help_text=u"Hvor godt systemet løser behovet",
			)
	teknisk_egnethet = models.IntegerField(choices=VURDERINGER_TEKNISK_VALG,
			verbose_name="Teknisk egnethet",
			blank=True, null=True,
			help_text=u"Moderne teknologi eller masse teknisk gjeld?",
			)
	konfidensialitetsvurdering = models.IntegerField(choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Oppsummert konfidensialitetsvurdering",
			blank=True, null=True,
			help_text=u"Oppsummert: Hvor sensitive er opplysningene?",
			)
	integritetsvurdering = models.IntegerField(choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Oppsummert integritetsvurdering",
			blank=True, null=True,
			help_text=u"Oppsummert: Hvor kritisk er det at opplysningene stemmer?",
			)
	tilgjengelighetsvurdering = models.IntegerField(choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Oppsummert tilgjengelighetsvurdering",
			blank=True, null=True,
			help_text=u"Oppsummert: Hvor kritisk er det om systemet ikke virker?",
			)
	tilgjengelighet_kritiske_perioder = models.TextField(
			verbose_name="Utdypning tilgjengelighet: Kritiske perioder",
			blank=True, null=True,
			help_text=u"Her legger du inn perioder av året hvor det er særskilt behov for at systemet er tilgjengelig. F.eks. knyttet til frister som eiendomsskatt, barnehageopptak eller lønnskjøring.",
			)
	url_risikovurdering = models.URLField(
			verbose_name="Risikovurdering (URL)",
			blank=True, null=True,
			help_text=u"URL-referanse dersom det finnes. Om ikke kan fritekstfeltet under benyttes.",
			)
	risikovurdering_tekst = models.TextField(
			verbose_name="Risikovurdering fritekst",
			blank=True, null=True,
			help_text=u"Ytterligere detaljer knyttet til gjennomføringen av risikovurdering for systemet.",
			)
	dato_sist_ros = models.DateTimeField(
			verbose_name="Dato sist gjennomførte risikovurdering",
			blank=True, null=True,
			help_text=u"YYYY-MM-DD eksempel 2019-05-05 (tidspunkt er påkrevet - sett 'Nå')",
			)
	systemtekniske_sikkerhetstiltak = models.TextField(
			verbose_name="Systemtekniske sikkerhetstiltak (oppsummering)",
			blank=True, null=True,
			help_text=u"fases ut til fordel for mer detaljerte spørsmål under.",
			)
	autentiseringsalternativer = models.ManyToManyField(Autentiseringsmetode,
			verbose_name="Autentiseringsalternativer", related_name='system_autentiseringsalternativer',
			blank=True,
			help_text=u"Valg av måter bruker autentiserer seg på",
			)
	loggingalternativer = models.ManyToManyField(Loggkategori,
			verbose_name="Etablerte logger i systemet", related_name='system_loggingalternativer',
			blank=True,
			help_text=u"Nivå av logging etablert i systemet",
			)
	autorisasjon_differensiering_beskrivelse = models.TextField(
			verbose_name="Differensiering av tilganger med bakgrunn i roller/identitet",
			blank=True, null=True,
			help_text=u"Beskriv mulighetene for å differensiere tilganger med bakgrunn i roller/identitet.",
			)
	autorisasjon_differensiering_saksalder = models.TextField(
			verbose_name="Differensiering av tilganger med bakgrunn i sakenes alder",
			blank=True, null=True,
			help_text=u"Beskriv mulighetene for å differensiere tilganger med bakgrunn i sakenes alder ",
			)
	dataminimalisering = models.TextField(
			verbose_name="Dataminimalisering",
			blank=True, null=True,
			help_text=u"Beskriv systemets funksjonalitet for å sikre dataminimalisering",
			)
	sletting_av_personopplysninger = models.TextField(
			verbose_name="Sletting av personopplysninger",
			blank=True, null=True,
			help_text=u"(Redundant med felt på behandling) Beskriv systemets funksjonalitet for sletting av personopplysninger",
			)
	funksjonalitet_kryptering = models.TextField(
			verbose_name="Funksjonalitet for kryptering",
			blank=True, null=True,
			help_text=u"Beskriv funksjonalitet for kryptering (hva krypteres og hvordan, både for transport/overføring og ved lagring)",
			)
	anonymisering_pseudonymisering = models.TextField(
			verbose_name="Anonymisering og pseudonymisering",
			blank=True, null=True,
			help_text=u"(Redundant med felt på behandling) Beskriv funksjonalitet for anonymisering / pseudonymisering ved bruk av personopplysninger til andre formål ",
			)
	sikkerhetsmessig_overvaaking = models.TextField(
			verbose_name="Sikkerhetsovervåking",
			blank=True, null=True,
			help_text=u"Beskriv hva slags aktiv overvåking av logger og hendelser som gjelder for systemet. Hvem utfører dette og hvor ofte?",
			)
	kontaktperson_innsyn = models.ManyToManyField(Ansvarlig, related_name='system_kontaktperson_innsyn',
			verbose_name="Kontaktperson innsyn",
			blank=True,
			help_text=u"Person som kan kontaktes for å undersøke om det er personopplysninger i systemet knyttet til en innsynsbegjæring.",
			)
	kjente_mangler = models.TextField(
			verbose_name="Kjente mangler i systemet",
			blank=True, null=True,
			help_text=u"Felt forvalter kan benytte for å notere ned kjente mangler.",
			)
	informasjonsklassifisering = models.ManyToManyField(InformasjonsKlasse, related_name='system_informasjonsklassifisering',
			verbose_name="Informasjonsklassifisering",
			blank=True,
			help_text=u"Velg de kategorier som er aktuelle.",
			)
	isolert_drift = models.BooleanField(
			verbose_name="På Tilpasset drift (felles IKT-plattform)",
			default=False,
			help_text=u"Krysses av dersom systemet ikke kan oppgraderes og derfor er spesielt adskilt fra andre systemer på plattformen.",
			)
	history = HistoricalRecords()

	def __str__(self):
		if self.ibruk == False:
			return u'%s (%s)' % (self.systemnavn, "avviklet")
		else:
			return u'%s' % (self.systemnavn)


	def felles_sektorsystem(self):
		if self.systemeierskapsmodell in ("FELLESSYSTEM", "SEKTORSYSTEM", "TVERRSEKTORIELT"):
			return True
		else:
			return False

	def fip_kritikalitet(self):
		if self.cmdbref_prod:
			return self.cmdbref_prod.kritikalitet
		else:
			return None

	def fip_kritikalitet_text(self):
		if self.cmdbref_prod:
			return self.cmdbref_prod.get_kritikalitet_display()
		else:
			return None

	class Meta:
		verbose_name_plural = "Systemer"
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
	systemer = models.ManyToManyField(System, related_name='sikkerhetstest_systemer',
			verbose_name="Systemer testet",
			blank=True,
			)
	type_test = models.IntegerField(choices=TYPE_SIKKERHETSTEST,
			verbose_name="Type sikkerhetstest",
			blank=True, null=True,
			help_text=u"Velg mest aktuelle som definert på <a href='https://confluence.oslo.kommune.no/x/eww4B'>Confluence</a>",
			)
	rapport = models.URLField(
			verbose_name="Link til rapport",
			max_length=600,
			blank=True, null=True,
			help_text=u"F.eks. på confluence eller til et arkivsystem",
			)
	dato_rapport = models.DateTimeField(
			verbose_name="Dato for sluttføring av rapport",
			blank=True, null=True,
			help_text=u"(tidspunkt er påkrevet - sett 'Nå')"
			)
	testet_av = models.ForeignKey(Leverandor, related_name='sikkerhetstest_testet_av',
			on_delete=models.PROTECT,
			verbose_name="Testet av (leverandør)",
			null=True, blank=True,
			help_text=u'Leverandør som har utført testen',
			)
	notater = models.TextField(
			verbose_name="Omfang av test og andre notater",
			blank=True, null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s: %s' % (self.testet_av, self.dato_rapport)

	class Meta:
		verbose_name_plural = "Sikkerhetstester"
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
	for_system = models.OneToOneField(System, related_name='DPIA_for_system',
			on_delete=models.PROTECT,
			verbose_name="DPIA for system (personvernvurderinger)",
			blank=False, null=True,
			)
	sist_gjennomforing_dpia = models.DateTimeField(
			verbose_name="Dato siste vurdering",
			blank=True, null=True,
			help_text=u"Når ble personvernkonsekvenser for systemet sist vurdert (tidspunkt er påkrevet - sett 'Nå')",
			)
	url_dpia = models.URLField(
			verbose_name="Arkivlink til godkjenningen av DPIA for dette systemet",
			max_length=600,
			blank=True, null=True,
			help_text=u"Oppbevares i et arkivsystem eller annet egnet sted",
			)
	kommentar = models.TextField(
			verbose_name="Arbeidsnotater til DPIA-arbeidet",
			blank=True, null=True,
			help_text=u"",
			)
	#trinn 2
	knyttning_identifiserbare_personer = models.TextField(
			verbose_name="Kan informasjonen på noen måte knyttes til identifiserbare personer (enten direkte eller via personnummer eller andre identifikatorer)?",
			blank=True, null=True,
			help_text=u"",
			)
	innhentet_dpia = models.TextField(
			verbose_name="Er det innhentet DPIA for mottakende systemer? Beskriv hvilke som er gjennomgått.",
			blank=True, null=True,
			help_text=u"",
			)
	teknologi = models.TextField(
			verbose_name="Hva slags teknologi skal benyttes?",
			blank=True, null=True,
			help_text=u"",
			)
	ny_endret_teknologi = models.TextField(
			verbose_name="Innebærer behandlingen på noen måte bruk av ny/endret teknologi?",
			blank=True, null=True,
			help_text=u"",
			)
	kjente_problemer_teknologien = models.TextField(
			verbose_name="Er det noen offentlig kjente problemer med teknologien det bør tas hensyn til?",
			blank=True, null=True,
			help_text=u"",
			)
	#trinn 3
	konsultasjon_registrerte = models.TextField(
			verbose_name="Har det vært en konsultasjonsprosess med de registrerte/de registreres interesseorganisasjoner? f.eks. fagforeninger, brukergrupper, pasientorganisasjoner. Hvordan og når ble konsultasjonen med de registrerte/de registreres interesseorganisasjoner gjennomført? Hvis NEI, må dette begrunnes nærmere.",
			blank=True, null=True,
			help_text=u"",
			)
	konsultasjon_registrerte_oppsummering = models.TextField(
			verbose_name="Oppsummering av de råd m.m. som kom etter konsultasjoner med de registrerte / interessegrupper som representerer de registrerte.",
			blank=True, null=True,
			help_text=u"",
			)
	konsultasjon_internt = models.TextField(
			verbose_name="Hvem internt er konsultert/involvert i planleggingen (IKT, jurister, fagpersoner, m.m.)?",
			blank=True, null=True,
			help_text=u"",
			)
	konsultasjon_internt_oppsummering = models.TextField(
			verbose_name="Oppsummering av de råd m.m. som kom etter konsultasjoner av interne ressurser:",
			blank=True, null=True,
			help_text=u"",
			)
	konsultasjon_databehandlere = models.TextField(
			verbose_name="Er databehandlere konsultert/involvert i planleggingen?",
			blank=True, null=True,
			help_text=u"",
			)
	konsultasjon_databehandlere_oppsummering = models.TextField(
			verbose_name="Oppsummering av de råd m.m. som kom etter konsultasjoner av databehandler.",
			blank=True, null=True,
			help_text=u"",
			)
	konsultasjon_eksterne = models.TextField(
			verbose_name="Er løsningen gjennomgått av eksterne eksperter (f.eks. eksperter på informasjonssikkerhet, jurister, fagpersoner)?",
			blank=True, null=True,
			help_text=u"",
			)
	konsultasjon_eksterne_oppsummering = models.TextField(
			verbose_name="Oppsummering av de råd m.m. som kom etter konsultasjoner av eksterne resurser.",
			blank=True, null=True,
			help_text=u"",
			)
	#trinn 4
	hoveddatabehandler = models.TextField(
			verbose_name="Hvem er hoveddatabehandler?",
			blank=True, null=True,
			help_text=u"",
			)
	#trinn 5
	personvern_i_risikovurdering = models.TextField(
			verbose_name="Er risikoen til individet beskrivet/ivaretatt i systemets risikovurdering?",
			blank=True, null=True,
			help_text=u"Ja/Nei-felt?",
			)

	#trinn 6
	tiltak_innledende_ros = models.TextField(
			verbose_name="Oppsummering av resultat av innledende risikovurdering.",
			blank=True, null=True,
			help_text=u"",
			)
	tiltak_etter_ytterligere_tiltak = models.TextField(
			verbose_name="Oppsummering av risikovurdering etter ytterligere risikovurderende tiltak.",
			blank=True, null=True,
			help_text=u"",
			)
	tiltak_forhandsdroftelser = models.TextField(
			verbose_name="Oppsummering av resultatet av forhåndsdrøftelse med Datatilsynet.",
			blank=True, null=True,
			help_text=u"",
			)

	#trinn 7
	godkjenning_personvernombudets_raad = models.TextField(
			verbose_name="Personvernombudets råd er innhentet (oppsummering av råd).",
			blank=True, null=True,
			help_text=u"Bør dette punktet inn under trinn 3?",
			)
	godkjenning_tiltak_restrisiko = models.TextField(
			verbose_name="Anbefalte tiltak og restrisiko godkjent (av hvem og når).",
			blank=True, null=True,
			help_text=u"",
			)
	godkjenning_datatilsynet = models.URLField(
			verbose_name="Datatilsynets godkjennelse ved «Uakseptabel» restrisiko (link).",
			blank=True, null=True,
			help_text=u"",
			)
	history = HistoricalRecords()


	def __str__(self):
		return u'DPIA for %s' % (self.for_system)

	class Meta:
		verbose_name_plural = "DPIA"
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
	brukergruppe = models.ForeignKey(Virksomhet,
			on_delete=models.PROTECT,
			blank=False, null=False,
			related_name='programvarebruk_brukergruppe',
			)
	programvare = models.ForeignKey(Programvare,
			on_delete=models.CASCADE,  # slett ProgramvareBruken når Programvaren slettes
			related_name='programvarebruk_programvare',
			blank=False, null=False,
			)
	livslop_status = models.IntegerField(choices=LIVSLOEP_VALG,
			verbose_name="Livsløpstatus",
			blank=True, null=True,
			help_text=u"",
			)
	kommentar = models.TextField(
			verbose_name="Kommentarer til denne bruken",
			blank=True, null=True,
			help_text=u"Utdyp hva programvaren brukes til hos din virksomhet.",
			)
	programvareeierskap = models.TextField(
			verbose_name="Programvareeierskap (fritekst)",
			blank=True, null=True,
			help_text=u"",
			)
	antall_brukere = models.IntegerField(
			verbose_name="Antall brukere",
			blank=True, null=True,
			help_text=u"Hvor mange bruker programvaren?",
			)
	avtaletype = models.CharField(
			verbose_name="Avtaletype",
			max_length=250,
			blank=True, null=True,
			help_text=u"",
			)
	avtalestatus = models.IntegerField(choices=VURDERING_AVTALESTATUS_VALG,
			verbose_name="Avtalestatus",
			blank=True, null=True,
			help_text=u"",
			)
	avtale_kan_avropes = models.NullBooleanField(
			verbose_name="Avtale kan avropes av andre virksomheter",
			blank=True, null=True,
			help_text=u"",
			)
	borger = models.IntegerField(choices=IBRUK_VALG,
			verbose_name="For borger?",
			blank=True, null=True,
			help_text=u"",
			)
	kostnader = models.IntegerField(
			verbose_name="Kostnader for programvaren",
			blank=True, null=True,
			help_text=u"",
			)
	strategisk_egnethet = models.IntegerField(choices=VURDERINGER_STRATEGISK_VALG,
			verbose_name="Strategisk egnethet",
			blank=True, null=True,
			help_text=u"",
			)
	funksjonell_egnethet = models.IntegerField(choices=VURDERINGER_FUNKSJONELL_VALG,
			verbose_name="Funksjonell egnethet",
			blank=True, null=True,
			help_text=u"",
			)
	teknisk_egnethet = models.IntegerField(choices=VURDERINGER_TEKNISK_VALG,
			verbose_name="Teknisk egnethet",
			blank=True, null=True,
			help_text=u"",
			)
	programvareleverandor = models.ManyToManyField(Leverandor, related_name='programvarebruk_programvareleverandor',
			verbose_name="Programvareleverandør",
			blank=True,
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s - %s' % (self.programvare, self.brukergruppe)

	class Meta:
		verbose_name_plural = "Programvarebruk"
		unique_together = ('programvare', 'brukergruppe')
		default_permissions = ('add', 'change', 'delete', 'view')



class SystemBruk(models.Model):
	sist_oppdatert = models.DateTimeField(
			verbose_name="Sist oppdatert",
			auto_now=True,
			)
	brukergruppe = models.ForeignKey(Virksomhet, related_name='systembruk_brukergruppe',
			verbose_name="Brukergruppe",
			on_delete=models.PROTECT,
			blank=False, null=False,
			)
	system = models.ForeignKey(System, related_name='systembruk_system',
			verbose_name="System som brukes",
			blank=False, null=False,
			on_delete=models.CASCADE,  # slett SystemBruken når Systemet slettes
			)
	del_behandlinger = models.BooleanField(
			verbose_name="Abonner på felles behandlinger i systemet",
			blank=True, default=False,
			help_text=u"Krysser du av på denne, vil alle felles behandlinger for systemet havne i din behandlingsprotokoll",
			)
	systemforvalter = models.ForeignKey(Virksomhet, related_name='systembruk_systemforvalter',
			on_delete=models.SET_NULL,
			verbose_name="Lokal forvalter (virksomhet)",
			blank=True, null=True,
			help_text=u"Fylles bare ut for fellesløsninger på applikasjonshotell der eierskapet er lokalt.",
			)
	systemforvalter_kontaktpersoner_referanse = models.ManyToManyField(Ansvarlig, related_name='systembruk_systemforvalter_kontaktpersoner',
			verbose_name="Lokal forvalter (person)",
			blank=True,
			help_text=u"Dersom fellesløsning på applikasjonshotell, hvilke roller/personer fyller rollen som forvalter?",
			)
	livslop_status = models.IntegerField(choices=LIVSLOEP_VALG,
			verbose_name="Livsløpstatus",
			blank=True, null=True,
			help_text=u"",
			)
	avhengigheter_referanser = models.ManyToManyField("System", related_name='systembruk_avhengigheter_referanser',
			verbose_name="Systemtekniske avhengigheter til andre systemer",
			blank=True,
			help_text=u"Andre systemer dette systemet har systemtekniske avhengigheter til.",
			)
	avhengigheter = models.TextField(
			verbose_name="Avhengigheter (fritekst)",
			blank=True, null=True,
			help_text=u"Moduler og eksterne/interne integrasjoner som er i bruk",
			)
	kommentar = models.TextField(
			verbose_name="Kommentarer til denne bruken",
			blank=True, null=True,
			help_text=u"Utdyp hva systemet brukes til hos din virksomhet.",
			)
	systemeierskap = models.TextField(
			verbose_name="Systemeierskap (fritekst)",
			blank=True, null=True,
			help_text=u"Hvis det er behov for å presisere eierskapet utover det som står på systemsiden.")
	#systemleverandor = models.ManyToManyField(Leverandor, related_name='systembruk_systemleverandor',
	#		verbose_name="Systemleverandør",
	#		blank=True,
	#		)
	driftsmodell_foreignkey = models.ForeignKey(Driftsmodell, related_name='systembruk_driftsmodell',
			on_delete=models.PROTECT,
			verbose_name="Driftsmodell / plattform (for denne bruken)",
			blank=True, null=True,
			help_text=u"Dette feltet blir faset ut. Dette er spesifisert på systemet.",
			)
	#antall_brukere = models.IntegerField(
	#		verbose_name="Antall brukere",
	#		blank=True, null=True,
	#		help_text=u"Hvor mange brukere har dere av systemet?",
	#		)
	konfidensialitetsvurdering = models.IntegerField(choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Konfidensialitetsvurdering",
			blank=True, null=True,
			help_text=u"Hvor sensitive er opplysningene?",
			)
	integritetsvurdering = models.IntegerField(choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Integritetsvurdering",
			blank=True, null=True,
			help_text=u"Hvor kritisk er det at opplysningene stemmer?",
			)
	tilgjengelighetsvurdering = models.IntegerField(choices=VURDERINGER_SIKKERHET_VALG,
			verbose_name="Tilgjengelighetsvurdering",
			blank=True, null=True,
			help_text=u"Hvor kritisk er det om systemet ikke virker?",
			)
	avtaletype = models.CharField(
			verbose_name="Avtaletype (fritekst)",
			max_length=250,
			blank=True, null=True,
			help_text=u"",
			)
	avtalestatus = models.IntegerField(choices=VURDERING_AVTALESTATUS_VALG,
			verbose_name="Avtalestatus",
			blank=True, null=True,
			help_text=u"",
			)
	avtale_kan_avropes = models.NullBooleanField(
			verbose_name="Avtale kan avropes av andre virksomheter",
			blank=True, null=True,
			help_text=u"",
			)
	#borger = models.IntegerField(blank=True, null=True, choices=IBRUK_VALG,
	#		verbose_name="For borger?",
	#		help_text=u"",
	#		)
	kostnadersystem = models.IntegerField(
			verbose_name="Kostnader for system",
			blank=True, null=True, help_text=u"",
			)
	systemeierskapsmodell = models.CharField(choices=SYSTEMEIERSKAPSMODELL_VALG,
			verbose_name="Systemeierskapsmodell",
			max_length=30,
			blank=True, null=True,
			help_text=u"Feltet skal avvikles da dette settes på systemet, ikke bruken",
			)
	programvarekategori = models.IntegerField(choices=PROGRAMVAREKATEGORI_VALG,
			verbose_name="Programvarekategori",
			blank=True, null=True,
			help_text=u"Feltet skal avvikles. Har ikke noe her å gjøre.",
			)
	strategisk_egnethet = models.IntegerField(choices=VURDERINGER_STRATEGISK_VALG,
			verbose_name="Strategisk egnethet",
			blank=True, null=True,
			help_text=u"",
			)
	funksjonell_egnethet = models.IntegerField(choices=VURDERINGER_FUNKSJONELL_VALG,
			verbose_name="Funksjonell egnethet",
			blank=True, null=True,
			help_text=u"",
			)
	teknisk_egnethet = models.IntegerField(choices=VURDERINGER_TEKNISK_VALG,
			verbose_name="Teknisk egnethet",
			blank=True, null=True,
			help_text=u"",
			)
	url_risikovurdering = models.URLField(
			verbose_name="Risikovurdering (URL)",
			blank=True, null=True,
			help_text=u"URL-referanse dersom det finnes. Om ikke kan fritekstfeltet under benyttes.",
			)
	risikovurdering_tekst = models.TextField(
			verbose_name="Risikovurdering fritekst",
			blank=True, null=True,
			help_text=u"Ytterligere detaljer knyttet til gjennomføringen av risikovurdering for systemet.",
			)
	dato_sist_ros = models.DateTimeField(
			verbose_name="Dato sist gjennomførte risikovurdering",
			blank=True, null=True,
			help_text=u"(tidspunkt er påkrevet - sett 'Nå')",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s - %s' % (self.system, self.brukergruppe)

	class Meta:
		verbose_name_plural = "Systembruk"
		unique_together = ('system', 'brukergruppe')
		default_permissions = ('add', 'change', 'delete', 'view')

	#def antall_behandlinger_virksomhet(self):
	# må generalisere denne fuksjonen..
	#	return BehandlingerPersonopplysninger.objects.filter(behandlingsansvarlig=self.virksomhet_pk).filter(systemer=bruk.system.pk).count()


class RegistrertKlassifisering(models.Model):
	navn = models.CharField(unique=True,
			verbose_name="Klassifikasjon",
			max_length=100,
			blank=False, null=False,
			help_text=u"F.eks. \"Særlige sårbare personer\", \"Vanlige personer\" og \"Profesjonelle aktører\".",
			)
	definisjon = models.TextField(
			verbose_name="Definisjon",
			blank=True, null=True,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Klassifisering av registrerte"
		default_permissions = ('add', 'change', 'delete', 'view')



class RelasjonRegistrert(models.Model):
	navn = models.CharField(unique=True,
			verbose_name="Navn på valg",
			max_length=150,
			blank=False, null=False,
			help_text=u"",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s' % (self.navn)

	class Meta:
		verbose_name_plural = "Relasjoner til den registrerte"
		default_permissions = ('add', 'change', 'delete', 'view')


BEHANDLING_VALGFRIHET = (
	(1, 'Stor valgfrihet'),
	(2, 'Middels valgfrihet'),
	(3, 'Ingen valgfrihet'),
)


class BehandlingerPersonopplysninger(models.Model):
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
			help_text=u"Krysses av når denne behandlingen er klar i første versjon.",
			)
	oppdateringsansvarlig = models.ManyToManyField(Ansvarlig, related_name='behandling_kontaktperson',
			verbose_name="Oppdateringsansvarlig",
			blank=True,
			help_text=u"Denne personen er ansvarlig for å holde denne behandlingen oppdatert.",
			)
	fellesbehandling = models.BooleanField(
			verbose_name="Fellesbehandling / kopieringskandidat",
			default=False,
			help_text="Sett denne dersom du mener denne behandlingen gjelder de fleste / alle virksomheter.",
			)
	krav_sikkerhetsnivaa  = models.IntegerField(choices=SIKKERHETSNIVAA_VALG,
			verbose_name="Krav til sikkerhetsnivå",
			blank=True, null=True,
			help_text=u'Sikkerhetsnivå for felles IKT-plattform i hht <a target="_blank" href="https://confluence.oslo.kommune.no/x/y8seAw">Informasjonstyper og behandlingskrav</a>',
			)
	dpia_tidligere_bekymringer_risikoer = models.TextField(
			verbose_name="Er det tidligere avdekket risikoer/bekymringer over denne typen behandling?",
			blank=True, null=True,
			help_text=u"",
			)
	dpia_tidligere_avdekket_sikkerhetsbrudd = models.TextField(
			verbose_name="Er det tidligere avdekket sikkerhetsbrudd i fm. tilsvarende behandling?",
			blank=True, null=True,
			help_text=u"",
			)
	behandlingsansvarlig = models.ForeignKey(Virksomhet, related_name='behandling_behandlingsansvarlig',
			verbose_name="Registrert av",
			on_delete=models.PROTECT,
			help_text=u"Den virksomhet som er ansvarlig for å holde denne behandlingen oppdatert.",
			)
	#behandlingsansvarlig_representant = models.ForeignKey(Ansvarlig, related_name='behandling_behandlingsansvarlig_representant',
	#		verbose_name="Ansvarlig person",
	#		blank=True, null=True,
	#		on_delete=models.PROTECT,
	#		help_text=u"Den person som er ansvarlig for å holde denne behandlingen oppdatert.",
	#		)
	internt_ansvarlig = models.CharField(
			verbose_name="Internt ansvarlig (avdeling/enhet)",
			max_length=600,
			blank=True, null=True,
			help_text=u"Angi hvem som er internt ansvarlig (dataansvarlig) eller avdeling. Eksempler: Personaladministrasjon (HR), Skoleadministrasjon",
			)
	funksjonsomraade = models.CharField(
			verbose_name="Hovedoppgave / Hovedformål",
			max_length=600,
			blank=True, null=True,
			help_text=u"Hvilket overordnet funksjons-eller virksomhetsområde faller behandlingen under? Angi eventuell hovedoppgave eller hovedformål.Eksempler: HR-prosesser, Oppfølging av pasient, Regnskap",
			)
	behandlingen = models.TextField(
			verbose_name="Kort beskrivelse av behandlingen/prosessen.",
			blank=False, null=False,
			help_text=u"Beskriv kort hva som skjer i prosessen. Det skal kun være noen få ord som beskriver hva behandlingen av personopplysninger innebærer. Eksempler: Personaladministrasjon (HR), Besøksregistrering, Bakgrunnssjekk av ansatte, Saksbehandling, Oppfølging av sykefravær",
			)
	ny_endret_prosess = models.TextField(
			verbose_name="Innebærer behandlingen på noen måte ny/endret prosess?",
			blank=True, null=True,
			help_text=u""
			)
	dpia_dekker_formal = models.TextField(
			verbose_name="Dekker behandlingsprosessen det faktiske formålet, og er det andre måter å oppnå det samme resultatet?",
			blank=True, null=True,
			help_text=u"Noe tilsvarende dataminimering, ikke sant?",
			)
	formaal = models.TextField(
			verbose_name="Hva er formålet med behandlingen?",
			blank=True, null=True,
			help_text=u"Angi hva som er formålet med behandlingen, inkludert hvorfor opplysningene blir samlet inn. Forklaringen skal være slik at alle berørte har en felles forståelse av hva opplysningene brukes til. Om behandlingen dekker flere formål kan det være nyttig å dele inn beskrivelsen i flere delområder slik at fokus settes på formålet med behandlingen. HR/personal vil for eksempel ha flere formål med å samle inn personopplysninger om ansatte; f.eks. utbetale lønn, personal-administrasjon, kompetanseoversikt mv. Hver behandling bør ha en egen rad i behandlingsoversikten. Eksempler: Rekruttere ansatte basert på riktig erfaring og utdanning, Utbetale lønn til de ansatte, Sikre identifisering før tilgang blir gitt.",
			)
	dpia_effekt_enkelte = models.TextField(
			verbose_name="Effekt for de registrerte?",
			blank=True, null=True,
			help_text=u"Beskriv den påtenkte effekten - positiv og negativ - på enkeltpersoner som blir omfattet av behandlingen",
			)
	dpia_effekt_samfunnet = models.TextField(
			verbose_name="Formål som realiseres for samfunnet?",
			blank=True, null=True,
			help_text=u"Beskriv hvilke positive effekter behandlingen har for samfunnet / Virksomheten og evt. hvilken ulempe det innebærer hvis behandlingen ikke kan gjennomføres",
			)
	dpia_proporsjonalitet_enkelte_samfunnet = models.TextField(
			verbose_name="Beskriv vurderingen som er foretatt av proporsjonalitet mellom samfunnsgevinst ved behandlingen og potensiell risiko for de registrerte",
			blank=True, null=True,
			help_text=u"",
			)
	kategorier_personopplysninger = models.ManyToManyField(Personsonopplysningskategori, related_name='behandling_kategorier_personopplysninger',
			verbose_name="Kategorier personopplysninger som behandles",
			blank=True,
			help_text=u"",
			)
	personopplysninger_utdyping = models.TextField(
			verbose_name="Utdyping av personopplysninger som behandles",
			blank=True, null=True,
			help_text=u"Kontaktopplysninger, Søknad/CV, skatt og arbeidsgiveravgift",
			)
	den_registrerte = models.ManyToManyField(Registrerte, related_name='behandling_den_registrerte',
			verbose_name="Hvem er den registrerte? (grupper)",
			blank=True,
			help_text=u"",
			)
	relasjon_registrerte = models.ManyToManyField(RelasjonRegistrert,
			verbose_name="Hvilken relasjon har virksomheten til de registrerte?",
			blank=True,
			help_text=u"",
			)
	#burde vært rettet opp til valgfrihet
	valgfriget_registrerte = models.IntegerField(choices=BEHANDLING_VALGFRIHET,
			verbose_name="Hvor mye kontroll vil de registrerte ha på den behandlingen som foretas?",
			blank=True, null=True,
			help_text=u''
			)
	den_registrerte_sarbare_grupper = models.NullBooleanField(
			verbose_name="Inkluderer behandlingen barn eller andre sårbare grupper (f.eks. uføre, eldre, syke)?",
			blank=True, null=True,
			help_text=u"",
			)
	forventet_bruk = models.TextField(
			verbose_name="Vil de registrerte forvente at personopplysninger om dem brukes på denne måten?",
			blank=True, null=True,
			help_text=u"",
			)
	den_registrerte_hovedkateogi = models.ManyToManyField(RegistrertKlassifisering, related_name='behandling_den_registrerte_hovedkateogi',
			verbose_name="Hvem er den registrerte? (klassifisering)",
			blank=True,
			help_text=u"",
			)
	den_registrerte_detaljer = models.TextField(
			verbose_name="Ytdyping av de registrerte. F.eks. i hvilket geografisk område befinner de registrerte seg?",
			blank=True, null=True,
			help_text=u"Utdypning om hvem det behandles opplysninger om.",
			)
	antall_registrerte = models.TextField(
			verbose_name="Antall registrerte i behandlingsprosessen.",
			blank=True, null=True,
			help_text=u"En tekstlig beskrivelse av omfanget av de registrerte. Gjerne begrenset til en aldersgruppe og geografisk område.",
			)
	tilgang_opplysninger = models.TextField(
			verbose_name="Brukergrupper med tilgang til personopplysningene i behandlingsprosessen",
			blank=True, null=True,
			help_text=u"Beskriv hvor mange / hvem som vil få tilgang til opplysnignene internt.",
			)
	behandlingsgrunnlag_valg = models.ManyToManyField(Behandlingsgrunnlag, related_name='behandling_behandlingsgrunnlag_valg',
			verbose_name="Hva er grunnlaget (hjemmel) for denne behandlingsprosessen (behandlingen)?",
			blank=True,
			help_text=u"Her må hjemmel i så vel i personopplysnings-loven som i aktuelle særlov f.eks. barnevernloven beskrives",
			)
	behandlingsgrunnlag_utdyping = models.TextField(
			verbose_name="Utdyping av rettslig forpliktelse, berettighet interesse mv",
			blank=True, null=True,
			help_text=u"F.eks. Skattebetalingsloven, A-meldingsloven",
			)
	behandlingsgrunnlag_saerlige_kategorier = models.TextField(
			verbose_name="Utdyping av behandlingsgrunnlag dersom særskilte kategorier personopplysninger",
			null=True, blank=True,
			help_text=u"Behandlingsgrunnlag etter artikkel 9 eller 10, Med ev henvisning også til annen lovgivning dersom relevant",
			)
	opplysningskilde = models.TextField(
			verbose_name="Hvor er opplysningene innsamlet fra?",
			blank=True, null=True,
			help_text=u"Den registrerte, egen virksomhet, adressemekler",
			)
	frekvens_automatisert_innsamling = models.TextField(
			verbose_name="Hvor ofte foretas automatisert elektronisk innsamling?",
			blank=True, null=True,
			help_text=u"Hva trigger ny innhenting?",
			)
	frekvens_innsamling_manuelt = models.TextField(
			verbose_name="Hvor ofte mottas personopplysninger som følge av aktive skritt fra de registrerte, ansatte eller tredjepart?",
			blank=True, null=True,
			help_text=u"",
			)
	systemer = models.ManyToManyField(System, related_name='behandling_systemer',
			verbose_name="Systemer som benyttes i behandlingen",
			blank=True,
			help_text=u"",
			)
	programvarer = models.ManyToManyField(Programvare, related_name='behandling_programvarer',
			verbose_name="Programvarer som benyttes i behandlingen",
			blank=True,
			help_text=u"Programvarer benyttet i behandlingen",
			)
	oppbevaringsplikt = models.TextField(
			verbose_name="Finnes det oppbevaringsplikt for behandlingen?",
			blank=True, null=True,
			help_text=u"Andre krav til lagring ut fra andre behandlingsgrunnlag f.eks. oppbevaringsplikt i bokføringsloven, behov for bevissikring, arkivplikt m.m. for behandlingen (hjemmel)",
			)
	sikre_dataminimalisering = models.TextField(
			verbose_name="Tiltak for dataminimalisering",
			blank=True, null=True,
			help_text=u"Beskriv tiltak som er gjennomført for å sikre dataminimalisering. Det å unngå å oppbevare informasjon som ikke er nødvendig.",
			)
	krav_slettefrister = models.TextField(
			verbose_name="Krav til sletting?",
			blank=True, null=True,
			help_text=u"Hva er krav til tidsfrister for sletting ut fra opprinnelig behandlingsgrunnlag?<br>Hva er krav til tidsfrister for sletting ut fra andre behandlingsgrunnlag f.eks. oppbevaringsplikt i bokføringsloven, behov for bevissikring, arkivplikt m.m. for behandlingen (lagringstid)?",
			)
	planlagte_slettefrister = models.TextField(
			verbose_name="Hva er gjeldende prosedyre for sletting?",
			blank=True, null=True,
			help_text=u"Dersom mulig. F.eks. x måneder/år etter hendelse/prosess",
			)
	begrensning_tilgang = models.TextField(
			verbose_name="Begrensning av tilganger",
			blank=True, null=True,
			help_text=u"I henhold til Artikkel 18. Hvilken gruppe saksbehandlere skal ha tilgang etter avsluttet saksbehandling hvis det foreligger oppbevaringsplikt / tidsintervall p.r. gruppe? (Tilgangsbegrensning basert på hvem som har tjenstlig behov i hvilke tidsintervaller)",
			)
	navn_databehandler = models.ManyToManyField(Leverandor, related_name='behandling_navn_databehandler',
			verbose_name="Eksterne databehandlere",
			blank=True,
			help_text=u"Ved bruk av databehandlere (ekstern leverandør), angi hvilke dette er. Underleverandører er også databehandlere.",
			)
	dpia_prosess_godkjenne_underleverandor = models.TextField(
			verbose_name="Hvilken prosess for godkjennelse av underleverandører er etablert (ved avtaleinngåelse og ved bruk av nye underleverandører i avtaleperioden)?",
			blank=True, null=True,
			help_text=u"",
			)
	databehandleravtale_status = models.TextField(
			verbose_name="Er det inngått databehandleravtale med tredjepart(er)?",
			blank=True, null=True,
			help_text=u"Utdyp",
			)
	databehandleravtale_status_boolean = models.NullBooleanField(
			verbose_name="Er det inngått databehandleravtale med alle?",
			blank=True, null=True,
			help_text=u"",
			)
	dpia_dba_ivaretakelse_sikkerhet = models.TextField(
			verbose_name="Hvilke krav er stilt til leverandøren(e) til ivaretakelse av personvern og informasjonssikkerhet?",
			blank=True, null=True,
			help_text=u"",
			)
	kommunens_maler = models.NullBooleanField(
			verbose_name="Er Oslo kommunes maler for databehandleravtaler benyttet i avtale(ne) med leverandøren(e)?",
			blank=True, null=True,
			help_text=u"",
			)
	kommunens_maler_hvis_nei = models.TextField(
			verbose_name="Hvis Oslo kommunes maler for databehandleravtaler ikke er benyttet, er avtalen gjennomgått av jurist og informasjonssikkerhetsansvarlig i virksomheten? Beskrive resultatet av gjennomgangen.",
			blank=True, null=True,
			help_text=u"",
			)
	utlevering_ekstern_myndighet = models.NullBooleanField(
			verbose_name="Utleveres opplysninger til andre tredjeparter?",
			blank=True, null=True,
			help_text=u"F.eks. eksterne myndigheter eller liknende.",
			)
	utlevering_ekstern_myndighet_utdyping = models.TextField(
			verbose_name="Utdyp utlevering til tredjeparter",
			blank=True, null=True,
			help_text=u"Henvis til hjemmel i lov",
			)
	innhenting_ekstern_myndighet = models.NullBooleanField(
			verbose_name="Innhentes opplysninger fra andre tredjeparter?",
			blank=True, null=True,
			help_text=u"F.eks. som eksterne myndigheter eller liknende.",
			)
	innhenting_ekstern_myndighet_utdyping = models.TextField(
			verbose_name="Utdyp innhenting fra tredjeparter",
			blank=True, null=True,
			help_text=u"Henvis til hjemmel i lov",
			)
	utlevering_registrerte_samtykke = models.NullBooleanField(
			verbose_name="Utleveres opplysningene til pårørende e.l. ved bruk av samtykke?",
			blank=False, null=True,
			help_text=u"",
			)
	utlevering_registrerte_samtykke_utdyping = models.TextField(
			verbose_name="Utdyp utlevering basert på samtykke",
			blank=True, null=True,
			help_text=u"",
			)
	tjenesteleveranse_land = models.TextField(
			verbose_name="Fra hvilke land leverer leverandører og underleverandører tjenester m.m. som inngår i avtalen?",
			blank=True, null=True,
			help_text=u"",
			)
	utlevering_utenfor_EU = models.NullBooleanField(
			verbose_name="Skjer det en overføring av opplysninger til land utenfor EU/EØS?",
			blank=False, null=True,
			help_text=u"",
			)
	garantier_overforing = models.TextField(
			verbose_name="Utdyp utlevering utenfor EU. Er det inngått EU Model Clause eller på annen måte sikret hjemmel for eksport av data ut av EØS området?",
			blank=True, null=True,
			help_text=u"Nødvendige garantier ved overføring til tredjeland eller internasjonale organisasjoner",
			)
	informering_til_registrerte = models.TextField(
			verbose_name="Hvilken informasjon gis til den registrerte om behandlingen?",
			blank=True, null=True,
			help_text=u"Beskriv tiltak som er gjennomført for at de registrerte får vite hva opplysningene om dem brukes til (f.eks. personvernerklæring). Hvilke tiltak er iverksatt for å hjelpe den registrerte til å kunne gjøre bruk av sine rettigheter etter personopplysningsloven (f.eks. informasjonsskriv om rettigheter, etablering av portal som kan håndtere henvendelse m.m.)?",
			)
	innsyn_egenkontroll = models.TextField(
			verbose_name="Registrertes mulighet for innsyn og kontroll?",
			blank=True, null=True,
			help_text=u"Beskriv tiltak som er gjennomført for at de registrerte får innsyn i og kan kontrollere opplysningene registrert om dem",
			)
	rette_opplysninger = models.TextField(
			verbose_name="Hvordan kan den registrerte rette egne opplysninger?",
			blank=True, null=True,
			help_text=u"Beskriv tiltak som er gjennomført for at de registrerte kan rette sine opplysninger",
			)
	hoy_personvernrisiko = models.NullBooleanField(
			verbose_name="Høy personvernrisiko? Er det behov for å vurdere personvernkonsekvenser (DPIA)?",
			default=None,
			help_text="Se veiledningen <a target=\"_blank\" href=\"https://confluence.oslo.kommune.no/pages/viewpage.action?pageId=86934676\">Vurdering av om «høy risiko» foreligger</a>.",
			)
	dpia_unnga_hoy_risiko = models.NullBooleanField(
			verbose_name="Er det mulig å unngå 'høy risiko' for de registrerte?",
			default=None,
			help_text="",
			)
	sikkerhetstiltak = models.TextField(
			verbose_name="Hvilke organisatoriske tiltak for informasjonssikkerhet er gjennomført? ",
			blank=True, null=True,
			help_text=u"Manuelle rutiner som f.eks. autorisering av personell, gjennomgang av logger, revisjoner og regelmessig sletting. De tekniske tiltakene er beskrevet under det enkelte system.",
			)
	virksomhet_blacklist = models.ManyToManyField(Virksomhet,
			verbose_name="Ekskluderingsliste for fellesbehandling (ikke i bruk)",
			related_name="behandling_virksomhet_blacklist",
			blank=True,
			help_text="Behandlingen vises ikke i behandlingsoversikten for disse virksomhetene. Dette feltet er utfaset.",
			)
	history = HistoricalRecords()

	def __str__(self):
		return u'%s: %s' % (self.behandlingsansvarlig, self.behandlingen)

	class Meta:
		verbose_name_plural = "Behandlinger"
		default_permissions = ('add', 'change', 'delete', 'view')



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
