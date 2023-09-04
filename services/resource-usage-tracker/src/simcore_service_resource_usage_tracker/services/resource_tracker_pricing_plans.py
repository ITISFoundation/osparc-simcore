from typing import Annotated

from fastapi import Depends, Query
from models_library.api_schemas_webserver.resource_usage import (
    PricingDetailMinimalGet,
    PricingPlanGet,
)
from models_library.products import ProductName
from models_library.services import ServiceKey, ServiceVersion

from ..api.dependencies import get_repository
from ..modules.db.repositories.resource_tracker import ResourceTrackerRepository


async def _list_pricing_plans_by_product(
    resource_tracker_repo: ResourceTrackerRepository, product_name: ProductName
) -> list[PricingPlanGet]:
    list_of_pricing_plan_get = []
    active_pricing_plans = (
        await resource_tracker_repo.list_active_pricing_plans_by_product(product_name)
    )
    for active_pricing_plan in active_pricing_plans:
        list_of_pricing_detail_db = (
            await resource_tracker_repo.list_pricing_details_by_pricing_plan(
                active_pricing_plan.pricing_plan_id
            )
        )
        list_of_pricing_plan_get.append(
            PricingPlanGet(
                pricing_plan_id=active_pricing_plan.pricing_plan_id,
                name=active_pricing_plan.name,
                description=active_pricing_plan.description,
                classification=active_pricing_plan.classification,
                created_at=active_pricing_plan.created,
                details=[
                    PricingDetailMinimalGet(
                        pricing_detail_id=detail.pricing_detail_id,
                        unit_name=detail.unit_name,
                        cost_per_unit=detail.cost_per_unit,
                        valid_from=detail.valid_from,
                        simcore_default=detail.simcore_default,
                    )
                    for detail in list_of_pricing_detail_db
                ],
            )
        )
    return list_of_pricing_plan_get


async def _list_pricing_plans_by_product_and_service(
    resource_tracker_repo: ResourceTrackerRepository,
    product_name: ProductName,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> list[PricingPlanGet]:
    # NOTE: Currently user service can have only one pricing plan.
    # Therefore the list should contain only one item!
    # The reason for this was so I can reuse the same endpoint.
    pricing_plan_id = (
        await resource_tracker_repo.get_pricing_plan_by_product_and_service(
            product_name, service_key, service_version
        )
    )
    if pricing_plan_id is None:
        raise ValueError

    pricing_plan_db = await resource_tracker_repo.get_pricing_plan(pricing_plan_id)
    list_of_pricing_detail_db = (
        await resource_tracker_repo.list_pricing_details_by_pricing_plan(
            pricing_plan_db.pricing_plan_id
        )
    )
    return [
        PricingPlanGet(
            pricing_plan_id=pricing_plan_db.pricing_plan_id,
            name=pricing_plan_db.name,
            description=pricing_plan_db.description,
            classification=pricing_plan_db.classification,
            created_at=pricing_plan_db.created,
            details=[
                PricingDetailMinimalGet(
                    pricing_detail_id=detail.pricing_detail_id,
                    unit_name=detail.unit_name,
                    cost_per_unit=detail.cost_per_unit,
                    valid_from=detail.valid_from,
                    simcore_default=detail.simcore_default,
                )
                for detail in list_of_pricing_detail_db
            ],
        )
    ]


async def list_pricing_plans(
    product_name: ProductName,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
    service_key: ServiceKey = Query(None),
    service_version: ServiceVersion = Query(None),
) -> list[PricingPlanGet]:
    if service_key is None and service_version is None:
        return await _list_pricing_plans_by_product(resource_tracker_repo, product_name)
    else:
        return await _list_pricing_plans_by_product_and_service(
            resource_tracker_repo, product_name, service_key, service_version
        )
