import datetime
import logging
from typing import Any, Final, cast

import arrow
import asyncpg  # type: ignore[import-untyped]
import sqlalchemy as sa
import sqlalchemy.exc as sql_exc
from models_library.api_schemas_directorv2.comp_runs import ComputationRunRpcGet
from models_library.basic_types import IDStr
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import PositiveInt
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.dialects.postgresql.asyncpg import AsyncAdapt_asyncpg_dbapi
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import or_
from sqlalchemy.sql.elements import literal_column
from sqlalchemy.sql.expression import desc

from ....core.errors import (
    ComputationalRunNotFoundError,
    DirectorError,
    ProjectNotFoundError,
    UserNotFoundError,
)
from ....models.comp_runs import CompRunsAtDB, RunMetadataDict
from ....utils.db import DB_TO_RUNNING_STATE, RUNNING_STATE_TO_DB
from ..tables import comp_runs
from ._base import BaseRepository

logger = logging.getLogger(__name__)

_POSTGRES_FK_COLUMN_TO_ERROR_MAP: Final[
    dict[sa.Column, tuple[type[DirectorError], tuple[str, ...]]]
] = {
    comp_runs.c.user_id: (UserNotFoundError, ("users", "user_id")),
    comp_runs.c.project_uuid: (
        ProjectNotFoundError,
        ("projects", "project_id"),
    ),
}


async def _get_next_iteration(
    conn: AsyncConnection, user_id: UserID, project_id: ProjectID
) -> PositiveInt:
    """Calculate the next iteration number for a project"""
    last_iteration = await conn.scalar(
        sa.select(comp_runs.c.iteration)
        .where(
            (comp_runs.c.user_id == user_id)
            & (comp_runs.c.project_uuid == f"{project_id}")
        )
        .order_by(desc(comp_runs.c.iteration))
    )
    return cast(PositiveInt, (last_iteration or 0) + 1)


def _handle_foreign_key_violation(
    exc: sql_exc.IntegrityError, **error_keys: Any
) -> None:
    """Handle foreign key violation errors and raise appropriate exceptions"""
    if not isinstance(exc.orig, AsyncAdapt_asyncpg_dbapi.IntegrityError):
        return

    if (
        not hasattr(exc.orig, "pgcode")
        or exc.orig.pgcode != asyncpg.ForeignKeyViolationError.sqlstate
    ):
        return

    if not isinstance(
        exc.orig.__cause__, asyncpg.ForeignKeyViolationError
    ) or not hasattr(exc.orig.__cause__, "constraint_name"):
        return

    constraint_name = exc.orig.__cause__.constraint_name

    for foreign_key in comp_runs.foreign_keys:
        if constraint_name == foreign_key.name and foreign_key.parent is not None:
            exc_type, exc_keys = _POSTGRES_FK_COLUMN_TO_ERROR_MAP[foreign_key.parent]
            raise exc_type(**{k: error_keys.get(k) for k in exc_keys})


