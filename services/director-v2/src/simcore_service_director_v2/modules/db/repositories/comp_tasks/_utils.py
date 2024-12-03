import asyncio
import logging
from decimal import Decimal
from typing import Any, Final, cast

import aiopg.sa
import arrow
from dask_task_models_library.container_tasks.protocol import ContainerEnvsDict
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.api_schemas_directorv2.services import (
    NodeRequirements,
    ServiceExtras,
)
from models_library.function_services_catalog import iter_service_docker_data
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.resource_tracker import HardwareInfo
from models_library.service_settings_labels import (
    SimcoreServiceLabels,
    SimcoreServiceSettingsLabel,
)
from models_library.services import (
    ServiceKey,
    ServiceKeyVersion,
    ServiceMetaDataPublished,
    ServiceVersion,
)
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    BootMode,
    ImageResources,
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.users import UserID
from models_library.wallets import ZERO_CREDITS, WalletInfo
from pydantic import TypeAdapter
from servicelib.rabbitmq import (
    RabbitMQRPCClient,
    RemoteMethodNotRegisteredError,
    RPCServerError,
)
from servicelib.rabbitmq.rpc_interfaces.clusters_keeper.ec2_instances import (
    get_instance_type_details,
)
from simcore_postgres_database.utils_projects_nodes import ProjectNodesRepo

from .....core.errors import (
    ClustersKeeperNotAvailableError,
    ConfigurationError,
    WalletNotEnoughCreditsError,
)
from .....models.comp_tasks import CompTaskAtDB, Image, NodeSchema
from .....models.pricing import PricingInfo
from .....modules.resource_usage_tracker_client import ResourceUsageTrackerClient
from .....utils.computations import to_node_class
from ....catalog import CatalogClient
from ....comp_scheduler._utils import COMPLETED_STATES
from ....director_v0 import DirectorV0Client
from ...tables import NodeClass

_logger = logging.getLogger(__name__)

#
# This is a catalog of front-end services that are translated as tasks
#
# The evaluation of this task is already done in the front-end
# The front-end sets the outputs in the node payload and therefore
# no evaluation is expected in the backend.
#
# Examples are nodes like file-picker or parameter/*
#
_FRONTEND_SERVICES_CATALOG: dict[str, ServiceMetaDataPublished] = {
    meta.key: meta for meta in iter_service_docker_data()
}


async def _get_service_details(
    catalog_client: CatalogClient,
    user_id: UserID,
    product_name: str,
    node: ServiceKeyVersion,
) -> ServiceMetaDataPublished:
    service_details = await catalog_client.get_service(
        user_id,
        node.key,
        node.version,
        product_name,
    )
    obj: ServiceMetaDataPublished = ServiceMetaDataPublished(**service_details)
    return obj


def _compute_node_requirements(
    node_resources: ServiceResourcesDict,
) -> NodeRequirements:
    node_defined_resources: dict[str, Any] = {}

    for image_data in node_resources.values():
        for resource_name, resource_value in image_data.resources.items():
            node_defined_resources[resource_name] = node_defined_resources.get(
                resource_name, 0
            ) + min(resource_value.limit, resource_value.reservation)
    return NodeRequirements(**node_defined_resources)


def _compute_node_boot_mode(node_resources: ServiceResourcesDict) -> BootMode:
    for image_data in node_resources.values():
        return image_data.boot_modes[0]
    msg = "No BootMode"
    raise RuntimeError(msg)


_VALID_ENV_VALUE_NUM_PARTS: Final[int] = 2


def _compute_node_envs(node_labels: SimcoreServiceLabels) -> ContainerEnvsDict:
    node_envs = {}
    for service_setting in cast(SimcoreServiceSettingsLabel, node_labels.settings):
        if service_setting.name == "env":
            for complete_env in service_setting.value:
                parts = complete_env.split("=")
                if len(parts) == _VALID_ENV_VALUE_NUM_PARTS:
                    node_envs[parts[0]] = parts[1]

    return node_envs


async def _get_node_infos(
    catalog_client: CatalogClient,
    director_client: DirectorV0Client,
    user_id: UserID,
    product_name: str,
    node: ServiceKeyVersion,
) -> tuple[
    ServiceMetaDataPublished | None, ServiceExtras | None, SimcoreServiceLabels | None
]:
    if to_node_class(node.key) == NodeClass.FRONTEND:
        return (
            _FRONTEND_SERVICES_CATALOG.get(node.key, None),
            None,
            None,
        )

    result: tuple[
        ServiceMetaDataPublished, ServiceExtras, SimcoreServiceLabels
    ] = await asyncio.gather(
        _get_service_details(catalog_client, user_id, product_name, node),
        director_client.get_service_extras(node.key, node.version),
        director_client.get_service_labels(node),
    )
    return result


