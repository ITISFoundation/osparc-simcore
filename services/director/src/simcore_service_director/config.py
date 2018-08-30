from pathlib import Path
import os

CONVERT_OLD_API = True

OPEN_API_BASE_FOLDER = Path(__file__).parent / ".openapi/v1"
OPEN_API_SPEC_FILE = "director_api.yaml"
JSON_SCHEMA_BASE_FOLDER = Path(__file__).parent / ".openapi/v1"
NODE_JSON_SCHEMA_FILE = "node-meta-v0.0.1.json"

REGISTRY_AUTH = os.environ.get("REGISTRY_AUTH", False) in ["true", "True"]
REGISTRY_USER = os.environ.get("REGISTRY_USER", "")
REGISTRY_PW = os.environ.get("REGISTRY_PW", "")
REGISTRY_URL = os.environ.get("REGISTRY_URL", "")