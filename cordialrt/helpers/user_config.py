"""Reads the user confic file whcih conains information on the user and the folder for storing DICOM files"""

import definitions
def read_user_config():
    """ Read user config file and return as dict"""
    user_config = dict()

    with open(f"{definitions.ROOT_DIR}/cordialrt/user_config.txt") as config_file:
        for line in config_file:
            key, value = line.split('=')
            user_config[key] = value.strip()
    return(user_config)
