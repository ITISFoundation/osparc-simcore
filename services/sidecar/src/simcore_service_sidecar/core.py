import asyncio
import logging
from datetime import datetime
from typing import Optional

import networkx as nx
from aiopg.sa import Engine, SAConnection
from aiopg.sa.result import RowProxy
from simcore_postgres_database.sidecar_models import (
    StateType,
    comp_pipeline,
    comp_tasks,
)
from simcore_sdk.node_ports_v2 import log as node_port_v2_log
from sqlalchemy import and_, literal_column

from . import config, exceptions
from .boot_mode import BootMode
from .executor import Executor
from .rabbitmq import RabbitMQ
from .utils import execution_graph

log = logging.getLogger(__name__)
log.setLevel(config.SIDECAR_LOGLEVEL)
node_port_v2_log.setLevel(config.SIDECAR_LOGLEVEL)


async def _try_get_task_from_db(
    db_connection: SAConnection,
    job_request_id: str,
    project_id: str,
    node_id: str,
) -> Optional[RowProxy]:
    # Use SELECT FOR UPDATE TO lock the row
    result = await db_connection.execute(
        query=comp_tasks.select(for_update=True).where(
            (comp_tasks.c.node_id == node_id)
            & (comp_tasks.c.project_id == project_id)
            & ((comp_tasks.c.state == StateType.PENDING))
        ),
    )
    task: RowProxy = await result.fetchone()

    if not task:
        log.debug("No task found")
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


async def _set_task_state(
    conn: SAConnection, project_id: str, node_id: str, state: StateType
):
    log.debug("setting task status of %s:%s to %s", project_id, node_id, state)
    await conn.execute(
        # pylint: disable=E1120
        comp_tasks.update()
        .where(
            and_(
                comp_tasks.c.node_id == node_id,
                comp_tasks.c.project_id == project_id,
            )
        )
        .values(state=state, end=datetime.utcnow())
    )


async def _set_tasks_state(
    conn: SAConnection,
    project_id: str,
    graph: nx.DiGraph,
    state: StateType,
    offset: int = 0,
):
    log.debug("setting tasks state from %s to %s", graph, state)
    for node_id in list(graph.nodes())[offset:]:
        await _set_task_state(conn, project_id, node_id, state)


async def run_computational_task(
    # pylint: disable=too-many-arguments
    db_engine: Engine,
    rabbit_mq: RabbitMQ,
    job_request_id: str,
    user_id: str,
    project_id: str,
    node_id: str,
    retry: int,
    max_retries: int,
    sidecar_mode: BootMode,
) -> None:

    async with db_engine.acquire() as connection:
        task: Optional[RowProxy] = None
        graph: Optional[nx.DiGraph] = None
        try:
            log.debug(
                "ENTERING inspect with user %s pipeline:node %s: %s",
                user_id,
                project_id,
                node_id,
            )

            pipeline: RowProxy = await _get_pipeline_from_db(connection, project_id)
            graph = execution_graph(pipeline)
            log.debug("NODE id is %s, getting the task from DB...", node_id)
            task = await _try_get_task_from_db(
                connection, job_request_id, project_id, node_id
            )

            if not task:
                log.warning(
                    "Worker received task for user %s, project %s, node %s, but the task is already taken! this should not happen. going back to sleep...",
                    user_id,
                    project_id,
                    node_id,
                )
                return
        except asyncio.CancelledError:
            log.warning("Task has been cancelled")
            await _set_task_state(connection, project_id, node_id, StateType.ABORTED)
            raise

        run_result = StateType.FAILED
        try:
            await rabbit_mq.post_log_message(
                user_id,
                project_id,
                node_id,
                "[sidecar]Task found: starting...",
            )

            # now proceed actually running the task (we do that after the db session has been closed)
            # try to run the task, return empyt list of next nodes if anything goes wrong
            executor = Executor(
                db_engine=db_engine,
                rabbit_mq=rabbit_mq,
                task=task,
                user_id=user_id,
                sidecar_mode=sidecar_mode,
            )
            await executor.run()
            run_result = StateType.SUCCESS
        except asyncio.CancelledError:
            log.warning("Task has been cancelled")
            run_result = StateType.ABORTED
            raise

        finally:
            await rabbit_mq.post_log_message(
                user_id,
                project_id,
                node_id,
                f"[sidecar]Task completed with result: {run_result.name} [Trial {retry+1}/{max_retries}]",
            )
            if (retry + 1) < max_retries and run_result == StateType.FAILED:
                # try again!
                run_result = StateType.PENDING
            await _set_task_state(connection, project_id, node_id, run_result)
            if run_result == StateType.FAILED:
                # set the successive tasks as ABORTED
                await _set_tasks_state(
                    connection,
                    project_id,
                    nx.bfs_tree(graph, node_id),
                    StateType.ABORTED,
                    offset=1,
                )
