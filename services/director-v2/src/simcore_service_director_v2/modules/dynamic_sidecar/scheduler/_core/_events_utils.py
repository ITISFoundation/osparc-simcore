# pylint: disable=relative-beyond-top-level

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, cast

from fastapi import FastAPI
from models_library.api_schemas_long_running_tasks.base import ProgressPercent
from models_library.products import ProductName
from models_library.projects_networks import ProjectsNetworks
from models_library.projects_nodes_io import NodeID, NodeIDStr
from models_library.rabbitmq_messages import InstrumentationRabbitMessage
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceKeyVersion
from models_library.shared_user_preferences import (
    AllowMetricsCollectionFrontendUserPreference,
)
from models_library.sidecar_volumes import VolumeCategory, VolumeStatus
from models_library.user_preferences import FrontendUserPreference
from models_library.users import UserID
from servicelib.fastapi.http_client_thin import BaseHttpClientError
from servicelib.fastapi.long_running_tasks.client import (
    ProgressCallback,
    TaskClientResultError,
)
from servicelib.fastapi.long_running_tasks.server import TaskProgress
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.agent.errors import (
    NoServiceVolumesFoundRPCError,
)
from servicelib.rabbitmq.rpc_interfaces.agent.volumes import (
    remove_volumes_without_backup_for_service,
)
from servicelib.utils import limited_gather, logged_gather
from simcore_postgres_database.models.comp_tasks import NodeClass
from tenacity import RetryError, TryAgain
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .....core.dynamic_services_settings.scheduler import (
    DynamicServicesSchedulerSettings,
)
from .....core.settings import AppSettings
from .....models.dynamic_services_scheduler import (
    DockerContainerInspect,
    DockerStatus,
    SchedulerData,
)
from .....modules.instrumentation import (
    get_instrumentation,
    get_metrics_labels,
    get_rate,
    track_duration,
)
from .....utils.db import get_repository
from ....db.repositories.projects import ProjectsRepository
from ....db.repositories.projects_networks import ProjectsNetworksRepository
from ....db.repositories.user_preferences_frontend import (
    UserPreferencesFrontendRepository,
)
from ....director_v0 import DirectorV0Client
from ...api_client import (
    SidecarsClient,
    get_dynamic_sidecar_service_health,
    get_sidecars_client,
    remove_sidecars_client,
)
from ...docker_api import (
    get_projects_networks_containers,
    remove_dynamic_sidecar_network,
    remove_dynamic_sidecar_stack,
    try_to_remove_network,
)
from ...errors import EntrypointContainerNotFoundError

if TYPE_CHECKING:
    # NOTE: TYPE_CHECKING is True when static type checkers are running,
    # allowing for circular imports only for them (mypy, pylance, ruff)
    from .._task import DynamicSidecarsScheduler

_logger = logging.getLogger(__name__)


def get_director_v0_client(app: FastAPI) -> DirectorV0Client:
    return DirectorV0Client.instance(app)


def parse_containers_inspect(
    containers_inspect: dict[str, Any] | None
) -> list[DockerContainerInspect]:
    if containers_inspect is None:
        return []

    return [
        DockerContainerInspect.from_container(containers_inspect[container_id])
        for container_id in containers_inspect
    ]


def are_all_user_services_containers_running(
    containers_inspect: list[DockerContainerInspect],
) -> bool:
    return len(containers_inspect) > 0 and all(
        x.status == DockerStatus.running for x in containers_inspect
    )


def _get_scheduler_data(app: FastAPI, node_uuid: NodeID) -> SchedulerData:
    dynamic_sidecars_scheduler: DynamicSidecarsScheduler = (
        app.state.dynamic_sidecar_scheduler
    )
    # pylint: disable=protected-access
    scheduler_data: SchedulerData = (
        dynamic_sidecars_scheduler.scheduler.get_scheduler_data(node_uuid)
    )
    return scheduler_data


