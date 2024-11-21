import functools
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

from fastapi import FastAPI
from models_library.api_schemas_long_running_tasks.base import (
    ProgressPercent,
    TaskProgress,
)
from models_library.basic_types import IDStr
from models_library.generated_models.docker_rest_api import ContainerState
from models_library.rabbitmq_messages import ProgressType, SimcorePlatformStatus
from pydantic import PositiveInt
from servicelib.file_utils import log_directory_changes
from servicelib.logging_utils import log_context
from servicelib.progress_bar import ProgressBarData
from servicelib.utils import logged_gather
from simcore_sdk.node_data import data_manager
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
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
from ..core.docker_utils import (
    are_all_containers_in_expected_states,
    get_container_states,
    get_containers_count_from_names,
)
from ..core.rabbitmq import (
    post_event_reload_iframe,
    post_progress_message,
    post_sidecar_log_message,
)
from ..core.settings import ApplicationSettings
from ..core.utils import CommandResult
from ..core.validation import parse_compose_spec
from ..models.schemas.application_health import ApplicationHealth
from ..models.schemas.containers import ContainersCreate
from ..models.shared_store import SharedStore
from ..modules import nodeports, user_services_preferences
from ..modules.mounted_fs import MountedVolumes
from ..modules.notifications._notifications_ports import PortNotifier
from ..modules.outputs import OutputsManager, event_propagation_disabled
from .long_running_tasksutils import run_before_shutdown_actions
from .resource_tracking import send_service_started, send_service_stopped

_logger = logging.getLogger(__name__)


# TASKS

# NOTE: most services have only 1 "working" directory
CONCURRENCY_STATE_SAVE_RESTORE: Final[int] = 2
_MINUTE: Final[int] = 60


def _raise_for_errors(
    command_result: CommandResult, docker_compose_command: str
) -> None:
    if not command_result.success:
        _logger.warning(
            "docker compose %s command finished with errors\n%s",
            docker_compose_command,
            command_result.message,
        )
        raise RuntimeError(command_result.message)


@retry(
    wait=wait_random_exponential(max=30),
    stop=stop_after_delay(5 * _MINUTE),
    retry=retry_if_result(lambda result: result.success is False),
    reraise=False,
    before_sleep=before_sleep_log(_logger, logging.WARNING, exc_info=True),
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
    retry=retry_if_result(lambda result: result.success is False),
    reraise=False,
    before_sleep=before_sleep_log(_logger, logging.WARNING, exc_info=True),
)
async def _retry_docker_compose_down(
    compose_spec: str, settings: ApplicationSettings
) -> CommandResult:
    return await docker_compose_down(compose_spec, settings)


@retry(
    wait=wait_random_exponential(max=30),
    stop=stop_after_delay(5 * _MINUTE),
    retry=retry_if_result(lambda result: result is False),
    reraise=True,
    before_sleep=before_sleep_log(_logger, logging.WARNING, exc_info=True),
)
async def _retry_docker_compose_create(
    compose_spec: str, settings: ApplicationSettings
) -> bool:
    result = await docker_compose_create(compose_spec, settings)
    _raise_for_errors(result, "up")

    compose_spec_dict = parse_compose_spec(compose_spec)
    container_names = list(compose_spec_dict["services"].keys())

    expected_num_containers = len(container_names)
    actual_num_containers = await get_containers_count_from_names(container_names)

    return expected_num_containers == actual_num_containers


@asynccontextmanager
async def _reset_on_error(
    shared_store: SharedStore,
) -> AsyncGenerator[None, None]:
    try:
        yield None
    except Exception:
        async with shared_store:
            shared_store.compose_spec = None
            shared_store.container_names = []
        raise


async def task_pull_user_servcices_docker_images(
    progress: TaskProgress, shared_store: SharedStore, app: FastAPI
) -> None:
    assert shared_store.compose_spec  # nosec

    progress.update(message="started pulling user services", percent=ProgressPercent(0))

    await docker_compose_pull(app, shared_store.compose_spec)

    progress.update(
        message="finished pulling user services", percent=ProgressPercent(1)
    )


