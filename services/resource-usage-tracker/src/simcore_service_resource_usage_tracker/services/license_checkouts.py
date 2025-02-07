from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_resource_usage_tracker.license_checkouts import (
    LicenseCheckoutGet,
    LicenseCheckoutsPage,
)
from models_library.licenses import LicenseID
from models_library.products import ProductName
from models_library.resource_tracker import ServiceRunStatus
from models_library.resource_tracker_license_checkouts import LicenseCheckoutID
from models_library.rest_ordering import OrderBy
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    CanNotCheckoutNotEnoughAvailableSeatsError,
    CanNotCheckoutServiceIsNotRunningError,
    NotEnoughAvailableSeatsError,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from ..api.rest.dependencies import get_resource_tracker_db_engine
from ..models.license_checkouts import CreateLicenseCheckoutDB, LicenseCheckoutDB
from .modules.db import license_checkouts_db, license_purchases_db, service_runs_db


async def list_license_checkouts(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    product_name: ProductName,
    filter_wallet_id: WalletID,
    offset: int,
    limit: int,
    order_by: OrderBy,
) -> LicenseCheckoutsPage:
    total, license_checkouts_list_db = await license_checkouts_db.list_(
        db_engine,
        product_name=product_name,
        filter_wallet_id=filter_wallet_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )
    return LicenseCheckoutsPage(
        total=total,
        items=[
            LicenseCheckoutGet(
                license_checkout_id=licensed_item_checkout_db.license_checkout_id,
                license_id=licensed_item_checkout_db.license_id,
                wallet_id=licensed_item_checkout_db.wallet_id,
                user_id=licensed_item_checkout_db.user_id,
                user_email=licensed_item_checkout_db.user_email,
                product_name=licensed_item_checkout_db.product_name,
                service_run_id=licensed_item_checkout_db.service_run_id,
                started_at=licensed_item_checkout_db.started_at,
                stopped_at=licensed_item_checkout_db.stopped_at,
                num_of_seats=licensed_item_checkout_db.num_of_seats,
            )
            for licensed_item_checkout_db in license_checkouts_list_db
        ],
    )


async def get_license_checkout(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    product_name: ProductName,
    license_checkout_id: LicenseCheckoutID,
) -> LicenseCheckoutGet:
    licensed_item_checkout_db: LicenseCheckoutDB = await license_checkouts_db.get(
        db_engine,
        product_name=product_name,
        license_checkout_id=license_checkout_id,
    )

    return LicenseCheckoutGet(
        license_checkout_id=licensed_item_checkout_db.license_checkout_id,
        license_id=licensed_item_checkout_db.license_id,
        wallet_id=licensed_item_checkout_db.wallet_id,
        user_id=licensed_item_checkout_db.user_id,
        user_email=licensed_item_checkout_db.user_email,
        product_name=licensed_item_checkout_db.product_name,
        service_run_id=licensed_item_checkout_db.service_run_id,
        started_at=licensed_item_checkout_db.started_at,
        stopped_at=licensed_item_checkout_db.stopped_at,
        num_of_seats=licensed_item_checkout_db.num_of_seats,
    )


async def checkout_license(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    license_id: LicenseID,
    wallet_id: WalletID,
    product_name: ProductName,
    num_of_seats: int,
    service_run_id: ServiceRunID,
    user_id: UserID,
    user_email: str,
) -> LicenseCheckoutGet:

    _active_purchased_seats: int = (
        await license_purchases_db.get_active_purchased_seats_for_item_and_wallet(
            db_engine,
            license_id=license_id,
            wallet_id=wallet_id,
            product_name=product_name,
        )
    )

    _currently_used_seats = (
        await license_checkouts_db.get_currently_used_seats_for_item_and_wallet(
            db_engine,
            license_id=license_id,
            wallet_id=wallet_id,
            product_name=product_name,
        )
    )

    available_seats = _active_purchased_seats - _currently_used_seats
    if available_seats <= 0:
        raise NotEnoughAvailableSeatsError(
            license_id=license_id, available_num_of_seats=available_seats
        )

    if available_seats - num_of_seats < 0:
        raise CanNotCheckoutNotEnoughAvailableSeatsError(
            license_id=license_id,
            available_num_of_seats=available_seats,
            num_of_seats=num_of_seats,
        )

    # Check if the service run ID is currently running
    service_run = await service_runs_db.get_service_run_by_id(
        db_engine, service_run_id=service_run_id
    )
    if (
        service_run is None
        or service_run.service_run_status != ServiceRunStatus.RUNNING
    ):
        raise CanNotCheckoutServiceIsNotRunningError(
            license_id=license_id, service_run=service_run
        )

    _create_item_checkout = CreateLicenseCheckoutDB(
        license_id=license_id,
        wallet_id=wallet_id,
        user_id=user_id,
        user_email=user_email,
        product_name=product_name,
        service_run_id=service_run_id,
        started_at=datetime.now(tz=UTC),
        num_of_seats=num_of_seats,
    )
    licensed_item_checkout_db = await license_checkouts_db.create(
        db_engine, data=_create_item_checkout
    )

    # Return checkout ID
    return LicenseCheckoutGet(
        license_checkout_id=licensed_item_checkout_db.license_checkout_id,
        license_id=licensed_item_checkout_db.license_id,
        wallet_id=licensed_item_checkout_db.wallet_id,
        user_id=licensed_item_checkout_db.user_id,
        user_email=licensed_item_checkout_db.user_email,
        product_name=licensed_item_checkout_db.product_name,
        service_run_id=licensed_item_checkout_db.service_run_id,
        started_at=licensed_item_checkout_db.started_at,
        stopped_at=licensed_item_checkout_db.stopped_at,
        num_of_seats=licensed_item_checkout_db.num_of_seats,
    )


async def release_license(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    license_checkout_id: LicenseCheckoutID,
    product_name: ProductName,
) -> LicenseCheckoutGet:

    licensed_item_checkout_db: LicenseCheckoutDB = await license_checkouts_db.update(
        db_engine,
        license_checkout_id=license_checkout_id,
        product_name=product_name,
        stopped_at=datetime.now(tz=UTC),
    )

    return LicenseCheckoutGet(
        license_checkout_id=licensed_item_checkout_db.license_checkout_id,
        license_id=licensed_item_checkout_db.license_id,
        wallet_id=licensed_item_checkout_db.wallet_id,
        user_id=licensed_item_checkout_db.user_id,
        user_email=licensed_item_checkout_db.user_email,
        product_name=licensed_item_checkout_db.product_name,
        service_run_id=licensed_item_checkout_db.service_run_id,
        started_at=licensed_item_checkout_db.started_at,
        stopped_at=licensed_item_checkout_db.stopped_at,
        num_of_seats=licensed_item_checkout_db.num_of_seats,
    )
