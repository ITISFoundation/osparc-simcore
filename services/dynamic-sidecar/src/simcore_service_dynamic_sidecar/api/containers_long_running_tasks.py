from textwrap import dedent
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request, status
from servicelib.fastapi.long_running_tasks.server import (
    TaskAlreadyRunningError,
    TaskId,
    TasksManager,
    get_tasks_manager,
    start_task,
)
from servicelib.fastapi.requests_decorators import cancel_on_disconnect

from ..core.settings import ApplicationSettings
from ..models.schemas.application_health import ApplicationHealth
from ..models.schemas.containers import ContainersCreate
from ..models.shared_store import SharedStore
from ..modules.long_running_tasks import (
    task_containers_restart,
    task_create_service_containers,
    task_ports_inputs_pull,
    task_ports_outputs_pull,
    task_ports_outputs_push,
    task_restore_state,
    task_runs_docker_compose_down,
    task_save_state,
)
from ..modules.mounted_fs import MountedVolumes
from ..modules.outputs import OutputsManager
from ._dependencies import (
    get_application,
    get_application_health,
    get_mounted_volumes,
    get_outputs_manager,
    get_settings,
    get_shared_store,
)

router = APIRouter()


@router.post(
    "/containers",
    summary=dedent(
        """
        Starts the containers as defined in ContainerCreate by:
        - cleaning up resources from previous runs if any
        - pulling the needed images
        - starting the containers

        Progress may be obtained through URL
        Process may be cancelled through URL
        """
    ).strip(),
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def create_service_containers_task(  # pylint: disable=too-many-arguments
    request: Request,
    containers_create: ContainersCreate,
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
    shared_store: Annotated[SharedStore, Depends(get_shared_store)],
    app: Annotated[FastAPI, Depends(get_application)],
    application_health: Annotated[ApplicationHealth, Depends(get_application_health)],
    mounted_volumes: Annotated[MountedVolumes, Depends(get_mounted_volumes)],
) -> TaskId:
    assert request  # nosec

    try:
        return start_task(
            tasks_manager,
            task=task_create_service_containers,
            unique=True,
            settings=settings,
            containers_create=containers_create,
            shared_store=shared_store,
            mounted_volumes=mounted_volumes,
            app=app,
            application_health=application_health,
        )
    except TaskAlreadyRunningError as e:
        return e.managed_task.task_id  # pylint: disable=no-member


@router.post(
    "/containers:down",
    summary="Remove the previously started containers",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def runs_docker_compose_down_task(
    request: Request,
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
    shared_store: Annotated[SharedStore, Depends(get_shared_store)],
    app: Annotated[FastAPI, Depends(get_application)],
) -> TaskId:
    assert request  # nosec

    try:
        return start_task(
            tasks_manager,
            task=task_runs_docker_compose_down,
            unique=True,
            app=app,
            shared_store=shared_store,
            settings=settings,
        )
    except TaskAlreadyRunningError as e:
        return e.managed_task.task_id  # pylint: disable=no-member


@router.post(
    "/containers/state:restore",
    summary="Restores the state of the dynamic service",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def state_restore_task(
    request: Request,
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
    mounted_volumes: Annotated[MountedVolumes, Depends(get_mounted_volumes)],
    app: Annotated[FastAPI, Depends(get_application)],
) -> TaskId:
    assert request  # nosec

    try:
        return start_task(
            tasks_manager,
            task=task_restore_state,
            unique=True,
            settings=settings,
            mounted_volumes=mounted_volumes,
            app=app,
        )
    except TaskAlreadyRunningError as e:
        return e.managed_task.task_id  # pylint: disable=no-member


@router.post(
    "/containers/state:save",
    summary="Stores the state of the dynamic service",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def state_save_task(
    request: Request,
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
    app: Annotated[FastAPI, Depends(get_application)],
    mounted_volumes: Annotated[MountedVolumes, Depends(get_mounted_volumes)],
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
) -> TaskId:
    assert request  # nosec

    try:
        return start_task(
            tasks_manager,
            task=task_save_state,
            unique=True,
            settings=settings,
            mounted_volumes=mounted_volumes,
            app=app,
        )
    except TaskAlreadyRunningError as e:
        return e.managed_task.task_id  # pylint: disable=no-member


@router.post(
    "/containers/ports/inputs:pull",
    summary="Pull input ports data",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def ports_inputs_pull_task(
    request: Request,
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
    app: Annotated[FastAPI, Depends(get_application)],
    mounted_volumes: Annotated[MountedVolumes, Depends(get_mounted_volumes)],
    port_keys: list[str] | None = None,
) -> TaskId:
    assert request  # nosec

    # TODO: also disable pulling

    try:
        return start_task(
            tasks_manager,
            task=task_ports_inputs_pull,
            unique=True,
            port_keys=port_keys,
            mounted_volumes=mounted_volumes,
            app=app,
        )
    except TaskAlreadyRunningError as e:
        return e.managed_task.task_id  # pylint: disable=no-member


@router.post(
    "/containers/ports/outputs:pull",
    summary="Pull output ports data",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def ports_outputs_pull_task(
    request: Request,
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
    app: Annotated[FastAPI, Depends(get_application)],
    mounted_volumes: Annotated[MountedVolumes, Depends(get_mounted_volumes)],
    port_keys: list[str] | None = None,
) -> TaskId:
    assert request  # nosec

    try:
        return start_task(
            tasks_manager,
            task=task_ports_outputs_pull,
            unique=True,
            port_keys=port_keys,
            mounted_volumes=mounted_volumes,
            app=app,
        )
    except TaskAlreadyRunningError as e:
        return e.managed_task.task_id  # pylint: disable=no-member


@router.post(
    "/containers/ports/outputs:push",
    summary="Push output ports data",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def ports_outputs_push_task(
    request: Request,
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
    outputs_manager: Annotated[OutputsManager, Depends(get_outputs_manager)],
    app: Annotated[FastAPI, Depends(get_application)],
) -> TaskId:
    assert request  # nosec

    try:
        return start_task(
            tasks_manager,
            task=task_ports_outputs_push,
            unique=True,
            outputs_manager=outputs_manager,
            app=app,
        )
    except TaskAlreadyRunningError as e:
        return e.managed_task.task_id  # pylint: disable=no-member


@router.post(
    "/containers:restart",
    summary="Restarts previously started containers",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def containers_restart_task(
    request: Request,
    tasks_manager: Annotated[TasksManager, Depends(get_tasks_manager)],
    app: Annotated[FastAPI, Depends(get_application)],
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
    shared_store: Annotated[SharedStore, Depends(get_shared_store)],
) -> TaskId:
    assert request  # nosec

    try:
        return start_task(
            tasks_manager,
            task=task_containers_restart,
            unique=True,
            app=app,
            settings=settings,
            shared_store=shared_store,
        )
    except TaskAlreadyRunningError as e:
        return e.managed_task.task_id  # pylint: disable=no-member
