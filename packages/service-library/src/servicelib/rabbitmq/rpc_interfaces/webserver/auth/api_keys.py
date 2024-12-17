import logging

from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.basic_types import IDStr
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rpc.webserver.auth.api_keys import ApiKeyCreate, ApiKeyGet
from pydantic import TypeAdapter
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def create_api_key(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: str,
    product_name: str,
    api_key: ApiKeyCreate,
) -> ApiKeyGet:
    result: ApiKeyGet = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("create_api_key"),
        user_id=user_id,
        product_name=product_name,
        api_key=api_key,
    )
    assert isinstance(result, ApiKeyGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_api_key(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: str,
    product_name: str,
    api_key_id: IDStr,
) -> ApiKeyGet:
    result: ApiKeyGet = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_api_key"),
        user_id=user_id,
        product_name=product_name,
        api_key_id=api_key_id,
    )
    assert isinstance(result, ApiKeyGet)  # nosec
    return result


async def delete_api_key(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: str,
    product_name: str,
    api_key_id: IDStr,
) -> None:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_api_key"),
        user_id=user_id,
        product_name=product_name,
        api_key_id=api_key_id,
    )
    assert result is None  # nosec
