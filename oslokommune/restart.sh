#!/bin/sh
echo "Restarting webserver.."
sudo systemctl restart httpd.service
echo "Complete"