async def _generate_task_image(
    *,
    catalog_client: CatalogClient,
    connection: aiopg.sa.connection.SAConnection,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    node: Node,
    node_extras: ServiceExtras | None,
    node_labels: SimcoreServiceLabels | None,
) -> Image:
    # aggregates node_details and node_extras into Image
    data: dict[str, Any] = {
        "name": node.key,
        "tag": node.version,
    }
    project_nodes_repo = ProjectNodesRepo(project_uuid=project_id)
    project_node = await project_nodes_repo.get(connection, node_id=node_id)
    node_resources = TypeAdapter(ServiceResourcesDict).validate_python(
        project_node.required_resources
    )
    if not node_resources:
        node_resources = await catalog_client.get_service_resources(
            user_id, node.key, node.version
        )

    if node_resources:
        data.update(node_requirements=_compute_node_requirements(node_resources))
        data.update(boot_mode=_compute_node_boot_mode(node_resources))
    if node_labels:
        data.update(envs=_compute_node_envs(node_labels))
    if node_extras and node_extras.container_spec:
        data.update(command=node_extras.container_spec.command)
    return Image(**data)


async def _get_pricing_and_hardware_infos(
    connection: aiopg.sa.connection.SAConnection,
    rut_client: ResourceUsageTrackerClient,
    *,
    is_wallet: bool,
    project_id: ProjectID,
    node_id: NodeID,
    product_name: str,
    node_key: ServiceKey,
    node_version: ServiceVersion,
) -> tuple[PricingInfo | None, HardwareInfo]:
    if not is_wallet or (to_node_class(node_key) == NodeClass.FRONTEND):
        # NOTE: frontend services have no pricing plans, therefore no need to call RUT
        return None, HardwareInfo(aws_ec2_instances=[])
    project_nodes_repo = ProjectNodesRepo(project_uuid=project_id)
    output = await project_nodes_repo.get_project_node_pricing_unit_id(
        connection, node_uuid=node_id
    )
    # NOTE: this is some kind of lazy insertion of the pricing unit
    # the projects_nodes is already in at this time, and not in sync with the hardware info
    # this will need to move away and be in sync.
    if output:
        pricing_plan_id, pricing_unit_id = output
    else:
        (
            pricing_plan_id,
            pricing_unit_id,
            _,
            _,
        ) = await rut_client.get_default_pricing_and_hardware_info(
            product_name, node_key, node_version
        )
        await project_nodes_repo.connect_pricing_unit_to_project_node(
            connection,
            node_uuid=node_id,
            pricing_plan_id=pricing_plan_id,
            pricing_unit_id=pricing_unit_id,
        )

    pricing_unit_get = await rut_client.get_pricing_unit(
        product_name, pricing_plan_id, pricing_unit_id
    )
    pricing_unit_cost_id = pricing_unit_get.current_cost_per_unit_id
    aws_ec2_instances = pricing_unit_get.specific_info.aws_ec2_instances

    pricing_info = PricingInfo(
        pricing_plan_id=pricing_plan_id,
        pricing_unit_id=pricing_unit_id,
        pricing_unit_cost_id=pricing_unit_cost_id,
        pricing_unit_cost=pricing_unit_get.current_cost_per_unit,
    )
    hardware_info = HardwareInfo(aws_ec2_instances=aws_ec2_instances)
    return pricing_info, hardware_info


_RAM_SAFE_MARGIN_RATIO: Final[
    float
] = 0.1  # NOTE: machines always have less available RAM than advertised
_CPUS_SAFE_MARGIN: Final[float] = 0.1


async def _update_project_node_resources_from_hardware_info(
    connection: aiopg.sa.connection.SAConnection,
    *,
    is_wallet: bool,
    project_id: ProjectID,
    node_id: NodeID,
    hardware_info: HardwareInfo,
    rabbitmq_rpc_client: RabbitMQRPCClient,
) -> None:
    if not is_wallet:
        return
    if not hardware_info.aws_ec2_instances:
        return
    try:
        unordered_list_ec2_instance_types: list[
            EC2InstanceTypeGet
        ] = await get_instance_type_details(
            rabbitmq_rpc_client,
            instance_type_names=set(hardware_info.aws_ec2_instances),
        )

        assert unordered_list_ec2_instance_types  # nosec

        # NOTE: with the current implementation, there is no use to get the instance past the first one
        def _by_type_name(ec2: EC2InstanceTypeGet) -> bool:
            return bool(ec2.name == hardware_info.aws_ec2_instances[0])

        selected_ec2_instance_type = next(
            iter(filter(_by_type_name, unordered_list_ec2_instance_types))
        )

        # now update the project node required resources
        # NOTE: we keep a safe margin with the RAM as the dask-sidecar "sees"
        # less memory than the machine theoretical amount
        project_nodes_repo = ProjectNodesRepo(project_uuid=project_id)
        node = await project_nodes_repo.get(connection, node_id=node_id)
        node_resources = TypeAdapter(ServiceResourcesDict).validate_python(
            node.required_resources
        )
        if DEFAULT_SINGLE_SERVICE_NAME in node_resources:
            image_resources: ImageResources = node_resources[
                DEFAULT_SINGLE_SERVICE_NAME
            ]
            image_resources.resources["CPU"].set_value(
                float(selected_ec2_instance_type.cpus) - _CPUS_SAFE_MARGIN
            )
            image_resources.resources["RAM"].set_value(
                int(
                    selected_ec2_instance_type.ram
                    - _RAM_SAFE_MARGIN_RATIO * selected_ec2_instance_type.ram
                )
            )

            await project_nodes_repo.update(
                connection,
                node_id=node_id,
                required_resources=ServiceResourcesDictHelpers.create_jsonable(
                    node_resources
                ),
            )
        else:
            _logger.warning(
                "Services resource override not implemented yet for multi-container services!!!"
            )
    except StopIteration as exc:
        msg = (
            f"invalid EC2 type name selected {set(hardware_info.aws_ec2_instances)}."
            " TIP: adjust product configuration"
        )
        raise ConfigurationError(msg=msg) from exc
    except (
        RemoteMethodNotRegisteredError,
        RPCServerError,
        TimeoutError,
    ) as exc:
        raise ClustersKeeperNotAvailableError from exc


