# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å oppdatere en lokal oversikt over alle AD-grupper, både for å kunne analysere medlemskap, f.eks. tomme grupper, kunne finne grupper som ikke stammer fra AD, kunne følge med på opprettelse av nye grupper.
"""

# TODO slette grupper som ikke ble funnet

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.utils import ldap_paged_search
from datetime import timedelta
from django.utils import timezone
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
		ATTRLIST = ['cn', 'description', 'memberOf', 'member', 'displayName', 'mail'] # if empty we get all attr we have access to
		PAGESIZE = 5000

		report_data = {
			"created": 0,
			"modified": 0,
			"removed": 0,
		}

		@transaction.atomic
		def remove_unseen_groups():
			old_groups = ADgroup.objects.filter(sist_oppdatert__lte=timezone.now()-timedelta(hours=12)) # det vil aldri gå mer enn noen få minutter, men for å være sikker..
			print("sletter %s utgåtte grupper" % len(old_groups))
			for g in old_groups:
				g.delete()
			log_entry_message = ', '.join([str(g.common_name) for g in old_groups])
			log_entry = ApplicationLog.objects.create(
					event_type="AD-grupper slettet",
					message=log_entry_message,
			)
			print(log_entry_message)

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
						if membercount == 0: # skjer enten fordi gruppen er tom, eller fordi det er flere enn 5000 medlemmer (i denne AD-en, kan settes til en annen verdi i AD)
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

					mail = ""
					try:
						binary_description = attrs["mail"]
						for d in binary_description:
							mail += d.decode()
					except KeyError as e:
						pass

					try:
						common_name = distinguishedname[3:].split(",")[0]
					except:
						common_name = None

					displayname = ""
					try:
						displayname = attrs["displayName"][0].decode()
					except KeyError as e:
						pass

					try:
						g = ADgroup.objects.get(distinguishedname=distinguishedname)
						print("u", end="")
						report_data["modified"] += 1
					except:
						g = ADgroup.objects.create(distinguishedname=distinguishedname) # lager den om den ikke finnes
						print("n", end="")
						report_data["created"] += 1

					g.common_name = common_name
					g.description = description
					g.member = member
					g.membercount = membercount
					g.memberof = memberof
					g.memberofcount = memberofcount
					g.display_name = displayname
					g.mail = mail
					g.save()

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


		# her kjører selve synkroniseringen
		result = ldap_paged_search(BASEDN, SEARCHFILTER, LDAP_SCOPE, ATTRLIST, PAGESIZE, result_handler, report_data)
		report(result)
		remove_unseen_groups()


		@transaction.atomic  # uklart om det er behov for denne lenger. trolig noe som gikk galt første kjøringer av scripetet..
		def cleanup():
			from django.db.models import Count
			duplicates = ADgroup.objects.values("distinguishedname").annotate(count=Count("distinguishedname")).filter(count__gt=1)
			for group in duplicates:
				group = ADgroup.objects.filter(distinguishedname=group["distinguishedname"])
				print("rydder opp %s" % (group["distinguishedname"]))
				group.delete()

		cleanup()