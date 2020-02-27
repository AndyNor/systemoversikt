# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å oppdatere en lokal oversikt over alle AD-grupper, både for å kunne analysere medlemskap, f.eks. tomme grupper, kunne finne grupper som ikke stammer fra AD, kunne følge med på opprettelse av nye grupper.
"""

# TODO slette grupper som ikke ble funnet

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.utils import ldap_paged_search
import ldap
import sys


from systemoversikt.models import ApplicationLog, ADOrgUnit, ADgroup
import json

class Command(BaseCommand):
	def handle(self, **options):

		# Configuration
		BASEDN ='DC=oslofelles,DC=oslo,DC=kommune,DC=no'
		SEARCHFILTER = '(objectclass=group)'
		LDAP_SCOPE = ldap.SCOPE_SUBTREE
		ATTRLIST = ['cn', 'description', 'memberOf', 'member'] # if empty we get all attr we have access to
		PAGESIZE = 1000
		LOG_EVENT_TYPE = "AD group-import"

		report_data = {
			"created": 0,
			"modified": 0,
			"removed": 0,
		}

		@transaction.atomic  # for speeding up database performance
		def result_handler(rdata, report_data, existing_objects=None):
			for dn, attrs in rdata:

					distinguishedname = dn
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

					description = ""
					try:
						binary_description = attrs["description"]
						for d in binary_description:
							description += d.decode()
					except KeyError as e:
						pass

					try:
						g = ADgroup.objects.get(distinguishedname=distinguishedname)
						g.description = description
						g.member = member
						g.membercount = membercount
						g.memberof = memberof
						g.memberofcount = memberofcount
						g.save()
						report_data["modified"] += 1
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
						report_data["created"] += 1

					sys.stdout.flush()


		def report(result):
			log_entry_message = "Det tok %s sekunder. %s treff. %s nye, %s endrede." % (
					result["total_runtime"],
					result["objects_returned"],
					result["report_data"]["created"],
					result["report_data"]["modified"],
			)
			log_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=log_entry_message,
			)
			print(log_entry_message)


		result = ldap_paged_search(BASEDN, SEARCHFILTER, LDAP_SCOPE, ATTRLIST, PAGESIZE, result_handler, report_data)
		report(result)