async def service_remove_containers(
    app: FastAPI,
    node_uuid: NodeID,
    sidecars_client: SidecarsClient,
    progress_callback: ProgressCallback | None = None,
) -> None:
    scheduler_data: SchedulerData = _get_scheduler_data(app, node_uuid)

    try:
        await sidecars_client.stop_service(
            scheduler_data.endpoint, progress_callback=progress_callback
        )
    except (BaseHttpClientError, TaskClientResultError) as e:
        _logger.info(
            (
                "Could not remove service containers for %s. "
                "Will continue to save the data from the service! Error: %s"
            ),
            scheduler_data.service_name,
            f"{type(e)}: {e}",
        )


async def service_free_reserved_disk_space(
    app: FastAPI, node_id: NodeID, sidecars_client: SidecarsClient
) -> None:
    scheduler_data: SchedulerData = _get_scheduler_data(app, node_id)
    try:
        await sidecars_client.free_reserved_disk_space(scheduler_data.endpoint)
    except BaseHttpClientError as e:
        _logger.info(
            (
                "Could not remove service containers for %s. "
                "Will continue to save the data from the service! Error: %s"
            ),
            scheduler_data.service_name,
            f"{type(e)}: {e}",
        )


async def service_save_state(
    app: FastAPI,
    node_uuid: NodeID,
    sidecars_client: SidecarsClient,
    progress_callback: ProgressCallback | None = None,
) -> None:
    scheduler_data: SchedulerData = _get_scheduler_data(app, node_uuid)

    with track_duration() as duration:
        size = await sidecars_client.save_service_state(
            scheduler_data.endpoint, progress_callback=progress_callback
        )
    if size and size > 0:
        get_instrumentation(app).dynamic_sidecar_metrics.push_service_state_rate.labels(
            **get_metrics_labels(scheduler_data)
        ).observe(get_rate(size, duration.to_float()))

    await sidecars_client.update_volume_state(
        scheduler_data.endpoint,
        volume_category=VolumeCategory.STATES,
        volume_status=VolumeStatus.CONTENT_WAS_SAVED,
    )


async def service_push_outputs(
    app: FastAPI,
    node_uuid: NodeID,
    sidecars_client: SidecarsClient,
    progress_callback: ProgressCallback | None = None,
) -> None:
    scheduler_data: SchedulerData = _get_scheduler_data(app, node_uuid)
    await sidecars_client.push_service_output_ports(
        scheduler_data.endpoint, progress_callback=progress_callback
    )
    await sidecars_client.update_volume_state(
        scheduler_data.endpoint,
        volume_category=VolumeCategory.OUTPUTS,
        volume_status=VolumeStatus.CONTENT_WAS_SAVED,
    )


