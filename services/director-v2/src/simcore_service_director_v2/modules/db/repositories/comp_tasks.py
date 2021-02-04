import logging
from datetime import datetime
from typing import List, Optional

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.services import (
    Author,
    ServiceDockerData,
    ServiceKeyVersion,
    ServiceType,
)
from sqlalchemy.dialects.postgresql import insert

from ....models.domains.comp_tasks import CompTaskAtDB, Image, NodeSchema
from ....models.schemas.services import NodeRequirement, ServiceExtras
from ....utils.async_utils import run_sequentially_in_context
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

    if "file-picker" in service.key:
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
    return None


async def _generate_tasks_list_from_project(
    project: ProjectAtDB,
    director_client: DirectorV0Client,
    published_nodes: List[NodeID],
) -> List[CompTaskAtDB]:

    list_comp_tasks = []

    for internal_id, node_id in enumerate(project.workbench, 1):
        node: Node = project.workbench[node_id]

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
            requires_gpu = NodeRequirement.GPU in node_extras.node_requirements
            requires_mpi = NodeRequirement.MPI in node_extras.node_requirements
        image = Image(
            name=service_key_version.key,
            tag=service_key_version.version,
            requires_gpu=requires_gpu,
            requires_mpi=requires_mpi,
        )

        task_db = CompTaskAtDB(
            project_id=project.uuid,
            node_id=node_id,
            schema=NodeSchema(inputs=node_details.inputs, outputs=node_details.outputs),
            inputs=node.inputs,
            outputs=node.outputs,
            image=image,
            submit=datetime.utcnow(),
            state=(
                RunningState.PUBLISHED
                if node_id in published_nodes and node_class == NodeClass.COMPUTATIONAL
                else RunningState.NOT_STARTED
            ),
            internal_id=internal_id,
            node_class=node_class,
        )

        list_comp_tasks.append(task_db)
    return list_comp_tasks


class CompTasksRepository(BaseRepository):
    @log_decorator(logger=logger)
    async def get_all_tasks(
        self,
        project_id: ProjectID,
    ) -> List[CompTaskAtDB]:
        tasks: List[CompTaskAtDB] = []
        async for row in self.connection.execute(
            sa.select([comp_tasks]).where((comp_tasks.c.project_id == str(project_id)))
        ):
            task_db = CompTaskAtDB.from_orm(row)
            tasks.append(task_db)

        return tasks

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

    # pylint: disable=unused-argument
    @run_sequentially_in_context(target_args=["str_project_uuid"])
    async def _sequentially_upsert_tasks_from_project(
        self,
        project: ProjectAtDB,
        director_client: DirectorV0Client,
        published_nodes: List[NodeID],
        str_project_uuid: str,
    ) -> None:

        # NOTE: really do an upsert here because of issue https://github.com/ITISFoundation/osparc-simcore/issues/2125
        list_of_comp_tasks_in_project = await _generate_tasks_list_from_project(
            project, director_client, published_nodes
        )
        # get current tasks
        result: RowProxy = await self.connection.execute(
            sa.select([comp_tasks.c.node_id]).where(
                comp_tasks.c.project_id == str(project.uuid)
            )
        )
        # remove the tasks that were removed from project workbench
        node_ids_to_delete = [
            t.node_id
            for t in await result.fetchall()
            if t.node_id not in project.workbench
        ]
        for node_id in node_ids_to_delete:
            await self.connection.execute(
                sa.delete(comp_tasks).where(
                    (comp_tasks.c.project_id == str(project.uuid))
                    & (comp_tasks.c.node_id == node_id)
                )
            )

        # insert or update the remaining tasks
        # NOTE: comp_tasks DB only trigger a notification to the webserver if an UPDATE on comp_tasks.outputs or comp_tasks.state is done
        # NOTE: an exception to this is when a frontend service changes its output since there is no node_ports, the UPDATE must be done here.
        for comp_task_db in list_of_comp_tasks_in_project:

            insert_stmt = insert(comp_tasks).values(
                **comp_task_db.dict(by_alias=True, exclude_unset=True)
            )

            exclusion_rule = {"state"}
            if to_node_class(comp_task_db.image.name) != NodeClass.FRONTEND:
                exclusion_rule.add("outputs")
            on_update_stmt = insert_stmt.on_conflict_do_update(
                index_elements=[comp_tasks.c.project_id, comp_tasks.c.node_id],
                set_=comp_task_db.dict(
                    by_alias=True, exclude_unset=True, exclude=exclusion_rule
                ),
            )
            await self.connection.execute(on_update_stmt)

    @log_decorator(logger=logger)
    async def upsert_tasks_from_project(
        self,
        project: ProjectAtDB,
        director_client: DirectorV0Client,
        published_nodes: List[NodeID],
    ) -> None:

        # only used by the decorator on the "_sequentially_upsert_tasks_from_project"
        str_project_uuid: str = str(project.uuid)

        # It is guaranteed that in the context of this application  no 2 updates
        # will run in parallel.
        #
        # If we need to scale this service or the same comp_task entry is used in
        # a different service an implementation of "therun_sequentially_in_context"
        # based on redis queues needs to be put in place.
        await self._sequentially_upsert_tasks_from_project(
            project=project,
            director_client=director_client,
            published_nodes=published_nodes,
            str_project_uuid=str_project_uuid,
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
