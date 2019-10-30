#list jobs
crontab -l

#edit jobs. Åpnes i vim. "i" for å redigere og "ctrl c" for å gå ut av redigeringsmodus. ":wq!" for å lagre og gå ut (write quit force).
crontab -e
 
#jobber (minutt, time, dag, måned, år)
0 8,11,13,17 * * * /path/systemoversikt/bash_scripts/backup_script_db
0 12,18 * * * /path/systemoversikt/bash_scripts/backup_script_app
0 3 * * * /path/systemoversikt/bash_scripts/ldap_update_all_users