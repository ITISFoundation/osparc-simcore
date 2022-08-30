import logging
from collections import deque
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Deque, Dict, Final, List, Optional, Type

from fastapi import FastAPI
from pydantic import AnyHttpUrl
from servicelib.fastapi.long_running_tasks.client import TaskClientResultError
from servicelib.utils import logged_gather

from ....api.dependencies.database import get_base_repository
from ....core.errors import NodeRightsAcquireError
from ....core.settings import AppSettings, DynamicSidecarSettings
from ....models.schemas.dynamic_services.scheduler import (
    DockerContainerInspect,
    DockerStatus,
    SchedulerData,
)
from ...db.repositories import BaseRepository
from ...director_v0 import DirectorV0Client
from ...node_rights import NodeRightsManager, ResourceName
from ..api_client import (
    BaseClientHTTPError,
    DynamicSidecarClient,
    get_dynamic_sidecar_client,
)
from ..docker_api import (
    get_projects_networks_containers,
    remove_dynamic_sidecar_network,
    remove_dynamic_sidecar_stack,
    try_to_remove_network,
)

logger = logging.getLogger(__name__)


# Used to ensure no more that X services per node pull or push data
# Locking is applied when:
# - study is being opened (state and outputs are pulled)
# - study is being closed (state and outputs are saved)
RESOURCE_STATE_AND_INPUTS: Final[ResourceName] = "state_and_inputs"


@asynccontextmanager
async def disabled_directory_watcher(
    dynamic_sidecar_client: DynamicSidecarClient, dynamic_sidecar_endpoint: AnyHttpUrl
) -> AsyncIterator[None]:
    try:
        # disable file system event watcher while writing
        # to the outputs directory to avoid data being pushed
        # via nodeports upon change
        await dynamic_sidecar_client.service_disable_dir_watcher(
            dynamic_sidecar_endpoint
        )
        yield
    finally:
        # enable file system event watcher so data from outputs
        # can be again synced via nodeports upon change
        await dynamic_sidecar_client.service_enable_dir_watcher(
            dynamic_sidecar_endpoint
        )


def fetch_repo_outside_of_request(
    app: FastAPI, repo_type: Type[BaseRepository]
) -> BaseRepository:
    return get_base_repository(engine=app.state.engine, repo_type=repo_type)


def get_director_v0_client(app: FastAPI) -> DirectorV0Client:
    client = DirectorV0Client.instance(app)
    return client


def parse_containers_inspect(
    containers_inspect: Optional[Dict[str, Any]]
) -> List[DockerContainerInspect]:
    results: Deque[DockerContainerInspect] = deque()

    if containers_inspect is None:
        return []

    for container_id in containers_inspect:
        container_inspect_data = containers_inspect[container_id]
        results.append(DockerContainerInspect.from_container(container_inspect_data))
    return list(results)


def all_containers_running(containers_inspect: List[DockerContainerInspect]) -> bool:
    return len(containers_inspect) > 0 and all(
        (x.status == DockerStatus.RUNNING for x in containers_inspect)
    )


async def save_and_remove_user_created_services(
    app: FastAPI, scheduler_data: SchedulerData
) -> None:
    # invoke container cleanup at this point
    app_settings: AppSettings = app.state.settings
    dynamic_sidecar_settings: DynamicSidecarSettings = (
        app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
    )

    async def _remove_containers_save_state_and_outputs() -> None:
        dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(app)
        dynamic_sidecar_endpoint: AnyHttpUrl = scheduler_data.dynamic_sidecar.endpoint

        try:
            await dynamic_sidecar_client.stop_service(dynamic_sidecar_endpoint)
        except (BaseClientHTTPError, TaskClientResultError) as e:
            logger.warning(
                (
                    "Could not remove service containers for "
                    "%s\n%s. Will continue to save the data from the service!"
                ),
                scheduler_data.service_name,
                f"{e}",
            )

        # only try to save the status if :
        # - it is requested to save the state
        # - the dynamic-sidecar has finished booting correctly
        if (
            scheduler_data.dynamic_sidecar.service_removal_state.can_save
            and scheduler_data.dynamic_sidecar.were_containers_created
        ):
            dynamic_sidecar_client = get_dynamic_sidecar_client(app)

            logger.info(
                "Calling into dynamic-sidecar to save state and pushing data to nodeports"
            )
            try:
                tasks = [
                    dynamic_sidecar_client.push_service_output_ports(
                        dynamic_sidecar_endpoint
                    )
                ]

                # When enabled no longer uploads state via nodeports
                # It uses rclone mounted volumes for this task.
                if not app_settings.DIRECTOR_V2_DEV_FEATURES_ENABLED:
                    tasks.append(
                        dynamic_sidecar_client.save_service_state(
                            dynamic_sidecar_endpoint
                        )
                    )

                await logged_gather(*tasks, max_concurrency=2)
                scheduler_data.dynamic_sidecar.was_data_saved_when_closing = True

                logger.info("Ports data pushed by dynamic-sidecar")
            except (BaseClientHTTPError, TaskClientResultError) as e:
                logger.error(
                    (
                        "Could not contact dynamic-sidecar to save service "
                        "state or upload outputs %s\n%s"
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
        assert scheduler_data.docker_node_id  # nosec
        try:
            async with node_rights_manager.acquire(
                scheduler_data.docker_node_id,
                resource_name=RESOURCE_STATE_AND_INPUTS,
            ):
                await _remove_containers_save_state_and_outputs()
        except NodeRightsAcquireError:
            # Next observation cycle, the service will try again
            logger.debug(
                "Skip saving service state for %s. Docker node %s is busy. Will try later.",
                scheduler_data.node_uuid,
                scheduler_data.docker_node_id,
            )
            return
    else:
        await _remove_containers_save_state_and_outputs()

    # remove the 2 services
    await remove_dynamic_sidecar_stack(
        node_uuid=scheduler_data.node_uuid,
        dynamic_sidecar_settings=dynamic_sidecar_settings,
    )
    # remove network
    await remove_dynamic_sidecar_network(scheduler_data.dynamic_sidecar_network_name)


    # NOTE: when adding volume removal, check that:
    # `scheduler_data.dynamic_sidecar.was_data_saved_when_closing` was
    # set to True before removing data otherwise do nothing

    logger.debug(
        "Removed dynamic-sidecar created services for '%s'",
        scheduler_data.service_name,
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

    await app.state.dynamic_sidecar_scheduler.remove_service_from_observation(
        scheduler_data.node_uuid
    )
    scheduler_data.dynamic_sidecar.service_removal_state.mark_removed()
