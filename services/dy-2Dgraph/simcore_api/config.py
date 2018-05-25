import os
import json
import logging


CONFIG = {
    "config_location":"file"
}


def get_ports_configuration():
    """returns the configuration of the node ports where this code is running. 
    
    Returns:
        dict -- a dictionary containing the ports configuration                
    """

    if CONFIG["config_location"] == "file":
        config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), r"../config/connection_config.json")
        with open(config_file) as file:
            return json.load(file)
    else:
        assert()

