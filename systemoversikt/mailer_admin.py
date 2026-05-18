# -*- coding: utf-8 -*-
from django.contrib import admin
from mailer.admin import MessageLogAdmin as BaseMessageLogAdmin
from mailer.models import MessageLog


def _email_addresses_match(email, term):
	if email is None:
		return False
	addresses = []
	addresses.extend(getattr(email, 'to', None) or [])
	addresses.extend(getattr(email, 'cc', None) or [])
	addresses.extend(getattr(email, 'bcc', None) or [])
	return any(term in (address or '').lower() for address in addresses)


class MessageLogAdmin(BaseMessageLogAdmin):
	search_fields = ['message_id', 'log_message']

	def get_search_results(self, request, queryset, search_term):
		filtered_qs, use_distinct = super().get_search_results(
			request, queryset, search_term,
		)
		term = (search_term or '').strip().lower()
		if not term:
			return filtered_qs, use_distinct

		extra_pks = []
		for log in queryset.only('pk', 'message_data').iterator(chunk_size=200):
			if _email_addresses_match(log.email, term):
				extra_pks.append(log.pk)

		if extra_pks:
			filtered_qs = filtered_qs | queryset.filter(pk__in=extra_pks)
			use_distinct = True

		return filtered_qs, use_distinct


admin.site.unregister(MessageLog)
admin.site.register(MessageLog, MessageLogAdmin)