async def service_remove_sidecar_proxy_docker_networks_and_volumes(
    task_progress: TaskProgress,
    app: FastAPI,
    node_uuid: NodeID,
    swarm_stack_name: str,
    set_were_state_and_outputs_saved: bool | None = None,
) -> None:
    scheduler_data: SchedulerData = _get_scheduler_data(app, node_uuid)

    if set_were_state_and_outputs_saved is not None:
        scheduler_data.dynamic_sidecar.were_state_and_outputs_saved = True

    task_progress.update(
        message="removing dynamic sidecar stack", percent=ProgressPercent(0.1)
    )
    await remove_dynamic_sidecar_stack(
        node_uuid=scheduler_data.node_uuid,
        swarm_stack_name=swarm_stack_name,
    )
    # remove network
    task_progress.update(message="removing network", percent=ProgressPercent(0.2))
    await remove_dynamic_sidecar_network(scheduler_data.dynamic_sidecar_network_name)

    if scheduler_data.dynamic_sidecar.were_state_and_outputs_saved:
        if scheduler_data.dynamic_sidecar.docker_node_id is None:
            _logger.warning(
                "Skipped volume removal for %s, since a docker_node_id was not found.",
                scheduler_data.node_uuid,
            )
        else:
            # Remove all dy-sidecar associated volumes from node
            task_progress.update(
                message="removing volumes", percent=ProgressPercent(0.3)
            )
            with log_context(_logger, logging.DEBUG, f"removing volumes '{node_uuid}'"):
                rabbit_rpc_client: RabbitMQRPCClient = app.state.rabbitmq_rpc_client
                try:
                    await remove_volumes_without_backup_for_service(
                        rabbit_rpc_client,
                        docker_node_id=scheduler_data.dynamic_sidecar.docker_node_id,
                        swarm_stack_name=swarm_stack_name,
                        node_id=scheduler_data.node_uuid,
                    )
                except NoServiceVolumesFoundRPCError as e:
                    _logger.info("Could not remove volumes, reason: %s", e)

    _logger.debug(
        "Removed dynamic-sidecar services and crated container for '%s'",
        scheduler_data.service_name,
    )

    task_progress.update(
        message="removing project networks", percent=ProgressPercent(0.8)
    )
    used_projects_networks = await get_projects_networks_containers(
        project_id=scheduler_data.project_id
    )
    await logged_gather(
        *[
            try_to_remove_network(network_name)
            for network_name, container_count in used_projects_networks.items()
            if container_count == 0
        ]
    )

    # pylint: disable=protected-access
    scheduler_data.dynamic_sidecar.service_removal_state.mark_removed()
    await app.state.dynamic_sidecar_scheduler.scheduler.remove_service_from_observation(
        scheduler_data.node_uuid
    )
    task_progress.update(
        message="finished removing resources", percent=ProgressPercent(1)
    )


async def attempt_pod_removal_and_data_saving(
    app: FastAPI, scheduler_data: SchedulerData
) -> None:
    # invoke container cleanup at this point
    app_settings: AppSettings = app.state.settings
    settings: DynamicServicesSchedulerSettings = (
        app_settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
    )

    _logger.debug("removing service; scheduler_data=%s", scheduler_data)

    sidecars_client: SidecarsClient = await get_sidecars_client(
        app, scheduler_data.node_uuid
    )

    await service_remove_containers(app, scheduler_data.node_uuid, sidecars_client)

    # used for debuug, normally sleeps 0
    await asyncio.sleep(
        settings.DIRECTOR_V2_DYNAMIC_SIDECAR_SLEEP_AFTER_CONTAINER_REMOVAL.total_seconds()
    )

    # only try to save the status if :
    # - it is requested to save the state
    # - the dynamic-sidecar has finished booting correctly

    can_really_save: bool = False
    if scheduler_data.dynamic_sidecar.service_removal_state.can_save:
        # if node is not present in the workbench it makes no sense
        # to try and save the data, nodeports will raise errors
        # and sidecar will hang

        projects_repository: ProjectsRepository = get_repository(
            app, ProjectsRepository
        )

        can_really_save = await projects_repository.is_node_present_in_workbench(
            project_id=scheduler_data.project_id, node_uuid=scheduler_data.node_uuid
        )

    if can_really_save and scheduler_data.dynamic_sidecar.were_containers_created:
        _logger.info("Calling into dynamic-sidecar to save: state and output ports")

        await service_free_reserved_disk_space(
            app, scheduler_data.node_uuid, sidecars_client
        )

        try:
            tasks = [
                service_push_outputs(app, scheduler_data.node_uuid, sidecars_client)
            ]

            # When enabled no longer uploads state via nodeports
            # It uses rclone mounted volumes for this task.
            if not app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED:
                tasks.append(
                    service_save_state(app, scheduler_data.node_uuid, sidecars_client)
                )

            await logged_gather(*tasks, max_concurrency=2)
            scheduler_data.dynamic_sidecar.were_state_and_outputs_saved = True

            _logger.info("dynamic-sidecar saved: state and output ports")
        except (BaseHttpClientError, TaskClientResultError) as e:
            _logger.error(  # noqa: TRY400
                (
                    "Could not contact dynamic-sidecar to save service "
                    "state or output ports %s\n%s"
                ),
                scheduler_data.service_name,
                f"{e}",
            )
            # ensure dynamic-sidecar does not get removed
            # user data can be manually saved and manual
            # cleanup of the dynamic-sidecar is required

            scheduler_data.dynamic_sidecar.wait_for_manual_intervention_after_error = (
                True
            )
            raise

    await service_remove_sidecar_proxy_docker_networks_and_volumes(
        TaskProgress.create(), app, scheduler_data.node_uuid, settings.SWARM_STACK_NAME
    )

    # remove sidecar's api client
    remove_sidecars_client(app, scheduler_data.node_uuid)

    # instrumentation
    message = InstrumentationRabbitMessage(
        metrics="service_stopped",
        user_id=scheduler_data.user_id,
        project_id=scheduler_data.project_id,
        node_id=scheduler_data.node_uuid,
        service_uuid=scheduler_data.node_uuid,
        service_type=NodeClass.INTERACTIVE.value,
        service_key=scheduler_data.key,
        service_tag=scheduler_data.version,
        simcore_user_agent=scheduler_data.request_simcore_user_agent,
    )
    rabbitmq_client: RabbitMQClient = app.state.rabbitmq_client
    await rabbitmq_client.publish(message.channel_name, message)

    # metrics

    stop_duration = (
        scheduler_data.dynamic_sidecar.instrumentation.elapsed_since_close_request()
    )
    assert stop_duration is not None  # nosec
    get_instrumentation(app).dynamic_sidecar_metrics.stop_time_duration.labels(
        **get_metrics_labels(scheduler_data)
    ).observe(stop_duration)


