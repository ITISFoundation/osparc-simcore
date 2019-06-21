"""
   Facade to keep API LEGACY
"""
from simcore_postgres_models.tables.base import metadata
from simcore_postgres_models.webserver_tables import (ConfirmationAction,
                                                      UserRole, UserStatus,
                                                      confirmations, tokens,
                                                      users)

# TODO: roles table that maps every role with allowed tasks e.g. read/write,...??

__all__ = (
    "UserStatus", "UserRole", "ConfirmationAction",
    "users", "confirmations", "tokens",
    "metadata"
)
