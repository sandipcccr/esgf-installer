import sys
import subprocess
import logging
from esg_init import EsgInit
import esg_bash2py

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
config = EsgInit()

#----------------------------------------------------------
# Environment Management Utility Functions
#----------------------------------------------------------
def remove_env(env_name):
    print "removing %s's environment from %s" % (env_name, config.envfile)
    found_in_env_file = False
    datafile = open(config.envfile, "r+")
    searchlines = datafile.readlines()
    datafile.seek(0)
    for line in searchlines:
        if env_name not in line:
            datafile.write(line)
        else:
            found_in_env_file = True
    datafile.truncate()
    datafile.close()
    return found_in_env_file

#TODO: Fix sed statement
def remove_install_log_entry(entry):
    print "removing %s's install log entry from %s" % (entry, config.config_dictionary["install_manifest"])
    subprocess.check_output("sed -i '/[:]\?'${key}'=/d' ${install_manifest}")

#TODO: This might be redundant with esg_property_manager.deduplicate_properties_file();
#should just be able to pass in whatever file to deduplicate
def deduplicate_settings_in_file(envfile = None):
    '''
    Environment variable files of the form
    Ex: export FOOBAR=some_value
    Will have duplicate keys removed such that the
    last entry of that variable is the only one present
    in the final output.
    envfile - The environment file to have duplicate entries removed.
    '''

    infile = esg_bash2py.Expand.colonMinus(envfile, config.envfile)
    try:
        my_set = set()
        deduplicated_list = []
        with open(infile, 'r+') as environment_file:
            env_settings = environment_file.readlines()

            for setting in reversed(env_settings):
                key, value = setting.split("=")

                if key not in my_set:
                    deduplicated_list.append(key+ "=" + value)
                    my_set.add(key)
            deduplicated_list.reverse()
            
            environment_file.seek(0)
            for setting in deduplicated_list:
                environment_file.write(setting)
            environment_file.truncate()
    except IOError, error:
        logger.error(error)
        sys.exit(0)


#TODO: fix awk statements
# def get_config_ip(interface_value):
#     '''
#     #####
#     # Get Current IP Address - Needed (at least temporarily) for Mesos Master
#     ####
#     Takes a single interface value
#     "eth0" or "lo", etc...
#     '''
    # return subprocess.check_output("ifconfig $1 | grep \"inet[^6]\" | awk '{ gsub (\" *inet [^:]*:\",\"\"); print $1}'")
