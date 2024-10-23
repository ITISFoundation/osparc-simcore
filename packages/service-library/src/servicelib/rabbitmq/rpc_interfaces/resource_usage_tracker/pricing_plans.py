import logging
from typing import Final

from models_library.api_schemas_resource_usage_tracker import (
    RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
)
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanGet,
    PricingPlanToServiceGet,
)
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.resource_tracker import (
    PricingPlanCreate,
    PricingPlanId,
    PricingPlanUpdate,
)
from models_library.services import ServiceKey, ServiceVersion
from pydantic import NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ....rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 20

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


@log_decorator(_logger, level=logging.DEBUG)
async def get_pricing_plan(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
) -> PricingPlanGet:
    result: PricingPlanGet = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_pricing_plan"),
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, PricingPlanGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def list_pricing_plans(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
) -> list[PricingPlanGet]:
    result: PricingPlanGet = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("list_pricing_plans"),
        product_name=product_name,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, list)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def create_pricing_plan(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    data: PricingPlanCreate,
) -> PricingPlanGet:
    result: PricingPlanGet = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("create_pricing_plan"),
        data=data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, PricingPlanGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def update_pricing_plan(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    data: PricingPlanUpdate,
) -> PricingPlanGet:
    result: PricingPlanGet = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("update_pricing_plan"),
        product_name=product_name,
        data=data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, PricingPlanGet)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def list_connected_services_to_pricing_plan_by_pricing_plan(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
) -> list[PricingPlanToServiceGet]:
    result: PricingPlanGet = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python(
            "list_connected_services_to_pricing_plan_by_pricing_plan"
        ),
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, list)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def connect_service_to_pricing_plan(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> PricingPlanToServiceGet:
    result: PricingPlanGet = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("connect_service_to_pricing_plan"),
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
        service_key=service_key,
        service_version=service_version,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, PricingPlanToServiceGet)  # nosec
    return result
