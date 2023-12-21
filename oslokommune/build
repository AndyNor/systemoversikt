#!/bin/sh
echo "Downloading latest source code.."
git fetch
git reset --hard origin/master

echo "Installing dependencies.."
pip install -q -r /var/kartoteket/source/systemoversikt/requirements.txt


echo "Migrating database.."
python /var/kartoteket/source/systemoversikt/manage.py makemigrations
python /var/kartoteket/source/systemoversikt/manage.py migrate

echo "Collecting static files.."
python /var/kartoteket/source/systemoversikt/manage.py collectstatic --noinput

echo "Rydder opp i databasefilen.."
sqlite3 /var/kartoteket/source/systemoversikt/db.sqlite3 "VACUUM;"

echo "Restarting webserver.."
#sudo service httpd restart
sudo systemctl restart httpd.service

echo "Server is now updated!"
