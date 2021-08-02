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
	from secrets import load_secrets
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
	#SECURE_SSL_REDIRECT = True  #I Oslo kommune er det en webproxy som redirecter http til https i produksjon
	TEST_ENV_NAME = "" # brukes ikke i produksjon
	SITE_SCHEME = "https"
	SITE_DOMAIN = "kartoteket.oslo.kommune.no"
	SITE_PORT_OVERRIDE = ""  # start with ":", default empty ("")
	#SITE_URL = SITE_SCHEME + "://" + SITE_DOMAIN + SITE_PORT_OVERRIDE
	ALLOWED_HOSTS = ["localhost", "kartoteket.oslo.kommune.no", "systemoversikt.oslo.kommune.no", "10.134.162.203"]
if THIS_ENVIRONMENT == "DEV":
	SECURE_SSL_REDIRECT = False
	TEST_ENV_NAME = "development"
	SITE_SCHEME = "http"
	SITE_DOMAIN = "localhost"
	SITE_PORT_OVERRIDE = ":8000"  # start with ":", default empty ("")
	#SITE_URL = SITE_SCHEME + "://" + SITE_DOMAIN + SITE_PORT_OVERRIDE
	ALLOWED_HOSTS = ["localhost", SITE_DOMAIN, "kartoteket.andynor.net"]
if THIS_ENVIRONMENT == "TEST":
	TEST_ENV_NAME = "test"
	SITE_SCHEME = "http"
	SITE_DOMAIN = "localhost:8000"
	SITE_PORT_OVERRIDE = ""  # start with ":", default empty ("")
	#SITE_URL = SITE_SCHEME + "://" + SITE_DOMAIN + SITE_PORT_OVERRIDE
	ALLOWED_HOSTS = ["localhost", SITE_DOMAIN, "kartoteket-test.oslo.kommune.no", "kartoteket.andynor.net"]

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
	'systemoversikt.restapi',
	'simple_history',
	'mailer',
	'widget_tweaks'
]
if THIS_ENVIRONMENT == "DEV":
	INSTALLED_APPS += [
		'debug_permissions',
		'django_extensions',
	]

# django-mailer
EMAIL_BACKEND = "mailer.backend.DbBackend"


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

# Security headers
# CSP reqires "CSPMiddleware"
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
		'systemoversikt.oidc.CustomOIDCAuthenticationBackend',  # SSO / login.oslo.kommune.no
		'django.contrib.auth.backends.ModelBackend',  # trenger denne dersom SSO ikke er tilgjengelig
	)
if THIS_ENVIRONMENT == "DEV":
	AUTHENTICATION_BACKENDS = (
		'systemoversikt.oidc.CustomOIDCAuthenticationBackend',  # SSO / login.oslo.kommune.no
		'django.contrib.auth.backends.ModelBackend',  # trenger denne dersom SSO ikke er tilgjengelig
	)
if THIS_ENVIRONMENT == "TEST":
	AUTHENTICATION_BACKENDS = (
		#'systemoversikt.oidc.CustomOIDCAuthenticationBackend',  # ikke satt opp for test
		'django.contrib.auth.backends.ModelBackend',  # trenger denne dersom SSO ikke er tilgjengelig
	)

OIDC_RP_CLIENT_SECRET = os.environ['KARTOTEKET_OIDC_RP_CLIENT_SECRET']
if THIS_ENVIRONMENT == "PROD":
	LOGIN_URL = "/oidc/authenticate/"
	LOGIN_REDIRECT_URL = "/"
	OIDC_IDP_URL_BASE = "https://login.oslo.kommune.no"
	OIDC_IDP_REALM = "AD"
	OIDC_RP_SCOPES = "openid email"
	OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 900
	OIDC_RP_SIGN_ALGO = "RS256"
	OIDC_OP_JWKS_ENDPOINT = OIDC_IDP_URL_BASE + "/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/certs"
	OIDC_RP_CLIENT_ID = "systemoversikt"
	OIDC_OP_AUTHORIZATION_ENDPOINT = "https://login.oslo.kommune.no/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/auth"
	OIDC_OP_TOKEN_ENDPOINT = OIDC_IDP_URL_BASE + "/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/token"
	OIDC_OP_USER_ENDPOINT = OIDC_IDP_URL_BASE + "/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/userinfo"
	OIDC_OP_LOGOUT_URL_METHOD = "systemoversikt.oidc.provider_logout"  # deaktiver denne for å skru av single logout
	LOGOUT_REDIRECT_URL = "https://kartoteket.oslo.kommune.no"
	SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') # fordi det er HTTP mellom BigIP og Kartoteket (slik at redirect_uri mot KeyCloak blir https)
	#LOGOUT_REDIRECT_URL = SITE_URL + "/"
if THIS_ENVIRONMENT == "DEV":
	LOGIN_URL = "/oidc/authenticate/"
	LOGIN_REDIRECT_URL = "/"
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
	LOGOUT_REDIRECT_URL = "http://localhost:8000"
if THIS_ENVIRONMENT == "TEST":
	LOGIN_URL = "/login/"
	LOGIN_REDIRECT_URL = "/"
	LOGOUT_REDIRECT_URL = "/"
	OIDC_IDP_URL_BASE = None  # kreves av context_processors.py
	OIDC_IDP_REALM = None  # kreves av context_processors.py


#session security
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
#CSRF_FAILURE_VIEW = "systemoversikt.views.csrf403"
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_AGE = 36000  # 10 timer
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
if THIS_ENVIRONMENT == "PROD":
	SESSION_COOKIE_SECURE = True
	CSRF_COOKIE_SECURE = True
	SECURE_HSTS_SECONDS = 31536000
if THIS_ENVIRONMENT == "DEV":
	SESSION_COOKIE_SECURE = False
	CSRF_COOKIE_SECURE = False
	#SECURE_HSTS_SECONDS = 31536000



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

"""
log_file = os.path.join(BASE_DIR, 'django.log')
LOGGING = {
	'version': 1,
	'disable_existing_loggers': False,
	'handlers': {
		'file': {
			'level': 'DEBUG',
			'class': 'logging.FileHandler',
			'filename': log_file,
		},
	},
	'loggers': {
		#'django': {
		#	'handlers': ['file'],
		#	'level': 'DEBUG',
		#	'propagate': True,
		#},
		'mozilla_django_oidc': {
			'handlers': ['file'],
			'level': 'DEBUG'
		},
	},
}
"""