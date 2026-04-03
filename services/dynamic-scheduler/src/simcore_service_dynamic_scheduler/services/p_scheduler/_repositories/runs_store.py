from typing import Any

import sqlalchemy as sa
from simcore_postgres_database.models.p_scheduler import ps_run_store
from simcore_postgres_database.utils_repos import pass_or_acquire_connection, transaction_context
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ...base_repository import BaseRepository
from .._models import RunId


class RunsStoreRepository(BaseRepository):
    async def get_from_store(self, run_id: RunId, keys: set[str]) -> dict[str, Any]:
        if not keys:
            return {}

        async with pass_or_acquire_connection(self.engine) as conn:
            result = await conn.execute(
                sa.select(ps_run_store.c.key, ps_run_store.c.value).where(
                    (ps_run_store.c.run_id == run_id) & (ps_run_store.c.key.in_(keys))
                )
            )
            rows = result.fetchall()
        return {row.key: row.value for row in rows}

    async def set_to_store(self, run_id: RunId, data: dict[str, Any]) -> None:
        if not data:
            return
        async with transaction_context(self.engine) as conn:
            for key, value in data.items():
                insert_stmt = pg_insert(ps_run_store).values(run_id=run_id, key=key, value=value)
                upsert_stmt = insert_stmt.on_conflict_do_update(
                    constraint=f"pk_{ps_run_store.name}",
                    set_={
                        "value": insert_stmt.excluded.value,
                        "updated_at": sa.func.now(),
                    },
                )
                await conn.execute(upsert_stmt)