async def generate_tasks_list_from_project(
    *,
    project: ProjectAtDB,
    catalog_client: CatalogClient,
    director_client: DirectorV0Client,
    published_nodes: list[NodeID],
    user_id: UserID,
    product_name: str,
    connection: aiopg.sa.connection.SAConnection,
    rut_client: ResourceUsageTrackerClient,
    wallet_info: WalletInfo | None,
    rabbitmq_rpc_client: RabbitMQRPCClient,
) -> list[CompTaskAtDB]:
    list_comp_tasks = []

    unique_service_key_versions: set[ServiceKeyVersion] = {
        ServiceKeyVersion(
            key=node.key, version=node.version
        )  # the service key version is frozen
        for node in project.workbench.values()
    }

    key_version_to_node_infos = {
        key_version: await _get_node_infos(
            catalog_client,
            director_client,
            user_id,
            product_name,
            key_version,
        )
        for key_version in unique_service_key_versions
    }

    for internal_id, node_id in enumerate(project.workbench, 1):
        node: Node = project.workbench[node_id]
        node_key_version = ServiceKeyVersion(key=node.key, version=node.version)
        node_details, node_extras, node_labels = key_version_to_node_infos.get(
            node_key_version,
            (None, None, None),
        )

        if not node_details:
            continue

        assert node.state is not None  # nosec
        task_state = node.state.current_status
        task_progress = None
        if task_state in COMPLETED_STATES:
            task_progress = node.state.progress
        if (
            NodeID(node_id) in published_nodes
            and to_node_class(node.key) == NodeClass.COMPUTATIONAL
        ):
            task_state = RunningState.PUBLISHED

        pricing_info, hardware_info = await _get_pricing_and_hardware_infos(
            connection,
            rut_client,
            is_wallet=bool(wallet_info),
            project_id=project.uuid,
            node_id=NodeID(node_id),
            product_name=product_name,
            node_key=node.key,
            node_version=node.version,
        )
        # Check for zero credits (if pricing unit is greater than 0).
        if (
            wallet_info
            and pricing_info
            and pricing_info.pricing_unit_cost > Decimal(0)
            and wallet_info.wallet_credit_amount <= ZERO_CREDITS
        ):
            raise WalletNotEnoughCreditsError(
                wallet_name=wallet_info.wallet_name,
                wallet_credit_amount=wallet_info.wallet_credit_amount,
            )

        assert rabbitmq_rpc_client  # nosec
        await _update_project_node_resources_from_hardware_info(
            connection,
            is_wallet=bool(wallet_info),
            project_id=project.uuid,
            node_id=NodeID(node_id),
            hardware_info=hardware_info,
            rabbitmq_rpc_client=rabbitmq_rpc_client,
        )

        image = await _generate_task_image(
            catalog_client=catalog_client,
            connection=connection,
            user_id=user_id,
            project_id=project.uuid,
            node_id=NodeID(node_id),
            node=node,
            node_extras=node_extras,
            node_labels=node_labels,
        )

        task_db = CompTaskAtDB(
            project_id=project.uuid,
            node_id=NodeID(node_id),
            schema=NodeSchema(
                **node_details.model_dump(
                    exclude_unset=True, by_alias=True, include={"inputs", "outputs"}
                )
            ),
            inputs=node.inputs,
            outputs=node.outputs,
            image=image,
            submit=arrow.utcnow().datetime,
            state=task_state,
            internal_id=internal_id,
            node_class=to_node_class(node.key),
            progress=task_progress,
            last_heartbeat=None,
            created=arrow.utcnow().datetime,
            modified=arrow.utcnow().datetime,
            pricing_info=(
                pricing_info.model_dump(exclude={"pricing_unit_cost"})
                if pricing_info
                else None
            ),
            hardware_info=hardware_info,
        )

        list_comp_tasks.append(task_db)
    return list_comp_tasks
