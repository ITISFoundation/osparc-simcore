from typing import TypeAlias

from simcore_postgres_database.models.api_keys import api_keys
from simcore_postgres_database.models.groups import GroupType, groups, user_to_groups
from simcore_postgres_database.models.users import UserRole, UserStatus, users

metadata: TypeAlias = api_keys.metadata

assert api_keys  # nosec
assert groups  # nosec
assert GroupType  # nosec
assert user_to_groups  # nosec
assert UserRole  # nosec
assert users  # nosec
assert UserStatus  # nosec

__all__: tuple[str, ...] = (
    "api_keys",
    "groups",
    "GroupType",
    "metadata",
    "user_to_groups",
    "UserRole",
    "users",
    "UserStatus",
)
