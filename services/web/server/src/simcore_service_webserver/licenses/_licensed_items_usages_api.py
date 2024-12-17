from aiohttp import web
from models_library.api_schemas_resource_usage_tracker import (
    licensed_items_usages as rut_licensed_items_usages,
)
from models_library.api_schemas_webserver import (
    licensed_items_usages as webserver_licensed_items_usages,
)
from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.resource_tracker import ServiceRunId
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    licensed_items_usages,
)

from ..rabbitmq import get_rabbitmq_rpc_client
from ..wallets.api import get_wallet_by_user


async def checkout_licensed_item_for_wallet(
    app: web.Application,
    licensed_item_id: LicensedItemID,
    wallet_id: WalletID,
    product_name: ProductName,
    num_of_seats: int,
    service_run_id: ServiceRunId,
    user_id: UserID,
    user_email: str,
) -> webserver_licensed_items_usages.LicenseCheckoutGet:
    # Check whether user has access to the wallet
    await get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
        product_name=product_name,
    )

    rpc_client = get_rabbitmq_rpc_client(app)
    license_checkout_get: rut_licensed_items_usages.LicenseCheckoutGet = (
        await licensed_items_usages.checkout_licensed_item(
            rpc_client,
            licensed_item_id=licensed_item_id,
            wallet_id=wallet_id,
            product_name=product_name,
            num_of_seats=num_of_seats,
            service_run_id=service_run_id,
            user_id=user_id,
            user_email=user_email,
        )
    )

    return webserver_licensed_items_usages.LicenseCheckoutGet(
        checkout_id=license_checkout_get.checkout_id
    )


async def release_licensed_item_for_wallet(
    app: web.Application,
    product_name: ProductName,
    user_id: UserID,
    checkout_id: rut_licensed_items_usages.LicenseCheckoutID,
) -> webserver_licensed_items_usages.LicensedItemUsageGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    # Get
    checkout_item = await licensed_items_usages.get_licensed_item_usage(
        rpc_client, product_name=product_name, licensed_item_usage_id=checkout_id
    )

    # Check whether user has access to the wallet
    await get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=checkout_item.wallet_id,
        product_name=product_name,
    )

    licensed_item_get: rut_licensed_items_usages.LicensedItemUsageGet = (
        await licensed_items_usages.release_licensed_item(
            rpc_client,
            product_name=product_name,
            checkout_id=checkout_id,
        )
    )

    return webserver_licensed_items_usages.LicensedItemUsageGet(
        licensed_item_usage_id=licensed_item_get.licensed_item_usage_id,
        licensed_item_id=licensed_item_get.licensed_item_id,
        wallet_id=licensed_item_get.wallet_id,
        user_id=licensed_item_get.user_id,
        product_name=licensed_item_get.product_name,
        started_at=licensed_item_get.started_at,
        stopped_at=licensed_item_get.stopped_at,
        num_of_seats=licensed_item_get.num_of_seats,
    )
