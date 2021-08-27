import asyncio
import logging
from typing import Callable, Optional

import click
from servicelib.logging_utils import log_decorator

from .boot_mode import BootMode
from .config import SIDECAR_INTERVAL_TO_CHECK_TASK_ABORTED_S
from .core import run_computational_task
from .db import DBContextManager
from .rabbitmq import RabbitMQ
from .utils import cancel_task

log = logging.getLogger(__name__)


@click.command()
@click.option("--job_id", default=0, type=int, help="The job ID")
@click.option("--user_id", default=0, type=int, help="The user ID")
@click.option("--project_id", default="0", help="The project ID")
@click.option("--node_id", default=None, help="The node ID or nothing")
def main(job_id: str, user_id: str, project_id: str, node_id: str) -> None:

    try:
        asyncio.run(
            run_sidecar(
                job_id, user_id, project_id, node_id=node_id, sidecar_mode=BootMode.CPU
            )
        )
    except Exception:  # pylint: disable=broad-except
        log.exception("Unexpected problem while running sidecar")


@log_decorator(logger=log, level=logging.INFO)
async def perdiodicaly_check_if_aborted(
    is_aborted_cb: Callable[[], bool], task_name: str
) -> None:
    try:
        while await asyncio.sleep(
            SIDECAR_INTERVAL_TO_CHECK_TASK_ABORTED_S, result=True
        ):
            if is_aborted_cb():
                log.info("Task was aborted. Cancelling fct [%s]...", task_name)
                asyncio.get_event_loop().call_soon(cancel_task, task_name)
    except asyncio.CancelledError:
        pass


@log_decorator(logger=log, level=logging.INFO)
async def run_sidecar(  # pylint: disable=too-many-arguments
    job_id: str,
    user_id: str,
    project_id: str,
    node_id: str,
    sidecar_mode: BootMode,
    is_aborted_cb: Optional[Callable[[], bool]] = None,
    retry: int = 1,
    max_retries: int = 1,
) -> None:

    abortion_task: Optional[asyncio.Task] = None
    if current_task := asyncio.current_task():
        abortion_task = (
            asyncio.create_task(
                perdiodicaly_check_if_aborted(is_aborted_cb, current_task.get_name())
            )
            if is_aborted_cb
            else None
        )
    try:
        async with DBContextManager() as db_engine, RabbitMQ() as rabbit_mq:
            await run_computational_task(
                db_engine,
                rabbit_mq,
                job_id,
                user_id,
                project_id,
                node_id=node_id,
                retry=retry,
                max_retries=max_retries,
                sidecar_mode=sidecar_mode,
            )
    finally:
        if abortion_task:
            abortion_task.cancel()
