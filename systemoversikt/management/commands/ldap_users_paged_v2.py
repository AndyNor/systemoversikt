# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.contrib.auth.models import User
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
	BASEDN = 'DC=oslofelles,DC=oslo,DC=kommune,DC=no'
	SEARCHFILTER = '(&(objectCategory=person)(objectClass=user))'
	LDAP_SCOPE = ldap.SCOPE_SUBTREE
	ATTRLIST = ['objectSid', 'cn', 'title', 'givenName', 'sn', 'userAccountControl', 'mail', 'msDS-UserPasswordExpiryTimeComputed', 'description', 'displayName', 'sAMAccountName', 'lastLogonTimestamp', 'whenCreated', 'pwdLastSet', 'servicePrincipalName']
	PAGESIZE = 2000


	def handle(self, **options):
		INTEGRASJON_KODEORD = "ad_users"
		LOG_EVENT_TYPE = "AD user-import"
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
		int_config.helsestatus = "Forbereder"
		int_config.save()

		try:
			timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
			print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
			runtime_t0 = time.time()
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

			def print_with_timestamp(message):
				current_time = datetime.datetime.now()
				print(f"{current_time.hour}:{current_time.minute} {message}")

			def microsoft_date_decode(raw_value):
				if isinstance(raw_value, bytes):
					value_str = raw_value.decode()
				else:
					value_str = raw_value

				if value_str in ('9223372036854775807', '0'):
					return None

				ms_timestamp = int(value_str[:-1])
				ms_epoch_start = datetime.datetime(1601, 1, 1)
				timedelta = datetime.timedelta(microseconds=ms_timestamp)
				try:
					return make_aware(ms_epoch_start + timedelta)
				except (pytz.NonExistentTimeError, pytz.AmbiguousTimeError):
					return make_aware(ms_epoch_start + timedelta + datetime.timedelta(hours=1))


			# Prefetch lookup tables
			print_with_timestamp("Bygger oppslagstabeller...")
			user_lookup = {u.username: u for u in User.objects.select_related('profile').all()}
			virksomhet_lookup = {v.virksomhetsforkortelse: v for v in Virksomhet.objects.all()}
			ou_lookup = {ou.distinguishedname: ou for ou in ADOrgUnit.objects.all()}
			ansattid_lookup = {a.ansattnr: a for a in AnsattID.objects.all()}
			print_with_timestamp(f"Ferdig. {len(user_lookup)} brukere, {len(virksomhet_lookup)} virksomheter, {len(ou_lookup)} OUer, {len(ansattid_lookup)} ansatt-IDer")

			existing_user_objects = set(user_lookup.keys())
			is_test_env = os.environ.get('THIS_ENV') == "TEST"


			def ldap_paged_search():
				LDAPUSER = os.environ["KARTOTEKET_LDAPUSER"]
				LDAPPASSWORD = os.environ["KARTOTEKET_LDAPPASSWORD"]
				LDAPSERVER = os.environ["KARTOTEKET_LDAPSERVER"]
				ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
				ldap.set_option(ldap.OPT_REFERRALS, 0)
				LDAP24API = LooseVersion(ldap.__version__) >= LooseVersion('2.4')

				def create_controls(pagesize):
					if LDAP24API:
						return SimplePagedResultsControl(True, size=pagesize, cookie='')
					else:
						return SimplePagedResultsControl(ldap.LDAP_CONTROL_PAGE_OID, True, (pagesize, ''))

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
						lc_object.controlValue = (pagesize, cookie)
						return cookie

				l = ldap.initialize(LDAPSERVER)
				l.protocol_version = 3
				try:
					l.simple_bind_s(LDAPUSER, LDAPPASSWORD)
				except ldap.LDAPError as e:
					raise Exception(f'ERROR: LDAP bind failed: {e}')
				lc = create_controls(Command.PAGESIZE)

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
					print_with_timestamp(f"Fetching page {current_round}: element {objects_start}-{objects_returned}")

					result_handler(rdata)
					time.sleep(1)

					pctrls = get_pctrls(serverctrls)
					if not pctrls:
						print('WARNING: Server ignores RFC 2696 control.')
						break

					cookie = set_cookie(lc, pctrls, Command.PAGESIZE)
					if not cookie:
						break

				l.unbind()
				Command.SUMMARY['number_of_items'] = objects_returned
				return


			def result_handler(rdata):
				users_to_update = []
				ansattid_to_create = []
				profiles_to_update = []
				now = timezone.now()

				for dn, attrs in rdata:
					if "cn" not in attrs:
						print(f"Fant ikke brukernavn for {dn}")
						continue

					username = attrs["sAMAccountName"][0].decode().lower()
					user_organization = dn.split(",")[1][3:]

					if username in user_lookup:
						user = user_lookup[username]
						existing_user_objects.discard(username)
					else:
						user = User.objects.create(username=username)
						user_lookup[username] = user
						Command.SUMMARY["created"] += 1

					if "servicePrincipalName" in attrs:
						user.profile.service_principal_name = json.dumps([spn.decode() for spn in attrs["servicePrincipalName"]])
					else:
						user.profile.service_principal_name = None

					if "userAccountControl" not in attrs:
						print(f"{user} mangler userAccountControl i attrs")
						continue

					userAccountControl = int(attrs["userAccountControl"][0].decode())
					userAccountControl_decoded = decode_useraccountcontrol(userAccountControl)
					user.profile.userAccountControl = userAccountControl_decoded

					# Detect transitions before overwriting
					was_disabled = user.profile.accountdisable

					if "ACCOUNTDISABLE" in userAccountControl_decoded:
						user.profile.accountdisable = True
						if not was_disabled:
							Command.SUMMARY["deaktivert"] += 1
							message = f"Endret status for {user} ({user.username})"
							UserChangeLog.objects.create(event_type='ACCOUNT DISABLE', message=message)
						else:
							Command.SUMMARY["modified"] += 1
					else:
						user.profile.accountdisable = False
						if was_disabled:
							Command.SUMMARY["reaktivert"] += 1
							message = f"Endret status for {user} ({user.username})"
							UserChangeLog.objects.create(event_type='ACCOUNT ENABLE', message=message)
						else:
							Command.SUMMARY["modified"] += 1

					user.profile.lockout = "LOCKOUT" in userAccountControl_decoded
					user.profile.passwd_notreqd = "PASSWD_NOTREQD" in userAccountControl_decoded
					user.profile.trusted_for_delegation = "TRUSTED_FOR_DELEGATION" in userAccountControl_decoded
					user.profile.trusted_to_auth_for_delegation = "TRUSTED_TO_AUTH_FOR_DELEGATION" in userAccountControl_decoded
					user.profile.not_delegated = "NOT_DELEGATED" in userAccountControl_decoded
					user.profile.dont_req_preauth = "DONT_REQ_PREAUTH" in userAccountControl_decoded
					user.profile.dont_expire_password = "DONT_EXPIRE_PASSWORD" in userAccountControl_decoded
					user.profile.password_expired = "PASSWORD_EXPIRED" in userAccountControl_decoded

					if "OU=Eksterne brukere" in dn:
						user.profile.ekstern_ressurs = True
						user.profile.account_type = "Ekstern"
					elif "OU=Brukere" in dn:
						user.profile.ekstern_ressurs = False
						user.profile.account_type = "Intern"
					elif "OU=Ressurser,OU=OK" in dn:
						user.profile.account_type = "Ressurs"
					elif "OU=Servicekontoer,OU=OK" in dn:
						user.profile.account_type = "Servicekonto"
					elif "OU=Kontakt,OU=OK" in dn:
						user.profile.account_type = "Kontakt"

					if "msDS-UserPasswordExpiryTimeComputed" in attrs:
						UserPasswordExpiry = attrs["msDS-UserPasswordExpiryTimeComputed"]
						if len(UserPasswordExpiry) > 0:
							try:
								user.profile.userPasswordExpiry = microsoft_date_decode(UserPasswordExpiry[0])
							except:
								pass

					virksomhet_tbf = user_organization.upper()
					if virksomhet_tbf in virksomhet_lookup:
						user.profile.virksomhet = virksomhet_lookup[virksomhet_tbf]

					first_name = attrs["givenName"][0].decode() if "givenName" in attrs else ""
					if is_test_env:
						first_name = hashlib.sha256(first_name.encode('utf-8')).hexdigest()[0:24]
					user.first_name = first_name

					last_name = attrs["sn"][0].decode() if "sn" in attrs else ""
					if is_test_env:
						last_name = hashlib.sha256(last_name.encode('utf-8')).hexdigest()[0:24]
					user.last_name = last_name

					user.profile.job_title = attrs["title"][0].decode() if "title" in attrs else ""

					try:
						objectsid = attrs["objectSid"]
						if len(objectsid) > 0:
							user.profile.object_sid = decode_sid(objectsid[0])
					except:
						pass

					email = ""
					if "mail" in attrs:
						email = attrs["mail"][0].decode()
						if is_test_env:
							email_parts = email.split("@")
							email_identifier = hashlib.sha256(email_parts[0].encode('utf-8')).hexdigest()[0:24]
							email = f"{email_identifier}@{email_parts[1]}"
					user.email = email

					try:
						time_str = attrs["whenCreated"][0].decode().split('.')[0]
						user.profile.whenCreated = datetime.datetime.strptime(time_str, "%Y%m%d%H%M%S").replace(tzinfo=datetime.timezone.utc)
					except (KeyError, ValueError):
						user.profile.whenCreated = None

					try:
						user.profile.pwdLastSet = microsoft_date_decode(attrs["pwdLastSet"][0])
					except (KeyError, ValueError):
						user.profile.pwdLastSet = None

					try:
						description = attrs["description"][0].decode()
					except KeyError:
						description = ""
					if is_test_env:
						description = hashlib.sha256(description.encode('utf-8')).hexdigest()[0:24]
					user.profile.description = description

					try:
						user.profile.lastLogonTimestamp = microsoft_date_decode(attrs["lastLogonTimestamp"][0])
					except KeyError:
						user.profile.lastLogonTimestamp = None

					user.profile.distinguishedname = dn

					parent_ou_str = ",".join(dn.split(',')[1:])
					user.profile.ou = ou_lookup.get(parent_ou_str)

					displayName = attrs["displayName"][0].decode() if "displayName" in attrs else ""
					if is_test_env:
						displayName = hashlib.sha256(displayName.encode('utf-8')).hexdigest()[0:24]
					user.profile.displayName = displayName

					user.is_active = True

					if user.profile.ansattnr_ref is None:
						try:
							ansattnr_match = re.search(r'(\d{4,})', user.username, re.I)
							if ansattnr_match:
								ansattnr = int(ansattnr_match[0])
								if ansattnr in ansattid_lookup:
									user.profile.ansattnr_ref = ansattid_lookup[ansattnr]
								else:
									aid = AnsattID(ansattnr=ansattnr)
									ansattid_to_create.append(aid)
									ansattid_lookup[ansattnr] = aid
									user.profile.ansattnr_ref = aid
						except:
							print(f"Kobling mot AnsattID feilet for {user}")

					user.profile.ad_sist_oppdatert = now
					users_to_update.append(user)
					profiles_to_update.append(user.profile)

				print_with_timestamp(f"Skriver oppdateringer til {len(users_to_update)} brukerobjekter")

				@transaction.atomic
				def save_to_db():
					AnsattID.objects.bulk_create(ansattid_to_create)
					User.objects.bulk_update(users_to_update, ["first_name", "last_name", "email", "is_active"])
					Profile.objects.bulk_update(profiles_to_update, ["service_principal_name", "userAccountControl", "accountdisable", "lockout", "passwd_notreqd", "trusted_for_delegation", "trusted_to_auth_for_delegation", "not_delegated", "dont_req_preauth", "dont_expire_password", "password_expired", "ekstern_ressurs", "account_type", "userPasswordExpiry", "virksomhet", "job_title", "object_sid", "whenCreated", "pwdLastSet", "description", "lastLogonTimestamp", "distinguishedname", "ou", "displayName", "ansattnr_ref", "ad_sist_oppdatert",])

				save_to_db()


			@transaction.atomic
			def cleanup():
				if not existing_user_objects:
					return
				users_to_deactivate = User.objects.filter(
					username__in=existing_user_objects
				).exclude(
					is_superuser=True
				).filter(
					is_active=True
				)
				count = users_to_deactivate.update(is_active=False)
				Command.SUMMARY["removed"] = count

			@transaction.atomic
			def slett_ikkeaktive_brukere():
				for user in User.objects.filter(is_active=False):
					try:
						user.delete()
					except:
						Command.SUMMARY["inactive_user_not_deleted"].append(user.username)
						user.profile.accountdisable = True
						user.save()


			print_with_timestamp(f"Det er {len(existing_user_objects)} eksisterende brukere")
			print_with_timestamp("Starter oppslag mot Active Directory...")
			ldap_paged_search()

			print_with_timestamp(f"Deaktiverer {len(existing_user_objects)} brukere som ikke ble oppdatert...")
			cleanup()

			print_with_timestamp("Prøver å slette deaktiverte brukere...")
			slett_ikkeaktive_brukere()
			print_with_timestamp(f"Det var {len(Command.SUMMARY['inactive_user_not_deleted'])} brukere som ikke kunne slettes.")


			log_statistics = f"{Command.SUMMARY['number_of_items']} treff. {Command.SUMMARY['created']} nye, {Command.SUMMARY['modified']} oppdatert, {Command.SUMMARY['deaktivert']} deaktivert, {Command.SUMMARY['reaktivert']} reaktivert og {Command.SUMMARY['removed']} slettet. {len(Command.SUMMARY['inactive_user_not_deleted'])} kunne ikke slettes (låst)."
			int_config.sist_status = log_statistics

			log_entry_message = f"{log_statistics} Følgende brukere kunne ikke slettes: {Command.SUMMARY['inactive_user_not_deleted']}"
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=log_entry_message)
			print(log_entry_message)

			int_config.dato_sist_oppdatert = timezone.now()
			int_config.elementer = int(Command.SUMMARY['number_of_items'])

			runtime_t1 = time.time()
			int_config.runtime = int(runtime_t1 - runtime_t0)
			int_config.helsestatus = "Vellykket"
			int_config.save()


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message=logg_message)
			print(logg_message)
			import traceback
			int_config.helsestatus = f"Feilet\n{traceback.format_exc()}"
			int_config.save()
			push_pushover(f"{SCRIPT_NAVN} feilet")
