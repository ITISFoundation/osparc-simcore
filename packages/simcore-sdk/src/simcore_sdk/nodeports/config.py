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
TYPE_TO_PYTHON_TYPE_MAP = {"integer":int, 
                            "number":float, 
                            "file-url":str, 
                            "bool":bool, 
                            "string":str, 
                            "folder-url":str}
# S3 stored information
TYPE_TO_S3_FILE_LIST = ["file-url"]
TYPE_TO_S3_FOLDER_LIST = ["folder-url"]

LINK_PREFIX = "link."

# nodeports is a library for accessing data linked to the node
# in that sense it should not log stuff unless the application code wants it to be so.
logging.getLogger(__name__).addHandler(logging.NullHandler())
_LOGGER = logging.getLogger(__name__)

