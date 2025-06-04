import logging
from decimal import Decimal

from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.products import CreditResultRpcGet
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def get_credit_amount(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    dollar_amount: Decimal,
    product_name: ProductName,
) -> CreditResultRpcGet:
    """
    Get credit amount for a specific dollar amount and product.

    Args:
        rabbitmq_rpc_client: RPC client to communicate with the webserver
        dollar_amount: The amount in dollars to be converted to credits
        product_name: The product for which to calculate the credit amount

    Returns:
        Credit result information containing the credit amount
    """
    result: CreditResultRpcGet = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_credit_amount"),
        dollar_amount=dollar_amount,
        product_name=product_name,
    )
    assert isinstance(result, CreditResultRpcGet)  # nosec
    return result
