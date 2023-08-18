# pylint: disable=relative-beyond-top-level

import logging
from typing import Any, Final

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.aiodocker_api import AioDockerServiceSpec
from models_library.projects import ProjectAtDB
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeIDStr
from models_library.rabbitmq_messages import (
    InstrumentationRabbitMessage,
    ProgressRabbitMessageNode,
    ProgressType,
)
from models_library.service_settings_labels import SimcoreServiceSettingsLabel
from models_library.services import RunID
from servicelib.json_serialization import json_dumps
from servicelib.rabbitmq import RabbitMQClient
from simcore_postgres_database.models.comp_tasks import NodeClass

from .....core.settings import DynamicSidecarProxySettings, DynamicSidecarSettings
from .....models.dynamic_services_scheduler import (
    DockerContainerInspect,
    DockerStatus,
    DynamicSidecarStatus,
    NetworkId,
    SchedulerData,
)
from .....utils.db import get_repository
from .....utils.dict_utils import nested_update
from ....catalog import CatalogClient
from ....db.repositories.groups_extra_properties import GroupsExtraPropertiesRepository
from ....db.repositories.projects import ProjectsRepository
from ....director_v0 import DirectorV0Client
from ...api_client import (
    BaseClientHTTPError,
    get_dynamic_sidecar_service_health,
    get_sidecars_client,
)
from ...docker_api import (
    constrain_service_to_node,
    create_network,
    create_service_and_get_id,
    get_dynamic_sidecar_placement,
    get_swarm_network,
    is_dynamic_sidecar_stack_missing,
)
from ...docker_service_specs import (
    extract_service_port_service_settings,
    get_dynamic_proxy_spec,
    get_dynamic_sidecar_spec,
    merge_settings_before_use,
)
from ...errors import UnexpectedContainerStatusError
from ._abc import DynamicSchedulerEvent
from ._events_user_services import create_user_services
from ._events_utils import (
    are_all_user_services_containers_running,
    attach_project_networks,
    attempt_pod_removal_and_data_saving,
    get_director_v0_client,
    parse_containers_inspect,
    prepare_services_environment,
    wait_for_sidecar_api,
)

_logger = logging.getLogger(__name__)

_DYNAMIC_SIDECAR_SERVICE_EXTENDABLE_SPECS: Final[tuple[list[str], ...]] = (
    ["labels"],
    ["task_template", "Resources", "Limits"],
    ["task_template", "Resources", "Reservation", "MemoryBytes"],
    ["task_template", "Resources", "Reservation", "NanoCPUs"],
    ["task_template", "Placement", "Constraints"],
    ["task_template", "ContainerSpec", "Env"],
    ["task_template", "Resources", "Reservation", "GenericResources"],
)

_EXPECTED_STATUSES: set[DockerStatus] = {DockerStatus.created, DockerStatus.running}


