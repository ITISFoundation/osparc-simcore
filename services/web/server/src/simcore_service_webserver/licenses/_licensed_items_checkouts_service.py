from aiohttp import web
from models_library.api_schemas_resource_usage_tracker import (
    licensed_items_checkouts as rut_licensed_items_checkouts,
)
from models_library.licenses import LicensedItemID
from models_library.products import ProductName
from models_library.resource_tracker_licensed_items_checkouts import (
    LicensedItemCheckoutID,
)
from models_library.rest_ordering import OrderBy
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    licensed_items_checkouts,
)

from ..rabbitmq import get_rabbitmq_rpc_client
from ..users import users_service
from ..wallets.api import get_wallet_by_user
from . import _licensed_items_repository
from ._licensed_items_checkouts_models import (
    LicensedItemCheckoutGet,
    LicensedItemCheckoutGetPage,
)


async def list_licensed_items_checkouts_for_wallet(
    app: web.Application,
    *,
    # access context
    product_name: ProductName,
    user_id: UserID,
    wallet_id: WalletID,
    offset: int,
    limit: int,
    order_by: OrderBy,
) -> LicensedItemCheckoutGetPage:
    # Check whether user has access to the wallet
    await get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
        product_name=product_name,
    )

    rpc_client = get_rabbitmq_rpc_client(app)

    result = await licensed_items_checkouts.get_licensed_items_checkouts_page(
        rpc_client,
        product_name=product_name,
        filter_wallet_id=wallet_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )

    return LicensedItemCheckoutGetPage(
        total=result.total,
        items=[
            LicensedItemCheckoutGet.model_construct(
                licensed_item_checkout_id=checkout_item.licensed_item_checkout_id,
                licensed_item_id=checkout_item.licensed_item_id,
                key=checkout_item.key,
                version=checkout_item.version,
                wallet_id=checkout_item.wallet_id,
                user_id=checkout_item.user_id,
                user_email=checkout_item.user_email,
                product_name=checkout_item.product_name,
                started_at=checkout_item.started_at,
                stopped_at=checkout_item.stopped_at,
                num_of_seats=checkout_item.num_of_seats,
            )
            for checkout_item in result.items
        ],
    )


async def get_licensed_item_checkout(
    app: web.Application,
    *,
    # access context
    product_name: ProductName,
    user_id: UserID,
    licensed_item_checkout_id: LicensedItemCheckoutID,
) -> LicensedItemCheckoutGet:
    rpc_client = get_rabbitmq_rpc_client(app)

    checkout_item = await licensed_items_checkouts.get_licensed_item_checkout(
        rpc_client,
        product_name=product_name,
        licensed_item_checkout_id=licensed_item_checkout_id,
    )

    # Check whether user has access to the wallet
    await get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=checkout_item.wallet_id,
        product_name=product_name,
    )

    return LicensedItemCheckoutGet.model_construct(
        licensed_item_checkout_id=checkout_item.licensed_item_checkout_id,
        licensed_item_id=checkout_item.licensed_item_id,
        key=checkout_item.key,
        version=checkout_item.version,
        wallet_id=checkout_item.wallet_id,
        user_id=checkout_item.user_id,
        user_email=checkout_item.user_email,
        product_name=checkout_item.product_name,
        started_at=checkout_item.started_at,
        stopped_at=checkout_item.stopped_at,
        num_of_seats=checkout_item.num_of_seats,
    )


async def checkout_licensed_item_for_wallet(
    app: web.Application,
    *,
    # access context
    product_name: ProductName,
    wallet_id: WalletID,
    user_id: UserID,
    # checkout args
    licensed_item_id: LicensedItemID,
    num_of_seats: int,
    service_run_id: ServiceRunID,
) -> LicensedItemCheckoutGet:
    # Check whether user has access to the wallet
    await get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
        product_name=product_name,
    )

    user = await users_service.get_user(app, user_id=user_id)

    licensed_item_db = await _licensed_items_repository.get(
        app, licensed_item_id=licensed_item_id, product_name=product_name
    )

    rpc_client = get_rabbitmq_rpc_client(app)
    licensed_item_get: rut_licensed_items_checkouts.LicensedItemCheckoutGet = (
        await licensed_items_checkouts.checkout_licensed_item(
            rpc_client,
            licensed_item_id=licensed_item_db.licensed_item_id,
            key=licensed_item_db.key,
            version=licensed_item_db.version,
            wallet_id=wallet_id,
            product_name=product_name,
            num_of_seats=num_of_seats,
            service_run_id=service_run_id,
            user_id=user_id,
            user_email=user["email"],
        )
    )

    return LicensedItemCheckoutGet.model_construct(
        licensed_item_checkout_id=licensed_item_get.licensed_item_checkout_id,
        licensed_item_id=licensed_item_get.licensed_item_id,
        key=licensed_item_get.key,
        version=licensed_item_get.version,
        wallet_id=licensed_item_get.wallet_id,
        user_id=licensed_item_get.user_id,
        user_email=licensed_item_get.user_email,
        product_name=licensed_item_get.product_name,
        started_at=licensed_item_get.started_at,
        stopped_at=licensed_item_get.stopped_at,
        num_of_seats=licensed_item_get.num_of_seats,
    )


async def release_licensed_item_for_wallet(
    app: web.Application,
    *,
    # access context
    product_name: ProductName,
    user_id: UserID,
    # release args
    licensed_item_checkout_id: LicensedItemCheckoutID,
) -> LicensedItemCheckoutGet:
    rpc_client = get_rabbitmq_rpc_client(app)

    checkout_item = await licensed_items_checkouts.get_licensed_item_checkout(
        rpc_client,
        product_name=product_name,
        licensed_item_checkout_id=licensed_item_checkout_id,
    )

    # Check whether user has access to the wallet
    await get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=checkout_item.wallet_id,
        product_name=product_name,
    )

    licensed_item_get: rut_licensed_items_checkouts.LicensedItemCheckoutGet = (
        await licensed_items_checkouts.release_licensed_item(
            rpc_client,
            product_name=product_name,
            licensed_item_checkout_id=licensed_item_checkout_id,
        )
    )

    return LicensedItemCheckoutGet.model_construct(
        licensed_item_checkout_id=licensed_item_get.licensed_item_checkout_id,
        licensed_item_id=licensed_item_get.licensed_item_id,
        key=licensed_item_get.key,
        version=licensed_item_get.version,
        wallet_id=licensed_item_get.wallet_id,
        user_id=licensed_item_get.user_id,
        user_email=licensed_item_get.user_email,
        product_name=licensed_item_get.product_name,
        started_at=licensed_item_get.started_at,
        stopped_at=licensed_item_get.stopped_at,
        num_of_seats=licensed_item_get.num_of_seats,
    )
