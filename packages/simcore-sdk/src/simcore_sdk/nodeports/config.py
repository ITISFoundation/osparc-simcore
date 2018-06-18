"""Takes care of the configurations.

    The configuration may be located in a file or in a database.
"""
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
    LOCATION = Location.DATABASE

class DevelopmentConfig(CommonConfig):
    LOG_LEVEL = logging.DEBUG

class TestingConfig(CommonConfig):
    LOG_LEVEL = logging.DEBUG

class ProductionConfig(CommonConfig):
    LOG_LEVEL = logging.WARNING
    LOCATION = Location.DATABASE

CONFIG = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,

    "default": DevelopmentConfig
}
