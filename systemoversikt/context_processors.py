from django.conf import settings

def global_settings(request):
	# return only necessary values
	return {
		'OIDC_IDP_URL_BASE': settings.OIDC_IDP_URL_BASE,
		'OIDC_IDP_REALM': settings.OIDC_IDP_REALM,
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
    
