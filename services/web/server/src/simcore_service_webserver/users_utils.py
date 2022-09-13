import logging
from typing import Any, Mapping, Optional

from .utils import gravatar_hash

logger = logging.getLogger(__name__)


def convert_user_db_to_schema(
    row: Mapping[str, Any], prefix: Optional[str] = ""
) -> dict[str, Any]:
    parts = row[f"{prefix}name"].split(".") + [""]
    data = {
        "id": row[f"{prefix}id"],
        "login": row[f"{prefix}email"],
        "first_name": parts[0],
        "last_name": parts[1],
        "role": row[f"{prefix}role"].name.capitalize(),
        "gravatar_id": gravatar_hash(row[f"{prefix}email"]),
    }

    if expires_at := row[f"{prefix}expires_at"]:
        data["expires_at"] = expires_at
    return data
