# -*- coding: utf-8 -*-
# Change log:
# 2026-06-21: Single e-mail with all recipients in To; CSIRT once on Cc.
# 2026-06-21: Live e-mail sending enabled (dry-run off).
# 2026-06-21: Include sender name in varsling e-mail footer.
# 2026-06-21: Full ApplicationLog audit entry for each varsling (user, recipients, title, body).
# 2026-06-21: Dry-run mode – preview planned mail without sending until explicitly enabled.

import os

from django.conf import settings
from django.core.mail import EmailMessage, get_connection

SIKKERHETSANALYTIKER_GROUP = '/DS-SYSTEMOVERSIKT_SAARBARHETSOVERSIKT_SIKKERHETSANALYTIKER'

# Set to False when live sending is approved.
CSIRT_VARSLING_DRY_RUN = False


def csirt_email_address():
	"""Sender and CC address for CSIRT outbound mail (from environment)."""
	return os.environ['CSIRT_EMAIL_ADDR'].strip()


def user_is_sikkerhetsanalytiker(user):
	return user.groups.filter(name=SIKKERHETSANALYTIKER_GROUP).exists()


def _ansvarlig_email(ansvarlig):
	user = ansvarlig.brukernavn
	if not user.is_active:
		return None
	profile = getattr(user, 'profile', None)
	if profile is not None and profile.accountdisable:
		return None
	email = (user.email or '').strip()
	return email or None


def security_contact_emails_for_virksomhet(virksomhet):
	"""
	Resolve notification recipients: security mailboxes, then ISK, then IKT-hovedkontakt.
	Returns (emails, source_label). source_label is empty when no contacts found.
	"""
	role_fields = (
		('varslingsmottak_sikkerhet_ref', 'Sikkerhetsvarsler'),
		('informasjonssikkerhetskoordinator', 'ISK'),
		('ikt_kontakt', 'IKT-hovedkontakt'),
	)
	for field_name, source_label in role_fields:
		emails = []
		for ansvarlig in getattr(virksomhet, field_name).all():
			email = _ansvarlig_email(ansvarlig)
			if email:
				emails.append(email)
		if emails:
			return _dedupe_preserve_order(emails), source_label
	return [], ''


def append_varsling_footer(body, sender):
	"""Append Kartoteket attribution and sender to outbound message body."""
	return (
		f"{body.rstrip()}\n\n"
		f"---\n"
		f"Meldingen ble sendt fra Kartoteket.\n"
		f"Sendt av: {sender}"
	)


def log_csirt_varsling_to_application_log(username, subject, body, delivery_preview, dry_run=False):
	"""Write full varsling details to ApplicationLog (shown at /admin/logger/audit/)."""
	from systemoversikt.models import ApplicationLog

	lines = [
		f'Tørrkjøring av {username}' if dry_run else f'Sendt av {username}',
		f'Tittel: {subject}',
		f"Til ({len(delivery_preview['all_to'])} mottakere): {', '.join(delivery_preview['all_to'])}",
		'Mottakere per virksomhet:',
	]
	for item in delivery_preview['messages']:
		vir = item['virksomhet']
		lines.append(
			f"  {vir.virksomhetsforkortelse} – {vir.virksomhetsnavn}: "
			f"{', '.join(item['to'])} ({item['source']})"
		)
	if delivery_preview['skipped']:
		lines.append('Uten mottakere:')
		for vir in delivery_preview['skipped']:
			lines.append(f"  {vir.virksomhetsforkortelse} – {vir.virksomhetsnavn}")
	lines.append('Melding:')
	lines.append(body)

	ApplicationLog.objects.create(
		event_type='csirt_varsling_virksomheter',
		message='\n'.join(lines),
	)


def _dedupe_preserve_order(emails):
	seen = set()
	unique = []
	for email in emails:
		key = email.lower()
		if key in seen:
			continue
		seen.add(key)
		unique.append(email)
	return unique


def plan_security_alert_to_virksomheter(virksomheter, subject, body):
	"""Build mail plan: one message, all recipients combined in To. Used for preview and send."""
	try:
		csirt_addr = csirt_email_address()
	except KeyError:
		csirt_addr = None

	planned_messages = []
	skipped = []
	all_to = []
	for virksomhet in virksomheter:
		recipients, source = security_contact_emails_for_virksomhet(virksomhet)
		if not recipients:
			skipped.append(virksomhet)
			continue
		planned_messages.append({
			'virksomhet': virksomhet,
			'to': recipients,
			'source': source,
		})
		all_to.extend(recipients)

	all_to = _dedupe_preserve_order(all_to)

	return {
		'from_email': csirt_addr,
		'cc': [csirt_addr] if csirt_addr else [],
		'subject': subject,
		'body': body,
		'all_to': all_to,
		'messages': planned_messages,
		'skipped': skipped,
		'mail_count': 1 if all_to else 0,
		'recipient_total': len(all_to),
	}


def send_immediate_csirt_email(subject, body, to, cc=None):
	"""Send immediately via MAILER_EMAIL_BACKEND, bypassing django-mailer queue."""
	backend = getattr(
		settings,
		'MAILER_EMAIL_BACKEND',
		'django.core.mail.backends.smtp.EmailBackend',
	)
	connection = get_connection(backend=backend)
	from_email = csirt_email_address()
	email = EmailMessage(
		subject=subject,
		body=body,
		from_email=from_email,
		to=to,
		cc=cc or [],
		connection=connection,
	)
	email.send()
	return len(to) + len(cc or [])


def send_security_alert_to_virksomheter(virksomheter, subject, body):
	"""
	Send one immediate e-mail with all security contacts in To and CSIRT on Cc.
	Returns skipped virksomheter (no contacts). Raises if no recipients or dry-run.
	"""
	if CSIRT_VARSLING_DRY_RUN:
		raise RuntimeError('CSIRT varsling is in dry-run mode; use plan_security_alert_to_virksomheter().')

	delivery_plan = plan_security_alert_to_virksomheter(virksomheter, subject, body)
	if not delivery_plan['all_to']:
		raise ValueError('Ingen mottakere med gyldig e-postadresse blant valgte virksomheter.')

	csirt_addr = csirt_email_address()
	send_immediate_csirt_email(
		subject=subject,
		body=body,
		to=delivery_plan['all_to'],
		cc=[csirt_addr],
	)
	return delivery_plan['skipped']
