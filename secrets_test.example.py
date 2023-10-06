# -*- coding: utf-8 -*-

SECRET_ALLOWED_HOSTS = []
def load_secrets():
	import os
	os.environ["KARTOTEKET_SECRET_KEY"] = '' # generate a django secret and put it here
	#os.environ["KARTOTEKET_OIDC_RP_CLIENT_SECRET"] = ""

	os.environ['KARTOTEKET_LDAPUSER'] = ''
	os.environ['KARTOTEKET_LDAPPASSWORD'] = ''
	os.environ["KARTOTEKET_LDAPSERVER"] = ''
	os.environ["KARTOTEKET_LDAPROOT"] = ''

	os.environ['EMAIL_HOST_USER'] = ''
	os.environ['EMAIL_HOST_PASSWORD'] = ''

	os.environ['PRK_FORM_APIKEY'] = ''
	os.environ['PRK_FORM_URL'] = ''
	os.environ['PRK_USERS_URL'] = ''
	os.environ['PRK_ORG_URL'] = ''

	os.environ['AZUREAD_USER'] = ''
	os.environ['AZUREAD_PASSWORD'] = ''

	os.environ['SHAREPOINT_CLIENT_ID'] = ""
	os.environ['SHAREPOINT_CLIENT_SECRET'] = ""
	os.environ['SHAREPOINT_SITE'] = ""

	os.environ['AZURE_TENANT_ID'] = ""
	os.environ['AZURE_ENTERPRISEAPP_CLIENT'] = ""
	os.environ['AZURE_ENTERPRISEAPP_SECRET'] = ""

	os.environ['PROXY_HTTPS'] = ""

	os.environ['AZURE_AUTH_SECRET'] = ""
	os.environ['AZURE_AUTH_CLIENT'] = ""

	os.environ['PUSHOVER_USER_KEY'] = ""
	os.environ['PUSHOVER_APP_TOKEN'] = ""