import logging
from typing import List, Optional, Set

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from pydantic import PositiveInt
from simcore_service_director_v2.utils.db import RUNNING_STATE_TO_DB
from sqlalchemy.sql import or_
from sqlalchemy.sql.elements import literal_column
from sqlalchemy.sql.expression import desc

from ....models.domains.comp_runs import CompRunsAtDB
from ....models.schemas.constants import UserID
from ..tables import comp_runs
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class CompRunsRepository(BaseRepository):
    async def list(
        self, filter_by_state: Set[RunningState] = None
    ) -> List[CompRunsAtDB]:
        runs_in_db = []
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
        return runs_in_db

    async def create(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: Optional[PositiveInt] = None,
    ) -> CompRunsAtDB:
        async with self.db_engine.acquire() as conn:
            if iteration is None:
                # let's get the latest if it exists
                last_iteration = await conn.scalar(
                    sa.select(comp_runs.c.iteration)
                    .where(
                        (comp_runs.c.user_id == user_id)
                        & (comp_runs.c.project_id == str(project_id))
                    )
                    .order_by(desc(comp_runs.c.iteration))
                    .limit(1)
                )
                iteration = last_iteration or 1

            row: RowProxy = await conn.execute(
                sa.insert(comp_runs)
                .values(user_id=user_id, project_id=project_id, iteration=iteration)
                .returning(literal_column("*"))
            ).first()
            return CompRunsAtDB.from_orm(row)

    async def update(
        self, user_id: UserID, project_id: ProjectID, iteration: PositiveInt, **values
    ) -> CompRunsAtDB:
        async with self.db_engine.acquire() as conn:
            row: RowProxy = await conn.execute(
                sa.update(comp_runs)
                .where(
                    (comp_runs.c.project_id == str(project_id))
                    & (comp_runs.c.user_id == str(user_id))
                    & (comp_runs.c.iteration == iteration)
                )
                .values(**values)
                .returning(literal_column("*"))
            ).first()
            return CompRunsAtDB.from_orm(row)

    async def set_run_result(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: PositiveInt,
        result_state: RunningState,
    ) -> CompRunsAtDB:
        return self.update(user_id, project_id, iteration, result=result_state)
