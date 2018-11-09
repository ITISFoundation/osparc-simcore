"""Takes care of the configurations.
"""
import logging
import os

NODE_UUID = os.environ.get("SIMCORE_NODE_UUID", default="undefined")
PROJECT_ID = os.environ.get("SIMCORE_PIPELINE_ID", default="undefined")
USER_ID = os.environ.get("SIMCORE_USER_ID", default="undefined")

STORAGE_ENDPOINT = os.environ.get("STORAGE_ENDPOINT", default="undefined")
STORAGE_VERSION = "v0"

STORE = "simcore.s3"
BUCKET = "simcore"

NODE_KEYS = {"version":True,
"schema":True,
"inputs":True,
"outputs":True}

# defined by JSON schema
DATA_ITEM_KEYS = {"key":True,
                "value":True}

# True if required, defined by JSON schema
SCHEMA_ITEM_KEYS = {"key":True,
                    "label":True,
                    "description":True,
                    "type":True,
                    "displayOrder":True,
                    "fileToKeyMap":False,
                    "defaultValue":False,
                    "widget":False}
# allowed types
TYPE_TO_PYTHON_TYPE_MAP = {"integer":{"type":int, "converter":int},
                            "number":{"type":float, "converter":float},
                            "boolean":{"type":bool, "converter":bool},
                            "string":{"type":str, "converter":str}
                            }
FILE_TYPE_PREFIX = "data:"

# nodeports is a library for accessing data linked to the node
# in that sense it should not log stuff unless the application code wants it to be so.
logging.getLogger(__name__).addHandler(logging.NullHandler())
log = logging.getLogger(__name__)
