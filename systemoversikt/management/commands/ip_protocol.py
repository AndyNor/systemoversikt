# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
import os
import time
import sys
import csv
from datetime import datetime
from django.utils.timezone import make_aware
import requests
from systemoversikt.models import CMDBdevice, Virksomhet, ApplicationLog, IpProtocol
from django.core.exceptions import ObjectDoesNotExist
from py_topping.data_connection.sharepoint import da_tran_SP365


class Command(BaseCommand):
	def handle(self, **options):

		@transaction.atomic
		def run():
			with open("systemoversikt/management/commands/service-names-port-numbers.csv", 'r', encoding='latin-1') as destination_file:
				csv_data = list(csv.DictReader(destination_file, delimiter=","))
				print("Det er %s linjer i filen" % len(csv_data))

			IpProtocol.objects.all().delete()
			for line in csv_data:
				if line["Transport Protocol"] == "":
					continue
				if line["Port Number"] == "" or "-" in line["Port Number"]:
					continue
				if line["Description"].lower() == "unassigned" or line["Description"].lower() == "reserved":
					continue
				if line["Description"] == "":
					continue
				if line["Assignee"].lower() == "unassigned" or line["Description"].lower() == "reserved":
					continue

				IpProtocol.objects.create(
						port=line["Port Number"],
						protocol=line["Transport Protocol"],
						description=line["Description"],
					)
		run()

