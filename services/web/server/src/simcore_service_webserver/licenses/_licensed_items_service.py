# pylint: disable=unused-argument

import logging
from datetime import UTC, datetime, timedelta

from aiohttp import web
from models_library.api_schemas_webserver.licensed_items import (
    LicensedItemGet,
    LicensedItemGetPage,
)
from models_library.licensed_items import (
    LicensedItemDB,
    LicensedItemID,
    LicensedItemUpdateDB,
    LicensedResourceType,
)
from models_library.products import ProductName
from models_library.resource_tracker_licensed_items_purchases import (
    LicensedItemsPurchasesCreate,
)
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from pydantic import BaseModel, NonNegativeInt
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker import (
    licensed_items_purchases,
)

from ..rabbitmq import get_rabbitmq_rpc_client
from ..resource_usage.service import get_pricing_plan_unit
from ..users.api import get_user
from ..wallets.api import get_wallet_with_available_credits_by_user_and_wallet
from ..wallets.errors import WalletNotEnoughCreditsError
from . import _licensed_items_repository
from ._common.models import LicensedItemsBodyParams
from .errors import LicensedItemNotFoundError, LicensedItemPricingPlanMatchError

_logger = logging.getLogger(__name__)


def _compute_difference(old_data: dict, new_data: dict):
    differences = {
        k: {"old": old_data[k], "new": new_data[k]}
        for k in old_data
        if old_data[k] != new_data.get(k)
    }
    differences.update(
        {k: {"old": None, "new": new_data[k]} for k in new_data if k not in old_data}
    )
    return differences


async def register_licensed_item_from_resource(
    app: web.Application,
    *,
    licensed_resource_name: str,
    licensed_resource_type: LicensedResourceType,
    licensed_resource_data: BaseModel,
    license_key: str | None,
) -> LicensedItemDB:

    try:
        license_item = await _licensed_items_repository.get_by_resource_identifier(
            app,
            licensed_resource_name=licensed_resource_name,
            licensed_resource_type=licensed_resource_type,
        )

        if license_item.licensed_resource_data != licensed_resource_data.model_dump(
            mode="json", exclude_unset=True
        ):
            differences = _compute_difference(
                license_item.licensed_resource_data or {},
                licensed_resource_data.model_dump(mode="json", exclude_unset=True),
            )
            _logger.warning(
                "CHANGES: NEEDED for %s, %s: Resource differs from the one registered: %s",
                licensed_resource_name,
                licensed_resource_type,
                differences,
            )
        else:
            _logger.info(
                "Resource %s, %s already registered",
                licensed_resource_name,
                licensed_resource_type,
            )

    except LicensedItemNotFoundError:
        license_item = await _licensed_items_repository.create_if_not_exists(
            app,
            licensed_resource_name=licensed_resource_name,
            licensed_resource_type=licensed_resource_type,
            licensed_resource_data=licensed_resource_data.model_dump(
                mode="json", exclude_unset=True
            ),
            license_key=license_key,
            product_name=None,
            pricing_plan_id=None,
        )

        _logger.info(
            "NEW license with resource %s, %s already registered",
            licensed_resource_name,
            licensed_resource_type,
        )

    return license_item


async def get_licensed_item(
    app: web.Application,
    *,
    licensed_item_id: LicensedItemID,
    product_name: ProductName,
) -> LicensedItemGet:

    licensed_item_db = await _licensed_items_repository.get(
        app, licensed_item_id=licensed_item_id, product_name=product_name
    )
    return LicensedItemGet.from_domain_model(licensed_item_db)


async def list_licensed_items(
    app: web.Application,
    *,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> LicensedItemGetPage:
    total_count, items = await _licensed_items_repository.list_(
        app,
        product_name=product_name,
        offset=offset,
        limit=limit,
        order_by=order_by,
        trashed="exclude",
        inactive="exclude",
    )
    return LicensedItemGetPage(
        items=[
            LicensedItemGet.from_domain_model(licensed_item_db)
            for licensed_item_db in items
        ],
        total=total_count,
    )


async def trash_licensed_item(
    app: web.Application,
    *,
    product_name: ProductName,
    licensed_item_id: LicensedItemID,
):
    await _licensed_items_repository.update(
        app,
        product_name=product_name,
        licensed_item_id=licensed_item_id,
        updates=LicensedItemUpdateDB(trash=True),
    )


async def untrash_licensed_item(
    app: web.Application,
    *,
    product_name: ProductName,
    licensed_item_id: LicensedItemID,
):
    await _licensed_items_repository.update(
        app,
        product_name=product_name,
        licensed_item_id=licensed_item_id,
        updates=LicensedItemUpdateDB(trash=True),
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
