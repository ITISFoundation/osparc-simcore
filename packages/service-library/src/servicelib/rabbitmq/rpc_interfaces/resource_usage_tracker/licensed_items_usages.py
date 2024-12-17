import logging
from typing import Final

from models_library.api_schemas_resource_usage_tracker import (
    RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
)
from models_library.api_schemas_resource_usage_tracker.licensed_items_usages import (
    LicenseCheckoutGet,
    LicenseCheckoutID,
    LicensedItemsUsagesPage,
    LicensedItemUsageGet,
)
from models_library.basic_types import IDStr
from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.resource_tracker import ServiceRunId
from models_library.resource_tracker_licensed_items_usages import LicensedItemUsageID
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ....rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 30

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


@log_decorator(_logger, level=logging.DEBUG)
async def get_licensed_item_usage(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    licensed_item_usage_id: LicensedItemUsageID,
) -> LicensedItemUsageGet:
    result = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_licensed_item_usage"),
        product_name=product_name,
        licensed_item_usage_id=licensed_item_usage_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, LicensedItemUsageGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_licensed_items_usages_page(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    filter_wallet_id: WalletID,
    offset: int = 0,
    limit: int = 20,
    order_by: OrderBy | None = None,
) -> LicensedItemsUsagesPage:
    """
    Default order_by field is "started_at"
    """
    if order_by is None:
        order_by = OrderBy(field=IDStr("started_at"))

    result = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_licensed_items_usages_page"),
        product_name=product_name,
        filter_wallet_id=filter_wallet_id,
        limit=limit,
        offset=offset,
        order_by=order_by,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, LicensedItemsUsagesPage)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def checkout_licensed_item(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    licensed_item_id: LicensedItemID,
    wallet_id: WalletID,
    product_name: ProductName,
    num_of_seats: int,
    service_run_id: ServiceRunId,
    user_id: UserID,
    user_email: str,
) -> LicenseCheckoutGet:
    result: LicenseCheckoutGet = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("checkout_licensed_item"),
        licensed_item_id=licensed_item_id,
        wallet_id=wallet_id,
        product_name=product_name,
        num_of_seats=num_of_seats,
        service_run_id=service_run_id,
        user_id=user_id,
        user_email=user_email,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, LicenseCheckoutGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def release_licensed_item(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    checkout_id: LicenseCheckoutID,
    product_name: ProductName,
) -> LicensedItemUsageGet:
    result: LicensedItemUsageGet = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("release_licensed_item"),
        checkout_id=checkout_id,
        product_name=product_name,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, LicensedItemUsageGet)  # nosec
    return result
