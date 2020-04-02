from datetime import datetime
from typing import List, Optional

import aiopg
import networkx as nx
from celery.utils.log import get_task_logger
from sqlalchemy import and_, literal_column

from simcore_postgres_database.sidecar_models import (  # PENDING,
    FAILED,
    RUNNING,
    SUCCESS,
    UNKNOWN,
    comp_pipeline,
    comp_tasks,
)
from simcore_sdk import node_ports
from simcore_sdk.node_ports import log as node_port_log

from . import config, exceptions
from .executor import Sidecar
from .rabbitmq import RabbitMQ
from .utils import execution_graph, find_entry_point, is_node_ready

log = get_task_logger(__name__)
log.setLevel(config.SIDECAR_LOGLEVEL)
node_port_log.setLevel(config.SIDECAR_LOGLEVEL)


async def _try_get_task_from_db(
    db_connection: aiopg.sa.SAConnection,
    graph: nx.DiGraph,
    job_request_id: int,
    project_id: str,
    node_id: str,
) -> Optional[aiopg.sa.result.RowProxy]:
    task: aiopg.sa.result.RowProxy = None
    # Use SELECT FOR UPDATE TO lock the row
    result = await db_connection.execute(
        query=comp_tasks.select(for_update=True).where(
            and_(
                comp_tasks.c.node_id == node_id,
                comp_tasks.c.project_id == project_id,
                comp_tasks.c.job_id == None,
                comp_tasks.c.state == UNKNOWN,
            )
        )
    )
    task = await result.fetchone()

    if not task:
        log.debug("No task found")
        return

    # Check if node's dependecies are there
    if not await is_node_ready(task, graph, db_connection, log):
        log.debug("TASK %s NOT YET READY", task.internal_id)
        return

    # the task is ready!
    result = await db_connection.execute(
        # FIXME: E1120:No value for argument 'dml' in method call
        # pylint: disable=E1120
        comp_tasks.update()
        .where(
            and_(
                comp_tasks.c.node_id == node_id, comp_tasks.c.project_id == project_id,
            )
        )
        .values(job_id=job_request_id, state=RUNNING, start=datetime.utcnow())
        .returning(literal_column("*"))
    )
    task = await result.fetchone()
    log.debug(
        "Task %s taken for project:node %s:%s",
        task.job_id,
        task.project_id,
        task.node_id,
    )
    return task


async def _get_pipeline_from_db(
    db_connection: aiopg.sa.SAConnection, project_id: str,
) -> aiopg.sa.result.RowProxy:
    pipeline: aiopg.sa.result.RowProxy = None
    # get the pipeline
    result = await db_connection.execute(
        comp_pipeline.select().where(comp_pipeline.c.project_id == project_id)
    )
    if result.rowcount > 1:
        raise exceptions.DatabaseError(
            f"Pipeline {result.rowcount} found instead of only one for project_id {project_id}"
        )

    pipeline = await result.first()
    if not pipeline:
        raise exceptions.DatabaseError(f"Pipeline {project_id} not found")
    log.debug("found pipeline %s", pipeline)
    return pipeline


async def inspect(
    # pylint: disable=too-many-arguments
    db_engine: aiopg.sa.Engine,
    rabbit_mq: RabbitMQ,
    job_request_id: int,
    user_id: str,
    project_id: str,
    node_id: str,
) -> Optional[List[str]]:
    log.debug(
        "ENTERING inspect with user %s pipeline:node %s: %s",
        user_id,
        project_id,
        node_id,
    )

    pipeline: aiopg.sa.result.RowProxy = None
    task: aiopg.sa.result.RowProxy = None
    graph: nx.DiGraph = None
    async with db_engine.acquire() as connection:
        pipeline = await _get_pipeline_from_db(connection, project_id)
        graph = execution_graph(pipeline)
        if not node_id:
            log.debug("NODE id was zero, this was the entry node id")
            return find_entry_point(graph)
        task = await _try_get_task_from_db(
            connection, graph, job_request_id, project_id, node_id
        )

    if not task:
        log.debug("no task at hand, let's rest...")
        return

    # config nodeports
    node_ports.node_config.USER_ID = user_id
    node_ports.node_config.NODE_UUID = task.node_id
    node_ports.node_config.PROJECT_ID = task.project_id

    # now proceed actually running the task (we do that after the db session has been closed)
    # try to run the task, return empyt list of next nodes if anything goes wrong
    run_result = SUCCESS
    next_task_nodes = []
    try:
        sidecar = Sidecar(
            db_engine=db_engine, rabbit_mq=rabbit_mq, task=task, user_id=user_id,
        )
        await sidecar.run()
        next_task_nodes = list(graph.successors(node_id))
    except exceptions.SidecarException:
        run_result = FAILED
        log.exception("Error during execution")

    finally:
        async with db_engine.acquire() as connection:
            await connection.execute(
                # FIXME: E1120:No value for argument 'dml' in method call
                # pylint: disable=E1120
                comp_tasks.update()
                .where(
                    and_(
                        comp_tasks.c.node_id == node_id,
                        comp_tasks.c.project_id == project_id,
                    )
                )
                .values(state=run_result, end=datetime.utcnow())
            )

    return next_task_nodes
