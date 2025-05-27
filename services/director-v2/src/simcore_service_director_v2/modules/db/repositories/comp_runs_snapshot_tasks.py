import logging

from simcore_postgres_database.utils_comp_run_snapshot_tasks import (
    COMP_RUN_SNAPSHOT_TASKS_DB_COLS,
)
from simcore_postgres_database.utils_repos import (
    transaction_context,
)

from ..tables import comp_run_snapshot_tasks
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class CompRunsSnapshotTasksRepository(BaseRepository):

    async def batch_create(
        self, *, data: list[dict]
    ) -> None:  # list[CompRunSnapshotTaskAtDBGet]:
        async with transaction_context(self.db_engine) as conn:

            try:
                await conn.execute(
                    comp_run_snapshot_tasks.insert().returning(
                        *COMP_RUN_SNAPSHOT_TASKS_DB_COLS
                    ),
                    data,
                )
                # rows = result.fetchall()
                # return [CompRunSnapshotTaskAtDBGet.model_validate(row) for row in rows]
            except Exception as e:
                logger.error(
                    "Failed to batch create comp run snapshot tasks: %s",
                    e,
                    exc_info=True,
                )
                raise

    # async def update_for_run_id_and_node_id(
    #     self,
    #     connection: AsyncConnection | None = None,
    #     *,
    #     run_id: PositiveInt,
    #     node_id: NodeID,
    #     data: dict,
    # ) -> CompRunSnapshotTaskAtDBGet:
    #     row = await update_for_run_id_and_node_id(
    #         self.db_engine,
    #         conn=connection,
    #         run_id=run_id,
    #         node_id=f"{node_id}",
    #         data=data,
    #     )
    #     return CompRunSnapshotTaskAtDBGet.model_validate(row)
