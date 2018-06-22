"""Takes care of the configurations.
"""
import logging


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
                            "file-url":str, 
                            "bool":bool, 
                            "string":str, 
                            "folder-url":str}
# S3 stored information
TYPE_TO_S3_FILE_LIST = ["file-url"]
TYPE_TO_S3_FOLDER_LIST = ["folder-url"]

# nodeports is a library for accessing data linked to the node
# in that sense it should not log stuff unless the application code wants it to be so.
logging.getLogger(__name__).addHandler(logging.NullHandler())
_LOGGER = logging.getLogger(__name__)

# pylint: disable=C0111
class CommonConfig(object):
    pass
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
