import datetime
import logging
from typing import Any, Final

import arrow
import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.clusters import DEFAULT_CLUSTER_ID, ClusterID
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import PositiveInt
from simcore_postgres_database.errors import ForeignKeyViolation
from sqlalchemy.sql import or_
from sqlalchemy.sql.elements import literal_column
from sqlalchemy.sql.expression import desc

from ....core.errors import (
    ClusterNotFoundError,
    ComputationalRunNotFoundError,
    DirectorError,
    ProjectNotFoundError,
    UserNotFoundError,
)
from ....models.comp_runs import CompRunsAtDB, RunMetadataDict
from ....utils.db import RUNNING_STATE_TO_DB
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
    comp_runs.c.cluster_id: (
        ClusterNotFoundError,
        ("clusters", "cluster_id"),
    ),
}
_DEFAULT_FK_CONSTRAINT_TO_ERROR: Final[tuple[type[DirectorError], tuple]] = (
    DirectorError,
    (),
)


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
        async with self.db_engine.acquire() as conn:
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
            row: RowProxy | None = await result.first()
            if not row:
                raise ComputationalRunNotFoundError
            return CompRunsAtDB.model_validate(row)

    async def list(
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

        async with self.db_engine.acquire() as conn:
            return [
                CompRunsAtDB.model_validate(row)
                async for row in conn.execute(
                    sa.select(comp_runs).where(
                        sa.and_(True, *conditions)  # noqa: FBT003
                    )
                )
            ]

    async def create(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        iteration: PositiveInt | None = None,
        metadata: RunMetadataDict,
        use_on_demand_clusters: bool,
    ) -> CompRunsAtDB:
        try:
            async with self.db_engine.acquire() as conn:
                if iteration is None:
                    # let's get the latest if it exists
                    last_iteration = await conn.scalar(
                        sa.select(comp_runs.c.iteration)
                        .where(
                            (comp_runs.c.user_id == user_id)
                            & (comp_runs.c.project_uuid == f"{project_id}")
                        )
                        .order_by(desc(comp_runs.c.iteration))
                    )
                    iteration = (last_iteration or 0) + 1

                result = await conn.execute(
                    comp_runs.insert()  # pylint: disable=no-value-for-parameter
                    .values(
                        user_id=user_id,
                        project_uuid=f"{project_id}",
                        cluster_id=(
                            cluster_id if cluster_id != DEFAULT_CLUSTER_ID else None
                        ),
                        iteration=iteration,
                        result=RUNNING_STATE_TO_DB[RunningState.PUBLISHED],
                        started=datetime.datetime.now(tz=datetime.UTC),
                        metadata=jsonable_encoder(metadata),
                        use_on_demand_clusters=use_on_demand_clusters,
                    )
                    .returning(literal_column("*"))
                )
                row = await result.first()
                return CompRunsAtDB.model_validate(row)
        except ForeignKeyViolation as exc:
            assert exc.diag.constraint_name  # nosec  # noqa: PT017
            for foreign_key in comp_runs.foreign_keys:
                if exc.diag.constraint_name == foreign_key.name:
                    assert foreign_key.parent is not None  # nosec
                    exc_type, exc_keys = _POSTGRES_FK_COLUMN_TO_ERROR_MAP[
                        foreign_key.parent
                    ]
                    raise exc_type(
                        **{f"{k}": locals().get(k) for k in exc_keys}
                    ) from exc
            raise DirectorError from exc

    async def update(
        self, user_id: UserID, project_id: ProjectID, iteration: PositiveInt, **values
    ) -> CompRunsAtDB | None:
        async with self.db_engine.acquire() as conn:
            result = await conn.execute(
                sa.update(comp_runs)
                .where(
                    (comp_runs.c.project_uuid == f"{project_id}")
                    & (comp_runs.c.user_id == f"{user_id}")
                    & (comp_runs.c.iteration == iteration)
                )
                .values(**values)
                .returning(literal_column("*"))
            )
            row = await result.first()
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
