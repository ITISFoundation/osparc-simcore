"""Director service configuration
"""

import logging
import os

logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s-%(lineno)d: %(message)s'
    )

CONVERT_OLD_API = True
API_VERSION = "v0"

REGISTRY_AUTH = os.environ.get("REGISTRY_AUTH", False) in ["true", "True"]
REGISTRY_USER = os.environ.get("REGISTRY_USER", "")
REGISTRY_PW = os.environ.get("REGISTRY_PW", "")
REGISTRY_URL = os.environ.get("REGISTRY_URL", "")
REGISTRY_SSL = os.environ.get("REGISTRY_SSL", True)

POSTGRES_ENDPOINT = os.environ.get("POSTGRES_ENDPOINT", "")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "")

S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "")
