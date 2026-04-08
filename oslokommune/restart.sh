#!/bin/sh
echo "Restarting gunicorn.."
sudo systemctl restart gunicorn-mysite.service
echo "Restarting webserver.."
sudo systemctl restart httpd.service
echo "Complete"