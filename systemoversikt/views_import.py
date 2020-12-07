# -*- coding: utf-8 -*-
from django.shortcuts import render, redirect
from django.core.exceptions import ObjectDoesNotExist
from django.core import serializers
from systemoversikt.models import *
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.db.models import Count
from django.db.models.functions import Lower
from django.db.models import Q
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponseBadRequest, JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
import datetime
import json, os
from django.db import transaction


def import_group_permissions(request):
	import json, os
	from django.contrib.auth.models import Group, Permission
	required_permissions = 'auth.change_group'
	if request.user.has_perm(required_permissions):

		if request.POST:
			filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/group_permissions.json"
			try:
				with open(filepath, 'r', encoding='UTF-8') as json_file:
					data = json.load(json_file)
					for group in data:
						#print(group["group"])
						group_name = group["group"]
						try:
							g = Group.objects.get(name=group_name)
						except:
							messages.warning(request, 'Gruppen %s finnes ikke' % group_name)
							continue
						g.permissions.clear()
						for new_perm in group["permissions"]:
							#print(new_perm)
							try:
								p = Permission.objects.get(Q(codename=new_perm["codename"]) & Q(content_type__app_label=new_perm["content_type__app_label"]))
								g.permissions.add(p)
							except:
								messages.warning(request, 'Rettigheten %s finnes ikke' % new_perm["codename"])
								continue

				logg_entry_message = ("Det er utført en import fra fil av %s" % request.user)
				logg_entry = ApplicationLog.objects.create(
						event_type='Grupperettigheter import',
						message=logg_entry_message,
					)
				messages.success(request, logg_entry_message)

				return render(request, 'site_home.html', {
					'request': request,
				})
			except:
				messages.warning(request, 'Filen %s finnes ikke' % (filepath))
				return render(request, 'admin_import.html', {'request': request,})

		else:
			return render(request, 'admin_import.html', {'request': request,})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def konverter_environment(str):
	oppslagsmatrise = {
		"": 8,  # ukjent
		"production": 1,
		"staging": 6,
		"test": 2,
		"qa": 7,
		"development": 3,
		"training": 4,
		"demonstration": 2,
		"disaster recovery": 9,
	}
	try:
		return oppslagsmatrise[str.lower()]  # lowercase for å slippe unødige feil
	except:
		messages.success(request, 'Konvertere environment: fant ikke %s' % (str))
		return 8  # Ukjent


def konverter_kritikalitet(str):
	oppslagsmatrise = {
		"": None,  # ukjent
		"4 - not critical": 4,
		"3 - less critical": 3,
		"2 - somewhat critical": 2,
		"1 - most critical": 1,
	}
	try:
		return oppslagsmatrise[str.lower()]  # lowercase for å slippe unødige feil
	except:
		messages.error(request, 'Konvertere kritikalitet: fant ikke %s' % (str))
		return None  # Ukjent


def convertToInt(string):
	try:
		return int(string)
	except:
		return None


def convertToBool(string):
	if string.lower() == "yes":
		return True
	if string.lower() == "no":
		return False
	else:
		return None


