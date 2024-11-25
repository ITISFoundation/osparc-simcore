# pylint: disable=relative-beyond-top-level

import logging
from typing import Any, Final

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.aiodocker_api import AioDockerServiceSpec
from models_library.progress_bar import ProgressReport
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
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient
from simcore_postgres_database.models.comp_tasks import NodeClass

from .....core.dynamic_services_settings import DynamicServicesSettings
from .....core.dynamic_services_settings.proxy import DynamicSidecarProxySettings
from .....core.dynamic_services_settings.scheduler import (
    DynamicServicesSchedulerSettings,
)
from .....core.dynamic_services_settings.sidecar import (
    DynamicSidecarSettings,
    PlacementSettings,
)
from .....models.dynamic_services_scheduler import NetworkId, SchedulerData
from .....utils.db import get_repository
from .....utils.dict_utils import nested_update
from ....catalog import CatalogClient
from ....db.repositories.groups_extra_properties import GroupsExtraPropertiesRepository
from ....db.repositories.projects import ProjectsRepository
from ....director_v0 import DirectorV0Client
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
from ._abc import DynamicSchedulerEvent
from ._events_utils import get_allow_metrics_collection, get_director_v0_client

_logger = logging.getLogger(__name__)

_DYNAMIC_SIDECAR_SERVICE_EXTENDABLE_SPECS: Final[tuple[list[str], ...]] = (
    ["labels"],
    ["task_template", "container_spec", "env"],
    ["task_template", "placement", "constraints"],
    ["task_template", "resources", "reservation", "generic_resources"],
    ["task_template", "resources", "limits"],
    ["task_template", "resources", "reservation", "memory_bytes"],
    ["task_template", "resources", "reservation", "nano_cp_us"],
)


def _merge_service_base_and_user_specs(
    dynamic_sidecar_service_spec_base: AioDockerServiceSpec,
    user_specific_service_spec: AioDockerServiceSpec,
) -> AioDockerServiceSpec:
    # NOTE: since user_specific_service_spec follows Docker Service Spec and not Aio
    # we do not use aliases when exporting dynamic_sidecar_service_spec_base
    return AioDockerServiceSpec.model_validate(
        nested_update(
            jsonable_encoder(
                dynamic_sidecar_service_spec_base, exclude_unset=True, by_alias=False
            ),
            jsonable_encoder(
                user_specific_service_spec, exclude_unset=True, by_alias=False
            ),
            include=_DYNAMIC_SIDECAR_SERVICE_EXTENDABLE_SPECS,
        )
    )


async def _create_proxy_service(
    app,
    *,
    scheduler_data: SchedulerData,
    dynamic_sidecar_network_id: NetworkId,
    swarm_network_id: NetworkId,
    swarm_network_name: str,
):
    proxy_settings: DynamicSidecarProxySettings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR_PROXY_SETTINGS
    )
    scheduler_data.proxy_admin_api_port = (
        proxy_settings.DYNAMIC_SIDECAR_CADDY_ADMIN_API_PORT
    )

    dynamic_services_settings: DynamicServicesSettings = (
        app.state.settings.DYNAMIC_SERVICES
    )

    dynamic_sidecar_proxy_create_service_params: dict[
        str, Any
    ] = get_dynamic_proxy_spec(
        scheduler_data=scheduler_data,
        dynamic_services_settings=dynamic_services_settings,
        dynamic_sidecar_network_id=dynamic_sidecar_network_id,
        swarm_network_id=swarm_network_id,
        swarm_network_name=swarm_network_name,
    )
    _logger.debug(
        "dynamic-sidecar-proxy create_service_params %s",
        json_dumps(dynamic_sidecar_proxy_create_service_params),
    )

    await create_service_and_get_id(dynamic_sidecar_proxy_create_service_params)


