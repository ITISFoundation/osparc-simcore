import logging
from datetime import datetime
from typing import Dict, Tuple

import networkx as nx
import sqlalchemy as sa
from models_library.projects import NodeID, ProjectID

from ....models.domains.comp_tasks import CompTaskAtDB
from ..tables import NodeClass, StateType, comp_pipeline, comp_tasks
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class CompPipelinesRepository(BaseRepository):
    async def publish_pipeline(
        self, project_id: ProjectID, dag_graph: nx.DiGraph
    ) -> None:
        await self.connection.execute(
            sa.insert(comp_pipeline)
            .values(
                project_id=str(project_id),
                dag_adjacency_list=dag_graph.adj,
                state=StateType.PUBLISHED,
            )
            .on_conflict_do_update(
                index_elements=[comp_pipeline.c.project_id],
                set_={"dag_adjacency_list": dag_graph.adj},
            )
        )


class CompTasksRepository(BaseRepository):
    async def get_comp_tasks(
        self,
        project_id: ProjectID,
    ) -> Dict[NodeID, CompTaskAtDB]:
        tasks: Dict[NodeID, CompTaskAtDB] = {}
        async for row in self.connection.execute(
            sa.select([comp_tasks]).where(
                (comp_tasks.c.project_id == str(project_id))
                & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
            )
        ):
            task_db = CompTaskAtDB.from_orm(row)
            tasks[task_db.node_id] = task_db

        return tasks

    async def publish_tasks(self, project_id: ProjectID) -> None:
        await self.connection.execute(
            sa.update(comp_tasks)
            .where(
                (comp_tasks.c.project_id == str(project_id))
                & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
            )
            .values(state=StateType.PUBLISHED, job_id=None)
        )
