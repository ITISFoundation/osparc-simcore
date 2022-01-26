import json
import logging
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Type

import httpx
from fastapi import FastAPI
from models_library.projects import ProjectAtDB
from models_library.projects_nodes import Node
from models_library.service_settings_labels import (
    SimcoreServiceLabels,
    SimcoreServiceSettingsLabel,
)
from models_library.services import ServiceKeyVersion
from servicelib.json_serialization import json_dumps
from servicelib.utils import logged_gather
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_exponential, wait_fixed

from ....api.dependencies.database import get_base_repository
from ....core.settings import AppSettings, DynamicSidecarSettings
from ....modules.db.repositories import BaseRepository
from ....models.schemas.dynamic_services import (
    DockerContainerInspect,
    DynamicSidecarStatus,
    SchedulerData,
)
from ....modules.director_v0 import DirectorV0Client
from ...db.repositories.projects import ProjectsRepository
from ..client_api import DynamicSidecarClient, get_dynamic_sidecar_client
from ..docker_api import (
    create_network,
    create_service_and_get_id,
    get_node_id_from_task_for_service,
    get_swarm_network,
    is_dynamic_sidecar_missing,
    remove_dynamic_sidecar_network,
    remove_dynamic_sidecar_stack,
    remove_dynamic_sidecar_volumes,
)
from ..docker_compose_specs import assemble_spec
from ..docker_service_specs import (
    extract_service_port_from_compose_start_spec,
    get_dynamic_proxy_spec,
    get_dynamic_sidecar_spec,
    merge_settings_before_use,
)
from ..errors import (
    DynamicSidecarUnexpectedResponseStatus,
    EntrypointContainerNotFoundError,
    GenericDockerError,
)
from .abc import DynamicSchedulerEvent
from .events_utils import disabled_directory_watcher


logger = logging.getLogger(__name__)


def _fetch_repo_outside_of_request(
    app: FastAPI, repo_type: Type[BaseRepository]
) -> BaseRepository:
    return get_base_repository(engine=app.state.engine, repo_type=repo_type)


def _get_director_v0_client(app: FastAPI) -> DirectorV0Client:
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


class CreateSidecars(DynamicSchedulerEvent):
    """Created the dynamic-sidecar and the proxy."""

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        # the call to is_dynamic_sidecar_missing is expensive
        # if the dynamic sidecar was started skip
        if scheduler_data.dynamic_sidecar.was_dynamic_sidecar_started:
            return False

        return await is_dynamic_sidecar_missing(
            node_uuid=scheduler_data.node_uuid,
            dynamic_sidecar_settings=app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR,
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )
        # the dynamic-sidecar should merge all the settings, especially:
        # resources and placement derived from all the images in
        # the provided docker-compose spec
        # also other encodes the env vars to target the proper container
        director_v0_client: DirectorV0Client = _get_director_v0_client(app)

        # fetching project form DB and fetching user settings
        projects_repository = _fetch_repo_outside_of_request(app, ProjectsRepository)
        project: ProjectAtDB = await projects_repository.get_project(
            project_id=scheduler_data.project_id
        )

        node_uuid_str = str(scheduler_data.node_uuid)
        node: Optional[Node] = project.workbench.get(node_uuid_str)
        boot_options = (
            node.boot_options
            if node is not None and node.boot_options is not None
            else {}
        )
        logger.info("%s", f"{boot_options=}")

        settings: SimcoreServiceSettingsLabel = await merge_settings_before_use(
            director_v0_client=director_v0_client,
            service_key=scheduler_data.key,
            service_tag=scheduler_data.version,
            service_user_selection_boot_options=boot_options,
        )

        # these configuration should guarantee 245 address network
        network_config = {
            "Name": scheduler_data.dynamic_sidecar_network_name,
            "Driver": "overlay",
            "Labels": {
                "io.simcore.zone": f"{dynamic_sidecar_settings.TRAEFIK_SIMCORE_ZONE}",
                "com.simcore.description": f"interactive for node: {scheduler_data.node_uuid}",
                "uuid": f"{scheduler_data.node_uuid}",  # needed for removal when project is closed
            },
            "Attachable": True,
            "Internal": False,
        }
        dynamic_sidecar_network_id = await create_network(network_config)

        # attach the service to the swarm network dedicated to services
        swarm_network: Dict[str, Any] = await get_swarm_network(
            dynamic_sidecar_settings
        )
        swarm_network_id: str = swarm_network["Id"]
        swarm_network_name: str = swarm_network["Name"]

        # start dynamic-sidecar and run the proxy on the same node
        dynamic_sidecar_create_service_params = get_dynamic_sidecar_spec(
            scheduler_data=scheduler_data,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            dynamic_sidecar_network_id=dynamic_sidecar_network_id,
            swarm_network_id=swarm_network_id,
            settings=settings,
            app_settings=app.state.settings,
        )
        logger.debug(
            "dynamic-sidecar create_service_params %s",
            json_dumps(dynamic_sidecar_create_service_params),
        )

        dynamic_sidecar_id = await create_service_and_get_id(
            dynamic_sidecar_create_service_params
        )

        # update service_port and assing it to the status
        # needed by CreateUserServices action
        scheduler_data.service_port = extract_service_port_from_compose_start_spec(
            dynamic_sidecar_create_service_params
        )

        # finally mark services created
        scheduler_data.dynamic_sidecar.dynamic_sidecar_id = dynamic_sidecar_id
        scheduler_data.dynamic_sidecar.dynamic_sidecar_network_id = (
            dynamic_sidecar_network_id
        )
        scheduler_data.dynamic_sidecar.swarm_network_id = swarm_network_id
        scheduler_data.dynamic_sidecar.swarm_network_name = swarm_network_name
        scheduler_data.dynamic_sidecar.was_dynamic_sidecar_started = True


