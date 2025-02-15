# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import Virksomhet

class Command(BaseCommand):
	def handle(self, **options):

		for u in User.objects.all():
			if u.username[0:5].upper() == "DRIFT":
				virksomhet_obj_ref = Virksomhet.objects.get(virksomhetsforkortelse="DRIFT")
				u.profile.virksomhet = virksomhet_obj_ref
				u.save()
				print("Fikset %s" % u)
