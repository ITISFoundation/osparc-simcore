import logging

import networkx as nx
import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from sqlalchemy.dialects.postgresql import insert

from ....core.errors import PipelineNotFoundError
from ....models.comp_pipelines import CompPipelineAtDB
from ..tables import comp_pipeline
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class CompPipelinesRepository(BaseRepository):
    async def get_pipeline(self, project_id: ProjectID) -> CompPipelineAtDB:
        async with self.db_engine.acquire() as conn:
            result = await conn.execute(
                sa.select(comp_pipeline).where(
                    comp_pipeline.c.project_id == str(project_id)
                )
            )
            row: RowProxy | None = await result.fetchone()
        if not row:
            raise PipelineNotFoundError(pipeline_id=project_id)
        return CompPipelineAtDB.model_validate(row)

    async def upsert_pipeline(
        self,
        project_id: ProjectID,
        dag_graph: nx.DiGraph,
        publish: bool,
    ) -> None:
        pipeline_at_db = CompPipelineAtDB(
            project_id=project_id,
            dag_adjacency_list=nx.to_dict_of_lists(dag_graph),
            state=RunningState.PUBLISHED if publish else RunningState.NOT_STARTED,
        )
        insert_stmt = insert(comp_pipeline).values(
            **pipeline_at_db.model_dump(by_alias=True)
        )
        # FIXME: This is not a nice thing. this part of the information should be kept in comp_runs.
        update_exclusion_policy = set()
        if not dag_graph.nodes():
            update_exclusion_policy.add("dag_adjacency_list")
        on_update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[comp_pipeline.c.project_id],
            set_=pipeline_at_db.model_dump(
                by_alias=True, exclude_unset=True, exclude=update_exclusion_policy
            ),
        )
        async with self.db_engine.acquire() as conn:
            await conn.execute(on_update_stmt)

    async def delete_pipeline(self, project_id: ProjectID) -> None:
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.delete(comp_pipeline).where(
                    comp_pipeline.c.project_id == str(project_id)
                )
            )

    async def mark_pipeline_state(
        self, project_id: ProjectID, state: RunningState
    ) -> None:
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.update(comp_pipeline)
                .where(comp_pipeline.c.project_id == str(project_id))
                .values(state=state)
            )
