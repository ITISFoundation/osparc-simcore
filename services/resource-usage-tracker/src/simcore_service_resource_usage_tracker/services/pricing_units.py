from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    RutPricingUnitGet,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    PricingPlanId,
    PricingUnitId,
    PricingUnitWithCostCreate,
    PricingUnitWithCostUpdate,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from ..api.rest.dependencies import get_resource_tracker_db_engine
from .modules.db import pricing_plans_db


async def get_pricing_unit(
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    pricing_unit_id: PricingUnitId,
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
) -> RutPricingUnitGet:
    pricing_unit = await pricing_plans_db.get_valid_pricing_unit(
        db_engine,
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
        pricing_unit_id=pricing_unit_id,
    )

    return RutPricingUnitGet(
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
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
) -> RutPricingUnitGet:
    # Check whether pricing plan exists
    pricing_plan_db = await pricing_plans_db.get_pricing_plan(
        db_engine, product_name=product_name, pricing_plan_id=data.pricing_plan_id
    )
    # Create new pricing unit
    pricing_unit_id, _ = await pricing_plans_db.create_pricing_unit_with_cost(
        db_engine, data=data, pricing_plan_key=pricing_plan_db.pricing_plan_key
    )

    pricing_unit = await pricing_plans_db.get_valid_pricing_unit(
        db_engine,
        product_name=product_name,
        pricing_plan_id=data.pricing_plan_id,
        pricing_unit_id=pricing_unit_id,
    )
    return RutPricingUnitGet(
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
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
) -> RutPricingUnitGet:
    # Check whether pricing unit exists
    await pricing_plans_db.get_valid_pricing_unit(
        db_engine,
        product_name=product_name,
        pricing_plan_id=data.pricing_plan_id,
        pricing_unit_id=data.pricing_unit_id,
    )
    # Get pricing plan
    pricing_plan_db = await pricing_plans_db.get_pricing_plan(
        db_engine, product_name=product_name, pricing_plan_id=data.pricing_plan_id
    )

    # Update pricing unit and cost
    await pricing_plans_db.update_pricing_unit_with_cost(
        db_engine, data=data, pricing_plan_key=pricing_plan_db.pricing_plan_key
    )

    pricing_unit = await pricing_plans_db.get_valid_pricing_unit(
        db_engine,
        product_name=product_name,
        pricing_plan_id=data.pricing_plan_id,
        pricing_unit_id=data.pricing_unit_id,
    )
    return RutPricingUnitGet(
        pricing_unit_id=pricing_unit.pricing_unit_id,
        unit_name=pricing_unit.unit_name,
        unit_extra_info=pricing_unit.unit_extra_info,
        current_cost_per_unit=pricing_unit.current_cost_per_unit,
        current_cost_per_unit_id=pricing_unit.current_cost_per_unit_id,
        default=pricing_unit.default,
        specific_info=pricing_unit.specific_info,
    )
