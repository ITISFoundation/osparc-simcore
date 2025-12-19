from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanToServiceGet,
    RutPricingPlanGet,
    RutPricingPlanPage,
    RutPricingUnitGet,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    PricingPlanCreate,
    PricingPlanId,
    PricingPlanUpdate,
)
from models_library.services import ServiceKey, ServiceVersion
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncEngine

from ..api.rest.dependencies import get_resource_tracker_db_engine
from ..exceptions.errors import PricingPlanNotFoundForServiceError
from ..models.pricing_plans import PricingPlansDB, PricingPlanToServiceDB
from ..models.pricing_units import PricingUnitsDB
from .modules.db import pricing_plans_db


async def _create_pricing_plan_get(
    pricing_plan_db: PricingPlansDB, pricing_plan_unit_db: list[PricingUnitsDB]
) -> RutPricingPlanGet:
    return RutPricingPlanGet(
        pricing_plan_id=pricing_plan_db.pricing_plan_id,
        display_name=pricing_plan_db.display_name,
        description=pricing_plan_db.description,
        classification=pricing_plan_db.classification,
        created_at=pricing_plan_db.created,
        pricing_plan_key=pricing_plan_db.pricing_plan_key,
        pricing_units=[
            RutPricingUnitGet(
                pricing_unit_id=unit.pricing_unit_id,
                unit_name=unit.unit_name,
                unit_extra_info=unit.unit_extra_info,
                current_cost_per_unit=unit.current_cost_per_unit,
                current_cost_per_unit_id=unit.current_cost_per_unit_id,
                default=unit.default,
                specific_info=unit.specific_info,
            )
            for unit in pricing_plan_unit_db
        ],
        is_active=pricing_plan_db.is_active,
    )


async def get_service_default_pricing_plan(
    product_name: ProductName,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
) -> RutPricingPlanGet:
    active_service_pricing_plans = (
        await pricing_plans_db.list_active_service_pricing_plans_by_product_and_service(
            db_engine,
            product_name=product_name,
            service_key=service_key,
            service_version=service_version,
        )
    )

    default_pricing_plan = None
    for active_service_pricing_plan in active_service_pricing_plans:
        if active_service_pricing_plan.service_default_plan is True:
            default_pricing_plan = active_service_pricing_plan
            break

    if default_pricing_plan is None:
        raise PricingPlanNotFoundForServiceError(
            service_key=service_key, service_version=service_version
        )

    pricing_plan_unit_db = await pricing_plans_db.list_pricing_units_by_pricing_plan(
        db_engine, pricing_plan_id=default_pricing_plan.pricing_plan_id
    )

    return await _create_pricing_plan_get(default_pricing_plan, pricing_plan_unit_db)


async def list_connected_services_to_pricing_plan_by_pricing_plan(
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
):
    output_list: list[
        PricingPlanToServiceDB
    ] = await pricing_plans_db.list_connected_services_to_pricing_plan_by_pricing_plan(
        db_engine, product_name=product_name, pricing_plan_id=pricing_plan_id
    )
    return [
        TypeAdapter(PricingPlanToServiceGet).validate_python(item.model_dump())
        for item in output_list
    ]


async def connect_service_to_pricing_plan(
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
) -> PricingPlanToServiceGet:
    output: PricingPlanToServiceDB = (
        await pricing_plans_db.upsert_service_to_pricing_plan(
            db_engine,
            product_name=product_name,
            pricing_plan_id=pricing_plan_id,
            service_key=service_key,
            service_version=service_version,
        )
    )
    return TypeAdapter(PricingPlanToServiceGet).validate_python(output.model_dump())


async def list_pricing_plans_without_pricing_units(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    product_name: ProductName,
    exclude_inactive: bool,
    # pagination
    offset: int,
    limit: int,
) -> RutPricingPlanPage:
    total, pricing_plans_list_db = await pricing_plans_db.list_pricing_plans_by_product(
        db_engine,
        product_name=product_name,
        exclude_inactive=exclude_inactive,
        offset=offset,
        limit=limit,
    )
    return RutPricingPlanPage(
        items=[
            RutPricingPlanGet(
                pricing_plan_id=pricing_plan_db.pricing_plan_id,
                display_name=pricing_plan_db.display_name,
                description=pricing_plan_db.description,
                classification=pricing_plan_db.classification,
                created_at=pricing_plan_db.created,
                pricing_plan_key=pricing_plan_db.pricing_plan_key,
                pricing_units=None,
                is_active=pricing_plan_db.is_active,
            )
            for pricing_plan_db in pricing_plans_list_db
        ],
        total=total,
    )


async def get_pricing_plan(
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
) -> RutPricingPlanGet:
    pricing_plan_db = await pricing_plans_db.get_pricing_plan(
        db_engine, product_name=product_name, pricing_plan_id=pricing_plan_id
    )
    pricing_plan_unit_db = await pricing_plans_db.list_pricing_units_by_pricing_plan(
        db_engine, pricing_plan_id=pricing_plan_db.pricing_plan_id
    )
    return await _create_pricing_plan_get(pricing_plan_db, pricing_plan_unit_db)


async def create_pricing_plan(
    data: PricingPlanCreate,
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
) -> RutPricingPlanGet:
    pricing_plan_db = await pricing_plans_db.create_pricing_plan(db_engine, data=data)
    pricing_plan_unit_db = await pricing_plans_db.list_pricing_units_by_pricing_plan(
        db_engine, pricing_plan_id=pricing_plan_db.pricing_plan_id
    )
    return await _create_pricing_plan_get(pricing_plan_db, pricing_plan_unit_db)


async def update_pricing_plan(
    product_name: ProductName,
    data: PricingPlanUpdate,
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
) -> RutPricingPlanGet:
    # Check whether pricing plan exists
    pricing_plan_db = await pricing_plans_db.get_pricing_plan(
        db_engine, product_name=product_name, pricing_plan_id=data.pricing_plan_id
    )
    # Update pricing plan
    pricing_plan_updated_db = await pricing_plans_db.update_pricing_plan(
        db_engine, product_name=product_name, data=data
    )
    if pricing_plan_updated_db:
        pricing_plan_db = pricing_plan_updated_db

    pricing_plan_unit_db = await pricing_plans_db.list_pricing_units_by_pricing_plan(
        db_engine, pricing_plan_id=pricing_plan_db.pricing_plan_id
    )
    return await _create_pricing_plan_get(pricing_plan_db, pricing_plan_unit_db)
