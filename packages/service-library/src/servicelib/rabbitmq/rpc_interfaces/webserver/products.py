import logging
from decimal import Decimal

from models_library.api_schemas_webserver.products import CreditResultRpcGet
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from pydantic import TypeAdapter
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def get_credit_amount(
    rpc_client: RabbitMQRPCClient,
    rpc_namespace: RPCNamespace,
    *,
    dollar_amount: Decimal,
    product_name: ProductName,
) -> CreditResultRpcGet:
    """
    Get credit amount for a specific dollar amount and product.

    Args:
        rpc_client: RPC client to communicate with the webserver
        rpc_namespace: Namespace for the RPC call
        dollar_amount: The amount in dollars to be converted to credits
        product_name: The product for which to calculate the credit amount

    Returns:
        Credit result information containing the credit amount
    """
    result: CreditResultRpcGet = await rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("get_credit_amount"),
        dollar_amount=dollar_amount,
        product_name=product_name,
    )
    assert isinstance(result, CreditResultRpcGet)  # nosec
    return result