async def task_create_service_containers(
    progress: TaskProgress,
    settings: ApplicationSettings,
    containers_create: ContainersCreate,
    shared_store: SharedStore,
    app: FastAPI,
    application_health: ApplicationHealth,
) -> list[str]:
    progress.update(message="validating service spec", percent=ProgressPercent(0))

    assert shared_store.compose_spec  # nosec

    async with event_propagation_disabled(app), _reset_on_error(
        shared_store
    ), ProgressBarData(
        num_steps=4,
        progress_report_cb=functools.partial(
            post_progress_message,
            app,
            ProgressType.SERVICE_CONTAINERS_STARTING,
        ),
        description=IDStr("starting software"),
    ) as progress_bar:
        with log_context(_logger, logging.INFO, "load user services preferences"):
            if user_services_preferences.is_feature_enabled(app):
                await user_services_preferences.load_user_services_preferences(app)
        await progress_bar.update()

        # removes previous pending containers
        progress.update(message="cleanup previous used resources")
        result = await docker_compose_rm(shared_store.compose_spec, settings)
        _raise_for_errors(result, "rm")
        await progress_bar.update()

        progress.update(
            message="creating and starting containers", percent=ProgressPercent(0.90)
        )
        await post_sidecar_log_message(
            app, "starting service containers", log_level=logging.INFO
        )
        await _retry_docker_compose_create(shared_store.compose_spec, settings)
        await progress_bar.update()

        progress.update(
            message="ensure containers are started", percent=ProgressPercent(0.95)
        )
        compose_start_result = await _retry_docker_compose_start(
            shared_store.compose_spec, settings
        )

    await send_service_started(app, metrics_params=containers_create.metrics_params)

    message = (
        f"Finished docker-compose start with output\n{compose_start_result.message}"
    )

    if compose_start_result.success:
        await post_sidecar_log_message(
            app, "user services started", log_level=logging.INFO
        )
        _logger.debug(message)
        for container_name in shared_store.container_names:
            await start_log_fetching(app, container_name)
    else:
        application_health.is_healthy = False
        application_health.error_message = message
        _logger.error(
            "Marked sidecar as unhealthy, see below for details\n:%s", message
        )
        await post_sidecar_log_message(
            app, "could not start user services", log_level=logging.ERROR
        )

    return shared_store.container_names


