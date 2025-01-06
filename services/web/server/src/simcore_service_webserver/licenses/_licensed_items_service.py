# pylint: disable=unused-argument

import logging
from datetime import UTC, datetime, timedelta

from aiohttp import web
from models_library.api_schemas_webserver.licensed_items import (
    LicensedItemGet,
    LicensedItemGetPage,
)
from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.resource_tracker_licensed_items_purchases import (
    LicensedItemsPurchasesCreate,
)
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from pydantic import NonNegativeInt
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    licensed_items_purchases,
)

from ..rabbitmq import get_rabbitmq_rpc_client
from ..resource_usage.api import get_pricing_plan_unit
from ..users.api import get_user
from ..wallets.api import get_wallet_with_available_credits_by_user_and_wallet
from ..wallets.errors import WalletNotEnoughCreditsError
from . import _licensed_items_repository
from ._models import LicensedItemsBodyParams
from .errors import LicensedItemPricingPlanMatchError

_logger = logging.getLogger(__name__)


async def get_licensed_item(
    app: web.Application,
    *,
    licensed_item_id: LicensedItemID,
    product_name: ProductName,
) -> LicensedItemGet:

    licensed_item_db = await _licensed_items_repository.get(
        app, licensed_item_id=licensed_item_id, product_name=product_name
    )
    return LicensedItemGet(
        licensed_item_id=licensed_item_db.licensed_item_id,
        name=licensed_item_db.name,
        license_key=licensed_item_db.license_key,
        licensed_resource_type=licensed_item_db.licensed_resource_type,
        pricing_plan_id=licensed_item_db.pricing_plan_id,
        created_at=licensed_item_db.created,
        modified_at=licensed_item_db.modified,
    )


async def list_licensed_items(
    app: web.Application,
    *,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> LicensedItemGetPage:
    total_count, licensed_item_db_list = await _licensed_items_repository.list_(
        app, product_name=product_name, offset=offset, limit=limit, order_by=order_by
    )
    return LicensedItemGetPage(
        items=[
            LicensedItemGet(
                licensed_item_id=licensed_item_db.licensed_item_id,
                name=licensed_item_db.name,
                license_key=licensed_item_db.license_key,
                licensed_resource_type=licensed_item_db.licensed_resource_type,
                pricing_plan_id=licensed_item_db.pricing_plan_id,
                created_at=licensed_item_db.created,
                modified_at=licensed_item_db.modified,
            )
            for licensed_item_db in licensed_item_db_list
        ],
        total=total_count,
    )


async def purchase_licensed_item(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    licensed_item_id: LicensedItemID,
    body_params: LicensedItemsBodyParams,
) -> None:
    # Check user wallet permissions
    wallet = await get_wallet_with_available_credits_by_user_and_wallet(
        app, user_id=user_id, wallet_id=body_params.wallet_id, product_name=product_name
    )

    licensed_item = await get_licensed_item(
        app, licensed_item_id=licensed_item_id, product_name=product_name
    )

    if licensed_item.pricing_plan_id != body_params.pricing_plan_id:
        raise LicensedItemPricingPlanMatchError(
            pricing_plan_id=body_params.pricing_plan_id,
            licensed_item_id=licensed_item_id,
        )

    pricing_unit = await get_pricing_plan_unit(
        app,
        product_name=product_name,
        pricing_plan_id=body_params.pricing_plan_id,
        pricing_unit_id=body_params.pricing_unit_id,
    )

    # Check whether wallet has enough credits
    if wallet.available_credits - pricing_unit.current_cost_per_unit < 0:
        raise WalletNotEnoughCreditsError(
            reason=f"Wallet '{wallet.name}' has {wallet.available_credits} credits."
        )

    user = await get_user(app, user_id=user_id)

    _data = LicensedItemsPurchasesCreate(
        product_name=product_name,
        licensed_item_id=licensed_item_id,
        wallet_id=wallet.wallet_id,
        wallet_name=wallet.name,
        pricing_plan_id=body_params.pricing_plan_id,
        pricing_unit_id=body_params.pricing_unit_id,
        pricing_unit_cost_id=pricing_unit.current_cost_per_unit_id,
        pricing_unit_cost=pricing_unit.current_cost_per_unit,
        start_at=datetime.now(tz=UTC),
        expire_at=datetime.now(tz=UTC)
        + timedelta(days=30),  # <-- Temporary agreement with OM for proof of concept
        num_of_seats=body_params.num_of_seats,
        purchased_by_user=user_id,
        user_email=user["email"],
        purchased_at=datetime.now(tz=UTC),
    )
    rpc_client = get_rabbitmq_rpc_client(app)
    await licensed_items_purchases.create_licensed_item_purchase(rpc_client, data=_data)
