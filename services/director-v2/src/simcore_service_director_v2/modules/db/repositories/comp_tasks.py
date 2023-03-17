import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

import sqlalchemy as sa
from models_library.function_services_catalog import iter_service_docker_data
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.services import ServiceDockerData
from models_library.users import UserID
from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert

from ....core.errors import ErrorDict
from ....models.domains.comp_tasks import CompTaskAtDB, Image, NodeSchema
from ....models.schemas.services import NodeRequirements, ServiceExtras
from ....utils.computations import to_node_class
from ....utils.db import RUNNING_STATE_TO_DB
from ...catalog import CatalogClient
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
_FRONTEND_SERVICES_CATALOG: dict[str, ServiceDockerData] = {
    meta.key: meta for meta in iter_service_docker_data()
}


async def _get_service_details(
    catalog_client: CatalogClient, user_id: UserID, product_name: str, node: Node
) -> ServiceDockerData:
    service_details = await catalog_client.get_service(
        user_id,
        node.key,
        node.version,
        product_name,
    )
    return ServiceDockerData.construct(**service_details)


def _compute_node_requirements(node_resources: dict[str, Any]) -> NodeRequirements:
    node_defined_resources = {}

    for image_data in node_resources.values():
        for resource_name, resource_value in image_data.get("resources", {}).items():
            node_defined_resources[resource_name] = node_defined_resources.get(
                resource_name, 0
            ) + min(resource_value["limit"], resource_value["reservation"])
    return NodeRequirements.parse_obj(node_defined_resources)


async def _generate_tasks_list_from_project(
    project: ProjectAtDB,
    catalog_client: CatalogClient,
    director_client: DirectorV0Client,
    published_nodes: list[NodeID],
    user_id: UserID,
    product_name: str,
) -> list[CompTaskAtDB]:
    list_comp_tasks = []
    for internal_id, node_id in enumerate(project.workbench, 1):
        node: Node = project.workbench[node_id]

        # get node infos
        node_class = to_node_class(node.key)
        node_details: Optional[ServiceDockerData] = None
        node_resources: Optional[dict[str, Any]] = None
        node_extras: Optional[ServiceExtras] = None
        if node_class == NodeClass.FRONTEND:
            node_details = _FRONTEND_SERVICES_CATALOG.get(node.key, None)
        else:
            node_details, node_resources, node_extras = await asyncio.gather(
                _get_service_details(catalog_client, user_id, product_name, node),
                catalog_client.get_service_resources(user_id, node.key, node.version),
                director_client.get_service_extras(node.key, node.version),
            )

        if not node_details:
            continue

        # aggregates node_details and node_extras into Image
        data: dict[str, Any] = {
            "name": node.key,
            "tag": node.version,
        }

        if node_resources:
            data.update(node_requirements=_compute_node_requirements(node_resources))
        if node_extras and node_extras.container_spec:
            data.update(command=node_extras.container_spec.command)
        image = Image.parse_obj(data)

        assert node.state is not None  # nosec
        task_state = node.state.current_status
        if node_id in published_nodes and node_class == NodeClass.COMPUTATIONAL:
            task_state = RunningState.PUBLISHED

        task_db = CompTaskAtDB(
            project_id=project.uuid,
            node_id=NodeID(node_id),
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
    async def get_all_tasks(
        self,
        project_id: ProjectID,
    ) -> list[CompTaskAtDB]:
        tasks: list[CompTaskAtDB] = []
        async with self.db_engine.acquire() as conn:
            async for row in conn.execute(
                sa.select([comp_tasks]).where(
                    comp_tasks.c.project_id == f"{project_id}"
                )
            ):
                task_db = CompTaskAtDB.from_orm(row)
                tasks.append(task_db)

        return tasks

    async def get_comp_tasks(
        self,
        project_id: ProjectID,
    ) -> list[CompTaskAtDB]:
        tasks: list[CompTaskAtDB] = []
        async with self.db_engine.acquire() as conn:
            async for row in conn.execute(
                sa.select([comp_tasks]).where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
                )
            ):
                task_db = CompTaskAtDB.from_orm(row)
                tasks.append(task_db)
        logger.debug("found the tasks: %s", f"{tasks=}")
        return tasks

    async def check_task_exists(self, project_id: ProjectID, node_id: NodeID) -> bool:
        async with self.db_engine.acquire() as conn:
            nid: Optional[str] = await conn.scalar(
                sa.select([comp_tasks.c.node_id]).where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_id == f"{node_id}")
                )
            )
            return nid is not None

    async def upsert_tasks_from_project(
        self,
        project: ProjectAtDB,
        catalog_client: CatalogClient,
        director_client: DirectorV0Client,
        published_nodes: list[NodeID],
        user_id: UserID,
        product_name: str,
    ) -> list[CompTaskAtDB]:
        # NOTE: really do an upsert here because of issue https://github.com/ITISFoundation/osparc-simcore/issues/2125
        list_of_comp_tasks_in_project: list[
            CompTaskAtDB
        ] = await _generate_tasks_list_from_project(
            project,
            catalog_client,
            director_client,
            published_nodes,
            user_id,
            product_name,
        )
        async with self.db_engine.acquire() as conn:
            # get current tasks
            result = await conn.execute(
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
            inserted_comp_tasks_db: list[CompTaskAtDB] = []
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
                row = await result.fetchone()
                assert row  # nosec
                inserted_comp_tasks_db.append(CompTaskAtDB.from_orm(row))
            logger.debug(
                "inserted the following tasks in comp_tasks: %s",
                f"{inserted_comp_tasks_db=}",
            )
            return inserted_comp_tasks_db

    async def mark_project_published_tasks_as_aborted(
        self, project_id: ProjectID
    ) -> None:
        # block all pending tasks, so the sidecars stop taking them
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.update(comp_tasks)
                .where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
                    & (comp_tasks.c.state == StateType.PUBLISHED)
                )
                .values(state=StateType.ABORTED)
            )
        logger.debug("marked project %s published tasks as aborted", f"{project_id=}")

    async def set_project_task_job_id(
        self, project_id: ProjectID, task: NodeID, job_id: str
    ) -> None:
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.update(comp_tasks)
                .where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_id == f"{task}")
                )
                .values(job_id=job_id)
            )
        logger.debug(
            "set project %s task %s with job id: %s",
            f"{project_id=}",
            f"{task=}",
            f"{job_id=}",
        )

    async def set_project_tasks_state(
        self,
        project_id: ProjectID,
        tasks: list[NodeID],
        state: RunningState,
        errors: Optional[list[ErrorDict]] = None,
    ) -> None:
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.update(comp_tasks)
                .where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_id.in_([str(t) for t in tasks]))
                )
                .values(state=RUNNING_STATE_TO_DB[state], errors=errors)
            )
        logger.debug(
            "set project %s tasks %s with state %s",
            f"{project_id=}",
            f"{tasks=}",
            f"{state=}",
        )

    async def delete_tasks_from_project(self, project: ProjectAtDB) -> None:
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.delete(comp_tasks).where(
                    comp_tasks.c.project_id == str(project.uuid)
                )
            )
        logger.debug("deleted tasks from project %s", f"{project.uuid=}")
