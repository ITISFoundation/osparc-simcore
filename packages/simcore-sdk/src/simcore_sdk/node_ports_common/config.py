"""Takes care of the configurations.
"""
import os
from typing import Final

from .constants import MINUTE

# required configurations
STORAGE_ENDPOINT: str = os.environ.get("STORAGE_ENDPOINT", default="undefined")
STORAGE_VERSION: str = "v0"

POSTGRES_ENDPOINT: str = os.environ.get("POSTGRES_ENDPOINT", "postgres:5432")
POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "simcoredb")
POSTGRES_PW: str = os.environ.get("POSTGRES_PASSWORD", "simcore")
POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "simcore")

STORAGE_MULTIPART_UPLOAD_COMPLETION_TIMEOUT_S: Final[int] = int(
    os.environ.get(
        "STORAGE_MULTIPART_UPLOAD_COMPLETION_TIMEOUT_S", default=f"{5 * MINUTE}"
    )
)
