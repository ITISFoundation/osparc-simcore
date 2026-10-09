import logging
from datetime import datetime
from typing import Any, cast

import sqlalchemy as sa
from models_library.basic_types import IDStr
from models_library.errors import ErrorDict
from models_library.projects import NodesDict, ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.resource_tracker import PricingPlanId, PricingUnitId
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.users import UserID
from models_library.wallets import WalletInfo
from pydantic import TypeAdapter
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQRPCClient
from simcore_postgres_database.utils_projects_nodes import ProjectNodesRepo
from simcore_postgres_database.utils_repos import pass_or_acquire_connection, transaction_context
from sqlalchemy import CursorResult, literal_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from .....core.errors import (
    ComputationalTaskJobIdAlreadySetError,
    ComputationalTaskNotFoundError,
)
from .....models.comp_runs import RunID
from .....models.comp_tasks import CompTaskAtDB, ComputationTaskForRpcDBGet
from .....modules.resource_usage_tracker_client import ResourceUsageTrackerClient
from .....utils.computations import to_node_class
from .....utils.db import RUNNING_STATE_TO_DB
from ....catalog import CatalogClient
from ...tables import NodeClass, comp_run_snapshot_tasks, comp_tasks, projects
from .._base import BaseRepository
from . import _utils

_logger = logging.getLogger(__name__)


