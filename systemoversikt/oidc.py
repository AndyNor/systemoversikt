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
import logging


#if settings.IDP_PROVIDER == "KEYCLOAK":

#	class CustomOIDCAuthenticationBackend(OIDCAuthenticationBackend):
#		def filter_users_by_claims(self, claims):
#			"""Return all users matching the specified username."""
#			# vi tar vare på claims i tilfelle vi trenger den et annet sted senere.
#			#messages.info(self.request, 'Prøver å logge inn')
#			self.request.session['oidc-token'] = claims
#			#messages.info(self.request, '%s' % claims)
#			username = claims.get('preferred_username').lower()
#			message = "Prøver å logge inn %s" % username
#			ApplicationLog.objects.create(event_type="Brukerpålogging", message=message)
#			if not username:
#				return self.UserModel.objects.none()
#				messages.warning(self.request, 'Du ble logget på uten brukernavn. Innlogging feilet.')
#			return self.UserModel.objects.filter(username__iexact=username)

#		""" Origos nye ooo-brukere kunne ikke logge på. Grunnen var at de ikke har e-postadresse som denne originalkoden
#		til verify_claims() sjekket etter. Den blir derfor her overskrevet til å bare sjekke brukernavn.
#		"""
#		def verify_claims(self, claims):
#			"""Verify the provided claims to decide if authentication should be allowed."""
#			#messages.info(self.request, 'Verifiserer claims')
#			# Verify claims required by default configuration
#			scopes = self.get_settings('OIDC_RP_SCOPES', 'openid email')
#			if 'preferred_username' in scopes.split():
#				return 'preferred_username' in claims
#
#			return True
#
#		# https://docs.djangoproject.com/en/2.0/ref/contrib/auth/#django.contrib.auth.models.User.username
#		# https://mozilla-django-oidc.readthedocs.io/en/stable/installation.html#additional-optional-configuration
#		def update_user(self, user, claims):
#			#messages.info(self.request, 'Oppdaterer bruker')
#			user.is_active = True
#
#			user.first_name = claims.get('given_name', '')
#			user.last_name = claims.get('family_name', '')
#			user.email = claims.get('email', '')
#			user.is_staff = True
#
#			# sjekke om bruker skal være superbruker
#			claim_groups = claims.get('groups', '')
#			superuser_group = "/DS-SYSTEMOVERSIKT_ADMINISTRATOR_SYSTEMADMINISTRATOR"
#			if superuser_group in claim_groups:
#				user.is_superuser = True
#				messages.warning(self.request, 'Du ble logget på som systemadministrator')
#				claim_groups.remove(superuser_group)
#			else:
#				user.is_superuser = False
#
#
#			#synkronisere gruppetilhørighet (slette alle og legge til på nytt)
#			current_memberships = user.groups.values_list('name',flat=True)
#			for existing_group in current_memberships:
#				g = Group.objects.get(name=existing_group)
#				g.user_set.remove(user)
#
#			for group in claim_groups:
#				try:
#					g = Group.objects.get(name=group)
#					g.user_set.add(user)
#				except:
#					#messages.warning(self.request, 'Gruppen %s finnes ikke i denne databasen.' % group)
#					pass
#
#			# prøve å sette virksomhetstilhørighet
#			try:
#				virksomhet_tbf = user.username[0:3].upper()
#				if user.username[0:5].upper() == "DRIFT": # all usernames are prefixed 3 letters by default in Oslo kommune, except DRIFT
#					virksomhet_tbf = "DRIFT"
#
#				virksomhet_obj_ref = Virksomhet.objects.get(virksomhetsforkortelse=virksomhet_tbf)
#				user.profile.virksomhet = virksomhet_obj_ref
#				user.profile.virksomhet_innlogget_som = virksomhet_obj_ref
#			except:
#				messages.warning(self.request, 'Fant ikke tilhørende virksomhet %s. Du er derfor ikke knyttet til noen virksomhet.' % virksomhet_tbf)
#
#			#user.last_login = timezone.now()
#			user.save()
#			messages.success(self.request, 'Du er nå logget på. Trykk på navnet ditt for å få opp mer administrativ informasjon.')
#			return user
#
#		def create_user(self, claims):
#			"""Return object for a newly created user account.
#			KeyCloak returns username in lower case. AD-LDAP by default in upper case.
#			In case of error "Multiple users returned" caused by two user objects, one with upper and one
#			with lower, make sure all import of usernames is in lowercase!
#			"""
#			messages.info(self.request, 'Ny bruker opprettes')
#			username = claims.get('preferred_username', '').lower()
#			if username == '':
#				return None
#			user = self.UserModel.objects.create_user(username, is_staff=True) # må være staff for å kunne bruker adminpanel
#			user = self.update_user(user, claims)
#			return user
#
#	def provider_logout(request):
#		# See your provider's documentation for details on if and how this is
#		# supported
#
#		"""
#		Kalles av mozilla_django_oidc.OIDCLogoutView via ettings.OIDC_OP_LOGOUT_URL_METHOD som peker hit for å generere en identity provider logout URL.
#		OIDCLogoutView godtar både post og get, men har bare definert metoden post for utlogging. Ved å sette denne til get fungerer utlogging. Bug?
#		"""
#		messages.info(request, 'Starter å logge ut')
#		redirect_url = settings.OIDC_IDP_URL_BASE + '/auth/realms/'+ settings.OIDC_IDP_REALM +'/protocol/openid-connect/logout?redirect_uri='  + settings.LOGOUT_REDIRECT_URL
#		return redirect_url


