from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_resource_usage_tracker.licensed_items_usages import (
    LicenseCheckoutID,
    LicensedItemsUsagesPage,
    LicensedItemUsageGet,
    LicenseItemCheckoutGet,
)
from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.resource_tracker import ServiceRunId, ServiceRunStatus
from models_library.resource_tracker_licensed_items_usages import LicensedItemUsageID
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.wallets import WalletID
from sqlalchemy.ext.asyncio import AsyncEngine

from ..api.rest.dependencies import get_resource_tracker_db_engine
from ..models.licensed_items_usages import (
    CreateLicensedItemUsageDB,
    LicensedItemUsageDB,
)
from .modules.db import (
    licensed_items_purchases_db,
    licensed_items_usages_db,
    service_runs_db,
)


async def list_licensed_items_purchases(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    product_name: ProductName,
    filter_wallet_id: WalletID,
    offset: int = 0,
    limit: int = 20,
    order_by: OrderBy,
) -> LicensedItemsUsagesPage:
    total, licensed_items_usages_list_db = await licensed_items_usages_db.list_(
        db_engine,
        product_name=product_name,
        filter_wallet_id=filter_wallet_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )
    return LicensedItemsUsagesPage(
        total=total,
        items=[
            LicensedItemUsageGet(
                licensed_item_usage_id=licensed_item_usage_db.licensed_item_usage_id,
                licensed_item_id=licensed_item_usage_db.licensed_item_id,
                wallet_id=licensed_item_usage_db.wallet_id,
                user_id=licensed_item_usage_db.user_id,
                product_name=licensed_item_usage_db.product_name,
                service_run_id=licensed_item_usage_db.service_run_id,
                start_at=licensed_item_usage_db.start_at,
                stopped_at=licensed_item_usage_db.stopped_at,
                num_of_seats=licensed_item_usage_db.num_of_seats,
            )
            for licensed_item_usage_db in licensed_items_usages_list_db
        ],
    )


async def get_licensed_item_usage(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    product_name: ProductName,
    licensed_item_usage_id: LicensedItemUsageID,
) -> LicensedItemUsageGet:
    licensed_item_usage_db: LicensedItemUsageDB = await licensed_items_usages_db.get(
        db_engine,
        product_name=product_name,
        licensed_item_usage_id=licensed_item_usage_id,
    )

    return LicensedItemUsageGet(
        licensed_item_usage_id=licensed_item_usage_db.licensed_item_usage_id,
        licensed_item_id=licensed_item_usage_db.licensed_item_id,
        wallet_id=licensed_item_usage_db.wallet_id,
        user_id=licensed_item_usage_db.user_id,
        product_name=licensed_item_usage_db.product_name,
        service_run_id=licensed_item_usage_db.service_run_id,
        start_at=licensed_item_usage_db.start_at,
        stopped_at=licensed_item_usage_db.stopped_at,
        num_of_seats=licensed_item_usage_db.num_of_seats,
    )


async def checkout_licensed_item(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    licensed_item_id: LicensedItemID,
    wallet_id: WalletID,
    product_name: ProductName,
    num_of_seats: int,
    service_run_id: ServiceRunId,
    user_id: UserID,
    user_email: str,
) -> LicenseItemCheckoutGet:

    _active_purchased_seats: int = await licensed_items_purchases_db.get_active_purchased_seats_for_item_and_wallet(
        db_engine,
        licensed_item_id=licensed_item_id,
        wallet_id=wallet_id,
        product_name=product_name,
    )

    _currently_used_seats = (
        await licensed_items_usages_db.get_currently_used_seats_for_item_and_wallet(
            db_engine,
            licensed_item_id=licensed_item_id,
            wallet_id=wallet_id,
            product_name=product_name,
        )
    )

    available_seats = _active_purchased_seats - _currently_used_seats
    if available_seats <= 0:
        raise ValueError("Not enough available seats")

    if available_seats - num_of_seats < 0:
        raise ValueError("Can not checkout num of seats, not enough available")

    # Check if the service run ID is currently running
    service_run = await service_runs_db.get_service_run_by_id(
        db_engine, service_run_id=service_run_id
    )
    if (
        service_run is None
        or service_run.service_run_status != ServiceRunStatus.RUNNING
    ):
        raise ValueError("This should not happen")

    _create_item_usage = CreateLicensedItemUsageDB(
        licensed_item_id=licensed_item_id,
        wallet_id=wallet_id,
        user_id=user_id,
        user_email=user_email,
        product_name=product_name,
        service_run_id=service_run_id,
        start_at=datetime.now(tz=UTC),
        num_of_seats=num_of_seats,
    )
    license_item_usage_db = await licensed_items_usages_db.create(
        db_engine, data=_create_item_usage
    )

    # Return checkout ID
    return LicenseItemCheckoutGet(
        checkout_id=license_item_usage_db.licensed_item_usage_id
    )


async def release_licensed_item(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    checkout_id: LicenseCheckoutID,
    product_name: ProductName,
) -> LicensedItemUsageGet:

    licensed_item_usage_db: LicensedItemUsageDB = await licensed_items_usages_db.update(
        db_engine,
        licensed_item_usage_id=checkout_id,
        product_name=product_name,
        stopped_at=datetime.now(tz=UTC),
    )

    return LicensedItemUsageGet(
        licensed_item_usage_id=licensed_item_usage_db.licensed_item_usage_id,
        licensed_item_id=licensed_item_usage_db.licensed_item_id,
        wallet_id=licensed_item_usage_db.wallet_id,
        user_id=licensed_item_usage_db.user_id,
        product_name=licensed_item_usage_db.product_name,
        service_run_id=licensed_item_usage_db.service_run_id,
        start_at=licensed_item_usage_db.start_at,
        stopped_at=licensed_item_usage_db.stopped_at,
        num_of_seats=licensed_item_usage_db.num_of_seats,
    )
