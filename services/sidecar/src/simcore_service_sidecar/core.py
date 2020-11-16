import asyncio
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Union

import networkx as nx
from aiopg.sa import Engine, SAConnection
from aiopg.sa.result import RowProxy
from celery.utils.log import get_task_logger
from simcore_postgres_database.sidecar_models import (
    StateType,
    comp_pipeline,
    comp_tasks,
)
from simcore_sdk import node_ports
from simcore_sdk.node_ports import log as node_port_log
from sqlalchemy import and_, literal_column

from . import config, exceptions
from .db import DBContextManager
from .executor import Executor
from .rabbitmq import RabbitMQ
from .utils import execution_graph, find_entry_point, is_node_ready

log = get_task_logger(__name__)
log.setLevel(config.SIDECAR_LOGLEVEL)
node_port_log.setLevel(config.SIDECAR_LOGLEVEL)


async def task_required_resources(node_id: str) -> Union[Dict[str, bool], None]:
    """Checks if the comp_task's image field if it requires to use the GPU"""
    try:
        async with DBContextManager() as db_engine:
            async with db_engine.acquire() as db_connection:
                result = await db_connection.execute(
                    query=comp_tasks.select().where(comp_tasks.c.node_id == node_id)
                )
                task = await result.fetchone()

                if not task:
                    log.warning("Task for node_id %s was not found", node_id)
                    raise exceptions.TaskNotFound("Could not find a relative task")

                # Image has to following format
                # {"name": "simcore/services/comp/itis/sleeper", "tag": "1.0.0", "requires_gpu": false, "requires_mpi": false}
                return {
                    "requires_gpu": task["image"]["requires_gpu"],
                    "requires_mpi": task["image"]["requires_mpi"],
                }
    except Exception:  # pylint: disable=broad-except
        log.error(
            "%s\nThe above exception ocurred because it could not be "
            "determined if task requires GPU, MPI  MPI for node_id %s",
            traceback.format_exc(),
            node_id,
        )
        return None


async def _try_get_task_from_db(
    db_connection: SAConnection,
    graph: nx.DiGraph,
    job_request_id: str,
    project_id: str,
    node_id: str,
) -> Optional[RowProxy]:
    # Use SELECT FOR UPDATE TO lock the row
    result = await db_connection.execute(
        query=comp_tasks.select(for_update=True).where(
            (comp_tasks.c.node_id == node_id)
            & (comp_tasks.c.project_id == project_id)
            & (
                (
                    (comp_tasks.c.job_id == None)
                    & (comp_tasks.c.state == StateType.PENDING)
                )
                | (comp_tasks.c.state == StateType.FAILED)
            )
        ),
    )
    task: RowProxy = await result.fetchone()

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
                comp_tasks.c.node_id == node_id,
                comp_tasks.c.project_id == project_id,
            )
        )
        .values(job_id=job_request_id, state=StateType.RUNNING, start=datetime.utcnow())
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
    db_connection: SAConnection,
    project_id: str,
) -> RowProxy:
    # get the pipeline
    result = await db_connection.execute(
        comp_pipeline.select().where(comp_pipeline.c.project_id == project_id)
    )
    if result.rowcount > 1:
        raise exceptions.DatabaseError(
            f"Pipeline {result.rowcount} found instead of only one for project_id {project_id}"
        )

    pipeline: RowProxy = await result.first()
    if not pipeline:
        raise exceptions.DatabaseError(f"Pipeline {project_id} not found")
    log.debug("found pipeline %s", pipeline)
    return pipeline


async def _set_task_status(
    db_engine: Engine, project_id: str, node_id: str, run_result
):
    log.debug("setting task status of %s:%s to %s", project_id, node_id, run_result)
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


async def _set_pipeline_tasks_as_pending(
    conn: SAConnection, graph: nx.DiGraph, project_id: str
):
    node_ids = list(graph.nodes)
    for node_id in node_ids:
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            comp_tasks.update()
            .where(
                (comp_tasks.c.node_id == node_id)
                & (comp_tasks.c.project_id == project_id)
                & (comp_tasks.c.state != StateType.ABORTED)
            )
            .values(state=StateType.PENDING)
        )


async def inspect(
    # pylint: disable=too-many-arguments
    db_engine: Engine,
    rabbit_mq: RabbitMQ,
    job_request_id: str,
    user_id: str,
    project_id: str,
    node_id: Optional[str],
) -> Optional[List[str]]:

    try:
        log.debug(
            "ENTERING inspect with user %s pipeline:node %s: %s",
            user_id,
            project_id,
            node_id,
        )

        task: Optional[RowProxy] = None
        graph: Optional[nx.DiGraph] = None
        async with db_engine.acquire() as connection:
            pipeline: RowProxy = await _get_pipeline_from_db(connection, project_id)
            graph = execution_graph(pipeline)
            if not node_id:
                log.debug("NODE id was zero, this was the entry node id")
                await _set_pipeline_tasks_as_pending(connection, graph, project_id)
                return find_entry_point(graph)
            log.debug("NODE id is %s, getting the task from DB...", node_id)
            task = await _try_get_task_from_db(
                connection, graph, job_request_id, project_id, node_id
            )

        if not task:
            log.debug("no task at hand, let's rest...")
            return
    except asyncio.CancelledError:
        log.warning("Task has been cancelled")
        if node_id:
            await _set_task_status(db_engine, project_id, node_id, StateType.ABORTED)
        raise

    run_result = StateType.FAILED
    try:
        await rabbit_mq.post_log_message(
            user_id,
            project_id,
            node_id,
            "[sidecar]Task found: starting...",
        )

        # config nodeports
        node_ports.node_config.USER_ID = user_id
        node_ports.node_config.NODE_UUID = task.node_id
        node_ports.node_config.PROJECT_ID = task.project_id

        # now proceed actually running the task (we do that after the db session has been closed)
        # try to run the task, return empyt list of next nodes if anything goes wrong

        next_task_nodes = []

        executor = Executor(
            db_engine=db_engine,
            rabbit_mq=rabbit_mq,
            task=task,
            user_id=user_id,
        )
        await executor.run()
        next_task_nodes = list(graph.successors(node_id))
        run_result = StateType.SUCCESS
    except asyncio.CancelledError:
        log.warning("Task has been cancelled")
        run_result = StateType.ABORTED
        await _set_task_status(db_engine, project_id, node_id, run_result)
        raise

    finally:
        if node_id:
            await rabbit_mq.post_log_message(
                user_id,
                project_id,
                node_id,
                f"[sidecar]Task completed with result: {run_result.name}",
            )
            await _set_task_status(db_engine, project_id, node_id, run_result)

    return next_task_nodes
