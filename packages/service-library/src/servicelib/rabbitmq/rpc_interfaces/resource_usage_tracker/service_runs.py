import logging
from typing import Final

from models_library.api_schemas_resource_usage_tracker import (
    RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
)
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    ServiceRunPage,
)
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.resource_tracker import ServiceResourceUsagesFilters
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import NonNegativeInt, parse_obj_as
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 20


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
    order_by: list[OrderBy] | None = None,
    filters: ServiceResourceUsagesFilters | None = None
) -> ServiceRunPage:
    result = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "get_service_run_page"),
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
