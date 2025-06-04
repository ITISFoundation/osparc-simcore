import logging
from decimal import Decimal

from models_library.payments import InvoiceDataGet
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def get_invoice_data(
    rpc_client: RabbitMQRPCClient,
    rpc_namespace: RPCNamespace,
    *,
    user_id: UserID,
    dollar_amount: Decimal,
    product_name: ProductName,
) -> InvoiceDataGet:
    result: InvoiceDataGet = await rpc_client.request(
        rpc_namespace,
        TypeAdapter(RPCMethodName).validate_python("get_invoice_data"),
        user_id=user_id,
        dollar_amount=dollar_amount,
        product_name=product_name,
    )
    assert isinstance(result, InvoiceDataGet)  # nosec
    return result
