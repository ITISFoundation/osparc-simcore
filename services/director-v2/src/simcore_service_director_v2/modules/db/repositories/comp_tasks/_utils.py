import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Any, Final

import arrow
from annotated_types import doc
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
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    RutPricingUnitGet,
)
from models_library.function_services_catalog import iter_service_docker_data
from models_library.projects import NodesDict, ProjectAtDB, ProjectID
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.resource_tracker import (
    HardwareInfo,
    PricingPlanAndUnitIdsTuple,
)
from models_library.service_settings_labels import (
    SimcoreServiceLabels,
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
from servicelib.utils import limited_gather
from simcore_postgres_database.utils_projects_nodes import ProjectNodesRepo
from sqlalchemy.ext.asyncio import AsyncConnection

from .....core.errors import (
    ClustersKeeperNotAvailableError,
    EC2InstanceTypeNotFoundError,
    MultiContainerOverrideNotSupportedError,
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

_MAX_CONCURRENT_CATALOG_CALLS: Final[
    Annotated[
        int,
        doc(
            "The catalog is queried while the project row is locked in `upsert_tasks_from_project`, "
            "so these remote calls run concurrently but bounded. "
            "See https://github.com/ITISFoundation/private-issues/issues/669"
        ),
    ]
] = 10


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
    connection: AsyncConnection,
    user_id: UserID,
    product_name: str,
    project_id: ProjectID,
    node_id: NodeID,
    node: Node,
    node_extras: ServiceExtras | None,
    node_labels: SimcoreServiceLabels | None,
    service_resources_cache: dict[ServiceKeyVersion, ServiceResourcesDict],
) -> Image:
    # aggregates node_details and node_extras into Image
    data: dict[str, Any] = {
        "name": node.key,
        "tag": node.version,
    }
    project_nodes_repo = ProjectNodesRepo(project_uuid=project_id)
    project_node = await project_nodes_repo.get(connection, node_id=node_id)
    node_resources = TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).validate_python(
        project_node.required_resources
    )
    if not node_resources:
        # all the nodes of the same service ask the catalog for the very same resources
        key_version = ServiceKeyVersion(key=node.key, version=node.version)
        if key_version not in service_resources_cache:
            service_resources_cache[key_version] = await catalog_client.get_service_resources(
                user_id, node.key, node.version, product_name
            )
        node_resources = service_resources_cache[key_version]

    if node_resources:
        data.update(node_requirements=_compute_node_requirements(node_resources))
        data.update(boot_mode=_compute_node_boot_mode(node_resources))
    if node_labels:
        data.update(envs=_compute_node_envs(node_labels))
    if node_extras and node_extras.container_spec:
        data.update(command=node_extras.container_spec.command)
    return Image(**data)


