# pylint: disable=unused-argument

import logging
from datetime import UTC, datetime, timedelta

from aiohttp import web
from models_library.api_schemas_resource_usage_tracker.licensed_items_purchases import (
    LicensedItemPurchaseGet,
)
from models_library.licenses import (
    LicensedItem,
    LicensedItemID,
    LicensedItemKey,
    LicensedItemPage,
    LicensedItemVersion,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    PricingPlanClassification,
    UnitExtraInfoLicense,
)
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
from ..resource_usage.service import get_pricing_plan, get_pricing_plan_unit
from ..users import users_service
from ..wallets.api import get_wallet_with_available_credits_by_user_and_wallet
from ..wallets.errors import WalletNotEnoughCreditsError
from . import _licensed_items_repository
from ._common.models import LicensedItemsBodyParams
from .errors import (
    LicensedItemNumOfSeatsMatchError,
    LicensedItemPricingPlanConfigurationError,
    LicensedItemPricingPlanMatchError,
)

_logger = logging.getLogger(__name__)


async def get_licensed_item(
    app: web.Application,
    *,
    key: LicensedItemKey,
    version: LicensedItemVersion,
    product_name: ProductName,
) -> LicensedItem:

    return await _licensed_items_repository.get_licensed_item_by_key_version(
        app, key=key, version=version, product_name=product_name
    )


async def list_licensed_items(
    app: web.Application,
    *,
    product_name: ProductName,
    include_hidden_items_on_market: bool,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> LicensedItemPage:
    total_count, items = await _licensed_items_repository.list_licensed_items(
        app,
        product_name=product_name,
        include_hidden_items_on_market=include_hidden_items_on_market,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )
    return LicensedItemPage(
        items=items,
        total=total_count,
    )


async def purchase_licensed_item(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    licensed_item_id: LicensedItemID,
    body_params: LicensedItemsBodyParams,
) -> LicensedItemPurchaseGet:
    # Check user wallet permissions
    wallet = await get_wallet_with_available_credits_by_user_and_wallet(
        app, user_id=user_id, wallet_id=body_params.wallet_id, product_name=product_name
    )

    licensed_item_db = await _licensed_items_repository.get(
        app, licensed_item_id=licensed_item_id, product_name=product_name
    )
    licensed_item = await get_licensed_item(
        app,
        key=licensed_item_db.key,
        version=licensed_item_db.version,
        product_name=product_name,
    )

    if licensed_item.pricing_plan_id != body_params.pricing_plan_id:
        raise LicensedItemPricingPlanMatchError(
            pricing_plan_id=body_params.pricing_plan_id,
            licensed_item_id=licensed_item.licensed_item_id,
        )

    pricing_plan = await get_pricing_plan(
        app, product_name=product_name, pricing_plan_id=body_params.pricing_plan_id
    )
    if pricing_plan.classification is not PricingPlanClassification.LICENSE:
        raise LicensedItemPricingPlanConfigurationError(
            pricing_plan_id=body_params.pricing_plan_id
        )

    pricing_unit = await get_pricing_plan_unit(
        app,
        product_name=product_name,
        pricing_plan_id=body_params.pricing_plan_id,
        pricing_unit_id=body_params.pricing_unit_id,
    )
    assert isinstance(pricing_unit.unit_extra_info, UnitExtraInfoLicense)  # nosec
    if pricing_unit.unit_extra_info.num_of_seats != body_params.num_of_seats:
        raise LicensedItemNumOfSeatsMatchError(
            num_of_seats=body_params.num_of_seats,
            pricing_unit_id=body_params.pricing_unit_id,
        )

    # Check whether wallet has enough credits
    if wallet.available_credits - pricing_unit.current_cost_per_unit < 0:
        raise WalletNotEnoughCreditsError(
            reason=f"Wallet '{wallet.name}' has {wallet.available_credits} credits."
        )

    user = await users_service.get_user(app, user_id=user_id)

    _data = LicensedItemsPurchasesCreate(
        product_name=product_name,
        licensed_item_id=licensed_item.licensed_item_id,
        key=licensed_item_db.key,
        version=licensed_item_db.version,
        wallet_id=wallet.wallet_id,
        wallet_name=wallet.name,
        pricing_plan_id=body_params.pricing_plan_id,
        pricing_unit_id=body_params.pricing_unit_id,
        pricing_unit_cost_id=pricing_unit.current_cost_per_unit_id,
        pricing_unit_cost=pricing_unit.current_cost_per_unit,
        start_at=datetime.now(tz=UTC),
        expire_at=datetime.now(tz=UTC) + timedelta(days=365),
        num_of_seats=body_params.num_of_seats,
        purchased_by_user=user_id,
        user_email=user["email"],
        purchased_at=datetime.now(tz=UTC),
    )
    rpc_client = get_rabbitmq_rpc_client(app)
    return await licensed_items_purchases.create_licensed_item_purchase(
        rpc_client, data=_data
    )
