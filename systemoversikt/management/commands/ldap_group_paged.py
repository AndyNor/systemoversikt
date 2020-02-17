from django.core.management.base import BaseCommand
from ldap.controls import SimplePagedResultsControl
from distutils.version import LooseVersion
from systemoversikt.models import ADgroup, ApplicationLog
import sys
import time
import ldap
import os
import json

logg_antall_grupper = 0
logg_antall_eksisterende_grupper = 0

class Command(BaseCommand):
	def handle(self, **options):

		runetime_t0 = time.time()  # start time

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
				for dn, attrs in rdata:

					distinguishedname = dn
					#print(distinguishedname)
					if distinguishedname == None:
						print(attrs)
						continue

					try:
						member = []
						binary_member = attrs["member"]
						membercount = len(binary_member)
						for m in binary_member:
							member.append(m.decode())
					except KeyError as e:
						member = []
						membercount = 0
					member = json.dumps(member)
					#print(member)
					#print(membercount)

					try:
						memberof = []
						binary_memberof = attrs["memberOf"]
						memberofcount = len(binary_memberof)
						for m in binary_memberof:
							memberof.append(m.decode())
					except KeyError as e:
						memberof = []
						memberofcount = 0
					memberof = json.dumps(memberof)
					#print(memberof)
					#print(memberofcount)


					description = ""
					try:
						binary_description = attrs["description"]
						for d in binary_description:
							description += d.decode()
					except KeyError as e:
						pass
					#print(description)

					try:
						g = ADgroup.objects.get(distinguishedname=distinguishedname)
						g.description = description
						g.member = member
						g.membercount = membercount
						g.memberof = memberof
						g.memberofcount = memberofcount
						g.save()

						global logg_antall_eksisterende_grupper
						logg_antall_eksisterende_grupper += 1
						print("u", end="")
					except:
						g = ADgroup.objects.create(
								distinguishedname=distinguishedname,
								description=description,
								member=member,
								membercount=membercount,
								memberof=memberof,
								memberofcount=memberofcount,
							)
						print("n", end="")
						global logg_antall_grupper
						logg_antall_grupper += 1

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
		basedn ='OU=UKE,OU=Distribusjonsgrupper,OU=OK,DC=oslofelles,DC=oslo,DC=kommune,DC=no'
		pagesize = 1000
		attrlist = ['cn', 'description', 'memberOf', 'member']
		searchfiler = '(objectclass=group)'
		ldap_search(basedn, pagesize, attrlist, searchfiler)

		runetime_t1 = time.time() # end time
		logg_total_runtime = runetime_t1 - runetime_t0
		global logg_antall_grupper

		logg_entry_message = "Kjøretid: %s sekunder, importerte %s grupper. %s eksisterte" % (
				round(logg_total_runtime, 1),
				logg_antall_grupper,
				logg_antall_eksisterende_grupper,
		)
		print("\n")
		print(logg_entry_message)
		logg_entry = ApplicationLog.objects.create(
				event_type='LDAP group import',
				message=logg_entry_message,
		)
		logg_entry.save()

