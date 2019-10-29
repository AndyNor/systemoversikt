# -*- coding: utf-8 -*-
"""
Django settings for systemoversikt project.
Generated by 'django-admin startproject' using Django 1.11.15.
For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/
For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""

from secrets import load_secrets
load_secrets()

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ['KARTOTEKET_SECRET_KEY']

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
TEST_ENV_NAME = "" # brukes ikke i produksjon
SITE_SCHEME = "https"
SITE_DOMAIN = "systemoversikt.oslo.kommune.no"
SITE_PORT_OVERRIDE = ""  # start with ":", default empty ("")
SITE_URL = SITE_SCHEME + "://" + SITE_DOMAIN + SITE_PORT_OVERRIDE
ALLOWED_HOSTS = ["localhost", "kartoteket.oslo.kommune.no", "systemoversikt.oslo.kommune.no", "10.134.162.203"]

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
]

# django-mailer
EMAIL_BACKEND = "mailer.backend.DbBackend"


# django SMTP-settings
EMAIL_HOST = "indre-relay.oslo.kommune.no"
EMAIL_PORT = 25
EMAIL_HOST_USER = os.environ['EMAIL_HOST_USER']
EMAIL_HOST_PASSWORD = os.environ['EMAIL_HOST_PASSWORD']
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = "kartoteket@uke.oslo.kommune.no"


REST_FRAMEWORK = {
    #'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    #'PAGE_SIZE': 100,
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly',
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
]

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
                'django.template.context_processors.request', # kreves for templatetags (brukes av meny for å sette class="active")
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

AUTHENTICATION_BACKENDS = (
    'systemoversikt.oidc.CustomOIDCAuthenticationBackend',  # SSO / login.oslo.kommune.no
    'django.contrib.auth.backends.ModelBackend',  # trenger denne dersom SSO ikke er tilgjengelig
)
OIDC_IDP_URL_BASE = "https://login.oslo.kommune.no"
OIDC_IDP_REALM = "AD"
OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 900
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_OP_JWKS_ENDPOINT = OIDC_IDP_URL_BASE + "/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/certs"
os.environ["OIDC_RP_CLIENT_ID"] = "systemoversikt"
OIDC_RP_CLIENT_ID = os.environ['OIDC_RP_CLIENT_ID']
OIDC_RP_CLIENT_SECRET = os.environ['KARTOTEKET_OIDC_RP_CLIENT_SECRET']
OIDC_OP_AUTHORIZATION_ENDPOINT = "https://login.oslo.kommune.no/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/auth"
OIDC_OP_TOKEN_ENDPOINT = OIDC_IDP_URL_BASE + "/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/token"
OIDC_OP_USER_ENDPOINT = OIDC_IDP_URL_BASE + "/auth/realms/"+OIDC_IDP_REALM+"/protocol/openid-connect/userinfo"
OIDC_OP_LOGOUT_URL_METHOD = "systemoversikt.oidc.provider_logout"  # deaktiver denne for å skru av single logout
LOGIN_URL = "/oidc/authenticate/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = SITE_URL + "/"
CSRF_COOKIE_HTTPONLY = True
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_AGE = 36000  # 10 timer
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
CSRF_FAILURE_VIEW = "systemoversikt.views.csrf403"

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
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format' : "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            'datefmt' : "%d/%b/%Y %H:%M:%S"
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': '/home/drift23914/metadata/kartotek_django_warn.log',
            'when': 'D', # this specifies the interval
            'interval': 1, # defaults to 1, only necessary for other values
            'backupCount': 10, # how many backup file to keep, 10 days
            'formatter': 'verbose',
        },

    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
        },
    },
}
"""
