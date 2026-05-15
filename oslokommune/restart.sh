#!/bin/sh
echo "Reloading deamons.."
sudo systemctl daemon-reload
echo "Restarting gunicorn.."
sudo systemctl restart gunicorn-mysite.service
echo "Restarting webserver.."
sudo systemctl restart httpd.service
echo "Restarting database.."
sudo systemctl restart postgresql.service
echo "Complete"