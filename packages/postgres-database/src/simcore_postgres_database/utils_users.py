"""Free functions, repository pattern, errors and data structures for the users resource
i.e. models.users main table and all its relations
"""

import re
import secrets
import string
from dataclasses import dataclass, fields
from datetime import datetime
from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.engine.result import Row
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio.engine import AsyncConnection, AsyncEngine
from sqlalchemy.sql import Select

from .models.users import UserRole, UserStatus, users
from .models.users_details import users_pre_registration_details
from .models.users_secrets import users_secrets
from .utils_repos import pass_or_acquire_connection, transaction_context


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


@dataclass(frozen=True)
class UserRow:
    id: int
    name: str
    email: str
    role: UserRole
    status: UserStatus
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None

    @classmethod
    def from_row(cls, row: Row) -> "UserRow":
        return cls(**{f.name: getattr(row, f.name) for f in fields(cls)})


class UsersRepo:
    _user_columns = (
        users.c.id,
        users.c.name,
        users.c.email,
        users.c.role,
        users.c.status,
        users.c.first_name,
        users.c.last_name,
        users.c.phone,
    )

    def __init__(self, engine: AsyncEngine):
        self._engine = engine

    async def _get_scalar_or_raise(
        self,
        query: Select,
        connection: AsyncConnection | None = None,
    ) -> Any:
        """Execute a scalar query and raise UserNotFoundInRepoError if no value found."""
        async with pass_or_acquire_connection(self._engine, connection) as conn:
            value = await conn.scalar(query)
            if value is not None:
                return value
            raise UserNotFoundInRepoError

    async def new_user(
        self,
        connection: AsyncConnection | None = None,
        *,
        email: str,
        password_hash: str,
        status: UserStatus,
        expires_at: datetime | None,
        role: UserRole = UserRole.USER,
    ) -> UserRow:
        user_data: dict[str, Any] = {
            "name": _generate_username_from_email(email),
            "email": email,
            "status": status,
            "role": role,
            "expires_at": expires_at,
        }

        user_id = None
        while user_id is None:
            try:
                async with transaction_context(self._engine, connection) as conn:
                    # Insert user record
                    user_id = await conn.scalar(
                        users.insert().values(**user_data).returning(users.c.id)
                    )

                    # Insert password hash into users_secrets table
                    await conn.execute(
                        users_secrets.insert().values(
                            user_id=user_id,
                            password_hash=password_hash,
                        )
                    )
            except IntegrityError:
                user_data["name"] = generate_alternative_username(user_data["name"])
                user_id = None  # Reset to retry with new username

        async with pass_or_acquire_connection(self._engine, connection) as conn:
            result = await conn.execute(
                sa.select(*self._user_columns).where(users.c.id == user_id)
            )
            return UserRow.from_row(result.one())

    async def link_and_update_user_from_pre_registration(
        self,
        connection: AsyncConnection | None = None,
        *,
        new_user_id: int,
        new_user_email: str,
    ) -> None:
        """After a user is created, it can be associated with information provided during invitation

        Links ALL pre-registrations for the given email to the user, regardless of product_name.

        WARNING: Use ONLY upon new user creation. It might override user_details.user_id,
        users.first_name, users.last_name etc if already applied or changes happen in users table
        """
        assert new_user_email  # nosec
        assert new_user_id > 0  # nosec

        async with transaction_context(self._engine, connection) as conn:
            # Link ALL pre-registrations for this email to the user
            result = await conn.execute(
                users_pre_registration_details.update()
                .where(users_pre_registration_details.c.pre_email == new_user_email)
                .values(user_id=new_user_id)
            )

            # COPIES some pre-registration details to the users table
            pre_columns = (
                users_pre_registration_details.c.pre_first_name,
                users_pre_registration_details.c.pre_last_name,
                # NOTE: pre_phone is not copied since it has to be validated.
                # Otherwise, if phone is wrong, currently user won't be able to login!
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

            # Get the most recent pre-registration data to copy to users table
            result = await conn.execute(
                sa.select(*pre_columns)
                .where(users_pre_registration_details.c.pre_email == new_user_email)
                .order_by(users_pre_registration_details.c.created.desc())
                .limit(1)
            )
            if pre_registration_details_data := result.one_or_none():
                await conn.execute(
                    users.update()
                    .where(users.c.id == new_user_id)
                    .values(
                        first_name=pre_registration_details_data.pre_first_name,
                        last_name=pre_registration_details_data.pre_last_name,
                    )
                )

    async def get_role(
        self, connection: AsyncConnection | None = None, *, user_id: int
    ) -> UserRole:
        value = await self._get_scalar_or_raise(
            sa.select(users.c.role).where(users.c.id == user_id),
            connection=connection,
        )
        assert isinstance(value, UserRole)  # nosec
        return UserRole(value)

    async def get_email(
        self, connection: AsyncConnection | None = None, *, user_id: int
    ) -> str:
        value = await self._get_scalar_or_raise(
            sa.select(users.c.email).where(users.c.id == user_id),
            connection=connection,
        )
        assert isinstance(value, str)  # nosec
        return value

    async def get_active_user_email(
        self, connection: AsyncConnection | None = None, *, user_id: int
    ) -> str:
        value = await self._get_scalar_or_raise(
            sa.select(users.c.email).where(
                (users.c.status == UserStatus.ACTIVE) & (users.c.id == user_id)
            ),
            connection=connection,
        )
        assert isinstance(value, str)  # nosec
        return value

    async def get_password_hash(
        self, connection: AsyncConnection | None = None, *, user_id: int
    ) -> str:
        value = await self._get_scalar_or_raise(
            sa.select(users_secrets.c.password_hash).where(
                users_secrets.c.user_id == user_id
            ),
            connection=connection,
        )
        assert isinstance(value, str)  # nosec
        return value

    async def get_user_by_email_or_none(
        self, connection: AsyncConnection | None = None, *, email: str
    ) -> UserRow | None:
        async with pass_or_acquire_connection(self._engine, connection) as conn:
            result = await conn.execute(
                sa.select(*self._user_columns).where(users.c.email == email.lower())
            )
            row = result.one_or_none()
            return UserRow.from_row(row) if row else None

    async def get_user_by_id_or_none(
        self, connection: AsyncConnection | None = None, *, user_id: int
    ) -> UserRow | None:
        async with pass_or_acquire_connection(self._engine, connection) as conn:
            result = await conn.execute(
                sa.select(*self._user_columns).where(users.c.id == user_id)
            )
            row = result.one_or_none()
            return UserRow.from_row(row) if row else None

    async def update_user_phone(
        self, connection: AsyncConnection | None = None, *, user_id: int, phone: str
    ) -> None:
        async with transaction_context(self._engine, connection) as conn:
            await conn.execute(
                users.update().where(users.c.id == user_id).values(phone=phone)
            )

    async def update_user_password_hash(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: int,
        password_hash: str,
    ) -> None:
        async with transaction_context(self._engine, connection) as conn:
            await self.get_password_hash(
                connection=conn, user_id=user_id
            )  # ensure user exists
            await conn.execute(
                users_secrets.update()
                .where(users_secrets.c.user_id == user_id)
                .values(password_hash=password_hash)
            )

    async def is_email_used(
        self, connection: AsyncConnection | None = None, *, email: str
    ) -> bool:

        async with pass_or_acquire_connection(self._engine, connection) as conn:

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

    async def get_billing_details(
        self, connection: AsyncConnection | None = None, *, user_id: int
    ) -> Any | None:
        async with pass_or_acquire_connection(self._engine, connection) as conn:
            result = await conn.execute(
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
                .order_by(users_pre_registration_details.c.created.desc())
                .limit(1)
                # NOTE: might want to copy billing details to users table??
            )
            return result.one_or_none()


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
