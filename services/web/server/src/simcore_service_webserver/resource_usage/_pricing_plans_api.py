from aiohttp import web
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingUnitGet,
    ServicePricingPlanGet,
)
from models_library.products import ProductName
from models_library.resource_tracker import PricingPlanId, PricingUnitId
from models_library.services import ServiceKey, ServiceVersion

from . import _client as resource_tracker_client


async def get_default_service_pricing_plan(
    app: web.Application,
    product_name: ProductName,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> ServicePricingPlanGet:
    data: ServicePricingPlanGet = (
        await resource_tracker_client.get_default_service_pricing_plan(
            app=app,
            product_name=product_name,
            service_key=service_key,
            service_version=service_version,
        )
    )

    return data


async def get_pricing_plan_unit(
    app: web.Application,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    pricing_unit_id: PricingUnitId,
) -> PricingUnitGet:
    data: PricingUnitGet = await resource_tracker_client.get_pricing_plan_unit(
        app=app,
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
        pricing_unit_id=pricing_unit_id,
    )

    return data