class GetStatus(DynamicSchedulerEvent):
    """
    Triggered after CreateSidecars.action() runs.
    Requests the dynamic-sidecar for all "self started running containers"
    docker inspect result.
    Parses and stores the result for usage by other components.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        return (
            scheduler_data.dynamic_sidecar.status.current == DynamicSidecarStatus.OK
            and scheduler_data.dynamic_sidecar.is_available == True
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        dynamic_sidecar_client = get_dynamic_sidecar_client(app)
        dynamic_sidecar_endpoint = scheduler_data.dynamic_sidecar.endpoint

        try:
            containers_inspect: Dict[
                str, Any
            ] = await dynamic_sidecar_client.containers_inspect(
                dynamic_sidecar_endpoint
            )
        except (httpx.HTTPError, DynamicSidecarUnexpectedResponseStatus):
            # After the service creation it takes a bit of time for the container to start
            # If the same message appears in the log multiple times in a row (for the same
            # service) something might be wrong with the service.
            logger.warning(
                "No container present for %s. Usually not an issue.",
                scheduler_data.service_name,
            )
            return

        # parse and store data from container
        scheduler_data.dynamic_sidecar.containers_inspect = parse_containers_inspect(
            containers_inspect
        )


class PrepareServicesEnvironment(DynamicSchedulerEvent):
    """
    Triggered when the dynamic-sidecar is responding to http requests.
    This step runs before CreateUserServices.

    Sets up the environment on the host required by the service.
    - restores service state
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        return (
            scheduler_data.dynamic_sidecar.status.current == DynamicSidecarStatus.OK
            and scheduler_data.dynamic_sidecar.is_available == True
            and scheduler_data.dynamic_sidecar.service_environment_prepared == False
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        app_settings: AppSettings = app.state.settings
        dynamic_sidecar_client = get_dynamic_sidecar_client(app)
        dynamic_sidecar_endpoint = scheduler_data.dynamic_sidecar.endpoint

        async with disabled_directory_watcher(
            dynamic_sidecar_client, dynamic_sidecar_endpoint
        ):
            tasks = [
                dynamic_sidecar_client.service_pull_output_ports(
                    dynamic_sidecar_endpoint
                )
            ]
            # When enabled no longer downloads state via nodeports
            # S3 is used to store state paths
            if not app_settings.DIRECTOR_V2_DEV_FEATURES_ENABLED:
                tasks.append(
                    dynamic_sidecar_client.service_restore_state(
                        dynamic_sidecar_endpoint
                    )
                )
            await logged_gather(*tasks)

            # inside this directory create the missing dirs, fetch those form the labels
            director_v0_client: DirectorV0Client = _get_director_v0_client(app)
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
                "Creating dirs from service outputs labels: %s", service_outputs_labels
            )
            await dynamic_sidecar_client.service_outputs_create_dirs(
                dynamic_sidecar_endpoint, service_outputs_labels
            )

            scheduler_data.dynamic_sidecar.service_environment_prepared = True


