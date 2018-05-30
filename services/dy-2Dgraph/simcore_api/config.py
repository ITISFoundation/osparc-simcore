"""Takes care of the configurations.

    The configuration may be located in a file or in a database.
"""

import os


CONFIG = {
    "config_location":"file"
}

_DEFAULT_FILE_LOCATION = r"../config/connection_config.json"

def get_ports_configuration():
    """returns the json configuration of the node ports where this code is running. 
    
    Returns:
        string -- a json containing the ports configuration                
    """

    if CONFIG["config_location"] == "file":
        file_location = os.environ.get('SIMCORE_CONFIG_PATH', _DEFAULT_FILE_LOCATION)
        config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), file_location)

        with open(config_file) as simcore_config:
            return simcore_config.read()

    assert "not implemented yet"
