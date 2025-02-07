import logging
from typing import Final

from models_library.api_schemas_resource_usage_tracker import (
    RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
)
from models_library.api_schemas_resource_usage_tracker.license_checkouts import (
    LicenseCheckoutGet,
    LicenseCheckoutsPage,
)
from models_library.basic_types import IDStr
from models_library.licenses import LicenseID
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.resource_tracker_license_checkouts import LicenseCheckoutID
from models_library.rest_ordering import OrderBy
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 30

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


@log_decorator(_logger, level=logging.DEBUG)
async def get_license_checkout(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    license_checkout_id: LicenseCheckoutID,
) -> LicenseCheckoutGet:
    result = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_license_checkout"),
        product_name=product_name,
        license_checkout_id=license_checkout_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, LicenseCheckoutGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_license_checkouts_page(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    filter_wallet_id: WalletID,
    offset: int = 0,
    limit: int = 20,
    order_by: OrderBy | None = None,
) -> LicenseCheckoutsPage:
    """
    Default order_by field is "started_at"
    """
    if order_by is None:
        order_by = OrderBy(field=IDStr("started_at"))

    result = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_license_checkouts_page"),
        product_name=product_name,
        filter_wallet_id=filter_wallet_id,
        limit=limit,
        offset=offset,
        order_by=order_by,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, LicenseCheckoutsPage)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def checkout_license(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    license_id: LicenseID,
    wallet_id: WalletID,
    product_name: ProductName,
    num_of_seats: int,
    service_run_id: ServiceRunID,
    user_id: UserID,
    user_email: str,
) -> LicenseCheckoutGet:
    result: LicenseCheckoutGet = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("checkout_license"),
        license_id=license_id,
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
async def release_license(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    license_checkout_id: LicenseCheckoutID,
    product_name: ProductName,
) -> LicenseCheckoutGet:
    result: LicenseCheckoutGet = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("release_license"),
        license_checkout_id=license_checkout_id,
        product_name=product_name,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, LicenseCheckoutGet)  # nosec
    return result