async def task_runs_docker_compose_down(
    progress: TaskProgress,
    app: FastAPI,
    shared_store: SharedStore,
    settings: ApplicationSettings,
) -> None:
    if shared_store.compose_spec is None:
        _logger.warning("No compose-spec was found")
        return

    container_states: dict[str, ContainerState | None] = await get_container_states(
        shared_store.container_names
    )
    containers_were_ok = are_all_containers_in_expected_states(
        container_states.values()
    )

    container_count_before_down: PositiveInt = await get_containers_count_from_names(
        shared_store.container_names
    )

    async def _send_resource_tracking_stop(platform_status: SimcorePlatformStatus):
        # NOTE: avoids sending a stop message without a start or any heartbeats,
        # which makes no sense for the purpose of billing
        if container_count_before_down > 0:
            # if containers were not OK, we need to check their status
            # only if oom killed we report as BAD
            simcore_platform_status = platform_status
            if not containers_were_ok:
                any_container_oom_killed = any(
                    c.oom_killed is True
                    for c in container_states.values()
                    if c is not None
                )
                # if it's not an OOM killer (the user killed it) we set it as bad
                # since the platform failed the container
                if any_container_oom_killed:
                    _logger.warning(
                        "Containers killed to to OOMKiller: %s", container_states
                    )
                else:
                    # NOTE: MD/ANE discussed: Initial thought was to use SimcorePlatformStatus to
                    # inform RUT that there was some problem on Simcore side and therefore we will
                    # not bill the user for running the service. This needs to be discussed
                    # therefore we will always consider it as OK for now.
                    # NOTE: https://github.com/ITISFoundation/osparc-simcore/issues/4952
                    simcore_platform_status = SimcorePlatformStatus.OK

            await send_service_stopped(app, simcore_platform_status)

    try:
        progress.update(
            message="running docker-compose-down", percent=ProgressPercent(0.1)
        )

        await run_before_shutdown_actions(
            shared_store, settings.DY_SIDECAR_CALLBACKS_MAPPING.before_shutdown
        )

        with log_context(_logger, logging.INFO, "save user services preferences"):
            if user_services_preferences.is_feature_enabled(app):
                await user_services_preferences.save_user_services_preferences(app)

        result = await _retry_docker_compose_down(shared_store.compose_spec, settings)
        _raise_for_errors(result, "down")

        progress.update(message="stopping logs", percent=ProgressPercent(0.9))
        for container_name in shared_store.container_names:
            await stop_log_fetching(app, container_name)

        progress.update(
            message="removing pending resources", percent=ProgressPercent(0.95)
        )
        result = await docker_compose_rm(shared_store.compose_spec, settings)
        _raise_for_errors(result, "rm")
    except Exception:
        # NOTE: https://github.com/ITISFoundation/osparc-simcore/issues/4952
        await _send_resource_tracking_stop(SimcorePlatformStatus.OK)
        raise

    await _send_resource_tracking_stop(SimcorePlatformStatus.OK)

    # removing compose-file spec
    async with shared_store:
        shared_store.compose_spec = None
        shared_store.container_names = []
    progress.update(message="done", percent=ProgressPercent(0.99))


def _get_satate_folders_size(paths: list[Path]) -> int:
    total_size: int = 0
    for path in paths:
        for file in path.rglob("*"):
            if file.is_file():
                total_size += file.stat().st_size
    return total_size


async def _restore_state_folder(
    app: FastAPI,
    *,
    settings: ApplicationSettings,
    progress_bar: ProgressBarData,
    state_path: Path,
) -> None:
    await data_manager.pull(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=settings.DY_SIDECAR_PROJECT_ID,
        node_uuid=settings.DY_SIDECAR_NODE_ID,
        destination_path=state_path,
        io_log_redirect_cb=functools.partial(
            post_sidecar_log_message, app, log_level=logging.INFO
        ),
        r_clone_settings=settings.DY_SIDECAR_R_CLONE_SETTINGS,
        progress_bar=progress_bar,
        aws_s3_cli_settings=settings.DY_SIDECAR_AWS_S3_CLI_SETTINGS,
    )


async def task_restore_state(
    progress: TaskProgress,
    settings: ApplicationSettings,
    mounted_volumes: MountedVolumes,
    app: FastAPI,
) -> int:
    # NOTE: the legacy data format was a zip file
    # this method will maintain retro compatibility.
    # The legacy archive is always downloaded and decompressed
    # if found. If the `task_save_state` is successful the legacy
    # archive will be removed.
    # When the legacy archive is detected it will have precedence
    # over the new format.
    # NOTE: this implies that the legacy format will always be decompressed
    # until it is not removed.

    progress.update(message="Downloading state", percent=ProgressPercent(0.05))
    state_paths = list(mounted_volumes.disk_state_paths_iter())
    await post_sidecar_log_message(
        app,
        f"Downloading state files for {state_paths}...",
        log_level=logging.INFO,
    )
    async with ProgressBarData(
        num_steps=len(state_paths),
        progress_report_cb=functools.partial(
            post_progress_message,
            app,
            ProgressType.SERVICE_STATE_PULLING,
        ),
        description=IDStr("pulling states"),
    ) as root_progress:
        await logged_gather(
            *(
                _restore_state_folder(
                    app, settings=settings, progress_bar=root_progress, state_path=path
                )
                for path in mounted_volumes.disk_state_paths_iter()
            ),
            max_concurrency=CONCURRENCY_STATE_SAVE_RESTORE,
            reraise=True,  # this should raise if there is an issue
        )

    await post_sidecar_log_message(
        app, "Finished state downloading", log_level=logging.INFO
    )
    progress.update(message="state restored", percent=ProgressPercent(0.99))

    return _get_satate_folders_size(state_paths)


