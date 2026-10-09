import asyncio
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Final

import arrow
from dask_task_models_library.container_tasks.protocol import ContainerEnvsDict
from dask_task_models_library.resource_constraints import (
    estimate_dask_worker_resources_from_ec2_instance,
)
from models_library.api_schemas_catalog.services import ServiceGet
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.api_schemas_directorv2.services import (
    NodeRequirements,
    ServiceExtras,
)
from models_library.api_schemas_resource_usage_tracker.pricing_plans import RutPricingUnitGet
from models_library.function_services_catalog import iter_service_docker_data
from models_library.projects import NodesDict, ProjectAtDB, ProjectID
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.resource_tracker import (
    HardwareInfo,
    PricingPlanId,
    PricingUnitId,
)
from models_library.service_settings_labels import (
    SimcoreServiceLabels,
)
from models_library.services import (
    ServiceKeyVersion,
    ServiceMetaDataPublished,
)
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    BootMode,
    ServiceResourcesDict,
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

from .....core.errors import (
    ClustersKeeperNotAvailableError,
    EC2InstanceTypeNotFoundError,
)
from .....models.comp_tasks import CompTaskAtDB, Image, NodeSchema
from .....models.pricing import PricingInfo
from .....modules.resource_usage_tracker_client import ResourceUsageTrackerClient
from .....utils.computations import to_node_class
from ....catalog import CatalogClient
from ....comp_scheduler._utils import COMPLETED_STATES
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
    obj: ServiceMetaDataPublished = ServiceGet(**service_details)
    return obj


def _compute_node_requirements(
    node_resources: ServiceResourcesDict,
) -> NodeRequirements:
    node_defined_resources: dict[str, Any] = {}

    for image_data in node_resources.values():
        for resource_name, resource_value in image_data.resources.items():
            node_defined_resources[resource_name] = node_defined_resources.get(resource_name, 0) + min(
                resource_value.limit, resource_value.reservation
            )
    return NodeRequirements(**node_defined_resources)


def _compute_node_boot_mode(node_resources: ServiceResourcesDict) -> BootMode:
    for image_data in node_resources.values():
        return image_data.boot_modes[0]
    msg = "No BootMode"
    raise RuntimeError(msg)


_VALID_ENV_VALUE_NUM_PARTS: Final[int] = 2


def _compute_node_envs(node_labels: SimcoreServiceLabels) -> ContainerEnvsDict:
    node_envs = {}
    for service_setting in node_labels.settings:
        if service_setting.name == "env":
            for complete_env in service_setting.value:
                parts = complete_env.split("=")
                if len(parts) == _VALID_ENV_VALUE_NUM_PARTS:
                    node_envs[parts[0]] = parts[1]

    return node_envs


async def _get_node_infos(
    catalog_client: CatalogClient,
    user_id: UserID,
    product_name: str,
    node: ServiceKeyVersion,
) -> tuple[ServiceMetaDataPublished | None, ServiceExtras | None, SimcoreServiceLabels | None]:
    if to_node_class(node.key) == NodeClass.FRONTEND:
        return (
            _FRONTEND_SERVICES_CATALOG.get(node.key),
            None,
            None,
        )

    result: tuple[ServiceMetaDataPublished, ServiceExtras, SimcoreServiceLabels] = await asyncio.gather(
        _get_service_details(catalog_client, user_id, product_name, node),
        catalog_client.get_service_extras(node.key, node.version),
        catalog_client.get_service_labels(node.key, node.version),
    )
    return result


async def _generate_task_image(
    *,
    catalog_client: CatalogClient,
    user_id: UserID,
    product_name: str,
    node: Node,
    node_resources: ServiceResourcesDict,
    node_extras: ServiceExtras | None,
    node_labels: SimcoreServiceLabels | None,
) -> Image:
    # aggregates node_details and node_extras into Image
    data: dict[str, Any] = {
        "name": node.key,
        "tag": node.version,
    }
    if not node_resources:
        node_resources = await catalog_client.get_service_resources(user_id, node.key, node.version, product_name)

    if node_resources:
        data.update(node_requirements=_compute_node_requirements(node_resources))
        data.update(boot_mode=_compute_node_boot_mode(node_resources))
    if node_labels:
        data.update(envs=_compute_node_envs(node_labels))
    if node_extras and node_extras.container_spec:
        data.update(command=node_extras.container_spec.command)
    return Image(**data)


