import sys
import os
import subprocess
import re
import shutil
from OpenSSL import crypto
import logging
import requests
import socket
import platform
import netifaces
import tld
import grp
import shlex
import hashlib
import urlparse
import glob
import pwd
from time import sleep
import datetime
from esg_init import EsgInit
# import esg_init as config
from esg_exceptions import UnprivilegedUserError, WrongOSError, UnverifiedScriptError
import esg_bash2py
import esg_functions
import esg_bootstrap
import esg_env_manager
import esg_property_manager
import esg_version_manager
import esg_postgres
from esg_tomcat_manager import stop_tomcat
from urlparse import urljoin

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
config = EsgInit()

envfile = "/etc/esg.env"

#TODO: Maybe move these to esg_init
TOMCAT_USER_ID = pwd.getpwnam(config.config_dictionary["tomcat_user"]).pw_uid
TOMCAT_GROUP_ID = grp.getgrnam(config.config_dictionary["tomcat_group"]).gr_gid

#--------------
# User Defined / Settable (public)
#--------------
#--------------

# Sourcing esg-installarg esg-functions file and esg-init file
# [ -e ${esg_functions_file} ] && source ${esg_functions_file} && ((VERBOSE)) && printf "sourcing from: ${esg_functions_file} \n"

force_install = False

esg_dist_url = "http://distrib-coffee.ipsl.jussieu.fr/pub/esgf/dist"
esgf_host = esg_functions.get_esgf_host()

node_manager_app_context_root = "esgf-node-manager"
node_dist_url = "{esg_dist_url}/esgf-node-manager/esgf-node-manager-{esgf_node_manager_version}.tar.gz".format(
    esg_dist_url=esg_dist_url, esgf_node_manager_version=config.config_dictionary["esgf_node_manager_version"])
logger.debug("node_dist_url: %s", node_dist_url)


def init():
    #[ -n "${envfile}" ] && [ -e "${envfile}" ] && source ${envfile} && ((VERBOSE)) && printf "node manager: sourcing environment from: ${envfile} \n"

    esgf_node_manager_egg_file = "esgf_node_manager-{esgf_node_manager_db_version}-py{python_version}.egg".format(
        esgf_node_manager_db_version=config.config_dictionary["esgf_node_manager_db_version"], python_version=config.config_dictionary["python_version"])


    # get_property node_use_ssl && [ -z "${node_use_ssl}" ] && add_to_property_file node_use_ssl true
    node_use_ssl = esg_property_manager.get_property("node_use_ssl")
    esg_property_manager.add_to_property_file("node_use_ssl", True)

    # get_property node_manager_service_app_home ${tomcat_install_dir}/webapps/${node_manager_app_context_root}
    # add_to_property_file node_manager_service_app_home
    node_manager_service_app_home = esg_property_manager.get_property("node_manager_service_app_home", "{tomcat_install_dir}/webapps/{node_manager_app_context_root}".format(
        tomcat_install_dir=config.config_dictionary["tomcat_install_dir"], node_manager_app_context_root=node_manager_app_context_root))
    esg_property_manager.add_to_property_file(
        "node_manager_service_app_home", node_manager_service_app_home)

    # add_to_property_file node_manager_service_endpoint "http$([ "${node_use_ssl}" = "true" ] && echo "s" || echo "")://${esgf_host}/${node_manager_app_context_root}/node"
    if node_use_ssl:
        node_manager_service_endpoint = "https://{esgf_host}/{node_manager_app_context_root}/node".format(
            esgf_host=esgf_host, node_manager_app_context_root=node_manager_app_context_root)
    else:
        node_manager_service_endpoint = "http://{esgf_host}/{node_manager_app_context_root}/node".format(
            esgf_host=esgf_host, node_manager_app_context_root=node_manager_app_context_root)
    esg_property_manager.add_to_property_file(
        "node_manager_service_endpoint", node_manager_service_endpoint)

    # get_property node_use_ips && [ -z "${node_use_ips}" ] && add_to_property_file node_use_ips true
    node_use_ips = esg_property_manager.get_property("node_use_ips")
    esg_property_manager.add_to_property_file("node_use_ips", True)

    # get_property node_poke_timeout && [ -z "${node_poke_timeout}" ] && add_to_property_file node_poke_timeout 6000
    node_poke_timeout = esg_property_manager.get_property("node_poke_timeout")
    esg_property_manager.add_to_property_file("node_poke_timeout", 6000)

    # Database information....
    node_db_node_manager_schema_name = "esgf_node_manager"

    # Notification component information...
    # mail_smtp_host=${mail_smtp_host:-smtp.`hostname --domain`} #standard guess.
    # Overwrite mail_smtp_host value if already defined in props file
    # get_property mail_smtp_host ${mail_smtp_host}
    config.config_dictionary["mail_smtp_host"] = esg_property_manager.get_property("mail_smtp_host")

    # Launcher script for the esgf-sh
    esgf_shell_launcher = "esgf-sh"


