import logging

from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.licensed_items import (
    LicensedItemGet,
    LicensedItemGetPage,
)
from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.resource_tracker import ServiceRunId
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import TypeAdapter
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def get_licensed_items(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: str,
    offset: int,
    limit: int,
) -> LicensedItemGetPage:
    result: LicensedItemGetPage = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_licensed_items"),
        product_name=product_name,
        offset=offset,
        limit=limit,
    )
    assert isinstance(result, LicensedItemGetPage)
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_licensed_items_for_wallet(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    wallet_id: WalletID,
) -> LicensedItemGet:
    result: LicensedItemGet = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_licensed_items_for_wallet"),
        user_id=user_id,
        product_name=product_name,
        wallet_id=wallet_id,
    )
    assert isinstance(result, LicensedItemGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def checkout_licensed_item_for_wallet(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    wallet_id: WalletID,
    licensed_item_id: LicensedItemID,
    num_of_seats: int,
    service_run_id: ServiceRunId,
) -> None:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("checkout_licensed_item_for_wallet"),
        user_id=user_id,
        product_name=product_name,
        wallet_id=wallet_id,
        licensed_item_id=licensed_item_id,
        num_of_seats=num_of_seats,
        service_run_id=service_run_id,
    )
    assert result is None  # nosec


@log_decorator(_logger, level=logging.DEBUG)
async def release_licensed_item_for_wallet(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    wallet_id: WalletID,
    licensed_item_id: LicensedItemID,
    num_of_seats: int,
    service_run_id: ServiceRunId,
) -> None:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("release_licensed_item_for_wallet"),
        user_id=user_id,
        product_name=product_name,
        wallet_id=wallet_id,
        licensed_item_id=licensed_item_id,
        num_of_seats=num_of_seats,
        service_run_id=service_run_id,
    )
    assert result is None  # nosec