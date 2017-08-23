#!/bin/bash

force_install=${force_install:-0}
cdat_home="/usr/local/cdat"
esgf_security_version=${esgf_security_version:-"1.2.8"}
esgf_security_db_version=${esgf_security_db_version:-"0.1.4"}
esgf_security_egg_file=esgf_security-${esgf_security_db_version}-py${python_version}.egg
python_version=${python_version:-"2.7"}

#Database information....
node_db_name=${node_db_name:-"esgcet"}
node_db_security_schema_name="esgf_security"

postgress_driver=${postgress_driver:-org.postgresql.Driver}
postgress_protocol=${postgress_protocol:-jdbc:postgresql:}
postgress_host=${PGHOST:-localhost}
postgress_port=${PGPORT:-5432}
postgress_user=${PGUSER:-dbsuper}
pg_sys_acct_passwd=${pg_sys_acct_passwd:=${pg_secret:=changeme}}

#install the egg....
source ${cdat_home}/bin/activate esgf-pub

((DEBUG)) && "easy_install ${esgf_security_egg_file}"
$cdat_home/bin/easy_install ${esgf_security_egg_file}
[ $? != 0 ] && echo "ERROR: Could not create esgf security python module" && checked_done 1

if [ -n "$(postgres_list_db_schemas ${node_db_security_schema_name})" ]; then
    default="N"
    ((force_install)) && default="Y"
    dobackup=${default}
    read -p "Do you want to make a back up of the existing database schema [${node_db_name}:${node_db_security_schema_name}]? $([ "$default" = "N" ] && echo "[y/N]" || echo "[Y/n]") " dobackup
    [ -z "${dobackup}" ] && dobackup=${default}
    if [ "${dobackup}" = "Y" ] || [ "${dobackup}" = "y" ]; then
        echo "Creating a backup archive of the database schema [$node_db_name:${node_db_security_schema_name}]"
        backup_db -db ${node_db_name} -s ${node_db_security_schema_name}
    fi
    unset dobackup
    unset default
    echo
fi

#run the code to build the database and install sql migration...
((DEBUG)) && echo "$cdat_home/bin/esgf_security_initialize --dburl ${postgress_user}:${pg_sys_acct_passwd}@${postgress_host}:${postgress_port}/${node_db_name} -c"
esgf_security_initialize --dburl ${postgress_user}:${pg_sys_acct_passwd}@${postgress_host}:${postgress_port}/${node_db_name} -c
[ $? != 0 ] && echo "ERROR: Could not create esgf security database tables in ${node_db_name}" && checked_done 1

source deactivate
