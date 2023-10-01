from aiohttp import web
from models_library.api_schemas_resource_usage_tracker import (
    pricing_plans as rut_api_schemas,
)
from models_library.api_schemas_webserver import resource_usage as webserver_api_schemas
from models_library.products import ProductName
from models_library.resource_tracker import PricingPlanId, PricingUnitId
from models_library.services import ServiceKey, ServiceVersion
from pydantic import parse_obj_as

from . import resource_usage_tracker_client as resource_tracker_client


async def get_default_service_pricing_plan(
    app: web.Application,
    product_name: ProductName,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> webserver_api_schemas.ServicePricingPlanGet:
    data: rut_api_schemas.ServicePricingPlanGet = (
        await resource_tracker_client.get_default_service_pricing_plan(
            app=app,
            product_name=product_name,
            service_key=service_key,
            service_version=service_version,
        )
    )

    return parse_obj_as(webserver_api_schemas.ServicePricingPlanGet, data)


async def get_pricing_plan_unit(
    app: web.Application,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    pricing_unit_id: PricingUnitId,
) -> webserver_api_schemas.PricingUnitGet:
    data: rut_api_schemas.PricingUnitGet = (
        await resource_tracker_client.get_pricing_plan_unit(
            app=app,
            product_name=product_name,
            pricing_plan_id=pricing_plan_id,
            pricing_unit_id=pricing_unit_id,
        )
    )

    return webserver_api_schemas.PricingUnitGet(
        pricing_unit_id=data.pricing_unit_id,
        unit_name=data.unit_name,
        current_cost_per_unit=data.current_cost_per_unit,
        default=data.default,
    )
