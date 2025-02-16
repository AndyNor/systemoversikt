# -*- coding: utf-8 -*-

def ldap_paged_search(BASEDN, SEARCHFILTER, LDAP_SCOPE, ATTRLIST, PAGESIZE, result_handler, report_data, existing_objects=None):
	from ldap.controls import SimplePagedResultsControl
	from distutils.version import LooseVersion

	import os
	import time
	import ldap

	LDAPUSER = os.environ["KARTOTEKET_LDAPUSER"]
	LDAPPASSWORD = os.environ["KARTOTEKET_LDAPPASSWORD"]
	LDAPSERVER = os.environ["KARTOTEKET_LDAPSERVER"]

	ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # self signed
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
		raise Exception(f'ERROR: LDAP bind failed: {e}')

	lc = create_controls(PAGESIZE)


	# Search and loop until no more pages
	current_round = 0
	objects_returned = 0
	while True:
		current_round += 1
		try:
			msgid = l.search_ext(BASEDN, LDAP_SCOPE, SEARCHFILTER, ATTRLIST, serverctrls=[lc])
		except ldap.LDAPError as e:
			raise Exception(f'ERROR: LDAP search failed: {e}')

		try:
			rtype, rdata, rmsgid, serverctrls = l.result3(msgid)
		except ldap.LDAPError as e:
			raise Exception(f'ERROR: Could not pull LDAP results: {e}')

		objects_start = objects_returned + 1
		objects_returned += len(rdata)
		print(f"Page {current_round}: {objects_start}-{objects_returned}")

		# Do stuff with results
		result_handler(rdata, report_data, existing_objects)
		#time.sleep(2)

		pctrls = get_pctrls(serverctrls)
		if not pctrls:
			print('WARNING: Server ignores RFC 2696 control.')
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