async def _get_pricing_and_hardware_infos(
    connection: AsyncConnection,
    rut_client: ResourceUsageTrackerClient,
    *,
    is_wallet: bool,
    project_id: ProjectID,
    node_id: NodeID,
    product_name: str,
    node_key: ServiceKey,
    node_version: ServiceVersion,
    default_pricing_cache: dict[ServiceKeyVersion, PricingPlanAndUnitIdsTuple],
    pricing_unit_cache: dict[PricingPlanAndUnitIdsTuple, RutPricingUnitGet],
) -> tuple[PricingInfo | None, HardwareInfo]:
    if not is_wallet or (to_node_class(node_key) == NodeClass.FRONTEND):
        # NOTE: frontend services have no pricing plans, therefore no need to call RUT
        return None, HardwareInfo(aws_ec2_instances=[])
    project_nodes_repo = ProjectNodesRepo(project_uuid=project_id)
    output = await project_nodes_repo.get_project_node_pricing_unit_id(connection, node_uuid=node_id)
    # NOTE: this is some kind of lazy insertion of the pricing unit
    # the projects_nodes is already in at this time, and not in sync with the hardware info
    # this will need to move away and be in sync.
    key_version = ServiceKeyVersion(key=node_key, version=node_version)
    if output:
        pricing_plan_id, pricing_unit_id = output
    else:
        # the same service always gets the same default, so RUT is asked only once per service
        if key_version not in default_pricing_cache:
            (
                pricing_plan_id,
                pricing_unit_id,
                _,
                _,
            ) = await rut_client.get_default_pricing_and_hardware_info(product_name, node_key, node_version)
            default_pricing_cache[key_version] = PricingPlanAndUnitIdsTuple(
                pricing_plan_id=pricing_plan_id,
                pricing_unit_id=pricing_unit_id,
            )
        pricing_plan_id, pricing_unit_id = default_pricing_cache[key_version]
        await project_nodes_repo.connect_pricing_unit_to_project_node(
            connection,
            node_uuid=node_id,
            pricing_plan_id=pricing_plan_id,
            pricing_unit_id=pricing_unit_id,
        )

    # nodes sharing a pricing unit share its cost and hardware, so RUT is asked once per unit;
    # only the RUT response is cached, the derived infos are cheap to rebuild
    unit_ids = PricingPlanAndUnitIdsTuple(
        pricing_plan_id=pricing_plan_id,
        pricing_unit_id=pricing_unit_id,
    )
    pricing_unit_get = pricing_unit_cache.get(unit_ids)
    if pricing_unit_get is None:
        pricing_unit_get = await rut_client.get_pricing_unit(product_name, pricing_plan_id, pricing_unit_id)
        pricing_unit_cache[unit_ids] = pricing_unit_get
    pricing_info = PricingInfo(
        pricing_plan_id=pricing_plan_id,
        pricing_unit_id=pricing_unit_id,
        pricing_unit_cost_id=pricing_unit_get.current_cost_per_unit_id,
        pricing_unit_cost=pricing_unit_get.current_cost_per_unit,
    )
    hardware_info = HardwareInfo(aws_ec2_instances=pricing_unit_get.specific_info.aws_ec2_instances)
    return pricing_info, hardware_info


_RAM_SAFE_MARGIN_RATIO: Final[float] = 0.1  # NOTE: machines always have less available RAM than advertised
_CPUS_SAFE_MARGIN: Final[float] = 0.1


async def _update_project_node_resources_from_hardware_info(
    connection: AsyncConnection,
    *,
    is_wallet: bool,
    project_id: ProjectID,
    node_id: NodeID,
    hardware_info: HardwareInfo,
    ec2_instance_types: list[EC2InstanceTypeGet],
) -> None:
    if not is_wallet:
        return
    if not hardware_info.aws_ec2_instances:
        return
    try:
        # NOTE: with the current implementation, there is no use to get the instance past the first one
        def _by_type_name(ec2: EC2InstanceTypeGet) -> bool:
            return bool(ec2.name == hardware_info.aws_ec2_instances[0])

        selected_ec2_instance_type = next(iter(filter(_by_type_name, ec2_instance_types)))

        # now update the project node required resources
        # NOTE: we keep a safe margin with the RAM as the dask-sidecar "sees"
        # less memory than the machine theoretical amount
        project_nodes_repo = ProjectNodesRepo(project_uuid=project_id)
        node = await project_nodes_repo.get(connection, node_id=node_id)
        resources_adapter = TypeAdapter[ServiceResourcesDict](ServiceResourcesDict)
        node_resources = resources_adapter.validate_python(node.required_resources)
        if DEFAULT_SINGLE_SERVICE_NAME in node_resources:
            image_resources: ImageResources = node_resources[DEFAULT_SINGLE_SERVICE_NAME]
            adjusted_cpus, adjusted_ram = estimate_dask_worker_resources_from_ec2_instance(
                float(selected_ec2_instance_type.cpus),
                selected_ec2_instance_type.ram,
            )
            image_resources.resources["CPU"].set_value(adjusted_cpus)
            image_resources.resources["RAM"].set_value(adjusted_ram)

            new_resources = resources_adapter.dump_python(node_resources, mode="json")
            if new_resources == resources_adapter.dump_python(
                resources_adapter.validate_python(node.required_resources), mode="json"
            ):
                # the node is already sized for the selected machine: writing it again would lock
                # the parent `projects` row through the `projects_nodes_changed` trigger for
                # nothing, while this transaction holds that very row, see
                # https://github.com/ITISFoundation/private-issues/issues/669
                return

            await project_nodes_repo.update(connection, node_id=node_id, required_resources=new_resources)
        else:
            # sizing a multi-container service per sub-service is not implemented: the
            # computation cannot run machine-sized, so it must not start at all
            raise MultiContainerOverrideNotSupportedError(
                sub_service_names=set(node_resources),
                node_id=f"{node_id}",
                project_id=f"{project_id}",
            )
    except StopIteration as exc:
        raise EC2InstanceTypeNotFoundError(
            ec2_instance_types=f"{set(hardware_info.aws_ec2_instances)}",
            node_id=f"{node_id}",
            project_id=f"{project_id}",
        ) from exc


