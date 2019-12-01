#!/bin/sh
# execute permissions must be turned off on test server
#git config --local core.fileMode false
# move to correct folder
cd ~/webapps/kartoteket_test/myproject/systemoversikt/
# update source code
git fetch
git reset --hard origin/master
# makemigrations (entironment is set up with python3.7)
python3.7 manage.py makemigrations
python3.7 manage.py migrate
python3.7 manage.py collectstatic --noinput
# restart apache
~/webapps/kartoteket_test/apache2/bin/restart

cd ~/webapps/kartoteket_test/myproject/systemoversikt/bash_scripts/
chmod +x *
