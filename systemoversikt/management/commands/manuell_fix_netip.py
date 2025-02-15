# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import *
import ipaddress

class Command(BaseCommand):
	def handle(self, **options):

		for n in NetworkIPAddress.objects.all():
			if n.ip_address_integer == None:
				print(n)
				n.ip_address_integer = int(ipaddress.ip_address(n.ip_address))
				n.save()