async def attach_project_networks(app: FastAPI, scheduler_data: SchedulerData) -> None:
    _logger.debug("Attaching project networks for %s", scheduler_data.service_name)

    sidecars_client = await get_sidecars_client(app, scheduler_data.node_uuid)
    dynamic_sidecar_endpoint = scheduler_data.endpoint

    projects_networks_repository: ProjectsNetworksRepository = get_repository(
        app, ProjectsNetworksRepository
    )

    projects_networks: ProjectsNetworks = (
        await projects_networks_repository.get_projects_networks(
            project_id=scheduler_data.project_id
        )
    )
    for (
        network_name,
        container_aliases,
    ) in projects_networks.networks_with_aliases.items():
        network_alias = container_aliases.get(NodeIDStr(scheduler_data.node_uuid))
        if network_alias is not None:
            await sidecars_client.attach_service_containers_to_project_network(
                dynamic_sidecar_endpoint=dynamic_sidecar_endpoint,
                dynamic_sidecar_network_name=scheduler_data.dynamic_sidecar_network_name,
                project_network=network_name,
                project_id=scheduler_data.project_id,
                network_alias=network_alias,
            )

    scheduler_data.dynamic_sidecar.is_project_network_attached = True


async def wait_for_sidecar_api(app: FastAPI, scheduler_data: SchedulerData) -> None:
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
    )
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(
                dynamic_services_scheduler_settings.DYNAMIC_SIDECAR_STARTUP_TIMEOUT_S
            ),
            wait=wait_fixed(1),
            before_sleep=before_sleep_log(_logger, logging.DEBUG),
        ):
            with attempt:
                if not await get_dynamic_sidecar_service_health(
                    app, scheduler_data, with_retry=False
                ):
                    raise TryAgain
                scheduler_data.dynamic_sidecar.is_healthy = True
    except RetryError as e:
        raise EntrypointContainerNotFoundError from e