@transaction.atomic
def import_business_services(request):

	required_permissions = 'systemoversikt.change_cmdbref'
	if request.user.has_perm(required_permissions):

		#business_services_filename = "u_cmdb_service_subservice.json"
		#business_services_filename = "u_cmdb_service_subservice.xlsx"
		business_services_filename = "OK - Kartoketet Business Services.xlsx"

		filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/" + business_services_filename
		#messages.success(request, 'Lastet inn filen %s' % (filepath))

		"""
		with open(filepath, 'r', encoding='UTF-8') as json_file:
			data = json.load(json_file)
			antall_records = len(data["records"])
			messages.success(request, 'Fant %s elementer' % (antall_records))
		"""

		import pandas as pd
		import numpy as np
		dfRaw = pd.read_excel(filepath)
		dfRaw = dfRaw.replace(np.nan, '', regex=True)
		data = dfRaw.to_dict('records')


		# Gå igjennom alle eksisterende business services, dersom ikke i ny fil, merk med "utgått"
		alle_eksisterende_cmdbref = list(CMDBRef.objects.all()) #bss
		alle_eksisterende_cmdbbs = list(CMDBbs.objects.all()) #bs

		# Importere enheter (andre data i importfil nummer 2)
		antall_nye_bs = 0
		antall_deaktiverte_bs = 0
		antall_nye_bss = 0
		antall_slettede_bss = 0

		antall_records = len(data)

		for record in data:

			bss_dropped = 0
			bs_dropped = 0
			bss_name = record["Name"]
			bs_name = record["Name.1"]
			bss_id = record["Sys ID.1"]
			bs_id = record["Sys ID"]

			if bs_name == "" or bss_name == "":
				messages.error(request, "Business service navn eller BSS-navn mangler")
				bss_dropped += 1
				continue  # Det må være en verdi på denne

			# sjekke om bs finnes fra før, om ikke opprette
			if len(bs_id) < 32:
				messages.error(request, "Business service %s manglet unik ID" % bs_name)
				bs_dropped += 1
				continue

			try:
				business_service = CMDBbs.objects.get(bs_external_ref=bs_id)
				if business_service in alle_eksisterende_cmdbbs:
					alle_eksisterende_cmdbbs.remove(business_service)
				if business_service.navn != bs_name:
					messages.info(request, "Nytt og gammelt navn stemmer ikke overens for %s og %s" % (business_service.navn, bs_name))
			except:
				antall_nye_bs += 1
				business_service = CMDBbs.objects.create(
						bs_external_ref=bs_id,
				)
			business_service.navn = bs_name
			#business_service.bs_external_ref = record["Sys ID"]
			business_service.save()

			# sjekke om bss finnes fra før, om ikke opprette
			if len(bss_id) < 32:
				messages.error(request, "Business sub service %s manglet unik ID" % bss_name)
				bss_dropped += 1
				continue

			try:
				business_sub_service = CMDBRef.objects.get(bss_external_ref=bss_id)
				if business_sub_service in alle_eksisterende_cmdbref:
					alle_eksisterende_cmdbref.remove(business_sub_service)
				if business_sub_service.navn != bss_name:
					messages.info(request, "Nytt og gammelt navn stemmer ikke overens for %s og %s" % (business_sub_service.navn, bss_name))
			except:
				antall_nye_bs += 1
				business_sub_service = CMDBRef.objects.create(
						bss_external_ref=bss_id,
				)

			business_sub_service.navn = bss_name
			#business_sub_service.bss_external_ref = record["Sys ID.1"]
			business_sub_service.environment=konverter_environment(record["Environment"])
			business_sub_service.kritikalitet=konverter_kritikalitet(record["Business criticality"])
			#business_sub_service.u_service_portfolio=record["sub_u_service_portfolio"]
			business_sub_service.u_service_availability=record["Service Availability"]
			business_sub_service.u_service_operation_factor = record["Service Operation Factor"]
			business_sub_service.u_service_complexity = record["Service Complexity"]
			business_sub_service.operational_status = True if record["Operational status"] == "Operational" else False
			business_sub_service.u_service_billable = True if record["Service Billable"] == "Yes" else False
			business_sub_service.parent_ref = business_service
			business_sub_service.service_classification = record["Service classification"]
			business_sub_service.comments = record["Description"]

			business_sub_service.save()

		# deaktiverer alle bs og sletter alle bss som er igjen
		for cmdbbs in alle_eksisterende_cmdbbs:
			if cmdbbs.operational_status == True:
				cmdbbs.operational_status = False
				antall_deaktiverte_bs += 1
				cmdbbs.save()

		for cmdbref in alle_eksisterende_cmdbref:
			antall_slettede_bss += 1
			cmdbref.delete()

		logg_entry_message = "Antall BSS: %s. Nye BS: %s (%s satt inaktiv), nye BSS: %s (%s slettede). %s BS og %s BSS feilet. Utført av %s" % (
					antall_records,
					antall_nye_bs,
					antall_deaktiverte_bs,
					antall_nye_bss,
					antall_slettede_bss,
					bs_dropped,
					bss_dropped,
					request.user
				)
		logg_entry = ApplicationLog.objects.create(
				event_type='CMDB business service import',
				message=logg_entry_message,
			)
		messages.success(request, logg_entry_message)

		return render(request, 'cmdb_index.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


# TODO to ganske like script for oracle og mssql. datakildene er ikke like..
@transaction.atomic
def import_cmdb_databases_oracle(request):
	required_permissions = 'systemoversikt.change_cmdbref'
	if request.user.has_perm(required_permissions):

		import json, os
		import pandas as pd
		import numpy as np
		#import xlrd

		db_dropped = 0

		#temporary file with oracle disk size
		filepath_size = os.path.dirname(os.path.abspath(__file__)) + "/import/oracle_disksize.xlsx"
		dfRaw = pd.read_excel(filepath_size)
		dfRaw = dfRaw.replace(np.nan, '', regex=True)
		size_data = dfRaw.to_dict('records')
		size_data = {"%s@%s" % (item["SID"], item["Server Name"]):item["Bytes Used (GB)"] for item in size_data}
		#print(size_data)


		#filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/u_cmdb_bs_bss_db_oracle.json"
		#filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/u_cmdb_bs_bss_db_oracle.xlsx"
		filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/OK - CMDB - BS - BSS - DB_Oracle.xlsx"

		if ".xlsx" in filepath:
			dfRaw = pd.read_excel(filepath)
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			data = dfRaw.to_dict('records')

		if ".json" in filepath:
			with open(filepath, 'r', encoding='UTF-8') as json_file:
				data = json.load(json_file)["records"]

		if data == None:
			return

		antall_records = len(data)

		all_existing_db = list(CMDBdatabase.objects.filter(Q(db_version__startswith="Oracle ") & Q(db_operational_status=True)))

		for record in data:
			#print(record)

			if ".xlsx" in filepath:
				try:
					db_fullname = record["Name"] # det er to felt som heter "name" og dette er det første...
					db_name = record["Name"].split("@")[0] # første del er databasenavnet
					db_server = record["Name"].split("@")[1] # andre del etter @ er servernavn.
				except:
					db_dropped += 1
					continue # hvis dette ikke går er navnet feilformattert.
				#print(db_name)
				if db_name == "":
					messages.error(request, "Database mangler navn")
					db_dropped += 1
					continue  # Det må være en verdi på denne

				# vi sjekker om enheten finnes fra før
				try:
					cmdb_db = CMDBdatabase.objects.get(db_database=db_name)
					# fjerner fra oversikt over alle vi hadde før vi startet
					if cmdb_db in all_existing_db: # i tilfelle reintrodusert
						all_existing_db.remove(cmdb_db)
				except:
					# lager en ny
					cmdb_db = CMDBdatabase.objects.create(db_database=db_name)

				cmdb_db.db_server = db_server

				if record["Operational status"] == "Operational":
					cmdb_db.db_operational_status = True
				else:
					cmdb_db.db_operational_status = False

				cmdb_db.db_version = "Oracle " + record["Version"]

				#try:
				#	filesize = int(record.get("db_u_datafilessizekb", 0)) * 1024 # convert to bytes
				#except:
				#	filesize = 0

				try:
					size_bytes = int(size_data[db_fullname]) * 1024 * 1024 * 1024  # kommer som string i GB.
					cmdb_db.db_u_datafilessizekb = size_bytes
					#print(size_bytes)
				except:
					#print("failed")
					cmdb_db.db_u_datafilessizekb = 0


				cmdb_db.db_used_for = record["Used for"]
				cmdb_db.db_comments = record["Comments"]

				cmdb_db.sub_name = None  # reset old lookups
				try:
					business_service = CMDBRef.objects.get(navn=record["Name.1"]) # dette er det andre "name"-feltet
					cmdb_db.sub_name = business_service # add this lookup
				except:
					pass
				cmdb_db.save()


			"""
			if ".json" in filepath:
				db_name = record["db_name"]
				print(db_name)
				if db_name == "":
					messages.error(request, "Database mangler navn")
					db_dropped += 1
					continue  # Det må være en verdi på denne
				# vi sjekker om enheten finnes fra før
				try:
					cmdb_db = CMDBdatabase.objects.get(db_database=db_name)
					# fjerner fra oversikt over alle vi hadde før vi startet
					if cmdb_db in all_existing_db: # i tilfelle reintrodusert
						all_existing_db.remove(cmdb_db)
				except:
					# lager en ny
					cmdb_db = CMDBdatabase.objects.create(db_database=db_name)

				if record["db_operational_status"] == "1":
					cmdb_db.db_operational_status = True
				else:
					cmdb_db.db_operational_status = False

				cmdb_db.db_version = "Oracle " + record["db_version"]

				try:
					match = size_data[db_name]
					size_bytes = int(size_data[db_name]) * 1024 * 1024 * 1024  # kommer som string i GB.
					cmdb_db.db_u_datafilessizekb = size_bytes
					#print(size_bytes)
				except:
					#print("failed")
					cmdb_db.db_u_datafilessizekb = 0

				cmdb_db.db_used_for = record["db_used_for"]
				cmdb_db.db_comments = record["db_comments"]

				cmdb_db.sub_name.clear() # reset old lookups
				try:
					business_service = CMDBRef.objects.get(navn=record["sub_name"])
					cmdb_db.sub_name.add(business_service) # add this lookup
				except:
					pass
				cmdb_db.save()
			"""



		# cleanup
		obsolete_devices = all_existing_db

		for item in obsolete_devices:
			item.delete()

		logg_entry_message = 'Fant %s databaser. %s manglet navn. Slettet %s inaktive databaser. Utført av %s.' % (antall_records, db_dropped, len(obsolete_devices), request.user)
		logg_entry = ApplicationLog.objects.create(
				event_type='CMDB database import (Oracle)',
				message=logg_entry_message,
			)
		messages.success(request, logg_entry_message)

		return render(request, 'cmdb_index.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


#MSSQL-import
@transaction.atomic
def import_cmdb_databases(request):
	required_permissions = 'systemoversikt.change_cmdbref'
	if request.user.has_perm(required_permissions):

		#messages.success(request, 'Klargjør import av databaser')
		import json, os
		import pandas as pd
		import numpy as np

		db_dropped = 0

		#filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/u_cmdb_service_to_db_2.json"
		filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/u_cmdb_service_to_db_2.xlsx"

		if ".xlsx" in filepath:
			dfRaw = pd.read_excel(filepath)
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			data = dfRaw.to_dict('records')

		if ".json" in filepath:
			with open(filepath, 'r', encoding='UTF-8') as json_file:
				data = json.load(json_file)["records"]

		if data == None:
			return


		antall_records = len(data)
		#messages.success(request, 'Fant %s elementer' % (antall_records))

		all_existing_db = list(CMDBdatabase.objects.filter(~Q(db_version__startswith="Oracle ") & Q(db_operational_status=True)))


		for record in data:
			#print(record)

			if ".xlsx" in filepath:
				db_name = record["Name"]
				if db_name == "":
					messages.error(request, "Database mangler navn")
					db_dropped += 1
					continue  # Det må være en verdi på denne

				try:
					hostname = record["Comments"].split("@")[1]
				except:
					messages.error(request, "Database mangler informasjon om host (%s)" % (db_name))
					hostname = ""

				db_id = "%s@%s" % (db_name, hostname)
				# vi sjekker om databasen finnes fra før
				try:
					cmdb_db = CMDBdatabase.objects.get(db_database=db_id)
					# fjerner fra oversikt over alle vi hadde før vi startet denne oppdateringen
					if cmdb_db in all_existing_db: # i tilfelle reintrodusert
						all_existing_db.remove(cmdb_db)
				except:
					# lager en ny
					cmdb_db = CMDBdatabase.objects.create(db_database=db_id)

				if record["Operational status"] == "Operational":
					cmdb_db.db_operational_status = True
				else:
					cmdb_db.db_operational_status = False

				if record["Version"] != "":
					cmdb_db.db_version = record["Version"]
				else:
					cmdb_db.db_version = "MSSQL"

				try:
					filesize = int(record.get("DataFilesSizeKB", 0)) * 1024 # convert to bytes
				except:
					filesize = 0
				cmdb_db.db_u_datafilessizekb = filesize

				cmdb_db.db_used_for = record["Used for"]
				cmdb_db.db_comments = record["Comments"]

				cmdb_db.sub_name = None  # reset old lookups
				try:
					business_service = CMDBRef.objects.get(navn=record["Name.1"]) # dette er det andre "name"-feltet
					cmdb_db.sub_name = business_service # add this lookup
				except:
					pass

				cmdb_db.save()

		obsolete_devices = all_existing_db

		for item in obsolete_devices:
			item.delete()

		logg_entry_message = 'Fant %s databaser. %s manglet navn. Slettet %s inaktive databaser. Utført av %s.' % (
				antall_records,
				db_dropped,
				len(obsolete_devices),
				request.user
			)
		logg_entry = ApplicationLog.objects.create(
				event_type='CMDB database import',
				message=logg_entry_message,
			)
		messages.success(request, logg_entry_message)

		return render(request, 'cmdb_index.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })




@transaction.atomic
def import_cmdb_servers(request):
	required_permissions = 'systemoversikt.change_cmdbref'
	if request.user.has_perm(required_permissions):

		import json, os
		import pandas as pd
		import numpy as np

		server_dropped = 0

		#filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/u_cmdb_computer_to_sub_to_bs.xlsx"
		filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/Oslo Kommune - CMDB - Computer with BS and BSS - Ken Persen NY.xlsx"

		if ".xlsx" in filepath:
			dfRaw = pd.read_excel(filepath)
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			data = dfRaw.to_dict('records')

		if data == None:
			return

		antall_records = len(data)
		all_existing_devices = list(CMDBdevice.objects.all())

		def convertToInt(string, multiplier=1):
			try:
				number = int(string)
			except:
				return None

			return number * multiplier


		for record in data:
			#print(record)

			comp_name = record["Name"]
			if comp_name == "":
				messages.error(request, "Maskinen mangler navn")
				server_dropped += 1
				continue  # Det må være en verdi på denne

			# vi sjekker om enheten finnes fra før
			try:
				cmdbdevice = CMDBdevice.objects.get(comp_name=comp_name)
				# fjerner fra oversikt over alle vi hadde før vi startet
				if cmdbdevice in all_existing_devices: # i tilfelle reintrodusert
					all_existing_devices.remove(cmdbdevice)
			except:
				# lager en ny
				cmdbdevice = CMDBdevice.objects.create(comp_name=comp_name)

			cmdbdevice.active = True
			cmdbdevice.comp_disk_space = convertToInt(record["Disk space (GB)"])
			cmdbdevice.comp_cpu_core_count = convertToInt(record["CPU total"])
			cmdbdevice.comp_ram = convertToInt(record["RAM (MB)"])
			cmdbdevice.comp_ip_address = record["IP Address"]
			cmdbdevice.comp_cpu_speed = convertToInt(record["CPU speed (MHz)"])
			cmdbdevice.comp_os = record["Operating System"]
			cmdbdevice.comp_os_version = record["OS Version"]
			cmdbdevice.comp_os_service_pack = record["OS Service Pack"]
			cmdbdevice.comp_location = record["Location"]
			#cmdbdevice.comp_cpu_core_count = convertToInt(record["comp_cpu_core_count"])
			#cmdbdevice.comp_cpu_count = convertToInt(record["comp_cpu_count"])
			#cmdbdevice.comp_cpu_name = record["comp_cpu_name"]
			#cmdbdevice.comp_u_cpu_total = convertToInt(record["comp_u_cpu_total"])
			#cmdbdevice.comp_ram = convertToInt(record["comp_ram"])
			#cmdbdevice.comp_sys_id = record["comp_sys_id"]

			try:
				sub_name = CMDBRef.objects.get(navn=record["Name.1"])
				cmdbdevice.sub_name = sub_name
			except:
				messages.error(request, 'Business sub service %s for %s finnes ikke' % (record["sub_name"], comp_name))
				server_dropped += 1
				continue

			cmdbdevice.save()

		obsolete_devices = all_existing_devices
		devices_set_inactive = 0

		for item in obsolete_devices:
			if item.active == True:
				item.active = False
				devices_set_inactive += 1
				item.save()

		logg_entry_message = 'Fant %s maskiner. %s manglet navn eller tilhørighet. Satte %s servere inaktiv. Utført av %s.' % (
				antall_records,
				server_dropped,
				devices_set_inactive,
				request.user
			)
		logg_entry = ApplicationLog.objects.create(
				event_type='CMDB server import',
				message=logg_entry_message,
			)
		messages.success(request, logg_entry_message)

		return render(request, 'cmdb_index.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


@transaction.atomic
def import_cmdb_disk(request):
	required_permissions = 'systemoversikt.change_cmdbref'
	if request.user.has_perm(required_permissions):

		import json, os
		import pandas as pd
		import numpy as np

		disk_dropped = 0

		#filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/cmdb_ci_file_system.xlsx"
		filepath = os.path.dirname(os.path.abspath(__file__)) + "/import/OK - Kartoteket - Disk Information.xlsx"

		if ".xlsx" in filepath:
			dfRaw = pd.read_excel(filepath)
			dfRaw = dfRaw.replace(np.nan, '', regex=True)
			data = dfRaw.to_dict('records')

		if data == None:
			return

		antall_records = len(data)

		all_existing_devices = list(CMDBDisk.objects.all())

		def convertToInt(string, multiplier=1):
			try:
				number = int(string)
			except:
				return None

			return number * multiplier

		ikke_koblet = 0

		for record in data:

			disk_name = record["Name"]
			mount_point = record["Mount point"]

			if mount_point == "" and disk_name != "":
				mount_point = disk_name

			if mount_point == "":
				disk_dropped += 1
				messages.warning(request, 'Disk manglet mount point')
				continue

			# vi sjekker om disken finnes fra før
			try:
				cmdb_disk = CMDBDisk.objects.get(Q(computer=record["Computer"]) & Q(mount_point=mount_point))
				# fjerner fra oversikt over alle vi hadde før vi startet
				if cmdb_disk in all_existing_devices: # i tilfelle reintrodusert
					all_existing_devices.remove(cmdb_disk)
			except:
				# lager en ny
				cmdb_disk = CMDBDisk.objects.create(computer=record["Computer"], mount_point=mount_point)


			cmdb_disk.operational_status = True
			cmdb_disk.name = disk_name
			cmdb_disk.size_bytes = convertToInt(record["Size bytes"], 1)
			cmdb_disk.free_space_bytes = convertToInt(record["Free space bytes"], 1)
			cmdb_disk.file_system = record["File system"]
			#cmdb_disk.capacity = record["capacity"]
			#cmdb_disk.available_space = record["available_space"]


			try:
				computer_ref = CMDBdevice.objects.get(comp_name=record["Computer"])
				cmdb_disk.computer_ref = computer_ref
				#messages.success(request, 'Maskin med ID %s koblet' % (record["computer"]))
			except:
				disk_dropped += 1
				cmdb_disk.delete()
				continue
				#messages.error(request, 'Maskin med ID %s finnes ikke' % (record["computer"]))
				#sub_name = CMDBRef.objects.create(
				#		navn=record["sub_name"],
				#		operational_status=1,
				#	)

			cmdb_disk.save()

		obsolete_devices = all_existing_devices
		for item in obsolete_devices:
			item.delete()


		logg_entry_message = '%s disker funnet. %s manglet vesentlig informasjon og ble ikke importert. %s gamle slettet. Utført av %s.' % (
				antall_records,
				disk_dropped,
				len(obsolete_devices),
				request.user
			)
		logg_entry = ApplicationLog.objects.create(
				event_type='CMDB disk import',
				message=logg_entry_message,
			)
		messages.success(request, logg_entry_message)

		return render(request, 'cmdb_index.html', {
			'request': request,
		})
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })


def import_organisatorisk_forkortelser(request):
	required_permissions = 'systemoversikt.add_definisjon'
	if request.user.has_perm(required_permissions):

		antall_importert = 0

		try:
			definisjonskontekst = DefinisjonKontekster.objects.get(navn="Organisatorisk forkortelse")
		except:
			definisjonskontekst = DefinisjonKontekster.objects.create(navn="Organisatorisk forkortelse")

		alle_virksomheter = Virksomhet.objects.all()
		for v in alle_virksomheter:
			virksomhetsforkortelse = v.virksomhetsforkortelse
			virksomhetsnavn = v.virksomhetsnavn
			try:
				d = Definisjon.objects.get(begrep=v.virksomhetsforkortelse)
				#messages.info(request, "Forkortelsen %s eksisterer fra før av, går til neste" % v.virksomhetsforkortelse)
			except:
				if v.virksomhetsforkortelse:
					d = Definisjon.objects.create(
						status=1,
						begrep=v.virksomhetsforkortelse,
						definisjon=v.virksomhetsnavn)
					d.kontekst_ref = definisjonskontekst
					d.save()
					antall_importert += 1
					messages.success(request, "Importerte begrepet %s" % v.virksomhetsforkortelse)
				else:
					messages.warning(request, "Hopper over %s" % v.virksomhetsnavn)

		messages.success(request, "Alle virksomhetsforkortelser er nå lagt til")
		return HttpResponseRedirect(reverse('alle_definisjoner'))
	else:
		return render(request, '403.html', {'required_permissions': required_permissions, 'groups': request.user.groups })



def load_dns_sonefile(filename, domain):
	import dns.zone
	z = dns.zone.from_file(filename, domain)
	dns_datastructure = []
	for (name, ttl, rdata) in z.iterate_rdatas('A'):
		data = {"name":name,"target":"", "ip_address":rdata.address}
		dns_datastructure.append(data)
	for (name, ttl, rdata) in z.iterate_rdatas('CNAME'):
		lookup = z.get_rdataset(rdata.target, 'A')
		if lookup is None:
			pass
		else:
			lookup = lookup.to_text().split()[3]
		data = {"name":name,"target":rdata.target, "ip_address":lookup}
		dns_datastructure.append(data)
	return dns_datastructure

def find_ip_in_dns(address, dns_data):
	import ipaddress
	result_text = ""
	for item in dns_data:
		if item["ip_address"] is not None:
			if ipaddress.ip_address(address) == ipaddress.ip_address(item["ip_address"]):
				result_text += str(item["name"])
				result_text += ", "
	return(result_text)


def load_vlan(filename):
	import csv
	vlan_data = []
	with open(filename, 'r', encoding='latin-1') as file:
		vlan_datastructure = list(csv.DictReader(file, delimiter="\t"))
		for line in vlan_datastructure:
			t = {
				"address": line["Subnett"],
				"address_v6": line["IPv6"],
				"beskrivelse": line["Beskrivelse"],
				"sikkerhetsnivaa": line["Sikkerhetsnivå"],
				"vlan": line["VLAN"],
				"vlan_name": line["VLAN-navn"],
			}
			vlan_data.append(t)
	return vlan_data

def ip_in_network(query, network):
	import ipaddress
	try:
		# ip_network supports a single network (like 10.0.0.1/32)
		network = ipaddress.ip_network(network)
	except:
		return False
	query_ip = ipaddress.ip_address(query)
	if query_ip in network:
		return True
	else:
		return False

def find_vlan(input_var, vlan_data):
	result_text = ""
	for item in vlan_data:
		network = (item["address"], item["address_v6"])
		for n in network:
			if ip_in_network(input_var, n):
				result_text += (item["beskrivelse"] + "(" + item["address"] + ")" + " (VLAN " + item["vlan"] + ")" + " (" + item["sikkerhetsnivaa"] + ")")
	return result_text


def load_nat(filename):
	import csv
	nat_datastructure = []
	with open(filename, 'r', encoding='latin-1') as file:
		nat_data = list(csv.DictReader(file, delimiter="\t"))
		for line in nat_data:
			t = {
					"public_ip_address": line["Offisiell IP"],
					"private_ip_address":line["Privat IP"],
					"firewall":line["FW"],
					"comment": line["Kommentar"]
			}
			nat_datastructure.append(t)
	return nat_datastructure

def find_ip_in_nat(ip, nat_data):
	for item in nat_data:
		if item["comment"] == "NAT hide for OKMAN mot DAX":
			continue  # they would end up in every 10.x.x.x search

		def pretty_print(item):
			result_text = (""
					+ str(item["public_ip_address"])
					+ " <--> "
					+ str(item["private_ip_address"])
					+ " ("
					+ str(item["firewall"])
					+ ", "
					+ str(item["comment"])
					+ ")"
			)
			return result_text

		if ip_in_network(ip, item["private_ip_address"]):
			return(pretty_print(item))
		if ip_in_network(ip, item["public_ip_address"]):
			return(pretty_print(item))


def load_bigip(filename):
	import csv
	bigip_data = []
	with open(filename, 'r', encoding='latin-1') as file:
		bigip_datastructure = list(csv.DictReader(file, delimiter="\t"))
		for line in bigip_datastructure:
			t = {
				"vip": line["VIP-adresse"],
				"vip_text": line["VIP"],
				"pool": line["Pool"],
				"port": line["Port"],
				"url": line["URL"]
			}
			bigip_data.append(t)
	return bigip_data

def find_bigip(input_var, bigip_data):
	for item in bigip_data:
		network = (item["vip"],item["pool"])
		for n in network:
			if ip_in_network(input_var, n):
				return(item["url"] + " (" + item["vip"] + " --> " + item["pool"] + " " + item["port"] + ")")
	return None
