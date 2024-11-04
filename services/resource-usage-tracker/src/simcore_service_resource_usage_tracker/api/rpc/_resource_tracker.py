from fastapi import FastAPI
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanGet,
    PricingPlanToServiceGet,
    PricingUnitGet,
)
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    OsparcCreditsAggregatedUsagesPage,
    ServiceRunPage,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    PricingPlanCreate,
    PricingPlanId,
    PricingPlanUpdate,
    PricingUnitId,
    PricingUnitWithCostCreate,
    PricingUnitWithCostUpdate,
    ServiceResourceUsagesFilters,
    ServicesAggregatedUsagesTimePeriod,
    ServicesAggregatedUsagesType,
)
from models_library.rest_ordering import OrderBy
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import AnyUrl
from servicelib.rabbitmq import RPCRouter

from ...core.settings import ApplicationSettings
from ...services import pricing_plans, pricing_units, service_runs
from ...services.modules.db.repositories.resource_tracker import (
    ResourceTrackerRepository,
)
from ...services.modules.s3 import get_s3_client

router = RPCRouter()


## Service runs


@router.expose(reraise_if_error_type=())
async def get_service_run_page(
    app: FastAPI,
    *,
    user_id: UserID,
    product_name: ProductName,
    limit: int = 20,
    offset: int = 0,
    wallet_id: WalletID | None = None,
    access_all_wallet_usage: bool = False,
    order_by: OrderBy | None = None,
    filters: ServiceResourceUsagesFilters | None = None,
) -> ServiceRunPage:
    return await service_runs.list_service_runs(
        user_id=user_id,
        product_name=product_name,
        resource_tracker_repo=ResourceTrackerRepository(db_engine=app.state.engine),
        limit=limit,
        offset=offset,
        wallet_id=wallet_id,
        access_all_wallet_usage=access_all_wallet_usage,
        order_by=order_by,
        filters=filters,
    )


@router.expose(reraise_if_error_type=())
async def export_service_runs(
    app: FastAPI,
    *,
    user_id: UserID,
    product_name: ProductName,
    wallet_id: WalletID | None = None,
    access_all_wallet_usage: bool = False,
    order_by: OrderBy | None = None,
    filters: ServiceResourceUsagesFilters | None = None,
) -> AnyUrl:
    app_settings: ApplicationSettings = app.state.settings
    s3_settings = app_settings.RESOURCE_USAGE_TRACKER_S3
    assert s3_settings  # nosec

    return await service_runs.export_service_runs(
        s3_client=get_s3_client(app),
        bucket_name=f"{s3_settings.S3_BUCKET_NAME}",
        s3_region=s3_settings.S3_REGION,
        user_id=user_id,
        product_name=product_name,
        resource_tracker_repo=ResourceTrackerRepository(db_engine=app.state.engine),
        wallet_id=wallet_id,
        access_all_wallet_usage=access_all_wallet_usage,
        order_by=order_by,
        filters=filters,
    )


@router.expose(reraise_if_error_type=())
async def get_osparc_credits_aggregated_usages_page(
    app: FastAPI,
    *,
    user_id: UserID,
    product_name: ProductName,
    aggregated_by: ServicesAggregatedUsagesType,
    time_period: ServicesAggregatedUsagesTimePeriod,
    limit: int = 20,
    offset: int = 0,
    wallet_id: WalletID,
    access_all_wallet_usage: bool = False,
) -> OsparcCreditsAggregatedUsagesPage:
    return await service_runs.get_osparc_credits_aggregated_usages_page(
        user_id=user_id,
        product_name=product_name,
        resource_tracker_repo=ResourceTrackerRepository(db_engine=app.state.engine),
        aggregated_by=aggregated_by,
        time_period=time_period,
        limit=limit,
        offset=offset,
        wallet_id=wallet_id,
        access_all_wallet_usage=access_all_wallet_usage,
    )


## Pricing plans


@router.expose(reraise_if_error_type=())
async def get_pricing_plan(
    app: FastAPI,
    *,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
) -> PricingPlanGet:
    return await pricing_plans.get_pricing_plan(
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
        resource_tracker_repo=ResourceTrackerRepository(db_engine=app.state.engine),
    )


@router.expose(reraise_if_error_type=())
async def list_pricing_plans(
    app: FastAPI,
    *,
    product_name: ProductName,
) -> list[PricingPlanGet]:
    return await pricing_plans.list_pricing_plans_by_product(
        product_name=product_name,
        resource_tracker_repo=ResourceTrackerRepository(db_engine=app.state.engine),
    )


@router.expose(reraise_if_error_type=())
async def create_pricing_plan(
    app: FastAPI,
    *,
    data: PricingPlanCreate,
) -> PricingPlanGet:
    return await pricing_plans.create_pricing_plan(
        data=data,
        resource_tracker_repo=ResourceTrackerRepository(db_engine=app.state.engine),
    )


@router.expose(reraise_if_error_type=())
async def update_pricing_plan(
    app: FastAPI,
    *,
    product_name: ProductName,
    data: PricingPlanUpdate,
) -> PricingPlanGet:
    return await pricing_plans.update_pricing_plan(
        product_name=product_name,
        data=data,
        resource_tracker_repo=ResourceTrackerRepository(db_engine=app.state.engine),
    )


## Pricing units


@router.expose(reraise_if_error_type=())
async def get_pricing_unit(
    app: FastAPI,
    *,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    pricing_unit_id: PricingUnitId,
) -> PricingUnitGet:
    return await pricing_units.get_pricing_unit(
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
        pricing_unit_id=pricing_unit_id,
        resource_tracker_repo=ResourceTrackerRepository(db_engine=app.state.engine),
    )


@router.expose(reraise_if_error_type=())
async def create_pricing_unit(
    app: FastAPI,
    *,
    product_name: ProductName,
    data: PricingUnitWithCostCreate,
) -> PricingUnitGet:
    return await pricing_units.create_pricing_unit(
        product_name=product_name,
        data=data,
        resource_tracker_repo=ResourceTrackerRepository(db_engine=app.state.engine),
    )


@router.expose(reraise_if_error_type=())
async def update_pricing_unit(
    app: FastAPI,
    *,
    product_name: ProductName,
    data: PricingUnitWithCostUpdate,
) -> PricingUnitGet:
    return await pricing_units.update_pricing_unit(
        product_name=product_name,
        data=data,
        resource_tracker_repo=ResourceTrackerRepository(db_engine=app.state.engine),
    )


## Pricing plan to service


@router.expose(reraise_if_error_type=())
async def list_connected_services_to_pricing_plan_by_pricing_plan(
    app: FastAPI,
    *,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
) -> list[PricingPlanToServiceGet]:
    output: list[
        PricingPlanToServiceGet
    ] = await pricing_plans.list_connected_services_to_pricing_plan_by_pricing_plan(
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
        resource_tracker_repo=ResourceTrackerRepository(db_engine=app.state.engine),
    )
    return output


@router.expose(reraise_if_error_type=())
async def connect_service_to_pricing_plan(
    app: FastAPI,
    *,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> PricingPlanToServiceGet:
    return await pricing_plans.connect_service_to_pricing_plan(
        product_name=product_name,
        pricing_plan_id=pricing_plan_id,
        service_key=service_key,
        service_version=service_version,
        resource_tracker_repo=ResourceTrackerRepository(db_engine=app.state.engine),
    )
