"""Reads the user confic file whcih conains information on the user and the folder for storing DICOM files"""

import os

CONFIG_PATH = "user_config.txt"


def read_user_config():
    """Read user config file and return as dict"""
    user_config = dict()

    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH) as config_file:
            for line in config_file:
                key, value = line.split("=")
                user_config[key] = value.strip()
        return user_config

    print("A config file is missing, please see the README for help")
    raise FileExistsError
