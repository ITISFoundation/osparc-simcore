"""Sizing of a node's container resources from an EC2 machine type

The knowledge of how much of an EC2 machine a node's containers may use (safe
margins, sidecar overhead, scaling of multi-container services) lives here. Other
services request it through the director-v2 RPC
``compute_node_resources_for_hardware``.
"""

import collections
import logging
from typing import Annotated, Final

from annotated_types import doc
from dask_task_models_library.resource_constraints import (
    estimate_dask_worker_resources_from_ec2_instance,
)
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.resource_tracker import HardwareInfo
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    ServiceResourcesDict,
)
from pydantic import ByteSize, TypeAdapter
from servicelib.docker_utils import (
    DYNAMIC_SIDECAR_MIN_CPUS,
    estimate_dynamic_sidecar_resources_from_ec2_instance,
)
from servicelib.rabbitmq import (
    RabbitMQRPCClient,
    RemoteMethodNotRegisteredError,
    RPCServerError,
)
from servicelib.rabbitmq.rpc_interfaces.clusters_keeper.ec2_instances import (
    get_instance_type_details,
)
from servicelib.rabbitmq.rpc_interfaces.clusters_keeper.errors import (
    InvalidEC2InstanceTypesRPCError,
)
from servicelib.rabbitmq.rpc_interfaces.director_v2.errors import (
    ClustersKeeperNotAvailableRPCError,
    EC2InstanceTypeNotFoundRPCError,
    MultiContainerOverrideNotSupportedRPCError,
    UnsupportedNodeClassRPCError,
)

from ..utils.computations import to_node_class
from .db.tables import NodeClass

_logger = logging.getLogger(__name__)

_SERVICE_RESOURCES_ADAPTER: Final[TypeAdapter[ServiceResourcesDict]] = TypeAdapter(ServiceResourcesDict)

_MIN_RAM_PER_SUB_SERVICE: Final[
    Annotated[ByteSize, doc("smallest RAM a sub-service container may be resized down to")]
] = ByteSize(128 * 1024 * 1024)


def _select_ec2_instance_type(
    hardware_info: HardwareInfo, ec2_instance_types: list[EC2InstanceTypeGet]
) -> EC2InstanceTypeGet:
    # NOTE: with the current implementation, there is no use to get the instance past
    # the first one
    try:
        return next(t for t in ec2_instance_types if t.name == hardware_info.aws_ec2_instances[0])
    except StopIteration as exc:
        raise EC2InstanceTypeNotFoundRPCError(ec2_types=set(hardware_info.aws_ec2_instances)) from exc


def resize_computational_node_resources(
    resources: ServiceResourcesDict, *, ec2_instance_type: EC2InstanceTypeGet
) -> ServiceResourcesDict:
    """Sizes a single-container computational node as a dask worker on the machine.

    Raises:
        MultiContainerOverrideNotSupportedRPCError -- multi-container services: sizing
            their sub-services from a machine is not implemented, so they are never
            machine-derived (rather than silently left unsized)

    """
    resized_resources = _SERVICE_RESOURCES_ADAPTER.validate_python(resources)
    if DEFAULT_SINGLE_SERVICE_NAME not in resized_resources:
        raise MultiContainerOverrideNotSupportedRPCError(sub_service_names=set(resized_resources))

    adjusted_cpus, adjusted_ram = estimate_dask_worker_resources_from_ec2_instance(
        float(ec2_instance_type.cpus),
        ec2_instance_type.ram,
    )
    image_resources = resized_resources[DEFAULT_SINGLE_SERVICE_NAME]
    image_resources.resources["CPU"].set_value(adjusted_cpus)
    image_resources.resources["RAM"].set_value(adjusted_ram)
    return resized_resources


