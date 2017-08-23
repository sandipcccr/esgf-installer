#!/bin/bash

python_version=${python_version:-"2.7"}
esgf_node_manager_version=${esgf_node_manager_version:-"0.5.1"}
esgf_node_manager_db_version=${esgf_node_manager_db_version:-"0.1.5"}
esgf_node_manager_egg_file=esgf_node_manager-${esgf_node_manager_db_version}-py${python_version}.egg

node_db_node_manager_schema_name="esgf_node_manager"
node_db_name=${node_db_name:-"esgcet"}

postgress_user=${PGUSER:-dbsuper}
pg_sys_acct_passwd=${pg_sys_acct_passwd:=${pg_secret:=changeme}}
postgress_host=${PGHOST:-localhost}
postgress_port=${PGPORT:-5432}

source ${cdat_home}/bin/activate esgf-pub

easy_install ${esgf_node_manager_egg_file}
[ $? != 0 ] && echo "ERROR: Could not create esgf node manager python module" && checked_done 1

if [ -n "$(postgres_list_db_schemas ${node_db_node_manager_schema_name})" ]; then
    default="N"
    ((force_install)) && default="Y"
    dobackup=${default}
    read -p "Do you want to make a back up of the existing database schema [${node_db_name}:${node_db_node_manager_schema_name}]? $([ "$default" = "N" ] && echo "[y/N]" || echo "[Y/n]") " dobackup
    [ -z "${dobackup}" ] && dobackup=${default}
    if [ "${dobackup}" = "Y" ] || [ "${dobackup}" = "y" ]; then
        echo "Creating a backup archive of the database schema [$node_db_name:${node_db_node_manager_schema_name}]"
        backup_db -db ${node_db_name} -s ${node_db_node_manager_schema_name}
    fi
    unset dobackup
    unset default
    echo
fi

#run the code to build the database and install sql migration...
((DEBUG)) && echo "$cdat_home/bin/esgf_node_manager_initialize --dburl ${postgress_user}:${pg_sys_acct_passwd}@${postgress_host}:${postgress_port}/${node_db_name} -c"
esgf_node_manager_initialize --dburl ${postgress_user}:${pg_sys_acct_passwd}@${postgress_host}:${postgress_port}/${node_db_name} -c
[ $? != 0 ] && echo "ERROR: Could not create esgf manager database tables in ${node_db_name}" && checked_done 1

source deactivate