def set_aside_web_app(app_home):
    pass


def choose_mail_admin_address():
    mail_admin_address = esg_property_manager.get_property("mail_admin_address")
    if not mail_admin_address or force_install:
        mail_admin_address_input = raw_input(
            "What email address should notifications be sent as? [{mail_admin_address}]: ".format(mail_admin_address=mail_admin_address))
    else:
        logger.info("mail_admin_address = [%s]", mail_admin_address)
        config.config_dictionary["mail_admin_address"] = mail_admin_address


def setup_node_manager(mode="install"):
    #####
    # Install The Node Manager
    #####
    # - Takes boolean arg: 0 = setup / install mode (default)
    #                      1 = updated mode
    #
    # In setup mode it is an idempotent install (default)
    # In update mode it will always pull down latest after archiving old
    #
    print "Checking for node manager {esgf_node_manager_version}".format(esgf_node_manager_version=config.config_dictionary["esgf_node_manager_version"])
    if esg_version_manager.check_webapp_version("esgf-node-manager", config.config_dictionary["esgf_node_manager_version"]) == 0 and not force_install:
        print "\n Found existing version of the node-manager [OK]"
        return True

    init()

    print "*******************************"
    print "Setting up The ESGF Node Manager..."
    print "*******************************"

    # local upgrade=${1:-0}

    db_set = 0

    if force_install:
        default_answer = "N"
    else:
        default_answer = "Y"
    # local dosetup
    node_manager_service_app_home = esg_property_manager.get_property(
        "node_manager_service_app_home")
    if os.path.isdir(node_manager_service_app_home):
        db_set = 1
        print "Detected an existing node manager installation..."
        if default_answer == "Y":
            installation_answer = raw_input(
                "Do you want to continue with node manager installation and setup? [Y/n]") or default_answer
        else:
            installation_answer = raw_input(
                "Do you want to continue with node manager installation and setup? [y/N]") or default_answer
        if installation_answer.lower() not in ["y", "yes"]:
            print "Skipping node manager installation and setup - will assume it's setup properly"
            # resetting node manager version to what it is already, not what we prescribed in the script
            # this way downstream processes will use the *actual* version in play, namely the (access logging) filter(s)
            esgf_node_manager_version = esg_version_manager.get_current_webapp_version(
                "esgf_node_manager")
            return True

        backup_default_answer = "Y"
        backup_answer = raw_input("Do you want to make a back up of the existing distribution [{node_manager_app_context_root}]? [Y/n] ".format(
            node_manager_app_context_root=node_manager_app_context_root)) or backup_default_answer
        if backup_answer.lower in ["yes", "y"]:
            print "Creating a backup archive of this web application [{node_manager_service_app_home}]".format(node_manager_service_app_home=node_manager_service_app_home)
            esg_functions.backup(node_manager_service_app_home)

        backup_db_default_answer = "Y"
        backup_db_answer = raw_input("Do you want to make a back up of the existing database [{node_db_name}:esgf_node_manager]?? [Y/n] ".format(
            node_db_name=config.config_dictionary["node_db_name"])) or backup_db_default_answer

        if backup_db_answer.lower() in ["yes", "y"]:
            print "Creating a backup archive of the manager database schema [{node_db_name}:esgf_node_manager]".format(node_db_name=config.config_dictionary["node_db_name"])
            # TODO: Implement this
            # esg_postgres.backup_db() -db ${node_db_name} -s node_manager

    esg_bash2py.mkdir_p(config.config_dictionary["workdir"])
    with esg_bash2py.pushd(config.config_dictionary["workdir"]):
        logger.debug("changed directory to : %s", os.getcwd())

        # strip off .tar.gz at the end
        #(Ex: esgf-node-manager-0.9.0.tar.gz -> esgf-node-manager-0.9.0)
        node_dist_file = esg_bash2py.trim_string_from_head(node_dist_url)
        logger.debug("node_dist_file: %s", node_dist_file)
        # Should just be esgf-node-manager-x.x.x
        node_dist_dir = node_dist_file

        # checked_get ${node_dist_file} ${node_dist_url} $((force_install))
        if not esg_functions.download_update(node_dist_file, node_dist_url, force_download=force_install):
            print "ERROR: Could not download {node_dist_url} :-(".format(node_dist_url=node_dist_url)
            esg_functions.checked_done(1)

        # make room for new install
        if force_install:
            print "Removing Previous Installation of the ESGF Node Manager... ({node_dist_dir})".format(node_dist_dir=node_dist_dir)
            try:
                shutil.rmtree(node_dist_dir)
                logger.info("Deleted directory: %s", node_dist_dir)
            except IOError, error:
                logger.error(error)
                logger.error("Could not delete directory: %s", node_dist_dir)
                esg_functions.checked_done(1)

            clean_node_manager_webapp_subsystem()

        print "\nunpacking {node_dist_file}...".format(node_dist_file=node_dist_file)
        # This probably won't work, because the extension has already been stripped, no idea how this even worked in the bash code smh
        try:
            tar = tarfile.open(node_dist_file)
            tar.extractall()
            tar.close()
        except Exception, error:
            logger.error(error)
            print "ERROR: Could not extract the ESG Node: {node_dist_file}".format(node_dist_file=node_dist_file)
            esg_functions.checked_done(1)

        # pushd ${node_dist_dir} >& /dev/null
        with esg_bash2py.pushd(node_dist_dir):
            logger.debug("changed directory to : %s", os.getcwd())
            stop_tomcat()

            # strip the version number off(#.#.#) the dir and append .war to get the name of war file
            #(Ex: esgf-node-manager-0.9.0 -> esgf-node-manager.war)
            # local trimmed_name=$(pwd)/${node_dist_dir%-*}
            split_dir_name_list = node_dist_dir.split("-")
            versionless_name = '-'.join(split_dir_name_list[:3])
            trimmed_name = os.path.join(os.getcwd(), versionless_name)
            node_war_file = trimmed_name + ".war"
            logger.debug("node_war_file: %s", node_war_file)

            #----------------------------
            # make room for new INSTALL
            # ((upgrade == 0)) && set_aside_web_app ${node_manager_service_app_home}
            if mode != "upgrade":
                set_aside_web_app(node_manager_service_app_home)
            #----------------------------
            # mkdir -p ${node_manager_service_app_home}
            esg_bash2py.mkdir_p(node_manager_service_app_home)
            # cd ${node_manager_service_app_home}
            os.chdir(node_manager_service_app_home)
            logger.debug("changed directory to : %s", os.getcwd())

            #----------------------------
            # fetch_file=esgf-node-manager.properties
            download_file_name = "esgf-node-manager.properties"

            # NOTE: The saving of the last config file must be done *BEFORE* we untar the new distro!
            # if ((upgrade)) && [ -e WEB-INF/classes/${fetch_file} ]; then
            if mode == "upgrade" and os.path.isfile("WEB-INF/classes/{download_file_name}".format(download_file_name=download_file_name)):
                # cp WEB-INF/classes/${fetch_file} WEB-INF/classes/${fetch_file}.saved
                esg_functions.create_backup_file(
                    "WEB-INF/classes/{download_file_name}".format(download_file_name=download_file_name), ".saved")
                # chmod 600 WEB-INF/classes/${fetch_file}*
                for file_name in glob.glob("WEB-INF/classes/{download_file_name}".format(download_file_name=download_file_name)):
                    try:
                        os.chmod(file_name, 0600)
                    except OSError, error:
                        logger.error(error)

            print "\nExpanding war {node_war_file} in {current_directory}".format(node_war_file=node_war_file, current_directory=os.getcwd())
            # $JAVA_HOME/bin/jar xf ${node_war_file}
            try:
                tar = tarfile.open(node_war_file)
                tar.extractall()
                tar.close()
            except Exception, error:
                logger.error(error)
                print "ERROR: Could not extract the ESG Node: {node_war_file}".format(node_war_file=node_war_file)
                esg_functions.checked_done(1)

            #----------------------------
            # Property file fetching and token replacement...
            #----------------------------
            # pushd WEB-INF/classes >& /dev/null
            with esg_bash2py.pushd("WEB-INF/classes"):
                # cat ${fetch_file}.tmpl >> ${config_file}
                with open(download_file_name + ".tmpl", "r") as download_file:
                    with open(config.config_dictionary["config_file"], "w") as config_file:
                        download_file_contents = download_file.read()
                        config_file.write(download_file_contents)

                # chown -R ${tomcat_user} ${node_manager_service_app_home}
                # chgrp -R ${tomcat_group} ${node_manager_service_app_home}
                os.chown(esg_functions.readlinkf(node_manager_service_app_home), pwd.getpwnam(config.config_dictionary["tomcat_user"]).pw_uid, grp.getgrnam(config.config_dictionary["tomcat_group"]).gr_gid)
            #----------------------------

    # popd >& /dev/null

    # NOTE TODO: Create a function that reads the property file and for
    # every property that is not assigned and/or in a list of manidtory
    # properties go through and ask the user to assign a value. -gavin

    # if [ -z "${mail_admin_address}" ]; then
    #     while [ 1 ]; do
    #         local input
    #         read -p "What email address should notifications be sent as? " input
    #         [ -n "${input}" ] && mail_admin_address=${input}  && unset input && break
    #     done
    # fi

    # choose_mail_admin_address()

    if db_set > 0:
        if write_node_manager_config() != 0 or configure_postgress() != 0:
            esg_functions.checked_done(1)

    touch_generated_whitelist_files()
    write_node_manager_install_log()
    write_shell_contrib_command_file()

    fetch_shell_launcher()

