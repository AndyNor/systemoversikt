# systemoversikt

Kodebasen til Oslo kommunes system- og behandlingsoversikt "Kartoteket".

# reqirements
Python3, Django2.1 and different modules in requirements.txt

Login using OIDC (KeyCloak is configured).

SMTP-server for sending e-mail.

LDAP to active directory for user-import and queries.

# getting started
manage.py must point to the correct systemoversikt/settings.py (_dev and _test if not production).

settings.py points to secrets.py (or _dev or _test) with passwords loaded as environment variable at runtime.

In production, django is loaded as a module in httpd/redhat. Remember to configure static path and run "python manage.py collectstatic".

In dev one can run with "python manage.py runserver <0.0.0.0:8000>" and static files are handled by the test-server.

