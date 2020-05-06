"""
   Facade to keep API LEGACY
"""
from simcore_postgres_database.models.base import metadata
from simcore_postgres_database.webserver_models import (
    ConfirmationAction,
    UserRole,
    UserStatus,
    confirmations,
    tokens,
    users,
    groups,
    GroupType,
    user_to_groups,
    tags,
    study_tags,
    api_keys,
)

# TODO: roles table that maps every role with allowed tasks e.g. read/write,...??

__all__ = (
    "UserStatus",
    "UserRole",
    "ConfirmationAction",
    "users",
    "groups",
    "GroupType",
    "user_to_groups",
    "confirmations",
    "tokens",
    "metadata",
    "tags",
    "study_tags",
    "api_keys",
)
