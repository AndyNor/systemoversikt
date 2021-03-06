import unicodedata
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from .models import Virksomhet, ApplicationLog
from django.contrib.auth.models import Group
from django.conf import settings
from django.contrib import messages
from django.utils import timezone

class CustomOIDCAuthenticationBackend(OIDCAuthenticationBackend):
	def filter_users_by_claims(self, claims):
		"""Return all users matching the specified username."""
		# vi tar vare på claims i tilfelle vi trenger den et annet sted senere.
		#messages.info(self.request, 'Prøver å logge inn')
		self.request.session['oidc-token'] = claims
		#messages.info(self.request, '%s' % claims)
		username = claims.get('preferred_username').lower()
		message = "Prøver å logge inn %s" % username
		ApplicationLog.objects.create(event_type="Brukerpålogging", message=message)
		if not username:
			return self.UserModel.objects.none()
			messages.warning(self.request, 'Du ble logget på uten brukernavn. Innlogging feilet.')
		return self.UserModel.objects.filter(username__iexact=username)

	""" Origos nye ooo-brukere kunne ikke logge på. Grunnen var at de ikke har e-postadresse som denne originalkoden
	til verify_claims() sjekket etter. Den blir derfor her overskrevet til å bare sjekke brukernavn.
	"""
	def verify_claims(self, claims):
		"""Verify the provided claims to decide if authentication should be allowed."""
		#messages.info(self.request, 'Verifiserer claims')
		# Verify claims required by default configuration
		scopes = self.get_settings('OIDC_RP_SCOPES', 'openid email')
		if 'preferred_username' in scopes.split():
			return 'preferred_username' in claims

		return True

	# https://docs.djangoproject.com/en/2.0/ref/contrib/auth/#django.contrib.auth.models.User.username
	# https://mozilla-django-oidc.readthedocs.io/en/stable/installation.html#additional-optional-configuration
	def update_user(self, user, claims):
		#messages.info(self.request, 'Oppdaterer bruker')
		user.is_active = True

		user.first_name = claims.get('given_name', '')
		user.last_name = claims.get('family_name', '')
		user.email = claims.get('email', '')
		user.is_staff = True

		# sjekke om bruker skal være superbruker
		claim_groups = claims.get('groups', '')
		superuser_group = "/DS-SYSTEMOVERSIKT_ADMINISTRATOR_SYSTEMADMINISTRATOR"
		if superuser_group in claim_groups:
			user.is_superuser = True
			messages.warning(self.request, 'Du ble logget på som systemadministrator')
			claim_groups.remove(superuser_group)
		else:
			user.is_superuser = False


		#synkronisere gruppetilhørighet (slette alle og legge til på nytt)
		current_memberships = user.groups.values_list('name',flat=True)
		for existing_group in current_memberships:
			g = Group.objects.get(name=existing_group)
			g.user_set.remove(user)

		for group in claim_groups:
			try:
				g = Group.objects.get(name=group)
				g.user_set.add(user)
			except:
				#messages.warning(self.request, 'Gruppen %s finnes ikke i denne databasen.' % group)
				pass

		# prøve å sette virksomhetstilhørighet
		try:
			virksomhet_tbf = user.username[0:3].upper()
			if user.username[0:5].upper() == "DRIFT": # all usernames are 3 letters by default in Oslo kommune, except DRIFT
				virksomhet_tbf = "DRIFT"

			virksomhet_obj_ref = Virksomhet.objects.get(virksomhetsforkortelse=virksomhet_tbf)
			user.profile.virksomhet = virksomhet_obj_ref
			user.profile.virksomhet_innlogget_som = virksomhet_obj_ref
		except:
			messages.warning(self.request, 'Fant ikke tilhørende virksomhet %s. Du er derfor ikke knyttet til noen virksomhet.' % virksomhet_tbf)

		#user.last_login = timezone.now()
		user.save()
		messages.success(self.request, 'Du er nå logget på. Trykk på navnet ditt for å få opp mer administrativ informasjon. Ved siden av navnet ditt står det også hvilken virksomhet du nå representerer (som kan endres via den linken).')
		return user

	def create_user(self, claims):
		"""Return object for a newly created user account.
		KeyCloak returns username in lower case. AD-LDAP by default in upper case.
		In case of error "Multiple users returned" caused by two user objects, one with upper and one
		with lower, make sure all import of usernames is in lowercase!
		"""
		messages.info(self.request, 'Ny bruker opprettes')
		username = claims.get('preferred_username', '').lower()
		if username == '':
			return None
		user = self.UserModel.objects.create_user(username, is_staff=True) # må være staff for å kunne bruker adminpanel
		user = self.update_user(user, claims)
		return user

def provider_logout(request):
	# See your provider's documentation for details on if and how this is
	# supported

	"""
	Kalles av mozilla_django_oidc.OIDCLogoutView via ettings.OIDC_OP_LOGOUT_URL_METHOD som peker hit for å generere en identity provider logout URL.
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