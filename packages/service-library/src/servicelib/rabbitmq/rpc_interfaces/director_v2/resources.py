import logging
from typing import Final

from models_library.api_schemas_directorv2 import (
    DIRECTOR_V2_RPC_NAMESPACE,
)
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import ByteSize, NonNegativeFloat, NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 20

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


@log_decorator(_logger, level=logging.DEBUG)
async def get_helper_containers_resources(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    max_user_service_container_memory: ByteSize,
) -> tuple[NonNegativeFloat, ByteSize]:
    result = await rabbitmq_rpc_client.request(
        DIRECTOR_V2_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_helper_containers_resources"),
        user_id=user_id,
        product_name=product_name,
        service_key=service_key,
        service_version=service_version,
        max_user_service_container_memory=max_user_service_container_memory,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, tuple)  # nosec
    return result
