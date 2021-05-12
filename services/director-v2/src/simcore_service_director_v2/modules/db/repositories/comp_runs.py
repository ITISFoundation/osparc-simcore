import logging
from typing import List, Set

import sqlalchemy as sa
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from pydantic import PositiveInt
from simcore_service_director_v2.utils.db import RUNNING_STATE_TO_DB
from sqlalchemy.sql import or_
from sqlalchemy.sql.elements import literal_column

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

    async def update(
        self, user_id: UserID, project_id: ProjectID, iteration: PositiveInt, **values
    ) -> CompRunsAtDB:
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.update(comp_runs)
                .where(
                    (comp_runs.c.project_id == str(project_id))
                    & (comp_runs.c.user_id == str(user_id))
                    & (comp_runs.c.iteration == iteration)
                )
                .values(**values)
                .returning(literal_column("*"))
            )
