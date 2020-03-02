# -*- coding: utf-8 -*-

#TODO teste

"""
Hensikten med denne koden er å oppdatere en lokal oversikt over alle AD-grupper, både for å kunne analysere medlemskap, f.eks. tomme grupper, kunne finne grupper som ikke stammer fra AD, kunne følge med på opprettelse av nye grupper.
"""
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.utils import ldap_paged_search, decode_useraccountcontrol, microsoft_date_decode
import ldap
import sys

from django.contrib.auth.models import User
from systemoversikt.models import ADUser, ApplicationLog, PRKuser
import time
import os

class Command(BaseCommand):
	def handle(self, **options):

		# Configuration
		BASEDN ='DC=oslofelles,DC=oslo,DC=kommune,DC=no'
		SEARCHFILTER = '(objectclass=user)'
		LDAP_SCOPE = ldap.SCOPE_SUBTREE
		ATTRLIST = ['description', 'sn', 'givenName', 'displayName', 'sAMAccountName', 'lastLogonTimestamp', 'userAccountControl']  # if empty we get all attr we have access to
		PAGESIZE = 1000
		LOG_EVENT_TYPE = "AD users other"

		report_data = {
			"created": 0,
			"modified": 0,
			"removed": 0,
		}

		@transaction.atomic  # for speeding up database performance
		def result_handler(rdata, report_data, existing_objects=None):
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

					report_data["modified"] += 1

					if g in existing_objects:
						existing_objects.remove(g)
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
					report_data["created"] += 1

				sys.stdout.flush()

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



		existing_users = list(ADUser.objects.all())
		result = ldap_paged_search(BASEDN, SEARCHFILTER, LDAP_SCOPE, ATTRLIST, PAGESIZE, result_handler, report_data, existing_users)

		print("Sletter eksisterende brukere som ikke ble funnet denne kjøringen..")
		print(len(existing_users))
		for u in existing_users:
			u.delete()
			result["report_data"]["removed"] += 1
			print("x", end="")

		report(result)
