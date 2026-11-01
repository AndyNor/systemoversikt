# -*- coding: utf-8 -*-
# Change log:
# 2026-11-01: Remove Keycloak backend, lokal_rettighetstest, and dead provider_logout; access testing moves to /admin/profil/.
# 2026-11-01: Replace per-role login flash messages with one-shot welcome summary (session flag).
# 2026-11-01: Store access grant sources in session for /admin/profil/ (auto vs gruppemedlemskap, root).
# 2026-11-01: Commented out login success message about user access details – redundant with other messages.
# 2026-08-24: Do not gate OIDC on nightly LDAP accountdisable; Entra decides who can log in.
# 2026-08-23: Do not wipe groups when AD/Entra lookup fails; clear auto-OIDC flags after successful update_user.
# 2026-08-23: Clear auto-OIDC session flags after successful login so a later logout can auto-login again.
# 2026-06-21: Removed @vav.oslo email rewrite and oidc-token session storage – legacy debug paths retired.
# 2026-06-21: Removed OKONOMI_FULLTILGANG from OIDC group mapping – UBW module retired.
#
# følgende tilgangsstyring skal her implementeres:
# CN=DS-SYSTEMOVERSIKT_BRUKER_KUN_LESE,ou=Systemoversikt,ou=Felles,...
# Gir lesetilgang
# Gis direkte ved pålogging dersom innlogget bruker har en "ansvarlig"-rolle
# gis til DIG systemutvikling
# kan tildeles via IDA.
#
# CN=DS-SYSTEMOVERSIKT_FORVALTER_SYSTEMFORVALTER,ou=Systemoversikt,ou=Felles,...
# gir tilgang til å redigere systemer tilhørende din virksomhet
# Tildeles automatisk dersom du er systemforvalter eller eier
# kan ikke tildeles via IDA/PRK
#
# CN=DS-SYSTEMOVERSIKT_FORVALTER_VIRKSOMHETER,ou=Systemoversikt,ou=Felles,...
# Gir systemforvaltertilgang + virksomhet + plattformer for alt registrert på din virksomhet
# settes automatisk ved pålogging for hovedkontakt/ISK/PKO.
# kan tildeles via IDA
#
# CN=DS-SYSTEMOVERSIKT_ADMINISTRATOR_ADMINISTRATOR,ou=Systemoversikt,ou=Felles,...
# gir superbruker på tvers av virksomheter
# kan kun tildeles via IDA
#
# CN=DS-SYSTEMOVERSIKT_SAARBARHETSOVERSIKT_SIKKERHETSANALYTIKER,ou=Systemoversikt,ou=Felles,...
# brukes for å kunne se sårbarheter for alle systemer
# tildeles via IDA begrenset med autorisasjon
#
# CN=DS-SYSTEMOVERSIKT_ADMINISTRATOR_SYSTEMADMINISTRATOR,ou=Systemoversikt,ou=Felles,...
# gir root-tilgang til admingrensesnittet
# kan kun settes via IDA med autorisasjon
#
# redigering av system er begrenset til virksomhet utenom for DS-SYSTEMOVERSIKT_ADMINISTRATOR_ADMINISTRATOR og superuser
# redigering av virksomhet er begrenset til virksomhet utenom for DS-SYSTEMOVERSIKT_ADMINISTRATOR_ADMINISTRATOR og superuser
# redigering av plattform er begrenset til virksomhet utenom for DS-SYSTEMOVERSIKT_ADMINISTRATOR_ADMINISTRATOR og superuser

from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from .models import Virksomhet, ApplicationLog
from django.contrib.auth.models import Group
from django.conf import settings
from django.contrib import messages
from django.utils import timezone
import requests
import systemoversikt.settings
from systemoversikt.views import ldap_users_securitygroups
import logging


