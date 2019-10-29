# -*- coding: utf-8 -*-
def load_secrets():
	import os
	os.environ["KARTOTEKET_SECRET_KEY"] = '' # generate a django secret and put it here
	os.environ["KARTOTEKET_OIDC_RP_CLIENT_SECRET"] = ""  # from keycloak
	os.environ["KARTOTEKET_LDAPUSER"] = 'domain\\user' # from active directory
	os.environ["KARTOTEKET_LDAPPASSWORD"] = ''
	os.environ["EMAIL_HOST_USER"] = ''
	os.environ["EMAIL_HOST_PASSWORD"] = ''