async def _save_state_folder(
    app: FastAPI,
    *,
    settings: ApplicationSettings,
    progress_bar: ProgressBarData,
    state_path: Path,
    mounted_volumes: MountedVolumes,
) -> None:
    await data_manager.push(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=settings.DY_SIDECAR_PROJECT_ID,
        node_uuid=settings.DY_SIDECAR_NODE_ID,
        source_path=state_path,
        r_clone_settings=settings.DY_SIDECAR_R_CLONE_SETTINGS,
        exclude_patterns=mounted_volumes.state_exclude,
        io_log_redirect_cb=functools.partial(
            post_sidecar_log_message, app, log_level=logging.INFO
        ),
        progress_bar=progress_bar,
        aws_s3_cli_settings=settings.DY_SIDECAR_AWS_S3_CLI_SETTINGS,
    )


async def task_save_state(
    progress: TaskProgress,
    settings: ApplicationSettings,
    mounted_volumes: MountedVolumes,
    app: FastAPI,
) -> int:
    """
    Saves the states of the service.
    If a legacy archive is detected, it will be removed after
    saving the new format.
    """
    progress.update(message="starting state save", percent=ProgressPercent(0.0))
    state_paths = list(mounted_volumes.disk_state_paths_iter())
    async with ProgressBarData(
        num_steps=len(state_paths),
        progress_report_cb=functools.partial(
            post_progress_message,
            app,
            ProgressType.SERVICE_STATE_PUSHING,
        ),
        description=IDStr("pushing state"),
    ) as root_progress:
        await logged_gather(
            *[
                _save_state_folder(
                    app,
                    settings=settings,
                    progress_bar=root_progress,
                    state_path=state_path,
                    mounted_volumes=mounted_volumes,
                )
                for state_path in state_paths
            ],
            max_concurrency=CONCURRENCY_STATE_SAVE_RESTORE,
        )

    await post_sidecar_log_message(app, "Finished state saving", log_level=logging.INFO)
    progress.update(message="finished state saving", percent=ProgressPercent(0.99))

    return _get_satate_folders_size(state_paths)


async def task_ports_inputs_pull(
    progress: TaskProgress,
    port_keys: list[str] | None,
    mounted_volumes: MountedVolumes,
    app: FastAPI,
    settings: ApplicationSettings,
    *,
    inputs_pulling_enabled: bool,
) -> int:
    if not inputs_pulling_enabled:
        _logger.info("Received request to pull inputs but was ignored")
        return 0

    progress.update(message="starting inputs pulling", percent=ProgressPercent(0.0))
    port_keys = [] if port_keys is None else port_keys
    await post_sidecar_log_message(
        app, f"Pulling inputs for {port_keys}", log_level=logging.INFO
    )
    progress.update(message="pulling inputs", percent=ProgressPercent(0.1))
    async with ProgressBarData(
        num_steps=1,
        progress_report_cb=functools.partial(
            post_progress_message,
            app,
            ProgressType.SERVICE_INPUTS_PULLING,
        ),
        description=IDStr("pulling inputs"),
    ) as root_progress:
        with log_directory_changes(
            mounted_volumes.disk_inputs_path, _logger, logging.INFO
        ):
            transferred_bytes = await nodeports.download_target_ports(
                nodeports.PortTypeName.INPUTS,
                mounted_volumes.disk_inputs_path,
                port_keys=port_keys,
                io_log_redirect_cb=functools.partial(
                    post_sidecar_log_message, app, log_level=logging.INFO
                ),
                progress_bar=root_progress,
                port_notifier=PortNotifier(
                    app,
                    settings.DY_SIDECAR_USER_ID,
                    settings.DY_SIDECAR_PROJECT_ID,
                    settings.DY_SIDECAR_NODE_ID,
                ),
            )
    await post_sidecar_log_message(
        app, "Finished pulling inputs", log_level=logging.INFO
    )
    progress.update(message="finished inputs pulling", percent=ProgressPercent(0.99))
    return int(transferred_bytes)


