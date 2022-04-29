# Kartoteket

Source code for Oslo kommune's register for information about systems
also known as "system- og behandlingsoversikt" or "Kartoteket".

## Backend reqirements
Python3, Django2 and different modules in requirements.txt

Note the module python-ldap might be difficult to install on windows. It will fail automatic install. Precompiled at https://www.lfd.uci.edu/~gohlke/pythonlibs/#python-ldap.

Login in environment "dev" and "prod" is set up for OIDC asuming KeyCloak configured acording to Oslo kommunes AD-structure. The environment "test" is configured with django auth backend. Can be modified to suit needs.

(optional) SMTP-server for sending e-mail.

(optional) LDAP configuration to an active directory server for user-import and general queries.

## Frontend requirements (included)
jQuery https://jquery.com/

bootstrap https://getbootstrap.com/

tablesorter https://mottie.github.io/tablesorter/docs/

tableexport https://tableexport.v5.travismclarke.com/#tableexport

floatThead https://mkoryak.github.io/floatThead/

cytoscape https://cytoscape.org/

open-iconic https://useiconic.com/open



## Getting started 101 - Test or development
On Windows
* Download latest python from https://www.python.org/
* Install - would recommend install for current user (C:/Users/<user>/AppData/Local/Programs/Python) and remeber to check the option to set environment variabels. If you forget, they can be added later. You need both root and the /Scrips/ folders.
* open a command prompt window ("cmd")
* run: ```python```
* Make sure you get a python 3.x prompt. Exit with "quit()".
* run: ```pip3 install virtualenv``` --> install virtual environment, for package separation
* run: ```pip3 install virtualenvwrapper-win``` --> gives you a nice "workon" shortcut
* run: ```cd %HOMEPATH%``` --> move to your home directory
* run: ```virtualenv name``` --> e.g. kartoteket (check out https://medium.com/@jtpaasch/the-right-way-to-use-virtual-environments-1bc255a0cba7 for good practice regarding folder setup)
* run: ```workon name``` --> you will see the prompt change to "(name).." (in most cases)
* clone this repo (using git or git desktop) and move into the root of the "systemoversikt"-folder.
* Make sure you rename secrets.example.py to secrets.py and set a value to "KARTOTEKET_SECRET_KEY".
* Also rename "this_env.example.py" to "this_env.py".
* run: ```pip3 install -r requirements.txt```
* run: ```python manage.py makemigrations systemoversikt```
* run: ```python manage.py migrate```
* run: ```python manage.py createsuperuser``` --> enter username, no email and choose password
* run: ```python manage.py runserver```
* Open a browser and go to http://localhost:8000
* Login at http://localhost:8000/admin/
* Exit the virtual environment with ```deactivate``` (or close the terminal window)

On Linux
* Let's assume you know how to set up your environment if you're on a linux-variant.

## getting started production
In production, django is usually loaded as a module in httpd or webserver of choosing.
Remember to configure static path and run ```python manage.py collectstatic```.


## nice to know
The outer template folder is for customizing the django admin (part of the django installation). The inner is used troughout this webapplication.

LDAP-user synchronization can be set up using a script, and the script can be run regularly with e.g. cron

``` bash
#!/bin/sh
# enable virtual environment
source /<path>/bin/activate
# run batch job
python /<path>/manage.py ldap_paged
```

## handy commands
```
pip list --format=freeze > requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py get_all_permissions
```
