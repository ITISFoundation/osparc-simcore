import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.frontend_services_catalog import iter_service_docker_data
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.services import ServiceDockerData, ServiceKeyVersion
from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert

from ....models.domains.comp_tasks import CompTaskAtDB, Image, NodeSchema
from ....models.schemas.services import ServiceExtras
from ....utils.computations import to_node_class
from ....utils.db import RUNNING_STATE_TO_DB
from ....utils.logging_utils import log_decorator
from ...director_v0 import DirectorV0Client
from ..tables import NodeClass, StateType, comp_tasks
from ._base import BaseRepository

logger = logging.getLogger(__name__)

#
# This is a catalog of front-end services that are translated as tasks
#
# The evaluation of this task is already done in the front-end
# The front-end sets the outputs in the node payload and therefore
# no evaluation is expected in the backend.
#
# Examples are nodes like file-picker or parameter/*
#
_FRONTEND_SERVICES_CATALOG: Dict[str, ServiceDockerData] = {
    meta.key: meta
    for meta in iter_service_docker_data()
    if any(name in meta.key for name in ["file-picker", "parameter"])
}
assert (  # nosec
    len(_FRONTEND_SERVICES_CATALOG) == 4
), "If this fails, review filter above and update"  # nosec


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
        node_details: Optional[ServiceDockerData] = None
        node_extras: Optional[ServiceExtras] = None
        if node_class == NodeClass.FRONTEND:
            node_details = _FRONTEND_SERVICES_CATALOG.get(service_key_version.key, None)
        else:
            node_details, node_extras = await asyncio.gather(
                director_client.get_service_details(service_key_version),
                director_client.get_service_extras(service_key_version),
            )

        if not node_details:
            continue

        image = Image(
            name=service_key_version.key,
            tag=service_key_version.version,
            node_requirements=node_extras.node_requirements if node_extras else None,
        )

        assert node.state is not None  # nosec
        task_state = node.state.current_status
        if node_id in published_nodes and node_class == NodeClass.COMPUTATIONAL:
            task_state = RunningState.PUBLISHED

        task_db = CompTaskAtDB(
            project_id=project.uuid,
            node_id=node_id,
            schema=NodeSchema.parse_obj(
                node_details.dict(
                    exclude_unset=True, by_alias=True, include={"inputs", "outputs"}
                )
            ),
            inputs=node.inputs,
            outputs=node.outputs,
            image=image,
            submit=datetime.utcnow(),
            state=task_state,
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
        async with self.db_engine.acquire() as conn:
            async for row in conn.execute(
                sa.select([comp_tasks]).where(
                    (comp_tasks.c.project_id == f"{project_id}")
                )
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
        async with self.db_engine.acquire() as conn:
            async for row in conn.execute(
                sa.select([comp_tasks]).where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
                )
            ):
                task_db = CompTaskAtDB.from_orm(row)
                tasks.append(task_db)

        return tasks

    @log_decorator(logger=logger)
    async def upsert_tasks_from_project(
        self,
        project: ProjectAtDB,
        director_client: DirectorV0Client,
        published_nodes: List[NodeID],
    ) -> List[CompTaskAtDB]:
        # NOTE: really do an upsert here because of issue https://github.com/ITISFoundation/osparc-simcore/issues/2125
        list_of_comp_tasks_in_project: List[
            CompTaskAtDB
        ] = await _generate_tasks_list_from_project(
            project, director_client, published_nodes
        )
        async with self.db_engine.acquire() as conn:
            # get current tasks
            result: RowProxy = await conn.execute(
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
                await conn.execute(
                    sa.delete(comp_tasks).where(
                        (comp_tasks.c.project_id == str(project.uuid))
                        & (comp_tasks.c.node_id == node_id)
                    )
                )

            # insert or update the remaining tasks
            # NOTE: comp_tasks DB only trigger a notification to the webserver if an UPDATE on comp_tasks.outputs or comp_tasks.state is done
            # NOTE: an exception to this is when a frontend service changes its output since there is no node_ports, the UPDATE must be done here.
            inserted_comp_tasks_db: List[CompTaskAtDB] = []
            for comp_task_db in list_of_comp_tasks_in_project:

                insert_stmt = insert(comp_tasks).values(**comp_task_db.to_db_model())

                exclusion_rule = (
                    {"state"}
                    if str(comp_task_db.node_id) not in published_nodes
                    else set()
                )
                if to_node_class(comp_task_db.image.name) != NodeClass.FRONTEND:
                    exclusion_rule.add("outputs")
                on_update_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=[comp_tasks.c.project_id, comp_tasks.c.node_id],
                    set_=comp_task_db.to_db_model(exclude=exclusion_rule),
                ).returning(literal_column("*"))
                result = await conn.execute(on_update_stmt)
                row: RowProxy = await result.fetchone()
                inserted_comp_tasks_db.append(CompTaskAtDB.from_orm(row))
            return inserted_comp_tasks_db

    @log_decorator(logger=logger)
    async def mark_project_tasks_as_aborted(self, project_id: ProjectID) -> None:
        # block all pending tasks, so the sidecars stop taking them
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.update(comp_tasks)
                .where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
                    & (
                        (comp_tasks.c.state == StateType.PUBLISHED)
                        | (comp_tasks.c.state == StateType.PENDING)
                        | (comp_tasks.c.state == StateType.RUNNING)
                    )
                )
                .values(state=StateType.ABORTED)
            )

    @log_decorator(logger=logger)
    async def set_project_task_job_id(
        self, project_id: ProjectID, task: NodeID, job_id: str
    ) -> None:
        # block all pending tasks, so the sidecars stop taking them
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.update(comp_tasks)
                .where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_id == f"{task}")
                )
                .values(job_id=job_id)
            )

    @log_decorator(logger=logger)
    async def set_project_tasks_state(
        self, project_id: ProjectID, tasks: List[NodeID], state: RunningState
    ) -> None:
        # block all pending tasks, so the sidecars stop taking them
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.update(comp_tasks)
                .where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_id.in_([str(t) for t in tasks]))
                )
                .values(state=RUNNING_STATE_TO_DB[state])
            )

    @log_decorator(logger=logger)
    async def delete_tasks_from_project(self, project: ProjectAtDB) -> None:
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.delete(comp_tasks).where(
                    comp_tasks.c.project_id == str(project.uuid)
                )
            )