class CreateSidecars(DynamicSchedulerEvent):
    """Created the dynamic-sidecar and the proxy."""

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        # the call to is_dynamic_sidecar_stack_missing is expensive
        # if the dynamic sidecar was started skip
        if scheduler_data.dynamic_sidecar.was_dynamic_sidecar_started:
            return False

        return await is_dynamic_sidecar_stack_missing(
            node_uuid=scheduler_data.node_uuid,
            dynamic_sidecar_settings=app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR,
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        # instrumentation
        message = InstrumentationRabbitMessage(
            metrics="service_started",
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

        dynamic_sidecar_settings: DynamicSidecarSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )
        # the dynamic-sidecar should merge all the settings, especially:
        # resources and placement derived from all the images in
        # the provided docker-compose spec
        # also other encodes the env vars to target the proper container
        director_v0_client: DirectorV0Client = get_director_v0_client(app)
        # fetching project form DB and fetching user settings
        projects_repository = get_repository(app, ProjectsRepository)

        project: ProjectAtDB = await projects_repository.get_project(
            project_id=scheduler_data.project_id
        )

        node_uuid_str = NodeIDStr(scheduler_data.node_uuid)
        node: Node | None = project.workbench.get(node_uuid_str)
        boot_options = (
            node.boot_options
            if node is not None and node.boot_options is not None
            else {}
        )
        _logger.info("%s", f"{boot_options=}")

        settings: SimcoreServiceSettingsLabel = await merge_settings_before_use(
            director_v0_client=director_v0_client,
            service_key=scheduler_data.key,
            service_tag=scheduler_data.version,
            service_user_selection_boot_options=boot_options,
            service_resources=scheduler_data.service_resources,
        )

        groups_extra_properties = get_repository(app, GroupsExtraPropertiesRepository)

        assert scheduler_data.product_name is not None  # nosec
        allow_internet_access: bool = await groups_extra_properties.has_internet_access(
            user_id=scheduler_data.user_id, product_name=scheduler_data.product_name
        )

        network_config = {
            "Name": scheduler_data.dynamic_sidecar_network_name,
            "Driver": "overlay",
            "Labels": {
                "io.simcore.zone": f"{dynamic_sidecar_settings.TRAEFIK_SIMCORE_ZONE}",
                "com.simcore.description": f"interactive for node: {scheduler_data.node_uuid}",
                "uuid": f"{scheduler_data.node_uuid}",  # needed for removal when project is closed
            },
            "Attachable": True,
            "Internal": not allow_internet_access,
        }
        dynamic_sidecar_network_id = await create_network(network_config)

        # attach the service to the swarm network dedicated to services
        swarm_network: dict[str, Any] = await get_swarm_network(
            dynamic_sidecar_settings
        )
        swarm_network_id: NetworkId = swarm_network["Id"]
        swarm_network_name: str = swarm_network["Name"]

        # start dynamic-sidecar and run the proxy on the same node

        # Each time a new dynamic-sidecar service is created
        # generate a new `run_id` to avoid resource collisions
        scheduler_data.run_id = RunID.create()

        # WARNING: do NOT log, this structure has secrets in the open
        # If you want to log, please use an obfuscator
        dynamic_sidecar_service_spec_base: AioDockerServiceSpec = get_dynamic_sidecar_spec(
            scheduler_data=scheduler_data,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            swarm_network_id=swarm_network_id,
            settings=settings,
            app_settings=app.state.settings,
            has_quota_support=dynamic_sidecar_settings.DYNAMIC_SIDECAR_ENABLE_VOLUME_LIMITS,
            allow_internet_access=allow_internet_access,
        )

        catalog_client = CatalogClient.instance(app)
        user_specific_service_spec = (
            await catalog_client.get_service_specifications(
                scheduler_data.user_id, scheduler_data.key, scheduler_data.version
            )
        ).get("sidecar", {}) or {}
        user_specific_service_spec = AioDockerServiceSpec.parse_obj(
            user_specific_service_spec
        )
        # NOTE: since user_specific_service_spec follows Docker Service Spec and not Aio
        # we do not use aliases when exporting dynamic_sidecar_service_spec_base
        dynamic_sidecar_service_final_spec = AioDockerServiceSpec.parse_obj(
            nested_update(
                jsonable_encoder(dynamic_sidecar_service_spec_base, exclude_unset=True),
                jsonable_encoder(user_specific_service_spec, exclude_unset=True),
                include=_DYNAMIC_SIDECAR_SERVICE_EXTENDABLE_SPECS,
            )
        )
        rabbit_message = ProgressRabbitMessageNode(
            user_id=scheduler_data.user_id,
            project_id=scheduler_data.project_id,
            node_id=scheduler_data.node_uuid,
            progress_type=ProgressType.SIDECARS_PULLING,
            progress=0,
        )
        await rabbitmq_client.publish(rabbit_message.channel_name, rabbit_message)
        dynamic_sidecar_id = await create_service_and_get_id(
            dynamic_sidecar_service_final_spec
        )
        # constrain service to the same node
        scheduler_data.dynamic_sidecar.docker_node_id = (
            await get_dynamic_sidecar_placement(
                dynamic_sidecar_id, dynamic_sidecar_settings
            )
        )
        rabbit_message = ProgressRabbitMessageNode(
            user_id=scheduler_data.user_id,
            project_id=scheduler_data.project_id,
            node_id=scheduler_data.node_uuid,
            progress_type=ProgressType.SIDECARS_PULLING,
            progress=1,
        )
        await rabbitmq_client.publish(rabbit_message.channel_name, rabbit_message)

        await constrain_service_to_node(
            service_name=scheduler_data.service_name,
            docker_node_id=scheduler_data.dynamic_sidecar.docker_node_id,
        )

        # update service_port and assign it to the status
        # needed by CreateUserServices action
        scheduler_data.service_port = extract_service_port_service_settings(settings)

        proxy_settings: DynamicSidecarProxySettings = (
            dynamic_sidecar_settings.DYNAMIC_SIDECAR_PROXY_SETTINGS
        )
        scheduler_data.proxy_admin_api_port = (
            proxy_settings.DYNAMIC_SIDECAR_CADDY_ADMIN_API_PORT
        )

        dynamic_sidecar_proxy_create_service_params: dict[
            str, Any
        ] = get_dynamic_proxy_spec(
            scheduler_data=scheduler_data,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            dynamic_sidecar_network_id=dynamic_sidecar_network_id,
            swarm_network_id=swarm_network_id,
            swarm_network_name=swarm_network_name,
        )
        _logger.debug(
            "dynamic-sidecar-proxy create_service_params %s",
            json_dumps(dynamic_sidecar_proxy_create_service_params),
        )

        await create_service_and_get_id(dynamic_sidecar_proxy_create_service_params)

        # finally mark services created
        scheduler_data.dynamic_sidecar.dynamic_sidecar_id = dynamic_sidecar_id
        scheduler_data.dynamic_sidecar.dynamic_sidecar_network_id = (
            dynamic_sidecar_network_id
        )
        scheduler_data.dynamic_sidecar.swarm_network_id = swarm_network_id
        scheduler_data.dynamic_sidecar.swarm_network_name = swarm_network_name
        scheduler_data.dynamic_sidecar.was_dynamic_sidecar_started = True


class WaitForSidecarAPI(DynamicSchedulerEvent):
    """
    Waits for the sidecar to start and respond to API calls.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        _ = app
        return (
            scheduler_data.dynamic_sidecar.was_dynamic_sidecar_started
            and not scheduler_data.dynamic_sidecar.is_healthy
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        await wait_for_sidecar_api(app, scheduler_data)


class UpdateHealth(DynamicSchedulerEvent):
    """
    Updates the health of the sidecar.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        _ = app
        return scheduler_data.dynamic_sidecar.was_dynamic_sidecar_started

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        scheduler_data.dynamic_sidecar.is_ready = (
            await get_dynamic_sidecar_service_health(app, scheduler_data)
        )


class GetStatus(DynamicSchedulerEvent):
    """
    Triggered after CreateSidecars.action() runs.
    Requests the dynamic-sidecar for all "self started running containers"
    docker inspect result.
    Parses and stores the result for usage by other components.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        _ = app
        return (
            scheduler_data.dynamic_sidecar.status.current == DynamicSidecarStatus.OK
            and scheduler_data.dynamic_sidecar.is_ready
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        sidecars_client = get_sidecars_client(app, scheduler_data.node_uuid)
        dynamic_sidecar_endpoint = scheduler_data.endpoint
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )
        scheduler_data.dynamic_sidecar.inspect_error_handler.delay_for = (
            dynamic_sidecar_settings.DYNAMIC_SIDECAR_CLIENT_REQUEST_TIMEOUT_S
        )

        try:
            containers_inspect: dict[
                str, Any
            ] = await sidecars_client.containers_inspect(dynamic_sidecar_endpoint)
        except BaseClientHTTPError as e:
            were_service_containers_previously_present = (
                len(scheduler_data.dynamic_sidecar.containers_inspect) > 0
            )
            if were_service_containers_previously_present:
                # Containers disappeared after they were started.
                # for now just mark as error and remove the sidecar

                # NOTE: Network performance can degrade and the sidecar might
                # be temporarily unreachable.
                # Adding a delay between when the error is first seen and when the
                # error is raised to avoid random shutdowns of dynamic-sidecar services.
                scheduler_data.dynamic_sidecar.inspect_error_handler.try_to_raise(e)
            return

        scheduler_data.dynamic_sidecar.inspect_error_handler.else_reset()

        # parse and store data from container
        scheduler_data.dynamic_sidecar.containers_inspect = parse_containers_inspect(
            containers_inspect
        )

        # NOTE: All containers are expected to be either created or running.
        # Extra containers (utilities like forward proxies) can also be present here,
        # these also are expected to be created or running.

        containers_with_error: list[DockerContainerInspect] = [
            container_inspect
            for container_inspect in scheduler_data.dynamic_sidecar.containers_inspect
            if container_inspect.status not in _EXPECTED_STATUSES
        ]

        if len(containers_with_error) > 0:
            raise UnexpectedContainerStatusError(
                containers_with_error=containers_with_error
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
        _ = app
        return (
            scheduler_data.dynamic_sidecar.status.current == DynamicSidecarStatus.OK
            and scheduler_data.dynamic_sidecar.is_ready
            and not scheduler_data.dynamic_sidecar.is_service_environment_ready
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        await prepare_services_environment(app, scheduler_data)


class CreateUserServices(DynamicSchedulerEvent):
    """
    Triggered when the the environment was prepared.
    The docker compose spec for the service is assembled.
    The dynamic-sidecar is asked to start a service for that service spec.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        _ = app
        return (
            scheduler_data.dynamic_sidecar.is_service_environment_ready
            and not scheduler_data.dynamic_sidecar.compose_spec_submitted
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        await create_user_services(app, scheduler_data)


class AttachProjectsNetworks(DynamicSchedulerEvent):
    """
    Triggers after CreateUserServices and when all started containers are running.

    Will attach all started containers to the project network based on what
    is saved in the project_network db entry.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        _ = app
        return (
            scheduler_data.dynamic_sidecar.were_containers_created
            and not scheduler_data.dynamic_sidecar.is_project_network_attached
            and are_all_user_services_containers_running(
                scheduler_data.dynamic_sidecar.containers_inspect
            )
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        await attach_project_networks(app, scheduler_data)


class RemoveUserCreatedServices(DynamicSchedulerEvent):
    """
    Triggered when the service is marked for removal.

    The state of the service will be stored. If dynamic-sidecar
        is not reachable a warning is logged.
    The outputs of the service wil be pushed. If dynamic-sidecar
        is not reachable a warning is logged.
    The dynamic-sidecar together with spawned containers
    and dedicated network will be removed.
    The scheduler will no longer track the service.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        _ = app
        return scheduler_data.dynamic_sidecar.service_removal_state.can_remove

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        await attempt_pod_removal_and_data_saving(app, scheduler_data)


# register all handlers defined in this module here
# A list is essential to guarantee execution order
REGISTERED_EVENTS: list[type[DynamicSchedulerEvent]] = [
    CreateSidecars,
    WaitForSidecarAPI,
    UpdateHealth,
    GetStatus,
    PrepareServicesEnvironment,
    CreateUserServices,
    AttachProjectsNetworks,
    RemoveUserCreatedServices,
]
