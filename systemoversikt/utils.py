# -*- coding: utf-8 -*-
""" Her er funksjoner som gjenbrukes ofte og derfor er skilt ut """

def microsoft_date_decode(timestamp):
	import pytz
	if timestamp == b'9223372036854775807' or timestamp == b'0':
		return None #

	from django.utils.timezone import make_aware
	import datetime

	ms_timestamp = int(timestamp[:-1])  # removing one trailing digit: steps of 100ns to steps pf 1 micro second.
	ms_epoch_start = datetime.datetime(1601,1,1)
	timedelta = datetime.timedelta(microseconds=ms_timestamp)
	try:
		return make_aware(ms_epoch_start + timedelta)
	except (pytz.NonExistentTimeError, pytz.AmbiguousTimeError):
		return make_aware(ms_epoch_start + timedelta + datetime.timedelta(hours=1))  # her velger vi bare å dytte tiden frem.



def ldap_OK_virksomheter():
	l = ldap.initialize(os.environ["KARTOTEKET_LDAPSERVER"])
	l.bind_s(os.environ["KARTOTEKET_LDAPUSER"], os.environ["KARTOTEKET_LDAPPASSWORD"])
	virksomheter = []
	query_result = l.search_s(
			'OU=Brukere,OU=OK,DC=oslofelles,DC=oslo,DC=kommune,DC=no',
			ldap.SCOPE_ONELEVEL,
			('objectCategory=organizationalUnit'),
			['ou',]
		)
	for key in query_result:
		virksomheter.append(key[1]["ou"][0].decode())
	l.unbind_s()
	return virksomheter


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


def ldap_paged_search(BASEDN, SEARCHFILTER, LDAP_SCOPE, ATTRLIST, PAGESIZE, result_handler, report_data, existing_objects=None):

	from ldap.controls import SimplePagedResultsControl
	from distutils.version import LooseVersion

	import os
	import sys
	import time
	import ldap

	"""
	Factoring out this part. Example parameters:
		BASEDN ='OU=Administrasjon,DC=oslofelles,DC=oslo,DC=kommune,DC=no'
		SEARCHFILTER = '(objectclass=group)'
		LDAP_SCOPE = ldap.SCOPE_SUBTREE
		ATTRLIST = ['cn', 'description',]  # if empty we get all attr we have access to
		PAGESIZE = 1000
	"""
	LDAPUSER = os.environ["KARTOTEKET_LDAPUSER"]
	LDAPPASSWORD = os.environ["KARTOTEKET_LDAPPASSWORD"]
	LDAPSERVER = os.environ["KARTOTEKET_LDAPSERVER"]

	ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)  # TODO this is unsafe
	ldap.set_option(ldap.OPT_REFERRALS, 0)
	LDAP24API = LooseVersion(ldap.__version__) >= LooseVersion('2.4')

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

	# Initiate
	runtime_t0 = time.time()

	l = ldap.initialize(LDAPSERVER)
	l.protocol_version = 3  # Paged results require versjon 3
	try:
		l.simple_bind_s(LDAPUSER, LDAPPASSWORD)
	except ldap.LDAPError as e:
		exit('ERROR: LDAP bind failed: %s' % e)

	lc = create_controls(PAGESIZE)


	# Search and loop until no more pages
	current_round = 0
	objects_returned = 0
	while True:
		current_round += 1
		try:
			msgid = l.search_ext(BASEDN, LDAP_SCOPE, SEARCHFILTER, ATTRLIST, serverctrls=[lc])
		except ldap.LDAPError as e:
			sys.exit('ERROR: LDAP search failed: %s' % e)

		try:
			rtype, rdata, rmsgid, serverctrls = l.result3(msgid)
		except ldap.LDAPError as e:
			sys.exit('ERROR: Could not pull LDAP results: %s' % e)
		objects_start = objects_returned + 1
		objects_returned += len(rdata)
		#print("\nINFO: New page %s (%s-%s)" % (current_round, objects_start, objects_returned))

		# Do stuff with results
		result_handler(rdata, report_data, existing_objects)

		pctrls = get_pctrls(serverctrls)
		if not pctrls:
			print >> sys.stderr, 'WARNING: Server ignores RFC 2696 control.'
			break

		cookie = set_cookie(lc, pctrls, PAGESIZE)
		if not cookie:
			runtime_t1 = time.time()
			total_runtime = round(runtime_t1 - runtime_t0, 2)
			#print("\nINFO: No more pages, %s results returned." % (objects_returned))
			break  # Done

	l.unbind()
	return({
		"report_data": report_data,
		"total_runtime": total_runtime,
		"objects_returned": objects_returned
	})
