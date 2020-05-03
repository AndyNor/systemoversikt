#!/bin/sh

# make a compressed backup of the "systemoversikt"-folder
tar -zcf /path/backup/app/djangoapp_`date +%F_%H:%M:%S`.tar.gz /path/systemoversikt

# remove duplicates - keep one
cd /path/backup/app/
last=-1; find . -type f -name '*.tar.gz' -printf '%f\0' | sort -nz |
    while read -d '' i; do
        s=$(stat -c '%s' "$i");
        [[ $s = $last ]] && rm "$i";
    last=$s;
done