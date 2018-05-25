import os
import json


def get_connection_configuration():
    config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), r"../connection_config.json")
    with open(config_file) as file:
        return json.load(file)