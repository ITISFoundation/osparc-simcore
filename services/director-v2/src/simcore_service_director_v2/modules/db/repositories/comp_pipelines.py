import logging

import networkx as nx
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from models_library.projects import ProjectID
from models_library.projects_state import RunningState

from ....models.domains.comp_pipelines import CompPipelineAtDB
from ....utils.logging_utils import log_decorator
from ..tables import comp_pipeline
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class CompPipelinesRepository(BaseRepository):
    @log_decorator(logger=logger)
    async def upsert_pipeline(
        self, project_id: ProjectID, dag_graph: nx.DiGraph, publish: bool
    ) -> None:

        pipeline_at_db = CompPipelineAtDB(
            project_id=project_id,
            dag_adjacency_list=nx.to_dict_of_lists(dag_graph),
            state=RunningState.PUBLISHED if publish else RunningState.NOT_STARTED,
        )
        insert_stmt = insert(comp_pipeline).values(**pipeline_at_db.dict(by_alias=True))
        on_update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[comp_pipeline.c.project_id],
            set_=pipeline_at_db.dict(by_alias=True, exclude_unset=True),
        )
        await self.connection.execute(on_update_stmt)

    @log_decorator(logger=logger)
    async def delete_pipeline(self, project_id: ProjectID) -> None:
        await self.connection.execute(
            sa.delete(comp_pipeline).where(
                comp_pipeline.c.project_id == str(project_id)
            )
        )
