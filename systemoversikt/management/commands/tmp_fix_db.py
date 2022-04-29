# -*- coding: utf-8 -*-
"""
Hensikten med denne koden er å fikse tilknytning virksomhet for DRIFT-brukere
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from systemoversikt.models import System, Database

class Command(BaseCommand):
	def handle(self, **options):

		for s in System.objects.filter(database=1): # MSSQL: Hotell på felles IKT-plattform
			s.database_in_use.add(Database.objects.get(pk=2))  # MS SQL
			s.database_supported.add(Database.objects.get(pk=2))  # MS SQL
			s.avhengigheter_referanser.add(System.objects.get(pk=913)) # MSSQL databasehotell (Sentral løsning)
			s.save()
		print("Ferdig med MSSQL hotell")

		for s in System.objects.filter(database=2): #MSSQL: Annen drift
			s.database_in_use.add(Database.objects.get(pk=2))  # MS SQL
			s.database_supported.add(Database.objects.get(pk=2))  # MS SQL
			s.save()
		print("Ferdig med MSSQL annet")

		for s in System.objects.filter(database=3): # Oracle: Hotell på felles IKT-plattform
			s.database_in_use.add(Database.objects.get(pk=6))  # Oracle
			s.database_supported.add(Database.objects.get(pk=6))  # Oracle
			s.avhengigheter_referanser.add(System.objects.get(pk=917)) # Oracle databasehotell (Sentral løsning)
			s.save()
		print("Ferdig med Oracle hotell")

		for s in System.objects.filter(database=4): # Oracle: Annen drift
			s.database_in_use.add(Database.objects.get(pk=6))  # Oracle
			s.database_supported.add(Database.objects.get(pk=6))  # Oracle
			s.save()
		print("Ferdig med Oracle annet")

		for s in System.objects.filter(database=5): # SQLite
			s.database_in_use.add(Database.objects.get(pk=1))  # SQLite
			s.database_supported.add(Database.objects.get(pk=1))  # SQLite
			s.save()
		print("Ferdig med SQLite")

		for s in System.objects.filter(database=6): # PostgreSQL
			s.database_in_use.add(Database.objects.get(pk=4))  # PostgreSQL
			s.database_supported.add(Database.objects.get(pk=4))  # PostgreSQL
			s.save()
		print("Ferdig med PostgreSQL")

		for s in System.objects.filter(database=7): # MySQL
			s.database_in_use.add(Database.objects.get(pk=3))  # PostgreSQL
			s.database_supported.add(Database.objects.get(pk=3))  # PostgreSQL
			s.save()
		print("Ferdig med MySQL")

		for s in System.objects.filter(database=8): # Firebird
			s.database_in_use.add(Database.objects.get(pk=5))  # Firebird
			s.database_supported.add(Database.objects.get(pk=5))  # Firebird
			s.save()
		print("Ferdig med Firebird")
