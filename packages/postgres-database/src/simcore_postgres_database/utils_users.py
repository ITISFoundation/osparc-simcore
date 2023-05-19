""" Free functions, repository pattern, errors and data structures for the users resource
    i.e. models.users main table and all its relations
"""

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from models_library.users import UserID

from .models.users import UserRole, users


class BaseUserRepoError(Exception):
    pass


class UserNotFoundInRepoError(BaseUserRepoError):
    pass


class UsersRepo:
    async def get_role(self, conn: SAConnection, user_id: UserID) -> UserRole:
        if value := await conn.scalar(
            sa.select(users.c.role).where(users.c.id == user_id)
        ):
            return UserRole(value)
        raise UserNotFoundInRepoError()

    async def get_email(self, conn: SAConnection, user_id: UserID) -> str:
        if value := await conn.scalar(
            sa.select(users.c.email).where(users.c.id == user_id)
        ):
            return str(value)
        raise UserNotFoundInRepoError()
