import logging
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from servicelib.fastapi.long_running_tasks.server import (
    TaskAlreadyRunningError,
    TaskId,
    TaskManager,
    get_task_manager,
    start_task,
)
from servicelib.fastapi.requests_decorators import cancel_on_disconnect

from ..core.rabbitmq import RabbitMQ
from ..core.settings import ApplicationSettings
from ..models.schemas.application_health import ApplicationHealth
from ..models.shared_store import SharedStore
from ..modules.long_running_tasks import (
    ContainersCreate,
    task_create_service_containers,
    task_ports_inputs_pull,
    task_restore_state,
    task_runs_docker_compose_down,
    task_save_state,
    task_ports_outputs_pull,
    task_ports_outputs_push,
)
from ..modules.mounted_fs import MountedVolumes
from ._dependencies import (
    get_application,
    get_application_health,
    get_mounted_volumes,
    get_rabbitmq,
    get_settings,
    get_shared_store,
)

logger = logging.getLogger(__name__)

containers_router_tasks = APIRouter(tags=["containers"])


# HANDLERS


@containers_router_tasks.post(
    "/containers/tasks",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Cannot validate submitted compose spec"
        },
        status.HTTP_409_CONFLICT: {
            "description": "Could not start a task while another is running"
        },
    },
)
@cancel_on_disconnect
async def create_service_containers_task(  # pylint: disable=too-many-arguments
    request: Request,
    containers_create: ContainersCreate,
    task_manager: TaskManager = Depends(get_task_manager),
    long_running_compose_timeout: int = Query(
        3600, description="docker-compose `up` and `pull` timeout to avoid hanging"
    ),
    validation_timeout: int = Query(
        60, description="docker-compose config timeout (EXPERIMENTAL)"
    ),
    settings: ApplicationSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
    app: FastAPI = Depends(get_application),
    application_health: ApplicationHealth = Depends(get_application_health),
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> TaskId:
    """
    Starts a background task responsible for:
    - cleaning up resources from previous runs
    - pulling the images
    - starting the containers

    NOTE: only one instance of this task can run at a time
    """
    assert request  # nosec

    try:
        task_id = start_task(
            task_manager=task_manager,
            handler=task_create_service_containers,
            unique=True,
            settings=settings,
            containers_create=containers_create,
            shared_store=shared_store,
            mounted_volumes=mounted_volumes,
            app=app,
            application_health=application_health,
            rabbitmq=rabbitmq,
            long_running_compose_timeout=long_running_compose_timeout,
            validation_timeout=validation_timeout,
        )
        return task_id
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e


@containers_router_tasks.post(
    "/containers/tasks:down",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Could not start a task while another is running"
        },
    },
)
@cancel_on_disconnect
async def runs_docker_compose_down_task(
    request: Request,
    command_timeout: int = Query(
        10, description="docker-compose down command timeout default  (EXPERIMENTAL)"
    ),
    task_manager: TaskManager = Depends(get_task_manager),
    settings: ApplicationSettings = Depends(get_settings),
    shared_store: SharedStore = Depends(get_shared_store),
    app: FastAPI = Depends(get_application),
) -> TaskId:
    """Removes the previously started service
    and returns the docker-compose output"""
    assert request  # nosec

    try:
        task_id = start_task(
            task_manager=task_manager,
            handler=task_runs_docker_compose_down,
            unique=True,
            app=app,
            shared_store=shared_store,
            settings=settings,
            command_timeout=command_timeout,
        )
        return task_id
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e


@containers_router_tasks.post(
    "/containers/tasks/state:restore",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Could not start a task while another is running"
        },
    },
)
@cancel_on_disconnect
async def state_restore_task(
    request: Request,
    task_manager: TaskManager = Depends(get_task_manager),
    settings: ApplicationSettings = Depends(get_settings),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
) -> TaskId:
    """
    Restores the state of the dynamic service

    When restoring the state:
    - pull inputs via nodeports
    - pull all the extra state paths
    """
    assert request  # nosec

    try:
        task_id = start_task(
            task_manager=task_manager,
            handler=task_restore_state,
            unique=True,
            settings=settings,
            mounted_volumes=mounted_volumes,
            rabbitmq=rabbitmq,
        )
        return task_id
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e


@containers_router_tasks.post(
    "/containers/tasks/state:save",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Could not start a task while another is running"
        },
    },
)
@cancel_on_disconnect
async def state_save_task(
    request: Request,
    task_manager: TaskManager = Depends(get_task_manager),
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
    settings: ApplicationSettings = Depends(get_settings),
) -> TaskId:
    """Stores the state of the dynamic service"""
    assert request  # nosec

    try:
        task_id = start_task(
            task_manager=task_manager,
            handler=task_save_state,
            unique=True,
            settings=settings,
            mounted_volumes=mounted_volumes,
            rabbitmq=rabbitmq,
        )
        return task_id
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e


@containers_router_tasks.post(
    "/containers/tasks/ports/inputs:pull",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Could not start a task while another is running"
        },
    },
)
@cancel_on_disconnect
async def ports_inputs_pull_task(
    request: Request,
    port_keys: Optional[list[str]] = None,
    task_manager: TaskManager = Depends(get_task_manager),
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> TaskId:
    """Pull input ports data"""
    assert request  # nosec

    try:
        task_id = start_task(
            task_manager=task_manager,
            handler=task_ports_inputs_pull,
            unique=True,
            port_keys=port_keys,
            mounted_volumes=mounted_volumes,
            rabbitmq=rabbitmq,
        )
        return task_id
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e


@containers_router_tasks.post(
    "/containers/tasks/ports/outputs:pull",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Could not start a task while another is running"
        },
    },
)
@cancel_on_disconnect
async def ports_outputs_pull_task(
    request: Request,
    port_keys: Optional[list[str]] = None,
    task_manager: TaskManager = Depends(get_task_manager),
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> TaskId:
    """Pull output ports data"""
    assert request  # nosec

    try:
        task_id = start_task(
            task_manager=task_manager,
            handler=task_ports_outputs_pull,
            unique=True,
            port_keys=port_keys,
            mounted_volumes=mounted_volumes,
            rabbitmq=rabbitmq,
        )
        return task_id
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e


@containers_router_tasks.post(
    "/containers/tasks/ports/outputs:push",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Could not start a task while another is running"
        },
    },
)
@cancel_on_disconnect
async def ports_outputs_push_task(
    request: Request,
    port_keys: Optional[list[str]] = None,
    task_manager: TaskManager = Depends(get_task_manager),
    rabbitmq: RabbitMQ = Depends(get_rabbitmq),
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> TaskId:
    """Push output ports data"""
    assert request  # nosec
    try:
        task_id = start_task(
            task_manager=task_manager,
            handler=task_ports_outputs_push,
            unique=True,
            port_keys=port_keys,
            mounted_volumes=mounted_volumes,
            rabbitmq=rabbitmq,
        )
        return task_id
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e
