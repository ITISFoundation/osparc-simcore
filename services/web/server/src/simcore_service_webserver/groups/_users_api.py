"""
NOTE: Coupling with user's plugin api modules should be added here to avoid cyclic dependencies
"""

from collections.abc import Mapping
from typing import Any

from ..utils import gravatar_hash


def convert_user_in_group_to_schema(user: Mapping[str, Any]) -> dict[str, str]:

    group_user = {
        "id": user["id"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "login": user["email"],
        "gravatar_id": gravatar_hash(user["email"]),
    }
    group_user["accessRights"] = user["access_rights"]
    group_user["gid"] = user["primary_gid"]
    return group_user
