import logging

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel
from servicelib.fastapi.long_running_tasks.server import (
    TaskAlreadyRunningError,
    TaskId,
    TaskManager,
    TaskProgress,
    get_task_manager,
    start_task,
)
from servicelib.fastapi.requests_decorators import cancel_on_disconnect
from servicelib.utils import logged_gather
from simcore_sdk.node_data import data_manager

from ..core.docker_compose_utils import (
    docker_compose_down,
    docker_compose_pull,
    docker_compose_rm,
    docker_compose_up,
)
from ..core.docker_logs import start_log_fetching, stop_log_fetching
from ..core.rabbitmq import RabbitMQ
from ..core.settings import ApplicationSettings
from ..core.utils import assemble_container_names
from ..core.validation import validate_compose_spec
from ..models.schemas.application_health import ApplicationHealth
from ..models.shared_store import SharedStore
from ..modules.directory_watcher import directory_watcher_disabled
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


class ContainersCreate(BaseModel):
    docker_compose_yaml: str


async def send_message(rabbitmq: RabbitMQ, message: str) -> None:
    logger.info(message)
    await rabbitmq.post_log_message(f"[sidecar] {message}")


# TASKS


async def _task_create_service_containers(
    progress: TaskProgress,
    settings: ApplicationSettings,
    containers_create: ContainersCreate,
    shared_store: SharedStore,
    mounted_volumes: MountedVolumes,
    app: FastAPI,
    application_health: ApplicationHealth,
    rabbitmq: RabbitMQ,
    long_running_compose_timeout: int,
    validation_timeout: int,
) -> list[str]:
    progress.publish(message="validating service spec", percent=0)

    shared_store.compose_spec = await validate_compose_spec(
        settings=settings,
        compose_file_content=containers_create.docker_compose_yaml,
        mounted_volumes=mounted_volumes,
        docker_compose_config_timeout=validation_timeout,
    )
    shared_store.container_names = assemble_container_names(shared_store.compose_spec)

    logger.debug("Validated compose-spec:\n%s", f"{shared_store.compose_spec}")

    await send_message(rabbitmq, "starting service containers")
    assert shared_store.compose_spec  # nosec

    with directory_watcher_disabled(app):
        # removes previous pending containers
        progress.publish(message="cleanup previous used resources")
        await docker_compose_rm(shared_store.compose_spec, settings)

        progress.publish(message="pulling images", percent=0.01)
        await docker_compose_pull(
            shared_store.compose_spec, settings, timeout=long_running_compose_timeout
        )

        progress.publish(message="starting service containers", percent=0.90)
        r = await docker_compose_up(
            shared_store.compose_spec, settings, timeout=long_running_compose_timeout
        )

    message = f"Finished docker-compose up with output\n{r.message}"

    if r.success:
        await send_message(rabbitmq, "service containers started")
        logger.info(message)
        for container_name in shared_store.container_names:
            await start_log_fetching(app, container_name)
    else:
        application_health.is_healthy = False
        application_health.error_message = message
        logger.error("Marked sidecar as unhealthy, see below for details\n:%s", message)
        await send_message(rabbitmq, "could not start service containers")

    progress.publish(message="done", percent=1)

    return shared_store.container_names


async def _task_runs_docker_compose_down(
    progress: TaskProgress,
    app: FastAPI,
    shared_store: SharedStore,
    settings: ApplicationSettings,
    command_timeout: int,
) -> None:
    if shared_store.compose_spec is None:
        raise RuntimeError("No compose-spec was found")

    progress.publish(message="running docker-compose-down", percent=0)
    result = await docker_compose_down(
        shared_store.compose_spec,
        settings,
        timeout=min(command_timeout, settings.DYNAMIC_SIDECAR_STOP_AND_REMOVE_TIMEOUT),
    )
    if not result.success:
        logger.warning(
            "docker-compose down command finished with errors\n%s",
            result.message,
        )
        raise RuntimeError(result.message)

    progress.publish(message="stopping logs", percent=0.9)
    for container_name in shared_store.container_names:
        await stop_log_fetching(app, container_name)

    progress.publish(message="removing pending resources", percent=0.95)
    await docker_compose_rm(shared_store.compose_spec, settings)

    # removing compose-file spec
    shared_store.clear()
    progress.publish(message="done", percent=1)


async def _task_restore_state(
    progress: TaskProgress,
    settings: ApplicationSettings,
    mounted_volumes: MountedVolumes,
    rabbitmq: RabbitMQ,
) -> None:
    progress.publish(message="checking files", percent=0.0)
    # first check if there are files (no max concurrency here, these are just quick REST calls)
    existing_files: list[bool] = await logged_gather(
        *(
            data_manager.exists(
                user_id=settings.DY_SIDECAR_USER_ID,
                project_id=f"{settings.DY_SIDECAR_PROJECT_ID}",
                node_uuid=f"{settings.DY_SIDECAR_NODE_ID}",
                file_path=path,
            )
            for path in mounted_volumes.disk_state_paths()
        ),
        reraise=True,
    )

    progress.publish(message="Downloading state", percent=0.05)
    await send_message(
        rabbitmq,
        f"Downloading state files for {existing_files}...",
    )
    await logged_gather(
        *(
            data_manager.pull(
                user_id=settings.DY_SIDECAR_USER_ID,
                project_id=str(settings.DY_SIDECAR_PROJECT_ID),
                node_uuid=str(settings.DY_SIDECAR_NODE_ID),
                file_or_folder=path,
            )
            for path, exists in zip(mounted_volumes.disk_state_paths(), existing_files)
            if exists
        ),
        max_concurrency=2,  # limit amount of downloads
        reraise=True,  # this should raise if there is an issue
    )

    await send_message(rabbitmq, "Finished state downloading")
    progress.publish(message="state restored", percent=1)


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
            handler=_task_create_service_containers,
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
            handler=_task_runs_docker_compose_down,
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
async def restore_state(
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
            handler=_task_restore_state,
            unique=True,
            settings=settings,
            mounted_volumes=mounted_volumes,
            rabbitmq=rabbitmq,
        )
        return task_id
    except TaskAlreadyRunningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{e}") from e
