from typing import Any

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .models.user_preferences import (
    user_preferences_frontend,
    user_preferences_user_service,
)


class CouldNotCreateOrUpdateUserPreferenceError(Exception):
    ...


async def _save_preference(
    conn: SAConnection,
    table: sa.Table,
    *,
    user_id: int,
    product_name: str,
    preference_name: str,
    payload: Any,
):
    data: dict[str, Any] = {
        "user_id": user_id,
        "product_name": product_name,
        "preference_name": preference_name,
        "payload": payload,
    }

    insert_stmt = pg_insert(table).values(**data)
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[table.c.user_id, table.c.product_name, table.c.preference_name],
        set_=data,
    ).returning(sa.literal_column("*"))

    await conn.execute(upsert_stmt)


async def _load_preference_payload(
    conn: SAConnection,
    table: sa.Table,
    *,
    user_id: int,
    product_name: str,
    preference_name: str,
) -> Any | None:
    payload: Any | None = await conn.scalar(
        sa.select(table.c.payload).where(
            table.c.user_id == user_id,
            table.c.product_name == product_name,
            table.c.preference_name == preference_name,
        )
    )
    return payload


class UserPreferencesRepo:
    @staticmethod
    async def save_frontend_preference_payload(
        conn: SAConnection,
        *,
        user_id: int,
        product_name: str,
        preference_name: str,
        payload: Any,
    ) -> None:
        await _save_preference(
            conn,
            user_preferences_frontend,
            user_id=user_id,
            product_name=product_name,
            preference_name=preference_name,
            payload=payload,
        )

    @staticmethod
    async def load_frontend_preference_payload(
        conn: SAConnection, *, user_id: int, product_name: str, preference_name: Any
    ) -> Any | None:
        return await _load_preference_payload(
            conn,
            user_preferences_frontend,
            user_id=user_id,
            product_name=product_name,
            preference_name=preference_name,
        )

    @staticmethod
    async def save_user_service_preference_payload(
        conn: SAConnection,
        *,
        user_id: int,
        product_name: str,
        preference_name: str,
        payload: bytes,
    ) -> None:
        await _save_preference(
            conn,
            user_preferences_user_service,
            user_id=user_id,
            product_name=product_name,
            preference_name=preference_name,
            payload=payload,
        )

    @staticmethod
    async def load_user_service_preference_payload(
        conn: SAConnection, *, user_id: int, product_name: str, preference_name: Any
    ) -> bytes | None:
        return await _load_preference_payload(
            conn,
            user_preferences_user_service,
            user_id=user_id,
            product_name=product_name,
            preference_name=preference_name,
        )