#    setup_conda_env
    setup_py_pkgs()

    setup_nm_repo()

    esg_functions.checked_done(0)


def setup_nm_repo():
    pass


def setup_py_pkgs():
    pass


def fetch_shell_launcher():
    ''' Download the esgf_shell_launcher script '''
    with esg_bash2py.pushd(config.config_dictionary["scripts_dir"]):
        node_dist_url_root = esg_bash2py.trim_string_from_head(node_dist_url)
        esgf_shell_launcher_url = urljoin(node_dist_url_root, "esgf_shell_launcher")
        logger.debug("esgf_shell_launcher_url: %s", esgf_shell_launcher_url)
        if not esg_functions.download_update(esgf_shell_launcher, esgf_shell_launcher_url, force_install):
            logger.error("Could not download: %s", esgf_shell_launcher_url)
            return False
        os.chmod(esgf_shell_launcher, 0755)
    return True


def write_shell_contrib_command_file():
    pass


def write_node_manager_install_log():
    ''' Log out to the install manifest file, i.e esgf-install-manifest '''
    with open(config.install_manifest, "a") as manifest_file:
        date_string = str(datetime.date.today())
        log_entry = "{date} webapp:esgf-node-manager={esgf_node_manager_version} {node_manager_service_app_home}".format(date=date_string, esgf_node_manager_version=esgf_node_manager_version, node_manager_service_app_home=node_manager_service_app_home)
        manifest_file.write(log_entry)

    esg_env_manager.deduplicate_settings_in_file(config.install_manifest)
    return True


