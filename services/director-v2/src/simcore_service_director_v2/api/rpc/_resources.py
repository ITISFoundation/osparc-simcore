from fastapi import FastAPI
from models_library.resource_tracker import HardwareInfo
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_resources import ServiceResourcesDict
from pydantic import validate_call
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.director_v2.errors import (
    ClustersKeeperNotAvailableRPCError,
    EC2InstanceTypeNotFoundRPCError,
    UnsupportedNodeClassRPCError,
)

from ...modules import resources_sizing
from ...modules.rabbitmq import get_rabbitmq_rpc_client

router = RPCRouter()


@router.expose(
    reraise_if_error_type=(
        EC2InstanceTypeNotFoundRPCError,
        ClustersKeeperNotAvailableRPCError,
        UnsupportedNodeClassRPCError,
        KeyError,
    )
)
@validate_call(config={"arbitrary_types_allowed": True})
async def compute_node_resources_for_hardware(
    app: FastAPI,
    *,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    resources: ServiceResourcesDict,
    hardware_info: HardwareInfo,
) -> ServiceResourcesDict:
    return await resources_sizing.compute_node_resources_for_hardware(
        get_rabbitmq_rpc_client(app),
        service_key=service_key,
        service_version=service_version,
        resources=resources,
        hardware_info=hardware_info,
    )
