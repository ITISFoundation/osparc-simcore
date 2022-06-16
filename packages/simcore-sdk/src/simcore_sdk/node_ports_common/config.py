"""Takes care of the configurations.
"""
import os

# required configurations
STORAGE_ENDPOINT: str = os.environ.get("STORAGE_ENDPOINT", default="undefined")
STORAGE_VERSION: str = "v0"

POSTGRES_ENDPOINT: str = os.environ.get("POSTGRES_ENDPOINT", "postgres:5432")
POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "simcoredb")
POSTGRES_PW: str = os.environ.get("POSTGRES_PASSWORD", "simcore")
POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "simcore")
