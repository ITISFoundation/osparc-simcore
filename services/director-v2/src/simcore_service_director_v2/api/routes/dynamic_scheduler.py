from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from models_library.projects_nodes import NodeID
from pydantic import BaseModel
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

from ...core.settings import DynamicSidecarSettings
from ...modules.dynamic_sidecar.api_client import DynamicSidecarClient
from ...modules.dynamic_sidecar.scheduler import (
    DynamicSidecarsScheduler,
    push_outputs,
    remove_containers,
    remove_sidecar_proxy_docker_networks_and_volumes,
    save_state,
)
from ...utils.routes import NoContentResponse
from ..dependencies import get_app
from ..dependencies.dynamic_sidecar import (
    get_dynamic_sidecar_client,
    get_dynamic_sidecar_scheduler,
    get_dynamic_sidecar_settings,
)


class ObservationItem(BaseModel):
    is_disabled: bool


router = APIRouter()


@router.patch(
    "/services/{node_uuid}/observation",
    summary="Enable/disable observation of the service",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_service_observation(
    node_uuid: NodeID,
    observation_item: ObservationItem,
    dynamic_sidecars_scheduler: DynamicSidecarsScheduler = Depends(
        get_dynamic_sidecar_scheduler
    ),
) -> NoContentResponse:
    if dynamic_sidecars_scheduler.toggle_observation_cycle(
        node_uuid, observation_item.is_disabled
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
    tasks_manager: TasksManager = Depends(get_tasks_manager),
    dynamic_sidecar_client: DynamicSidecarClient = Depends(get_dynamic_sidecar_client),
    app: FastAPI = Depends(get_app),
):
    async def _task_remove_service_containers(
        task_progress: TaskProgress,
        app: FastAPI,
        node_uuid: NodeID,
        dynamic_sidecar_client: DynamicSidecarClient,
    ) -> None:
        async def _progress_callback(
            message: ProgressMessage, percent: ProgressPercent, _: TaskId
        ) -> None:
            task_progress.update(message=message, percent=percent)

        await remove_containers(
            app, node_uuid, dynamic_sidecar_client, _progress_callback
        )

    try:
        task_id = start_task(
            tasks_manager,
            task=_task_remove_service_containers,
            unique=True,
            app=app,
            node_uuid=node_uuid,
            dynamic_sidecar_client=dynamic_sidecar_client,
        )
        return task_id
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
    tasks_manager: TasksManager = Depends(get_tasks_manager),
    dynamic_sidecar_client: DynamicSidecarClient = Depends(get_dynamic_sidecar_client),
    app: FastAPI = Depends(get_app),
):
    async def _task_save_service_state(
        task_progress: TaskProgress,
        app: FastAPI,
        node_uuid: NodeID,
        dynamic_sidecar_client: DynamicSidecarClient,
    ) -> None:
        async def _progress_callback(
            message: ProgressMessage, percent: ProgressPercent, _: TaskId
        ) -> None:
            task_progress.update(message=message, percent=percent)

        await save_state(app, node_uuid, dynamic_sidecar_client, _progress_callback)

    try:
        task_id = start_task(
            tasks_manager,
            task=_task_save_service_state,
            unique=True,
            app=app,
            node_uuid=node_uuid,
            dynamic_sidecar_client=dynamic_sidecar_client,
        )
        return task_id
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
    tasks_manager: TasksManager = Depends(get_tasks_manager),
    dynamic_sidecar_client: DynamicSidecarClient = Depends(get_dynamic_sidecar_client),
    app: FastAPI = Depends(get_app),
):
    async def _task_push_service_outputs(
        task_progress: TaskProgress,
        app: FastAPI,
        node_uuid: NodeID,
        dynamic_sidecar_client: DynamicSidecarClient,
    ) -> None:
        async def _progress_callback(
            message: ProgressMessage, percent: ProgressPercent, _: TaskId
        ) -> None:
            task_progress.update(message=message, percent=percent)

        await push_outputs(app, node_uuid, dynamic_sidecar_client, _progress_callback)

    try:
        task_id = start_task(
            tasks_manager,
            task=_task_push_service_outputs,
            unique=True,
            app=app,
            node_uuid=node_uuid,
            dynamic_sidecar_client=dynamic_sidecar_client,
        )
        return task_id
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
    tasks_manager: TasksManager = Depends(get_tasks_manager),
    app: FastAPI = Depends(get_app),
    dynamic_sidecar_settings: DynamicSidecarSettings = Depends(
        get_dynamic_sidecar_settings
    ),
):
    async def _task_cleanup_service_docker_resources(
        task_progress: TaskProgress,
        app: FastAPI,
        node_uuid: NodeID,
        dynamic_sidecar_settings: DynamicSidecarSettings,
    ) -> None:
        await remove_sidecar_proxy_docker_networks_and_volumes(
            task_progress, app, node_uuid, dynamic_sidecar_settings
        )

    try:
        task_id = start_task(
            tasks_manager,
            task=_task_cleanup_service_docker_resources,
            unique=True,
            app=app,
            node_uuid=node_uuid,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
        )
        return task_id
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e
