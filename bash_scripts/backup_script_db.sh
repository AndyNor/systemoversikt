#!/bin/sh

# make a compressed backup of the db.sqlite3-file
tar -zcf /path/backup/db/db_`date +%F_%H:%M:%S`.tar.gz /path/db.sqlite3

# remove duplicated - keep one copy
cd /path/backup/db/
last=-1; find . -type f -name '*.tar.gz' -printf '%f\0' | sort -nz |
    while read -d '' i; do
        s=$(stat -c '%s' "$i");
        [[ $s = $last ]] && rm "$i";
    last=$s;
done

# remove files older than 21 days
find /path/backup/db/ -mindepth 1 -mtime +21 -delete

