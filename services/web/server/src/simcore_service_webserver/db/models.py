"""
   Facade to keep API LEGACY
"""
from simcore_postgres_database.models.base import metadata
from simcore_postgres_database.webserver_models import (
    ConfirmationAction,
    GroupType,
    UserRole,
    UserStatus,
    api_keys,
    confirmations,
    group_classifiers,
    groups,
    products,
    projects,
    projects_to_wallet,
    scicrunch_resources,
    study_tags,
    tags,
    tokens,
    user_to_groups,
    users,
)

__all__: tuple[str, ...] = (
    "api_keys",
    "ConfirmationAction",
    "confirmations",
    "group_classifiers",
    "groups",
    "GroupType",
    "metadata",
    "products",
    "projects",
    "scicrunch_resources",
    "study_tags",
    "tags",
    "tokens",
    "user_to_groups",
    "UserRole",
    "users",
    "UserStatus",
    "projects_to_wallet",
)
# nopycln: file
