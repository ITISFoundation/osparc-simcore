from aiohttp import web
from models_library.api_schemas_webserver.licensed_items import (
    LicensedItemRpcGet,
    LicensedItemRpcGetPage,
    LicensedResource,
)
from models_library.api_schemas_webserver.licensed_items_checkouts import (
    LicensedItemCheckoutRpcGet,
)
from models_library.basic_types import IDStr
from models_library.licenses import LicensedItemID, LicensedItemPage
from models_library.products import ProductName
from models_library.resource_tracker_licensed_items_checkouts import (
    LicensedItemCheckoutID,
)
from models_library.rest_ordering import OrderBy
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    LICENSES_ERRORS,
    CanNotCheckoutNotEnoughAvailableSeatsError,
    CanNotCheckoutServiceIsNotRunningError,
    LicensedItemCheckoutNotFoundError,
    NotEnoughAvailableSeatsError,
)

from ..application_settings import get_application_settings
from ..rabbitmq import get_rabbitmq_rpc_server
from . import _licensed_items_checkouts_service, _licensed_items_service

router = RPCRouter()


@router.expose(reraise_if_error_type=LICENSES_ERRORS)
async def get_licensed_items(
    app: web.Application,
    *,
    product_name: ProductName,
    offset: int,
    limit: int,
) -> LicensedItemRpcGetPage:
    licensed_item_page: LicensedItemPage = (
        await _licensed_items_service.list_licensed_items(
            app=app,
            product_name=product_name,
            include_hidden_items_on_market=True,
            offset=offset,
            limit=limit,
            order_by=OrderBy(field=IDStr("display_name")),
        )
    )

    licensed_item_get_page: LicensedItemRpcGetPage = LicensedItemRpcGetPage(
        items=[
            LicensedItemRpcGet(
                licensed_item_id=licensed_item.licensed_item_id,
                key=licensed_item.key,
                version=licensed_item.version,
                display_name=licensed_item.display_name,
                licensed_resource_type=licensed_item.licensed_resource_type,
                licensed_resources=[
                    LicensedResource(**resource)
                    for resource in licensed_item.licensed_resources
                ],
                pricing_plan_id=licensed_item.pricing_plan_id,
                is_hidden_on_market=licensed_item.is_hidden_on_market,
                created_at=licensed_item.created_at,
                modified_at=licensed_item.modified_at,
            )
            for licensed_item in licensed_item_page.items
        ],
        total=licensed_item_page.total,
    )
    return licensed_item_get_page


@router.expose(reraise_if_error_type=(NotImplementedError,))
async def get_available_licensed_items_for_wallet(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    wallet_id: WalletID,
    offset: int,
    limit: int,
) -> LicensedItemRpcGetPage:
    raise NotImplementedError


@router.expose(
    reraise_if_error_type=(
        NotEnoughAvailableSeatsError,
        CanNotCheckoutNotEnoughAvailableSeatsError,
        CanNotCheckoutServiceIsNotRunningError,
    )
)
async def checkout_licensed_item_for_wallet(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    wallet_id: WalletID,
    licensed_item_id: LicensedItemID,
    num_of_seats: int,
    service_run_id: ServiceRunID,
) -> LicensedItemCheckoutRpcGet:
    licensed_item_get = (
        await _licensed_items_checkouts_service.checkout_licensed_item_for_wallet(
            app,
            wallet_id=wallet_id,
            product_name=product_name,
            licensed_item_id=licensed_item_id,
            num_of_seats=num_of_seats,
            service_run_id=service_run_id,
            user_id=user_id,
        )
    )
    return LicensedItemCheckoutRpcGet.model_construct(
        licensed_item_checkout_id=licensed_item_get.licensed_item_checkout_id,
        licensed_item_id=licensed_item_get.licensed_item_id,
        key=licensed_item_get.key,
        version=licensed_item_get.version,
        wallet_id=licensed_item_get.wallet_id,
        user_id=licensed_item_get.user_id,
        product_name=licensed_item_get.product_name,
        started_at=licensed_item_get.started_at,
        stopped_at=licensed_item_get.stopped_at,
        num_of_seats=licensed_item_get.num_of_seats,
    )


@router.expose(reraise_if_error_type=(LicensedItemCheckoutNotFoundError,))
async def release_licensed_item_for_wallet(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    licensed_item_checkout_id: LicensedItemCheckoutID,
) -> LicensedItemCheckoutRpcGet:
    licensed_item_get = (
        await _licensed_items_checkouts_service.release_licensed_item_for_wallet(
            app,
            product_name=product_name,
            user_id=user_id,
            licensed_item_checkout_id=licensed_item_checkout_id,
        )
    )
    return LicensedItemCheckoutRpcGet.model_construct(
        licensed_item_checkout_id=licensed_item_get.licensed_item_checkout_id,
        licensed_item_id=licensed_item_get.licensed_item_id,
        key=licensed_item_get.key,
        version=licensed_item_get.version,
        wallet_id=licensed_item_get.wallet_id,
        user_id=licensed_item_get.user_id,
        product_name=licensed_item_get.product_name,
        started_at=licensed_item_get.started_at,
        stopped_at=licensed_item_get.stopped_at,
        num_of_seats=licensed_item_get.num_of_seats,
    )


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    settings = get_application_settings(app)
    if not settings.WEBSERVER_RPC_NAMESPACE:
        msg = "RPC namespace is not configured"
        raise ValueError(msg)

    await rpc_server.register_router(router, settings.WEBSERVER_RPC_NAMESPACE, app)
