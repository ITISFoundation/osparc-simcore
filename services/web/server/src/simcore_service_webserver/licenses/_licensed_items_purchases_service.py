import logging

from aiohttp import web
from models_library.api_schemas_resource_usage_tracker import (
    licensed_items_purchases as rut_licensed_items_purchases,
)
from models_library.api_schemas_webserver import (
    licensed_items_purchases as webserver_licensed_items_purchases,
)
from models_library.products import ProductName
from models_library.resource_tracker_licensed_items_purchases import (
    LicensedItemPurchaseID,
)
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    licensed_items_purchases,
)

from ..rabbitmq import get_rabbitmq_rpc_client
from ..wallets.api import get_wallet_by_user

_logger = logging.getLogger(__name__)


async def list_licensed_items_purchases(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    wallet_id: WalletID,
    offset: int,
    limit: int,
    order_by: OrderBy,
) -> webserver_licensed_items_purchases.LicensedItemPurchaseGetPage:

    # Check whether user has access to the wallet
    await get_wallet_by_user(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )

    rpc_client = get_rabbitmq_rpc_client(app)
    result: rut_licensed_items_purchases.LicensedItemsPurchasesPage = (
        await licensed_items_purchases.get_licensed_items_purchases_page(
            rpc_client,
            product_name=product_name,
            wallet_id=wallet_id,
            offset=offset,
            limit=limit,
            order_by=order_by,
        )
    )
    return webserver_licensed_items_purchases.LicensedItemPurchaseGetPage(
        total=result.total,
        items=[
            webserver_licensed_items_purchases.LicensedItemPurchaseGet(
                licensed_item_purchase_id=item.licensed_item_purchase_id,
                product_name=item.product_name,
                licensed_item_id=item.licensed_item_id,
                key=item.key,
                version=item.version,
                wallet_id=item.wallet_id,
                pricing_unit_cost_id=item.pricing_unit_cost_id,
                pricing_unit_cost=item.pricing_unit_cost,
                start_at=item.start_at,
                expire_at=item.expire_at,
                num_of_seats=item.num_of_seats,
                purchased_by_user=item.purchased_by_user,
                user_email=item.user_email,
                purchased_at=item.purchased_at,
                modified_at=item.modified,
            )
            for item in result.items
        ],
    )


async def get_licensed_item_purchase(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    licensed_item_purchase_id: LicensedItemPurchaseID,
) -> webserver_licensed_items_purchases.LicensedItemPurchaseGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    licensed_item_get: rut_licensed_items_purchases.LicensedItemPurchaseGet = (
        await licensed_items_purchases.get_licensed_item_purchase(
            rpc_client,
            product_name=product_name,
            licensed_item_purchase_id=licensed_item_purchase_id,
        )
    )

    # Check whether user has access to the wallet
    await get_wallet_by_user(
        app,
        user_id=user_id,
        wallet_id=licensed_item_get.wallet_id,
        product_name=product_name,
    )

    return webserver_licensed_items_purchases.LicensedItemPurchaseGet(
        licensed_item_purchase_id=licensed_item_get.licensed_item_purchase_id,
        product_name=licensed_item_get.product_name,
        licensed_item_id=licensed_item_get.licensed_item_id,
        key=licensed_item_get.key,
        version=licensed_item_get.version,
        wallet_id=licensed_item_get.wallet_id,
        pricing_unit_cost_id=licensed_item_get.pricing_unit_cost_id,
        pricing_unit_cost=licensed_item_get.pricing_unit_cost,
        start_at=licensed_item_get.start_at,
        expire_at=licensed_item_get.expire_at,
        num_of_seats=licensed_item_get.num_of_seats,
        purchased_by_user=licensed_item_get.purchased_by_user,
        user_email=licensed_item_get.user_email,
        purchased_at=licensed_item_get.purchased_at,
        modified_at=licensed_item_get.modified,
    )