logger = logging.getLogger(__name__)
if settings.IDP_PROVIDER == "AZUREAD":
	class CustomOIDCAuthenticationBackend(OIDCAuthenticationBackend):
		def filter_users_by_claims(self, claims):
			# Return all users matching the specified username
			# messages.info(self.request, 'Prøver å logge inn')
			self.request.session['oidc-token'] = claims
			#logger.error("Auth: filter_user_by_claim: %s" % claims)
			#messages.info(self.request, '%s' % claims)
			username = claims.get('samAccountName')
			email = claims.get('email')
			#print(f"username {username}, email {email}")


			if username: # primærmetode
				username = username.lower()
				try:
					message = "%s logget inn." % username
					ApplicationLog.objects.create(event_type="Brukerpålogging", message=message)
					#messages.warning(self.request, 'Pålogging via brukernavn.')
					return self.UserModel.objects.filter(username__iexact=username)
				except:
					messages.warning(self.request, 'Kunne ikke logge inn med brukernavn.')


			if email: # sekundærmetode
				email = email.lower()
				try:
					message = "%s logget inn." % email
					ApplicationLog.objects.create(event_type="Brukerpålogging", message=message)
					messages.info(self.request, 'Pålogging via brukernavn feilet. Prøver pålogging via e-postadresse...')
					try:
						return self.UserModel.objects.filter(email__iexact=email)
					except:
						logger.error("Auth: filter_user_by_claim: No match for %s" % email)
						return self.UserModel.objects.none()
				except:
					messages.info(self.request, 'Kunne ikke logge inn med e-postadresse.')

			messages.warning(self.request, 'Det fulge ikke med et brukernavn i claim, og e-post stemmer ikke med e-post i on-prem AD. Innlogging feilet.')
			return self.UserModel.objects.none()

		def get_or_create_user(self, access_token, id_token, payload):
			from django.core.exceptions import SuspiciousOperation
			"""Returns a User instance if 1 user is found. Creates a user if not found
			and configured to do so. Returns nothing if multiple users are matched."""

			user_info = self.get_userinfo(access_token, id_token, payload)
			claims_verified = self.verify_claims(user_info)
			if not claims_verified:
				logger.error("Auth: get_or_create_user: Claims verification failed")
				logger.error("Auth: get_or_create_user: %s" % user_info)
				msg = 'Claims verification failed'
				#raise SuspiciousOperation(msg)
				return None

			# email based filtering
			users = self.filter_users_by_claims(user_info)

			if len(users) == 1:
				logger.error("Auth: get_or_create_user fant brukerID %s" % users[0])
				return self.update_user(users[0], user_info)
			elif len(users) > 1:
				# In the rare case that two user accounts have the same email address,
				# bail. Randomly selecting one seems really wrong. <-- JA! dette skriver altså utvikler av biblioteket :D
				msg = 'Multiple users returned'
				raise SuspiciousOperation(msg)
			elif self.get_settings('OIDC_CREATE_USER', True): # denne er deaktivert i settings.py
				user = self.create_user(user_info)
				return user
			else:
				logger.debug('Login failed: No user with %s found, and '
							 'OIDC_CREATE_USER is False',
							 self.describe_user_by_claims(user_info))
				return None


		def verify_claims(self, claims):
			# Verify the provided claims to decide if authentication should be allowed
			if 'samAccountName' in claims:
				return 'samAccountName' in claims
			if 'email' in claims:
				#messages.info(self.request, 'Problemer med pålogging. Ditt claim inneholder ikke "samAccountName" som er ditt brukernavn i Oslofelles AD. Prøver alternativ pålogging med e-postadresse. Ditt claim: %s' % claims)
				return 'email' in claims
			return False


		def get_userinfo(self, access_token, id_token, payload):
			#Return user details dictionary
			try:
				user_response = requests.get(
					self.OIDC_OP_USER_ENDPOINT,
					headers={
						'Authorization': 'Bearer {0}'.format(access_token)
					},
					verify=self.get_settings('OIDC_VERIFY_SSL', True),
					timeout=self.get_settings('OIDC_TIMEOUT', None),
					proxies=self.get_settings('OIDC_PROXY', None))
			except:
				logger.error("Auth: get_userinfo: Ingen kontakt med Microsoft Azure AD")
				return None

			user_response.raise_for_status()
			user_info = user_response.json()
			user_info.update(payload)
			# her skal vi prøve å hente ut gruppene direkte fra azure ad, men vet ikke helt hvordan enda..
			return user_info


		def update_user(self, user, claims):
			user.is_active = True
			user.first_name = claims.get('given_name', '')
			user.last_name = claims.get('family_name', '')
			user.email = claims.get('email', '')
			user.is_staff = True

			if settings.AD_DIRECT_ACCESS == True:
				try:
					ad_groups = ldap_users_securitygroups(user.username)
					claim_groups = []
					for g in ad_groups:
						kartotek_kompatibelt = "/" + g.split(',')[0].split('CN=')[1]
						claim_groups.append(kartotek_kompatibelt)


					superuser_group = "/DS-SYSTEMOVERSIKT_ADMINISTRATOR_SYSTEMADMINISTRATOR"
					if superuser_group in claim_groups:
						user.is_superuser = True
						messages.warning(self.request, 'Du ble logget på som systemadministrator')
						from systemoversikt.views import push_pushover
						#push_pushover(f"Bruker {user} logget inn som systemadministrator")
						claim_groups.remove(superuser_group)
					else:
						user.is_superuser = False

					# Slette alle rettigheter
					current_memberships = user.groups.values_list('name', flat=True)
					for existing_group in current_memberships:
						g = Group.objects.get(name=existing_group)
						g.user_set.remove(user)

					# Legge til nye bekreftede rettigheter
					for group in claim_groups:
						try:
							g = Group.objects.get(name=group)
							#messages.info(self.request, 'Rettighet: %s' % g)
							g.user_set.add(user)
						except:
							#messages.warning(self.request, 'Gruppen %s finnes ikke i denne databasen.' % group)
							pass
				except:
					logger.error("Auth: update_user: Ingen kontakt med AD. Kan ikke oppdatere tilganger.")

			else:
				messages.info(self.request, 'Kan ikke oppdatere tilganger, ingen kontakt med AD')


			# Sette virksomhetstilhørighet
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
		# Kan kalles av mozilla_django_oidc.OIDCLogoutView via settings.OIDC_OP_LOGOUT_URL_METHOD
		#OIDCLogoutView godtar både post og get, men har bare definert metoden post for utlogging. Ved å sette denne til get fungerer utlogging. Bug?
		messages.info(request, 'Starter å logge ut')
		redirect_url = settings.OIDC_IDP_URL_BASE + '/auth/realms/'+ settings.OIDC_IDP_REALM +'/protocol/openid-connect/logout?redirect_uri='  + settings.LOGOUT_REDIRECT_URL
		return redirect_url