class CreateSidecars(DynamicSchedulerEvent):
    """Created the dynamic-sidecar and the proxy."""

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        # the call to is_dynamic_sidecar_stack_missing is expensive
        # if the dynamic sidecar was started skip
        if scheduler_data.dynamic_sidecar.was_dynamic_sidecar_started:
            return False

        settings: DynamicServicesSchedulerSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
        )
        return await is_dynamic_sidecar_stack_missing(
            node_uuid=scheduler_data.node_uuid,
            swarm_stack_name=settings.SWARM_STACK_NAME,
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
        dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
        )
        dynamic_services_placement_settings: PlacementSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_PLACEMENT_SETTINGS
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
            placement_substitutions=dynamic_services_placement_settings.DIRECTOR_V2_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS,
        )

        groups_extra_properties = get_repository(app, GroupsExtraPropertiesRepository)

        assert scheduler_data.product_name is not None  # nosec

        user_extra_properties = await groups_extra_properties.get_user_extra_properties(
            user_id=scheduler_data.user_id, product_name=scheduler_data.product_name
        )

        network_config = {
            "Name": scheduler_data.dynamic_sidecar_network_name,
            "Driver": "overlay",
            "Labels": {
                "io.simcore.zone": f"{dynamic_services_scheduler_settings.TRAEFIK_SIMCORE_ZONE}",
                "com.simcore.description": f"interactive for node: {scheduler_data.node_uuid}",
                "uuid": f"{scheduler_data.node_uuid}",  # needed for removal when project is closed
            },
            "Attachable": True,
            "Internal": not user_extra_properties.is_internet_enabled,
        }
        dynamic_sidecar_network_id = await create_network(network_config)

        # attach the service to the swarm network dedicated to services
        swarm_network: dict[str, Any] = await get_swarm_network(
            dynamic_services_scheduler_settings.SIMCORE_SERVICES_NETWORK_NAME
        )
        swarm_network_id: NetworkId = swarm_network["Id"]
        swarm_network_name: str = swarm_network["Name"]

        metrics_collection_allowed: bool = await get_allow_metrics_collection(
            app,
            user_id=scheduler_data.user_id,
            product_name=scheduler_data.product_name,
        )

        # start dynamic-sidecar and run the proxy on the same node

        # Each time a new dynamic-sidecar service is created
        # generate a new `run_id` to avoid resource collisions
        scheduler_data.run_id = RunID.create()

        rpc_client: RabbitMQRPCClient = app.state.rabbitmq_rpc_client

        # WARNING: do NOT log, this structure has secrets in the open
        # If you want to log, please use an obfuscator
        dynamic_sidecar_service_spec_base: AioDockerServiceSpec = await get_dynamic_sidecar_spec(
            scheduler_data=scheduler_data,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            dynamic_services_scheduler_settings=dynamic_services_scheduler_settings,
            swarm_network_id=swarm_network_id,
            settings=settings,
            app_settings=app.state.settings,
            hardware_info=scheduler_data.hardware_info,
            has_quota_support=dynamic_services_scheduler_settings.DYNAMIC_SIDECAR_ENABLE_VOLUME_LIMITS,
            metrics_collection_allowed=metrics_collection_allowed,
            user_extra_properties=user_extra_properties,
            rpc_client=rpc_client,
        )

        catalog_client = CatalogClient.instance(app)
        user_specific_service_spec = (
            await catalog_client.get_service_specifications(
                scheduler_data.user_id, scheduler_data.key, scheduler_data.version
            )
        ).get("sidecar", {}) or {}
        user_specific_service_spec = AioDockerServiceSpec.model_validate(
            user_specific_service_spec
        )
        dynamic_sidecar_service_final_spec = _merge_service_base_and_user_specs(
            dynamic_sidecar_service_spec_base, user_specific_service_spec
        )
        rabbit_message = ProgressRabbitMessageNode.model_construct(
            user_id=scheduler_data.user_id,
            project_id=scheduler_data.project_id,
            node_id=scheduler_data.node_uuid,
            progress_type=ProgressType.SIDECARS_PULLING,
            report=ProgressReport(actual_value=0, total=1),
        )
        await rabbitmq_client.publish(rabbit_message.channel_name, rabbit_message)
        dynamic_sidecar_id = await create_service_and_get_id(
            dynamic_sidecar_service_final_spec
        )
        # constrain service to the same node
        scheduler_data.dynamic_sidecar.docker_node_id = (
            await get_dynamic_sidecar_placement(
                dynamic_sidecar_id, dynamic_services_scheduler_settings
            )
        )

        rabbit_message = ProgressRabbitMessageNode.model_construct(
            user_id=scheduler_data.user_id,
            project_id=scheduler_data.project_id,
            node_id=scheduler_data.node_uuid,
            progress_type=ProgressType.SIDECARS_PULLING,
            report=ProgressReport(actual_value=1, total=1),
        )
        await rabbitmq_client.publish(rabbit_message.channel_name, rabbit_message)

        await constrain_service_to_node(
            service_name=scheduler_data.service_name,
            docker_node_id=scheduler_data.dynamic_sidecar.docker_node_id,
        )

        # update service_port and assign it to the status
        # needed by CreateUserServices action
        scheduler_data.service_port = extract_service_port_service_settings(settings)

        await _create_proxy_service(
            app,
            scheduler_data=scheduler_data,
            dynamic_sidecar_network_id=dynamic_sidecar_network_id,
            swarm_network_id=swarm_network_id,
            swarm_network_name=swarm_network_name,
        )

        # finally mark services created
        scheduler_data.dynamic_sidecar.dynamic_sidecar_id = dynamic_sidecar_id
        scheduler_data.dynamic_sidecar.dynamic_sidecar_network_id = (
            dynamic_sidecar_network_id
        )
        scheduler_data.dynamic_sidecar.swarm_network_id = swarm_network_id
        scheduler_data.dynamic_sidecar.swarm_network_name = swarm_network_name
        scheduler_data.dynamic_sidecar.was_dynamic_sidecar_started = True
