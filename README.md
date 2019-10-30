# systemoversikt

The code for Oslo kommune "system- og behandlingsoversikt" / "Kartoteket".

## backend reqirements
Python3, Django2 and different modules in requirements.txt

Note the module python-ldap might be difficult to install on windows. Precompiled at https://www.lfd.uci.edu/~gohlke/pythonlibs/#python-ldap.

Login using OIDC (KeyCloak is configured and configured acording to Oslo kommunes AD-structure).

SMTP-server for sending e-mail.

LDAP to active directory for user-import and queries.

## frontend requirements
jQuery https://jquery.com/

bootstrap https://getbootstrap.com/

tablesorter https://mottie.github.io/tablesorter/docs/

tableexport https://tableexport.v5.travismclarke.com/#tableexport

floatThead https://mkoryak.github.io/floatThead/

cytoscape https://cytoscape.org/

open-iconic https://useiconic.com/open



## getting started development
manage.py must point to the correct systemoversikt/settings.py (_dev and _test if not production).

settings.py points to secrets.py (or _dev or _test) with passwords loaded as environment variable at runtime.

In local development one can run with ```python manage.py runserver <0.0.0.0:8000>``` which will handle static files automatically.

## getting started production
TODO
In production, django is usually loaded as a module in httpd. Remember to configure static path and run ```python manage.py collectstatic```.


## nice to know
The outer template folder is for customizing the django admin (part of the django installation). The inner is used troughout this webapplication.

TODO: setting up python, virtualenv, 

TODO: Setting up the database and a root-user
python manage.py createsuperuser --username=root

TODO: setting up scheduled tasks
LDAP-user synchronization can be set up using a script

``` bash
#!/bin/sh
# enable virtual environment
source /<path>/bin/activate
# run batch job
python /<path>/manage.py ldap_paged
```

## handy commands
```
pip freeze > requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py get_all_permissions
```
