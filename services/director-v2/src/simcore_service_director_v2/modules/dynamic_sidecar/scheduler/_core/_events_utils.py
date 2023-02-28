# pylint: disable=relative-beyond-top-level

import json
import logging
from collections import deque
from typing import Any, Deque, Final, Optional, cast

from fastapi import FastAPI
from models_library.projects_networks import ProjectsNetworks
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import NodeIDStr
from models_library.rabbitmq_messages import InstrumentationRabbitMessage
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceKeyVersion
from servicelib.fastapi.long_running_tasks.client import (
    ProgressCallback,
    TaskClientResultError,
)
from servicelib.fastapi.long_running_tasks.server import TaskProgress
from servicelib.utils import logged_gather
from simcore_postgres_database.models.comp_tasks import NodeClass
from tenacity import TryAgain
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .....core.errors import NodeRightsAcquireError
from .....core.settings import AppSettings, DynamicSidecarSettings
from .....models.schemas.dynamic_services.scheduler import (
    DockerContainerInspect,
    DockerStatus,
    SchedulerData,
)
from .....utils.db import get_repository
from ....db.repositories.projects import ProjectsRepository
from ....db.repositories.projects_networks import ProjectsNetworksRepository
from ....director_v0 import DirectorV0Client
from ....node_rights import NodeRightsManager, ResourceName
from ....rabbitmq import RabbitMQClient
from ...api_client import (
    BaseClientHTTPError,
    DynamicSidecarClient,
    get_dynamic_sidecar_client,
    get_dynamic_sidecar_service_health,
)
from ...docker_api import (
    get_projects_networks_containers,
    remove_dynamic_sidecar_network,
    remove_dynamic_sidecar_stack,
    remove_volumes_from_node,
    try_to_remove_network,
)
from ...errors import EntrypointContainerNotFoundError
from ...volumes import DY_SIDECAR_SHARED_STORE_PATH, DynamicSidecarVolumesPathsResolver

logger = logging.getLogger(__name__)


# Used to ensure no more that X services per node pull or push data
# Locking is applied when:
# - study is being opened (state and outputs are pulled)
# - study is being closed (state and outputs are saved)
RESOURCE_STATE_AND_INPUTS: Final[ResourceName] = "state_and_inputs"


def get_director_v0_client(app: FastAPI) -> DirectorV0Client:
    client = DirectorV0Client.instance(app)
    return client


def parse_containers_inspect(
    containers_inspect: Optional[dict[str, Any]]
) -> list[DockerContainerInspect]:
    results: Deque[DockerContainerInspect] = deque()

    if containers_inspect is None:
        return []

    for container_id in containers_inspect:
        container_inspect_data = containers_inspect[container_id]
        results.append(DockerContainerInspect.from_container(container_inspect_data))
    return list(results)


def are_all_user_services_containers_running(
    containers_inspect: list[DockerContainerInspect],
) -> bool:
    return len(containers_inspect) > 0 and all(
        x.status == DockerStatus.running for x in containers_inspect
    )


def _get_scheduler_data(app: FastAPI, node_uuid: NodeID) -> SchedulerData:
    dynamic_sidecars_scheduler: "DynamicSidecarsScheduler" = (
        app.state.dynamic_sidecar_scheduler
    )
    # pylint: disable=protected-access
    return dynamic_sidecars_scheduler._scheduler.get_scheduler_data(node_uuid)


async def service_remove_containers(
    app: FastAPI,
    node_uuid: NodeID,
    dynamic_sidecar_client: DynamicSidecarClient,
    progress_callback: Optional[ProgressCallback] = None,
) -> None:
    scheduler_data: SchedulerData = _get_scheduler_data(app, node_uuid)

    try:
        await dynamic_sidecar_client.stop_service(
            scheduler_data.endpoint, progress_callback=progress_callback
        )
    except (BaseClientHTTPError, TaskClientResultError) as e:
        logger.warning(
            (
                "Could not remove service containers for "
                "%s\n%s. Will continue to save the data from the service!"
            ),
            scheduler_data.service_name,
            f"{e}",
        )


async def service_save_state(
    app: FastAPI,
    node_uuid: NodeID,
    dynamic_sidecar_client: DynamicSidecarClient,
    progress_callback: Optional[ProgressCallback] = None,
) -> None:
    scheduler_data: SchedulerData = _get_scheduler_data(app, node_uuid)
    await dynamic_sidecar_client.save_service_state(
        scheduler_data.endpoint, progress_callback=progress_callback
    )


async def service_push_outputs(
    app: FastAPI,
    node_uuid: NodeID,
    dynamic_sidecar_client: DynamicSidecarClient,
    progress_callback: Optional[ProgressCallback] = None,
) -> None:
    scheduler_data: SchedulerData = _get_scheduler_data(app, node_uuid)
    await dynamic_sidecar_client.push_service_output_ports(
        scheduler_data.endpoint, progress_callback=progress_callback
    )


