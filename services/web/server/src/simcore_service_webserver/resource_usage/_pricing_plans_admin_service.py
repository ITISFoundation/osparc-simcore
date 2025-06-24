from aiohttp import web
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanToServiceGet,
    RutPricingPlanGet,
    RutPricingPlanPage,
    RutPricingUnitGet,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    PricingPlanClassification,
    PricingPlanCreate,
    PricingPlanId,
    PricingPlanUpdate,
    PricingUnitId,
    PricingUnitWithCostCreate,
    PricingUnitWithCostUpdate,
    UnitExtraInfoLicense,
    UnitExtraInfoTier,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    pricing_plans,
    pricing_units,
)

from ..catalog import catalog_service
from ..rabbitmq import get_rabbitmq_rpc_client

## Pricing Plans


async def list_pricing_plans_without_pricing_units(
    app: web.Application,
    *,
    product_name: ProductName,
    exclude_inactive: bool,
    offset: int,
    limit: int,
) -> RutPricingPlanPage:
    rpc_client = get_rabbitmq_rpc_client(app)
    output: RutPricingPlanPage = (
        await pricing_plans.list_pricing_plans_without_pricing_units(
            rpc_client,
            product_name=product_name,
            exclude_inactive=exclude_inactive,
            offset=offset,
            limit=limit,
        )
    )
    return output


async def get_pricing_plan(
    app: web.Application,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
) -> RutPricingPlanGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await pricing_plans.get_pricing_plan(
        rpc_client,
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
    )


async def create_pricing_plan(
    app: web.Application,
    data: PricingPlanCreate,
) -> RutPricingPlanGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await pricing_plans.create_pricing_plan(rpc_client, data=data)


async def update_pricing_plan(
    app: web.Application, product_name: ProductName, data: PricingPlanUpdate
) -> RutPricingPlanGet:
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
) -> RutPricingUnitGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await pricing_units.get_pricing_unit(
        rpc_client,
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
        pricing_unit_id=pricing_unit_id,
    )


async def create_pricing_unit(
    app: web.Application, product_name: ProductName, data: PricingUnitWithCostCreate
) -> RutPricingUnitGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    pricing_plan = await pricing_plans.get_pricing_plan(
        rpc_client, product_name=product_name, pricing_plan_id=data.pricing_plan_id
    )
    _validate_pricing_unit(pricing_plan.classification, data.unit_extra_info)
    return await pricing_units.create_pricing_unit(
        rpc_client, product_name=product_name, data=data
    )


async def update_pricing_unit(
    app: web.Application, product_name: ProductName, data: PricingUnitWithCostUpdate
) -> RutPricingUnitGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    pricing_plan = await pricing_plans.get_pricing_plan(
        rpc_client, product_name=product_name, pricing_plan_id=data.pricing_plan_id
    )
    _validate_pricing_unit(pricing_plan.classification, data.unit_extra_info)
    return await pricing_units.update_pricing_unit(
        rpc_client, product_name=product_name, data=data
    )


def _validate_pricing_unit(classification: PricingPlanClassification, unit_extra_info):
    if classification == PricingPlanClassification.LICENSE:
        if not isinstance(unit_extra_info, UnitExtraInfoLicense):
            msg = "Expected UnitExtraInfoLicense (num_of_seats) for LICENSE classification"
            raise ValueError(msg)
    elif classification == PricingPlanClassification.TIER:
        if not isinstance(unit_extra_info, UnitExtraInfoTier):
            msg = "Expected UnitExtraInfoTier (CPU, RAM, VRAM) for TIER classification"
            raise ValueError(msg)
    else:
        msg = "Not known pricing plan classification"  # type: ignore[unreachable]
        raise ValueError(msg)


## Pricing Plans to Service


async def list_connected_services_to_pricing_plan(
    app: web.Application, product_name: ProductName, pricing_plan_id: PricingPlanId
) -> list[PricingPlanToServiceGet]:
    rpc_client = get_rabbitmq_rpc_client(app)
    output: list[PricingPlanToServiceGet] = (
        await pricing_plans.list_connected_services_to_pricing_plan_by_pricing_plan(
            rpc_client, product_name=product_name, pricing_plan_id=pricing_plan_id
        )
    )
    return output


async def connect_service_to_pricing_plan(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> PricingPlanToServiceGet:
    # Check whether service key and version exists
    await catalog_service.get_service(
        app,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        product_name=product_name,
    )

    rpc_client = get_rabbitmq_rpc_client(app)
    output: PricingPlanToServiceGet = (
        await pricing_plans.connect_service_to_pricing_plan(
            rpc_client,
            product_name=product_name,
            pricing_plan_id=pricing_plan_id,
            service_key=service_key,
            service_version=service_version,
        )
    )
    return output
