import logging
from collections import deque
from typing import Any, Awaitable, Final, Optional

from fastapi import FastAPI
from servicelib.fastapi.long_running_tasks.server import TaskProgress
from servicelib.utils import logged_gather
from simcore_sdk.node_data import data_manager

from ..core.docker_compose_utils import (
    docker_compose_down,
    docker_compose_pull,
    docker_compose_restart,
    docker_compose_rm,
    docker_compose_up,
)
from ..core.docker_logs import start_log_fetching, stop_log_fetching
from ..core.rabbitmq import RabbitMQ
from ..core.settings import ApplicationSettings
from ..core.utils import assemble_container_names
from ..core.validation import validate_compose_spec
from ..models.schemas.application_health import ApplicationHealth
from ..models.schemas.containers import ContainersCreate
from ..models.shared_store import SharedStore
from ..modules import nodeports
from ..modules.directory_watcher import directory_watcher_disabled
from ..modules.mounted_fs import MountedVolumes

logger = logging.getLogger(__name__)


async def send_message(rabbitmq: RabbitMQ, message: str) -> None:
    logger.info(message)
    await rabbitmq.post_log_message(f"[sidecar] {message}")


# TASKS

# NOTE: most services have only 1 "working" directory
CONCURRENCY_STATE_SAVE_RESTORE: Final[int] = 2


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
    progress.publish(message="validating service spec", percent=0)

    shared_store.compose_spec = await validate_compose_spec(
        settings=settings,
        compose_file_content=containers_create.docker_compose_yaml,
        mounted_volumes=mounted_volumes,
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
        await docker_compose_pull(shared_store.compose_spec, settings)

        progress.publish(message="starting service containers", percent=0.90)
        r = await docker_compose_up(shared_store.compose_spec, settings)

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


async def task_runs_docker_compose_down(
    progress: TaskProgress,
    app: FastAPI,
    shared_store: SharedStore,
    settings: ApplicationSettings,
) -> None:
    if shared_store.compose_spec is None:
        raise RuntimeError("No compose-spec was found")

    progress.publish(message="running docker-compose-down", percent=0)
    result = await docker_compose_down(shared_store.compose_spec, settings)
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


async def task_restore_state(
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
        max_concurrency=CONCURRENCY_STATE_SAVE_RESTORE,
        reraise=True,  # this should raise if there is an issue
    )

    await send_message(rabbitmq, "Finished state downloading")
    progress.publish(message="state restored", percent=1)


async def task_save_state(
    progress: TaskProgress,
    settings: ApplicationSettings,
    mounted_volumes: MountedVolumes,
    rabbitmq: RabbitMQ,
) -> None:
    awaitables: deque[Awaitable[Optional[Any]]] = deque()

    progress.publish(message="starting state save", percent=0.0)

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
            )
        )

    progress.publish(message="state save scheduled", percent=0.1)
    await logged_gather(*awaitables, max_concurrency=CONCURRENCY_STATE_SAVE_RESTORE)

    await send_message(rabbitmq, "Finished state saving")
    progress.publish(message="finished state save", percent=0.1)


async def task_ports_inputs_pull(
    progress: TaskProgress,
    port_keys: Optional[list[str]],
    mounted_volumes: MountedVolumes,
    rabbitmq: RabbitMQ,
) -> int:
    progress.publish(message="starting inputs pulling", percent=0.0)
    port_keys = [] if port_keys is None else port_keys

    await send_message(rabbitmq, f"Pulling inputs for {port_keys}")
    transferred_bytes = await nodeports.download_target_ports(
        nodeports.PortTypeName.INPUTS,
        mounted_volumes.disk_inputs_path,
        port_keys=port_keys,
    )
    await send_message(rabbitmq, "Finished pulling inputs")
    progress.publish(message="finished inputs pulling", percent=1.0)
    return int(transferred_bytes)


async def task_ports_outputs_pull(
    progress: TaskProgress,
    port_keys: Optional[list[str]],
    mounted_volumes: MountedVolumes,
    rabbitmq: RabbitMQ,
) -> int:
    progress.publish(message="starting outputs pulling", percent=0.0)
    port_keys = [] if port_keys is None else port_keys

    await send_message(rabbitmq, f"Pulling output for {port_keys}")
    transferred_bytes = await nodeports.download_target_ports(
        nodeports.PortTypeName.OUTPUTS,
        mounted_volumes.disk_outputs_path,
        port_keys=port_keys,
    )
    await send_message(rabbitmq, "Finished pulling outputs")
    progress.publish(message="finished outputs pulling", percent=1.0)
    return int(transferred_bytes)


async def task_ports_outputs_push(
    progress: TaskProgress,
    port_keys: Optional[list[str]],
    mounted_volumes: MountedVolumes,
    rabbitmq: RabbitMQ,
) -> None:
    progress.publish(message="starting outputs pushing", percent=0.0)
    port_keys = [] if port_keys is None else port_keys

    await send_message(rabbitmq, f"Pushing outputs for {port_keys}")
    await nodeports.upload_outputs(
        mounted_volumes.disk_outputs_path, port_keys=port_keys
    )
    await send_message(rabbitmq, "Finished pulling outputs")
    progress.publish(message="finished outputs pushing", percent=1.0)


async def task_containers_restart(
    progress: TaskProgress,
    app: FastAPI,
    settings: ApplicationSettings,
    shared_store: SharedStore,
    rabbitmq: RabbitMQ,
) -> None:
    progress.publish(message="starting containers restart", percent=0.0)
    if shared_store.compose_spec is None:
        raise RuntimeError("No spec for docker-compose command was found")

    for container_name in shared_store.container_names:
        await stop_log_fetching(app, container_name)

    progress.publish(message="stopped log fetching", percent=0.1)

    result = await docker_compose_restart(shared_store.compose_spec, settings)

    if not result.success:
        logger.warning(
            "docker-compose restart finished with errors\n%s", result.message
        )
        raise RuntimeError(result.message)

    progress.publish(message="containers restarted", percent=0.8)

    for container_name in shared_store.container_names:
        await start_log_fetching(app, container_name)

    progress.publish(message="started log fetching", percent=0.9)

    await send_message(rabbitmq, "Service was restarted please reload the UI")
    await rabbitmq.send_event_reload_iframe()
    progress.publish(message="started log fetching", percent=1.0)