async def service_remove_sidecar_proxy_docker_networks_and_volumes(
    task_progress: TaskProgress,
    app: FastAPI,
    node_uuid: NodeID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    set_were_state_and_outputs_saved: Optional[bool] = None,
) -> None:
    scheduler_data: SchedulerData = _get_scheduler_data(app, node_uuid)

    if set_were_state_and_outputs_saved is not None:
        scheduler_data.dynamic_sidecar.were_state_and_outputs_saved = True

    # remove the 2 services
    task_progress.update(message="removing dynamic sidecar stack", percent=0.1)
    await remove_dynamic_sidecar_stack(
        node_uuid=scheduler_data.node_uuid,
        dynamic_sidecar_settings=dynamic_sidecar_settings,
    )
    # remove network
    task_progress.update(message="removing network", percent=0.2)
    await remove_dynamic_sidecar_network(scheduler_data.dynamic_sidecar_network_name)

    if scheduler_data.dynamic_sidecar.were_state_and_outputs_saved:
        if scheduler_data.dynamic_sidecar.docker_node_id is None:
            logger.warning(
                "Skipped volume removal for %s, since a docker_node_id was not found.",
                scheduler_data.node_uuid,
            )
        else:
            # Remove all dy-sidecar associated volumes from node
            task_progress.update(message="removing volumes", percent=0.3)
            unique_volume_names = [
                DynamicSidecarVolumesPathsResolver.source(
                    path=volume_path,
                    node_uuid=scheduler_data.node_uuid,
                    run_id=scheduler_data.run_id,
                )
                for volume_path in [
                    DY_SIDECAR_SHARED_STORE_PATH,
                    scheduler_data.paths_mapping.inputs_path,
                    scheduler_data.paths_mapping.outputs_path,
                ]
                + scheduler_data.paths_mapping.state_paths
            ]
            await remove_volumes_from_node(
                dynamic_sidecar_settings=dynamic_sidecar_settings,
                volume_names=unique_volume_names,
                docker_node_id=scheduler_data.dynamic_sidecar.docker_node_id,
                user_id=scheduler_data.user_id,
                project_id=scheduler_data.project_id,
                node_uuid=scheduler_data.node_uuid,
            )

    logger.debug(
        "Removed dynamic-sidecar services and crated container for '%s'",
        scheduler_data.service_name,
    )

    task_progress.update(message="removing project networks", percent=0.8)
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
    await app.state.dynamic_sidecar_scheduler._scheduler.remove_service_from_observation(
        scheduler_data.node_uuid
    )
    scheduler_data.dynamic_sidecar.service_removal_state.mark_removed()
    task_progress.update(message="finished removing resources", percent=1)


async def attempt_pod_removal_and_data_saving(
    app: FastAPI, scheduler_data: SchedulerData
) -> None:
    # invoke container cleanup at this point
    app_settings: AppSettings = app.state.settings
    dynamic_sidecar_settings: DynamicSidecarSettings = (
        app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
    )

    async def _remove_containers_save_state_and_outputs() -> None:
        dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(app)

        await service_remove_containers(
            app, scheduler_data.node_uuid, dynamic_sidecar_client
        )

        # only try to save the status if :
        # - it is requested to save the state
        # - the dynamic-sidecar has finished booting correctly

        can_really_save: bool = False
        if scheduler_data.dynamic_sidecar.service_removal_state.can_save:
            # if node is not present in the workbench it makes no sense
            # to try and save the data, nodeports will raise errors
            # and sidecar will hang

            projects_repository = cast(
                ProjectsRepository, get_repository(app, ProjectsRepository)
            )
            can_really_save = await projects_repository.is_node_present_in_workbench(
                project_id=scheduler_data.project_id, node_uuid=scheduler_data.node_uuid
            )

        if can_really_save and scheduler_data.dynamic_sidecar.were_containers_created:
            dynamic_sidecar_client = get_dynamic_sidecar_client(app)

            logger.info("Calling into dynamic-sidecar to save: state and output ports")
            try:
                tasks = [
                    service_push_outputs(
                        app, scheduler_data.node_uuid, dynamic_sidecar_client
                    )
                ]

                # When enabled no longer uploads state via nodeports
                # It uses rclone mounted volumes for this task.
                if not app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED:
                    tasks.append(
                        service_save_state(
                            app, scheduler_data.node_uuid, dynamic_sidecar_client
                        )
                    )

                await logged_gather(*tasks, max_concurrency=2)
                scheduler_data.dynamic_sidecar.were_state_and_outputs_saved = True

                logger.info("dynamic-sidecar saved: state and output ports")
            except (BaseClientHTTPError, TaskClientResultError) as e:
                logger.error(
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
                raise e

    if dynamic_sidecar_settings.DYNAMIC_SIDECAR_DOCKER_NODE_RESOURCE_LIMITS_ENABLED:
        node_rights_manager = NodeRightsManager.instance(app)
        assert scheduler_data.dynamic_sidecar.docker_node_id  # nosec
        try:
            async with node_rights_manager.acquire(
                scheduler_data.dynamic_sidecar.docker_node_id,
                resource_name=RESOURCE_STATE_AND_INPUTS,
            ):
                await _remove_containers_save_state_and_outputs()
        except NodeRightsAcquireError:
            # Next observation cycle, the service will try again
            logger.debug(
                "Skip saving service state for %s. Docker node %s is busy. Will try later.",
                scheduler_data.node_uuid,
                scheduler_data.dynamic_sidecar.docker_node_id,
            )
            return
    else:
        await _remove_containers_save_state_and_outputs()

    await service_remove_sidecar_proxy_docker_networks_and_volumes(
        TaskProgress.create(), app, scheduler_data.node_uuid, dynamic_sidecar_settings
    )

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
    )
    rabbitmq_client: RabbitMQClient = app.state.rabbitmq_client
    await rabbitmq_client.publish(message.channel_name, message.json())


