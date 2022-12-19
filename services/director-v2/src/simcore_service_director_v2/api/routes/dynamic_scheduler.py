from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from models_library.projects_nodes import NodeID
from pydantic import AnyHttpUrl, BaseModel
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
from ...models.schemas.dynamic_services import SchedulerData
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
    if dynamic_sidecars_scheduler.toggle_observation(
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
    dynamic_sidecars_scheduler: DynamicSidecarsScheduler = Depends(
        get_dynamic_sidecar_scheduler
    ),
):
    scheduler_data = dynamic_sidecars_scheduler.get_scheduler_data(node_uuid)

    async def _task_remove_service_containers(
        task_progress: TaskProgress,
        dynamic_sidecar_client: DynamicSidecarClient,
        scheduler_data: SchedulerData,
    ) -> None:
        async def _progress_callback(
            message: ProgressMessage, percent: ProgressPercent, _: TaskId
        ) -> None:
            task_progress.update(message=message, percent=percent)

        await remove_containers(
            dynamic_sidecar_client, scheduler_data, _progress_callback
        )

    try:
        task_id = start_task(
            tasks_manager,
            task=_task_remove_service_containers,
            unique=True,
            dynamic_sidecar_client=dynamic_sidecar_client,
            scheduler_data=scheduler_data,
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
    dynamic_sidecars_scheduler: DynamicSidecarsScheduler = Depends(
        get_dynamic_sidecar_scheduler
    ),
):
    scheduler_data = dynamic_sidecars_scheduler.get_scheduler_data(node_uuid)

    async def _task_save_service_state(
        task_progress: TaskProgress,
        dynamic_sidecar_client: DynamicSidecarClient,
        dynamic_sidecar_endpoint: AnyHttpUrl,
    ) -> None:
        async def _progress_callback(
            message: ProgressMessage, percent: ProgressPercent, _: TaskId
        ) -> None:
            task_progress.update(message=message, percent=percent)

        await save_state(
            dynamic_sidecar_client, dynamic_sidecar_endpoint, _progress_callback
        )

    try:
        task_id = start_task(
            tasks_manager,
            task=_task_save_service_state,
            unique=True,
            dynamic_sidecar_client=dynamic_sidecar_client,
            dynamic_sidecar_endpoint=scheduler_data.endpoint,
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
    dynamic_sidecars_scheduler: DynamicSidecarsScheduler = Depends(
        get_dynamic_sidecar_scheduler
    ),
):
    scheduler_data = dynamic_sidecars_scheduler.get_scheduler_data(node_uuid)

    async def _task_push_service_outputs(
        task_progress: TaskProgress,
        dynamic_sidecar_client: DynamicSidecarClient,
        dynamic_sidecar_endpoint: AnyHttpUrl,
    ) -> None:
        async def _progress_callback(
            message: ProgressMessage, percent: ProgressPercent, _: TaskId
        ) -> None:
            task_progress.update(message=message, percent=percent)

        await push_outputs(
            dynamic_sidecar_client, dynamic_sidecar_endpoint, _progress_callback
        )

    try:
        task_id = start_task(
            tasks_manager,
            task=_task_push_service_outputs,
            unique=True,
            dynamic_sidecar_client=dynamic_sidecar_client,
            dynamic_sidecar_endpoint=scheduler_data.endpoint,
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
    dynamic_sidecars_scheduler: DynamicSidecarsScheduler = Depends(
        get_dynamic_sidecar_scheduler
    ),
):
    scheduler_data = dynamic_sidecars_scheduler.get_scheduler_data(node_uuid)

    async def _task_cleanup_service_docker_resources(
        task_progress: TaskProgress,
        app: FastAPI,
        scheduler_data: SchedulerData,
        dynamic_sidecar_settings: DynamicSidecarSettings,
    ) -> None:
        scheduler_data.dynamic_sidecar.were_state_and_outputs_saved = True
        await remove_sidecar_proxy_docker_networks_and_volumes(
            task_progress, app, scheduler_data, dynamic_sidecar_settings
        )

    try:
        task_id = start_task(
            tasks_manager,
            task=_task_cleanup_service_docker_resources,
            unique=True,
            app=app,
            scheduler_data=scheduler_data,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
        )
        return task_id
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e
