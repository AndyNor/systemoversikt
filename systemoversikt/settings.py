# -*- coding: utf-8 -*-
"""
Django settings for systemoversikt project.
Generated by 'django-admin startproject' using Django 1.11.15.
For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/
For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""
import os

from this_env import this_env
this_env()

THIS_ENVIRONMENT = os.environ['THIS_ENV'] # "PROD" / "TEST" / "DEV"

if THIS_ENVIRONMENT == "PROD":
	from secrets_prod import load_secrets
if THIS_ENVIRONMENT == "DEV":
	from secrets_dev import load_secrets
if THIS_ENVIRONMENT == "TEST":
	from secrets_test import load_secrets
load_secrets()


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ['KARTOTEKET_SECRET_KEY']

# SECURITY WARNING: don't run with debug turned on in production!
if THIS_ENVIRONMENT == "PROD":
	DEBUG = False
if THIS_ENVIRONMENT == "DEV":
	DEBUG = True
if THIS_ENVIRONMENT == "TEST":
	DEBUG = True

if THIS_ENVIRONMENT == "PROD":
	ALLOWED_HOSTS = ["10.134.162.204", "localhost", "kartoteket.oslo.kommune.no", "systemoversikt.oslo.kommune.no", "10.134.162.203"]
	#SECURE_SSL_REDIRECT = True  #I Oslo kommune er det en webproxy som redirecter http til https i produksjon
	TEST_ENV_NAME = "" # brukes ikke i produksjon
	SITE_SCHEME = "https"
	SITE_DOMAIN = "kartoteket.oslo.kommune.no"
	#SITE_PORT_OVERRIDE = ""  # start with ":", default empty ("")
if THIS_ENVIRONMENT == "DEV":
	ALLOWED_HOSTS = ["localhost",]
	SECURE_SSL_REDIRECT = False
	TEST_ENV_NAME = "development"
	SITE_SCHEME = "http"
	SITE_DOMAIN = "localhost"
	#SITE_PORT_OVERRIDE = ":8000"  # start with ":", default empty ("")
if THIS_ENVIRONMENT == "TEST":
	ALLOWED_HOSTS = ["10.134.162.204", "localhost", "localhost:8000", "kartoteket-test.oslo.kommune.no", "kartoteket.andynor.net"]
	SECURE_SSL_REDIRECT = False
	TEST_ENV_NAME = "test"
	SITE_SCHEME = "http"
	SITE_DOMAIN = "localhost:8000"
	#SITE_PORT_OVERRIDE = ""  # start with ":", default empty ("")

# Application definition
INSTALLED_APPS = [
	'django.contrib.admin',
	'django.contrib.auth',
	'django.contrib.contenttypes',
	'django.contrib.sessions',
	'django.contrib.messages',
	'django.contrib.staticfiles',
	'django.contrib.humanize',
	'mozilla_django_oidc',
	'systemoversikt',
	'rest_framework',
	'mailer',
	'simple_history',
	'widget_tweaks',
]
if THIS_ENVIRONMENT == "DEV":
	INSTALLED_APPS += [
		'debug_permissions',
		'django_extensions',
	]
if THIS_ENVIRONMENT == "TEST":
	INSTALLED_APPS += [
		'debug_permissions',
		'django_extensions',
	]

# django-mailer
EMAIL_BACKEND = "mailer.backend.DbBackend"


#overgang til django 4 har innført "BigAutoField"
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# django SMTP-settings
EMAIL_HOST_USER = os.environ['EMAIL_HOST_USER']
EMAIL_HOST_PASSWORD = os.environ['EMAIL_HOST_PASSWORD']
DEFAULT_FROM_EMAIL = "kartoteket@uke.oslo.kommune.no"
if THIS_ENVIRONMENT == "PROD":
	EMAIL_HOST = "indre-relay.oslo.kommune.no"
	EMAIL_PORT = 25
	EMAIL_USE_TLS = True
if THIS_ENVIRONMENT == "DEV":
	EMAIL_HOST = "localhost"
	EMAIL_PORT = 25
	EMAIL_USE_TLS = True
if THIS_ENVIRONMENT == "TEST":
	EMAIL_HOST = "localhost"
	EMAIL_PORT = 9999 # vi ønsker ikke at test skal sende ut mail
	EMAIL_USE_TLS = True


# django rest framework
REST_FRAMEWORK = {
	#'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
	#'PAGE_SIZE': 100,
	'DEFAULT_PERMISSION_CLASSES': (
		'rest_framework.permissions.DjangoModelPermissions',
	)
}

MIDDLEWARE = [
	'django.middleware.security.SecurityMiddleware',
	'django.contrib.sessions.middleware.SessionMiddleware',
	'django.middleware.common.CommonMiddleware',
	'django.middleware.csrf.CsrfViewMiddleware',
	'django.contrib.auth.middleware.AuthenticationMiddleware',
	'django.contrib.messages.middleware.MessageMiddleware',
	'django.middleware.clickjacking.XFrameOptionsMiddleware',
	'simple_history.middleware.HistoryRequestMiddleware',
	'csp.middleware.CSPMiddleware',
]

SESSION_ENGINE = "django.contrib.sessions.backends.db"
#SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# Security headers. CSP reqires "CSPMiddleware"
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-eval'") # numeric.js bruker desverre eval()
CSP_FRAME_SRC = ("'self'",)
CSP_IMG_SRC = ("'self' data:")
CSP_STYLE_SRC = ("'unsafe-inline'", "'self'")
CSP_INCLUDE_NONCE_IN = ['script-src']
SECURE_CONTENT_TYPE_NOSNIFF = True  # requires "SecurityMiddleware"

ROOT_URLCONF = 'systemoversikt.urls'

TEMPLATES = [
	{
		'BACKEND': 'django.template.backends.django.DjangoTemplates',
		'DIRS': [
		'templates',
		os.path.join(BASE_DIR, 'templates'),
	],
		'APP_DIRS': True,
		'OPTIONS': {
			'context_processors': [
				'django.template.context_processors.debug',
				'django.template.context_processors.request',
				'django.contrib.auth.context_processors.auth',
				'django.contrib.messages.context_processors.messages',
				'django.template.context_processors.request',
				'systemoversikt.context_processors.global_settings',
			],
		},
	},
]

WSGI_APPLICATION = 'systemoversikt.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases
DATABASES = {
	'default': {
		'ENGINE': 'django.db.backends.sqlite3',
		'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
	}
}

# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators
if THIS_ENVIRONMENT == "PROD":
	AUTH_PASSWORD_VALIDATORS = [
		{
			'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
		},
		{
			'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
		},
		{
			'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
		},
		{
			'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
		},
	]

# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/
LANGUAGE_CODE = 'nb'
TIME_ZONE = 'Europe/Oslo'
USE_I18N = True
USE_L10N = True
USE_TZ = True


#Authentication
if THIS_ENVIRONMENT == "PROD":
	AUTHENTICATION_BACKENDS = (
		'django.contrib.auth.backends.ModelBackend',  # trenger denne dersom SSO ikke er tilgjengelig
		'systemoversikt.oidc.CustomOIDCAuthenticationBackend',  # SSO / login.oslo.kommune.no
	)
	LOGIN_URL = "/oidc/authenticate/"
	LOGIN_REDIRECT_URL = "/"
	LOGOUT_REDIRECT_URL = "https://kartoteket.oslo.kommune.no"
	OIDC_IDP_URL_BASE = "https://login.oslo.kommune.no"
	OIDC_IDP_REALM = "AD"
	OIDC_RP_SCOPES = "openid email"
	OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 900
	OIDC_RP_SIGN_ALGO = "RS256"
	OIDC_OP_JWKS_ENDPOINT = OIDC_IDP_URL_BASE + "/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/certs"
	OIDC_RP_CLIENT_ID = "systemoversikt"
	OIDC_RP_CLIENT_SECRET = os.environ['KARTOTEKET_OIDC_RP_CLIENT_SECRET']
	OIDC_OP_AUTHORIZATION_ENDPOINT = "https://login.oslo.kommune.no/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/auth"
	OIDC_OP_TOKEN_ENDPOINT = OIDC_IDP_URL_BASE + "/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/token"
	OIDC_OP_USER_ENDPOINT = OIDC_IDP_URL_BASE + "/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/userinfo"
	OIDC_OP_LOGOUT_URL_METHOD = "systemoversikt.oidc.provider_logout"  # deaktiver denne for å skru av single logout
	SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') # fordi det er HTTP mellom BigIP og Kartoteket (slik at redirect_uri mot KeyCloak blir https)

if THIS_ENVIRONMENT == "DEV":
	AUTHENTICATION_BACKENDS = (
		'systemoversikt.oidc.CustomOIDCAuthenticationBackend',  # SSO / login.oslo.kommune.no
		'django.contrib.auth.backends.ModelBackend',  # trenger denne dersom SSO ikke er tilgjengelig
	)
	LOGIN_URL = "/oidc/authenticate/"
	LOGIN_REDIRECT_URL = "/"
	LOGOUT_REDIRECT_URL = "http://localhost:8000"
	OIDC_IDP_URL_BASE = "http://localhost:8080"
	OIDC_IDP_REALM = "behandlingsoversikt"
	OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 900
	OIDC_RP_SIGN_ALGO = "RS256"
	OIDC_OP_JWKS_ENDPOINT = OIDC_IDP_URL_BASE + "/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/certs"
	OIDC_RP_CLIENT_ID = "sbo"
	OIDC_RP_CLIENT_SECRET = os.environ['KARTOTEKET_OIDC_RP_CLIENT_SECRET']
	OIDC_OP_AUTHORIZATION_ENDPOINT = OIDC_IDP_URL_BASE + "/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/auth"
	OIDC_OP_TOKEN_ENDPOINT = OIDC_IDP_URL_BASE + "/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/token"
	OIDC_OP_USER_ENDPOINT = OIDC_IDP_URL_BASE + "/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/userinfo"
	OIDC_OP_LOGOUT_URL_METHOD = "systemoversikt.oidc.provider_logout"  # deaktiver denne for å skru av single logout

if THIS_ENVIRONMENT == "TEST":
	AUTHENTICATION_BACKENDS = (
		'systemoversikt.oidc.CustomOIDCAuthenticationBackend',  # Azure AD
		'django.contrib.auth.backends.ModelBackend',  # trenger denne dersom SSO ikke er tilgjengelig
	)
	LOGIN_URL = "/oidc/authenticate/"
	LOGIN_REDIRECT_URL = "/?login=ok"
	LOGIN_REDIRECT_URL_FAILURE = "/?login=failed"
	LOGOUT_REDIRECT_URL = "/"
	OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 900
	OIDC_RP_SIGN_ALGO = "RS256"
	OIDC_RP_SCOPES = "openid profile"
	OIDC_IDP_URL_BASE = ""
	OIDC_IDP_REALM = ""
	OIDC_OP_JWKS_ENDPOINT = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
	OIDC_RP_CLIENT_ID = os.environ['AZURE_ENTERPRISEAPP_CLIENT']
	OIDC_RP_CLIENT_SECRET = os.environ['AZURE_ENTERPRISEAPP_SECRET']
	OIDC_OP_AUTHORIZATION_ENDPOINT = "https://login.microsoftonline.com/"+os.environ['AZURE_TENANT_ID']+"/oauth2/v2.0/authorize"
	OIDC_OP_TOKEN_ENDPOINT = "https://login.microsoftonline.com/"+os.environ['AZURE_TENANT_ID']+"/oauth2/v2.0/token"
	OIDC_OP_USER_ENDPOINT = "https://graph.microsoft.com/oidc/userinfo"
	OIDC_MAX_STATES = 5
	OIDC_CREATE_USER = False
	OIDC_STORE_ACCESS_TOKEN = False
	OIDC_STORE_ID_TOKEN = False
	#OIDC_OP_LOGOUT_URL_METHOD = "https://login.microsoftonline.com/"+os.environ['AZURE_TENANT_ID']+"/oauth2/v2.0/logout"


#session security
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
#CSRF_FAILURE_VIEW = "systemoversikt.views.csrf403"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax" # må endre fra strict grunnet at Firefox og Edge dropper session cookie dersom initiert fra andre domener
SESSION_COOKIE_AGE = 57600  # 10 timer
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

SECURE_BROWSER_XSS_FILTER = True

if THIS_ENVIRONMENT == "PROD":
	SESSION_COOKIE_SECURE = True
	CSRF_COOKIE_SECURE = True
	SECURE_HSTS_SECONDS = 31536000
if THIS_ENVIRONMENT == "DEV":
	SESSION_COOKIE_SECURE = False
	CSRF_COOKIE_SECURE = False
if THIS_ENVIRONMENT == "TEST":
	SESSION_COOKIE_SECURE = False
	CSRF_COOKIE_SECURE = False



MIDDLEWARE_CLASSES = [
	# middleware involving session and authentication must come first
	'mozilla_django_oidc.middleware.SessionRefresh',
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/
STATIC_URL = '/static/'
STATIC_DIRS = [os.path.join(BASE_DIR, 'statics'),]
STATIC_ROOT = os.path.join(BASE_DIR, "static/")

DATA_UPLOAD_MAX_NUMBER_FIELDS = 20480


LOGGING = {
	'version': 1,
	'disable_existing_loggers': False,
	'handlers': {
		'console': {
			'class': 'logging.StreamHandler',
		},
	},
	'loggers': {
		'django': {
			'handlers': ['console'],
			'level': 'WARNING',
		},
		'mozilla_django_oidc': {
			'handlers': ['console'],
			'level': 'DEBUG'
		},
	},
}