@dataclass(frozen=True, kw_only=True)
class ProjectNodesSnapshot:
    """`projects_nodes` state read up-front in a short read-only transaction.

    Passed to `generate_tasks_list_from_project` so that no external call (catalog,
    resource-usage-tracker, clusters-keeper) ever runs while a transaction — and therefore
    a row lock — is held. See https://github.com/ITISFoundation/private-issues/issues/669
    """

    required_resources: dict[NodeID, dict[str, Any]]
    pricing_unit_ids: dict[NodeID, tuple[PricingPlanId, PricingUnitId]]


@dataclass(frozen=True, kw_only=True)
class ProjectNodesPendingUpdates:
    """`projects_nodes` writes decided by `generate_tasks_list_from_project`.

    The caller applies them in a single short transaction, ordered by `node_id`.
    """

    required_resources: dict[NodeID, dict[str, Any]] = field(default_factory=dict)
    pricing_unit_ids: dict[NodeID, tuple[PricingPlanId, PricingUnitId]] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class PricingContext:
    """Everything the resource-usage-tracker was asked for, fetched once per distinct argument"""

    node_pricing_unit_ids: dict[NodeID, tuple[PricingPlanId, PricingUnitId]]
    pending_pricing_unit_ids: dict[NodeID, tuple[PricingPlanId, PricingUnitId]]
    pricing_units: dict[tuple[PricingPlanId, PricingUnitId], RutPricingUnitGet]
    ec2_instance_types: dict[str, EC2InstanceTypeGet]

    def get_pricing_and_hardware_info(self, node_id: NodeID) -> tuple[PricingInfo | None, HardwareInfo]:
        pricing_unit_ids = self.node_pricing_unit_ids.get(node_id)
        pricing_unit_get = self.pricing_units.get(pricing_unit_ids) if pricing_unit_ids else None
        if not pricing_unit_ids or pricing_unit_get is None:
            return None, HardwareInfo(aws_ec2_instances=[])
        return (
            PricingInfo(
                pricing_plan_id=pricing_unit_ids[0],
                pricing_unit_id=pricing_unit_ids[1],
                pricing_unit_cost_id=pricing_unit_get.current_cost_per_unit_id,
                pricing_unit_cost=pricing_unit_get.current_cost_per_unit,
            ),
            HardwareInfo(aws_ec2_instances=pricing_unit_get.specific_info.aws_ec2_instances),
        )


async def _gather_default_pricing_unit_ids(
    rut_client: ResourceUsageTrackerClient,
    *,
    product_name: str,
    missing: list[ServiceKeyVersion],
) -> dict[ServiceKeyVersion, tuple[PricingPlanId, PricingUnitId]]:
    """Resource-usage-tracker default pricing unit, once per service key/version"""
    if not missing:
        return {}
    results = await asyncio.gather(
        *(rut_client.get_default_pricing_and_hardware_info(product_name, kv.key, kv.version) for kv in missing)
    )
    return {
        key_version: (pricing_plan_id, pricing_unit_id)
        for key_version, (pricing_plan_id, pricing_unit_id, _, _) in zip(missing, results, strict=True)
    }


async def _gather_pricing_units(
    rut_client: ResourceUsageTrackerClient,
    *,
    product_name: str,
    pricing_unit_ids: list[tuple[PricingPlanId, PricingUnitId]],
) -> dict[tuple[PricingPlanId, PricingUnitId], RutPricingUnitGet]:
    """pricing units fetched once each, concurrently"""
    if not pricing_unit_ids:
        return {}
    results = await asyncio.gather(
        *(
            rut_client.get_pricing_unit(product_name, pricing_plan_id, pricing_unit_id)
            for pricing_plan_id, pricing_unit_id in pricing_unit_ids
        )
    )
    return dict(zip(pricing_unit_ids, results, strict=True))


