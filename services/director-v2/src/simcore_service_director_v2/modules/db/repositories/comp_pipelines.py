import logging
from collections import deque
from typing import List, Set

import networkx as nx
import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from simcore_service_director_v2.utils.db import RUNNING_STATE_TO_DB
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import or_

from ....models.domains.comp_pipelines import CompPipelineAtDB
from ....models.schemas.constants import UserID
from ....utils.exceptions import PipelineNotFoundError
from ....utils.logging_utils import log_decorator
from ..tables import comp_pipeline
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class CompPipelinesRepository(BaseRepository):
    async def list_pipelines_with_state(
        self, state: Set[RunningState] = None
    ) -> List[CompPipelineAtDB]:
        pipelines_in_db = deque()
        async with self.db_engine.acquire() as conn:
            async for row in conn.execute(
                sa.select([comp_pipeline]).where(
                    or_(
                        *[
                            comp_pipeline.c.state == RUNNING_STATE_TO_DB[s]
                            for s in state
                        ]
                    )
                )
            ):
                pipelines_in_db.append(CompPipelineAtDB.from_orm(row))
        return list(pipelines_in_db)

    @log_decorator(logger=logger)
    async def get_pipeline(self, project_id: ProjectID) -> CompPipelineAtDB:
        async with self.db_engine.acquire() as conn:
            result = await conn.execute(
                sa.select([comp_pipeline]).where(
                    comp_pipeline.c.project_id == str(project_id)
                )
            )
            row: RowProxy = await result.fetchone()
        if not row:
            raise PipelineNotFoundError(str(project_id))
        return CompPipelineAtDB.from_orm(row)

    @log_decorator(logger=logger)
    async def upsert_pipeline(
        self,
        user_id: UserID,
        project_id: ProjectID,
        dag_graph: nx.DiGraph,
        publish: bool,
    ) -> None:

        pipeline_at_db = CompPipelineAtDB(
            user_id=user_id,
            project_id=project_id,
            dag_adjacency_list=nx.to_dict_of_lists(dag_graph),
            state=RunningState.PUBLISHED if publish else RunningState.NOT_STARTED,
        )
        insert_stmt = insert(comp_pipeline).values(**pipeline_at_db.dict(by_alias=True))
        on_update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[comp_pipeline.c.project_id],
            set_=pipeline_at_db.dict(by_alias=True, exclude_unset=True),
        )
        async with self.db_engine.acquire() as conn:
            await conn.execute(on_update_stmt)

    @log_decorator(logger=logger)
    async def delete_pipeline(self, project_id: ProjectID) -> None:
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.delete(comp_pipeline).where(
                    comp_pipeline.c.project_id == str(project_id)
                )
            )

    @log_decorator(logger=logger)
    async def mark_pipeline_state(
        self, project_id: ProjectID, state: RunningState
    ) -> None:
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.update(comp_pipeline)
                .where(comp_pipeline.c.project_id == str(project_id))
                .values(state=state)
            )