def touch_generated_whitelist_files():
    '''Create whitlisted xml files '''

    whitelist_files = []

    logger.debug("touch_generated_whitelist_files....")

    tomcat_user_id = pwd.getpwnam(config.config_dictionary["tomcat_user"]).pw_uid
    tomcat_group_id = grp.getgrnam(config.config_dictionary["tomcat_group"]).gr_gid

    esgf_ats_xml_file = os.path.join(config.config_dictionary["esg_config_dir"], "esgf_ats.xml")
    whitelist_files.append(esgf_ats_xml_file)
    esgf_atz_xml_file = os.path.join(config.config_dictionary["esg_config_dir"], "esgf_atz.xml")
    whitelist_files.append(esgf_atz_xml_file)
    esgf_idp_xml_file = os.path.join(config.config_dictionary["esg_config_dir"], "esgf_idp.xml")
    whitelist_files.append(esgf_idp_xml_file)
    esgf_shards_xml_file = os.path.join(config.config_dictionary["esg_config_dir"], "esgf_shards.xml")
    whitelist_files.append(esgf_shards_xml_file)
    las_server_conf_directory = os.path.join(config.esg_root_dir, "content", "las", "conf", "server")
    if os.path.isdir(las_server_conf_directory):
        las_servers_xml = os.path.join(las_server_conf_directory, "las_servers.xml")
        whitelist_files.append(las_servers_xml)

    for whitelist_file in whitelist_files:
        esg_bash2py.touch(whitelist_file)
        os.chown(whitelist_file, tomcat_user_id, tomcat_group_id)
        os.chmod(whitelist_file, 0644)


