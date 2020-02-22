# -*- coding: utf-8 -*-

"""
Hensikten med denne koden er å laste inn alle orginære brukre koblet til en av kommunens vikrsomheter, slik at man i kartoteket kan tildele ansvar til en faktisk brukeridentitet. Her laster vi ikke inn manuelt opprettede brukere som ikke kommer fra PRK.
Denne importen vil ikke kunne svare på forskjeller mellom AD og PRK. Det er andre jobber som identifiserer slike avvik.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
import sys
import re

logg_antall_nye_brukere = 0
logg_antall_identer_funnet = 0
logg_endrede_brukere = 0

#optimize_status_codes = []

class Command(BaseCommand):
	def handle(self, **options):

		import time
		import sys
		import ldap
		import os
		from ldap.controls import SimplePagedResultsControl
		from distutils.version import LooseVersion
		from systemoversikt.models import Virksomhet, ApplicationLog

		runetime_t0 = time.time()

		LDAPUSER = os.environ["KARTOTEKET_LDAPUSER"]
		LDAPPASSWORD = os.environ["KARTOTEKET_LDAPPASSWORD"]
		LDAPSERVER='ldaps://ldaps.oslofelles.oslo.kommune.no:636'

		# Ignore server side certificate errors (assumes using LDAPS and
		# self-signed cert). Not necessary if not LDAPS or it's signed by
		# a real CA.
		ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)
		# Don't follow referrals
		ldap.set_option(ldap.OPT_REFERRALS, 0)


		# TODO finnes flere steder
		def decode_useraccountcontrol(code):
			#https://support.microsoft.com/nb-no/help/305144/how-to-use-useraccountcontrol-to-manipulate-user-account-properties
			active_codes = []
			status_codes = {
					"SCRIPT": 0,
					"ACCOUNTDISABLE": 1,
					"HOMEDIR_REQUIRED": 2,
					"LOCKOUT": 4,
					"PASSWD_NOTREQD": 5,
					"PASSWD_CANT_CHANGE": 6,
					"ENCRYPTED_TEXT_PWD_ALLOWED": 7,
					"TEMP_DUPLICATE_ACCOUNT": 8,
					"NORMAL_ACCOUNT": 9,
					"INTERDOMAIN_TRUST_ACCOUNT": 11,
					"WORKSTATION_TRUST_ACCOUNT": 12,
					"SERVER_TRUST_ACCOUNT": 13,
					"DONT_EXPIRE_PASSWORD": 16,
					"PASSWORD_EXPIRED": 23,
					"MNS_LOGON_ACCOUNT": 17,
					"SMARTCARD_REQUIRED": 18,
					"TRUSTED_FOR_DELEGATION": 19,
					"NOT_DELEGATED": 20,
					"USE_DES_KEY_ONLY": 21,
					"DONT_REQ_PREAUTH": 22,
					"TRUSTED_TO_AUTH_FOR_DELEGATION": 24,
					"PARTIAL_SECRETS_ACCOUNT": 26,
				}
			for key in status_codes:
				if int(code) >> status_codes[key] & 1:
					active_codes.append(key)
			return active_codes


		def ldap_import(virksomhet, eksisterende_brukere, brukerOU):
			# Measure performance, start time
			t0 = time.time()

			# Check if we're using the Python "ldap" 2.4 or greater API
			LDAP24API = LooseVersion(ldap.__version__) >= LooseVersion('2.4')
			BASEDN='OU=' + virksomhet + ',OU=' + brukerOU + ',OU=OK,DC=oslofelles,DC=oslo,DC=kommune,DC=no'
			PAGESIZE = 1000
			ATTRLIST = ['cn', 'givenName', 'sn', 'userAccountControl', 'mail']
			SEARCHFILTER='(objectclass=user)'

			def create_controls(pagesize):
				"""Create an LDAP control with a page size of "pagesize"."""
				# Initialize the LDAP controls for paging. Note that we pass ''
				# for the cookie because on first iteration, it starts out empty.
				if LDAP24API:
					return SimplePagedResultsControl(True, size=pagesize, cookie='')
				else:
					return SimplePagedResultsControl(ldap.LDAP_CONTROL_PAGE_OID, True, (pagesize,''))

			def get_pctrls(serverctrls):
				"""Lookup an LDAP paged control object from the returned controls."""
				# Look through the returned controls and find the page controls.
				# This will also have our returned cookie which we need to make
				# the next search request.
				if LDAP24API:
					return [c for c in serverctrls
							if c.controlType == SimplePagedResultsControl.controlType]
				else:
					return [c for c in serverctrls
							if c.controlType == ldap.LDAP_CONTROL_PAGE_OID]

			def set_cookie(lc_object, pctrls, pagesize):
				"""Push latest cookie back into the page control."""
				if LDAP24API:
					cookie = pctrls[0].cookie
					lc_object.cookie = cookie
					return cookie
				else:
					est, cookie = pctrls[0].controlValue
					lc_object.controlValue = (pagesize,cookie)
					return cookie


			l = ldap.initialize(LDAPSERVER)
			l.protocol_version = 3          # Paged results only apply to LDAP v3
			try:
				l.simple_bind_s(LDAPUSER, LDAPPASSWORD)
			except ldap.LDAPError as e:
				exit('LDAP bind failed: %s' % e)

			# Create the page control to work from
			lc = create_controls(PAGESIZE)

			# Do searches until we run out of "pages" to get from
			# the LDAP server.
			current_round = 0
			objects_returned = 0
			while True:
				current_round += 1
				# Send search request
				try:
					# If you leave out the ATTRLIST it'll return all attributes
					# which you have permissions to access. You may want to adjust
					# the scope level as well (perhaps "ldap.SCOPE_SUBTREE", but
					# it can reduce performance if you don't need it).
					msgid = l.search_ext(BASEDN, ldap.SCOPE_SUBTREE, SEARCHFILTER,
										 ATTRLIST, serverctrls=[lc])
				except ldap.LDAPError as e:
					sys.exit('LDAP search failed: %s' % e)

				# Pull the results from the search request
				try:
					rtype, rdata, rmsgid, serverctrls = l.result3(msgid)
				except ldap.LDAPError as e:
					sys.exit('Could not pull LDAP results: %s' % e)

				# Each "rdata" is a tuple of the form (dn, attrs), where dn is
				# a string containing the DN (distinguished name) of the entry,
				# and attrs is a dictionary containing the attributes associated
				# with the entry. The keys of attrs are strings, and the associated
				# values are lists of strings.
				objects_returned += len(rdata)
				#print("Loaded items: ", len(rdata))
				for dn, attrs in rdata:
					sys.stdout.flush()

					try:
						username = attrs["cn"][0].decode().lower()
					except:
						# vi må ha et brukernavn
						print("?", end="")
						continue

					# et gyldig brukernavn på en bruker er trebokstav (eller DRIFT) + 4-6 siffer
					if not re.match(r"^[a-z]{3}[0-9]{4,6}$", username) and not re.match(r"^drift[0-9]{4,6}$", username):  # username er kun lowercase
						try:
							user = User.objects.get(username=username)
							user.delete()  # TODO dette er kun for opprydding
						except:
							pass

						continue ## ugyldig brukernavn

					try:
						first_name = attrs["givenName"][0].decode()
					except:
						first_name = ""
					try:
						last_name = attrs["sn"][0].decode()
					except:
						last_name = ""
					try:
						email = attrs["mail"][0].decode()
					except:
						email = ""

					try:
						userAccountControl = attrs["userAccountControl"][0].decode()
					except:
						print("\nUserAccountControlError: ", username)
						continue

					def update_user_status(user, userAccountControl):
						userAccountControl_decoded = decode_useraccountcontrol(userAccountControl)
						if "ACCOUNTDISABLE" in userAccountControl_decoded:
							user.profile.accountdisable = True
							user.is_active = False
						else:
							user.profile.accountdisable = False
							user.is_active = True

						if "LOCKOUT" in userAccountControl_decoded:
							user.profile.lockout = True
						else:
							user.profile.lockout = False

						if "PASSWD_NOTREQD" in userAccountControl_decoded:
							user.profile.passwd_notreqd = True
						else:
							user.profile.passwd_notreqd = False

						if "DONT_EXPIRE_PASSWORD" in userAccountControl_decoded:
							user.profile.dont_expire_password = True
						else:
							user.profile.dont_expire_password = False

						if "PASSWORD_EXPIRED" in userAccountControl_decoded:
							user.profile.password_expired = True
						else:
							user.profile.password_expired = False

						if brukerOU == "Eksterne brukere":
							user.profile.ekstern_ressurs = True
						else:
							user.profile.ekstern_ressurs = False

						user.save()
						return user


					global logg_endrede_brukere
					if username in eksisterende_brukere:
						eksisterende_brukere.remove(username)
						if userAccountControl == "512":  # userAccountControl is a string. 512 is a normal active user.
							user = User.objects.get(username=username)
							if user.profile.accountdisable or user.profile.lockout or user.profile.passwd_notreqd or user.profile.dont_expire_password or user.profile.password_expired or not user.is_active:
								user = update_user_status(user, userAccountControl)
								print("u", end="")
								logg_endrede_brukere += 1
							else:
								print("-", end="")  # var allerede aktiv
								continue

						elif userAccountControl == "66048": ## 66050 DONT_EXPIRE_PASSWORD, NORMAL_ACCOUNT,
							user = User.objects.get(username=username)
							if user.profile.accountdisable or user.profile.lockout or user.profile.passwd_notreqd or not user.profile.dont_expire_password or user.profile.password_expired or not user.is_active:
								user = update_user_status(user, userAccountControl)
								print("u", end="")
								logg_endrede_brukere += 1
							else:
								print("-", end="")  # var allerede aktiv
								continue

						elif userAccountControl == "514": ## 514 er deaktivert normal bruker
							user = User.objects.get(username=username)
							if not user.profile.accountdisable or user.profile.lockout or user.profile.passwd_notreqd or user.profile.dont_expire_password or user.profile.password_expired or user.is_active:
								user = update_user_status(user, userAccountControl)
								print("u", end="")
								logg_endrede_brukere += 1
							else:
								print("-", end="")  # var allerede deaktivert
								continue

						elif userAccountControl == "66050": ## 66050 DONT_EXPIRE_PASSWORD, NORMAL_ACCOUNT, ACCOUNTDISABLE
							user = User.objects.get(username=username)
							if not user.profile.accountdisable or user.profile.lockout or user.profile.passwd_notreqd or not user.profile.dont_expire_password or user.profile.password_expired or user.is_active:
								user = update_user_status(user, userAccountControl)
								print("u", end="")
								logg_endrede_brukere += 1
							else:
								print("-", end="")  # var allerede deaktivert
								continue

						else:
							#global optimize_status_codes
							#optimize_status_codes.append(userAccountControl)
							# userAccountControl has some other variation, lets make a full update
							user = User.objects.get(username=username)
							user = update_user_status(user, userAccountControl)

					else:
						# bruker finnes ikke
						try:
							user = User.objects.create_user(username=username)
						except:
							print("\n\n***\nKunne ikke opprette bruker med brukernavn ", username, "\n***\n\n")
							continue
						user.first_name = first_name
						user.last_name = last_name
						user.email = email
						try:
							virksomhet_tbf = username[0:3].upper()
							if username[0:5].upper() == "DRIFT": # all usernames are 3 letters by default in Oslo kommune, except DRIFT
								virksomhet_tbf = "DRIFT"
							virksomhet_obj_ref = Virksomhet.objects.get(virksomhetsforkortelse=virksomhet_tbf)
							user.profile.virksomhet = virksomhet_obj_ref
						except:
							#print("Kunne ikke linke opp virksomhet for " + username)
							pass
						user = update_user_status(user, userAccountControl)
						print("n", end="")
						global logg_antall_nye_brukere
						logg_antall_nye_brukere += 1

				# Get cookie for next request
				pctrls = get_pctrls(serverctrls)
				if not pctrls:
					print >> sys.stderr, 'Warning: Server ignores RFC 2696 control.'
					break

				# Ok, we did find the page control, yank the cookie from it and
				# insert it into the control for our next search. If however there
				# is no cookie, we are done!
				cookie = set_cookie(lc, pctrls, PAGESIZE)
				if not cookie:
					break

			# Clean up
			l.unbind()

			# Measure performance, end time and print time of execution
			t1 = time.time()
			print("\nObjekter funnet: ", objects_returned, " (", current_round ," sider)")
			global logg_antall_identer_funnet
			logg_antall_identer_funnet += objects_returned
			#print("Runtime: ", t1 - t0)

			return eksisterende_brukere


		def OU_lookup():
			l = ldap.initialize(LDAPSERVER)
			l.bind_s(LDAPUSER, LDAPPASSWORD)
			virksomheter = []
			query_result = l.search_s(
					'OU=Brukere,OU=OK,DC=oslofelles,DC=oslo,DC=kommune,DC=no',
					ldap.SCOPE_ONELEVEL,
					('objectCategory=organizationalUnit'),
					['ou',]
				)
			for key in query_result:
				#ou = query_result[0][1][0].decode()
				virksomheter.append(key[1]["ou"][0].decode())
			l.unbind_s()
			return virksomheter


		from django.db.models.functions import Upper
		gyldige_virksomheter = list(Virksomhet.objects.values_list(Upper('virksomhetsforkortelse'), flat=True).distinct())

		eksisterende_brukere = list(User.objects.filter(is_superuser=False).values_list("username", flat=True))

		virksomheter = OU_lookup()
		print("Antall virksomheter: ", len(virksomheter))
		for virksomhet in virksomheter:
			print("\nLaster brukere fra ", virksomhet)
			virksomhet_uppercase = virksomhet.upper()
			if virksomhet_uppercase in gyldige_virksomheter:
				gyldige_virksomheter.remove(virksomhet_uppercase)
				print("Laster interne brukere...")
				eksisterende_brukere = ldap_import(virksomhet, eksisterende_brukere, "Brukere")
				print("Laster eksterne brukere...")
				eksisterende_brukere = ldap_import(virksomhet, eksisterende_brukere, "Eksterne brukere")

		print("\nVirksomheter det ikke var brukere for i AD: ", gyldige_virksomheter)
		print("Brukere igjen i oversikt: ", len(eksisterende_brukere))

		global logg_antall_nye_brukere
		global logg_antall_identer_funnet
		global logg_endrede_brukere

		print("\nDeaktiverer brukere som ikke ble funnet")
		#print("Brukere som ikke ble funnet igjen: ", eksisterende_brukere)
		for manglende_bruker in eksisterende_brukere:
			try:
				u = User.objects.get(username=manglende_bruker)
				if u.is_active:
					u.is_active = False
					u.save()
					print("r", end="")
					logg_endrede_brukere += 1
				else:
					print("-", end="")
			except ObjectDoesNotExist:
				pass

			sys.stdout.flush()



		### dette brukes bare for opprydding
		"""print("Fikse brukere som har blitt deaktivert feil")
		erronious_disabled_users = User.objects.filter(is_active=False).filter(profile__accountdisable=False)
		print(erronious_disabled_users)
		for e in erronious_disabled_users:
			e.is_active = True
			e.save()
			print(".", end="")
			sys.stdout.flush()
		"""


		runetime_t1 = time.time()
		logg_total_runtime = runetime_t1 - runetime_t0
		print("Total runtime: ", logg_total_runtime)

		#from collections import Counter
		#global optimize_status_codes
		#print(Counter(optimize_status_codes).keys())
		#print(Counter(optimize_status_codes).values())


		logg_entry_message = "Kjøretid: %s, antall brukere: %s, nye brukere: %s, endrede brukere: %s, fant ikke: %s" % (
				round(logg_total_runtime, 1),
				logg_antall_identer_funnet,
				logg_antall_nye_brukere,
				logg_endrede_brukere,
				gyldige_virksomheter
		)
		logg_entry = ApplicationLog.objects.create(
				event_type='LDAP import',
				message=logg_entry_message,
		)
		logg_entry.save()