class CreateUserServices(DynamicSchedulerEvent):
    """
    Triggered when the the environment was prepared.
    The docker compose spec for the service is assembled.
    The dynamic-sidecar is asked to start a service for that service spec.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        return (
            scheduler_data.dynamic_sidecar.service_environment_prepared
            and scheduler_data.dynamic_sidecar.compose_spec_submitted == False
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        logger.debug(
            "Getting docker compose spec for service %s", scheduler_data.service_name
        )

        dynamic_sidecar_client = get_dynamic_sidecar_client(app)
        dynamic_sidecar_endpoint = scheduler_data.dynamic_sidecar.endpoint

        # Starts dynamic SIDECAR -------------------------------------
        # creates a docker compose spec given the service key and tag
        compose_spec = assemble_spec(
            app=app,
            service_key=scheduler_data.key,
            service_tag=scheduler_data.version,
            paths_mapping=scheduler_data.paths_mapping,
            compose_spec=scheduler_data.compose_spec,
            container_http_entry=scheduler_data.container_http_entry,
            dynamic_sidecar_network_name=scheduler_data.dynamic_sidecar_network_name,
        )

        await dynamic_sidecar_client.start_service_creation(
            dynamic_sidecar_endpoint, compose_spec
        )

        # Starts PROXY -----------------------------------------------
        # The entrypoint container name was now computed
        # continue starting the proxy

        # check values have been set by previous step
        if (
            scheduler_data.dynamic_sidecar.dynamic_sidecar_id is None
            or scheduler_data.dynamic_sidecar.dynamic_sidecar_network_id is None
            or scheduler_data.dynamic_sidecar.swarm_network_id is None
            or scheduler_data.dynamic_sidecar.swarm_network_name is None
        ):
            raise ValueError(
                (
                    "Expected a value for all the following values: "
                    f"{scheduler_data.dynamic_sidecar.dynamic_sidecar_id=} "
                    f"{scheduler_data.dynamic_sidecar.dynamic_sidecar_network_id=} "
                    f"{scheduler_data.dynamic_sidecar.swarm_network_id=} "
                    f"{scheduler_data.dynamic_sidecar.swarm_network_name=}"
                )
            )

        dynamic_sidecar_settings: DynamicSidecarSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )

        async for attempt in AsyncRetrying(
            stop=stop_after_delay(
                dynamic_sidecar_settings.DYNAMIC_SIDECAR_WAIT_FOR_CONTAINERS_TO_START
            ),
            wait=wait_fixed(1),
            retry_error_cls=EntrypointContainerNotFoundError,
            before_sleep=before_sleep_log(logger, logging.WARNING),
        ):
            with attempt:
                if scheduler_data.dynamic_sidecar.service_removal_state.was_removed:
                    # the service was removed while waiting for the operation to finish
                    logger.warning(
                        "Stopping `get_entrypoint_container_name` operation. "
                        "Will no try to start the service."
                    )
                    return

                entrypoint_container = await dynamic_sidecar_client.get_entrypoint_container_name(
                    dynamic_sidecar_endpoint=dynamic_sidecar_endpoint,
                    dynamic_sidecar_network_name=scheduler_data.dynamic_sidecar_network_name,
                )
                logger.info(
                    "Fetched container entrypoint name %s", entrypoint_container
                )

        dynamic_sidecar_node_id = await get_node_id_from_task_for_service(
            scheduler_data.dynamic_sidecar.dynamic_sidecar_id, dynamic_sidecar_settings
        )

        dynamic_sidecar_proxy_create_service_params = get_dynamic_proxy_spec(
            scheduler_data=scheduler_data,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            dynamic_sidecar_network_id=scheduler_data.dynamic_sidecar.dynamic_sidecar_network_id,
            swarm_network_id=scheduler_data.dynamic_sidecar.swarm_network_id,
            swarm_network_name=scheduler_data.dynamic_sidecar.swarm_network_name,
            dynamic_sidecar_node_id=dynamic_sidecar_node_id,
            entrypoint_container_name=entrypoint_container,
            service_port=scheduler_data.service_port,
        )

        logger.debug(
            "dynamic-sidecar-proxy create_service_params %s",
            json_dumps(dynamic_sidecar_proxy_create_service_params),
        )

        # no need for the id any longer
        await create_service_and_get_id(dynamic_sidecar_proxy_create_service_params)
        scheduler_data.dynamic_sidecar.were_services_created = True

        scheduler_data.dynamic_sidecar.was_compose_spec_submitted = True


class RemoveUserCreatedServices(DynamicSchedulerEvent):
    """
    Triggered when the service is marked for removal.

    The state of the service will be stored. If dynamic-sidecar
        is not reachable a warning is logged.
    The outputs of the service wil be pushed. If dynamic-sidecar
        is not reachable a warning is logged.
    The dynamic-sidcar together with spawned containers
    and dedicated network will be removed.
    The scheduler will no longer track the service.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        return scheduler_data.dynamic_sidecar.service_removal_state.can_remove

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        # invoke container cleanup at this point
        dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(app)

        try:
            await dynamic_sidecar_client.begin_service_destruction(
                dynamic_sidecar_endpoint=scheduler_data.dynamic_sidecar.endpoint
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                "Could not contact dynamic-sidecar to begin destruction of %s\n%s",
                scheduler_data.service_name,
                str(e),
            )

        app_settings: AppSettings = app.state.settings
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )

        if scheduler_data.dynamic_sidecar.service_removal_state.can_save:
            dynamic_sidecar_client = get_dynamic_sidecar_client(app)
            dynamic_sidecar_endpoint = scheduler_data.dynamic_sidecar.endpoint

            logger.info(
                "Calling into dynamic-sidecar to save state and pushing data to nodeports"
            )
            try:
                tasks = [
                    dynamic_sidecar_client.service_push_output_ports(
                        dynamic_sidecar_endpoint,
                    )
                ]
                # When enabled no longer uploads state via nodeports
                # S3 is used to store state paths
                if not app_settings.DIRECTOR_V2_DEV_FEATURES_ENABLED:
                    tasks.append(
                        dynamic_sidecar_client.service_save_state(
                            dynamic_sidecar_endpoint,
                        )
                    )
                await logged_gather(*tasks)
                logger.info("Ports data pushed by dynamic-sidecar")
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    (
                        "Could not contact dynamic-sidecar to save service "
                        "state and upload outputs %s\n%s"
                    ),
                    scheduler_data.service_name,
                    str(e),
                )

        # remove the 2 services
        await remove_dynamic_sidecar_stack(
            node_uuid=scheduler_data.node_uuid,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
        )
        # remove network
        await remove_dynamic_sidecar_network(
            scheduler_data.dynamic_sidecar_network_name
        )

        # remove created inputs and outputs volumes
        async for attempt in AsyncRetrying(
            wait=wait_exponential(min=1),
            stop=stop_after_delay(20),
            retry_error_cls=GenericDockerError,
        ):
            with attempt:
                logger.info(
                    "Trying to remove volumes for %s", scheduler_data.service_name
                )
                await remove_dynamic_sidecar_volumes(scheduler_data.node_uuid)

        logger.debug(
            "Removed dynamic-sidecar created services for '%s'",
            scheduler_data.service_name,
        )

        await app.state.dynamic_sidecar_scheduler.finish_service_removal(
            scheduler_data.node_uuid
        )

        scheduler_data.dynamic_sidecar.service_removal_state.mark_removed()


# register all handlers defined in this module here
# A list is essential to guarantee execution order
REGISTERED_EVENTS: List[Type[DynamicSchedulerEvent]] = [
    CreateSidecars,
    GetStatus,
    PrepareServicesEnvironment,
    CreateUserServices,
    RemoveUserCreatedServices,
]
