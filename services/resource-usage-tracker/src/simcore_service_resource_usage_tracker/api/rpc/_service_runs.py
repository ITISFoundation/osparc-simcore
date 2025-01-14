from fastapi import FastAPI
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    OsparcCreditsAggregatedUsagesPage,
    ServiceRunPage,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.resource_tracker import (
    CreditTransactionStatus,
    ServiceResourceUsagesFilters,
    ServicesAggregatedUsagesTimePeriod,
    ServicesAggregatedUsagesType,
)
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import AnyUrl
from servicelib.rabbitmq import RPCRouter

from ...core.settings import ApplicationSettings
from ...services import service_runs
from ...services.modules.s3 import get_s3_client

router = RPCRouter()


## Service runs


@router.expose(reraise_if_error_type=())
async def get_service_run_page(
    app: FastAPI,
    *,
    user_id: UserID,
    product_name: ProductName,
    wallet_id: WalletID | None = None,
    access_all_wallet_usage: bool = False,
    filters: ServiceResourceUsagesFilters | None = None,
    transaction_status: CreditTransactionStatus | None = None,
    project_id: ProjectID | None = None,
    # pagination
    offset: int = 0,
    limit: int = 20,
    # ordering
    order_by: OrderBy | None = None,
) -> ServiceRunPage:
    return await service_runs.list_service_runs(
        db_engine=app.state.engine,
        user_id=user_id,
        product_name=product_name,
        wallet_id=wallet_id,
        access_all_wallet_usage=access_all_wallet_usage,
        filters=filters,
        transaction_status=transaction_status,
        project_id=project_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
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
        db_engine=app.state.engine,
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
        db_engine=app.state.engine,
        aggregated_by=aggregated_by,
        time_period=time_period,
        limit=limit,
        offset=offset,
        wallet_id=wallet_id,
        access_all_wallet_usage=access_all_wallet_usage,
    )
