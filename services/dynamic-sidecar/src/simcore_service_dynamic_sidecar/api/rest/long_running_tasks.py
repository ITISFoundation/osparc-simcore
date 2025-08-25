from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, status

from ...services.long_running_tasks import cleanup_long_running_tasks
from ._dependencies import get_application

router = APIRouter()


@router.delete(
    "/long-running-tasks",
    summary="Removes locally started long-running-tasks",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cleanup_local_long_running_tasks(
    app: Annotated[FastAPI, Depends(get_application)],
) -> None:
    await cleanup_long_running_tasks(app)
