import logging

import sqlalchemy as sa
from common_library.json_serialization import json_dumps, json_loads
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.db_asyncpg_utils import create_async_engine_and_database_ready
from settings_library.node_ports import NodePortsSettings
from simcore_postgres_database.models.comp_tasks import NodeClass, comp_tasks
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.utils_comp_run_snapshot_tasks import (
    update_for_run_id_and_node_id,
)
from simcore_postgres_database.utils_comp_runs import get_latest_run_id_for_project
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from .exceptions import NodeNotFound, ProjectNotFoundError

_logger = logging.getLogger(__name__)


async def _get_node_from_db(
    project_id: str, node_uuid: str, connection: AsyncConnection
) -> sa.engine.Row:
    _logger.debug(
        "Reading from comp_tasks table for node uuid %s, project %s",
        node_uuid,
        project_id,
    )
    rows_count = await connection.scalar(
        sa.select(sa.func.count())
        .select_from(comp_tasks)
        .where(
            (comp_tasks.c.node_id == node_uuid)
            & (comp_tasks.c.project_id == project_id),
        )
    )
    if rows_count > 1:
        _logger.error("the node id %s is not unique", node_uuid)
    result = await connection.execute(
        sa.select(comp_tasks).where(
            (comp_tasks.c.node_id == node_uuid)
            & (comp_tasks.c.project_id == project_id)
        )
    )
    node = result.one_or_none()
    if not node:
        _logger.error("the node id %s was not found", node_uuid)
        raise NodeNotFound(node_uuid)
    return node


class DBContextManager:
    def __init__(self, db_engine: AsyncEngine | None = None) -> None:
        self._db_engine: AsyncEngine | None = db_engine
        self._db_engine_created: bool = False

    @staticmethod
    async def _create_db_engine() -> AsyncEngine:
        settings = NodePortsSettings.create_from_envs()
        engine = await create_async_engine_and_database_ready(
            settings.POSTGRES_SETTINGS
        )
        assert isinstance(engine, AsyncEngine)  # nosec
        return engine

    async def __aenter__(self) -> AsyncEngine:
        if not self._db_engine:
            self._db_engine = await self._create_db_engine()
            self._db_engine_created = True
        return self._db_engine

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._db_engine and self._db_engine_created:
            await self._db_engine.dispose()


class DBManager:
    def __init__(self, db_engine: AsyncEngine | None = None):
        self._db_engine = db_engine

    async def write_ports_configuration(
        self,
        json_configuration: str,
        project_id: str,
        node_uuid: str,
    ):
        message = (
            f"Writing port configuration to database for "
            f"project={project_id} node={node_uuid}: {json_configuration}"
        )
        _logger.debug(message)

        node_configuration = json_loads(json_configuration)
        async with (
            DBContextManager(self._db_engine) as engine,
            engine.begin() as connection,
        ):
            # 1. Update comp_tasks table
            await connection.execute(
                comp_tasks.update()
                .where(
                    (comp_tasks.c.node_id == node_uuid)
                    & (comp_tasks.c.project_id == project_id),
                )
                .values(
                    schema=node_configuration["schema"],
                    inputs=node_configuration["inputs"],
                    outputs=node_configuration["outputs"],
                    run_hash=node_configuration.get("run_hash"),
                )
            )

            # 2. Update comp_run_snapshot_tasks table only if the node is computational
            node = await _get_node_from_db(project_id, node_uuid, connection)
            if node.node_class == NodeClass.COMPUTATIONAL.value:
                # 2.1 Get latest run id for the project
                _latest_run_id = await get_latest_run_id_for_project(
                    engine, connection, project_id=project_id
                )

                # 2.2 Update comp_run_snapshot_tasks table
                await update_for_run_id_and_node_id(
                    engine,
                    connection,
                    run_id=_latest_run_id,
                    node_id=node_uuid,
                    data={
                        "schema": node_configuration["schema"],
                        "inputs": node_configuration["inputs"],
                        "outputs": node_configuration["outputs"],
                        "run_hash": node_configuration.get("run_hash"),
                    },
                )

    async def get_ports_configuration_from_node_uuid(
        self, project_id: str, node_uuid: str
    ) -> str:
        _logger.debug(
            "Getting ports configuration of node %s from comp_tasks table", node_uuid
        )
        async with (
            DBContextManager(self._db_engine) as engine,
            engine.connect() as connection,
        ):
            node = await _get_node_from_db(project_id, node_uuid, connection)
            node_json_config = json_dumps(
                {
                    "schema": node.schema,
                    "inputs": node.inputs,
                    "outputs": node.outputs,
                    "run_hash": node.run_hash,
                }
            )
        _logger.debug("Found and converted to json")
        return node_json_config

    async def get_project_owner_user_id(self, project_id: ProjectID) -> UserID:
        async with (
            DBContextManager(self._db_engine) as engine,
            engine.connect() as connection,
        ):
            prj_owner = await connection.scalar(
                sa.select(projects.c.prj_owner).where(
                    projects.c.uuid == f"{project_id}"
                )
            )
            if prj_owner is None:
                raise ProjectNotFoundError(project_id)
        return TypeAdapter(UserID).validate_python(prj_owner)
