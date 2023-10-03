from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingUnitGet,
    ServicePricingPlanGet,
)
from models_library.products import ProductName
from models_library.resource_tracker import PricingPlanId, PricingUnitId
from models_library.services import ServiceKey, ServiceVersion

from ..api.dependencies import get_repository
from ..core.errors import ResourceUsageTrackerCustomRuntimeError
from ..modules.db.repositories.resource_tracker import ResourceTrackerRepository


async def get_service_default_pricing_plan(
    product_name: ProductName,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
) -> ServicePricingPlanGet:
    active_service_pricing_plans = await resource_tracker_repo.list_active_service_pricing_plans_by_product_and_service(
        product_name, service_key, service_version
    )

    default_pricing_plan = None
    for active_service_pricing_plan in active_service_pricing_plans:
        if active_service_pricing_plan.service_default_plan is True:
            default_pricing_plan = active_service_pricing_plan
            break

    if default_pricing_plan is None:
        raise ResourceUsageTrackerCustomRuntimeError(
            msg="No default pricing plan for the specified service"
        )

    pricing_plan_unit_db = (
        await resource_tracker_repo.list_pricing_units_by_pricing_plan(
            pricing_plan_id=default_pricing_plan.pricing_plan_id
        )
    )

    return ServicePricingPlanGet(
        pricing_plan_id=default_pricing_plan.pricing_plan_id,
        display_name=default_pricing_plan.display_name,
        description=default_pricing_plan.description,
        classification=default_pricing_plan.classification,
        created_at=default_pricing_plan.created,
        pricing_plan_key=default_pricing_plan.pricing_plan_key,
        pricing_units=[
            PricingUnitGet(
                pricing_unit_id=unit.pricing_unit_id,
                unit_name=unit.unit_name,
                current_cost_per_unit=unit.current_cost_per_unit,
                current_cost_per_unit_id=unit.current_cost_per_unit_id,
                default=unit.default,
                specific_info=unit.specific_info,
            )
            for unit in pricing_plan_unit_db
        ],
    )


async def get_pricing_unit(
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    pricing_unit_id: PricingUnitId,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
) -> PricingUnitGet:
    pricing_unit = await resource_tracker_repo.get_pricing_unit(
        product_name, pricing_plan_id, pricing_unit_id
    )

    return PricingUnitGet(
        pricing_unit_id=pricing_unit.pricing_unit_id,
        unit_name=pricing_unit.unit_name,
        current_cost_per_unit=pricing_unit.current_cost_per_unit,
        current_cost_per_unit_id=pricing_unit.current_cost_per_unit_id,
        default=pricing_unit.default,
        specific_info=pricing_unit.specific_info,
    )
