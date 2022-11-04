from fastapi import APIRouter, Depends, HTTPException, status

from ..modules.task_monitor import TaskMonitor
from ._dependencies import get_task_monitor

router = APIRouter()


@router.get("/health")
def health(task_monitor: TaskMonitor = Depends(get_task_monitor)) -> None:
    if not task_monitor.was_started or task_monitor.are_tasks_hanging:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="unhealthy")
