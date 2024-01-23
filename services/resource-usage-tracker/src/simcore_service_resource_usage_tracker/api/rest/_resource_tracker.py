import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi_pagination.api import create_page
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    CreditTransactionCreated,
    WalletTotalCredits,
)
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingUnitGet,
    ServicePricingPlanGet,
)
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    ServiceRunGet,
    ServiceRunPage,
)
from models_library.products import ProductName
from models_library.resource_tracker import CreditTransactionId
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import AnyUrl
from simcore_service_resource_usage_tracker.api.rest.dependencies import get_repository
from simcore_service_resource_usage_tracker.modules.db.repositories.resource_tracker import (
    ResourceTrackerRepository,
)

from ...core.settings import ApplicationSettings
from ...models.pagination import LimitOffsetPage, LimitOffsetParamsWithDefault
from ...modules.s3 import get_s3_client
from ...services import (
    resource_tracker_credit_transactions,
    resource_tracker_pricing_plans,
    resource_tracker_service_runs,
)

_logger = logging.getLogger(__name__)


router = APIRouter()


########
# USAGE
########


@router.get(
    "/services/-/usages",
    response_model=LimitOffsetPage[ServiceRunGet],
    operation_id="list_usage_services",
    description="Returns a list of tracked containers for a given user and product",
    tags=["usages"],
)
async def list_usage_services(
    page_params: Annotated[LimitOffsetParamsWithDefault, Depends()],
    user_id: UserID,
    product_name: ProductName,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
    wallet_id: Annotated[WalletID | None, Query()] = None,
    access_all_wallet_usage: Annotated[bool, Query()] = False,
):
    usage_services_page: ServiceRunPage = (
        await resource_tracker_service_runs.list_service_runs(
            user_id=user_id,
            product_name=product_name,
            resource_tracker_repo=resource_tracker_repo,
            limit=page_params.limit,
            offset=page_params.offset,
            wallet_id=wallet_id,
            access_all_wallet_usage=access_all_wallet_usage,
        )
    )

    return create_page(
        usage_services_page.items,
        total=usage_services_page.total,
        params=page_params,
    )


@router.get(
    "/services/-/usages/presigned-link",
    response_model=AnyUrl,
    operation_id="get_usages_presigned_link",
    description="Return presigned-link",
    tags=["usages"],
)
async def get_usages_presigned_link(
    request: Request,
    user_id: UserID,
    product_name: ProductName,
    resource_tracker_repo: Annotated[
        ResourceTrackerRepository, Depends(get_repository(ResourceTrackerRepository))
    ],
    wallet_id: Annotated[WalletID | None, Query()] = None,
    access_all_wallet_usage: Annotated[bool, Query()] = False,
):
    app_settings: ApplicationSettings = request.app.state.settings
    s3_settings = app_settings.RESOURCE_USAGE_TRACKER_S3
    assert s3_settings  # nosec

    return await resource_tracker_service_runs.export_service_runs(
        s3_client=get_s3_client(request.app),
        bucket_name=f"{s3_settings.S3_BUCKET_NAME}",
        user_id=user_id,
        product_name=product_name,
        resource_tracker_repo=resource_tracker_repo,
        wallet_id=wallet_id,
        access_all_wallet_usage=access_all_wallet_usage,
    )


######################
# CREDIT TRANSACTIONS
######################


@router.post(
    "/credit-transactions/credits:sum",
    response_model=WalletTotalCredits,
    summary="Sum total available credits in the wallet",
    tags=["credit-transactions"],
)
async def get_credit_transactions_sum(
    wallet_total_credits: Annotated[
        WalletTotalCredits,
        Depends(
            resource_tracker_credit_transactions.sum_credit_transactions_by_product_and_wallet
        ),
    ],
):
    return wallet_total_credits


@router.post(
    "/credit-transactions",
    response_model=CreditTransactionCreated,
    summary="Top up credits for specific wallet",
    status_code=status.HTTP_201_CREATED,
    tags=["credit-transactions"],
)
async def create_credit_transaction(
    transaction_id: Annotated[
        CreditTransactionId,
        Depends(resource_tracker_credit_transactions.create_credit_transaction),
    ],
):
    return {"credit_transaction_id": transaction_id}


################
# PRICING PLANS
################


@router.get(
    "/services/{service_key:path}/{service_version}/pricing-plan",
    response_model=ServicePricingPlanGet,
    operation_id="get_service_default_pricing_plan",
    description="Returns a default pricing plan with pricing details for a specified service",
    tags=["pricing-plans"],
)
async def get_service_default_pricing_plan(
    service_pricing_plans: Annotated[
        ServicePricingPlanGet,
        Depends(resource_tracker_pricing_plans.get_service_default_pricing_plan),
    ],
):
    return service_pricing_plans


@router.get(
    "/pricing-plans/{pricing_plan_id}/pricing-units/{pricing_unit_id}",
    response_model=PricingUnitGet,
    operation_id="list_service_pricing_plans",
    description="Returns a list of service pricing plans with pricing details for a specified service",
    tags=["pricing-plans"],
)
async def get_pricing_plan_unit(
    pricing_unit: Annotated[
        PricingUnitGet,
        Depends(resource_tracker_pricing_plans.get_pricing_unit),
    ]
):
    return pricing_unit
