import logging

from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter

from ....logging_utils import log_decorator
from ..._client_rpc import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def get_product_base_url(
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
) -> str:

    base_url = await rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_product_base_url"),
        product_name=product_name,
    )
    assert base_url  # nosec
    assert isinstance(base_url, str)  # nosec
    return base_url