async def task_ports_outputs_pull(
    progress: TaskProgress,
    port_keys: list[str] | None,
    mounted_volumes: MountedVolumes,
    app: FastAPI,
) -> int:
    progress.update(message="starting outputs pulling", percent=ProgressPercent(0.0))
    port_keys = [] if port_keys is None else port_keys
    await post_sidecar_log_message(
        app, f"Pulling output for {port_keys}", log_level=logging.INFO
    )
    async with ProgressBarData(
        num_steps=1,
        progress_report_cb=functools.partial(
            post_progress_message,
            app,
            ProgressType.SERVICE_OUTPUTS_PULLING,
        ),
        description=IDStr("pulling outputs"),
    ) as root_progress:
        transferred_bytes = await nodeports.download_target_ports(
            nodeports.PortTypeName.OUTPUTS,
            mounted_volumes.disk_outputs_path,
            port_keys=port_keys,
            io_log_redirect_cb=functools.partial(
                post_sidecar_log_message, app, log_level=logging.INFO
            ),
            progress_bar=root_progress,
            port_notifier=None,
        )
    await post_sidecar_log_message(
        app, "Finished pulling outputs", log_level=logging.INFO
    )
    progress.update(message="finished outputs pulling", percent=ProgressPercent(0.99))
    return int(transferred_bytes)


async def task_ports_outputs_push(
    progress: TaskProgress, outputs_manager: OutputsManager, app: FastAPI
) -> None:
    progress.update(message="starting outputs pushing", percent=ProgressPercent(0.0))
    await post_sidecar_log_message(
        app,
        f"waiting for outputs {outputs_manager.outputs_context.file_type_port_keys} to be pushed",
        log_level=logging.INFO,
    )

    await outputs_manager.wait_for_all_uploads_to_finish()

    await post_sidecar_log_message(
        app, "finished outputs pushing", log_level=logging.INFO
    )
    progress.update(message="finished outputs pushing", percent=ProgressPercent(0.99))


async def task_containers_restart(
    progress: TaskProgress,
    app: FastAPI,
    settings: ApplicationSettings,
    shared_store: SharedStore,
) -> None:
    assert app.state.container_restart_lock  # nosec

    # NOTE: if containers inspect reports that the containers are restarting
    # or some other state, the service will get shutdown, to prevent this
    # blocking status while containers are being restarted.
    async with app.state.container_restart_lock:
        progress.update(
            message="starting containers restart", percent=ProgressPercent(0.0)
        )
        if shared_store.compose_spec is None:
            msg = "No spec for docker compose command was found"
            raise RuntimeError(msg)

        for container_name in shared_store.container_names:
            await stop_log_fetching(app, container_name)

        progress.update(message="stopped log fetching", percent=ProgressPercent(0.1))

        result = await docker_compose_restart(shared_store.compose_spec, settings)
        _raise_for_errors(result, "restart")

        progress.update(message="containers restarted", percent=ProgressPercent(0.8))

        for container_name in shared_store.container_names:
            await start_log_fetching(app, container_name)

        progress.update(message="started log fetching", percent=ProgressPercent(0.9))

        await post_sidecar_log_message(
            app, "Service was restarted please reload the UI", log_level=logging.INFO
        )
        await post_event_reload_iframe(app)
        progress.update(message="started log fetching", percent=ProgressPercent(0.99))
