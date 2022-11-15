import functools
import logging
from collections import deque
from typing import Any, Awaitable, Final, Optional

from fastapi import FastAPI
from servicelib.fastapi.long_running_tasks.server import TaskProgress
from servicelib.utils import logged_gather
from simcore_sdk.node_data import data_manager
from tenacity import retry
from tenacity.retry import retry_if_result
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

from ..core.docker_compose_utils import (
    docker_compose_create,
    docker_compose_down,
    docker_compose_pull,
    docker_compose_restart,
    docker_compose_rm,
    docker_compose_start,
)
from ..core.docker_logs import start_log_fetching, stop_log_fetching
from ..core.docker_utils import get_running_containers_count_from_names
from ..core.rabbitmq import RabbitMQ, send_message
from ..core.settings import ApplicationSettings
from ..core.utils import CommandResult, assemble_container_names
from ..core.validation import parse_compose_spec, validate_compose_spec
from ..models.schemas.application_health import ApplicationHealth
from ..models.schemas.containers import ContainersCreate
from ..models.shared_store import SharedStore
from ..modules import nodeports
from ..modules.mounted_fs import MountedVolumes
from ..modules.outputs_manager import OutputsManager
from ..modules.outputs_watcher import outputs_watcher_disabled

logger = logging.getLogger(__name__)


# TASKS

# NOTE: most services have only 1 "working" directory
CONCURRENCY_STATE_SAVE_RESTORE: Final[int] = 2
_MINUTE: Final[int] = 60


@retry(
    wait=wait_random_exponential(max=30),
    stop=stop_after_delay(5 * _MINUTE),
    retry=retry_if_result(lambda result: result.success is False),
    reraise=False,
)
async def _retry_docker_compose_start(
    compose_spec: str, settings: ApplicationSettings
) -> CommandResult:
    # NOTE: sometimes the system is not capable of starting
    # the containers as soon as they are created. This might
    # happen due to the docker engine's load.
    return await docker_compose_start(compose_spec, settings)


@retry(
    wait=wait_random_exponential(max=30),
    stop=stop_after_delay(5 * _MINUTE),
    retry=retry_if_result(lambda result: result is False),
    reraise=True,
)
async def _retry_docker_compose_create(
    compose_spec: str, settings: ApplicationSettings
) -> bool:
    await docker_compose_create(compose_spec, settings)

    compose_spec_dict = parse_compose_spec(compose_spec)
    container_names = list(compose_spec_dict["services"].keys())

    expected_num_containers = len(container_names)
    actual_num_containers = await get_running_containers_count_from_names(
        container_names
    )

    return expected_num_containers == actual_num_containers


async def task_create_service_containers(
    progress: TaskProgress,
    settings: ApplicationSettings,
    containers_create: ContainersCreate,
    shared_store: SharedStore,
    mounted_volumes: MountedVolumes,
    app: FastAPI,
    application_health: ApplicationHealth,
    rabbitmq: RabbitMQ,
) -> list[str]:
    progress.update(message="validating service spec", percent=0)

    shared_store.compose_spec = await validate_compose_spec(
        settings=settings,
        compose_file_content=containers_create.docker_compose_yaml,
        mounted_volumes=mounted_volumes,
    )
    shared_store.container_names = assemble_container_names(shared_store.compose_spec)
    await shared_store.persist_to_disk()

    logger.info("Validated compose-spec:\n%s", f"{shared_store.compose_spec}")

    await send_message(rabbitmq, "starting service containers")
    assert shared_store.compose_spec  # nosec

    with outputs_watcher_disabled(app):
        # removes previous pending containers
        progress.update(message="cleanup previous used resources")
        await docker_compose_rm(shared_store.compose_spec, settings)

        progress.update(message="pulling images", percent=0.01)
        await docker_compose_pull(shared_store.compose_spec, settings)

        progress.update(message="creating and starting containers", percent=0.90)
        await _retry_docker_compose_create(shared_store.compose_spec, settings)

        progress.update(message="ensure containers are started", percent=0.95)
        r = await _retry_docker_compose_start(shared_store.compose_spec, settings)

    message = f"Finished docker-compose start with output\n{r.message}"

    if r.success:
        await send_message(rabbitmq, "service containers started")
        logger.debug(message)
        for container_name in shared_store.container_names:
            await start_log_fetching(app, container_name)
    else:
        application_health.is_healthy = False
        application_health.error_message = message
        logger.error("Marked sidecar as unhealthy, see below for details\n:%s", message)
        await send_message(rabbitmq, "could not start service containers")

    return shared_store.container_names


async def task_runs_docker_compose_down(
    progress: TaskProgress,
    app: FastAPI,
    shared_store: SharedStore,
    settings: ApplicationSettings,
) -> None:
    if shared_store.compose_spec is None:
        raise RuntimeError("No compose-spec was found")

    progress.update(message="running docker-compose-down", percent=0.1)
    result = await docker_compose_down(shared_store.compose_spec, settings)
    if not result.success:
        logger.warning(
            "docker-compose down command finished with errors\n%s",
            result.message,
        )
        raise RuntimeError(result.message)

    progress.update(message="stopping logs", percent=0.9)
    for container_name in shared_store.container_names:
        await stop_log_fetching(app, container_name)

    progress.update(message="removing pending resources", percent=0.95)
    await docker_compose_rm(shared_store.compose_spec, settings)

    # removing compose-file spec
    await shared_store.clear()
    progress.update(message="done", percent=0.99)


