import asyncio
import logging
from datetime import datetime
from typing import Any

import arrow
import sqlalchemy as sa
from models_library.errors import ErrorDict
from models_library.function_services_catalog import iter_service_docker_data
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.services import ServiceDockerData, ServiceKeyVersion
from models_library.services_resources import BootMode
from models_library.users import UserID
from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert

from ....models.domains.comp_tasks import CompTaskAtDB, Image, NodeSchema
from ....models.schemas.services import NodeRequirements, ServiceExtras
from ....utils.computations import to_node_class
from ....utils.db import RUNNING_STATE_TO_DB
from ...catalog import CatalogClient, ServiceResources
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
    catalog_client: CatalogClient,
    user_id: UserID,
    product_name: str,
    node: ServiceKeyVersion,
) -> ServiceDockerData:
    service_details = await catalog_client.get_service(
        user_id,
        node.key,
        node.version,
        product_name,
    )
    return ServiceDockerData.construct(**service_details)


def _compute_node_requirements(node_resources: dict[str, Any]) -> NodeRequirements:
    node_defined_resources: dict[str, Any] = {}

    for image_data in node_resources.values():
        for resource_name, resource_value in image_data.get("resources", {}).items():
            node_defined_resources[resource_name] = node_defined_resources.get(
                resource_name, 0
            ) + min(resource_value["limit"], resource_value["reservation"])
    return NodeRequirements.parse_obj(node_defined_resources)


def _compute_node_boot_mode(node_resources: dict[str, Any]) -> BootMode:
    for image_data in node_resources.values():
        return BootMode(image_data.get("boot_modes")[0])
    raise RuntimeError("No BootMode")


async def _get_node_infos(
    catalog_client: CatalogClient,
    director_client: DirectorV0Client,
    user_id: UserID,
    product_name: str,
    node: ServiceKeyVersion,
) -> tuple[ServiceDockerData | None, ServiceResources | None, ServiceExtras | None]:
    if to_node_class(node.key) == NodeClass.FRONTEND:
        return (
            _FRONTEND_SERVICES_CATALOG.get(node.key, None),
            None,
            None,
        )
    result: tuple[
        ServiceDockerData, ServiceResources, ServiceExtras
    ] = await asyncio.gather(
        _get_service_details(catalog_client, user_id, product_name, node),
        catalog_client.get_service_resources(user_id, node.key, node.version),
        director_client.get_service_extras(node.key, node.version),
    )
    return result


async def _generate_tasks_list_from_project(
    project: ProjectAtDB,
    catalog_client: CatalogClient,
    director_client: DirectorV0Client,
    published_nodes: list[NodeID],
    user_id: UserID,
    product_name: str,
) -> list[CompTaskAtDB]:
    list_comp_tasks = []

    unique_service_key_versions = {
        ServiceKeyVersion.construct(
            key=node.key, version=node.version
        )  # the service key version is frozen
        for node in project.workbench.values()
    }
    key_version_to_node_infos = {
        key_version: await _get_node_infos(
            catalog_client, director_client, user_id, product_name, key_version
        )
        for key_version in unique_service_key_versions
    }

    for internal_id, node_id in enumerate(project.workbench, 1):
        node: Node = project.workbench[node_id]
        node_key_version = ServiceKeyVersion.construct(
            key=node.key, version=node.version
        )
        node_details, node_resources, node_extras = key_version_to_node_infos.get(
            node_key_version,
            (
                None,
                None,
                None,
            ),
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
            data["boot_mode"] = _compute_node_boot_mode(node_resources)
        if node_extras and node_extras.container_spec:
            data.update(command=node_extras.container_spec.command)
        image = Image.parse_obj(data)

        assert node.state is not None  # nosec
        task_state = node.state.current_status
        task_progress = node.state.progress
        if (
            node_id in published_nodes
            and to_node_class(node.key) == NodeClass.COMPUTATIONAL
        ):
            task_state = RunningState.PUBLISHED
            task_progress = 0

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
            node_class=to_node_class(node.key),
            progress=task_progress,
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
                sa.select(comp_tasks).where(comp_tasks.c.project_id == f"{project_id}")
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
                sa.select(comp_tasks).where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
                )
            ):
                task_db = CompTaskAtDB.from_orm(row)
                tasks.append(task_db)
        return tasks

    async def check_task_exists(self, project_id: ProjectID, node_id: NodeID) -> bool:
        async with self.db_engine.acquire() as conn:
            nid: str | None = await conn.scalar(
                sa.select(comp_tasks.c.node_id).where(
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
                sa.select(comp_tasks.c.node_id).where(
                    comp_tasks.c.project_id == str(project.uuid)
                )
            )
            # remove the tasks that were removed from project workbench
            if all_nodes := await result.fetchall():
                node_ids_to_delete = [
                    t.node_id for t in all_nodes if t.node_id not in project.workbench
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
                    {"state", "progress"}
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
                .values(
                    state=StateType.ABORTED, progress=1.0, end=arrow.utcnow().datetime
                )
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

    async def update_project_tasks_state(
        self,
        project_id: ProjectID,
        tasks: list[NodeID],
        state: RunningState,
        errors: list[ErrorDict] | None = None,
        *,
        optional_progress: float | None = None,
        optional_started: datetime | None = None,
        optional_stopped: datetime | None = None,
    ) -> None:
        async with self.db_engine.acquire() as conn:
            update_values = {"state": RUNNING_STATE_TO_DB[state], "errors": errors}
            if optional_progress is not None:
                update_values["progress"] = optional_progress
            if optional_started is not None:
                update_values["start"] = optional_started
            if optional_stopped is not None:
                update_values["end"] = optional_stopped
            await conn.execute(
                sa.update(comp_tasks)
                .where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_id.in_([str(t) for t in tasks]))
                )
                .values(**update_values)
            )
        logger.debug(
            "set project %s tasks %s with state %s",
            f"{project_id=}",
            f"{tasks=}",
            f"{state=}",
        )

    async def update_project_task_progress(
        self, project_id: ProjectID, node_id: NodeID, progress: float
    ) -> None:
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.update(comp_tasks)
                .where(
                    (comp_tasks.c.project_id == f"{project_id}")
                    & (comp_tasks.c.node_id == f"{node_id}")
                )
                .values(progress=progress)
            )

        logger.debug(
            "set project %s task %s with progress %s",
            f"{project_id=}",
            f"{node_id=}",
            f"{progress=}",
        )

    async def delete_tasks_from_project(self, project_id: ProjectID) -> None:
        async with self.db_engine.acquire() as conn:
            await conn.execute(
                sa.delete(comp_tasks).where(comp_tasks.c.project_id == f"{project_id}")
            )
        logger.debug("deleted tasks from project %s", f"{project_id=}")