async def _gather_ec2_instance_types(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    instance_type_names: set[str],
) -> dict[str, EC2InstanceTypeGet]:
    """clusters-keeper instance types, in ONE call for the whole project"""
    if not instance_type_names:
        return {}
    assert rabbitmq_rpc_client  # nosec
    try:
        list_ec2_instance_types: list[EC2InstanceTypeGet] = await get_instance_type_details(
            rabbitmq_rpc_client,
            instance_type_names=instance_type_names,
        )
    except (RemoteMethodNotRegisteredError, RPCServerError, TimeoutError) as exc:
        raise ClustersKeeperNotAvailableError from exc
    return {ec2_instance_type.name: ec2_instance_type for ec2_instance_type in list_ec2_instance_types}


_RAM_SAFE_MARGIN_RATIO: Final[float] = 0.1  # NOTE: machines always have less available RAM than advertised
_CPUS_SAFE_MARGIN: Final[float] = 0.1


async def _gather_pricing_context(
    rut_client: ResourceUsageTrackerClient,
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: str,
    project_nodes: NodesDict,
    wallet_info: WalletInfo | None,
    snapshot: ProjectNodesSnapshot,
) -> PricingContext:
    # frontend services have no pricing plans, therefore no need to call RUT
    nodes_to_price: list[NodeID] = [
        NodeID(node_id)
        for node_id in sorted(project_nodes)
        if wallet_info and to_node_class(project_nodes[node_id].key) != NodeClass.FRONTEND
    ]
    services_missing_pricing_unit: list[ServiceKeyVersion] = sorted(
        {
            ServiceKeyVersion(key=node.key, version=node.version)
            for node_id, node in project_nodes.items()
            if NodeID(node_id) in nodes_to_price and snapshot.pricing_unit_ids.get(NodeID(node_id)) is None
        },
        key=lambda key_version: (key_version.key, key_version.version),
    )
    default_pricing_unit_ids = await _gather_default_pricing_unit_ids(
        rut_client,
        product_name=product_name,
        missing=services_missing_pricing_unit,
    )

    # NOTE: this is some kind of lazy insertion of the pricing unit: the projects_node is
    # already in at this time, and not in sync with the hardware info. It will need to move
    # away and be in sync.
    pending_pricing_unit_ids: dict[NodeID, tuple[PricingPlanId, PricingUnitId]] = {}
    node_pricing_unit_ids: dict[NodeID, tuple[PricingPlanId, PricingUnitId]] = {}
    for node_id in nodes_to_price:
        node = project_nodes[f"{node_id}"]
        pricing_unit_ids = (
            snapshot.pricing_unit_ids.get(node_id)
            or default_pricing_unit_ids[ServiceKeyVersion(key=node.key, version=node.version)]
        )
        if node_id not in snapshot.pricing_unit_ids:
            pending_pricing_unit_ids[node_id] = pricing_unit_ids
        node_pricing_unit_ids[node_id] = pricing_unit_ids

    pricing_unit_ids_to_fetch = sorted(set(node_pricing_unit_ids.values()))
    pricing_units = await _gather_pricing_units(
        rut_client,
        product_name=product_name,
        pricing_unit_ids=pricing_unit_ids_to_fetch,
    )
    ec2_instance_types = await _gather_ec2_instance_types(
        rabbitmq_rpc_client,
        instance_type_names={
            aws_ec2_instance
            for pricing_unit in pricing_units.values()
            for aws_ec2_instance in pricing_unit.specific_info.aws_ec2_instances
        },
    )
    return PricingContext(
        node_pricing_unit_ids=node_pricing_unit_ids,
        pending_pricing_unit_ids=pending_pricing_unit_ids,
        pricing_units=pricing_units,
        ec2_instance_types=ec2_instance_types,
    )


