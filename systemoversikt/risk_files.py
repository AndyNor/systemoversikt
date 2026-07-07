# -*- coding: utf-8 -*-
# Change log:
# 2026-07-07: Omfang figur/original validation and DB byte helpers for risk collection uploads.

import mimetypes
import os

from django.core.exceptions import ValidationError

OMFANG_FIGUR_MAX_BYTES = 10 * 1024 * 1024
OMFANG_ORIGINAL_MAX_BYTES = 25 * 1024 * 1024

OMFANG_FIGUR_EXTENSIONS = frozenset({
	'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg',
})
OMFANG_ORIGINAL_EXTENSIONS = frozenset({
	'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg',
	'.pdf', '.vsdx', '.vsd', '.drawio', '.xml', '.pptx', '.ppt',
	'.docx', '.doc', '.xlsx', '.xls', '.zip',
})


def _extension(filename):
	return os.path.splitext((filename or '').lower())[1]


def guess_content_type(filename, fallback='application/octet-stream'):
	guessed, _encoding = mimetypes.guess_type(filename or '')
	return guessed or fallback


def _validate_upload(upload, allowed_extensions, max_bytes, label):
	if upload is None:
		raise ValidationError('Ingen fil valgt.')
	name = getattr(upload, 'name', '') or ''
	ext = _extension(name)
	if ext not in allowed_extensions:
		raise ValidationError(
			'Ugyldig filtype for %s (%s). Tillatte filendelser: %s'
			% (label, ext or '(mangler)', ', '.join(sorted(allowed_extensions))),
		)
	size = getattr(upload, 'size', None)
	if size is None:
		try:
			pos = upload.tell()
			upload.seek(0, os.SEEK_END)
			size = upload.tell()
			upload.seek(pos)
		except (OSError, AttributeError):
			size = None
	if size is not None and size > max_bytes:
		raise ValidationError(
			'%s er for stor (maks %d MB).' % (label, max_bytes // (1024 * 1024)),
		)


def validate_omfang_figur(upload):
	_validate_upload(upload, OMFANG_FIGUR_EXTENSIONS, OMFANG_FIGUR_MAX_BYTES, 'Visningsfigur')


def validate_omfang_original(upload):
	_validate_upload(upload, OMFANG_ORIGINAL_EXTENSIONS, OMFANG_ORIGINAL_MAX_BYTES, 'Originalfil')


def read_upload_bytes(upload, validator):
	validator(upload)
	data = upload.read()
	if not data:
		raise ValidationError('Filen er tom.')
	if len(data) > OMFANG_ORIGINAL_MAX_BYTES:
		raise ValidationError('Filen er for stor.')
	return data


def clear_figur_fields(omfang_fil):
	omfang_fil.figur_data = None
	omfang_fil.figur_content_type = ''
	omfang_fil.figur_filnavn = ''


def clear_original_fields(omfang_fil):
	omfang_fil.original_data = None
	omfang_fil.original_content_type = ''
	omfang_fil.original_filnavn = ''
