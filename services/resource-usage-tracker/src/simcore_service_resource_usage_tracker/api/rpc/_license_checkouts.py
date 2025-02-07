from fastapi import FastAPI
from models_library.api_schemas_resource_usage_tracker.license_checkouts import (
    LicenseCheckoutGet,
    LicenseCheckoutsPage,
)
from models_library.licenses import LicenseID
from models_library.products import ProductName
from models_library.resource_tracker_license_checkouts import LicenseCheckoutID
from models_library.rest_ordering import OrderBy
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    LICENSES_ERRORS,
    LicenseCheckoutNotFoundError,
)

from ...services import license_checkouts

router = RPCRouter()


@router.expose(reraise_if_error_type=(LicenseCheckoutNotFoundError,))
async def get_license_checkout(
    app: FastAPI,
    *,
    product_name: ProductName,
    license_checkout_id: LicenseCheckoutID,
) -> LicenseCheckoutGet:
    return await license_checkouts.get_license_checkout(
        db_engine=app.state.engine,
        product_name=product_name,
        license_checkout_id=license_checkout_id,
    )


@router.expose(reraise_if_error_type=LICENSES_ERRORS)
async def get_license_checkouts_page(
    app: FastAPI,
    *,
    product_name: ProductName,
    filter_wallet_id: WalletID,
    offset: int = 0,
    limit: int = 20,
    order_by: OrderBy,
) -> LicenseCheckoutsPage:
    return await license_checkouts.list_license_checkouts(
        db_engine=app.state.engine,
        product_name=product_name,
        filter_wallet_id=filter_wallet_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )


@router.expose(reraise_if_error_type=LICENSES_ERRORS)
async def checkout_license(
    app: FastAPI,
    *,
    license_id: LicenseID,
    wallet_id: WalletID,
    product_name: ProductName,
    num_of_seats: int,
    service_run_id: ServiceRunID,
    user_id: UserID,
    user_email: str,
) -> LicenseCheckoutGet:
    return await license_checkouts.checkout_license(
        db_engine=app.state.engine,
        license_id=license_id,
        wallet_id=wallet_id,
        product_name=product_name,
        num_of_seats=num_of_seats,
        service_run_id=service_run_id,
        user_id=user_id,
        user_email=user_email,
    )


@router.expose(reraise_if_error_type=LICENSES_ERRORS)
async def release_license(
    app: FastAPI,
    *,
    license_checkout_id: LicenseCheckoutID,
    product_name: ProductName,
) -> LicenseCheckoutGet:
    return await license_checkouts.release_license(
        db_engine=app.state.engine,
        license_checkout_id=license_checkout_id,
        product_name=product_name,
    )
