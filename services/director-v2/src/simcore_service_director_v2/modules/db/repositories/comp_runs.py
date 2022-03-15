import logging
from collections import deque
from datetime import datetime
from typing import List, Optional, Set

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from pydantic import PositiveInt
from sqlalchemy.sql import or_
from sqlalchemy.sql.elements import literal_column
from sqlalchemy.sql.expression import desc

from ....models.domains.comp_runs import CompRunsAtDB
from ....models.schemas.constants import ClusterID, UserID
from ....utils.db import RUNNING_STATE_TO_DB
from ..tables import comp_runs
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class CompRunsRepository(BaseRepository):
    async def list(
        self, filter_by_state: Set[RunningState] = None
    ) -> List[CompRunsAtDB]:
        runs_in_db = deque()
        async with self.db_engine.acquire() as conn:
            async for row in conn.execute(
                sa.select([comp_runs]).where(
                    or_(
                        *[
                            comp_runs.c.result == RUNNING_STATE_TO_DB[s]
                            for s in filter_by_state
                        ]
                    )
                )
            ):
                runs_in_db.append(CompRunsAtDB.from_orm(row))
        return list(runs_in_db)

    async def create(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        default_cluster_id: ClusterID,
        iteration: Optional[PositiveInt] = None,
    ) -> CompRunsAtDB:
        async with self.db_engine.acquire() as conn:
            if iteration is None:
                # let's get the latest if it exists
                last_iteration = await conn.scalar(
                    sa.select([comp_runs.c.iteration])
                    .where(
                        (comp_runs.c.user_id == user_id)
                        & (comp_runs.c.project_uuid == str(project_id))
                    )
                    .order_by(desc(comp_runs.c.iteration))
                )
                iteration = (last_iteration or 1) + 1

            result = await conn.execute(
                comp_runs.insert()  # pylint: disable=no-value-for-parameter
                .values(
                    user_id=user_id,
                    project_uuid=f"{project_id}",
                    cluster_id=cluster_id if cluster_id != default_cluster_id else None,
                    iteration=iteration,
                    result=RUNNING_STATE_TO_DB[RunningState.PUBLISHED],
                    started=datetime.utcnow(),
                )
                .returning(literal_column("*"))
            )
            row = await result.first()
            return CompRunsAtDB.from_orm(row)

    async def update(
        self, user_id: UserID, project_id: ProjectID, iteration: PositiveInt, **values
    ) -> Optional[CompRunsAtDB]:
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
            row: RowProxy = await result.first()
            return CompRunsAtDB.from_orm(row) if row else None

    async def set_run_result(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: PositiveInt,
        result_state: RunningState,
        final_state: Optional[bool] = False,
    ) -> Optional[CompRunsAtDB]:
        values = {"result": RUNNING_STATE_TO_DB[result_state]}
        if final_state:
            values.update({"ended": datetime.utcnow()})
        return await self.update(
            user_id,
            project_id,
            iteration,
            **values,
        )
