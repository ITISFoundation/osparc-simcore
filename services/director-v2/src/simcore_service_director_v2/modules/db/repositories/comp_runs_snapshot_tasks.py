import logging

import sqlalchemy as sa
from models_library.projects_nodes_io import NodeID
from pydantic import PositiveInt
from simcore_postgres_database.utils_repos import (
    transaction_context,
)
from simcore_service_director_v2.models.comp_run_snapshot_tasks import (
    CompRunSnapshotTaskAtDBGet,
)
from sqlalchemy.ext.asyncio import AsyncConnection

from ..tables import comp_run_snapshot_tasks
from ._base import BaseRepository

logger = logging.getLogger(__name__)


_COMP_RUN_SNAPSHOT_TASKS_DB_COLS = (
    comp_run_snapshot_tasks.c.snapshot_task_id,
    comp_run_snapshot_tasks.c.run_id,
    comp_run_snapshot_tasks.c.project_id,
    comp_run_snapshot_tasks.c.node_id,
    comp_run_snapshot_tasks.c.node_class,
    comp_run_snapshot_tasks.c.job_id,
    comp_run_snapshot_tasks.c.internal_id,
    comp_run_snapshot_tasks.c.schema,
    comp_run_snapshot_tasks.c.inputs,
    comp_run_snapshot_tasks.c.outputs,
    comp_run_snapshot_tasks.c.run_hash,
    comp_run_snapshot_tasks.c.image,
    comp_run_snapshot_tasks.c.state,
    comp_run_snapshot_tasks.c.errors,
    comp_run_snapshot_tasks.c.progress,
    comp_run_snapshot_tasks.c.start,
    comp_run_snapshot_tasks.c.end,
    comp_run_snapshot_tasks.c.last_heartbeat,
    comp_run_snapshot_tasks.c.created,
    comp_run_snapshot_tasks.c.modified,
    comp_run_snapshot_tasks.c.pricing_info,
    comp_run_snapshot_tasks.c.hardware_info,
    comp_run_snapshot_tasks.c.submit,
)


class CompRunsSnapshotTasksRepository(BaseRepository):

    async def batch_create(
        self, *, data: list[dict]
    ) -> list[CompRunSnapshotTaskAtDBGet]:
        async with transaction_context(self.db_engine) as conn:

            result = await conn.execute(
                comp_run_snapshot_tasks.insert().returning(
                    *_COMP_RUN_SNAPSHOT_TASKS_DB_COLS
                ),
                data,
            )
            rows = result.fetchall()
            return [CompRunSnapshotTaskAtDBGet.model_validate(row) for row in rows]

    async def update_for_run_id_and_node_id(
        self,
        connection: AsyncConnection | None = None,
        *,
        run_id: PositiveInt,
        node_id: NodeID,
        data: dict,
    ) -> CompRunSnapshotTaskAtDBGet:
        async with transaction_context(self.db_engine, connection=connection) as conn:
            result = await conn.stream(
                comp_run_snapshot_tasks.update()
                .values(
                    **data,
                    modified=sa.func.now(),
                )
                .where(
                    (comp_run_snapshot_tasks.c.run_id == run_id)
                    & (comp_run_snapshot_tasks.c.node_id == f"{node_id}")
                )
                .returning(*_COMP_RUN_SNAPSHOT_TASKS_DB_COLS)
            )
            row = await result.one_or_none()
            if row is None:
                raise ValueError("improve message")
            return CompRunSnapshotTaskAtDBGet.model_validate(row)