async def prepare_services_environment(
    app: FastAPI, scheduler_data: SchedulerData
) -> None:
    app_settings: AppSettings = app.state.settings
    sidecars_client = await get_sidecars_client(app, scheduler_data.node_uuid)
    dynamic_sidecar_endpoint = scheduler_data.endpoint

    # Before starting, update the volume states. It is not always
    # required to save the data from these volumes, eg: when services
    # are opened in read only mode.
    volume_status: VolumeStatus = (
        VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED
        if scheduler_data.dynamic_sidecar.service_removal_state.can_save
        else VolumeStatus.CONTENT_NO_SAVE_REQUIRED
    )
    await logged_gather(
        *(
            sidecars_client.update_volume_state(
                scheduler_data.endpoint,
                volume_category=VolumeCategory.STATES,
                volume_status=volume_status,
            ),
            sidecars_client.update_volume_state(
                scheduler_data.endpoint,
                volume_category=VolumeCategory.OUTPUTS,
                volume_status=volume_status,
            ),
        )
    )

    async def _pull_output_ports_with_metrics() -> None:
        with track_duration() as duration:
            size: int = await sidecars_client.pull_service_output_ports(
                dynamic_sidecar_endpoint
            )
        if size and size > 0:
            get_instrumentation(
                app
            ).dynamic_sidecar_metrics.output_ports_pull_rate.labels(
                **get_metrics_labels(scheduler_data)
            ).observe(
                get_rate(size, duration.to_float())
            )

    async def _pull_user_services_images_with_metrics() -> None:
        with track_duration() as duration:
            await sidecars_client.pull_user_services_images(dynamic_sidecar_endpoint)

        get_instrumentation(
            app
        ).dynamic_sidecar_metrics.pull_user_services_images_duration.labels(
            **get_metrics_labels(scheduler_data)
        ).observe(
            duration.to_float()
        )

    async def _restore_service_state_with_metrics() -> None:
        with track_duration() as duration:
            size = await sidecars_client.restore_service_state(dynamic_sidecar_endpoint)

        if size and size > 0:
            get_instrumentation(
                app
            ).dynamic_sidecar_metrics.pull_service_state_rate.labels(
                **get_metrics_labels(scheduler_data)
            ).observe(
                get_rate(size, duration.to_float())
            )

    tasks = [
        _pull_user_services_images_with_metrics(),
        _pull_output_ports_with_metrics(),
    ]
    # When enabled no longer downloads state via nodeports
    # S3 is used to store state paths
    if not app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED:
        tasks.append(_restore_service_state_with_metrics())

    await limited_gather(*tasks, limit=3)

    # inside this directory create the missing dirs, fetch those form the labels
    director_v0_client: DirectorV0Client = get_director_v0_client(app)
    simcore_service_labels: SimcoreServiceLabels = (
        await director_v0_client.get_service_labels(
            service=ServiceKeyVersion(
                key=scheduler_data.key, version=scheduler_data.version
            )
        )
    )
    service_outputs_labels = json.loads(
        simcore_service_labels.model_dump().get("io.simcore.outputs", "{}")
    ).get("outputs", {})
    _logger.debug(
        "Creating dirs from service outputs labels: %s",
        service_outputs_labels,
    )
    await sidecars_client.service_outputs_create_dirs(
        dynamic_sidecar_endpoint, service_outputs_labels
    )

    scheduler_data.dynamic_sidecar.is_service_environment_ready = True


async def get_allow_metrics_collection(
    app: FastAPI, user_id: UserID, product_name: ProductName
) -> bool:
    repo = get_repository(app, UserPreferencesFrontendRepository)
    preference: FrontendUserPreference | None = await repo.get_user_preference(
        user_id=user_id,
        product_name=product_name,
        preference_class=AllowMetricsCollectionFrontendUserPreference,
    )

    if preference is None:
        return cast(
            bool, AllowMetricsCollectionFrontendUserPreference.get_default_value()
        )

    allow_metrics_collection = (
        AllowMetricsCollectionFrontendUserPreference.model_validate(preference)
    )
    return allow_metrics_collection.value
