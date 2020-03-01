# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å laste inn alle orginære brukre koblet til en av kommunens vikrsomheter, slik at man i kartoteket kan tildele ansvar til en faktisk brukeridentitet. Her laster vi ikke inn manuelt opprettede brukere som ikke kommer fra PRK.
Denne importen vil ikke kunne svare på forskjeller mellom AD og PRK. Det er andre jobber som identifiserer slike avvik.
"""

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.utils import ldap_paged_search, decode_useraccountcontrol, ldap_OK_virksomheter
import ldap
import sys

from django.contrib.auth.models import User
from systemoversikt.models import Virksomhet, ApplicationLog
from django.db.models.functions import Upper
import json
import re

class Command(BaseCommand):
	def handle(self, **options):

		# Configuration
		BASEDN ='OU=OK,DC=oslofelles,DC=oslo,DC=kommune,DC=no'
		SEARCHFILTER = '(objectclass=user)'
		LDAP_SCOPE = ldap.SCOPE_SUBTREE
		ATTRLIST = ['cn', 'givenName', 'sn', 'userAccountControl', 'mail'] # if empty we get all attr we have access to
		PAGESIZE = 1000
		LOG_EVENT_TYPE = "AD user-import"

		report_data = {
			"created": 0,
			"modified": 0,
			"removed": 0,
		}

		def update_user_status(user, dn, attrs, user_organization):

			if "userAccountControl" in attrs:
				userAccountControl = attrs["userAccountControl"][0].decode()
			else:
				print("c", end="")
				return

			try:
				virksomhet_tbf = user_organization.upper()
				virksomhet_obj_ref = Virksomhet.objects.get(virksomhetsforkortelse=virksomhet_tbf)
				user.profile.virksomhet = virksomhet_obj_ref
			except:
				pass

			first_name = ""
			if "givenName" in attrs:
				first_name = attrs["givenName"][0].decode()
			user.first_name = first_name

			last_name = ""
			if "sn" in attrs:
				last_name = attrs["sn"][0].decode()
			user.last_name = last_name

			email = ""
			if "mail" in attrs:
				email = attrs["mail"][0].decode()
			user.email = email

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
			if "OU=Eksterne brukere" in dn:
				user.profile.ekstern_ressurs = True
			if "OU=Brukere" in dn:
				user.profile.ekstern_ressurs = False
			user.save()
			return user


		@transaction.atomic  # for speeding up database performance
		def result_handler(rdata, report_data, existing_objects=None):

			gyldige_virksomheter = list(Virksomhet.objects.values_list(Upper('virksomhetsforkortelse'), flat=True).distinct())

			for dn, attrs in rdata:
				sys.stdout.flush()

				if "cn" in attrs:
					username = attrs["cn"][0].decode().lower()
				else:
					print("?", end="")
					continue  # vi må ha et brukernavn

				if not ("OU=Eksterne brukere" in dn or "OU=Brukere" in dn):
					#TODO prøv å slette for å rydde opp
					continue  # ikke en person

				user_organization = dn.split(",")[1][3:]  # andre OU, fjerner "OU=" som er tegn 0-2.
				if user_organization not in gyldige_virksomheter:
					print("?", end="")
					continue

				# et gyldig brukernavn på en bruker er trebokstav (eller DRIFT) + 4-6 siffer
				if not re.match(r"^[a-z]{3}[0-9]{4,6}$", username) and not re.match(r"^drift[0-9]{4,6}$", username):  # username er kun lowercase
					print("b", end="")
					continue # ugyldig brukernavn

				if username in existing_objects:
					existing_objects.remove(username) # holde track på brukere som ikke lenger finnes

					user = User.objects.get(username=username)
					user = update_user_status(user, dn, attrs, user_organization)

					print("u", end="")
					report_data["modified"] += 1

				else: # bruker finnes ikke
					try:
						user = User.objects.create_user(username=username)
					except:
						print("\nKunne ikke opprette bruker med brukernavn '%s'" % username)
						continue

					user = update_user_status(user, dn, attrs, user_organization)

					print("n", end="")
					report_data["created"] += 1


		def report(result):
			#print("\nVirksomheter det ikke var brukere for i AD: ", gyldige_virksomheter)
			#print("\nVirksomheter som ikke er i kartoteket: ", ad_grupper_utenfor_kartoteket)
			log_entry_message = "Det tok %s sekunder. %s treff. %s nye, %s oppdatert." % (
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


		# Start søk og opprydding
		existing_objects = list(User.objects.values_list("username", flat=True))

		result = ldap_paged_search(BASEDN, SEARCHFILTER, LDAP_SCOPE, ATTRLIST, PAGESIZE, result_handler, report_data, existing_objects)

		print("Deaktiverer brukere som ikke ble funnet")

		@transaction.atomic  # for speeding up database performance
		def cleanup(existing_objects, result):
			for b in existing_objects:
				try:
					u = User.objects.get(username=b)
					if u.is_superuser:
						continue # don't mess with super users
					if u.is_active:
						u.is_active = False
						u.save()
						print("r", end="")
						result["report_data"]["modified"] += 1
					else:
						print("-", end="")
				except ObjectDoesNotExist:
					pass
				sys.stdout.flush()
			print("")

		cleanup(existing_objects, result)

		report(result)
