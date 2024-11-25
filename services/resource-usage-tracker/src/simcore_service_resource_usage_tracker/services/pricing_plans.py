from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanGet,
    PricingPlanToServiceGet,
    PricingUnitGet,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    PricingPlanCreate,
    PricingPlanId,
    PricingPlanUpdate,
)
from models_library.services import ServiceKey, ServiceVersion
from pydantic import TypeAdapter

from ..api.rest.dependencies import get_repository
from ..exceptions.errors import PricingPlanNotFoundForServiceError
from ..models.pricing_plans import PricingPlansDB, PricingPlanToServiceDB
from ..models.pricing_units import PricingUnitsDB
from .modules.db.repositories.resource_tracker import ResourceTrackerRepository


async def _create_pricing_plan_get(
    pricing_plan_db: PricingPlansDB, pricing_plan_unit_db: list[PricingUnitsDB]
) -> PricingPlanGet:
    return PricingPlanGet(
        pricing_plan_id=pricing_plan_db.pricing_plan_id,
        display_name=pricing_plan_db.display_name,
        description=pricing_plan_db.description,
        classification=pricing_plan_db.classification,
        created_at=pricing_plan_db.created,
        pricing_plan_key=pricing_plan_db.pricing_plan_key,
        pricing_units=[
            PricingUnitGet(
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
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
) -> PricingPlanGet:
    active_service_pricing_plans = await resource_tracker_repo.list_active_service_pricing_plans_by_product_and_service(
        product_name, service_key, service_version
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

    pricing_plan_unit_db = (
        await resource_tracker_repo.list_pricing_units_by_pricing_plan(
            pricing_plan_id=default_pricing_plan.pricing_plan_id
        )
    )

    return await _create_pricing_plan_get(default_pricing_plan, pricing_plan_unit_db)


async def list_connected_services_to_pricing_plan_by_pricing_plan(
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
):
    output_list: list[
        PricingPlanToServiceDB
    ] = await resource_tracker_repo.list_connected_services_to_pricing_plan_by_pricing_plan(
        product_name=product_name, pricing_plan_id=pricing_plan_id
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
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
) -> PricingPlanToServiceGet:
    output: PricingPlanToServiceDB = (
        await resource_tracker_repo.upsert_service_to_pricing_plan(
            product_name=product_name,
            pricing_plan_id=pricing_plan_id,
            service_key=service_key,
            service_version=service_version,
        )
    )
    return TypeAdapter(PricingPlanToServiceGet).validate_python(output.model_dump())


async def list_pricing_plans_by_product(
    product_name: ProductName,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
) -> list[PricingPlanGet]:
    pricing_plans_list_db: list[
        PricingPlansDB
    ] = await resource_tracker_repo.list_pricing_plans_by_product(
        product_name=product_name
    )
    return [
        PricingPlanGet(
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
    ]


async def get_pricing_plan(
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
) -> PricingPlanGet:
    pricing_plan_db = await resource_tracker_repo.get_pricing_plan(
        product_name=product_name, pricing_plan_id=pricing_plan_id
    )
    pricing_plan_unit_db = (
        await resource_tracker_repo.list_pricing_units_by_pricing_plan(
            pricing_plan_id=pricing_plan_db.pricing_plan_id
        )
    )
    return await _create_pricing_plan_get(pricing_plan_db, pricing_plan_unit_db)


async def create_pricing_plan(
    data: PricingPlanCreate,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
) -> PricingPlanGet:
    pricing_plan_db = await resource_tracker_repo.create_pricing_plan(data=data)
    pricing_plan_unit_db = (
        await resource_tracker_repo.list_pricing_units_by_pricing_plan(
            pricing_plan_id=pricing_plan_db.pricing_plan_id
        )
    )
    return await _create_pricing_plan_get(pricing_plan_db, pricing_plan_unit_db)


async def update_pricing_plan(
    product_name: ProductName,
    data: PricingPlanUpdate,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
) -> PricingPlanGet:
    # Check whether pricing plan exists
    pricing_plan_db = await resource_tracker_repo.get_pricing_plan(
        product_name=product_name, pricing_plan_id=data.pricing_plan_id
    )
    # Update pricing plan
    pricing_plan_updated_db = await resource_tracker_repo.update_pricing_plan(
        product_name=product_name, data=data
    )
    if pricing_plan_updated_db:
        pricing_plan_db = pricing_plan_updated_db

    pricing_plan_unit_db = (
        await resource_tracker_repo.list_pricing_units_by_pricing_plan(
            pricing_plan_id=pricing_plan_db.pricing_plan_id
        )
    )
    return await _create_pricing_plan_get(pricing_plan_db, pricing_plan_unit_db)
