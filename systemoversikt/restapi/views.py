from rest_framework import viewsets
from rest_framework import serializers
import systemoversikt.models as models
from django.contrib.auth.models import User



class SystemSerializer(serializers.ModelSerializer):
	url = serializers.HyperlinkedIdentityField(
		view_name='systemer-detail',
	)
	class Meta:
		model = models.System
		fields = (
			'pk',
			'url',
			'systemnavn',
			'ibruk',
			'systembeskrivelse',
			#'driftsmodell_foreignkey',
			#'systemeier',
			'systemeier_kontaktpersoner_referanse',
			#'systemforvalter',
			#'systemforvalter_kontaktpersoner_referanse',
			#'sikkerhetsnivaa',
			#'database',
			#'datautveksling_mottar_fra',
			#'datautveksling_avleverer_til'
			)
class SystemViewSet(viewsets.ModelViewSet):
	queryset = models.System.objects.all().order_by('-systemnavn')
	serializer_class = SystemSerializer


class HELSystemSerializer(serializers.ModelSerializer):
	url = serializers.HyperlinkedIdentityField(
		view_name='systemer_HEL-detail',
	)
	class Meta:
		model = models.System
		fields = (
			'pk',
			'url',
			'systemnavn',
			'ibruk',
			'systembeskrivelse',
			#'driftsmodell_foreignkey',
			#'systemeier',
			'systemeier_kontaktpersoner_referanse',
			#'systemforvalter',
			#'systemforvalter_kontaktpersoner_referanse',
			#'sikkerhetsnivaa',
			#'database',
			#'datautveksling_mottar_fra',
			#'datautveksling_avleverer_til'
			)
class HELSystemViewSet(viewsets.ModelViewSet):
	queryset = models.System.objects.filter(systembruk_system__brukergruppe=145).order_by('-systemnavn')
	serializer_class = HELSystemSerializer


class VirksomhetSerializer(serializers.HyperlinkedModelSerializer):
	class Meta:
		model = models.Virksomhet
		fields = (
			'pk',
			'url',
			'virksomhetsnavn',
			'virksomhetsforkortelse',
			'orgnummer',
			'resultatenhet',
			'autoriserte_bestillere_tjenester'
			)
class VirksomhetViewSet(viewsets.ModelViewSet):
	queryset = models.Virksomhet.objects.all().order_by('-virksomhetsnavn')
	serializer_class = VirksomhetSerializer



class BehandlingerSerializer(serializers.ModelSerializer):
	class Meta:
		model = models.BehandlingerPersonopplysninger
		fields = (
			'pk',
			'oppdateringsansvarlig',
			'behandlingsansvarlig',
			'internt_ansvarlig',
			'funksjonsomraade',
			'behandlingen',
			'formaal',
			'kategorier_personopplysninger',
			'behandlingsgrunnlag_valg',
			'systemer',
			'navn_databehandler'
			)
class VirksomhetViewSet(viewsets.ModelViewSet):
	queryset = models.BehandlingerPersonopplysninger.objects.all()
	serializer_class = BehandlingerSerializer


class DriftsmodellSerializer(serializers.HyperlinkedModelSerializer):
	class Meta:
		model = models.Driftsmodell
		fields = (
			'pk',
			'url',
			'navn',
			'kommentar'
			)
class DriftsmodellViewSet(viewsets.ModelViewSet):
	queryset = models.Driftsmodell.objects.all().order_by('-navn')
	serializer_class = DriftsmodellSerializer

class UserSerializer(serializers.HyperlinkedModelSerializer):
	full_name = serializers.CharField(source='get_full_name')
	class Meta:
		model = User
		fields = (
			'pk',
			'url',
			'username',
			'full_name',
			)
class UserViewSet(viewsets.ModelViewSet):
	queryset = User.objects.all().order_by('-username')
	serializer_class = UserSerializer



class AnsvarligSerializer(serializers.HyperlinkedModelSerializer):
	full_name = serializers.CharField(source='brukernavn.get_full_name')
	email = serializers.CharField(source='brukernavn.email')
	virksomhet = serializers.CharField(source='brukernavn.profile.virksomhet')
	class Meta:
		model = models.Ansvarlig
		fields = (
			'pk',
			'url',
			'full_name',
			'email',
			'virksomhet',
			)
class AnsvarligViewSet(viewsets.ModelViewSet):
	queryset = models.Ansvarlig.objects.all().order_by('-brukernavn')
	serializer_class = AnsvarligSerializer
	#http_method_names = ['get','head']





class AvtaleSerializer(serializers.HyperlinkedModelSerializer):
	class Meta:
		model = models.Avtale
		fields = (
			'pk',
			'url',
			'avtaletype',
			'kortnavn',
			'beskrivelse',
			'virksomhet',
			'avtaleansvarlig',
			'leverandor',
			'leverandor_intern',
			'avtalereferanse',
			'dokumenturl'
			)
class AvtaleViewSet(viewsets.ModelViewSet):
	queryset = models.Avtale.objects.all().order_by('-kortnavn')
	serializer_class = AvtaleSerializer


class LeverandorSerializer(serializers.HyperlinkedModelSerializer):
	class Meta:
		model = models.Leverandor
		fields = ('pk',
			'url',
			'leverandor_navn',
			'orgnummer',
			'kontaktpersoner',
			'godkjent_opptaks_sertifiseringsordning',
			)
class LeverandorViewSet(viewsets.ModelViewSet):
	queryset = models.Leverandor.objects.all().order_by('-leverandor_navn')
	serializer_class = LeverandorSerializer


