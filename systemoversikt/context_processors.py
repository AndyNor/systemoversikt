# -*- coding: utf-8 -*-
# Change log:
# 2026-11-01: forvalter_secret_alert persists in session until dismiss (not one-shot with welcome).
# 2026-11-01: login_welcome also returns forvalter_secret_alert (expired/soon Azure keys, one-shot).
# 2026-11-01: Removed OIDC_IDP_URL_BASE/REALM from template context (Keycloak leftovers).
# 2026-11-01: login_welcome – one-shot post-login summary box (replaces per-role flash messages).
from django.conf import settings

KARTOTEK_SECRET_EXPIRY_ALERT_SESSION_KEY = 'kartotek_secret_expiry_alert'


def global_settings(request):
	# return only necessary values
	return {
		'DEBUG': settings.DEBUG,
		'TEST_ENV_NAME': settings.TEST_ENV_NAME,

	}


from .models import IntegrasjonKonfigurasjon
SUCCESS = "Vellykket"
def all_integrations_ok():
    return not IntegrasjonKonfigurasjon.objects.exclude(
        helsestatus=SUCCESS
    ).exists()


def integration_health(request):
    return {
        "integrations_ok": all_integrations_ok(),
    }


def _forvalter_secret_alert_from_session(request):
	# 2026-11-01: True = pending compute; list = cached rows; absent = dismissed / not set.
	val = request.session.get(KARTOTEK_SECRET_EXPIRY_ALERT_SESSION_KEY)
	if val is None:
		return None
	if val is True:
		from systemoversikt.views import build_forvalter_secret_expiry_alert
		alerts = build_forvalter_secret_expiry_alert(request.user)
		if not alerts:
			request.session.pop(KARTOTEK_SECRET_EXPIRY_ALERT_SESSION_KEY, None)
			return None
		payload = [
			{
				'pk': row['system'].pk,
				'systemnavn': row['system'].systemnavn,
				'expired': row['expired'],
				'soon': row['soon'],
			}
			for row in alerts
		]
		request.session[KARTOTEK_SECRET_EXPIRY_ALERT_SESSION_KEY] = payload
		return payload
	if isinstance(val, list) and val:
		return val
	request.session.pop(KARTOTEK_SECRET_EXPIRY_ALERT_SESSION_KEY, None)
	return None


def login_welcome(request):
	# 2026-11-01: Show compact login summary once after OIDC callback (or /?login=ok).
	# 2026-11-01: Secret-expiry alert is separate – stays until user dismisses via X.
	empty = {'login_welcome': None, 'forvalter_secret_alert': None}
	if not getattr(request, 'user', None) or not request.user.is_authenticated:
		return empty

	show_welcome = False
	if request.session.pop('kartotek_login_welcome', False):
		show_welcome = True
	elif request.GET.get('login') == 'ok':
		show_welcome = True
		# 2026-11-01: Enable pending secret alert when landing via ?login=ok without OIDC session flag.
		if KARTOTEK_SECRET_EXPIRY_ALERT_SESSION_KEY not in request.session:
			request.session[KARTOTEK_SECRET_EXPIRY_ALERT_SESSION_KEY] = True

	login_welcome_data = None
	if show_welcome:
		from systemoversikt.views import build_login_welcome_summary
		login_welcome_data = build_login_welcome_summary(request.user)

	return {
		'login_welcome': login_welcome_data,
		'forvalter_secret_alert': _forvalter_secret_alert_from_session(request),
	}

