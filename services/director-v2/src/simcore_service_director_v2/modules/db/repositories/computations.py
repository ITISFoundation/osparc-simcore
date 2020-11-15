import logging
from datetime import datetime
from typing import Dict

import networkx as nx
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from models_library.nodes import Node, NodeID
from models_library.projects import ProjectID, RunningState
from models_library.services import (
    Author,
    ServiceDockerData,
    ServiceKeyVersion,
    ServiceType,
)

from ....models.domains.comp_pipelines import CompPipelineAtDB
from ....models.domains.comp_tasks import CompTaskAtDB, Image, NodeSchema
from ....models.domains.projects import ProjectAtDB
from ....models.schemas.services import NodeRequirement, ServiceExtras
from ....utils.computations import to_node_class
from ....utils.logging_utils import log_decorator
from ...director_v0 import DirectorV0Client
from ..tables import NodeClass, StateType, comp_pipeline, comp_tasks
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class CompPipelinesRepository(BaseRepository):
    @log_decorator(logger=logger)
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


@log_decorator(logger=logger)
def _get_fake_service_details(service: ServiceKeyVersion) -> ServiceDockerData:
    if "file-picker" in service.key:
        file_picker_outputs = {
            "outFile": {
                "label": "the output",
                "displayOrder": 0,
                "description": "a file",
                "type": "data:*/*",
            }
        }
        file_picker_type = ServiceType.FRONTEND
        return ServiceDockerData(
            **service.dict(),
            name="file-picker",
            description="file-picks",
            authors=[
                Author(name="ITIS", email="itis@support.com", affiliation="IT'IS")
            ],
            contact="itis@support.com",
            inputs={},
            outputs=file_picker_outputs,
            type=file_picker_type,
        )
    raise ValueError("")


class CompTasksRepository(BaseRepository):
    @log_decorator(logger=logger)
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

    @log_decorator(logger=logger)
    async def publish_tasks_from_project(
        self,
        project: ProjectAtDB,
        director_client: DirectorV0Client,
    ) -> None:
        # start by removing the old tasks if they exist
        await self.connection.execute(
            sa.delete(comp_tasks).where(comp_tasks.c.project_id == str(project.uuid))
        )
        # create the tasks
        workbench = project.workbench
        internal_id = 1
        for node_id in workbench:
            node: Node = workbench[node_id]

            service_key_version = ServiceKeyVersion(
                key=node.key,
                version=node.version,
            )
            node_class = to_node_class(service_key_version.key)
            node_details: ServiceDockerData = None
            node_extras: ServiceExtras = None
            if node_class == NodeClass.FRONTEND:
                node_details = _get_fake_service_details(service_key_version)
            else:
                node_details = await director_client.get_service_details(
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
                name=service_key_version.key,
                tag=service_key_version.version,
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
                state=RunningState.PUBLISHED
                if node_class == NodeClass.COMPUTATIONAL
                else RunningState.NOT_STARTED,
                internal_id=internal_id,
                node_class=node_class,
            )
            internal_id = internal_id + 1

            await self.connection.execute(
                insert(comp_tasks).values(
                    **task_db.dict(by_alias=True, exclude_unset=True)
                )
            )

    @log_decorator(logger=logger)
    async def abort_tasks_from_project(self, project: ProjectAtDB) -> None:
        # block all pending tasks, so the sidecars stop taking them
        await self.connection.execute(
            sa.update(comp_tasks)
            .where(
                (comp_tasks.c.project_id == str(project.uuid))
                & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
                & (
                    (comp_tasks.c.state == StateType.PUBLISHED)
                    | (comp_tasks.c.state == StateType.PENDING)
                )
            )
            .values(state=StateType.ABORTED)
        )
