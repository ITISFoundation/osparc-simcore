from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingUnitGet,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    PricingPlanId,
    PricingUnitId,
    PricingUnitWithCostCreate,
    PricingUnitWithCostUpdate,
)

from ..api.rest.dependencies import get_repository
from .modules.db.repositories.resource_tracker import ResourceTrackerRepository


async def get_pricing_unit(
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    pricing_unit_id: PricingUnitId,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
) -> PricingUnitGet:
    pricing_unit = await resource_tracker_repo.get_valid_pricing_unit(
        product_name, pricing_plan_id, pricing_unit_id
    )

    return PricingUnitGet(
        pricing_unit_id=pricing_unit.pricing_unit_id,
        unit_name=pricing_unit.unit_name,
        unit_extra_info=pricing_unit.unit_extra_info,
        current_cost_per_unit=pricing_unit.current_cost_per_unit,
        current_cost_per_unit_id=pricing_unit.current_cost_per_unit_id,
        default=pricing_unit.default,
        specific_info=pricing_unit.specific_info,
    )


async def create_pricing_unit(
    product_name: ProductName,
    data: PricingUnitWithCostCreate,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
) -> PricingUnitGet:
    # Check whether pricing plan exists
    pricing_plan_db = await resource_tracker_repo.get_pricing_plan(
        product_name=product_name, pricing_plan_id=data.pricing_plan_id
    )
    # Create new pricing unit
    pricing_unit_id, _ = await resource_tracker_repo.create_pricing_unit_with_cost(
        data=data, pricing_plan_key=pricing_plan_db.pricing_plan_key
    )

    pricing_unit = await resource_tracker_repo.get_valid_pricing_unit(
        product_name, data.pricing_plan_id, pricing_unit_id
    )
    return PricingUnitGet(
        pricing_unit_id=pricing_unit.pricing_unit_id,
        unit_name=pricing_unit.unit_name,
        unit_extra_info=pricing_unit.unit_extra_info,
        current_cost_per_unit=pricing_unit.current_cost_per_unit,
        current_cost_per_unit_id=pricing_unit.current_cost_per_unit_id,
        default=pricing_unit.default,
        specific_info=pricing_unit.specific_info,
    )


async def update_pricing_unit(
    product_name: ProductName,
    data: PricingUnitWithCostUpdate,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
) -> PricingUnitGet:
    # Check whether pricing unit exists
    await resource_tracker_repo.get_valid_pricing_unit(
        product_name, data.pricing_plan_id, data.pricing_unit_id
    )
    # Get pricing plan
    pricing_plan_db = await resource_tracker_repo.get_pricing_plan(
        product_name, data.pricing_plan_id
    )

    # Update pricing unit and cost
    await resource_tracker_repo.update_pricing_unit_with_cost(
        data=data, pricing_plan_key=pricing_plan_db.pricing_plan_key
    )

    pricing_unit = await resource_tracker_repo.get_valid_pricing_unit(
        product_name, data.pricing_plan_id, data.pricing_unit_id
    )
    return PricingUnitGet(
        pricing_unit_id=pricing_unit.pricing_unit_id,
        unit_name=pricing_unit.unit_name,
        unit_extra_info=pricing_unit.unit_extra_info,
        current_cost_per_unit=pricing_unit.current_cost_per_unit,
        current_cost_per_unit_id=pricing_unit.current_cost_per_unit_id,
        default=pricing_unit.default,
        specific_info=pricing_unit.specific_info,
    )
