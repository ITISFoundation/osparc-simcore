import json
import logging
import socket
from typing import Optional

import aiopg.sa
import tenacity
from servicelib.aiopg_utils import (
    DataSourceName,
    PostgresRetryPolicyUponInitialization,
    create_pg_engine,
    is_postgres_responsive,
)
from simcore_postgres_database.models.comp_tasks import comp_tasks
from sqlalchemy import and_

from . import config
from .exceptions import NodeNotFound

log = logging.getLogger(__name__)


async def _get_node_from_db(
    node_uuid: str, connection: aiopg.sa.SAConnection
) -> comp_tasks:
    log.debug(
        "Reading from comp_tasks table for node uuid %s, project %s",
        node_uuid,
        config.PROJECT_ID,
    )
    result = await connection.execute(
        comp_tasks.select(
            and_(
                comp_tasks.c.node_id == node_uuid,
                comp_tasks.c.project_id == config.PROJECT_ID,
            )
        )
    )
    if result.rowcount > 1:
        log.error("the node id %s is not unique", node_uuid)
    node = await result.fetchone()
    if not node:
        log.error("the node id %s was not found", node_uuid)
        raise NodeNotFound(node_uuid)
    return node


@tenacity.retry(**PostgresRetryPolicyUponInitialization().kwargs)
async def wait_till_postgres_responsive(dsn: DataSourceName) -> None:
    if not is_postgres_responsive(dsn):
        raise Exception


class DBContextManager:
    def __init__(self, db_engine: Optional[aiopg.sa.Engine] = None):
        self._db_engine: aiopg.sa.Engine = db_engine
        self._db_engine_created: bool = False

    async def _create_db_engine(self) -> aiopg.sa.Engine:
        dsn = DataSourceName(
            application_name=f"{__name__}_{id(socket.gethostname())}",
            database=config.POSTGRES_DB,
            user=config.POSTGRES_USER,
            password=config.POSTGRES_PW,
            host=config.POSTGRES_ENDPOINT.split(":")[0],
            port=config.POSTGRES_ENDPOINT.split(":")[1],
        )
        await wait_till_postgres_responsive(dsn)
        engine = await create_pg_engine(dsn, minsize=1, maxsize=4)
        return engine

    async def __aenter__(self):
        if not self._db_engine:
            self._db_engine = await self._create_db_engine()
            self._db_engine_created = True
        return self._db_engine

    async def __aexit__(self, exc_type, exc, tb):
        if self._db_engine_created:
            self._db_engine.close()
            await self._db_engine.wait_closed()
            log.debug(
                "engine '%s' after shutdown: closed=%s, size=%d",
                self._db_engine.dsn,
                self._db_engine.closed,
                self._db_engine.size,
            )


class DBManager:
    def __init__(self, db_engine: Optional[aiopg.sa.Engine] = None):
        self._db_engine = db_engine

    async def write_ports_configuration(self, json_configuration: str, node_uuid: str):
        log.debug("Writing ports configuration to database")

        node_configuration = json.loads(json_configuration)
        async with DBContextManager(self._db_engine) as engine:
            async with engine.acquire() as connection:
                # update the necessary parts
                await connection.execute(
                    # FIXME: E1120:No value for argument 'dml' in method call
                    # pylint: disable=E1120
                    comp_tasks.update()
                    .where(
                        and_(
                            comp_tasks.c.node_id == node_uuid,
                            comp_tasks.c.project_id == config.PROJECT_ID,
                        )
                    )
                    .values(
                        schema=node_configuration["schema"],
                        inputs=node_configuration["inputs"],
                        outputs=node_configuration["outputs"],
                    )
                )

    async def get_ports_configuration_from_node_uuid(self, node_uuid: str) -> str:
        log.debug(
            "Getting ports configuration of node %s from comp_tasks table", node_uuid
        )
        async with DBContextManager(self._db_engine) as engine:
            async with engine.acquire() as connection:
                node = await _get_node_from_db(node_uuid, connection)
                node_json_config = json.dumps(
                    {
                        "schema": node.schema,
                        "inputs": node.inputs,
                        "outputs": node.outputs,
                    }
                )
        log.debug("Found and converted to json")
        return node_json_config
