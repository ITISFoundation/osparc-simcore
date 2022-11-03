from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ..modules.task_monitor import TaskMonitor
from ._dependencies import get_task_monitor

router = APIRouter()


@router.get("/health")
def health(task_monitor: TaskMonitor = Depends(get_task_monitor)) -> dict[str, Any]:
    # TODO: application health should b
    # e pulled from some metrics like the number of fails
    # from the monitoring system, if more thank X tasks fail in the last X, it needs to be marked as unhealthy

    if not task_monitor.is_running:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="unhealthy")

    return dict(task_monitor=task_monitor.is_running)
