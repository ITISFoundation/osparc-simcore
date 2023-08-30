import json
from typing import Any

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .models.user_preferences import user_preferences


class CouldNotCreateOrUpdateUserPreferenceError(Exception):
    ...


class UserPreferenceNameHelper:
    @classmethod
    def get_preference_name(
        cls, user_id: int, preference_name: str, product_name: str
    ) -> str:
        # NOTE: key is encoded with a minimal structure, allows for
        # 100% certainty when decoding in the future if needed
        return json.dumps([user_id, preference_name, product_name])


class UserPreferencesRepo:
    @staticmethod
    async def save_preference(
        conn: SAConnection,
        *,
        user_id: int,
        preference_name: str,
        product_name: str,
        payload: bytes,
    ) -> None:
        user_preference_name = UserPreferenceNameHelper.get_preference_name(
            user_id, preference_name, product_name
        )

        data: dict[str, Any] = {
            "user_preference_name": user_preference_name,
            "user_id": user_id,
            "payload": payload,
        }

        insert_stmt = pg_insert(user_preferences).values(**data)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[user_preferences.c.user_preference_name],
            set_=data,
        ).returning(sa.literal_column("*"))

        await conn.execute(upsert_stmt)

    @staticmethod
    async def get_preference_payload(
        conn: SAConnection, *, user_id: int, preference_name: str, product_name: str
    ) -> bytes | None:
        user_preference_name = UserPreferenceNameHelper.get_preference_name(
            user_id, preference_name, product_name
        )
        payload: bytes | None = await conn.scalar(
            sa.select(user_preferences.c.payload).where(
                user_preferences.c.user_preference_name == user_preference_name
            )
        )
        return payload
