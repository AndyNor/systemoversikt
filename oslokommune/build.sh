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

echo "Restarting gunicorn.."
sudo systemctl restart gunicorn-mysite.service

echo "Restarting webserver.."
sudo systemctl restart httpd.service

echo "Server is now updated!"
