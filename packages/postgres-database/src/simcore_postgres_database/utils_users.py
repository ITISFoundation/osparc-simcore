""" Free functions, repository pattern, errors and data structures for the users resource
    i.e. models.users main table and all its relations
"""


import re
import secrets
import string
from datetime import datetime

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy

from .errors import UniqueViolation
from .models.users import UserRole, UserStatus, users


class BaseUserRepoError(Exception):
    pass


class UserNotFoundInRepoError(BaseUserRepoError):
    pass


def _generate_username_from_email(email: str) -> str:
    username = email.split("@")[0]

    # Remove any non-alphanumeric characters and convert to lowercase
    return re.sub(r"[^a-zA-Z0-9]", "", username).lower()


def _generate_random_chars(length=5) -> str:
    """returns `length` random digit character"""
    return "".join(secrets.choice(string.digits) for _ in range(length - 1))


class UsersRepo:
    @staticmethod
    async def new_user(
        conn: SAConnection,
        email: str,
        password_hash: str,
        status: UserStatus,
        expires_at: datetime | None,
    ) -> RowProxy:
        data = {
            "name": _generate_username_from_email(email),
            "email": email,
            "password_hash": password_hash,
            "status": status,
            "role": UserRole.USER,
            "expires_at": expires_at,
        }

        user_id = None
        while user_id is None:
            try:
                user_id = await conn.scalar(
                    users.insert().values(**data).returning(users.c.id)
                )
            except UniqueViolation:  # noqa: PERF203
                data["name"] = f'{data["name"]}_{_generate_random_chars()}'

        result = await conn.execute(
            sa.select(
                users.c.id,
                users.c.name,
                users.c.email,
                users.c.role,
                users.c.status,
            ).where(users.c.id == user_id)
        )
        row = await result.first()
        assert row  # nosec
        return row

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
    async def get_active_user_email(conn: SAConnection, user_id: int) -> str:
        value: str | None = await conn.scalar(
            sa.select(users.c.email).where(
                (users.c.status == UserStatus.ACTIVE) & (users.c.id == user_id)
            )
        )
        if value:
            assert isinstance(value, str)  # nosec
            return value

        raise UserNotFoundInRepoError
