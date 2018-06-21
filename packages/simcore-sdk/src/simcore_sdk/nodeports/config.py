"""Takes care of the configurations.

    The configuration may be located in a file or in a database.
"""
import logging
from enum import Enum


# defined by JSON schema
DATA_ITEM_KEYS = ["key", 
                "label", 
                "desc", 
                "type", 
                "value", 
                "timestamp"]
# allowed types
TYPE_TO_PYTHON_TYPE_MAP = {"int":int, 
                            "integer":int, 
                            "float":float, 
                            "fileUrl":str, 
                            "bool":bool, 
                            "string":str, 
                            "folderUrl":str}
# S3 stored information
TYPE_TO_S3_FILE_LIST = ["fileUrl"]
TYPE_TO_S3_FOLDER_LIST = ["folderUrl"]

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

CONFIG = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,

    "default": DevelopmentConfig
}