def configure_postgress():
    pass


def write_node_manager_config():
    ''' Write Node Manger configuration settings to esgf.properties file '''
    logger.debug("Writing down database connection info and other node-wide properties")
    logger.info("Writing down database connection info and other node-wide properties")

    #TODO: No real reason to change to the config directory since I'm using absolute path
    with esg_bash2py.pushd(config.esg_config_dir):
        esg_property_manager.add_to_property_file("db.driver", config.config_dictionary["postgress_driver"])
        esg_property_manager.add_to_property_file("db.protocol", config.config_dictionary["postgress_protocol"])
        esg_property_manager.add_to_property_file("db.host", config.config_dictionary["postgress_host"])
        esg_property_manager.add_to_property_file("db.port", config.config_dictionary["postgress_port"])
        esg_property_manager.add_to_property_file("db.database", config.config_dictionary["node_db_name"])
        esg_property_manager.add_to_property_file("db.user", config.config_dictionary["postgress_user"])
        esg_property_manager.add_to_property_file("mail.smtp.host", config.config_dictionary["mail_smtp_host"])
        esg_property_manager.add_to_property_file("mail.admin.address", config.config_dictionary["mail_admin_address"])

        esg_property_manager.deduplicate_properties_file()

        os.chown(config.config_dictionary["config_file"], TOMCAT_USER_ID, TOMCAT_GROUP_ID)
        os.chmod(config.config_dictionary["config_file"], 0600)
    return True

#--------------------------------------
# Clean / Uninstall this module...
#--------------------------------------


def clean_node_manager_webapp_subsystem():
    pass
