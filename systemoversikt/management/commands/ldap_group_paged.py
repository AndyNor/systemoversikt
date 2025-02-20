# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.utils import ldap_paged_search
from datetime import timedelta
from datetime import datetime
from django.utils import timezone
from systemoversikt.models import *
from systemoversikt.views import push_pushover
import ldap, os, sys, time
from systemoversikt.models import ApplicationLog, ADOrgUnit, ADgroup
import json

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
		int_config.save()

		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"\n\n{timestamp} ------ Starter {SCRIPT_NAVN} ------")
		runtime_t0 = time.time()

		try:

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

			def ldap_query_members(common_name, start, stop):
				ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # have to deactivate sertificate check
				ldap.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
				l = ldap.initialize(os.environ["KARTOTEKET_LDAPSERVER"])
				l.set_option(ldap.OPT_REFERRALS, 0)
				l.bind_s(os.environ["KARTOTEKET_LDAPUSER"], os.environ["KARTOTEKET_LDAPPASSWORD"])

				ldap_path = "DC=oslofelles,DC=oslo,DC=kommune,DC=no"
				ldap_filter = '(&(objectCategory=Group)(cn=%s))' % common_name
				ldap_properties = 'member;range=%s-%s' % (start, stop)

				#attrs["member"]

				query_result = l.search_s(
						ldap_path,
						ldap.SCOPE_SUBTREE,
						ldap_filter,
						[ldap_properties]
					)

				l.unbind_s()

				for cn, attrs in query_result:
					if common_name in cn:
						return attrs
					else:
						return []


			def all_members(common_name):
				all_members = []
				more_pages = True
				limit = 5000 # hardkodet for nå. Burde egentlig sjekket hva den er..
				start = 0
				stop = '*' # best å ikke angi stopp, da rapporterer AD automatisk neste stopverdi

				while more_pages:
					next_members = ldap_query_members(common_name, start, stop)
					for key in next_members:
						if 'member;range' in key:
							#print(key)
							count_members = len(next_members[key])
							#print(count_members)
							if count_members < limit:
								more_pages = False
							for m in next_members[key]:
								#print("value=%s" % m)
								all_members.append(m)
							start = start + limit

				return all_members


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
							print(f"DN for {attrs} var tom.")
							continue

						try:
							common_name = distinguishedname[3:].split(",")[0]
						except:
							common_name = None

						try:
							member = []
							binary_member = attrs["member"]
							membercount = len(binary_member)
							if membercount == 0: # skjer enten fordi gruppen er tom, eller fordi det er flere enn 5000 medlemmer (i denne AD-en, kan settes til en annen verdi i AD)
								try:
									binary_member = all_members(common_name)
									membercount = len(binary_member)
									#print("Oppslag etter member-range. Fant %s medlemmer" % membercount)
								except Exception as e:
									print(e)
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


						displayname = ""
						try:
							displayname = attrs["displayName"][0].decode()
						except KeyError as e:
							pass

						try:
							g = ADgroup.objects.get(distinguishedname=distinguishedname)
							#print("u", end="")
							report_data["modified"] += 1
						except:
							g = ADgroup.objects.create(distinguishedname=distinguishedname) # lager den om den ikke finnes
							#print("n", end="")
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
				log_entry_message = f"Det tok{result['total_runtime']} sekunder. {result['objects_returned']} treff. {result['report_data']['created']} nye, {result['report_data']['modified']} endrede."
				log_entry = ApplicationLog.objects.create(
						event_type=LOG_EVENT_TYPE,
						message=log_entry_message,
				)
				print(log_entry_message)

				# lagre sist oppdatert tidspunkt
				int_config.dato_sist_oppdatert = timezone.now()
				int_config.sist_status = log_entry_message

				runtime_t1 = time.time()
				logg_total_runtime = int(runtime_t1 - runtime_t0)
				int_config.runtime = logg_total_runtime

				int_config.elementer = int(result['objects_returned'])

				int_config.save()


			# her kjører selve synkroniseringen
			result = ldap_paged_search(BASEDN, SEARCHFILTER, LDAP_SCOPE, ATTRLIST, PAGESIZE, result_handler, report_data)
			report(result)
			remove_unseen_groups()

			"""
			@transaction.atomic  # uklart om det er behov for denne lenger. trolig noe som gikk galt første kjøringer av scripetet..
			def cleanup():
				from django.db.models import Count
				duplicates = ADgroup.objects.values("distinguishedname").annotate(count=Count("distinguishedname")).filter(count__gt=1)
				for group in duplicates:
					group = ADgroup.objects.filter(distinguishedname=group["distinguishedname"])
					print("rydder opp %s" % (group["distinguishedname"]))
					group.delete()

			cleanup()
			"""


		except Exception as e:
			logg_message = f"{SCRIPT_NAVN} feilet med meldingen {e}"
			logg_entry = ApplicationLog.objects.create(
					event_type=LOG_EVENT_TYPE,
					message=logg_message,
					)
			print(logg_message)

			# Push error
			push_pushover(f"{SCRIPT_NAVN} feilet")