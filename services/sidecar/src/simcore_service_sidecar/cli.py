import asyncio
import logging
from typing import Callable, List, Optional

import click

from .celery_task_utils import cancel_task
from .config import SIDECAR_INTERVAL_TO_CHECK_TASK_ABORTED_S
from .core import inspect
from .db import DBContextManager
from .rabbitmq import RabbitMQ
from .utils import wrap_async_call

log = logging.getLogger(__name__)


@click.command()
@click.option("--job_id", default=0, type=int, help="The job ID")
@click.option("--user_id", default=0, type=int, help="The user ID")
@click.option("--project_id", default="0", help="The project ID")
@click.option("--node_id", default=None, help="The node ID or nothing")
def main(
    job_id: str, user_id: str, project_id: str, node_id: str
) -> Optional[List[str]]:

    try:
        next_task_nodes, _ = wrap_async_call(
            run_sidecar(job_id, user_id, project_id, node_id=node_id)
        )
        return next_task_nodes
    except Exception:  # pylint: disable=broad-except
        log.exception("Uncaught exception")


async def perdiodicaly_check_if_aborted(is_aborted_cb: Callable[[], bool]) -> None:
    log.info("Starting periodic check of task abortion...")
    while await asyncio.sleep(SIDECAR_INTERVAL_TO_CHECK_TASK_ABORTED_S, result=True):
        if is_aborted_cb():
            log.info("Task was aborted. Cancelling...")
            asyncio.get_event_loop().call_soon(cancel_task(run_sidecar))


async def run_sidecar(
    job_id: str,
    user_id: str,
    project_id: str,
    node_id: Optional[str] = None,
    is_aborted_cb: Optional[Callable[[], bool]] = None,
) -> Optional[List[str]]:

    log.info(
        "STARTING task %s processing for user %s, project %s, node %s",
        job_id,
        user_id,
        project_id,
        node_id,
    )

    abortion_task = (
        asyncio.get_event_loop().create_task(
            perdiodicaly_check_if_aborted(is_aborted_cb)
        )
        if is_aborted_cb
        else None
    )
    try:
        async with DBContextManager() as db_engine:
            async with RabbitMQ() as rabbit_mq:
                next_task_nodes: Optional[List[str]] = await inspect(
                    db_engine, rabbit_mq, job_id, user_id, project_id, node_id=node_id
                )
                log.info(
                    "COMPLETED task %s processing for user %s, project %s, node %s",
                    job_id,
                    user_id,
                    project_id,
                    node_id,
                )
                return next_task_nodes
    except asyncio.CancelledError:
        if abortion_task:
            abortion_task.cancel()
        raise