def _has_insufficient_credits(
    task_state: RunningState,
    wallet_info: WalletInfo | None,
    pricing_info: PricingInfo | None,
) -> bool:
    return bool(
        task_state == RunningState.PUBLISHED
        and wallet_info
        and pricing_info
        and pricing_info.pricing_unit_cost > Decimal(0)
        and wallet_info.wallet_credit_amount <= ZERO_CREDITS
    )


def _abort_published_tasks(list_comp_tasks: list[CompTaskAtDB]) -> None:
    # If any published node had insufficient credits, abort ALL published nodes
    for task in list_comp_tasks:
        if task.state == RunningState.PUBLISHED:
            task.state = RunningState.ABORTED


@dataclass
class _PreparedNode:  # pylint: disable=too-many-instance-attributes
    """everything about a node that is gathered before any of its rows is written"""

    internal_id: int
    node_id: NodeID
    node: Node
    node_details: ServiceMetaDataPublished
    node_extras: ServiceExtras | None
    node_labels: SimcoreServiceLabels | None
    task_state: RunningState
    task_progress: float | None
    pricing_info: PricingInfo | None
    hardware_info: HardwareInfo


async def generate_tasks_list_from_project(
    *,
    project: ProjectAtDB,
    project_nodes: NodesDict,
    catalog_client: CatalogClient,
    published_nodes: list[NodeID],
    user_id: UserID,
    product_name: str,
    connection: AsyncConnection,
    rut_client: ResourceUsageTrackerClient,
    wallet_info: WalletInfo | None,
    rabbitmq_rpc_client: RabbitMQRPCClient,
) -> tuple[list[CompTaskAtDB], bool]:
    """Returns (tasks_list, insufficient_credits).

    If insufficient_credits is True, affected published nodes were set to ABORTED.
    """
    list_comp_tasks = []
    insufficient_credits = False
    is_wallet = bool(wallet_info)

    unique_service_key_versions: set[ServiceKeyVersion] = {
        ServiceKeyVersion(key=node.key, version=node.version)  # pyright: ignore[reportUnhashable]  # frozen, hence hashable
        for node in project_nodes.values()
    }

    # this runs while the caller's transaction holds the `projects` row, so every remote call
    # made here extends how long that lock is held: ask the catalog once per distinct service
    # and run those calls concurrently, bounded
    sorted_key_versions = sorted(unique_service_key_versions, key=lambda kv: (f"{kv.key}", f"{kv.version}"))
    list_node_infos = await limited_gather(
        *(_get_node_infos(catalog_client, user_id, product_name, key_version) for key_version in sorted_key_versions),
        limit=_MAX_CONCURRENT_CATALOG_CALLS,
        log=_logger,
    )
    key_version_to_node_infos: dict[
        ServiceKeyVersion, tuple[ServiceMetaDataPublished | None, ServiceExtras | None, SimcoreServiceLabels | None]
    ] = dict(zip(sorted_key_versions, list_node_infos, strict=True))

    # the same answers are requested over and over within one project: keep them per call,
    # since a later call must not miss a change made in the meantime
    default_pricing_cache: dict[ServiceKeyVersion, PricingPlanAndUnitIdsTuple] = {}
    pricing_unit_cache: dict[PricingPlanAndUnitIdsTuple, RutPricingUnitGet] = {}
    service_resources_cache: dict[ServiceKeyVersion, ServiceResourcesDict] = {}

    # first pass: gather everything, without writing to `projects_nodes` yet
    prepared_nodes: list[_PreparedNode] = []
    all_ec2_instance_names: set[str] = set()
    for internal_id, node_id in enumerate(project_nodes, 1):
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

        pricing_info, hardware_info = await _get_pricing_and_hardware_infos(
            connection,
            rut_client,
            is_wallet=is_wallet,
            project_id=project.uuid,
            node_id=NodeID(node_id),
            product_name=product_name,
            node_key=node.key,
            node_version=node.version,
            default_pricing_cache=default_pricing_cache,
            pricing_unit_cache=pricing_unit_cache,
        )

        # Check credits for published nodes with non-zero cost
        insufficient_credits |= _has_insufficient_credits(task_state, wallet_info, pricing_info)

        all_ec2_instance_names.update(hardware_info.aws_ec2_instances)

        prepared_nodes.append(
            _PreparedNode(
                internal_id=internal_id,
                node_id=NodeID(node_id),
                node=node,
                node_details=node_details,
                node_extras=node_extras,
                node_labels=node_labels,
                task_state=task_state,
                task_progress=task_progress,
                pricing_info=pricing_info,
                hardware_info=hardware_info,
            )
        )

    # one call for all the nodes instead of one per node: they request the same machines
    assert rabbitmq_rpc_client  # nosec
    ec2_instance_types: list[EC2InstanceTypeGet] = []
    if is_wallet and all_ec2_instance_names:
        try:
            ec2_instance_types = await get_instance_type_details(
                rabbitmq_rpc_client,
                instance_type_names=all_ec2_instance_names,
            )
            assert ec2_instance_types  # nosec
        except (RemoteMethodNotRegisteredError, RPCServerError, TimeoutError) as exc:
            raise ClustersKeeperNotAvailableError from exc

    # second pass: in the same order as before, only what really changed is written
    for prepared in prepared_nodes:
        await _update_project_node_resources_from_hardware_info(
            connection,
            is_wallet=is_wallet,
            project_id=project.uuid,
            node_id=prepared.node_id,
            hardware_info=prepared.hardware_info,
            ec2_instance_types=ec2_instance_types,
        )

        image = await _generate_task_image(
            catalog_client=catalog_client,
            connection=connection,
            user_id=user_id,
            product_name=product_name,
            project_id=project.uuid,
            node_id=prepared.node_id,
            node=prepared.node,
            node_extras=prepared.node_extras,
            node_labels=prepared.node_labels,
            service_resources_cache=service_resources_cache,
        )

        task_db = CompTaskAtDB(
            project_id=project.uuid,
            node_id=prepared.node_id,
            schema=NodeSchema(
                **prepared.node_details.model_dump(exclude_unset=True, by_alias=True, include={"inputs", "outputs"})
            ),
            inputs=prepared.node.inputs,
            outputs=prepared.node.outputs,
            image=image,
            state=prepared.task_state,
            internal_id=prepared.internal_id,
            node_class=to_node_class(prepared.node.key),
            progress=prepared.task_progress,
            last_heartbeat=None,
            created=arrow.utcnow().datetime,
            modified=arrow.utcnow().datetime,
            pricing_info=(
                prepared.pricing_info.model_dump(exclude={"pricing_unit_cost"}) if prepared.pricing_info else None
            ),
            hardware_info=prepared.hardware_info,
        )

        list_comp_tasks.append(task_db)

    if insufficient_credits:
        _abort_published_tasks(list_comp_tasks)

    return list_comp_tasks, insufficient_credits
