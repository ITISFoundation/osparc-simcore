import logging
from typing import Final

from models_library.api_schemas_resource_usage_tracker import (
    RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
)
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    OsparcCreditsAggregatedUsagesPage,
    ServiceRunPage,
)
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.resource_tracker import (
    ServiceResourceUsagesFilters,
    ServicesAggregatedUsagesTimePeriod,
    ServicesAggregatedUsagesType,
)
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import AnyUrl, NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ....rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 20

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


@log_decorator(_logger, level=logging.DEBUG)
async def get_service_run_page(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    limit: int = 20,
    offset: int = 0,
    wallet_id: WalletID | None = None,
    access_all_wallet_usage: bool = False,
    order_by: OrderBy | None = None,
    filters: ServiceResourceUsagesFilters | None = None,
) -> ServiceRunPage:
    result = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_service_run_page"),
        user_id=user_id,
        product_name=product_name,
        limit=limit,
        offset=offset,
        wallet_id=wallet_id,
        access_all_wallet_usage=access_all_wallet_usage,
        order_by=order_by,
        filters=filters,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, ServiceRunPage)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_osparc_credits_aggregated_usages_page(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    aggregated_by: ServicesAggregatedUsagesType,
    time_period: ServicesAggregatedUsagesTimePeriod,
    limit: int = 20,
    offset: int = 0,
    wallet_id: WalletID,
    access_all_wallet_usage: bool = False,
) -> OsparcCreditsAggregatedUsagesPage:
    result = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python(
            "get_osparc_credits_aggregated_usages_page"
        ),
        user_id=user_id,
        product_name=product_name,
        limit=limit,
        offset=offset,
        wallet_id=wallet_id,
        access_all_wallet_usage=access_all_wallet_usage,
        aggregated_by=aggregated_by,
        time_period=time_period,
        timeout_s=60,
    )
    assert isinstance(result, OsparcCreditsAggregatedUsagesPage)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def export_service_runs(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    wallet_id: WalletID | None = None,
    access_all_wallet_usage: bool = False,
    order_by: OrderBy | None = None,
    filters: ServiceResourceUsagesFilters | None = None,
) -> AnyUrl:
    result: AnyUrl = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("export_service_runs"),
        user_id=user_id,
        product_name=product_name,
        wallet_id=wallet_id,
        access_all_wallet_usage=access_all_wallet_usage,
        order_by=order_by,
        filters=filters,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, AnyUrl)  # nosec
    return result
