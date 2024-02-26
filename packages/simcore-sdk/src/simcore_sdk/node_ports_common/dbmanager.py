import json
import logging
import os
import socket
from typing import Any

import aiopg.sa
import sqlalchemy as sa
import tenacity
from aiopg.sa.engine import Engine
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.common_aiopg_utils import DataSourceName, create_pg_engine
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from settings_library.node_ports import NodePortsSettings
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.utils_aiopg import (
    close_engine,
    raise_if_migration_not_ready,
)
from sqlalchemy import and_

from .exceptions import NodeNotFound, ProjectNotFoundError

log = logging.getLogger(__name__)


async def _get_node_from_db(
    project_id: str, node_uuid: str, connection: aiopg.sa.SAConnection
) -> RowProxy:
    log.debug(
        "Reading from comp_tasks table for node uuid %s, project %s",
        node_uuid,
        project_id,
    )
    result = await connection.execute(
        sa.select(comp_tasks).where(
            and_(
                comp_tasks.c.node_id == node_uuid,
                comp_tasks.c.project_id == project_id,
            )
        )
    )
    if result.rowcount > 1:
        log.error("the node id %s is not unique", node_uuid)
    node: RowProxy | None = await result.first()
    if not node:
        log.error("the node id %s was not found", node_uuid)
        raise NodeNotFound(node_uuid)
    return node


@tenacity.retry(**PostgresRetryPolicyUponInitialization().kwargs)
async def _ensure_postgres_ready(dsn: DataSourceName) -> Engine:
    engine = await create_pg_engine(dsn, minsize=1, maxsize=4)
    try:
        await raise_if_migration_not_ready(engine)
    except Exception:
        await close_engine(engine)
        raise
    return engine


class DBContextManager:
    def __init__(self, db_engine: aiopg.sa.Engine | None = None):
        self._db_engine: aiopg.sa.Engine | None = db_engine
        self._db_engine_created: bool = False

    @staticmethod
    async def _create_db_engine() -> aiopg.sa.Engine:
        settings = NodePortsSettings.create_from_envs()
        dsn = DataSourceName(
            application_name=f"{__name__}_{socket.gethostname()}_{os.getpid()}",
            database=settings.POSTGRES_SETTINGS.POSTGRES_DB,
            user=settings.POSTGRES_SETTINGS.POSTGRES_USER,
            password=settings.POSTGRES_SETTINGS.POSTGRES_PASSWORD.get_secret_value(),
            host=settings.POSTGRES_SETTINGS.POSTGRES_HOST,
            port=settings.POSTGRES_SETTINGS.POSTGRES_PORT,
        )

        engine = await _ensure_postgres_ready(dsn)
        return engine

    async def __aenter__(self):
        if not self._db_engine:
            self._db_engine = await self._create_db_engine()
            self._db_engine_created = True
        return self._db_engine

    async def __aexit__(self, exc_type, exc, tb):
        if self._db_engine and self._db_engine_created:
            await close_engine(self._db_engine)
            log.debug(
                "engine '%s' after shutdown: closed=%s, size=%d",
                self._db_engine.dsn,
                self._db_engine.closed,
                self._db_engine.size,
            )


class DBManager:
    def __init__(self, db_engine: aiopg.sa.Engine | None = None):
        self._db_engine = db_engine

    async def write_ports_configuration(
        self, json_configuration: str, project_id: str, node_uuid: str
    ):
        message = (
            f"Writing port configuration to database for "
            f"project={project_id} node={node_uuid}: {json_configuration}"
        )
        log.debug(message)

        node_configuration = json.loads(json_configuration)
        async with DBContextManager(
            self._db_engine
        ) as engine, engine.acquire() as connection:
            # update the necessary parts
            await connection.execute(
                comp_tasks.update()
                .where(
                    and_(
                        comp_tasks.c.node_id == node_uuid,
                        comp_tasks.c.project_id == project_id,
                    )
                )
                .values(
                    schema=node_configuration["schema"],
                    inputs=node_configuration["inputs"],
                    outputs=node_configuration["outputs"],
                    run_hash=node_configuration.get("run_hash"),
                )
            )

    async def get_ports_configuration_from_node_uuid(
        self, project_id: str, node_uuid: str
    ) -> str:
        log.debug(
            "Getting ports configuration of node %s from comp_tasks table", node_uuid
        )
        async with DBContextManager(
            self._db_engine
        ) as engine, engine.acquire() as connection:
            node: RowProxy = await _get_node_from_db(project_id, node_uuid, connection)
            node_json_config = json.dumps(
                {
                    "schema": node.schema,
                    "inputs": node.inputs,
                    "outputs": node.outputs,
                    "run_hash": node.run_hash,
                }
            )
        log.debug("Found and converted to json")
        return node_json_config

    async def get_project_owner_user_id(self, project_id: ProjectID) -> UserID:
        async with DBContextManager(
            self._db_engine
        ) as engine, engine.acquire() as connection:
            prj_owner: Any | None = await connection.scalar(
                sa.select(projects.c.prj_owner).where(
                    projects.c.uuid == f"{project_id}"
                )
            )
            if prj_owner is None:
                raise ProjectNotFoundError(project_id)
        return UserID(prj_owner)
