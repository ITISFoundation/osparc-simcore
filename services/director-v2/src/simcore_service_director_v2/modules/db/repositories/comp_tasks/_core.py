import logging
from datetime import datetime
from typing import Any, cast

import arrow
import sqlalchemy as sa
from models_library.basic_types import IDStr
from models_library.errors import ErrorDict
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.users import UserID
from models_library.wallets import WalletInfo
from pydantic import PositiveInt
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.utils import logged_gather
from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert

from .....core.errors import ComputationalTaskNotFoundError
from .....models.comp_tasks import CompTaskAtDB, ComputationTaskForRpcDBGet
from .....modules.resource_usage_tracker_client import ResourceUsageTrackerClient
from .....utils.computations import to_node_class
from .....utils.db import DB_TO_RUNNING_STATE, RUNNING_STATE_TO_DB
from ....catalog import CatalogClient
from ...tables import NodeClass, StateType, comp_run_snapshot_tasks, comp_tasks
from .._base import BaseRepository
from . import _utils

_logger = logging.getLogger(__name__)


class CompTasksRepository(BaseRepository):
    async def get_task(self, project_id: ProjectID, node_id: NodeID) -> CompTaskAtDB:
        async with self.db_engine.connect() as conn:
            result = await conn.execute(
                sa.select(comp_tasks).where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_id == f"{node_id}")
                )
            )
            row = result.one_or_none()
            if not row:
                raise ComputationalTaskNotFoundError(node_id=node_id)
            return CompTaskAtDB.model_validate(row)

    async def list_tasks(
        self,
        project_id: ProjectID,
    ) -> list[CompTaskAtDB]:
        tasks: list[CompTaskAtDB] = []
        async with self.db_engine.connect() as conn:
            async for row in await conn.stream(
                sa.select(comp_tasks).where(comp_tasks.c.project_id == f"{project_id}")
            ):
                task_db = CompTaskAtDB.model_validate(row)
                tasks.append(task_db)

        return tasks

    async def list_computational_tasks(
        self,
        project_id: ProjectID,
    ) -> list[CompTaskAtDB]:
        tasks: list[CompTaskAtDB] = []
        async with self.db_engine.connect() as conn:
            async for row in await conn.stream(
                sa.select(comp_tasks).where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
                )
            ):
                task_db = CompTaskAtDB.model_validate(row)
                tasks.append(task_db)
        return tasks

    async def list_computational_tasks_rpc_domain(
        self,
        *,
        project_ids: list[ProjectID],
        # pagination
        offset: int = 0,
        limit: int = 20,
        # ordering
        order_by: OrderBy | None = None,
    ) -> tuple[int, list[ComputationTaskForRpcDBGet]]:
        if order_by is None:
            order_by = OrderBy(field=IDStr("task_id"))  # default ordering

        base_select_query = (
            sa.select(
                comp_tasks.c.project_id.label("project_uuid"),
                comp_tasks.c.node_id,
                comp_tasks.c.state,
                comp_tasks.c.progress,
                comp_tasks.c.image,
                comp_tasks.c.start.label("started_at"),
                comp_tasks.c.end.label("ended_at"),
            )
            .select_from(comp_tasks)
            .where(
                (
                    comp_tasks.c.project_id.in_(
                        [f"{project_id}" for project_id in project_ids]
                    )
                )
                & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
            )
        )

        # Select total count from base_query
        count_query = sa.select(sa.func.count()).select_from(
            base_select_query.subquery()
        )

        # Ordering and pagination
        if order_by.direction == OrderDirection.ASC:
            list_query = base_select_query.order_by(
                sa.asc(getattr(comp_tasks.c, order_by.field)), comp_tasks.c.task_id
            )
        else:
            list_query = base_select_query.order_by(
                sa.desc(getattr(comp_tasks.c, order_by.field)), comp_tasks.c.task_id
            )
        list_query = list_query.offset(offset).limit(limit)

        async with self.db_engine.connect() as conn:
            total_count = await conn.scalar(count_query)

            items = [
                ComputationTaskForRpcDBGet.model_validate(
                    {
                        **row,
                        "state": DB_TO_RUNNING_STATE[row["state"]],  # Convert the state
                    }
                )
                async for row in await conn.stream(list_query)
            ]
            return cast(int, total_count), items

    async def task_exists(self, project_id: ProjectID, node_id: NodeID) -> bool:
        async with self.db_engine.connect() as conn:
            nid: str | None = await conn.scalar(
                sa.select(comp_tasks.c.node_id).where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_id == f"{node_id}")
                )
            )
            return nid is not None

    async def upsert_tasks_from_project(
        self,
        *,
        project: ProjectAtDB,
        catalog_client: CatalogClient,
        published_nodes: list[NodeID],
        user_id: UserID,
        product_name: str,
        rut_client: ResourceUsageTrackerClient,
        wallet_info: WalletInfo | None,
        rabbitmq_rpc_client: RabbitMQRPCClient,
    ) -> list[CompTaskAtDB]:
        # NOTE: really do an upsert here because of issue https://github.com/ITISFoundation/osparc-simcore/issues/2125
        async with self.db_engine.begin() as conn:
            list_of_comp_tasks_in_project: list[CompTaskAtDB] = (
                await _utils.generate_tasks_list_from_project(
                    project=project,
                    catalog_client=catalog_client,
                    published_nodes=published_nodes,
                    user_id=user_id,
                    product_name=product_name,
                    connection=conn,
                    rut_client=rut_client,
                    wallet_info=wallet_info,
                    rabbitmq_rpc_client=rabbitmq_rpc_client,
                )
            )
            # get current tasks
            result = await conn.execute(
                sa.select(comp_tasks.c.node_id).where(
                    comp_tasks.c.project_id == str(project.uuid)
                )
            )
            # remove the tasks that were removed from project workbench
            if all_nodes := result.all():
                node_ids_to_delete = [
                    t.node_id for t in all_nodes if t.node_id not in project.workbench
                ]
                for node_id in node_ids_to_delete:
                    await conn.execute(
                        sa.delete(comp_tasks).where(
                            (comp_tasks.c.project_id == str(project.uuid))
                            & (comp_tasks.c.node_id == node_id)
                        )
                    )

            # insert or update the remaining tasks
            # NOTE: comp_tasks DB only trigger a notification to the webserver if an UPDATE on comp_tasks.outputs or comp_tasks.state is done
            # NOTE: an exception to this is when a frontend service changes its output since there is no node_ports, the UPDATE must be done here.

            inserted_comp_tasks_db: list[CompTaskAtDB] = []
            for comp_task_db in list_of_comp_tasks_in_project:
                insert_stmt = insert(comp_tasks).values(
                    **comp_task_db.to_db_model(exclude={"created", "modified"})
                )

                exclusion_rule = (
                    {"state", "progress"}
                    if comp_task_db.node_id not in published_nodes
                    else set()
                )
                update_values = (
                    {"progress": None}
                    if comp_task_db.node_id in published_nodes
                    else {}
                )

                if to_node_class(comp_task_db.image.name) != NodeClass.FRONTEND:
                    exclusion_rule.add("outputs")
                else:
                    update_values = {}
                on_update_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=[comp_tasks.c.project_id, comp_tasks.c.node_id],
                    set_=comp_task_db.to_db_model(exclude=exclusion_rule)
                    | update_values,
                ).returning(literal_column("*"))
                result = await conn.execute(on_update_stmt)
                row = result.one()
                inserted_comp_tasks_db.append(CompTaskAtDB.model_validate(row))
                _logger.debug(
                    "inserted the following tasks in comp_tasks: %s",
                    f"{inserted_comp_tasks_db=}",
                )
            return inserted_comp_tasks_db

    async def _update_task(
        self, project_id: ProjectID, task: NodeID, run_id: PositiveInt, **task_kwargs
    ) -> CompTaskAtDB:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"update task {project_id=}:{task=} with '{task_kwargs}'",
        ):
            async with self.db_engine.begin() as conn:
                result = await conn.execute(
                    sa.update(comp_tasks)
                    .where(
                        (comp_tasks.c.project_id == f"{project_id}")
                        & (comp_tasks.c.node_id == f"{task}")
                    )
                    .values(**task_kwargs)
                    .returning(literal_column("*"))
                )
                # Sync with comp_run_snapshot_tasks table
                await conn.execute(
                    sa.update(comp_run_snapshot_tasks)
                    .where(
                        (comp_run_snapshot_tasks.c.run_id == run_id)
                        & (comp_run_snapshot_tasks.c.project_id == f"{project_id}")
                        & (comp_run_snapshot_tasks.c.node_id == f"{task}")
                    )
                    .values(**task_kwargs)
                )

                row = result.one()
                return CompTaskAtDB.model_validate(row)

    async def mark_project_published_waiting_for_cluster_tasks_as_aborted(
        self, project_id: ProjectID, run_id: PositiveInt
    ) -> None:
        # block all pending tasks, so the sidecars stop taking them
        async with self.db_engine.begin() as conn:
            await conn.execute(
                sa.update(comp_tasks)
                .where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
                    & (
                        (comp_tasks.c.state == StateType.PUBLISHED)
                        | (comp_tasks.c.state == StateType.WAITING_FOR_CLUSTER)
                    )
                )
                .values(
                    state=StateType.ABORTED, progress=1.0, end=arrow.utcnow().datetime
                )
            )
            # Sync with comp_run_snapshot_tasks table
            await conn.execute(
                sa.update(comp_run_snapshot_tasks)
                .where(
                    (comp_run_snapshot_tasks.c.run_id == run_id)
                    & (comp_run_snapshot_tasks.c.project_id == f"{project_id}")
                    & (comp_run_snapshot_tasks.c.node_class == NodeClass.COMPUTATIONAL)
                    & (
                        (comp_run_snapshot_tasks.c.state == StateType.PUBLISHED)
                        | (
                            comp_run_snapshot_tasks.c.state
                            == StateType.WAITING_FOR_CLUSTER
                        )
                    )
                )
                .values(
                    state=StateType.ABORTED,
                    progress=1.0,
                    end=arrow.utcnow().datetime,
                )
            )

        _logger.debug("marked project %s published tasks as aborted", f"{project_id=}")

    async def update_project_task_job_id(
        self, project_id: ProjectID, task: NodeID, run_id: PositiveInt, job_id: str
    ) -> None:
        await self._update_task(project_id, task, run_id, job_id=job_id)

    async def update_project_tasks_state(
        self,
        project_id: ProjectID,
        run_id: PositiveInt,
        tasks: list[NodeID],
        state: RunningState,
        errors: list[ErrorDict] | None = None,
        *,
        optional_progress: float | None = None,
        optional_started: datetime | None = None,
        optional_stopped: datetime | None = None,
    ) -> None:
        """update the task state values in the database
        passing None for the optional arguments will not update the respective values in the database
        Keyword Arguments:
            errors -- _description_ (default: {None})
            optional_progress -- _description_ (default: {None})
            optional_started -- _description_ (default: {None})
            optional_stopped -- _description_ (default: {None})
        """
        update_values: dict[str, Any] = {
            "state": RUNNING_STATE_TO_DB[state],
            "errors": errors,
        }
        if optional_progress is not None:
            update_values["progress"] = optional_progress
        if optional_started is not None:
            update_values["start"] = optional_started
        if optional_stopped is not None:
            update_values["end"] = optional_stopped
        await logged_gather(
            *(
                self._update_task(project_id, task_id, run_id, **update_values)
                for task_id in tasks
            )
        )

    async def update_project_task_progress(
        self,
        project_id: ProjectID,
        node_id: NodeID,
        run_id: PositiveInt,
        progress: float,
    ) -> None:
        await self._update_task(project_id, node_id, run_id, progress=progress)

    async def update_project_task_last_heartbeat(
        self,
        project_id: ProjectID,
        node_id: NodeID,
        run_id: PositiveInt,
        heartbeat_time: datetime,
    ) -> None:
        await self._update_task(
            project_id, node_id, run_id, last_heartbeat=heartbeat_time
        )

    async def delete_tasks_from_project(self, project_id: ProjectID) -> None:
        async with self.db_engine.begin() as conn:
            await conn.execute(
                sa.delete(comp_tasks).where(comp_tasks.c.project_id == f"{project_id}")
            )

    async def get_outputs_from_tasks(
        self, project_id: ProjectID, node_ids: set[NodeID]
    ) -> dict[NodeID, dict[IDStr, Any]]:
        selection = list(map(str, node_ids))
        query = sa.select(comp_tasks.c.node_id, comp_tasks.c.outputs).where(
            (comp_tasks.c.project_id == f"{project_id}")
            & (comp_tasks.c.node_id.in_(selection))
        )
        async with self.db_engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.all()
            if rows:
                assert set(selection) == {f"{_.node_id}" for _ in rows}  # nosec
                return {NodeID(_.node_id): _.outputs or {} for _ in rows}
            return {}
