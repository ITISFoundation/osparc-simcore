"""Takes care of the configurations.

    The configuration may be located in a file or in a database.
"""

import os
import logging
from enum import Enum


DATA_ITEM_KEYS = ["key", "label", "description", "type", "value", "timestamp"]
TYPE_TO_PYTHON_TYPE_MAP = {"int":int, "float":float, "file-url":str, "bool":bool, "string":str, "folder":str}

# nodeports is a library for accessing data linked to the node
# in that sense it should not log stuff unless the application code wants it to be so.
logging.getLogger(__name__).addHandler(logging.NullHandler())
_LOGGER = logging.getLogger(__name__)

# pylint: disable=C0111

class Location(Enum):
    FILE = "file"
    DATABASE = "database"

class CommonConfig(object):
    DEFAULT_FILE_LOCATION = r"../config/connection_config.json"
    LOCATION = Location.FILE

    @classmethod    
    def get_ports_configuration(cls):
        """returns the json configuration of the node ports where this code is running. 
        
        Returns:
            string -- a json containing the ports configuration                
        """
        _LOGGER.debug("Getting ports configuration using %s", cls.LOCATION)
        if cls.LOCATION == Location.FILE:
            file_location = os.environ.get('SIMCORE_CONFIG_PATH', cls.DEFAULT_FILE_LOCATION)
            config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), file_location)
            _LOGGER.debug("Reading ports configuration from %s", config_file)
            with open(config_file) as simcore_config:
                return simcore_config.read()
        else:
            raise NotImplementedError

    @classmethod
    def write_ports_configuration(cls, json_configuration):
        """writes the json configuration of the node ports.
        """
        _LOGGER.debug("Writing ports configuration to %s", cls.LOCATION)
        if cls.LOCATION == Location.FILE:
            file_location = os.environ.get('SIMCORE_CONFIG_PATH', cls.DEFAULT_FILE_LOCATION)
            config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), file_location)
            _LOGGER.debug("Writing ports configuration to %s", config_file)
            with open(config_file, "w") as simcore_file:
                simcore_file.write(json_configuration)
        else:
            raise NotImplementedError

class DevelopmentConfig(CommonConfig):
    LOG_LEVEL = logging.DEBUG

class TestingConfig(CommonConfig):
    LOG_LEVEL = logging.DEBUG

class ProductionConfig(CommonConfig):
    LOG_LEVEL = logging.WARNING

CONFIG = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,

    "default": DevelopmentConfig
}
