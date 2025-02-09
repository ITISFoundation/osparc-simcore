# pylint: disable=unused-argument

import logging
from datetime import UTC, datetime, timedelta
from enum import Enum, auto
from pprint import pformat
from typing import NamedTuple

from aiohttp import web
from deepdiff import DeepDiff  # type: ignore[attr-defined]
from models_library.licenses import (
    LicensedItem,
    LicensedItemDB,
    LicensedItemID,
    LicensedItemPage,
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
from . import _licensed_items_repository, _licensed_resources_repository
from ._common.models import LicensedItemsBodyParams
from .errors import LicensedItemNotFoundError, LicensedItemPricingPlanMatchError

_logger = logging.getLogger(__name__)


class RegistrationState(Enum):
    ALREADY_REGISTERED = auto()
    DIFFERENT_RESOURCE = auto()
    NEWLY_REGISTERED = auto()


class RegistrationResult(NamedTuple):
    registered: LicensedItemDB
    state: RegistrationState
    message: str | None


async def register_resource_as_licensed_resource(
    app: web.Application,
    *,
    licensed_resource_name: str,
    licensed_resource_type: LicensedResourceType,
    licensed_resource_data: BaseModel,
    licensed_item_display_name: str,
) -> RegistrationResult:
    # NOTE about the implementation choice:
    # Using `create_if_not_exists` (INSERT with IGNORE_ON_CONFLICT) would have been an option,
    # but it generates excessive error logs due to conflicts.
    #
    # To avoid this, we first attempt to retrieve the resource using `get_by_resource_identifier` (GET).
    # If the resource does not exist, we proceed with `create_if_not_exists` (INSERT with IGNORE_ON_CONFLICT).
    #
    # This approach not only reduces unnecessary error logs but also helps prevent race conditions
    # when multiple concurrent calls attempt to register the same resource.

    resource_key = f"{licensed_resource_type}, {licensed_resource_name}"
    new_licensed_resource_data = licensed_resource_data.model_dump(
        mode="json",
        exclude_unset=True,
    )

    try:
        licensed_item = await _licensed_items_repository.get_by_resource_identifier(
            app,
            licensed_resource_name=licensed_resource_name,
            licensed_resource_type=licensed_resource_type,
        )
        licensed_resource = (
            await _licensed_resources_repository.get_by_resource_identifier(
                app,
                licensed_resource_name=licensed_resource_name,
                licensed_resource_type=licensed_resource_type,
            )
        )
        # NOTE: MD: This is temporaty, we are splitting the licensed_item and licensed_resource
        assert (
            licensed_resource.licensed_resource_name
            == licensed_item.licensed_resource_name
        )  # nosec
        assert (
            licensed_resource.licensed_resource_type
            == licensed_item.licensed_resource_type
        )  # nosec

        if licensed_item.licensed_resource_data != new_licensed_resource_data:
            ddiff = DeepDiff(
                licensed_item.licensed_resource_data, new_licensed_resource_data
            )
            msg = (
                f"DIFFERENT_RESOURCE: {resource_key=} found in licensed_item_id={licensed_item.licensed_item_id} with different data. "
                f"Diff:\n\t{pformat(ddiff, indent=2, width=200)}"
            )
            return RegistrationResult(
                licensed_item, RegistrationState.DIFFERENT_RESOURCE, msg
            )

        return RegistrationResult(
            licensed_item,
            RegistrationState.ALREADY_REGISTERED,
            f"ALREADY_REGISTERED: {resource_key=} found in licensed_item_id={licensed_item.licensed_item_id}",
        )

    except LicensedItemNotFoundError:
        licensed_item = await _licensed_items_repository.create_if_not_exists(
            app,
            display_name=licensed_item_display_name,
            licensed_resource_name=licensed_resource_name,
            licensed_resource_type=licensed_resource_type,
            licensed_resource_data=new_licensed_resource_data,
            product_name=None,
            pricing_plan_id=None,
        )
        licensed_resource = await _licensed_resources_repository.create_if_not_exists(
            app,
            display_name=licensed_item_display_name,
            licensed_resource_name=licensed_resource_name,
            licensed_resource_type=licensed_resource_type,
            licensed_resource_data=new_licensed_resource_data,
        )
        # NOTE: MD: This is temporaty, we are splitting the licensed_item and licensed_resource
        assert (
            licensed_resource.licensed_resource_name
            == licensed_item.licensed_resource_name
        )  # nosec
        assert (
            licensed_resource.licensed_resource_type
            == licensed_item.licensed_resource_type
        )  # nosec

        return RegistrationResult(
            licensed_item,
            RegistrationState.NEWLY_REGISTERED,
            f"NEWLY_REGISTERED: {resource_key=} registered with licensed_item_id={licensed_item.licensed_item_id}",
        )


async def get_licensed_item(
    app: web.Application,
    *,
    licensed_item_id: LicensedItemID,
    product_name: ProductName,
) -> LicensedItem:

    licensed_item_db = await _licensed_items_repository.get(
        app, licensed_item_id=licensed_item_id, product_name=product_name
    )
    return LicensedItem.model_construct(
        licensed_item_id=licensed_item_db.licensed_item_id,
        display_name=licensed_item_db.display_name,
        licensed_resource_name=licensed_item_db.licensed_resource_name,
        licensed_resource_type=licensed_item_db.licensed_resource_type,
        licensed_resource_data=licensed_item_db.licensed_resource_data,
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
) -> LicensedItemPage:
    total_count, items = await _licensed_items_repository.list_(
        app,
        product_name=product_name,
        offset=offset,
        limit=limit,
        order_by=order_by,
        trashed="exclude",
        inactive="exclude",
    )
    return LicensedItemPage(
        items=[
            LicensedItem.model_construct(
                licensed_item_id=licensed_item_db.licensed_item_id,
                display_name=licensed_item_db.display_name,
                licensed_resource_name=licensed_item_db.licensed_resource_name,
                licensed_resource_type=licensed_item_db.licensed_resource_type,
                licensed_resource_data=licensed_item_db.licensed_resource_data,
                pricing_plan_id=licensed_item_db.pricing_plan_id,
                created_at=licensed_item_db.created,
                modified_at=licensed_item_db.modified,
            )
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
