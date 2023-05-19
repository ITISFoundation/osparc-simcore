""" Free functions, repository pattern, errors and data structures for the users resource
    i.e. models.users main table and all its relations
"""

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from models_library.users import UserID

from .models.users import UserRole, users


#
# Errors
#
class BaseUserRepoError(Exception):
    pass


class UserNotFoundInRepoError(BaseUserRepoError):
    pass


class UsersRepo:
    async def _get_or_raise(self, conn: SAConnection, user_id: UserID, column):
        value = await conn.scalar(sa.select(column).where(users.c.id == user_id))
        if value is None:
            raise UserNotFoundInRepoError()
        return value

    async def get_role(self, conn: SAConnection, user_id: UserID) -> UserRole:
        value = await self._get_or_raise(conn, user_id, users.c.role)
        return UserRole(value)

    async def get_email(self, conn: SAConnection, user_id: UserID) -> str:
        value = await self._get_or_raise(conn, user_id, users.c.email)
        return str(value)
