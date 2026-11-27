from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import Insert as PostgresInsert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from .models.user_preferences import (
    user_preferences_frontend,
    user_preferences_user_service,
)


class CouldNotCreateOrUpdateUserPreferenceError(Exception): ...


class BasePreferencesRepo:
    model: sa.Table

    @classmethod
    async def save(
        cls,
        conn: AsyncConnection,
        *,
        user_id: int,
        product_name: str,
        preference_name: str,
        payload: Any,
    ) -> None:
        data: dict[str, Any] = {
            "user_id": user_id,
            "product_name": product_name,
            "preference_name": preference_name,
            "payload": payload,
        }

        insert_stmt: PostgresInsert = pg_insert(cls.model).values(**data)
        upsert_stmt: Any = insert_stmt.on_conflict_do_update(
            index_elements=[
                cls.model.c.user_id,
                cls.model.c.product_name,
                cls.model.c.preference_name,
            ],
            set_=data,
        ).returning(sa.literal_column("*"))

        await conn.execute(upsert_stmt)

    @classmethod
    async def load(
        cls,
        conn: AsyncConnection,
        *,
        user_id: int,
        product_name: str,
        preference_name: Any,
    ) -> Any | None:
        payload: Any | None = await conn.scalar(
            sa.select(cls.model.c.payload).where(
                cls.model.c.user_id == user_id,
                cls.model.c.product_name == product_name,
                cls.model.c.preference_name == preference_name,
            )
        )
        return payload


class FrontendUserPreferencesRepo(BasePreferencesRepo):
    model = user_preferences_frontend

    @classmethod
    async def save_if_value_unchanged(
        cls,
        conn: AsyncConnection,
        *,
        user_id: int,
        product_name: str,
        preference_name: str,
        payload: dict[str, Any],
        expected_value: Any,
    ) -> bool:
        """Update an existing preference only when its stored value matches."""
        stmt = (
            sa.update(cls.model)
            .where(
                cls.model.c.user_id == user_id,
                cls.model.c.product_name == product_name,
                cls.model.c.preference_name == preference_name,
                sa.cast(cls.model.c.payload, JSONB)["value"] == sa.literal(expected_value, type_=JSONB),
            )
            .values(payload=payload)
            .returning(cls.model.c.user_id)
        )
        return await conn.scalar(stmt) is not None


class UserServicesUserPreferencesRepo(BasePreferencesRepo):
    model = user_preferences_user_service