async def attach_project_networks(app: FastAPI, scheduler_data: SchedulerData) -> None:
    logger.debug("Attaching project networks for %s", scheduler_data.service_name)

    dynamic_sidecar_client = get_dynamic_sidecar_client(app)
    dynamic_sidecar_endpoint = scheduler_data.endpoint

    projects_networks_repository: ProjectsNetworksRepository = cast(
        ProjectsNetworksRepository,
        get_repository(app, ProjectsNetworksRepository),
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
            await dynamic_sidecar_client.attach_service_containers_to_project_network(
                dynamic_sidecar_endpoint=dynamic_sidecar_endpoint,
                dynamic_sidecar_network_name=scheduler_data.dynamic_sidecar_network_name,
                project_network=network_name,
                project_id=scheduler_data.project_id,
                network_alias=network_alias,
            )

    scheduler_data.dynamic_sidecar.is_project_network_attached = True


async def wait_for_sidecar_api(app: FastAPI, scheduler_data: SchedulerData) -> None:
    dynamic_sidecar_settings: DynamicSidecarSettings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
    )

    async for attempt in AsyncRetrying(
        stop=stop_after_delay(
            dynamic_sidecar_settings.DYNAMIC_SIDECAR_STARTUP_TIMEOUT_S
        ),
        wait=wait_fixed(1),
        retry_error_cls=EntrypointContainerNotFoundError,
        before_sleep=before_sleep_log(logger, logging.DEBUG),
    ):
        with attempt:
            if not await get_dynamic_sidecar_service_health(
                app, scheduler_data, with_retry=False
            ):
                raise TryAgain()
            scheduler_data.dynamic_sidecar.is_healthy = True


async def prepare_services_environment(
    app: FastAPI, scheduler_data: SchedulerData
) -> None:
    app_settings: AppSettings = app.state.settings
    dynamic_sidecar_client = get_dynamic_sidecar_client(app)
    dynamic_sidecar_endpoint = scheduler_data.endpoint
    dynamic_sidecar_settings: DynamicSidecarSettings = (
        app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
    )

    async def _pull_outputs_and_state():
        tasks = [
            dynamic_sidecar_client.pull_service_output_ports(dynamic_sidecar_endpoint)
        ]
        # When enabled no longer downloads state via nodeports
        # S3 is used to store state paths
        if not app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED:
            tasks.append(
                dynamic_sidecar_client.restore_service_state(dynamic_sidecar_endpoint)
            )

        await logged_gather(*tasks, max_concurrency=2)

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
            simcore_service_labels.dict().get("io.simcore.outputs", "{}")
        ).get("outputs", {})
        logger.debug(
            "Creating dirs from service outputs labels: %s",
            service_outputs_labels,
        )
        await dynamic_sidecar_client.service_outputs_create_dirs(
            dynamic_sidecar_endpoint, service_outputs_labels
        )

        scheduler_data.dynamic_sidecar.is_service_environment_ready = True

    if dynamic_sidecar_settings.DYNAMIC_SIDECAR_DOCKER_NODE_RESOURCE_LIMITS_ENABLED:
        node_rights_manager = NodeRightsManager.instance(app)
        assert scheduler_data.dynamic_sidecar.docker_node_id  # nosec
        try:
            async with node_rights_manager.acquire(
                scheduler_data.dynamic_sidecar.docker_node_id,
                resource_name=RESOURCE_STATE_AND_INPUTS,
            ):
                await _pull_outputs_and_state()
        except NodeRightsAcquireError:
            # Next observation cycle, the service will try again
            logger.debug(
                "Skip saving service state for %s. Docker node %s is busy. Will try later.",
                scheduler_data.node_uuid,
                scheduler_data.dynamic_sidecar.docker_node_id,
            )
            return
    else:
        await _pull_outputs_and_state()