class CompRunsRepository(BaseRepository):
    async def get(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: PositiveInt | None = None,
    ) -> CompRunsAtDB:
        """returns the run defined by user_id, project_id and iteration
        In case iteration is None then returns the last iteration

        :raises ComputationalRunNotFoundError: no entry found
        """

        async with pass_or_acquire_connection(self.db_engine) as conn:
            result = await conn.execute(
                sa.select(comp_runs)
                .where(
                    (comp_runs.c.user_id == user_id)
                    & (comp_runs.c.project_uuid == f"{project_id}")
                    & (comp_runs.c.iteration == iteration if iteration else True)
                )
                .order_by(desc(comp_runs.c.iteration))
                .limit(1)
            )
            row = result.one_or_none()
            if not row:
                raise ComputationalRunNotFoundError
            return CompRunsAtDB.model_validate(row)

    async def list_(
        self,
        *,
        filter_by_state: set[RunningState] | None = None,
        never_scheduled: bool = False,
        processed_since: datetime.timedelta | None = None,
        scheduled_since: datetime.timedelta | None = None,
    ) -> list[CompRunsAtDB]:
        """lists the computational runs:
        filter_by_state AND (never_scheduled OR processed_since OR scheduled_since)


        Keyword Arguments:
            filter_by_state -- will return only the runs with result in filter_by_state (default: {None})
            never_scheduled -- will return the runs which were never scheduled (default: {False})
            processed_since -- will return the runs which were processed since X, which are not re-scheduled since then (default: {None})
            scheduled_since -- will return the runs which were scheduled since X, which are not processed since then (default: {None})
        """

        conditions = []
        if filter_by_state:
            conditions.append(
                or_(
                    *[
                        comp_runs.c.result == RUNNING_STATE_TO_DB[s]
                        for s in filter_by_state
                    ]
                )
            )

        scheduling_or_conditions = []
        if never_scheduled:
            scheduling_or_conditions.append(comp_runs.c.scheduled.is_(None))
        if scheduled_since is not None:
            # a scheduled run is a run that has been scheduled but not processed yet
            # e.g. the processing timepoint is either null or before the scheduling timepoint
            scheduled_cutoff = arrow.utcnow().datetime - scheduled_since
            scheduling_filter = (
                comp_runs.c.scheduled.is_not(None)
                & (
                    comp_runs.c.processed.is_(None)
                    | (comp_runs.c.scheduled > comp_runs.c.processed)
                )
                & (comp_runs.c.scheduled <= scheduled_cutoff)
            )
            scheduling_or_conditions.append(scheduling_filter)

        if processed_since is not None:
            # a processed run is a run that has been scheduled and processed
            # and the processing timepoint is after the scheduling timepoint
            processed_cutoff = arrow.utcnow().datetime - processed_since
            processed_filter = (
                comp_runs.c.processed.is_not(None)
                & (comp_runs.c.processed > comp_runs.c.scheduled)
                & (comp_runs.c.processed <= processed_cutoff)
            )

            scheduling_or_conditions.append(processed_filter)

        if scheduling_or_conditions:
            conditions.append(sa.or_(*scheduling_or_conditions))

        async with self.db_engine.connect() as conn:
            return [
                CompRunsAtDB.model_validate(row)
                async for row in await conn.stream(
                    sa.select(comp_runs).where(
                        sa.and_(True, *conditions)  # noqa: FBT003
                    )
                )
            ]

    _COMPUTATION_RUNS_RPC_GET_COLUMNS = [  # noqa: RUF012
        comp_runs.c.project_uuid,
        comp_runs.c.iteration,
        comp_runs.c.result.label("state"),
        comp_runs.c.metadata.label("info"),
        comp_runs.c.created.label("submitted_at"),
        comp_runs.c.started.label("started_at"),
        comp_runs.c.ended.label("ended_at"),
    ]

    async def list_for_user__only_latest_iterations(
        self,
        *,
        product_name: str,
        user_id: UserID,
        # filters
        filter_only_running: bool,
        # pagination
        offset: int,
        limit: int,
        # ordering
        order_by: OrderBy | None = None,
    ) -> tuple[int, list[ComputationRunRpcGet]]:
        # NOTE: Currently, we list only pipelines created by the user themselves.
        # If we want to list all pipelines that the user has read access to
        # via project access rights, we need to join the `projects_to_groups`
        # and `workspaces_access_rights` tables (which will make it slower, but we do
        # the same for listing projects).
        if order_by is None:
            order_by = OrderBy(field=IDStr("run_id"))  # default ordering

        _latest_runs = (
            sa.select(
                comp_runs.c.project_uuid,
                sa.func.max(comp_runs.c.iteration).label(
                    "latest_iteration"
                ),  # <-- NOTE: We might create a boolean column with latest iteration for fast retrieval
            )
            .where(
                (comp_runs.c.user_id == user_id)
                & (
                    comp_runs.c.metadata["product_name"].astext == product_name
                )  # <-- NOTE: We might create a separate column for this for fast retrieval
            )
            .group_by(comp_runs.c.project_uuid)
        )
        if filter_only_running:
            _latest_runs = _latest_runs.where(
                comp_runs.c.result.in_(
                    [
                        RUNNING_STATE_TO_DB[item]
                        for item in RunningState.list_running_states()
                    ]
                )
            )
        _latest_runs_subquery = _latest_runs.subquery().alias("latest_runs")

        base_select_query = sa.select(
            *self._COMPUTATION_RUNS_RPC_GET_COLUMNS
        ).select_from(
            _latest_runs_subquery.join(
                comp_runs,
                sa.and_(
                    comp_runs.c.project_uuid == _latest_runs_subquery.c.project_uuid,
                    comp_runs.c.iteration == _latest_runs_subquery.c.latest_iteration,
                ),
            )
        )

        # Select total count from base_query
        count_query = sa.select(sa.func.count()).select_from(
            base_select_query.subquery()
        )

        # Ordering and pagination
        if order_by.direction == OrderDirection.ASC:
            list_query = base_select_query.order_by(
                sa.asc(getattr(comp_runs.c, order_by.field)), comp_runs.c.run_id
            )
        else:
            list_query = base_select_query.order_by(
                desc(getattr(comp_runs.c, order_by.field)), comp_runs.c.run_id
            )
        list_query = list_query.offset(offset).limit(limit)

        async with pass_or_acquire_connection(self.db_engine) as conn:
            total_count = await conn.scalar(count_query)

            items = [
                ComputationRunRpcGet.model_validate(
                    {
                        **row,
                        "state": DB_TO_RUNNING_STATE[row["state"]],
                    }
                )
                async for row in await conn.stream(list_query)
            ]

            return cast(int, total_count), items

    async def list_for_user_and_project_all_iterations(
        self,
        *,
        product_name: str,
        user_id: UserID,
        project_ids: list[ProjectID],
        # pagination
        offset: int,
        limit: int,
        # ordering
        order_by: OrderBy | None = None,
    ) -> tuple[int, list[ComputationRunRpcGet]]:
        if order_by is None:
            order_by = OrderBy(field=IDStr("run_id"))  # default ordering

        base_select_query = sa.select(
            *self._COMPUTATION_RUNS_RPC_GET_COLUMNS,
        ).where(
            (comp_runs.c.user_id == user_id)
            & (
                comp_runs.c.project_uuid.in_(
                    [f"{project_id}" for project_id in project_ids]
                )
            )
            & (
                comp_runs.c.metadata["product_name"].astext == product_name
            )  # <-- NOTE: We might create a separate column for this for fast retrieval
        )

        # Select total count from base_query
        count_query = sa.select(sa.func.count()).select_from(
            base_select_query.subquery()
        )

        # Ordering and pagination
        if order_by.direction == OrderDirection.ASC:
            list_query = base_select_query.order_by(
                sa.asc(getattr(comp_runs.c, order_by.field)), comp_runs.c.run_id
            )
        else:
            list_query = base_select_query.order_by(
                desc(getattr(comp_runs.c, order_by.field)), comp_runs.c.run_id
            )
        list_query = list_query.offset(offset).limit(limit)

        async with pass_or_acquire_connection(self.db_engine) as conn:
            total_count = await conn.scalar(count_query)

            items = [
                ComputationRunRpcGet.model_validate(
                    {
                        **row,
                        "state": DB_TO_RUNNING_STATE[row["state"]],
                    }
                )
                async for row in await conn.stream(list_query)
            ]

            return cast(int, total_count), items

    async def get_latest_run_id_for_project(
        self,
        conn: AsyncConnection | None = None,
        *,
        project_id: ProjectID,
    ) -> PositiveInt:
        # Get latest run per (project_uuid, user_id)
        project_and_user_latest_runs = (
            sa.select(
                comp_runs.c.project_uuid,
                comp_runs.c.user_id,
                sa.func.max(comp_runs.c.iteration).label("latest_iteration"),
                sa.func.max(comp_runs.c.created).label("created"),
            )
            .where(comp_runs.c.project_uuid == f"{project_id}")
            .group_by(comp_runs.c.project_uuid, comp_runs.c.user_id)
            .subquery("project_and_user_latest_runs")
        )

        # Rank users per project by latest run creation time
        ranked = sa.select(
            project_and_user_latest_runs.c.project_uuid,
            project_and_user_latest_runs.c.user_id,
            project_and_user_latest_runs.c.latest_iteration,
            project_and_user_latest_runs.c.created,
            sa.func.row_number()
            .over(
                partition_by=project_and_user_latest_runs.c.project_uuid,
                order_by=project_and_user_latest_runs.c.created.desc(),
            )
            .label("row_number"),
        ).subquery("ranked")

        # Filter to only the top-ranked (most recent) user per project
        filtered_ranked = (
            sa.select(
                ranked.c.project_uuid,
                ranked.c.user_id,
                ranked.c.latest_iteration,
            )
            .where(ranked.c.row_number == 1)
            .subquery("filtered_ranked")
        )

        # Base select query
        base_select_query = sa.select(comp_runs.c.run_id).select_from(
            filtered_ranked.join(
                comp_runs,
                sa.and_(
                    comp_runs.c.project_uuid == filtered_ranked.c.project_uuid,
                    comp_runs.c.user_id == filtered_ranked.c.user_id,
                    comp_runs.c.iteration == filtered_ranked.c.latest_iteration,
                ),
            )
        )

        async with pass_or_acquire_connection(self.db_engine, connection=conn) as _conn:
            result = await conn.execute(base_select_query)
            row = result.one_or_none()
            if not row:
                raise ValueError("improve")
            return row.run_id

    async def create(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        iteration: PositiveInt | None = None,
        metadata: RunMetadataDict,
        use_on_demand_clusters: bool,
    ) -> CompRunsAtDB:
        try:
            async with transaction_context(self.db_engine) as conn:
                if iteration is None:
                    iteration = await _get_next_iteration(conn, user_id, project_id)

                result = await conn.execute(
                    comp_runs.insert()  # pylint: disable=no-value-for-parameter
                    .values(
                        user_id=user_id,
                        project_uuid=f"{project_id}",
                        iteration=iteration,
                        result=RUNNING_STATE_TO_DB[RunningState.PUBLISHED],
                        metadata=jsonable_encoder(metadata),
                        use_on_demand_clusters=use_on_demand_clusters,
                    )
                    .returning(literal_column("*"))
                )
                row = result.one()
                return CompRunsAtDB.model_validate(row)
        except sql_exc.IntegrityError as exc:
            _handle_foreign_key_violation(exc, project_id=project_id, user_id=user_id)
            raise DirectorError from exc

    async def update(
        self, user_id: UserID, project_id: ProjectID, iteration: PositiveInt, **values
    ) -> CompRunsAtDB | None:
        async with transaction_context(self.db_engine) as conn:
            result = await conn.execute(
                sa.update(comp_runs)
                .where(
                    (comp_runs.c.project_uuid == f"{project_id}")
                    & (comp_runs.c.user_id == user_id)
                    & (comp_runs.c.iteration == iteration)
                )
                .values(**values)
                .returning(literal_column("*"))
            )
            row = result.one_or_none()
            return CompRunsAtDB.model_validate(row) if row else None

    async def set_run_result(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        iteration: PositiveInt,
        result_state: RunningState,
        final_state: bool | None = False,
    ) -> CompRunsAtDB | None:
        values: dict[str, Any] = {"result": RUNNING_STATE_TO_DB[result_state]}
        if final_state:
            values.update({"ended": arrow.utcnow().datetime})
        return await self.update(
            user_id,
            project_id,
            iteration,
            **values,
        )

    async def mark_as_started(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        iteration: PositiveInt,
        started_time: datetime.datetime,
    ) -> CompRunsAtDB | None:
        return await self.update(
            user_id,
            project_id,
            iteration,
            started=started_time,
        )

    async def mark_for_cancellation(
        self, *, user_id: UserID, project_id: ProjectID, iteration: PositiveInt
    ) -> CompRunsAtDB | None:
        return await self.update(
            user_id,
            project_id,
            iteration,
            cancelled=arrow.utcnow().datetime,
        )

    async def mark_for_scheduling(
        self, *, user_id: UserID, project_id: ProjectID, iteration: PositiveInt
    ) -> CompRunsAtDB | None:
        return await self.update(
            user_id,
            project_id,
            iteration,
            scheduled=arrow.utcnow().datetime,
            processed=None,
        )

    async def mark_as_processed(
        self, *, user_id: UserID, project_id: ProjectID, iteration: PositiveInt
    ) -> CompRunsAtDB | None:
        return await self.update(
            user_id,
            project_id,
            iteration,
            processed=arrow.utcnow().datetime,
        )
