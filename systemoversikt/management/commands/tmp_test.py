# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å oppdatere en lokal oversikt over alle AD-grupper, både for å kunne analysere medlemskap, f.eks. tomme grupper, kunne finne grupper som ikke stammer fra AD, kunne følge med på opprettelse av nye grupper.
"""

# TODO slette grupper som ikke ble funnet

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from systemoversikt.utils import ldap_paged_search
import ldap
import sys
from systemoversikt.models import ApplicationLog, ADOrgUnit, ADgroup, CMDBbs, System
import json

class Command(BaseCommand):
	def handle(self, **options):

		"""
		# Configuration
		BASEDN ='DC=oslofelles,DC=oslo,DC=kommune,DC=no'
		SEARCHFILTER = '(&(objectCategory=Group)(|(CN=25170)(cn=DS-IWIKI*)(cn=DS-UVALEVTILGANG*)(cn=DS-WIKI*)(cn=TASK-OF2-DRIFT-UVALEVTILGANG)(cn=DS-HEL_TILGI_FAGSAVD*)(cn=DS-UKE_IKTL*)(cn=DS-*_ORG_ALLE)(cn=DS-ROLLEGRUPPER*)))'
		LDAP_SCOPE = ldap.SCOPE_SUBTREE
		ATTRLIST = ['cn', 'description', 'memberOf', 'member'] # if empty we get all attr we have access to
		PAGESIZE = 5000

		def result_handler(rdata, report_data, existing_objects=None):
			for dn, attrs in rdata:
				print(dn)


		report_data = {
			"created": 0,
			"modified": 0,
			"removed": 0,
		}

		result = ldap_paged_search(BASEDN, SEARCHFILTER, LDAP_SCOPE, ATTRLIST, PAGESIZE, result_handler, report_data)
		"""

		for s in System.objects.all():
			try:
				bs = s.bs_system_referanse
				if s.tilgjengelighetsvurdering == None:
					production_availability = []
					for bss in bs.cmdb_bss_to_bs.all():
						if bss.operational_status == 1 and bss.environment == 1:
							production_availability.append(bss.u_service_availability)
					print("%s mangler tilgjengelighetsvurdering. Mulige valg er %s" % (s, production_availability))
					if len(production_availability) > 0:
						chosen_production_availability = production_availability[0] # vi tar bare den tilfeldig første
						if chosen_production_availability == 'T1':
							s.tilgjengelighetsvurdering = 2 # Alvorlig
						if chosen_production_availability == 'T2':
							s.tilgjengelighetsvurdering = 3 # Moderat
						if chosen_production_availability == 'T3':
							s.tilgjengelighetsvurdering = 3 # Moderat
						if chosen_production_availability == 'T4':
							s.tilgjengelighetsvurdering = 4 # Lav
						print("endret %s til %s" % (s, s.tilgjengelighetsvurdering))
						s.save()

			except CMDBbs.DoesNotExist:
				pass
