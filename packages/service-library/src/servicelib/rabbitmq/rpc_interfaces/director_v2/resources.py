import logging
from typing import Final

from models_library.api_schemas_directorv2 import (
    DIRECTOR_V2_RPC_NAMESPACE,
)
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.services_resources import ServiceResourcesDict
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import ByteSize, NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 20

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


@log_decorator(_logger, level=logging.DEBUG)
async def scale_service_resources_for_instance_type(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    service_resources: ServiceResourcesDict,
    instance_cpus: float,
    instance_ram: ByteSize,
) -> ServiceResourcesDict:
    """Rescales the node's resources to fit the given machine.

    Everything running on that machine is accounted for: the user services, the
    dynamic-sidecar and the helper containers it creates. Callers only persist the result.

    Raises `InsufficientInstanceResourcesError` when the machine is too small.
    """
    result = await rabbitmq_rpc_client.request(
        DIRECTOR_V2_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("scale_service_resources_for_instance_type"),
        user_id=user_id,
        product_name=product_name,
        service_key=service_key,
        service_version=service_version,
        service_resources=service_resources,
        instance_cpus=instance_cpus,
        instance_ram=instance_ram,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, dict)  # nosec
    return result
