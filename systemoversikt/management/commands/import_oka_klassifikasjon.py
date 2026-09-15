# -*- coding: utf-8 -*-
# Change log:
# 2026-09-15: Management command wraps shared oka_import (also used by the upload page).

from django.core.management.base import BaseCommand, CommandError
from systemoversikt.oka_import import import_oka_workbook
import os


class Command(BaseCommand):
	help = 'Importer OKA-klassifikasjon fra Excel (samme logikk som Last inn OKA i administrasjon).'

	def add_arguments(self, parser):
		parser.add_argument(
			'--file',
			required=True,
			help='Sti til OKA Excel-fil (xlsx).',
		)

	def handle(self, **options):
		path = options['file']
		if not os.path.isfile(path):
			raise CommandError('Fant ikke fil: %s' % path)
		result = import_oka_workbook(path, filename=os.path.basename(path))
		self.stdout.write(self.style.SUCCESS(result['message']))