def _compute_hardware_adjusted_resources(
    *,
    project_id: ProjectID,
    node_id: NodeID,
    node_resources: ServiceResourcesDict,
    hardware_info: HardwareInfo,
    ec2_instance_types: dict[str, EC2InstanceTypeGet],
) -> tuple[dict[str, Any], ServiceResourcesDict] | None:
    """Resources pinned to the selected machine, or None when nothing has to be written.

    NOTE: with the current implementation, there is no use to get the instance past the first one
    """
    if not hardware_info.aws_ec2_instances:
        return None

    selected_ec2_instance_type = ec2_instance_types.get(hardware_info.aws_ec2_instances[0])
    if selected_ec2_instance_type is None:
        raise EC2InstanceTypeNotFoundError(
            ec2_instance_types=f"{set(hardware_info.aws_ec2_instances)}",
            node_id=f"{node_id}",
            project_id=f"{project_id}",
        )

    if DEFAULT_SINGLE_SERVICE_NAME not in node_resources:
        _logger.warning("Services resource override not implemented yet for multi-container services!!!")
        return None

    # NOTE: we keep a safe margin with the RAM as the dask-sidecar "sees"
    # less memory than the machine theoretical amount
    adjusted_resources: ServiceResourcesDict = {
        name: resources.model_copy(deep=True) for name, resources in node_resources.items()
    }
    adjusted_cpus, adjusted_ram = estimate_dask_worker_resources_from_ec2_instance(
        float(selected_ec2_instance_type.cpus),
        selected_ec2_instance_type.ram,
    )
    adjusted_resources[DEFAULT_SINGLE_SERVICE_NAME].resources["CPU"].set_value(adjusted_cpus)
    adjusted_resources[DEFAULT_SINGLE_SERVICE_NAME].resources["RAM"].set_value(adjusted_ram)

    return (
        TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).dump_python(
            adjusted_resources,
            mode="json",
        ),
        adjusted_resources,
    )


def _resolve_node_resources(
    *,
    project_id: ProjectID,
    node_id: NodeID,
    snapshot: ProjectNodesSnapshot,
    hardware_info: HardwareInfo,
    ec2_instance_types: dict[str, EC2InstanceTypeGet],
) -> tuple[ServiceResourcesDict, dict[str, Any] | None]:
    """the resources to run the node with, and the `projects_nodes` update to write (if any)"""
    current_resources: dict[str, Any] = snapshot.required_resources.get(node_id) or {}
    node_resources = TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).validate_python(current_resources)
    adjusted = _compute_hardware_adjusted_resources(
        project_id=project_id,
        node_id=node_id,
        node_resources=node_resources,
        hardware_info=hardware_info,
        ec2_instance_types=ec2_instance_types,
    )
    if adjusted is None:
        return node_resources, None
    dumped_resources, adjusted_resources = adjusted
    # NOTE: writing the same value again would take a row lock for nothing
    return adjusted_resources, dumped_resources if dumped_resources != current_resources else None


