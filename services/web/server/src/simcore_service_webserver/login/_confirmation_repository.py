import logging
from typing import Any

import sqlalchemy as sa
from models_library.users import UserID
from servicelib.utils_secrets import generate_passcode
from simcore_postgres_database.models.confirmations import confirmations
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.base_repository import BaseRepository
from ._models import ActionLiteralStr, Confirmation

_logger = logging.getLogger(__name__)


def _to_domain(confirmation_row: Row) -> Confirmation:
    return Confirmation.model_validate(
        {
            "code": confirmation_row.code,
            "user_id": confirmation_row.user_id,
            "action": confirmation_row.action.value,  # conversion to literal string
            "data": confirmation_row.data,
            "created_at": confirmation_row.created,  # renames
        }
    )


class ConfirmationRepository(BaseRepository):
    async def create_confirmation(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        action: ActionLiteralStr,
        data: str | None = None,
    ) -> Confirmation:
        """Create a new confirmation token for a user action."""

        async with transaction_context(self.engine, connection) as conn:
            # We want the same connection checking uniqueness and inserting
            while True:  # Generate unique code
                # NOTE: use only numbers since front-end does not handle well url encoding
                numeric_code: str = generate_passcode(20)

                # Check if code already exists
                check_query = sa.select(confirmations.c.code).where(
                    confirmations.c.code == numeric_code
                )
                result = await conn.execute(check_query)
                if result.one_or_none() is None:
                    break

            # Insert confirmation
            insert_query = (
                sa.insert(confirmations)
                .values(
                    code=numeric_code,
                    user_id=user_id,
                    action=action,
                    data=data,
                )
                .returning(*confirmations.c)
            )

            result = await conn.execute(insert_query)
            row = result.one()
            return _to_domain(row)

    async def get_confirmation(
        self,
        connection: AsyncConnection | None = None,
        *,
        filter_dict: dict[str, Any],
    ) -> Confirmation | None:
        """Get a confirmation by filter criteria."""
        # Handle legacy "user" key
        if "user" in filter_dict:
            filter_dict["user_id"] = filter_dict.pop("user")["id"]

        # Build where conditions
        where_conditions = []
        for key, value in filter_dict.items():
            if hasattr(confirmations.c, key):
                where_conditions.append(getattr(confirmations.c, key) == value)

        query = sa.select(*confirmations.c).where(sa.and_(*where_conditions))

        async with pass_or_acquire_connection(self.engine, connection) as conn:
            result = await conn.execute(query)
            if row := result.one_or_none():
                return _to_domain(row)
            return None

    async def delete_confirmation(
        self,
        connection: AsyncConnection | None = None,
        *,
        confirmation: Confirmation,
    ) -> None:
        """Delete a confirmation token."""
        query = sa.delete(confirmations).where(
            confirmations.c.code == confirmation.code
        )

        async with transaction_context(self.engine, connection) as conn:
            await conn.execute(query)

    async def delete_confirmation_and_user(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        confirmation: Confirmation,
    ) -> None:
        """Atomically delete confirmation and user."""
        async with transaction_context(self.engine, connection) as conn:
            # Delete confirmation
            await conn.execute(
                sa.delete(confirmations).where(
                    confirmations.c.code == confirmation.code
                )
            )

            # Delete user
            await conn.execute(sa.delete(users).where(users.c.id == user_id))

    async def delete_confirmation_and_update_user(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        updates: dict[str, Any],
        confirmation: Confirmation,
    ) -> None:
        """Atomically delete confirmation and update user."""
        async with transaction_context(self.engine, connection) as conn:
            # Delete confirmation
            await conn.execute(
                sa.delete(confirmations).where(
                    confirmations.c.code == confirmation.code
                )
            )

            # Update user
            await conn.execute(
                sa.update(users).where(users.c.id == user_id).values(**updates)
            )