async def task_restore_state(
    progress: TaskProgress,
    settings: ApplicationSettings,
    mounted_volumes: MountedVolumes,
    rabbitmq: RabbitMQ,
) -> None:
    progress.update(message="checking files", percent=0.0)
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

    progress.update(message="Downloading state", percent=0.05)
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
                io_log_redirect_cb=functools.partial(send_message, rabbitmq),
            )
            for path, exists in zip(mounted_volumes.disk_state_paths(), existing_files)
            if exists
        ),
        max_concurrency=CONCURRENCY_STATE_SAVE_RESTORE,
        reraise=True,  # this should raise if there is an issue
    )

    await send_message(rabbitmq, "Finished state downloading")
    progress.update(message="state restored", percent=0.99)


async def task_save_state(
    progress: TaskProgress,
    settings: ApplicationSettings,
    mounted_volumes: MountedVolumes,
    rabbitmq: RabbitMQ,
) -> None:
    awaitables: deque[Awaitable[Optional[Any]]] = deque()

    progress.update(message="starting state save", percent=0.0)

    for state_path in mounted_volumes.disk_state_paths():
        await send_message(rabbitmq, f"Saving state for {state_path}")
        awaitables.append(
            data_manager.push(
                user_id=settings.DY_SIDECAR_USER_ID,
                project_id=str(settings.DY_SIDECAR_PROJECT_ID),
                node_uuid=str(settings.DY_SIDECAR_NODE_ID),
                file_or_folder=state_path,
                r_clone_settings=settings.rclone_settings_for_nodeports,
                archive_exclude_patterns=mounted_volumes.state_exclude,
                io_log_redirect_cb=functools.partial(send_message, rabbitmq),
            )
        )

    progress.update(message="saving state", percent=0.1)
    await logged_gather(*awaitables, max_concurrency=CONCURRENCY_STATE_SAVE_RESTORE)

    await send_message(rabbitmq, "Finished state saving")
    progress.update(message="finished state saving", percent=0.99)


async def task_ports_inputs_pull(
    progress: TaskProgress,
    port_keys: Optional[list[str]],
    mounted_volumes: MountedVolumes,
    rabbitmq: RabbitMQ,
) -> int:
    progress.update(message="starting inputs pulling", percent=0.0)
    port_keys = [] if port_keys is None else port_keys

    await send_message(rabbitmq, f"Pulling inputs for {port_keys}")
    progress.update(message="pulling inputs", percent=0.1)
    transferred_bytes = await nodeports.download_target_ports(
        nodeports.PortTypeName.INPUTS,
        mounted_volumes.disk_inputs_path,
        port_keys=port_keys,
        io_log_redirect_cb=functools.partial(send_message, rabbitmq),
    )
    await send_message(rabbitmq, "Finished pulling inputs")
    progress.update(message="finished inputs pulling", percent=0.99)
    return int(transferred_bytes)


async def task_ports_outputs_pull(
    progress: TaskProgress,
    port_keys: Optional[list[str]],
    mounted_volumes: MountedVolumes,
    rabbitmq: RabbitMQ,
) -> int:
    progress.update(message="starting outputs pulling", percent=0.0)
    port_keys = [] if port_keys is None else port_keys

    await send_message(rabbitmq, f"Pulling output for {port_keys}")
    transferred_bytes = await nodeports.download_target_ports(
        nodeports.PortTypeName.OUTPUTS,
        mounted_volumes.disk_outputs_path,
        port_keys=port_keys,
        io_log_redirect_cb=functools.partial(send_message, rabbitmq),
    )
    await send_message(rabbitmq, "Finished pulling outputs")
    progress.update(message="finished outputs pulling", percent=0.99)
    return int(transferred_bytes)


async def task_ports_outputs_push(
    progress: TaskProgress,
    port_keys: Optional[list[str]],
    outputs_manager: OutputsManager,
    rabbitmq: RabbitMQ,
) -> None:
    progress.update(message="starting outputs pushing", percent=0.0)

    port_keys = list(outputs_manager.outputs_port_keys) if not port_keys else port_keys

    await send_message(rabbitmq, f"Pushing outputs for {port_keys}")

    await outputs_manager.wait_for_all_uploads_to_finish()

    await send_message(rabbitmq, "Finished pulling outputs")
    progress.update(message="finished outputs pushing", percent=0.99)


async def task_containers_restart(
    progress: TaskProgress,
    app: FastAPI,
    settings: ApplicationSettings,
    shared_store: SharedStore,
    rabbitmq: RabbitMQ,
) -> None:
    progress.update(message="starting containers restart", percent=0.0)
    if shared_store.compose_spec is None:
        raise RuntimeError("No spec for docker-compose command was found")

    for container_name in shared_store.container_names:
        await stop_log_fetching(app, container_name)

    progress.update(message="stopped log fetching", percent=0.1)

    result = await docker_compose_restart(shared_store.compose_spec, settings)

    if not result.success:
        logger.warning(
            "docker-compose restart finished with errors\n%s", result.message
        )
        raise RuntimeError(result.message)

    progress.update(message="containers restarted", percent=0.8)

    for container_name in shared_store.container_names:
        await start_log_fetching(app, container_name)

    progress.update(message="started log fetching", percent=0.9)

    await send_message(rabbitmq, "Service was restarted please reload the UI")
    await rabbitmq.send_event_reload_iframe()
    progress.update(message="started log fetching", percent=0.99)