async def generate_tasks_list_from_project(
    *,
    project: ProjectAtDB,
    project_nodes: NodesDict,
    catalog_client: CatalogClient,
    published_nodes: list[NodeID],
    user_id: UserID,
    product_name: str,
    rut_client: ResourceUsageTrackerClient,
    wallet_info: WalletInfo | None,
    rabbitmq_rpc_client: RabbitMQRPCClient,
    snapshot: ProjectNodesSnapshot,
) -> tuple[list[CompTaskAtDB], bool, ProjectNodesPendingUpdates]:
    """Returns (tasks_list, insufficient_credits, projects_nodes_updates).

    If insufficient_credits is True, affected published nodes were set to ABORTED.

    NOTE: this function performs **no** database write and takes no connection: every
    external call (catalog, resource-usage-tracker, clusters-keeper) is gathered here,
    outside of any transaction, and the resulting `projects_nodes` updates are returned to
    the caller to be applied in one short transaction. Holding row locks across these calls
    caused the production deadlock of
    https://github.com/ITISFoundation/private-issues/issues/669
    """
    list_comp_tasks = []
    insufficient_credits = False

    unique_service_key_versions: list[ServiceKeyVersion] = sorted(
        {
            ServiceKeyVersion(key=node.key, version=node.version)  # the service key version is frozen
            for node in project_nodes.values()
        },
        key=lambda key_version: (key_version.key, key_version.version),
    )

    key_version_to_node_infos = dict(
        zip(
            unique_service_key_versions,
            await asyncio.gather(
                *(
                    _get_node_infos(
                        catalog_client,
                        user_id,
                        product_name,
                        key_version,
                    )
                    for key_version in unique_service_key_versions
                )
            ),
            strict=True,
        )
    )

    pricing_context = await _gather_pricing_context(
        rut_client,
        rabbitmq_rpc_client,
        product_name=product_name,
        project_nodes=project_nodes,
        wallet_info=wallet_info,
        snapshot=snapshot,
    )

    pending_required_resources: dict[NodeID, dict[str, Any]] = {}

    for internal_id, node_id in enumerate(sorted(project_nodes), 1):
        node: Node = project_nodes[node_id]
        node_key_version = ServiceKeyVersion(key=node.key, version=node.version)
        node_details, node_extras, node_labels = key_version_to_node_infos.get(
            node_key_version,
            (None, None, None),
        )

        if not node_details:
            _logger.warning(
                "Skipping node %s (%s:%s) in project %s: "
                "service not found in catalog. No comp_tasks entry will be created.",
                node_id,
                node.key,
                node.version,
                project.uuid,
            )
            continue

        assert node.state is not None  # nosec
        task_state = node.state.current_status
        task_progress = None
        if task_state in COMPLETED_STATES:
            task_progress = node.state.progress
        if NodeID(node_id) in published_nodes and to_node_class(node.key) == NodeClass.COMPUTATIONAL:
            task_state = RunningState.PUBLISHED

        pricing_info, hardware_info = pricing_context.get_pricing_and_hardware_info(NodeID(node_id))

        # Check credits for published nodes with non-zero cost
        if (
            task_state == RunningState.PUBLISHED
            and wallet_info
            and pricing_info
            and pricing_info.pricing_unit_cost > Decimal(0)
            and wallet_info.wallet_credit_amount <= ZERO_CREDITS
        ):
            insufficient_credits = True

        node_resources, pending_resources = _resolve_node_resources(
            project_id=project.uuid,
            node_id=NodeID(node_id),
            snapshot=snapshot,
            hardware_info=hardware_info,
            ec2_instance_types=pricing_context.ec2_instance_types,
        )
        if pending_resources is not None:
            pending_required_resources[NodeID(node_id)] = pending_resources

        image = await _generate_task_image(
            catalog_client=catalog_client,
            user_id=user_id,
            product_name=product_name,
            node=node,
            node_resources=node_resources,
            node_extras=node_extras,
            node_labels=node_labels,
        )

        task_db = CompTaskAtDB(
            project_id=project.uuid,
            node_id=NodeID(node_id),
            schema=NodeSchema(
                **node_details.model_dump(exclude_unset=True, by_alias=True, include={"inputs", "outputs"})
            ),
            inputs=node.inputs,
            outputs=node.outputs,
            image=image,
            state=task_state,
            internal_id=internal_id,
            node_class=to_node_class(node.key),
            progress=task_progress,
            last_heartbeat=None,
            created=arrow.utcnow().datetime,
            modified=arrow.utcnow().datetime,
            pricing_info=(pricing_info.model_dump(exclude={"pricing_unit_cost"}) if pricing_info else None),
            hardware_info=hardware_info,
        )

        list_comp_tasks.append(task_db)

    # If any published node had insufficient credits, abort ALL published nodes
    if insufficient_credits:
        for task in list_comp_tasks:
            if task.state == RunningState.PUBLISHED:
                task.state = RunningState.ABORTED

    return (
        list_comp_tasks,
        insufficient_credits,
        ProjectNodesPendingUpdates(
            required_resources=pending_required_resources,
            pricing_unit_ids=pricing_context.pending_pricing_unit_ids,
        ),
    )
