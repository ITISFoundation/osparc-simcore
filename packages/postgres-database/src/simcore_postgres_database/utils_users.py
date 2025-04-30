"""Free functions, repository pattern, errors and data structures for the users resource
i.e. models.users main table and all its relations
"""

import re
import secrets
import string
from datetime import datetime
from typing import Any, Final

import sqlalchemy as sa
from common_library.async_tools import maybe_await
from sqlalchemy import Column

from ._protocols import DBConnection
from .aiopg_errors import UniqueViolation
from .models.users import UserRole, UserStatus, users
from .models.users_details import users_pre_registration_details


class BaseUserRepoError(Exception):
    pass


class UserNotFoundInRepoError(BaseUserRepoError):
    pass


# NOTE: see MyProfilePatch.user_name
MIN_USERNAME_LEN: Final[int] = 4


def _generate_random_chars(length: int = MIN_USERNAME_LEN) -> str:
    """returns `length` random digit character"""
    return "".join(secrets.choice(string.digits) for _ in range(length))


def _generate_username_from_email(email: str) -> str:
    username = email.split("@")[0]

    # Remove any non-alphanumeric characters and convert to lowercase
    username = re.sub(r"[^a-zA-Z0-9]", "", username).lower()

    # Ensure the username is at least 4 characters long
    if len(username) < MIN_USERNAME_LEN:
        username += _generate_random_chars(length=MIN_USERNAME_LEN - len(username))

    return username


def generate_alternative_username(username: str) -> str:
    return f"{username}_{_generate_random_chars()}"


class UsersRepo:
    @staticmethod
    async def new_user(
        conn: DBConnection,
        email: str,
        password_hash: str,
        status: UserStatus,
        expires_at: datetime | None,
    ) -> Any:
        data: dict[str, Any] = {
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
            except UniqueViolation:
                data["name"] = generate_alternative_username(data["name"])

        result = await conn.execute(
            sa.select(
                users.c.id,
                users.c.name,
                users.c.email,
                users.c.role,
                users.c.status,
            ).where(users.c.id == user_id)
        )
        row = await maybe_await(result.first())
        from aiopg.sa.result import RowProxy

        assert isinstance(row, RowProxy)  # nosec
        return row

    @staticmethod
    async def join_and_update_from_pre_registration_details(
        conn: DBConnection, new_user_id: int, new_user_email: str
    ) -> None:
        """After a user is created, it can be associated with information provided during invitation

        WARNING: Use ONLY upon new user creation. It might override user_details.user_id, users.first_name, users.last_name etc if already applied
        or changes happen in users table
        """
        assert new_user_email  # nosec
        assert new_user_id > 0  # nosec

        # link both tables first
        result = await conn.execute(
            users_pre_registration_details.update()
            .where(users_pre_registration_details.c.pre_email == new_user_email)
            .values(user_id=new_user_id)
        )

        from aiopg.sa.result import ResultProxy

        assert isinstance(result, ResultProxy)  # nosec

        if result.rowcount:
            pre_columns = (
                users_pre_registration_details.c.pre_first_name,
                users_pre_registration_details.c.pre_last_name,
                # NOTE: pre_phone is not copied since it has to be validated. Otherwise, if
                # phone is wrong, currently user won't be able to login!
            )

            assert {c.name for c in pre_columns} == {  # nosec
                c.name
                for c in users_pre_registration_details.columns
                if c
                not in (
                    users_pre_registration_details.c.pre_email,
                    users_pre_registration_details.c.pre_phone,
                )
                and c.name.startswith("pre_")
            }, "Different pre-cols detected. This code might need an update update"

            result = await conn.execute(
                sa.select(*pre_columns).where(
                    users_pre_registration_details.c.pre_email == new_user_email
                )
            )
            if details := await maybe_await(result.fetchone()):
                await conn.execute(
                    users.update()
                    .where(users.c.id == new_user_id)
                    .values(
                        first_name=details.pre_first_name,  # type: ignore[union-attr]
                        last_name=details.pre_last_name,  # type: ignore[union-attr]
                    )
                )

    @staticmethod
    def get_billing_details_query(user_id: int):
        return (
            sa.select(
                users.c.first_name,
                users.c.last_name,
                users_pre_registration_details.c.institution,
                users_pre_registration_details.c.address,
                users_pre_registration_details.c.city,
                users_pre_registration_details.c.state,
                users_pre_registration_details.c.country,
                users_pre_registration_details.c.postal_code,
                users.c.phone,
            )
            .select_from(
                users.join(
                    users_pre_registration_details,
                    users.c.id == users_pre_registration_details.c.user_id,
                )
            )
            .where(users.c.id == user_id)
        )

    @staticmethod
    async def get_billing_details(conn: DBConnection, user_id: int) -> Any | None:
        result = await conn.execute(
            UsersRepo.get_billing_details_query(user_id=user_id)
        )
        return await maybe_await(result.fetchone())

    @staticmethod
    async def get_role(conn: DBConnection, user_id: int) -> UserRole:
        value: UserRole | None = await conn.scalar(
            sa.select(users.c.role).where(users.c.id == user_id)
        )
        if value:
            assert isinstance(value, UserRole)  # nosec
            return UserRole(value)

        raise UserNotFoundInRepoError

    @staticmethod
    async def get_email(conn: DBConnection, user_id: int) -> str:
        value: str | None = await conn.scalar(
            sa.select(users.c.email).where(users.c.id == user_id)
        )
        if value:
            assert isinstance(value, str)  # nosec
            return value

        raise UserNotFoundInRepoError

    @staticmethod
    async def get_active_user_email(conn: DBConnection, user_id: int) -> str:
        value: str | None = await conn.scalar(
            sa.select(users.c.email).where(
                (users.c.status == UserStatus.ACTIVE) & (users.c.id == user_id)
            )
        )
        if value is not None:
            assert isinstance(value, str)  # nosec
            return value

        raise UserNotFoundInRepoError

    @staticmethod
    async def is_email_used(conn: DBConnection, email: str) -> bool:
        email = email.lower()

        registered = await conn.scalar(
            sa.select(users.c.id).where(users.c.email == email)
        )
        if registered:
            return True

        pre_registered = await conn.scalar(
            sa.select(users_pre_registration_details.c.user_id).where(
                users_pre_registration_details.c.pre_email == email
            )
        )
        return bool(pre_registered)


#
# Privacy settings
#


def is_private(hide_attribute: Column, caller_id: int):
    return hide_attribute.is_(True) & (users.c.id != caller_id)


def is_public(hide_attribute: Column, caller_id: int):
    return hide_attribute.is_(False) | (users.c.id == caller_id)


def visible_user_profile_cols(caller_id: int, *, username_label: str):
    """Returns user profile columns with visibility constraints applied based on privacy settings."""
    return (
        sa.case(
            (
                is_private(users.c.privacy_hide_username, caller_id),
                None,
            ),
            else_=users.c.name,
        ).label(username_label),
        sa.case(
            (
                is_private(users.c.privacy_hide_email, caller_id),
                None,
            ),
            else_=users.c.email,
        ).label("email"),
        sa.case(
            (
                is_private(users.c.privacy_hide_fullname, caller_id),
                None,
            ),
            else_=users.c.first_name,
        ).label("first_name"),
        sa.case(
            (
                is_private(users.c.privacy_hide_fullname, caller_id),
                None,
            ),
            else_=users.c.last_name,
        ).label("last_name"),
    )
