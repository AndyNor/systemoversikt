# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å oppdatere en lokal oversikt over alle AD-grupper, både for å kunne analysere medlemskap, f.eks. tomme grupper, kunne finne grupper som ikke stammer fra AD, kunne følge med på opprettelse av nye grupper.
"""

# TODO slette grupper som ikke ble funnet

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from systemoversikt.models import *
from django.db.models import Q


class Command(BaseCommand):
	def handle(self, **options):


		# systemer hvor server-os er utdatert
		utdaterte_bss = []


		windows2008_servere = CMDBdevice.objects.filter(comp_os__icontains="2008")
		windows2003_servere = CMDBdevice.objects.filter(comp_os__icontains="2003")
		linux_v5_servere = CMDBdevice.objects.filter(comp_os__icontains="Linux").filter(comp_os_version__istartswith="5")
		#linux_v6_servere = CMDBdevice.objects.filter(comp_os__icontains="Linux").filter(comp_os_version__istartswith="6")

		servere = windows2008_servere | windows2003_servere | linux_v5_servere #| linux_v6_servere

		for s in servere:
			utdaterte_bss.append(s.sub_name)


		# systemer hvor databaseversjon er utdatert
		mssql_2008 = CMDBdatabase.objects.filter(db_version__icontains="SQL server 2008")
		mssql_2005 = CMDBdatabase.objects.filter(db_version__icontains="SQL server 2005")
		oracle_9 = CMDBdatabase.objects.filter(db_version__icontains="Oracle 9")
		oracle_10 = CMDBdatabase.objects.filter(db_version__icontains="Oracle 10")

		databaser = mssql_2008 | mssql_2005 | oracle_9 | oracle_10

		for d in databaser:
			utdaterte_bss.append(d.sub_name)



		for bss in set(utdaterte_bss):
			if bss == None:
				continue
			try:
				systemeier = bss.parent_ref.systemreferanse.systemeier.virksomhetsforkortelse
			except:
				systemeier = "?"

			try:
				systemnavn = bss.parent_ref.systemreferanse.systemnavn
			except:
				systemnavn = "?"

			print("%s\n%s (%s)\n" % (bss.navn, systemnavn, systemeier))





