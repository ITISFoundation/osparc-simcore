# pylint: disable=too-many-arguments
import logging
from typing import Final

from models_library.api_schemas_directorv2 import DIRECTOR_V2_RPC_NAMESPACE
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.resource_tracker import HardwareInfo
from models_library.services_resources import ServiceResourcesDict
from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 20

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)
_SERVICE_RESOURCES_ADAPTER: TypeAdapter[ServiceResourcesDict] = TypeAdapter(ServiceResourcesDict)


@log_decorator(_logger, level=logging.DEBUG)
async def compute_node_resources_for_hardware(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    resources: ServiceResourcesDict,
    hardware_info: HardwareInfo,
) -> ServiceResourcesDict:
    """Computes the resources a node's containers shall get when running on the EC2
    machine type selected through its pricing unit's hardware info.

    **remote method**

    Raises:
        EC2InstanceTypeNotFoundRPCError -- the machine type is unknown to clusters-keeper
        ClustersKeeperNotAvailableRPCError -- clusters-keeper could not be reached
        UnsupportedNodeClassRPCError -- the service class cannot be sized from a machine
            (e.g. frontend services)
        KeyError -- a container's resources are missing the RAM/CPU keys

    """
    result = await rabbitmq_rpc_client.request(
        DIRECTOR_V2_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("compute_node_resources_for_hardware"),
        service_key=service_key,
        service_version=service_version,
        resources=_SERVICE_RESOURCES_ADAPTER.dump_python(resources, mode="json"),
        hardware_info=hardware_info,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    return _SERVICE_RESOURCES_ADAPTER.validate_python(result)
