from aiohttp import web
from models_library.api_schemas_resource_usage_tracker import (
    licensed_items_checkouts as rut_licensed_items_checkouts,
)
from models_library.api_schemas_webserver import (
    licensed_items_checkouts as webserver_licensed_items_checkouts,
)
from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.resource_tracker import ServiceRunId
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    licensed_items_checkouts,
)

from ..rabbitmq import get_rabbitmq_rpc_client
from ..users.api import get_user
from ..wallets.api import get_wallet_by_user


async def checkout_licensed_item_for_wallet(
    app: web.Application,
    licensed_item_id: LicensedItemID,
    wallet_id: WalletID,
    product_name: ProductName,
    num_of_seats: int,
    service_run_id: ServiceRunId,
    user_id: UserID,
) -> webserver_licensed_items_checkouts.LicenseCheckoutGet:
    # Check whether user has access to the wallet
    await get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
        product_name=product_name,
    )

    user = await get_user(app, user_id=user_id)

    rpc_client = get_rabbitmq_rpc_client(app)
    license_checkout_get: rut_licensed_items_checkouts.LicenseCheckoutGet = (
        await licensed_items_checkouts.checkout_licensed_item(
            rpc_client,
            licensed_item_id=licensed_item_id,
            wallet_id=wallet_id,
            product_name=product_name,
            num_of_seats=num_of_seats,
            service_run_id=service_run_id,
            user_id=user_id,
            user_email=user["email"],
        )
    )

    return webserver_licensed_items_checkouts.LicenseCheckoutGet(
        checkout_id=license_checkout_get.checkout_id
    )


async def release_licensed_item_for_wallet(
    app: web.Application,
    product_name: ProductName,
    user_id: UserID,
    checkout_id: rut_licensed_items_checkouts.LicenseCheckoutID,
) -> webserver_licensed_items_checkouts.LicensedItemCheckoutGet:
    rpc_client = get_rabbitmq_rpc_client(app)

    checkout_item = await licensed_items_checkouts.get_licensed_item_checkout(
        rpc_client, product_name=product_name, licensed_item_usage_id=checkout_id
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
            checkout_id=checkout_id,
        )
    )

    return webserver_licensed_items_checkouts.LicensedItemCheckoutGet(
        licensed_item_checkout_id=licensed_item_get.licensed_item_usage_id,
        licensed_item_id=licensed_item_get.licensed_item_id,
        wallet_id=licensed_item_get.wallet_id,
        user_id=licensed_item_get.user_id,
        product_name=licensed_item_get.product_name,
        started_at=licensed_item_get.started_at,
        stopped_at=licensed_item_get.stopped_at,
        num_of_seats=licensed_item_get.num_of_seats,
    )
