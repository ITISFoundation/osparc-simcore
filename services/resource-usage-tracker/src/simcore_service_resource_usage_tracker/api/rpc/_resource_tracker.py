from fastapi import FastAPI
from models_library.api_schemas_resource_usage_tracker.service_runs import (
    ServiceRunPage,
)
from models_library.products import ProductName
from models_library.resource_tracker import ServiceResourceUsagesFilters
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    CustomResourceUsageTrackerError,
)

from ...modules.db.repositories.resource_tracker import ResourceTrackerRepository
from ...services.resource_tracker_service_runs import list_service_runs

router = RPCRouter()


@router.expose(reraise_if_error_type=(CustomResourceUsageTrackerError,))
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
    filters: ServiceResourceUsagesFilters | None = None
) -> ServiceRunPage:
    return await list_service_runs(
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
