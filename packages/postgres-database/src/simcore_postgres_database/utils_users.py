""" Free functions, repository pattern, errors and data structures for the users resource
    i.e. models.users main table and all its relations
"""


import sqlalchemy as sa
from aiopg.sa.connection import SAConnection

from .models.users import UserRole, users


class BaseUserRepoError(Exception):
    pass


class UserNotFoundInRepoError(BaseUserRepoError):
    pass


class UsersRepo:
    @staticmethod
    async def get_role(conn: SAConnection, user_id: int) -> UserRole:
        value: UserRole | None = await conn.scalar(
            sa.select(users.c.role).where(users.c.id == user_id)
        )
        if value:
            assert isinstance(value, UserRole)  # nosec
            return UserRole(value)

        raise UserNotFoundInRepoError

    @staticmethod
    async def get_email(conn: SAConnection, user_id: int) -> str:
        value: str | None = await conn.scalar(
            sa.select(users.c.email).where(users.c.id == user_id)
        )
        if value:
            assert isinstance(value, str)  # nosec
            return value

        raise UserNotFoundInRepoError

    @staticmethod
    async def get_primary_group_id(conn: SAConnection, user_id: int) -> int:
        value: str | None = await conn.scalar(
            sa.select(users.c.primary_gid).where(users.c.id == user_id)
        )
        if value:
            assert isinstance(value, int)  # nosec
            return value

        raise UserNotFoundInRepoError
