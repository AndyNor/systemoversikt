# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.contrib.auth.models import User
from django.db.models.functions import Upper
from systemoversikt.models import *
from django.utils import timezone
import datetime, pytz
from systemoversikt.views import push_pushover
import json, re, hashlib, os, ldap, sys, time
from systemoversikt.views import decode_sid
from django.utils.timezone import make_aware
from systemoversikt.views import decode_useraccountcontrol
from ldap.controls import SimplePagedResultsControl
from distutils.version import LooseVersion

class Command(BaseCommand):
	SUMMARY = {
		"number_of_items": 0,
		"created": 0,
		"modified": 0,
		"deaktivert": 0,
		"reaktivert": 0,
		"removed": 0,
		"inactive_user_not_deleted": [],
	}
	BASEDN ='DC=oslofelles,DC=oslo,DC=kommune,DC=no'
	SEARCHFILTER = '(&(objectCategory=person)(objectClass=user))'
	LDAP_SCOPE = ldap.SCOPE_SUBTREE
	ATTRLIST = ['objectSid', 'cn', 'givenName', 'sn', 'userAccountControl', 'mail', 'msDS-UserPasswordExpiryTimeComputed', 'description', 'displayName', 'sAMAccountName', 'lastLogonTimestamp', 'whenCreated', 'pwdLastSet', 'servicePrincipalName'] # if empty we get all attr we have access to
	PAGESIZE = 200

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

		try:
			timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
			print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
			runtime_t0 = time.time()
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")


			def microsoft_date_decode(timestamp):
				if timestamp == b'9223372036854775807' or timestamp == b'0':
					return None

				ms_timestamp = int(timestamp[:-1])  # removing one trailing digit: steps of 100ns to steps pf 1 micro second.
				ms_epoch_start = datetime.datetime(1601,1,1)
				timedelta = datetime.timedelta(microseconds=ms_timestamp)
				try:
					return make_aware(ms_epoch_start + timedelta)
				except (pytz.NonExistentTimeError, pytz.AmbiguousTimeError):
					return make_aware(ms_epoch_start + timedelta + datetime.timedelta(hours=1))  # her velger vi bare å dytte tiden frem.


			def ldap_paged_search(existing_user_objects):
				LDAPUSER = os.environ["KARTOTEKET_LDAPUSER"]
				LDAPPASSWORD = os.environ["KARTOTEKET_LDAPPASSWORD"]
				LDAPSERVER = os.environ["KARTOTEKET_LDAPSERVER"]
				ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # self signed
				ldap.set_option(ldap.OPT_REFERRALS, 0)
				LDAP24API = LooseVersion(ldap.__version__) >= LooseVersion('2.4')

				def create_controls(pagesize):
					if LDAP24API:
						return SimplePagedResultsControl(True, size=pagesize, cookie='')
					else:
						return SimplePagedResultsControl(ldap.LDAP_CONTROL_PAGE_OID, True, (pagesize,''))

				def get_pctrls(serverctrls):
					if LDAP24API:
						return [c for c in serverctrls
								if c.controlType == SimplePagedResultsControl.controlType]
					else:
						return [c for c in serverctrls
								if c.controlType == ldap.LDAP_CONTROL_PAGE_OID]

				def set_cookie(lc_object, pctrls, pagesize):
					if LDAP24API:
						cookie = pctrls[0].cookie
						lc_object.cookie = cookie
						return cookie
					else:
						est, cookie = pctrls[0].controlValue
						lc_object.controlValue = (pagesize,cookie)
						return cookie

				l = ldap.initialize(LDAPSERVER)
				l.protocol_version = 3  # Paged results require versjon 3
				try:
					l.simple_bind_s(LDAPUSER, LDAPPASSWORD)
				except ldap.LDAPError as e:
					raise Exception(f'ERROR: LDAP bind failed: {e}')
				lc = create_controls(Command.PAGESIZE)


				# Search and loop until no more pages
				current_round = 0
				objects_returned = 0
				while True:
					current_round += 1
					try:
						msgid = l.search_ext(Command.BASEDN, Command.LDAP_SCOPE, Command.SEARCHFILTER, Command.ATTRLIST, serverctrls=[lc])
					except ldap.LDAPError as e:
						raise Exception(f'ERROR: LDAP search failed: {e}')

					try:
						rtype, rdata, rmsgid, serverctrls = l.result3(msgid)
					except ldap.LDAPError as e:
						raise Exception(f'ERROR: Could not pull LDAP results: {e}')

					objects_start = objects_returned + 1
					objects_returned += len(rdata)
					print(f"Fetching page {current_round}: element {objects_start}-{objects_returned}")

					# Do stuff with results
					result_handler(rdata, existing_user_objects)
					time.sleep(10)

					pctrls = get_pctrls(serverctrls)
					if not pctrls:
						print('WARNING: Server ignores RFC 2696 control.')
						break

					cookie = set_cookie(lc, pctrls, PAGESIZE)
					if not cookie:
						break  # Done

				l.unbind()
				Command.SUMMARY['number_of_items'] = objects_returned
				return


			def result_handler(rdata, existing_user_objects):
				for dn, attrs in rdata:
					if "cn" in attrs:
						username = attrs["sAMAccountName"][0].decode().lower()
					else:
						print(f"Fant ikke brukernavn for {dn}")
						continue  # vi må ha et brukernavn

					user_organization = dn.split(",")[1][3:]  # andre OU, fjerner "OU=" som er tegn 0-2.
					try:
						user = User.objects.get(username=username)
						print(f"Fant eksisterende bruker {user}")
						if username in existing_user_objects: # holde track på brukere som ikke lenger finnes
							existing_user_objects.remove(username)
					except:
						user = User.objects.create_user(username=username)
						print(f"Opprettet bruker {user}")
						Command.SUMMARY["created"] += 1


					if "servicePrincipalName" in attrs:
						all_spn = []
						for spn in attrs["servicePrincipalName"]:
							all_spn.append(spn.decode())
						user.profile.service_principal_name = json.dumps(all_spn)
					else:
						user.profile.service_principal_name = None


					if "userAccountControl" in attrs:
						userAccountControl = int(attrs["userAccountControl"][0].decode())
					else:
						print(f"{user} mangler userAccountControl i attrs")
						return

					userAccountControl_decoded = decode_useraccountcontrol(userAccountControl)
					user.profile.userAccountControl = userAccountControl_decoded

					if "ACCOUNTDISABLE" in userAccountControl_decoded:
						user.profile.accountdisable = True

						if user.profile.accountdisable == False:
							Command.SUMMARY["deaktivert"] += 1
							message = ("Endret status for %s (%s)" % (user, user.username))
							UserChangeLog.objects.create(event_type='ACCOUNT DISABLE', message=message)
						else:
							Command.SUMMARY["modified"] += 1

					else:
						user.profile.accountdisable = False

						if user.profile.accountdisable == True:
							Command.SUMMARY["reaktivert"] += 1
							message = ("Endret status for %s (%s)" % (user, user.username))
							UserChangeLog.objects.create(event_type='ACCOUNT ENABLE', message=message)
						else:
							Command.SUMMARY["modified"] += 1


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

					if "TRUSTED_TO_AUTH_FOR_DELEGATION" in userAccountControl_decoded:
						user.profile.trusted_to_auth_for_delegation = True
					else:
						user.profile.trusted_to_auth_for_delegation = False

					if "NOT_DELEGATED" in userAccountControl_decoded:
						user.profile.not_delegated = True
					else:
						user.profile.not_delegated = False

					if "DONT_REQ_PREAUTH" in userAccountControl_decoded:
						user.profile.dont_req_preauth = True
					else:
						user.profile.dont_req_preauth = False

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

					user.profile.ad_sist_oppdatert = timezone.now()
					user.save()
					return


			@transaction.atomic
			def cleanup(existing_user_objects):
				for b in existing_user_objects:
					try:
						u = User.objects.get(username=b)
						if u.is_superuser:
							continue # don't mess with super users
						if u.is_active:
							u.is_active = False
							u.save()
							Command.SUMMARY["removed"] += 1
						else:
							pass
					except ObjectDoesNotExist:
						pass

			@transaction.atomic
			def slett_ikkeaktive_brukere():
				for user in User.objects.filter(is_active=False):
					try:
						user.delete()
					except:
						Command.SUMMARY["inactive_user_not_deleted"].append(user.username)
						user.profile.accountdisable = True
						user.save()


			print("Lager liste over brukerobjekter som eksisterte før import starter...")
			existing_user_objects = list(User.objects.values_list("username", flat=True))
			print(f"Det er {len(existing_user_objects)} eksisterende brukere")

			print(f"Slår opp brukere direkte i AD...")
			ldap_paged_search(existing_user_objects)


			print(f"Deaktiverer {len(existing_user_objects)} brukere som ikke ble oppdatert...")
			cleanup(existing_user_objects)

			print("Prøver å slette deaktiverte brukere...")
			slett_ikkeaktive_brukere()
			print(f"Det var {len(Command.SUMMARY['inactive_user_not_deleted'])} brukere som ikke kunne slettes.")


			log_statistics = f"{Command.SUMMARY['number_of_items']} treff. {Command.SUMMARY['created']} nye, {Command.SUMMARY['modified']} oppdatert, {Command.SUMMARY['deaktivert']} deaktivert, {Command.SUMMARY['reaktivert']} reaktivert og {Command.SUMMARY['removed']} slettet. {len(Command.SUMMARY['inactive_user_not_deleted'])} kunne ikke slettes (låst)."
			int_config.sist_status = log_statistics

			log_entry_message = f"{log_statistics} Følgende brukere kunne ikke slettes: {Command.SUMMARY['inactive_user_not_deleted']}"
			log_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=log_entry_message)
			print(log_entry_message)

			int_config.dato_sist_oppdatert = timezone.now()
			int_config.elementer = int(CCommand.SUMMARY['number_of_items'])

			runtime_t1 = time.time()
			int_config.runtime = int(runtime_t1 - runtime_t0)
			int_config.save()


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			push_pushover(f"{SCRIPT_NAVN} feilet") # Push error