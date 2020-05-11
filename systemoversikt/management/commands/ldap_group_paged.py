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

		LOG_EVENT_TYPE = "AD group-import"
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

		# Configuration
		BASEDN ='DC=oslofelles,DC=oslo,DC=kommune,DC=no'
		SEARCHFILTER = '(objectclass=group)'
		LDAP_SCOPE = ldap.SCOPE_SUBTREE
		ATTRLIST = ['cn', 'description', 'memberOf', 'member'] # if empty we get all attr we have access to
		PAGESIZE = 5000

		report_data = {
			"created": 0,
			"modified": 0,
			"removed": 0,
		}

		@transaction.atomic  # for speeding up database performance
		def cleanup():
			from django.db.models import Count
			duplicates = ADgroup.objects.values("distinguishedname").annotate(count=Count("distinguishedname")).filter(count__gt=1)
			for group in duplicates:
				group = ADgroup.objects.filter(distinguishedname=group["distinguishedname"])
				group.delete()

		cleanup()


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
						if membercount == 0:
							try:
								#https://bgstack15.wordpress.com/tag/ldap/
								binary_member = attrs["member;range=0-4999"]
								membercount = len(binary_member)
							except:
								pass  # do nothing
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


					# dette er ikke så lurt, om noe skulle feile av annen grunn enn object.get..
					try:
						g = ADgroup.objects.get(distinguishedname=distinguishedname)
						try:
							g.common_name = distinguishedname[3:].split(",")[0]
						except:
							g.common_name = None

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