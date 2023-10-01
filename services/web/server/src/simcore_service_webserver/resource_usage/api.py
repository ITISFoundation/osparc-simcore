from datetime import datetime
from decimal import Decimal

from aiohttp import web
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from models_library.api_schemas_webserver.wallets import PaymentID
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID

from . import resource_usage_tracker_client
from ._pricing_plans_api import get_default_service_pricing_plan


async def get_wallet_total_available_credits(
    app: web.Application, product_name: ProductName, wallet_id: WalletID
) -> WalletTotalCredits:
    available_credits: WalletTotalCredits = (
        await resource_usage_tracker_client.sum_total_available_credits_in_the_wallet(
            app, product_name, wallet_id
        )
    )
    return available_credits


async def add_credits_to_wallet(
    app: web.Application,
    product_name: ProductName,
    wallet_id: WalletID,
    wallet_name: str,
    user_id: UserID,
    user_email: str,
    osparc_credits: Decimal,
    payment_id: PaymentID,
    created_at: datetime,
) -> None:
    await resource_usage_tracker_client.add_credits_to_wallet(
        app=app,
        product_name=product_name,
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        user_id=user_id,
        user_email=user_email,
        osparc_credits=osparc_credits,
        payment_transaction_id=payment_id,
        created_at=created_at,
    )


__all__ = ("get_default_service_pricing_plan",)
