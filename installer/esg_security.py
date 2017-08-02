import os
import esg_logging_manager
import esg_version_manager
import esg_postgres
import esg_bash2py
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


def configure_postgress():
    #TODO: check for IDP_BIT

    init()

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




    pass

def fetch_user_migration_launcher():
    pass

def fetch_policy_check_launcher():
    pass

def clean_security_webapp_subsystem():
    pass
