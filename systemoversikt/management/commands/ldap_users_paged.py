# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å laste inn alle ordinære brukere koblet til en av kommunens vikrsomheter, slik at man i kartoteket kan tildele ansvar til en faktisk brukeridentitet. Her laster vi ikke inn manuelt opprettede brukere som ikke kommer fra PRK.
Denne importen vil ikke kunne svare på forskjeller mellom AD og PRK. Det er andre jobber som identifiserer slike avvik.
"""

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.utils import ldap_paged_search, decode_useraccountcontrol, ldap_OK_virksomheter, microsoft_date_decode
import ldap
import sys
import datetime

from django.contrib.auth.models import User
from systemoversikt.models import Virksomhet, ApplicationLog, ADOrgUnit, UserChangeLog, AnsattID
from django.db.models.functions import Upper
import json
import re

class Command(BaseCommand):
	def handle(self, **options):

		LOG_EVENT_TYPE = "AD user-import"
		ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

		# Configuration
		BASEDN ='DC=oslofelles,DC=oslo,DC=kommune,DC=no'
		SEARCHFILTER = '(&(objectCategory=person)(objectClass=user))'
		LDAP_SCOPE = ldap.SCOPE_SUBTREE
		ATTRLIST = ['cn', 'givenName', 'sn', 'userAccountControl', 'mail', 'msDS-UserPasswordExpiryTimeComputed', 'description', 'displayName', 'sAMAccountName', 'lastLogonTimestamp', 'whenCreated'] # if empty we get all attr we have access to
		PAGESIZE = 2000

		report_data = {
			"created": 0,
			"modified": 0,
			"deaktivert": 0,
			"reaktivert": 0,
			"removed": 0,
			"user_not_deleted": [],
		}

		def update_user_status(user, dn, attrs, user_organization, report_data):

			if "userAccountControl" in attrs:
				userAccountControl = int(attrs["userAccountControl"][0].decode())
			else:
				print("-uac-", end="")
				return
			userAccountControl_decoded = decode_useraccountcontrol(userAccountControl)
			user.profile.userAccountControl = userAccountControl_decoded

			if "ACCOUNTDISABLE" in userAccountControl_decoded:
				if user.profile.accountdisable == False:
					report_data["deaktivert"] += 1
					message = ("Endret status for %s (%s)" % (user, user.username))
					UserChangeLog.objects.create(event_type='ACCOUNT DISABLE', message=message)
				else:
					report_data["modified"] += 1

				user.profile.accountdisable = True
			else:
				if user.profile.accountdisable == True:
					report_data["reaktivert"] += 1
					message = ("Endret status for %s (%s)" % (user, user.username))
					UserChangeLog.objects.create(event_type='ACCOUNT ENABLE', message=message)
				else:
					report_data["modified"] += 1

				user.profile.accountdisable = False

			if "LOCKOUT" in userAccountControl_decoded:
				user.profile.lockout = True
			else:
				user.profile.lockout = False
			if "PASSWD_NOTREQD" in userAccountControl_decoded:
				user.profile.passwd_notreqd = True
			else:
				user.profile.passwd_notreqd = False

			try:
				old_dont_expire_password = user.profile.dont_expire_password  # den finnes fra før av
			except:
				old_dont_expire_password = None
			if "DONT_EXPIRE_PASSWORD" in userAccountControl_decoded:
				user.profile.dont_expire_password = True
			else:
				user.profile.dont_expire_password = False
			if old_dont_expire_password != None:
				if old_dont_expire_password != user.profile.dont_expire_password:
					message = ("Status endret for %s (%s). Ny verdi: %s" % (user, user.username, user.profile.dont_expire_password))
					UserChangeLog.objects.create(event_type='DONT_EXPIRE_PASSWORD', message=message)

			if "PASSWORD_EXPIRED" in userAccountControl_decoded:
				user.profile.password_expired = True
			else:
				user.profile.password_expired = False
			if "OU=Eksterne brukere" in dn:
				user.profile.ekstern_ressurs = True
			if "OU=Brukere" in dn:
				user.profile.ekstern_ressurs = False

			UserPasswordExpiry = attrs["msDS-UserPasswordExpiryTimeComputed"]
			if len(UserPasswordExpiry) > 0:
				try:
					user.profile.userPasswordExpiry = microsoft_date_decode(UserPasswordExpiry[0])
				except:
					pass

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

			try:
				time_str = attrs["whenCreated"][0].decode().split('.')[0]
				whenCreated = datetime.datetime.strptime(time_str, "%Y%m%d%H%M%S").replace(tzinfo=datetime.timezone.utc)
			except KeyError:
				whenCreated = None
			user.profile.whenCreated = whenCreated

			try:
				description = attrs["description"][0].decode()
			except KeyError:
				description = ""
			user.profile.description = description

			try:
				lastLogonTimestamp = microsoft_date_decode(attrs["lastLogonTimestamp"][0].decode())
			except KeyError:
				lastLogonTimestamp = None
			user.profile.lastLogonTimestamp = lastLogonTimestamp

			user.profile.distinguishedname = dn

			parent_ou_str = ",".join(dn.split(',')[1:])
			try:
				parent_ou = ADOrgUnit.objects.get(distinguishedname=parent_ou_str)
			except:
				parent_ou = None

			user.profile.ou = parent_ou

			try:
				displayName = attrs["displayName"][0].decode()
			except KeyError:
				displayName = ""
			user.profile.displayName = displayName

			user.is_active = True

			if user.profile.ansattnr_ref == None:
				try:
					ansattnr_match = re.search(r'(\d{4,})', user.username, re.I)
					if ansattnr_match:
						ansattnr = int(ansattnr_match[0])
						try:
							aid = AnsattID.objects.get(ansattnr=ansattnr)
						except:
							aid = AnsattID.objects.create(ansattnr=ansattnr)

						user.profile.ansattnr_ref = aid
				except:
					print("Kobling mot AnsattID feilet for %s" % user)

			user.save()
			return


		@transaction.atomic  # for speeding up database performance
		def result_handler(rdata, report_data, existing_objects=None):

			#deaktivert da vi ikke lenger begrenser import til eksisterende virksomheter.
			#gyldige_virksomheter = list(Virksomhet.objects.values_list(Upper('virksomhetsforkortelse'), flat=True).distinct())

			for dn, attrs in rdata:
				sys.stdout.flush()

				if "cn" in attrs:
					username = attrs["sAMAccountName"][0].decode().lower()
				else:
					print("?", end="")
					continue  # vi må ha et brukernavn

				#if not ("OU=Eksterne brukere" in dn or "OU=Brukere" in dn):
				#	continue  # ikke en person

				user_organization = dn.split(",")[1][3:]  # andre OU, fjerner "OU=" som er tegn 0-2.
				#if user_organization not in gyldige_virksomheter:
				#	print("?", end="")
				#	continue

				# et gyldig brukernavn på en bruker er trebokstav (eller DRIFT) + 4-6 siffer
				#if not re.match(r"^[a-z]{3}[0-9]{4,6}$", username) and not re.match(r"^drift[0-9]{4,6}$", username):  # username er kun lowercase
				#	print("b", end="")
				#	continue # ugyldig brukernavn

				try:
					user = User.objects.get(username=username)
					if username in existing_objects: # holde track på brukere som ikke lenger finnes
						existing_objects.remove(username)
					print("u", end="")
				except:
					user = User.objects.create_user(username=username)
					report_data["created"] += 1
					print("n", end="")

				update_user_status(user, dn, attrs, user_organization, report_data)

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
						result["report_data"]["removed"] += 1
					else:
						print("-", end="")
				except ObjectDoesNotExist:
					pass
				sys.stdout.flush()
			print("")

		cleanup(existing_objects, result)

		@transaction.atomic
		def slett_ikkeaktive_brukere():
			for user in User.objects.filter(is_active=False):
				try:
					user.delete()
					print("Bruker %s slettet" % user.username)
				except:
					#print("kan ikke slette bruker %s (%s)" % (user.username, sys.exc_info()[0]))
					result["report_data"]["user_not_deleted"].append(user.username)
		slett_ikkeaktive_brukere()

		def report(result):
			#print("\nVirksomheter det ikke var brukere for i AD: ", gyldige_virksomheter)
			#print("\nVirksomheter som ikke er i kartoteket: ", ad_grupper_utenfor_kartoteket)
			log_entry_message = "Det tok %s sekunder. %s treff. %s nye, %s oppdatert, %s deaktivert, %s reaktivert og %s slettet. Følgende brukere kunne ikke slettes: %s" % (
					result["total_runtime"],
					result["objects_returned"],
					result["report_data"]["created"],
					result["report_data"]["modified"],
					result["report_data"]["deaktivert"],
					result["report_data"]["reaktivert"],
					result["report_data"]["removed"],
					result["report_data"]["user_not_deleted"],
			)
			log_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=log_entry_message,
			)
			print(log_entry_message)

		report(result)
