"""
NOTE: Coupling with user's plugin api modules should be added here to avoid cyclic dependencies
"""

from collections.abc import Mapping
from typing import Any

from ..users.schemas import convert_user_db_to_schema


def convert_user_in_group_to_schema(user: Mapping[str, Any]) -> dict[str, str]:
    group_user = convert_user_db_to_schema(user)
    group_user.pop("role")
    group_user["accessRights"] = user["access_rights"]
    group_user["gid"] = user["primary_gid"]
    return group_user
