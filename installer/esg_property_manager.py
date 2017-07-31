'''
Property reading and writing...
'''
import os
import sys
import re
import yaml
import esg_logging_manager
import esg_env_manager

logger = esg_logging_manager.create_rotating_log(__name__)

with open('esg_config.yaml', 'r') as config_file:
    config = yaml.load(config_file)


def load_properties(property_file = config["config_file"]):
    '''
        Load properties from a java-style property file
        providing them as script variables in this context
        property_file - optional property file (default file is esgf.properties)
    '''
    if not os.access(property_file, os.R_OK):
        return False
    esg_env_manager.deduplicate_properties(property_file)
    separator = "="
    count = 0
    with open(property_file) as f:
        for line in f:
            key,value = line.split(separator)
            print  "loading... "
            print  "[%s] -> " % (key)
            print "[%s]" % (value)
            count+=1
    print "Loaded (imported) %i properties from %s" % (count, property_file)
    return 0


def get_property(property_name, default_value = None):
    '''
        Gets a single property from a string arg and turns it into a shell var
        arg 1 - the string that you wish to get the property of (and make a variable)
        arg 2 - optional default value to set
    '''
    if not os.access(config["config_file"], os.R_OK):
        print "Unable to read file"
        return False
    property_name = re.sub(r'\_', r'.', property_name)
    datafile = open(config["config_file"], "r+")
    searchlines = datafile.readlines()
    datafile.seek(0)
    for line in searchlines:
        if property_name in line:
            _, value = line.split("=")
            if not value and default_value:
                return default_value.strip()
            else:
                return value.strip()

# TODO: Not used anywhere; maybe deprecate
def get_property_as():
    '''
        Gets a single property from the arg string and turns the alias into a
        shell var assigned to the value fetched.
        arg 1 - the string that you wish to get the property of (and make a variable)
        arg 2 - the alias string value of the variable you wish to create and assign
        arg 3 - the optional default value if no value is found for arg 1
    '''
    pass

def remove_property(key):
    '''
        Removes a given variable's property representation from the esgf.properties file
        key - a key to be removed from the property file
    '''
    print "removing %s's property from %s" % (key, config["config_file"])
    property_found = False
    datafile = open(config["config_file"], "r+")
    searchlines = datafile.readlines()
    datafile.seek(0)
    for line in searchlines:
        if key not in line:
            datafile.write(line)
        else:
            property_found = True
    datafile.truncate()
    datafile.close()
    return property_found


def add_to_property_file(property_name, property_value):
    '''
        Writes variable out to the esgf.properties file as java-stye property
        I am replacing all bash-style "_"s with java-style "."s

        property_name - The string of the variable you wish to write as property to property file
        property_value - The value to set the variable to (default: the value of arg1)

        Values gets written to the file in the following format: properlty.name=property_value
    '''
    datafile = open(config["config_file"], "a+")
    searchlines = datafile.readlines()
    datafile.seek(0)
    for line in searchlines:
        if property_name in line:
            print "Property already exists"
            return
    else:
        #replace underscores with periods
        property_name = property_name.replace("_", ".")
        datafile.write(property_name+"="+property_value+"\n")
        return True
