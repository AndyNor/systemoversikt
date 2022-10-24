import unicodedata
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from .models import Virksomhet, ApplicationLog
from django.contrib.auth.models import Group
from django.conf import settings
from django.contrib import messages
from django.utils import timezone
import requests
import os
import systemoversikt.settings
from systemoversikt.views import ldap_users_securitygroups


class CustomOIDCAuthenticationBackend(OIDCAuthenticationBackend):
	def filter_users_by_claims(self, claims):
		"""Return all users matching the specified username."""
		# vi tar vare på claims i tilfelle vi trenger den et annet sted senere.
		#messages.info(self.request, 'Prøver å logge inn')
		self.request.session['oidc-token'] = claims
		messages.info(self.request, '%s' % claims)
		email = claims.get('email').lower()
		if not email:
			return self.UserModel.objects.none()
			messages.warning(self.request, 'Du mangler e-postadresse. Innlogging feilet.')
		try:
			message = "%s logget inn." % email
			ApplicationLog.objects.create(event_type="Brukerpålogging", message=message)
			return self.UserModel.objects.filter(email=email)
		except:
			message = "%s kunne ikke logge inn. Kobling mot e-postadresse feilet" % email
			ApplicationLog.objects.create(event_type="Brukerpålogging", message=message)
			messages.warning(self.request, 'Fant ingen korresponderende bruker for denne e-postadressen. Innlogging feilet.')
			return self.UserModel.objects.none()


	""" Origos nye ooo-brukere kunne ikke logge på. Grunnen var at de ikke har e-postadresse som denne originalkoden
	til verify_claims() sjekket etter. Den blir derfor her overskrevet til å bare sjekke brukernavn.
	"""
	def verify_claims(self, claims):
		"""Verify the provided claims to decide if authentication should be allowed."""
		#messages.info(self.request, 'Verifiserer claims')
		# Verify claims required by default configuration
		scopes = self.get_settings('OIDC_RP_SCOPES', 'openid email')
		if 'email' in scopes.split():
			return 'email' in claims
		return True


	def get_userinfo(self, access_token, id_token, payload):
		"""Return user details dictionary. The id_token and payload are not used in
		the default implementation, but may be used when overriding this method"""
		user_response = requests.get(
			self.OIDC_OP_USER_ENDPOINT,
			headers={
				'Authorization': 'Bearer {0}'.format(access_token)
			},
			verify=self.get_settings('OIDC_VERIFY_SSL', True),
			timeout=self.get_settings('OIDC_TIMEOUT', None),
			proxies=self.get_settings('OIDC_PROXY', None))
		user_response.raise_for_status()
		user_info = user_response.json()
		user_info.update(payload)


		groups_response = requests.post(
			"https://graph.microsoft.com/beta/me/getMemberObjects",
			headers={
				'Authorization': 'Bearer {0}'.format(access_token),
			},
			verify=self.get_settings('OIDC_VERIFY_SSL', True),
			timeout=self.get_settings('OIDC_TIMEOUT', None),
			proxies=self.get_settings('OIDC_PROXY', None))
		print(groups_response.json())


		return user_info


	# https://docs.djangoproject.com/en/2.0/ref/contrib/auth/#django.contrib.auth.models.User.username
	# https://mozilla-django-oidc.readthedocs.io/en/stable/installation.html#additional-optional-configuration
	def update_user(self, user, claims):
		user.is_active = True
		user.first_name = claims.get('given_name', '')
		user.last_name = claims.get('family_name', '')
		user.email = claims.get('email', '')
		user.is_staff = True

		# sjekke om bruker skal være superbruker
		#claim_groups = claims.get('groups', '')
		#claim_groups = grupper = ldap_users_securitygroups(user.username)
		#print(claim_groups)
		#superuser_group = "/DS-SYSTEMOVERSIKT_ADMINISTRATOR_SYSTEMADMINISTRATOR"
		#if superuser_group in claim_groups:
		#	user.is_superuser = True
		#	messages.warning(self.request, 'Du ble logget på som systemadministrator')
		#	claim_groups.remove(superuser_group)
		#else:
		#	user.is_superuser = False


		#synkronisere gruppetilhørighet (slette alle og legge til på nytt)
		#current_memberships = user.groups.values_list('name', flat=True)
		#for existing_group in current_memberships:
		#	g = Group.objects.get(name=existing_group)
		#	g.user_set.remove(user)

		#for group in claim_groups:
		#	try:
		#		g = Group.objects.get(name=group)
		#		g.user_set.add(user)
		#	except:
		#		#messages.warning(self.request, 'Gruppen %s finnes ikke i denne databasen.' % group)
		#		pass

		# prøve å sette virksomhetstilhørighet
		try:
			virksomhet_tbf = user.username[0:3].upper()
			if user.username[0:5].upper() == "DRIFT": # all usernames are prefixed 3 letters by default in Oslo kommune, except DRIFT
				virksomhet_tbf = "DRIFT"

			virksomhet_obj_ref = Virksomhet.objects.get(virksomhetsforkortelse=virksomhet_tbf)
			user.profile.virksomhet = virksomhet_obj_ref
			user.profile.virksomhet_innlogget_som = virksomhet_obj_ref
		except:
			messages.warning(self.request, 'Fant ikke tilhørende virksomhet %s. Du er derfor ikke knyttet til noen virksomhet.' % virksomhet_tbf)

		#user.last_login = timezone.now()
		user.save()
		messages.success(self.request, 'Du er nå logget på. Trykk på navnet ditt for å få opp detaljer og for å logge av.')
		return user



def provider_logout(request):
	# See your provider's documentation for details on if and how this is
	# supported

	"""
	Kalles av mozilla_django_oidc.OIDCLogoutView via settings.OIDC_OP_LOGOUT_URL_METHOD som peker hit for å generere en identity provider logout URL.
	OIDCLogoutView godtar både post og get, men har bare definert metoden post for utlogging. Ved å sette denne til get fungerer utlogging. Bug?
	"""
	messages.info(request, 'Starter å logge ut')
	redirect_url = settings.OIDC_IDP_URL_BASE + '/auth/realms/'+ settings.OIDC_IDP_REALM +'/protocol/openid-connect/logout?redirect_uri='  + settings.LOGOUT_REDIRECT_URL
	return redirect_url

"""
def generate_username(email):
	# Using Python 3 and Django 1.11, usernames can contain alphanumeric
	# (ascii and unicode), _, @, +, . and - characters. So we normalize
	# it and slice at 150 characters.
	return unicodedata.normalize('NFKC', email)[:150]
"""