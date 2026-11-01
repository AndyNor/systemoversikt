# -*- coding: utf-8 -*-
# Change log:
# 2026-11-01: Removed OIDC_IDP_URL_BASE/REALM from template context (Keycloak leftovers).
# 2026-11-01: login_welcome – one-shot post-login summary box (replaces per-role flash messages).
from django.conf import settings

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


def login_welcome(request):
	# 2026-11-01: Show compact login summary once after OIDC callback (or /?login=ok).
	if not getattr(request, 'user', None) or not request.user.is_authenticated:
		return {'login_welcome': None}
	show = False
	if request.session.pop('kartotek_login_welcome', False):
		show = True
	elif request.GET.get('login') == 'ok':
		show = True
	if not show:
		return {'login_welcome': None}
	from systemoversikt.views import build_login_welcome_summary
	return {'login_welcome': build_login_welcome_summary(request.user)}

