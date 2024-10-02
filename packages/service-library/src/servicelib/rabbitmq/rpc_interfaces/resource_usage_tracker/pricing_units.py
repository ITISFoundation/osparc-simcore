import logging
from typing import Final

from models_library.api_schemas_resource_usage_tracker import (
    RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
)
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingUnitGet,
)
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.resource_tracker import (
    PricingPlanId,
    PricingUnitId,
    PricingUnitWithCostCreate,
    PricingUnitWithCostUpdate,
)
from pydantic import NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ....rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 20

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


@log_decorator(_logger, level=logging.DEBUG)
async def get_pricing_unit(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    pricing_unit_id: PricingUnitId,
) -> PricingUnitGet:
    result: PricingUnitGet = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_pricing_unit"),
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
        pricing_unit_id=pricing_unit_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, PricingUnitGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def create_pricing_unit(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    data: PricingUnitWithCostCreate,
) -> PricingUnitGet:
    result: PricingUnitGet = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("create_pricing_unit"),
        product_name=product_name,
        data=data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, PricingUnitGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def update_pricing_unit(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    data: PricingUnitWithCostUpdate,
) -> PricingUnitGet:
    result: PricingUnitGet = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("update_pricing_unit"),
        product_name=product_name,
        data=data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, PricingUnitGet)  # nosec
    return result
