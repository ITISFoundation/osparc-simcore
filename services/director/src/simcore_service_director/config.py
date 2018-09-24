import logging
import os
from pathlib import Path

logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s-%(lineno)d: %(message)s'
    )

# FIXME: adapt to new config. Issue #195
CONVERT_OLD_API = True

OPEN_API_BASE_FOLDER = Path(__file__).parent / "oas3/v1"
OPEN_API_SPEC_FILE = "openapi.yaml"
JSON_SCHEMA_BASE_FOLDER = Path(__file__).parent / "oas3/v1/schemas"
NODE_JSON_SCHEMA_FILE = "node-meta-v0.0.1.json"

REGISTRY_AUTH = os.environ.get("REGISTRY_AUTH", False) in ["true", "True"]
REGISTRY_USER = os.environ.get("REGISTRY_USER", "")
REGISTRY_PW = os.environ.get("REGISTRY_PW", "")
REGISTRY_URL = os.environ.get("REGISTRY_URL", "")

POSTGRES_ENDPOINT = os.environ.get("POSTGRES_ENDPOINT", "")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "")

S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
