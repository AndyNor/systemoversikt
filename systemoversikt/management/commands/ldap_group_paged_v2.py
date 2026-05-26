# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import timedelta, datetime
from django.utils import timezone
from systemoversikt.models import *
from systemoversikt.views import push_pushover
from systemoversikt.models import ApplicationLog, ADgroup
import ldap, os, sys, time, json
from ldap.controls import SimplePagedResultsControl
from distutils.version import LooseVersion

class Command(BaseCommand):
	def handle(self, **options):

		INTEGRASJON_KODEORD = "ad_groups"
		LOG_EVENT_TYPE = "AD group-import"
		KILDE = "Active Directory OSLOFELLES"
		PROTOKOLL = "LDAP"
		BESKRIVELSE = "Tilgangsgrupper"
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

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
		runtime_t0 = time.time()

		try:
			ApplicationLog.objects.create(event_type=LOG_EVENT_TYPE, message="starter..")

			BASEDN = 'DC=oslofelles,DC=oslo,DC=kommune,DC=no'
			SEARCHFILTER = '(objectclass=group)'
			LDAP_SCOPE = ldap.SCOPE_SUBTREE
			ATTRLIST = ['cn', 'description', 'memberOf', 'member', 'displayName', 'mail']
			PAGESIZE = 5000

			report_data = {
				"created": 0,
				"modified": 0,
				"removed": 0,
			}

			# Prefetch all existing groups into a dict for O(1) lookups
			print("Bygger oppslagstabell for eksisterende grupper...")
			existing_groups = {g.distinguishedname: g for g in ADgroup.objects.all()}
			print(f"Fant {len(existing_groups)} eksisterende grupper")

			# Track which groups we see during this run
			seen_dns = set()


			def get_ldap_connection():
				ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
				ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
				l = ldap.initialize(os.environ["KARTOTEKET_LDAPSERVER"])
				l.set_option(ldap.OPT_REFERRALS, 0)
				l.bind_s(os.environ["KARTOTEKET_LDAPUSER"], os.environ["KARTOTEKET_LDAPPASSWORD"])
				return l


			def all_members(common_name):
				"""Retrieve all members for groups with >5000 members using range retrieval."""
				result_members = []
				limit = 5000
				start = 0
				stop = '*'

				l = get_ldap_connection()
				try:
					while True:
						ldap_filter = '(&(objectCategory=Group)(cn=%s))' % common_name
						ldap_properties = 'member;range=%s-%s' % (start, stop)

						query_result = l.search_s(
							BASEDN,
							ldap.SCOPE_SUBTREE,
							ldap_filter,
							[ldap_properties]
						)

						found_range = False
						for cn, attrs in query_result:
							if cn and common_name in cn:
								for key in attrs:
									if 'member;range' in key:
										found_range = True
										page_members = attrs[key]
										result_members.extend(page_members)
										if len(page_members) < limit:
											return result_members
										start += limit
										break
								if found_range:
									break

						if not found_range:
							break
				finally:
					l.unbind_s()

				return result_members


			def result_handler(rdata, report_data, existing_objects=None):
				groups_to_create = []
				groups_to_update = []

				for dn, attrs in rdata:
					if dn is None:
						continue

					seen_dns.add(dn)

					try:
						common_name = dn[3:].split(",")[0]
					except:
						common_name = None

					# Parse member list
					try:
						binary_member = attrs["member"]
						membercount = len(binary_member)
						if membercount == 0 and common_name:
							try:
								binary_member = all_members(common_name)
								membercount = len(binary_member)
							except Exception as e:
								print(f"Range-retrieval feilet for {common_name}: {e}")
						member = json.dumps([m.decode() for m in binary_member])
					except KeyError:
						member = json.dumps([])
						membercount = 0

					# Parse memberOf list
					try:
						binary_memberof = attrs["memberOf"]
						memberofcount = len(binary_memberof)
						memberof = json.dumps([m.decode() for m in binary_memberof])
					except KeyError:
						memberof = json.dumps([])
						memberofcount = 0

					# Parse description
					description = ""
					try:
						for d in attrs["description"]:
							description += d.decode()
					except KeyError:
						pass

					# Parse mail
					mail = ""
					try:
						for d in attrs["mail"]:
							mail += d.decode()
					except KeyError:
						pass

					# Parse displayName
					displayname = ""
					try:
						displayname = attrs["displayName"][0].decode()
					except KeyError:
						pass

					# Update or create
					if dn in existing_groups:
						g = existing_groups[dn]
						report_data["modified"] += 1
					else:
						g = ADgroup(distinguishedname=dn)
						existing_groups[dn] = g
						report_data["created"] += 1

					g.common_name = common_name
					g.description = description
					g.member = member
					g.membercount = membercount
					g.memberof = memberof
					g.memberofcount = memberofcount
					g.display_name = displayname
					g.mail = mail

					if g.pk:
						groups_to_update.append(g)
					else:
						groups_to_create.append(g)

				# Bulk write
				if groups_to_create:
					ADgroup.objects.bulk_create(groups_to_create)
				if groups_to_update:
					ADgroup.objects.bulk_update(
						groups_to_update,
						["common_name", "description", "member", "membercount", "memberof", "memberofcount", "display_name", "mail"],
						batch_size=1000
					)

				sys.stdout.flush()


			# Paged LDAP search (inline, not using shared utility, for full control)
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

			lc = create_controls(PAGESIZE)
			current_round = 0
			objects_returned = 0

			while True:
				current_round += 1
				try:
					msgid = l.search_ext(BASEDN, LDAP_SCOPE, SEARCHFILTER, ATTRLIST, serverctrls=[lc])
				except ldap.LDAPError as e:
					raise Exception(f'ERROR: LDAP search failed: {e}')

				try:
					rtype, rdata, rmsgid, serverctrls = l.result3(msgid)
				except ldap.LDAPError as e:
					raise Exception(f'ERROR: Could not pull LDAP results: {e}')

				objects_start = objects_returned + 1
				objects_returned += len(rdata)
				print(f"Page {current_round}: element {objects_start}-{objects_returned}")

				with transaction.atomic():
					result_handler(rdata, report_data)

				pctrls = get_pctrls(serverctrls)
				if not pctrls:
					print('WARNING: Server ignores RFC 2696 control.')
					break

				cookie = set_cookie(lc, pctrls, PAGESIZE)
				if not cookie:
					break

			l.unbind()

			# Remove groups not seen in this run
			@transaction.atomic
			def remove_unseen_groups():
				old_groups = ADgroup.objects.filter(sist_oppdatert__lte=timezone.now() - timedelta(hours=12))
				group_names = list(old_groups.values_list('common_name', flat=True))
				count = old_groups.count()
				print(f"Sletter {count} utgåtte grupper")
				old_groups.delete()
				log_entry_message = ', '.join([str(n) for n in group_names[:100]])
				if count > 100:
					log_entry_message += f" ... og {count - 100} til"
				ApplicationLog.objects.create(
					event_type="AD-grupper slettet",
					message=log_entry_message,
				)
				report_data["removed"] = count
				print(log_entry_message)

			remove_unseen_groups()

			runtime_t1 = time.time()
			logg_total_runtime = int(runtime_t1 - runtime_t0)

			log_entry_message = f"Det tok {logg_total_runtime} sekunder. {objects_returned} treff. {report_data['created']} nye, {report_data['modified']} endrede, {report_data['removed']} slettet."
			ApplicationLog.objects.create(
				event_type=LOG_EVENT_TYPE,
				message=log_entry_message,
			)
			print(log_entry_message)

			int_config.dato_sist_oppdatert = timezone.now()
			int_config.sist_status = log_entry_message
			int_config.runtime = logg_total_runtime
			int_config.elementer = objects_returned
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
