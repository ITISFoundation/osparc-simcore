import logging
import re
from datetime import datetime
from typing import Dict

import networkx as nx
from simcore_service_director_v2.models.domains.comp_pipelines import CompPipelineAtDB
import sqlalchemy as sa
from models_library.projects import Node, NodeID, ProjectID, RunningState
from models_library.services import KEY_RE, ServiceDockerData, ServiceKeyVersion
from simcore_service_director_v2.models.domains.projects import ProjectAtDB
from simcore_service_director_v2.models.schemas.services import (
    NodeRequirement,
    ServiceExtras,
)
from sqlalchemy.dialects.postgresql import insert

from ....models.domains.comp_tasks import CompTaskAtDB, Image, NodeSchema
from ...director_v0 import DirectorV0Client
from ..tables import NodeClass, StateType, comp_pipeline, comp_tasks
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class CompPipelinesRepository(BaseRepository):
    async def publish_pipeline(
        self, project_id: ProjectID, dag_graph: nx.DiGraph
    ) -> None:

        pipeline_at_db = CompPipelineAtDB(
            project_id=project_id,
            dag_adjacency_list=nx.to_dict_of_lists(dag_graph),
            state=RunningState.PUBLISHED,
        )
        insert_stmt = insert(comp_pipeline).values(**pipeline_at_db.dict(by_alias=True))
        on_update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[comp_pipeline.c.project_id],
            set_=pipeline_at_db.dict(by_alias=True, exclude_unset=True),
        )
        await self.connection.execute(on_update_stmt)


_node_key_re = re.compile(KEY_RE)
_STR_TO_NODECLASS = {
    "comp": NodeClass.COMPUTATIONAL,
    "dynamic": NodeClass.INTERACTIVE,
    "frontend": NodeClass.FRONTEND,
}


def _to_node_class(node_details: Node) -> NodeClass:
    match = _node_key_re.match(node_details.key)
    if match:
        return _STR_TO_NODECLASS.get(match.group(3))
    raise ValueError


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

    async def publish_tasks_from_project(
        self,
        project: ProjectAtDB,
        dag_graph: nx.DiGraph,
        director_client: DirectorV0Client,
    ) -> None:
        # start by removing the old tasks if they exist
        await self.connection.execute(
            sa.delete(comp_tasks).where(comp_tasks.c.project_id == str(project.uuid))
        )
        # create the tasks
        workbench = project.workbench
        internal_id = 1
        for node_id in dag_graph.nodes:
            if not node_id in workbench:
                raise ValueError(
                    f"Node {node_id} is not available in workbench of project {project.uuid}"
                )

            node: Node = workbench[node_id]

            service_key_version = ServiceKeyVersion(
                key=dag_graph.nodes[node_id]["key"],
                version=dag_graph.nodes[node_id]["version"],
            )

            node_details: ServiceDockerData = await director_client.get_service_details(
                service_key_version
            )
            node_extras: ServiceExtras = await director_client.get_service_extras(
                service_key_version
            )
            requires_mpi = False
            requires_gpu = False
            if node_extras:
                requires_gpu = node_extras.node_requirements == NodeRequirement.GPU
                requires_mpi = node_extras.node_requirements == NodeRequirement.MPI
            image = Image(
                name=node_details.key,
                tag=node_details.version,
                requires_gpu=requires_gpu,
                requires_mpi=requires_mpi,
            )

            task_db = CompTaskAtDB(
                project_id=project.uuid,
                node_id=node_id,
                schema=NodeSchema(
                    inputs=node_details.inputs, outputs=node_details.outputs
                ),
                inputs=node.inputs,
                outputs=node.outputs,
                image=image,
                submit=datetime.utcnow(),
                state=RunningState.PUBLISHED,
                internal_id=internal_id,
                node_class=_to_node_class(node_details),
            )
            internal_id = internal_id + 1

            await self.connection.execute(
                insert(comp_tasks).values(
                    **task_db.dict(by_alias=True, exclude_unset=True)
                )
            )
