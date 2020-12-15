"""Takes care of the configurations.
"""
import os
from typing import Dict, Type

# required configurations
PROJECT_ID: str = os.environ.get("SIMCORE_PROJECT_ID", default="undefined")
NODE_UUID: str = os.environ.get("SIMCORE_NODE_UUID", default="undefined")
USER_ID: str = os.environ.get("SIMCORE_USER_ID", default="undefined")
STORAGE_ENDPOINT: str = os.environ.get("STORAGE_ENDPOINT", default="undefined")
STORAGE_VERSION: str = "v0"

POSTGRES_ENDPOINT: str = os.environ.get("POSTGRES_ENDPOINT", "postgres:5432")
POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "simcoredb")
POSTGRES_PW: str = os.environ.get("POSTGRES_PASSWORD", "simcore")
POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "simcore")

# overridable required configurations
STORE: str = os.environ.get("STORAGE_STORE_LOCATION_NAME", default="simcore.s3")
BUCKET: str = os.environ.get("S3_BUCKET_NAME", default="simcore")


# -------------------------------------------------------------------------
NODE_KEYS: Dict[str, bool] = {
    "schema": True,
    "inputs": True,
    "outputs": True,
}

DATA_ITEM_KEYS: Dict[str, bool] = {"key": True, "value": True}

# True if required, defined by JSON schema
SCHEMA_ITEM_KEYS: Dict[str, bool] = {
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
TYPE_TO_PYTHON_TYPE_MAP: Dict[str, Dict[str, Type]] = {
    "integer": {"type": int, "converter": int},
    "number": {"type": float, "converter": float},
    "boolean": {"type": bool, "converter": bool},
    "string": {"type": str, "converter": str},
}
FILE_TYPE_PREFIX: str = "data:"
