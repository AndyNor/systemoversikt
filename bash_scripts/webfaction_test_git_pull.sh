#!/bin/sh
# move to correct folder
cd ~/webapps/kartoteket_test/systemoversikt/
# update source code
git fetch
git reset --hard origin/master
# makemigrations (entironment is set up with python3.7)
python3.7 manage.py makemigrations
python3.7 manage.py migrate
# restart apache
~/webapps/kartoteket_test/apache2/bin/restart