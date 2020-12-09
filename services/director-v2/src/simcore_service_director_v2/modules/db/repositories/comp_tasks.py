import logging
from datetime import datetime
from typing import List, Optional

import sqlalchemy as sa
from models_library.projects import ProjectID
from models_library.projects_nodes import Node
from models_library.projects_state import RunningState
from models_library.services import (
    Author,
    ServiceDockerData,
    ServiceKeyVersion,
    ServiceType,
)
from sqlalchemy.dialects.postgresql import insert

from ....models.domains.comp_tasks import CompTaskAtDB, Image, NodeSchema
from ....models.domains.projects import ProjectAtDB
from ....models.schemas.services import NodeRequirement, ServiceExtras
from ....utils.computations import to_node_class
from ....utils.logging_utils import log_decorator
from ...director_v0 import DirectorV0Client
from ..tables import NodeClass, StateType, comp_tasks
from ._base import BaseRepository

logger = logging.getLogger(__name__)


@log_decorator(logger=logger)
def _get_fake_service_details(
    service: ServiceKeyVersion,
) -> Optional[ServiceDockerData]:

    if "file-picker" not in service.key:
        return

    file_picker_outputs = {
        "outFile": {
            "label": "File",
            "displayOrder": 0,
            "description": "Chosen File",
            "type": "data:*/*",
        }
    }
    return ServiceDockerData(
        **service.dict(),
        name="File Picker",
        description="File Picker",
        authors=[
            Author(name="Odei Maiz", email="maiz@itis.swiss", affiliation="IT'IS")
        ],
        contact="maiz@itis.swiss",
        inputs={},
        outputs=file_picker_outputs,
        type=ServiceType.FRONTEND,
    )


class CompTasksRepository(BaseRepository):
    @log_decorator(logger=logger)
    async def get_comp_tasks(
        self,
        project_id: ProjectID,
    ) -> List[CompTaskAtDB]:
        tasks: List[CompTaskAtDB] = []
        async for row in self.connection.execute(
            sa.select([comp_tasks]).where(
                (comp_tasks.c.project_id == str(project_id))
                & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
            )
        ):
            task_db = CompTaskAtDB.from_orm(row)
            tasks.append(task_db)

        return tasks

    @log_decorator(logger=logger)
    async def upsert_tasks_from_project(
        self, project: ProjectAtDB, director_client: DirectorV0Client, publish: bool
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
            if not node_details:
                continue

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

            comp_state = RunningState.PUBLISHED if publish else RunningState.NOT_STARTED
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
                state=comp_state
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
    async def mark_project_tasks_as_aborted(self, project: ProjectAtDB) -> None:
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

    @log_decorator(logger=logger)
    async def delete_tasks_from_project(self, project: ProjectAtDB) -> None:
        await self.connection.execute(
            sa.delete(comp_tasks).where(comp_tasks.c.project_id == str(project.uuid))
        )
