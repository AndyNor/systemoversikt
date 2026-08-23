# -*- coding: utf-8 -*-
# Change log:
# 2026-08-23: Auto-start OIDC for anonymous users on home/access-denied; restore next on failure.
"""Helpers for automatic OIDC login with anonymous fallback after a failed attempt."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

SESSION_AUTO_ATTEMPTED = "kartotek_oidc_auto_attempted"
SESSION_NEXT = "kartotek_oidc_next"


def clear_auto_oidc_session_flags(request):
	"""Clear auto-login bookkeeping after a successful OIDC login."""
	request.session.pop(SESSION_AUTO_ATTEMPTED, None)
	request.session.pop(SESSION_NEXT, None)


def should_attempt_auto_oidc(request):
	"""True when we should redirect an anonymous user into OIDC once per session."""
	if request.user.is_authenticated:
		return False
	if request.method != "GET":
		return False
	if request.path.startswith("/oidc/"):
		return False
	if request.path.startswith("/oidc-login-failed"):
		return False
	if request.GET.get("login") == "failed":
		return False
	if request.session.get(SESSION_AUTO_ATTEMPTED):
		return False
	return True


def redirect_to_oidc_login(request, next_path=None):
	"""
	Start OIDC authenticate, remembering next for success (via mozilla) and failure restore.
	"""
	if next_path is None:
		next_path = request.get_full_path()
	request.session[SESSION_AUTO_ATTEMPTED] = True
	request.session[SESSION_NEXT] = next_path
	oidc_url = reverse("oidc_authentication_init")
	return redirect("%s?%s" % (oidc_url, urlencode({"next": next_path})))


def maybe_redirect_anonymous_to_oidc(request):
	"""Return an OIDC redirect response if auto-login should run, else None."""
	if should_attempt_auto_oidc(request):
		return redirect_to_oidc_login(request)
	return None


def render_access_denied(request, required_permissions):
	"""
	For anonymous users who have not yet tried OIDC: redirect to login.
	Otherwise render the standard 403 page (authenticated missing perms, or after failed auto-login).
	"""
	oidc_redirect = maybe_redirect_anonymous_to_oidc(request)
	if oidc_redirect is not None:
		return oidc_redirect
	return render(
		request,
		"403.html",
		{
			"required_permissions": required_permissions,
			"groups": request.user.groups,
		},
	)


def _append_login_failed(path):
	"""Append login=failed to a relative path without dropping other query params."""
	parts = urlsplit(path)
	query = dict(parse_qsl(parts.query, keep_blank_values=True))
	query["login"] = "failed"
	return urlunsplit(("", "", parts.path or "/", urlencode(query), parts.fragment))


def oidc_login_failure(request):
	"""
	LOGIN_REDIRECT_URL_FAILURE target: send anonymous user back to the original URL.
	Keeps SESSION_AUTO_ATTEMPTED so we do not loop into OIDC again.
	"""
	# 2026-08-23: Restore deep-link after OIDC failure instead of always landing on "/?login=failed".
	next_path = request.session.get(SESSION_NEXT) or "/"
	if not url_has_allowed_host_and_scheme(
		next_path,
		allowed_hosts={request.get_host()},
		require_https=request.is_secure(),
	):
		next_path = "/"
	return HttpResponseRedirect(_append_login_failed(next_path))
