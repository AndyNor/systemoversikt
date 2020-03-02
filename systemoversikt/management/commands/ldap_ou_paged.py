# -*- coding: utf-8 -*-
""" Hensikten med denne koden er """

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.utils import ldap_paged_search
import ldap
import sys

from systemoversikt.models import ApplicationLog, ADOrgUnit


class Command(BaseCommand):
	def handle(self, **options):

		# Configuration
		BASEDN ='DC=oslofelles,DC=oslo,DC=kommune,DC=no'
		SEARCHFILTER = '(objectclass=organizationalUnit)'
		LDAP_SCOPE = ldap.SCOPE_SUBTREE
		ATTRLIST = ['ou', 'whenCreated']  # if empty we get all attr we have access to
		PAGESIZE = 1000
		LOG_EVENT_TYPE = "AD OU-import"

		report_data = {
			"created": 0,
			"modified": 0,
			"removed": 0,
		}

		@transaction.atomic  # for speeding up database performance
		def result_handler(rdata, report_data, existing_objects=None):
			for dn, attrs in rdata:
				#report_data["removed"] += 1

				distinguishedname = dn

				ou = ""
				if "ou" in attrs:
					ou = attrs["ou"][0].decode()

				whenCreated = ""
				if "whenCreated" in attrs:
					whenCreated = attrs["whenCreated"][0].decode()

				if distinguishedname == None:
					print("\n%s" % (attrs), end="")
					continue

				try:
					g = ADOrgUnit.objects.get(distinguishedname=distinguishedname)
					g.ou = ou
					g.when_created = whenCreated
					g.save()

					report_data["modified"] += 1
					print("u", end="")
				except:
					g = ADOrgUnit.objects.create(
							distinguishedname=distinguishedname,
							ou=ou,
							when_created=whenCreated,
						)
					print("n", end="")
					report_data["created"] += 1

				sys.stdout.flush()

		@transaction.atomic  # for speeding up database performance
		def map_child_mother():
			print("Trying to find parents for all the children")
			for ou in ADOrgUnit.objects.all():
				parent_str = ",".join(ou.distinguishedname.split(',')[1:])
				try:
					parent = ADOrgUnit.objects.get(distinguishedname=parent_str)
					ou.parent = parent
					ou.save()
				except:
					pass
			print("Done, preparing stats")


		def report(result):
			log_entry_message = "Det tok %s sekunder. %s treff. %s nye, %s endrede og %s slettede elementer." % (
					result["total_runtime"],
					result["objects_returned"],
					result["report_data"]["created"],
					result["report_data"]["modified"],
					result["report_data"]["removed"],
			)
			log_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=log_entry_message,
			)
			print(log_entry_message)


		result = ldap_paged_search(BASEDN, SEARCHFILTER, LDAP_SCOPE, ATTRLIST, PAGESIZE, result_handler, report_data)
		map_child_mother()
		report(result)

