# -*- coding: utf-8 -*-
#Hensikten med denne koden er å laste inn alle ordinære brukere koblet til en av kommunens vikrsomheter, slik at man i kartoteket kan tildele ansvar til en faktisk brukeridentitet. Her laster vi ikke inn manuelt opprettede brukere som ikke kommer fra PRK.
#Denne importen vil ikke kunne svare på forskjeller mellom AD og PRK. Det er andre jobber som identifiserer slike avvik.

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.utils import ldap_paged_search, decode_useraccountcontrol, ldap_OK_virksomheter, microsoft_date_decode
from django.contrib.auth.models import User
from django.db.models.functions import Upper
from systemoversikt.models import *
from django.utils import timezone
import datetime
from systemoversikt.views import push_pushover
import json
import re
import hashlib
import os
import ldap
import sys

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "ad_users"
		LOG_EVENT_TYPE = "AD user-import" # hentes automatisk
		KILDE = "Active Directory OSLOFELLES"
		PROTOKOLL = "LDAP"
		BESKRIVELSE = "Brukere"
		FILNAVN = ""
		URL = ""
		FREKVENS = "Hver natt"

		try:
			int_config = IntegrasjonKonfigurasjon.objects.get(kodeord=INTEGRASJON_KODEORD)
		except:
			int_config = IntegrasjonKonfigurasjon.objects.create(
					kodeord=INTEGRASJON_KODEORD,
					kilde=KILDE,
					protokoll=PROTOKOLL,
					informasjon=BESKRIVELSE,
					sp_filnavn=FILNAVN,
					url=URL,
					frekvensangivelse=FREKVENS,
					log_event_type=LOG_EVENT_TYPE,
				)

		SCRIPT_NAVN = os.path.basename(__file__)
		int_config.script_navn = SCRIPT_NAVN
		int_config.sp_filnavn = json.dumps(FILNAVN)
		int_config.save()

		timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")

		try:

			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

			# Configuration
			BASEDN ='DC=oslofelles,DC=oslo,DC=kommune,DC=no'
			SEARCHFILTER = '(&(objectCategory=person)(objectClass=user))'
			LDAP_SCOPE = ldap.SCOPE_SUBTREE
			ATTRLIST = ['objectSid', 'cn', 'givenName', 'sn', 'userAccountControl', 'mail', 'msDS-UserPasswordExpiryTimeComputed', 'description', 'displayName', 'sAMAccountName', 'lastLogonTimestamp', 'whenCreated', 'pwdLastSet', 'servicePrincipalName'] # if empty we get all attr we have access to
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

				if "servicePrincipalName" in attrs:
					#print(attrs["servicePrincipalName"])
					all_spn = []
					for spn in attrs["servicePrincipalName"]:
						all_spn.append(spn.decode())
					user.profile.service_principal_name = json.dumps(all_spn)
				else:
					user.profile.service_principal_name = None


				if "userAccountControl" in attrs:
					userAccountControl = int(attrs["userAccountControl"][0].decode())
				else:
					#print("-uac-", end="")
					print(f"{user} mangler userAccountControl i attrs")
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

				if "TRUSTED_FOR_DELEGATION" in userAccountControl_decoded:
					user.profile.trusted_for_delegation = True
				else:
					user.profile.trusted_for_delegation = False

				if "NOT_DELEGATED" in userAccountControl_decoded:
					user.profile.not_delegated = True
				else:
					user.profile.not_delegated = False

				if "DONT_REQ_PREAUTH" in userAccountControl_decoded:
					user.profile.dont_req_preauth = True
				else:
					user.profile.dont_req_preauth = False

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


				# map out type of user based on OU path
				if "OU=Eksterne brukere" in dn:
					user.profile.ekstern_ressurs = True
					user.profile.account_type = "Ekstern"
				if "OU=Brukere" in dn:
					user.profile.ekstern_ressurs = False
					user.profile.account_type = "Intern"
				if "OU=Ressurser,OU=OK" in dn:
					user.profile.account_type = "Ressurs"
				if "OU=Servicekontoer,OU=OK" in dn:
					user.profile.account_type = "Servicekonto"
				if "OU=Kontakt,OU=OK" in dn:
					user.profile.account_type = "Kontakt"

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
				if os.environ['THIS_ENV'] == "TEST":
					# fjerne navn i testmiljøet
					first_name = hashlib.sha256(first_name.encode('utf-8')).hexdigest()[0:24]
				user.first_name = first_name

				last_name = ""
				if "sn" in attrs:
					last_name = attrs["sn"][0].decode()
				if os.environ['THIS_ENV'] == "TEST":
					# fjerne navn i testmiljøet
					last_name = hashlib.sha256(last_name.encode('utf-8')).hexdigest()[0:24]
				user.last_name = last_name

				try:
					objectsid = attrs["objectSid"]
					if len(objectsid) == 0:
						print(f"ObjectSid contains no elements for {user}")
					else:
						user.profile.object_sid = decode_sid(objectsid[0])
						if len(objectsid) > 1:
							print(f"ObjectSid contains more than one element for {user}")
				except:
					print(f"ObjectSid failed for {user}")


				email = ""
				if "mail" in attrs:
					email = attrs["mail"][0].decode()
					if os.environ['THIS_ENV'] == "TEST": # innrykk: kan bare splitte hvis vi vet det er en e-postadresse
						# fjerne navn i testmiljøet
						email_parts = email.split("@")
						email_identifier = hashlib.sha256(email_parts[0].encode('utf-8')).hexdigest()[0:24]
						email_domain = email_parts[1]
						email = f"{email_identifier}@{email_domain}"
				user.email = email

				try:
					time_str = attrs["whenCreated"][0].decode().split('.')[0]
					whenCreated = datetime.datetime.strptime(time_str, "%Y%m%d%H%M%S").replace(tzinfo=datetime.timezone.utc)
				except (KeyError, ValueError):
					whenCreated = None
				user.profile.whenCreated = whenCreated

				try:
					pwdLastSet = microsoft_date_decode(attrs["pwdLastSet"][0].decode())
				except (KeyError, ValueError):
					pwdLastSet = None
				user.profile.pwdLastSet = pwdLastSet

				try:
					description = attrs["description"][0].decode()
				except KeyError:
					description = ""
				if os.environ['THIS_ENV'] == "TEST":
					# fjerne beskrivelse i testmiljøet
					description = hashlib.sha256(description.encode('utf-8')).hexdigest()[0:24]
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
				if os.environ['THIS_ENV'] == "TEST":
					# fjerne navn i testmiljøet
					displayName = hashlib.sha256(displayName.encode('utf-8')).hexdigest()[0:24]
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
						#print("?", end="")
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
						#print("u", end="")
					except:
						user = User.objects.create_user(username=username)
						report_data["created"] += 1
						#print("n", end="")

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
							#print("r", end="")
							result["report_data"]["removed"] += 1
						else:
							#print("-", end="")
							pass
					except ObjectDoesNotExist:
						pass
					#sys.stdout.flush()
				#print("")

			cleanup(existing_objects, result)

			@transaction.atomic
			def slett_ikkeaktive_brukere():
				for user in User.objects.filter(is_active=False):
					try:
						user.delete()
						#print("Bruker %s slettet" % user.username)
					except:
						#print("kan ikke slette bruker %s (%s)" % (user.username, sys.exc_info()[0]))
						result["report_data"]["user_not_deleted"].append(user.username)
						user.profile.accountdisable = True
						user.save()
			slett_ikkeaktive_brukere()

			def report(result):
				#print("\nVirksomheter det ikke var brukere for i AD: ", gyldige_virksomheter)
				#print("\nVirksomheter som ikke er i kartoteket: ", ad_grupper_utenfor_kartoteket)

				total_runtime = result["total_runtime"],
				objects_returned = result["objects_returned"],
				created = result["report_data"]["created"],
				modified = result["report_data"]["modified"],
				deaktivert = result["report_data"]["deaktivert"],
				reaktivert = result["report_data"]["reaktivert"],
				removed = result["report_data"]["removed"],
				user_not_deleted = result["report_data"]["user_not_deleted"],

				log_statistics = f"Det tok {total_runtime} sekunder. {objects_returned} treff. {created} nye, {modified} oppdatert, {deaktivert} deaktivert, {reaktivert} reaktivert og {removed} slettet. {len(user_not_deleted)} kunne ikke slettes (låst)."
				log_entry_message = f"{log_statistics} Følgende brukere kunne ikke slettes: {user_not_deleted}"
				log_entry = ApplicationLog.objects.create(
						event_type=LOG_EVENT_TYPE,
						message=log_entry_message,
				)
				print(log_entry_message)
				return log_statistics

			log_entry_message = report(result)
			# lagre sist oppdatert tidspunkt
			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = log_entry_message
			int_config.save()


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# Push error
			push_pushover(f"{SCRIPT_NAVN} feilet")