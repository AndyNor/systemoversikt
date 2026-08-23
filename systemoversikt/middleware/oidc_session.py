# -*- coding: utf-8 -*-
# Change log:
# 2026-08-23: If oidc_id_token_expiration is missing, seed it so SessionRefresh does not
#             treat the session as expired and force prompt=none (which can log users out).
"""Middleware helpers for OIDC session behaviour."""
import time

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class EnsureOIDCTokenExpirationMiddleware(MiddlewareMixin):
	"""
	SessionRefresh defaults missing oidc_id_token_expiration to 0 and then forces a
	silent re-auth. Seed a fresh expiry for authenticated users so deep-link logins are
	not immediately bounced through prompt=none.
	"""

	def process_request(self, request):
		if not getattr(request, "user", None) or not request.user.is_authenticated:
			return None
		if not hasattr(request, "session"):
			return None
		if "oidc_id_token_expiration" in request.session:
			return None
		renew_seconds = getattr(settings, "OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS", 60 * 15)
		request.session["oidc_id_token_expiration"] = time.time() + renew_seconds
		return None
