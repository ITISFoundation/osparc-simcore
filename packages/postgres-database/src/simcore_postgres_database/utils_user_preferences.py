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


class BasePreferencesRepo:
    model: sa.Table

    @classmethod
    async def save(
        cls,
        conn: SAConnection,
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

        insert_stmt = pg_insert(cls.model).values(**data)
        upsert_stmt = insert_stmt.on_conflict_do_update(
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
        conn: SAConnection,
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


class UserServicesUserPreferencesRepo(BasePreferencesRepo):
    model = user_preferences_user_service
