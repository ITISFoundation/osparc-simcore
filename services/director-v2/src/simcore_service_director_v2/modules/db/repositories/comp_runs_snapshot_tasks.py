import logging
from typing import cast

import sqlalchemy as sa
from models_library.basic_types import IDStr
from models_library.computations import CollectionRunID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy, OrderDirection
from simcore_postgres_database.utils_comp_run_snapshot_tasks import (
    COMP_RUN_SNAPSHOT_TASKS_DB_COLS,
)
from simcore_postgres_database.utils_repos import (
    transaction_context,
)

from ....models.comp_run_snapshot_tasks import CompRunSnapshotTaskDBGet
from ....utils.db import DB_TO_RUNNING_STATE
from ..tables import comp_run_snapshot_tasks, comp_runs
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

    async def list_computation_collection_run_tasks(
        self,
        *,
        product_name: ProductName,
        user_id: int,
        collection_run_id: CollectionRunID,
        # pagination
        offset: int = 0,
        limit: int = 20,
        # ordering
        order_by: OrderBy | None = None,
    ) -> tuple[int, list[CompRunSnapshotTaskDBGet]]:
        if order_by is None:
            order_by = OrderBy(field=IDStr("snapshot_task_id"))  # default ordering

        prefiltered_comp_runs = (
            sa.select(
                comp_runs.c.run_id,
                comp_runs.c.iteration,
            ).where(
                (comp_runs.c.user_id == user_id)
                & (comp_runs.c.metadata["product_name"].astext == product_name)
                & (comp_runs.c.collection_run_id == f"{collection_run_id}")
            )
        ).subquery("prefiltered_comp_runs")

        base_select_query = sa.select(
            comp_run_snapshot_tasks.c.snapshot_task_id,
            comp_run_snapshot_tasks.c.run_id,
            comp_run_snapshot_tasks.c.project_id.label("project_uuid"),
            comp_run_snapshot_tasks.c.node_id,
            comp_run_snapshot_tasks.c.state,
            comp_run_snapshot_tasks.c.progress,
            comp_run_snapshot_tasks.c.image,
            comp_run_snapshot_tasks.c.start.label("started_at"),
            comp_run_snapshot_tasks.c.end.label("ended_at"),
            prefiltered_comp_runs.c.iteration,
        ).select_from(
            comp_run_snapshot_tasks.join(
                prefiltered_comp_runs,
                comp_run_snapshot_tasks.c.run_id == prefiltered_comp_runs.c.run_id,
            )
        )

        # Select total count from base_query
        count_query = sa.select(sa.func.count()).select_from(
            base_select_query.subquery()
        )

        # Ordering and pagination
        if order_by.direction == OrderDirection.ASC:
            list_query = base_select_query.order_by(
                sa.asc(getattr(comp_run_snapshot_tasks.c, order_by.field)),
                comp_run_snapshot_tasks.c.snapshot_task_id,
            )
        else:
            list_query = base_select_query.order_by(
                sa.desc(getattr(comp_run_snapshot_tasks.c, order_by.field)),
                comp_run_snapshot_tasks.c.snapshot_task_id,
            )
        list_query = list_query.offset(offset).limit(limit)

        async with self.db_engine.connect() as conn:
            total_count = await conn.scalar(count_query)

            items = [
                CompRunSnapshotTaskDBGet.model_validate(
                    {
                        **row,
                        "state": DB_TO_RUNNING_STATE[row["state"]],  # Convert the state
                    }
                )
                async for row in await conn.stream(list_query)
            ]
            return cast(int, total_count), items
