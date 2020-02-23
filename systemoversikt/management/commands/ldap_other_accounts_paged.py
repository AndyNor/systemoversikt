# -*- coding: utf-8 -*-

"""
Hensikten med denne koden er å oppdatere en lokal oversikt over alle AD-grupper, både for å kunne analysere medlemskap, f.eks. tomme grupper, kunne finne grupper som ikke stammer fra AD, kunne følge med på opprettelse av nye grupper.
"""

from django.core.management.base import BaseCommand
from ldap.controls import SimplePagedResultsControl
from distutils.version import LooseVersion
from django.contrib.auth.models import User
from systemoversikt.models import ADUser, ApplicationLog, PRKuser
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import make_aware
import sys
import time
import ldap
import os
import datetime

logg_antall_nye_kontoer = 0
logg_antall_eksisterende_kontoer = 0

## TODO flere steder
def microsoft_date_decode(timestamp):
	ms_timestamp = int(timestamp[:-1])  # removing one trailing digit: steps of 100ns to steps pf 1 micro second.
	ms_epoch_start = datetime.datetime(1601,1,1)
	timedelta = datetime.timedelta(microseconds=ms_timestamp)
	return make_aware(ms_epoch_start + timedelta)


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

class Command(BaseCommand):
	def handle(self, **options):

		runtime_t0 = time.time()  # start time

		LDAPUSER = os.environ["KARTOTEKET_LDAPUSER"]
		LDAPPASSWORD = os.environ["KARTOTEKET_LDAPPASSWORD"]
		LDAPSERVER='ldaps://ldaps.oslofelles.oslo.kommune.no:636'

		# Ignore server side certificate errors (assumes using LDAPS and
		# self-signed cert). Not necessary if not LDAPS or it's signed by
		# a real CA.
		ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)
		# Don't follow referrals
		ldap.set_option(ldap.OPT_REFERRALS, 0)

		def ldap_search(basedn, pagesize, attrlist, searchfiler):

			# Check if we're using the Python "ldap" 2.4 or greater API
			LDAP24API = LooseVersion(ldap.__version__) >= LooseVersion('2.4')
			BASEDN = basedn
			PAGESIZE = pagesize
			ATTRLIST = attrlist
			SEARCHFILTER = searchfiler

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

				for distinguishedname, attrs in rdata:

					if distinguishedname == None:
						print(attrs)
						continue

					sAMAccountName = attrs["sAMAccountName"][0].decode().lower()

					if len(User.objects.filter(username=sAMAccountName)) > 0:
						continue  # it's already in the User database

					userAccountControl = decode_useraccountcontrol(int(attrs["userAccountControl"][0].decode()))

					try:
						description = attrs["description"][0].decode()
					except KeyError:
						description = ""

					try:
						displayName = attrs["displayName"][0].decode()
					except KeyError:
						displayName = ""

					try:
						etternavn = attrs["sn"][0].decode()
					except KeyError:
						etternavn = ""

					try:
						fornavn = attrs["givenName"][0].decode()
					except KeyError:
						fornavn = ""

					try:
						lastLogonTimestamp = microsoft_date_decode(attrs["lastLogonTimestamp"][0].decode())
					except KeyError:
						lastLogonTimestamp = None

					if len(PRKuser.objects.filter(username=sAMAccountName)) > 0:
						from_prk = True
					else:
						from_prk = False


					try:
						g = ADUser.objects.get(sAMAccountName=sAMAccountName)
						g.distinguishedname = distinguishedname
						g.userAccountControl = userAccountControl
						g.description = description
						g.displayName = displayName
						g.etternavn = etternavn
						g.fornavn = fornavn
						g.lastLogonTimestamp = lastLogonTimestamp
						g.from_prk = from_prk
						g.save()

						global logg_antall_eksisterende_kontoer
						logg_antall_eksisterende_kontoer += 1
						nonlocal existing_users
						existing_users.remove(g)
						print("u", end="")
					except ObjectDoesNotExist:
						g = ADUser.objects.create(
								distinguishedname=distinguishedname,
								sAMAccountName=sAMAccountName,
								userAccountControl=userAccountControl,
								description=description,
								displayName=displayName,
								etternavn=etternavn,
								fornavn=fornavn,
								lastLogonTimestamp=lastLogonTimestamp,
								from_prk=from_prk,
							)
						print("n", end="")
						global logg_antall_nye_kontoer
						logg_antall_nye_kontoer += 1

					sys.stdout.flush()


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


		### runtime ###
		basedn ='OU=KAO,OU=Brukere,OU=OK,DC=oslofelles,DC=oslo,DC=kommune,DC=no'
		pagesize = 1000
		attrlist = ['description', 'sn', 'givenName', 'displayName', 'sAMAccountName', 'lastLogonTimestamp', 'userAccountControl']
		searchfiler = '(objectclass=user)'

		existing_users = list(ADUser.objects.all())

		ldap_search(basedn, pagesize, attrlist, searchfiler)

		logg_antall_slettede_kontoer = 0
		for u in existing_users:
			u.delete()
			# fjerne "i PRK" fra users (en eller to?)
			logg_antall_slettede_kontoer += 1

		runtime_t1 = time.time() # end time
		logg_total_runtime = runtime_t1 - runtime_t0
		global logg_antall_nye_kontoer

		logg_entry_message = "Kjøretid: %s sekunder: importerte %s kontoer. %s eksisterte. %s gamle slettet" % (
				round(logg_total_runtime, 1),
				logg_antall_nye_kontoer,
				logg_antall_eksisterende_kontoer,
				logg_antall_slettede_kontoer
		)
		print("\n")
		print(logg_entry_message)
		logg_entry = ApplicationLog.objects.create(
				event_type='LDAP import of nonhuman useraccounts',
				message=logg_entry_message,
		)
		logg_entry.save()

