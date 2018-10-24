"""Takes care of the configurations.
"""
import logging
from distutils.util import strtobool # pylint: disable=no-name-in-module

# defined by JSON schema
DATA_ITEM_KEYS = ["key",
                "label",
                "desc",
                "type",
                "value",
                "timestamp"]

# True if required, defined by JSON schema
SCHEMA_ITEM_KEYS = {"key":True,
                    "label":True,
                    "description":True,
                    "type":True,
                    "fileToKeyMap":False,
                    "defaultValue":False,
                    "widget":False}
# allowed types
TYPE_TO_PYTHON_TYPE_MAP = {"integer":{"type":int, "converter":int},
                            "number":{"type":float, "converter":float},
                            "file-url":{"type":str, "converter":str},
                            "bool":{"type":bool, "converter":strtobool},
                            "string":{"type":str, "converter":str},
                            "folder-url":{"type":str, "converter":str}
                            }
# S3 stored information
TYPE_TO_S3_FILE_LIST = ["file-url"]
TYPE_TO_S3_FOLDER_LIST = ["folder-url"]

LINK_PREFIX = "link."

# nodeports is a library for accessing data linked to the node
# in that sense it should not log stuff unless the application code wants it to be so.
logging.getLogger(__name__).addHandler(logging.NullHandler())
log = logging.getLogger(__name__)
