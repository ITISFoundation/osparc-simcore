from pathlib import Path

CONVERT_OLD_API = True

OPEN_API_BASE_FOLDER = Path(__file__).parent / ".openapi/v1"
OPEN_API_SPEC_FILE = "director_api.yaml"
JSON_SCHEMA_BASE_FOLDER = Path(__file__).parent / ".openapi/v1"
NODE_JSON_SCHEMA_FILE = "node-meta-v0.0.1.json"