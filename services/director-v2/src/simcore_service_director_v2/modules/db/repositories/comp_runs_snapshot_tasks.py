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
        if not data:
            logger.warning(
                "No data provided for batch creation of comp run snapshot tasks"
            )
            return

        async with transaction_context(self.db_engine) as conn:

            try:
                await conn.execute(
                    comp_run_snapshot_tasks.insert().returning(
                        *COMP_RUN_SNAPSHOT_TASKS_DB_COLS
                    ),
                    data,
                )
            except Exception:
                logger.exception("Failed to batch create comp run snapshot tasks")
                raise
