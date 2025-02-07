import logging
from typing import Final

from models_library.api_schemas_resource_usage_tracker import (
    RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
)
from models_library.api_schemas_resource_usage_tracker.license_purchases import (
    LicensePurchaseGet,
    LicensesPurchasesPage,
)
from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.resource_tracker_license_purchases import (
    LicensePurchaseID,
    LicensePurchasesCreate,
)
from models_library.rest_ordering import OrderBy
from models_library.wallets import WalletID
from pydantic import NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 30

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


@log_decorator(_logger, level=logging.DEBUG)
async def get_license_purchases_page(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    wallet_id: WalletID,
    offset: int = 0,
    limit: int = 20,
    order_by: OrderBy | None = None,
) -> LicensesPurchasesPage:
    """
    Default order_by field is "purchased_at"
    """
    if order_by is None:
        order_by = OrderBy(field=IDStr("purchased_at"))

    result = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_license_purchases_page"),
        product_name=product_name,
        wallet_id=wallet_id,
        limit=limit,
        offset=offset,
        order_by=order_by,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, LicensesPurchasesPage)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_license_purchase(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    licensed_item_purchase_id: LicensePurchaseID,
) -> LicensePurchaseGet:
    result = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_license_purchase"),
        product_name=product_name,
        licensed_item_purchase_id=licensed_item_purchase_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, LicensePurchaseGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def create_license_purchase(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, data: LicensePurchasesCreate
) -> LicensePurchaseGet:
    result = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("create_license_purchase"),
        data=data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, LicensePurchaseGet)  # nosec
    return result