def resize_dynamic_node_resources(
    resources: ServiceResourcesDict, *, ec2_instance_type: EC2InstanceTypeGet
) -> ServiceResourcesDict:
    """Sizes a dynamic service so that all its containers fit into the machine,
    scaling up/down the largest sub-service.
    """
    resized_resources = _SERVICE_RESOURCES_ADAPTER.validate_python(resources)

    new_cpus_value, new_ram_value = estimate_dynamic_sidecar_resources_from_ec2_instance(
        float(ec2_instance_type.cpus),
        ec2_instance_type.ram,
    )

    scalable_service_name = DEFAULT_SINGLE_SERVICE_NAME
    if DEFAULT_SINGLE_SERVICE_NAME not in resized_resources:
        # NOTE: we go for the largest sub-service and scale it up/down
        scalable_service_name, hungry_service_resources = max(
            resized_resources.items(),
            key=lambda service_to_resources: int(service_to_resources[1].resources["RAM"].limit),
        )
        _logger.debug("the most hungry service is %s", f"{scalable_service_name=}:{hungry_service_resources}")
        other_services_resources = collections.Counter({"RAM": 0, "CPUS": 0})
        for service_name, sub_service_resources in resized_resources.items():
            if service_name != scalable_service_name:
                other_services_resources.update(
                    {
                        "RAM": sub_service_resources.resources["RAM"].limit,
                        "CPU": sub_service_resources.resources["CPU"].limit,
                    }
                )
        new_cpus_value = max(
            new_cpus_value - other_services_resources["CPU"],
            DYNAMIC_SIDECAR_MIN_CPUS,
        )
        new_ram_value = max(int(new_ram_value - other_services_resources["RAM"]), _MIN_RAM_PER_SUB_SERVICE)

    # scale the service
    resized_resources[scalable_service_name].resources["CPU"].set_value(new_cpus_value)
    resized_resources[scalable_service_name].resources["RAM"].set_value(new_ram_value)
    return resized_resources


async def compute_node_resources_for_hardware(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    resources: ServiceResourcesDict,
    hardware_info: HardwareInfo,
) -> ServiceResourcesDict:
    """Returns `resources` resized for the first EC2 machine type of `hardware_info`.

    The node class is derived from `service_key`: computational nodes are sized as
    dask workers, dynamic (interactive) nodes as dynamic-sidecar services; other
    classes cannot be sized from a machine.

    Raises:
        EC2InstanceTypeNotFoundRPCError -- machine type unknown to clusters-keeper
        ClustersKeeperNotAvailableRPCError -- clusters-keeper could not be reached
        UnsupportedNodeClassRPCError -- frontend (or unknown) service classes
        MultiContainerOverrideNotSupportedRPCError -- multi-container computational
            services (their per-sub-service sizing is not implemented)

    """
    # reject unsupported classes first: their resources never depend on an EC2
    # machine, so they must not depend on the clusters-keeper being reachable
    node_class = to_node_class(service_key)
    if node_class not in (NodeClass.COMPUTATIONAL, NodeClass.INTERACTIVE):
        raise UnsupportedNodeClassRPCError(service_key=service_key, service_version=service_version)

    if not hardware_info.aws_ec2_instances:
        return resources

    try:
        ec2_instance_types = await get_instance_type_details(
            rabbitmq_rpc_client,
            instance_type_names=set(hardware_info.aws_ec2_instances),
        )
        assert ec2_instance_types  # nosec
    except InvalidEC2InstanceTypesRPCError as exc:
        # the machine type is not a valid EC2 instance type: a bad request, not an
        # outage (this error is a RPCServerError subclass, so catch it first)
        raise EC2InstanceTypeNotFoundRPCError(ec2_types=set(hardware_info.aws_ec2_instances)) from exc
    except (TimeoutError, RemoteMethodNotRegisteredError, RPCServerError) as exc:
        raise ClustersKeeperNotAvailableRPCError from exc

    selected_ec2_instance_type = _select_ec2_instance_type(hardware_info, ec2_instance_types)

    if node_class == NodeClass.COMPUTATIONAL:
        return resize_computational_node_resources(resources, ec2_instance_type=selected_ec2_instance_type)
    return resize_dynamic_node_resources(resources, ec2_instance_type=selected_ec2_instance_type)
