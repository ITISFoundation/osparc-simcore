from aiohttp import web
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanGet,
    PricingUnitGet,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    PricingPlanCreate,
    PricingPlanId,
    PricingPlanUpdate,
    PricingUnitId,
    PricingUnitWithCostCreate,
    PricingUnitWithCostUpdate,
)
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    pricing_plans,
    pricing_units,
)

from ..rabbitmq import get_rabbitmq_rpc_client

## Pricing Plans


async def list_pricing_plans(
    app: web.Application,
    product_name: ProductName,
) -> list[PricingPlanGet]:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await pricing_plans.list_pricing_plans(rpc_client, product_name=product_name)


async def get_pricing_plan(
    app: web.Application,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
) -> PricingPlanGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await pricing_plans.get_pricing_plan(
        rpc_client,
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
    )


async def create_pricing_plan(
    app: web.Application,
    data: PricingPlanCreate,
) -> PricingPlanGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await pricing_plans.create_pricing_plan(rpc_client, data=data)


async def update_pricing_plan(
    app: web.Application, product_name: ProductName, data: PricingPlanUpdate
) -> PricingPlanGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await pricing_plans.update_pricing_plan(
        rpc_client, product_name=product_name, data=data
    )


## Pricing units


async def get_pricing_unit(
    app: web.Application,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    pricing_unit_id: PricingUnitId,
) -> PricingUnitGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await pricing_units.get_pricing_unit(
        rpc_client,
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
        pricing_unit_id=pricing_unit_id,
    )


async def create_pricing_unit(
    app: web.Application, product_name: ProductName, data: PricingUnitWithCostCreate
) -> PricingUnitGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await pricing_units.create_pricing_unit(
        rpc_client, product_name=product_name, data=data
    )


async def update_pricing_unit(
    app: web.Application, product_name: ProductName, data: PricingUnitWithCostUpdate
) -> PricingUnitGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await pricing_units.update_pricing_unit(
        rpc_client, product_name=product_name, data=data
    )
