import logging
from typing import Annotated, Final

from fastapi import APIRouter, Depends, HTTPException, status
from models_library.projects_nodes import NodeID
from pydantic import BaseModel, PositiveInt
from servicelib.fastapi.long_running_tasks.client import (
    ProgressMessage,
    ProgressPercent,
)
from servicelib.fastapi.long_running_tasks.server import (
    TaskAlreadyRunningError,
    TaskId,
    TaskProgress,
    TasksManager,
    get_tasks_manager,
    start_task,
)
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_result
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

from ...modules.dynamic_sidecar.scheduler import DynamicSidecarsScheduler
from ...utils.routes import NoContentResponse
from ..dependencies.dynamic_sidecar import get_dynamic_sidecar_scheduler

_logger = logging.getLogger(__name__)

_MINUTE: Final[PositiveInt] = 60


class ObservationItem(BaseModel):
    is_disabled: bool


router = APIRouter()


@retry(
    wait=wait_random_exponential(max=10),
    stop=stop_after_delay(1 * _MINUTE),
    retry=retry_if_result(lambda result: result is False),
    reraise=False,
    before_sleep=before_sleep_log(_logger, logging.WARNING, exc_info=True),
)
def _retry_toggle_observation(
    dynamic_sidecars_scheduler: DynamicSidecarsScheduler,
    node_uuid: NodeID,
    *,
    is_disabled: bool,
) -> bool:
    return dynamic_sidecars_scheduler.toggle_observation(node_uuid, is_disabled)


@router.patch(
    "/services/{node_uuid}/observation",
    summary="Enable/disable observation of the service",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_service_observation(
    node_uuid: NodeID,
    observation_item: ObservationItem,
    dynamic_sidecars_scheduler: Annotated[
        DynamicSidecarsScheduler, Depends(get_dynamic_sidecar_scheduler)
    ],
) -> NoContentResponse:
    if _retry_toggle_observation(
        dynamic_sidecars_scheduler=dynamic_sidecars_scheduler,
        node_uuid=node_uuid,
        is_disabled=observation_item.is_disabled,
    ):
        return NoContentResponse()

    raise HTTPException(
        status.HTTP_423_LOCKED,
        detail=f"Could not toggle service {node_uuid} observation to disabled={observation_item.is_disabled}",
    )


@router.delete(
    "/services/{node_uuid}/containers",
    summary="Removes the service's user services",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Task already running, cannot start a new one"
        }
    },
)
async def delete_service_containers(
    node_uuid: NodeID,
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
    dynamic_sidecars_scheduler: Annotated[
        DynamicSidecarsScheduler, Depends(get_dynamic_sidecar_scheduler)
    ],
):
    async def _task_remove_service_containers(
        task_progress: TaskProgress, node_uuid: NodeID
    ) -> None:
        async def _progress_callback(
            message: ProgressMessage, percent: ProgressPercent, _: TaskId
        ) -> None:
            task_progress.update(message=message, percent=percent)

        await dynamic_sidecars_scheduler.remove_service_containers(
            node_uuid=node_uuid, progress_callback=_progress_callback
        )

    try:
        return start_task(
            tasks_manager,
            task=_task_remove_service_containers,
            unique=True,
            node_uuid=node_uuid,
        )
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e


@router.post(
    "/services/{node_uuid}/state:save",
    summary="Starts the saving of the state for the service",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Task already running, cannot start a new one"
        }
    },
)
async def save_service_state(
    node_uuid: NodeID,
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
    dynamic_sidecars_scheduler: Annotated[
        DynamicSidecarsScheduler, Depends(get_dynamic_sidecar_scheduler)
    ],
):
    async def _task_save_service_state(
        task_progress: TaskProgress,
        node_uuid: NodeID,
    ) -> None:
        async def _progress_callback(
            message: ProgressMessage, percent: ProgressPercent, _: TaskId
        ) -> None:
            task_progress.update(message=message, percent=percent)

        await dynamic_sidecars_scheduler.save_service_state(
            node_uuid=node_uuid, progress_callback=_progress_callback
        )

    try:
        return start_task(
            tasks_manager,
            task=_task_save_service_state,
            unique=True,
            node_uuid=node_uuid,
        )
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e


@router.post(
    "/services/{node_uuid}/outputs:push",
    summary="Starts the pushing of the outputs for the service",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Task already running, cannot start a new one"
        }
    },
)
async def push_service_outputs(
    node_uuid: NodeID,
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
    dynamic_sidecars_scheduler: Annotated[
        DynamicSidecarsScheduler, Depends(get_dynamic_sidecar_scheduler)
    ],
):
    async def _task_push_service_outputs(
        task_progress: TaskProgress, node_uuid: NodeID
    ) -> None:
        async def _progress_callback(
            message: ProgressMessage, percent: ProgressPercent, _: TaskId
        ) -> None:
            task_progress.update(message=message, percent=percent)

        await dynamic_sidecars_scheduler.push_service_outputs(
            node_uuid=node_uuid, progress_callback=_progress_callback
        )

    try:
        return start_task(
            tasks_manager,
            task=_task_push_service_outputs,
            unique=True,
            node_uuid=node_uuid,
        )
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e


@router.delete(
    "/services/{node_uuid}/docker-resources",
    summary="Removes the service's sidecar, proxy and docker networks & volumes",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Task already running, cannot start a new one"
        }
    },
)
async def delete_service_docker_resources(
    node_uuid: NodeID,
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
    dynamic_sidecars_scheduler: Annotated[
        DynamicSidecarsScheduler, Depends(get_dynamic_sidecar_scheduler)
    ],
):
    async def _task_cleanup_service_docker_resources(
        task_progress: TaskProgress, node_uuid: NodeID
    ) -> None:
        await dynamic_sidecars_scheduler.remove_service_sidecar_proxy_docker_networks_and_volumes(
            task_progress=task_progress, node_uuid=node_uuid
        )

    try:
        return start_task(
            tasks_manager,
            task=_task_cleanup_service_docker_resources,
            unique=True,
            node_uuid=node_uuid,
        )
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e