class CompTasksRepository(BaseRepository):
    async def get_task(
        self,
        *,
        connection: AsyncConnection | None = None,
        project_id: ProjectID,
        node_id: NodeID,
    ) -> CompTaskAtDB:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            result = await conn.execute(
                sa.select(comp_tasks).where(
                    (comp_tasks.c.project_id == f"{project_id}") & (comp_tasks.c.node_id == f"{node_id}")
                )
            )
            row = result.one_or_none()
            if not row:
                raise ComputationalTaskNotFoundError(node_id=node_id)
            return CompTaskAtDB.model_validate(row)

    async def list_tasks(
        self,
        *,
        connection: AsyncConnection | None = None,
        project_id: ProjectID,
    ) -> list[CompTaskAtDB]:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            result = await conn.execute(sa.select(comp_tasks).where(comp_tasks.c.project_id == f"{project_id}"))
            return TypeAdapter(list[CompTaskAtDB]).validate_python(result.all())

    async def list_computational_tasks(
        self,
        *,
        connection: AsyncConnection | None = None,
        project_id: ProjectID,
    ) -> list[CompTaskAtDB]:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            result = await conn.execute(
                sa.select(comp_tasks).where(
                    (comp_tasks.c.project_id == f"{project_id}") & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
                )
            )
            return TypeAdapter(list[CompTaskAtDB]).validate_python(result.all())

    async def list_computational_tasks_rpc_domain(
        self,
        *,
        connection: AsyncConnection | None = None,
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
                (comp_tasks.c.project_id.in_([f"{project_id}" for project_id in project_ids]))
                & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
            )
        )

        # Select total count from base_query
        count_query = sa.select(sa.func.count()).select_from(base_select_query.subquery())

        # Ordering and pagination
        if order_by.direction == OrderDirection.ASC:
            list_query = base_select_query.order_by(sa.asc(getattr(comp_tasks.c, order_by.field)), comp_tasks.c.task_id)
        else:
            list_query = base_select_query.order_by(
                sa.desc(getattr(comp_tasks.c, order_by.field)), comp_tasks.c.task_id
            )
        list_query = list_query.offset(offset).limit(limit)

        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            total_count = await conn.scalar(count_query)
            result = await conn.execute(list_query)

            items = TypeAdapter(list[ComputationTaskForRpcDBGet]).validate_python(result.all())
            return cast(int, total_count), items

    async def task_exists(
        self, project_id: ProjectID, node_id: NodeID, *, connection: AsyncConnection | None = None
    ) -> bool:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            nid: str | None = await conn.scalar(
                sa.select(comp_tasks.c.node_id).where(
                    (comp_tasks.c.project_id == f"{project_id}") & (comp_tasks.c.node_id == f"{node_id}")
                )
            )
            return nid is not None

    async def _get_project_nodes_snapshot(self, project: ProjectAtDB) -> _utils.ProjectNodesSnapshot:
        """Reads, in one short transaction, everything `projects_nodes` holds for this project

        NOTE: nodes are read in `node_id` order so that every following write happens in the
        same order, which is what keeps a single transaction from taking row locks in an order
        another transaction could not wait for.
        """
        async with pass_or_acquire_connection(self.db_engine) as conn:
            projects_nodes_repo = ProjectNodesRepo(project_uuid=project.uuid)
            return _utils.ProjectNodesSnapshot(
                required_resources={
                    node.node_id: node.required_resources for node in await projects_nodes_repo.list(conn)
                },
                pricing_unit_ids={
                    node_id: (PricingPlanId(plan_id), PricingUnitId(unit_id))
                    for node_id, (plan_id, unit_id) in (
                        await projects_nodes_repo.get_project_node_pricing_unit_ids(conn)
                    ).items()
                },
            )

    async def upsert_tasks_from_project(
        self,
        *,
        project: ProjectAtDB,
        project_nodes: NodesDict,
        catalog_client: CatalogClient,
        published_nodes: list[NodeID],
        user_id: UserID,
        product_name: str,
        rut_client: ResourceUsageTrackerClient,
        wallet_info: WalletInfo | None,
        rabbitmq_rpc_client: RabbitMQRPCClient,
    ) -> tuple[list[CompTaskAtDB], bool]:
        """Returns (comp_tasks, insufficient_credits).

        If insufficient_credits is True, affected published nodes were set to ABORTED.

        NOTE: the database is read and written in two short transactions and every call to
        another backend service happens in between, i.e. while **no** row is locked.
        See https://github.com/ITISFoundation/private-issues/issues/669
        """
        # 1. read everything the task creation needs from the DB, then release the transaction
        snapshot = await self._get_project_nodes_snapshot(project)

        # 2. create the tasks, calling the catalog/resource-usage-tracker/clusters-keeper
        #    services outside of any transaction
        (
            list_of_comp_tasks_in_project,
            insufficient_credits,
            projects_nodes_updates,
        ) = (
            # WARNING: this is NOT a real repository method, it is a utility function
            # that calls backend services to generate the tasks list!! Refactoring needed!!
            await _utils.generate_tasks_list_from_project(
                project=project,
                project_nodes=project_nodes,
                catalog_client=catalog_client,
                published_nodes=published_nodes,
                user_id=user_id,
                product_name=product_name,
                rut_client=rut_client,
                wallet_info=wallet_info,
                rabbitmq_rpc_client=rabbitmq_rpc_client,
                snapshot=snapshot,
            )
        )

        # 3. apply every pending write in one short transaction
        # NOTE: really do an upsert here because of issue https://github.com/ITISFoundation/osparc-simcore/issues/2125
        async with transaction_context(self.db_engine) as conn:
            # Acquire the same lock as the webserver does before a graph mutation
            # (see utils_projects_nodes._lock_project_graph), i.e. before touching
            # `projects_nodes`. Both services then wait on the same row in `projects` and
            # cannot deadlock with each other any more.
            await conn.execute(
                sa.select(projects.c.uuid).where(projects.c.uuid == f"{project.uuid}").with_for_update(key_share=True)
            )

            projects_nodes_repo = ProjectNodesRepo(project_uuid=project.uuid)
            for node_id, pricing_unit_ids in sorted(projects_nodes_updates.pricing_unit_ids.items()):
                pricing_plan_id, pricing_unit_id = pricing_unit_ids
                await projects_nodes_repo.connect_pricing_unit_to_project_node(
                    conn,
                    node_uuid=node_id,
                    pricing_plan_id=pricing_plan_id,
                    pricing_unit_id=pricing_unit_id,
                )
            for node_id, required_resources in sorted(projects_nodes_updates.required_resources.items()):
                await projects_nodes_repo.update(conn, node_id=node_id, required_resources=required_resources)

            # get current tasks
            result = await conn.execute(
                sa.select(comp_tasks.c.node_id).where(comp_tasks.c.project_id == str(project.uuid))
            )
            # remove the tasks that were removed from project workbench
            if all_nodes := result.all():
                node_ids_to_delete = sorted(f"{t.node_id}" for t in all_nodes if t.node_id not in project_nodes)
                for deleted_node_id in node_ids_to_delete:
                    await conn.execute(
                        sa.delete(comp_tasks).where(
                            (comp_tasks.c.project_id == str(project.uuid)) & (comp_tasks.c.node_id == deleted_node_id)
                        )
                    )

            # insert or update the remaining tasks
            # NOTE: comp_tasks DB only trigger a notification to the webserver if an UPDATE on comp_tasks.outputs or comp_tasks.state is done
            # NOTE: an exception to this is when a frontend service changes its output since there is no node_ports, the UPDATE must be done here.

            inserted_comp_tasks_db: list[CompTaskAtDB] = []
            for comp_task_db in sorted(list_of_comp_tasks_in_project, key=lambda task: task.node_id):
                insert_stmt = insert(comp_tasks).values(**comp_task_db.to_db_model(exclude={"created", "modified"}))

                exclusion_rule = {"state", "progress"} if comp_task_db.node_id not in published_nodes else set()
                update_values = (
                    {"progress": None, "job_id": None, "start": None, "end": None, "errors": None}
                    if comp_task_db.node_id in published_nodes
                    else {}
                )

                if to_node_class(comp_task_db.image.name) != NodeClass.FRONTEND:
                    exclusion_rule.add("outputs")
                else:
                    update_values = {}
                result = await conn.execute(
                    insert_stmt.on_conflict_do_update(
                        index_elements=[comp_tasks.c.project_id, comp_tasks.c.node_id],
                        set_=comp_task_db.to_db_model(exclude=exclusion_rule) | update_values,
                    ).returning(literal_column("*"))
                )
                row = result.one()
                inserted_comp_tasks_db.append(CompTaskAtDB.model_validate(row))
                _logger.debug(
                    "inserted the following tasks in comp_tasks: %s",
                    f"{inserted_comp_tasks_db=}",
                )
            return inserted_comp_tasks_db, insufficient_credits

    async def _update_task(
        self,
        project_id: ProjectID,
        task: NodeID,
        run_id: RunID,
        *,
        connection: AsyncConnection | None = None,
        **task_kwargs,
    ) -> CompTaskAtDB:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"update task {project_id=}:{task=} with '{task_kwargs}'",
        ):
            async with transaction_context(self.db_engine, connection) as conn:
                result: CursorResult = await conn.execute(
                    sa.update(comp_tasks)
                    .where((comp_tasks.c.project_id == f"{project_id}") & (comp_tasks.c.node_id == f"{task}"))
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

    async def set_task_job_id(
        self,
        project_id: ProjectID,
        task: NodeID,
        run_id: RunID,
        job_id: str,
        *,
        connection: AsyncConnection | None = None,
    ) -> None:
        """sets the task's job_id and atomically moves it to PENDING.

        Raises:
            ComputationalTaskNotFoundError: if the task does not exist
            ComputationalTaskJobIdAlreadySetError: if the task already has a job_id
        """
        task_kwargs = {"job_id": job_id, "state": RUNNING_STATE_TO_DB[RunningState.PENDING]}
        async with transaction_context(self.db_engine, connection) as conn:
            result: CursorResult = await conn.execute(
                sa.update(comp_tasks)
                .where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_id == f"{task}")
                    & (comp_tasks.c.job_id.is_(None))
                )
                .values(**task_kwargs)
                .returning(literal_column("*"))
            )
            if result.one_or_none() is None:
                task_exists = await conn.scalar(
                    sa.select(comp_tasks.c.node_id).where(
                        (comp_tasks.c.project_id == f"{project_id}") & (comp_tasks.c.node_id == f"{task}")
                    )
                )
                if task_exists is None:
                    raise ComputationalTaskNotFoundError(node_id=task)
                raise ComputationalTaskJobIdAlreadySetError(project_id=project_id, node_id=task)
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

    async def reset_task_for_resubmission(
        self,
        project_id: ProjectID,
        task: NodeID,
        run_id: RunID,
        errors: list[ErrorDict] | None = None,
        *,
        connection: AsyncConnection | None = None,
    ) -> None:
        """clears the backend job reference so the scheduler picks the task up again"""
        await self._update_task(
            project_id,
            task,
            run_id,
            connection=connection,
            state=RUNNING_STATE_TO_DB[RunningState.WAITING_FOR_CLUSTER],
            job_id=None,
            progress=None,
            start=None,
            end=None,
            errors=errors,
        )

    async def update_project_tasks_state(  # pylint: disable=too-many-arguments
        self,
        project_id: ProjectID,
        run_id: RunID,
        tasks: list[NodeID],
        state: RunningState,
        errors: list[ErrorDict] | None = None,
        *,
        connection: AsyncConnection | None = None,
        clear_errors: bool = True,
        optional_progress: float | None = None,
        optional_started: datetime | None = None,
        optional_stopped: datetime | None = None,
    ) -> None:
        """update the task state values in the database
        passing None for the optional arguments will not update the respective values in the database
        Keyword Arguments:
            errors -- _description_ (default: {None})
            clear_errors -- if False and errors is None, the errors column is left untouched
                instead of being cleared (default: {True})
            optional_progress -- _description_ (default: {None})
            optional_started -- _description_ (default: {None})
            optional_stopped -- _description_ (default: {None})
        """
        if not tasks:
            return
        update_values: dict[str, Any] = {"state": RUNNING_STATE_TO_DB[state]}
        if clear_errors or errors is not None:
            update_values["errors"] = errors
        if optional_progress is not None:
            update_values["progress"] = optional_progress
        if optional_started is not None:
            update_values["start"] = optional_started
        if optional_stopped is not None:
            update_values["end"] = optional_stopped

        # NOTE: all the tasks share the same update_values, so this is done as a single
        # bulk update per table instead of one transaction per task (see ADR on comp_tasks batching)
        node_ids = [f"{task_id}" for task_id in tasks]
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"update tasks state {project_id=}:{node_ids=} with '{update_values}'",
        ):
            async with transaction_context(self.db_engine, connection) as conn:
                await conn.execute(
                    sa.update(comp_tasks)
                    .where((comp_tasks.c.project_id == f"{project_id}") & (comp_tasks.c.node_id.in_(node_ids)))
                    .values(**update_values)
                )
                # Sync with comp_run_snapshot_tasks table
                await conn.execute(
                    sa.update(comp_run_snapshot_tasks)
                    .where(
                        (comp_run_snapshot_tasks.c.run_id == run_id)
                        & (comp_run_snapshot_tasks.c.project_id == f"{project_id}")
                        & (comp_run_snapshot_tasks.c.node_id.in_(node_ids))
                    )
                    .values(**update_values)
                )

    async def update_project_task_progress(
        self,
        project_id: ProjectID,
        node_id: NodeID,
        run_id: RunID,
        progress: float,
        *,
        connection: AsyncConnection | None = None,
    ) -> None:
        await self._update_task(project_id, node_id, run_id, connection=connection, progress=progress)

    async def update_project_task_last_heartbeat(
        self,
        project_id: ProjectID,
        node_id: NodeID,
        run_id: RunID,
        heartbeat_time: datetime,
        *,
        connection: AsyncConnection | None = None,
    ) -> None:
        await self._update_task(project_id, node_id, run_id, connection=connection, last_heartbeat=heartbeat_time)

    async def delete_tasks_from_project(
        self,
        *,
        connection: AsyncConnection | None = None,
        project_id: ProjectID,
    ) -> None:
        async with transaction_context(self.db_engine, connection) as conn:
            await conn.execute(sa.delete(comp_tasks).where(comp_tasks.c.project_id == f"{project_id}"))

    async def get_outputs_from_tasks(
        self,
        *,
        connection: AsyncConnection | None = None,
        project_id: ProjectID,
        node_ids: set[NodeID],
    ) -> dict[NodeID, dict[IDStr, Any]]:
        selection = list(map(str, node_ids))
        query = sa.select(comp_tasks.c.node_id, comp_tasks.c.outputs).where(
            (comp_tasks.c.project_id == f"{project_id}") & (comp_tasks.c.node_id.in_(selection))
        )
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            result = await conn.execute(query)
            rows = result.all()
            if rows:
                assert set(selection) == {f"{_.node_id}" for _ in rows}  # nosec
                return {NodeID(_.node_id): _.outputs or {} for _ in rows}
            return {}