logger = logging.getLogger(__name__)
if settings.IDP_PROVIDER == "AZUREAD":
	class CustomOIDCAuthenticationBackend(OIDCAuthenticationBackend):
		def filter_users_by_claims(self, claims):
			# Return all users matching the specified username
			username = claims.get('samAccountName')
			email = claims.get('email')

			if username:  # primærmetode
				username = username.lower()

				# Try to find a matching user
				qs = self.UserModel.objects.filter(username__iexact=username)

				if qs.exists():
					# Found a matching user → return it
					message = f"{username} logget inn."
					ApplicationLog.objects.create(event_type="Brukerpålogging", message=message)
					return qs

			# siden vi ikke returnerte basert på username, prøver vi email
			if email:
				email = email.lower()
				qs = self.UserModel.objects.filter(email__iexact=email)
				if qs.exists():
					message = f"{email} logget inn (epostmatch)."
					ApplicationLog.objects.create(event_type="Brukerpålogging", message=message)
					return qs

			# nothing worked
			logger.error(f"Auth: filter_user_by_claim: No match for username={username!r} email={email!r}")
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
			# 2026-08-24: is_active is set here at OIDC login; Entra already admitted the user.
			user.is_active = True
			user.email = claims.get('email', '')
			user.is_staff = True # kreves for å kunne nå django adminportal som brukes for nesten all redigering.

			claim_groups = []
			# 2026-08-23: Do not wipe Django groups when AD/Entra lookup fails (SessionRefresh / re-login).
			group_lookup_ok = False

			if settings.AD_DIRECT_ACCESS == True:
				try:
					ad_groups = ldap_users_securitygroups(user.username)
					#print(ad_groups)
					for g in ad_groups:
						kartotek_kompatibelt = "/" + g.split(',')[0].split('CN=')[1]
						claim_groups.append(kartotek_kompatibelt)
					group_lookup_ok = True
				except:
					logger.error("Auth: update_user: Ingen kontakt med AD. Kan ikke oppdatere tilganger.")

			else:
				from systemoversikt.views import auth_kartoteket_group_lookup
				try:
					aad_groups = auth_kartoteket_group_lookup(user.username)
					for g in aad_groups:
						kartotek_kompatibelt = "/" + g
						claim_groups.append(kartotek_kompatibelt)
					group_lookup_ok = True
				except:
					messages.info(self.request, 'Kunne ikke hente grupper fra Entra ID')

			if not group_lookup_ok:
				messages.warning(
					self.request,
					'Kunne ikke oppdatere tilganger fra katalog. Eksisterende tilganger er beholdt.',
				)
			else:
				# Slette alle eksisterende rettigheter
				current_memberships = user.groups.values_list('name', flat=True)
				for existing_group in current_memberships:
					g = Group.objects.get(name=existing_group)
					g.user_set.remove(user)
				user.is_superuser = False

				# 2026-11-01: Track grant sources for /admin/profil/ (auto vs gruppemedlemskap).
				access_sources = {}
				def _record_access(group_name, reason):
					reasons = access_sources.setdefault(group_name, [])
					if reason not in reasons:
						reasons.append(reason)

				superuser_group = "/DS-SYSTEMOVERSIKT_ADMINISTRATOR_SYSTEMADMINISTRATOR"
				if superuser_group in claim_groups:
					user.is_superuser = True
					# 2026-11-01: Replaced by login welcome summary on forside/profil.
					#messages.warning(self.request, 'Du ble logget på som systemadministrator')
					from systemoversikt.views import push_pushover
					#push_pushover(f"Bruker {user} logget inn som systemadministrator")
					claim_groups.remove(superuser_group)
					_record_access(superuser_group, "Gruppemedlemskap (IDA)")
				else:
					user.is_superuser = False


				# Legge til nye bekreftede rettigheter
				# først alle tilgangsgrupper som kommer fra AD
				directly_assignable_groups = [
					"/DS-SYSTEMOVERSIKT_BRUKER_KUN_LESE",
					"/DS-SYSTEMOVERSIKT_FORVALTER_VIRKSOMHETER",
					"/DS-SYSTEMOVERSIKT_ADMINISTRATOR_ADMINISTRATOR",
					"/DS-SYSTEMOVERSIKT_SAARBARHETSOVERSIKT_SIKKERHETSANALYTIKER",
					"/DS-SYSTEMOVERSIKT_ADMINISTRATOR_SYSTEMADMINISTRATOR",
					"/DS-SYSTEMOVERSIKT_FORVALTER_BEHANDLINGSANSVARLIG", #midlertidig frem til modulen avvikles helt
				]

				for group in claim_groups:
					if group in directly_assignable_groups:
						try:
							g = Group.objects.get(name=group)
							#messages.info(self.request, 'Rettighet: %s' % g)
							g.user_set.add(user)
							_record_access(group, "Gruppemedlemskap (IDA)")
							if group == "/DS-SYSTEMOVERSIKT_ADMINISTRATOR_SYSTEMADMINISTRATOR" or group == "/DS-SYSTEMOVERSIKT_SAARBARHETSOVERSIKT_SIKKERHETSANALYTIKER":
								# da legger vi også til rettigheter på "lavere" roller
								ansvarlig_group = Group.objects.get(name="/DS-SYSTEMOVERSIKT_BRUKER_KUN_LESE")
								ansvarlig_group.user_set.add(user)
								virksomhetsrolle_group = Group.objects.get(name="/DS-SYSTEMOVERSIKT_FORVALTER_VIRKSOMHETER")
								virksomhetsrolle_group.user_set.add(user)
								systemforvalter_group = Group.objects.get(name="/DS-SYSTEMOVERSIKT_FORVALTER_SYSTEMFORVALTER")
								systemforvalter_group.user_set.add(user)
								_record_access("/DS-SYSTEMOVERSIKT_BRUKER_KUN_LESE", "Via høyere rolle")
								_record_access("/DS-SYSTEMOVERSIKT_FORVALTER_VIRKSOMHETER", "Via høyere rolle")
								_record_access("/DS-SYSTEMOVERSIKT_FORVALTER_SYSTEMFORVALTER", "Via høyere rolle")

							if group == "/DS-SYSTEMOVERSIKT_FORVALTER_VIRKSOMHETER":
								systemforvalter_group = Group.objects.get(name="/DS-SYSTEMOVERSIKT_FORVALTER_SYSTEMFORVALTER")
								systemforvalter_group.user_set.add(user)
								_record_access("/DS-SYSTEMOVERSIKT_FORVALTER_SYSTEMFORVALTER", "Via virksomhetsforvalter-rolle")
						except:
							#messages.warning(self.request, 'Gruppen %s finnes ikke i denne databasen.' % group)
							pass

				# så grupper sluttbruker skal tildeles automatisk
				from systemoversikt.views import auth_er_ansvarlig, auth_er_systemforvalter, auth_er_virksomhetsrolle
				er_ansvarlig = auth_er_ansvarlig(user)
				er_dig = ("/DS-ROLLEGRUPPER_UKEAOS_ANSATTELLERKONSULENT" in claim_groups) or ("/24055" in claim_groups)
				if er_ansvarlig or er_dig: # Utviklere og driftlev
					ansvarlig_group = Group.objects.get(name="/DS-SYSTEMOVERSIKT_BRUKER_KUN_LESE")
					ansvarlig_group.user_set.add(user)
					# 2026-11-01: Replaced by login welcome summary on forside/profil.
					#messages.info(self.request, 'Du ble automatisk tildelt leserettigheter')
					if er_ansvarlig:
						_record_access("/DS-SYSTEMOVERSIKT_BRUKER_KUN_LESE", "Automatisk (registrert som ansvarlig)")
					if er_dig:
						_record_access("/DS-SYSTEMOVERSIKT_BRUKER_KUN_LESE", "Automatisk (DIG systemutvikling)")

				if auth_er_systemforvalter(user):
					systemforvalter_group = Group.objects.get(name="/DS-SYSTEMOVERSIKT_FORVALTER_SYSTEMFORVALTER")
					systemforvalter_group.user_set.add(user)
					# 2026-11-01: Replaced by login welcome summary on forside/profil.
					#messages.info(self.request, 'Du ble automatisk tildelt systemforvalter-tilgang')
					_record_access("/DS-SYSTEMOVERSIKT_FORVALTER_SYSTEMFORVALTER", "Automatisk (systemforvalter/systemeier)")

				if auth_er_virksomhetsrolle(user):
					virksomhetsrolle_group = Group.objects.get(name="/DS-SYSTEMOVERSIKT_FORVALTER_VIRKSOMHETER")
					virksomhetsrolle_group.user_set.add(user)
					systemforvalter_group = Group.objects.get(name="/DS-SYSTEMOVERSIKT_FORVALTER_SYSTEMFORVALTER")
					systemforvalter_group.user_set.add(user)
					# 2026-11-01: Replaced by login welcome summary on forside/profil.
					#messages.info(self.request, 'Du ble automatisk tildelt virksomhetstilganger')
					_record_access("/DS-SYSTEMOVERSIKT_FORVALTER_VIRKSOMHETER", "Automatisk (IKT-kontakt/ISK/PKO)")
					_record_access("/DS-SYSTEMOVERSIKT_FORVALTER_SYSTEMFORVALTER", "Via virksomhetsforvalter-rolle")

				# 2026-11-01: Persist grant sources for the profile page (lost when group lookup fails above).
				self.request.session['kartotek_access_sources'] = access_sources
				self.request.session['kartotek_access_sources_at'] = timezone.now().isoformat()



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
			# 2026-11-01: Commented out – redundant with other login messages.
			#messages.success(self.request, 'Du er nå logget på. Trykk på navnet ditt for å få opp detaljer om dine tilganger.')

			# 2026-11-01: One-shot welcome box after real OIDC callback (not SessionRefresh on other paths).
			request_path = getattr(self.request, 'path', '') or ''
			if 'oidc/callback' in request_path:
				self.request.session['kartotek_login_welcome'] = True

			# 2026-08-23: Clear auto-OIDC flags after groups/profile are updated (successful login path).
			from systemoversikt.auto_oidc import clear_auto_oidc_session_flags
			clear_auto_oidc_session_flags(self.request)

			return user
