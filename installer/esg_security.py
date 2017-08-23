import os
import datetime
import esg_logging_manager
import esg_version_manager
import esg_postgres
import esg_bash2py
import esg_functions
import esg_env_manager
import psycopg2
import yaml

logger = esg_logging_manager.create_rotating_log(__name__)


with open('esg_config.yaml', 'r') as config_file:
    config = yaml.load(config_file)

def init():
    security_app_context_root = "esgf-security"

    esgf_security_version= "1.2.8"
    esgf_security_db_version="0.1.4"
    esgf_security_egg_file = "esgf_security-{esgf_security_db_version}-py{python_version}.egg".format(esgf_security_db_version=config["esgf_security_db_version"],python_version=config["python_version"])

    #Database information....
    node_db_name = "esgcet"
    node_db_security_schema_name = "esgf_security"

    postgress_driver = "org.postgresql.Driver"
    postgress_protocol= "jdbc:postgresql:"
    try:
        postgress_host = os.environ["PGHOST"]
    except KeyError, error:
        postgress_host = "localhost"

    try:
        postgress_port = os.environ["PGPORT"]
    except KeyError, error:
        postgress_port = "5432"

    try:
        postgress_user = os.environ["PGUSER"]
    except KeyError, error:
        postgress_user = "dbsuper"

    try:
        pg_sys_acct_passwd = config["pg_sys_acct_passwd"]
    except KeyError, error:
        pg_sys_acct_passwd = "changeme"

    return locals()

def find_currently_installed_version():
    ''' Returns the version number of the currently installed version of esgf-security from the install manifest file '''
    with open(config["install_manifest"], 'r+') as manifest_file:
        manifest_contents = manifest_file.readlines()

        for entry in manifest_contents:
            if "esgf-security" in entry:
                return entry.split("=")[-1]

def setup_security(mode="install"):
    #####
    # Install The ESGF Security Services
    #####
    # - Takes boolean arg: 0 = setup / install mode (default)
    #                      1 = updated mode
    #
    # In setup mode it is an idempotent install (default)
    # In update mode it will always pull down latest after archiving old
    #
    print "Checking for esgf security (lib) [{esgf_security_version}]".format(esgf_security_version=config["esgf_security_version"])
    #Check the install manifest for the currently installed version of esgf-security
    currently_installed_version = find_currently_installed_version()
    if currently_installed_version:
        if esg_version_manager.check_for_acceptible_version("esgf-security", currently_installed_version, config["esgf_security_version"]):
            print "Current version of esgf-security is sufficient.  Skipping setup"
            return True

    print "locals before init():", locals()
    init()

    print "locals after init():", locals()

    configure_postgress()
    fetch_user_migration_launcher()
    fetch_policy_check_launcher()

    #migration niceness...
    clean_security_webapp_subsystem()


def configure_postgress(IDP_BIT, node_type):
    #TODO: check for IDP_BIT
    if IDP_BIT:
        esg_security_variables = init()

        esg_postgres.start_postgres()

        print "*******************************"
        print "Configuring Postgres... for ESGF Security"
        print "*******************************"

        db_list = esg_postgres.postgres_list_dbs()
        print "db_list:", db_list
        if not config["node_db_name"] in db_list:
            esg_postgres.postgres_create_db(config["node_db_name"])
        else:
            schema_list = esg_postgres.postgres_list_db_schemas()
            if config["node_db_security_schema_name"] in schema_list:
                print "Detected an existing security schema installation..."
            else:
                esg_postgres.postgres_clean_schema_migration("ESGF Security")

        db_directory = os.path.join(config["workdir"], "esgf-security-{esgf_security_version}".format(esgf_security_version=config["esgf_security_version", "db"]))
        esg_bash2py.mkdir_p(db_directory)
        with esg_bash2py.pushd(db_directory):
            #------------------------------------------------------------------------
            #Based on the node type selection we build the appropriate database tables
            #------------------------------------------------------------------------

            #download the egg file from the distribution server is necessary....
            esgf_security_egg_file_url = "{esg_dist_url}/esgf-security/{esgf_security_egg_file}".format(esg_dist_url=esg_dist_url, esgf_security_egg_file=esgf_security_egg_file)
            if not esg_functions.download_update(esgf_security_egg_file, esgf_security_egg_file_url):
                print "Could not dowload {esgf_security_egg_file} from {esgf_security_egg_file_url}".format(esgf_security_egg_file=esgf_security_egg_file, esgf_security_egg_file_url=esgf_security_egg_file_url)

            #install the egg....
            esg_functions.call_subprocess("bash configure_postgres_esg_security.sh")

            write_security_db_install_log()
    else:
        print "This function, configure_postgress(), is not applicable to current node type ({node_type})".format(node_type=node_type)

def write_security_db_install_log():
    with open(config["install_manifest"], 'a') as manifest_file:
        manifest_file.write(str(datetime.date.today()) + "python:esgf_security={esgf_security_db_version}".format(esgf_security_db_version=esg_security_variables["esgf_security_db_version"]))
    esg_env_manager.deduplicate_settings_in_file(config.install_manifest)

#******************************************************************
# SECURITY SETUP
#******************************************************************
def security_startup_hook():
    print "Security Startup Hook: Setup policy and whitelists... "
    esg_security_variables = init()
    _setup_policy_files()
    _setup_static_whitelists()
    # echo -n "(p) " && _setup_policy_files && echo -n ":-) "
    # [ $? != 0 ] && echo -n ":-("
    # echo -n "(w) " && _setup_static_whitelists "ats idp" && echo -n ":-) "
    # [ $? != 0 ] && echo -n ":-("
    # echo

def _setup_policy_files():


def fetch_user_migration_launcher():
    pass

def fetch_policy_check_launcher():
    pass

def clean_security_webapp_subsystem():
    pass
