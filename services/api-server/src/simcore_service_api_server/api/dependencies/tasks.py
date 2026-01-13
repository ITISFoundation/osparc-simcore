from typing import Annotated

from fastapi import Depends
from servicelib.celery.task_manager import TaskManager

from ...services_rpc.async_jobs import AsyncJobClient
from .celery import get_task_manager


def get_async_jobs_client(
    task_manager: Annotated[TaskManager, Depends(get_task_manager)],
) -> AsyncJobClient:
    return AsyncJobClient(_task_manager=task_manager)
