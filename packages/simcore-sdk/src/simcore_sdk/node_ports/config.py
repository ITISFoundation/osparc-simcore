"""Takes care of the configurations.
"""
import os


# required configurations
PROJECT_ID = os.environ.get("SIMCORE_PROJECT_ID", default="undefined")
NODE_UUID = os.environ.get("SIMCORE_NODE_UUID", default="undefined")
USER_ID = os.environ.get("SIMCORE_USER_ID", default="undefined")
STORAGE_ENDPOINT = os.environ.get("STORAGE_ENDPOINT", default="undefined")
STORAGE_VERSION = "v0"

POSTGRES_ENDPOINT: str = os.environ.get("POSTGRES_ENDPOINT", "postgres:5432")
POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "simcoredb")
POSTGRES_PW: str = os.environ.get("POSTGRES_PASSWORD", "simcore")
POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "simcore")

# overridable required configurations
STORE = os.environ.get("STORAGE_STORE_LOCATION_NAME", default="simcore.s3")
BUCKET = os.environ.get("S3_BUCKET_NAME", default="simcore")


# -------------------------------------------------------------------------
STORAGE_ENDPOINT = os.environ.get("STORAGE_ENDPOINT", default="undefined")
STORAGE_VERSION = "v0"

NODE_KEYS = {"version": True, "schema": True, "inputs": True, "outputs": True}

DATA_ITEM_KEYS = {"key": True, "value": True}

# True if required, defined by JSON schema
SCHEMA_ITEM_KEYS = {
    "key": True,
    "label": True,
    "description": True,
    "type": True,
    "displayOrder": True,
    "fileToKeyMap": False,
    "defaultValue": False,
    "widget": False,
}
# allowed types
TYPE_TO_PYTHON_TYPE_MAP = {
    "integer": {"type": int, "converter": int},
    "number": {"type": float, "converter": float},
    "boolean": {"type": bool, "converter": bool},
    "string": {"type": str, "converter": str},
}
FILE_TYPE_PREFIX = "data:"
