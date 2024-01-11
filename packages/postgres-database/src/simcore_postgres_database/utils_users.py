""" Free functions, repository pattern, errors and data structures for the users resource
    i.e. models.users main table and all its relations
"""


import random
import re

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection

from .models.users import UserRole, users


class BaseUserRepoError(Exception):
    pass


class UserNotFoundInRepoError(BaseUserRepoError):
    pass


def generate_username_from_email(email: str) -> str:
    username = email.split("@")[0]

    # Remove any non-alphanumeric characters and convert to lowercase
    return re.sub(r"[^a-zA-Z0-9]", "", username).lower()


def generate_random_suffix() -> str:
    return f"_{random.randint(1000, 9999)}"  # noqa: S311


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
