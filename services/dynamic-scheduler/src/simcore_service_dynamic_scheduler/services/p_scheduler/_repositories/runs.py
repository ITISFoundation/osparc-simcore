from typing import Final

import sqlalchemy as sa
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.models.p_scheduler import ps_runs
from simcore_postgres_database.utils_repos import pass_or_acquire_connection, transaction_context
from sqlalchemy.engine.row import Row

from ...base_repository import BaseRepository
from .._models import Run, RunId, WorkflowName

_START_WORKFLOW: Final[WorkflowName] = "START"
_STOP_WORKFLOW: Final[WorkflowName] = "STOP"


def _row_to_run(row: Row) -> Run:
    return Run(
        run_id=row.run_id,
        created_at=row.created_at,
        node_id=row.node_id,
        workflow_name=row.workflow_name,
        is_reverting=row.is_reverting,
        waiting_manual_intervention=row.waiting_manual_intervention,
    )


class RunsRepository(BaseRepository):
    async def get_run(self, run_id: RunId) -> Run | None:
        async with pass_or_acquire_connection(self.engine) as conn:
            result = await conn.execute(sa.select(ps_runs).where(ps_runs.c.run_id == run_id))
            row = result.first()
        if row is None:
            return None
        return _row_to_run(row)

    async def get_run_from_node_id(self, node_id: NodeID) -> Run | None:
        async with pass_or_acquire_connection(self.engine) as conn:
            result = await conn.execute(sa.select(ps_runs).where(ps_runs.c.node_id == node_id))
            row = result.first()
        if row is None:
            return None
        return _row_to_run(row)

    async def _create_run(self, *, node_id: NodeID, workflow_name: WorkflowName, is_reverting: bool) -> Run:
        async with transaction_context(self.engine) as conn:
            result = await conn.execute(
                ps_runs.insert()
                .values(
                    node_id=node_id,
                    workflow_name=workflow_name,
                    is_reverting=is_reverting,
                    waiting_manual_intervention=False,
                )
                .returning(sa.literal_column("*"))
            )
            row = result.one()
        return _row_to_run(row)

    async def create_from_start_request(self, node_id: NodeID) -> Run:
        return await self._create_run(node_id=node_id, workflow_name=_START_WORKFLOW, is_reverting=False)

    async def create_from_stop_request(self, node_id: NodeID) -> Run:
        return await self._create_run(node_id=node_id, workflow_name=_STOP_WORKFLOW, is_reverting=True)

    async def cancel_run(self, run_id: RunId) -> None:
        async with transaction_context(self.engine) as conn:
            await conn.execute(ps_runs.update().where(ps_runs.c.run_id == run_id).values(is_reverting=True))

    async def set_waiting_manual_intervention(self, run_id: RunId) -> None:
        async with transaction_context(self.engine) as conn:
            await conn.execute(
                ps_runs.update().where(ps_runs.c.run_id == run_id).values(waiting_manual_intervention=True)
            )

    async def remove_run(self, run_id: RunId) -> None:
        async with transaction_context(self.engine) as conn:
            await conn.execute(ps_runs.delete().where(ps_runs.c.run_id == run_id))

    async def get_all_runs(self) -> list[Run]:
        async with pass_or_acquire_connection(self.engine) as conn:
            result = await conn.execute(sa.select(ps_runs).order_by(ps_runs.c.created_at))
            rows = result.fetchall()
        return [_row_to_run(row) for row in rows]
