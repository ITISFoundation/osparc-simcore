""" Requests to catalog service API

"""
import logging
import urllib.parse
from datetime import datetime
from decimal import Decimal

from aiohttp import ClientSession, ClientTimeout, web
from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientResponseError,
    InvalidURL,
)
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanGet,
    PricingUnitGet,
)
from models_library.resource_tracker import PricingPlanId, PricingUnitId
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import NonNegativeInt, parse_obj_as
from servicelib.aiohttp.client_session import get_client_session
from settings_library.resource_usage_tracker import ResourceUsageTrackerSettings
from yarl import URL

from ._utils import handle_client_exceptions
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


async def list_service_runs_by_user_and_product(
    app: web.Application,
    user_id: UserID,
    product_name: str,
    offset: int,
    limit: NonNegativeInt,
) -> dict:
    settings: ResourceUsageTrackerSettings = get_plugin_settings(app)
    url = (URL(settings.api_base_url) / "services" / "-" / "usages").with_query(
        {
            "user_id": user_id,
            "product_name": product_name,
            "offset": offset,
            "limit": limit,
        }
    )
    with handle_client_exceptions(app) as session:
        async with session.get(url) as response:
            body: dict = await response.json()
            return body


async def list_service_runs_by_user_and_product_and_wallet(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: str,
    wallet_id: WalletID,
    access_all_wallet_usage: bool,
    offset: int,
    limit: NonNegativeInt,
) -> dict:
    settings: ResourceUsageTrackerSettings = get_plugin_settings(app)
    url = (URL(settings.api_base_url) / "services" / "-" / "usages").with_query(
        {
            "user_id": user_id,
            "product_name": product_name,
            "wallet_id": wallet_id,
            "access_all_wallet_usage": f"{access_all_wallet_usage}".lower(),
            "offset": offset,
            "limit": limit,
        }
    )
    with handle_client_exceptions(app) as session:
        async with session.get(url) as response:
            body: dict = await response.json()
            return body


async def get_default_service_pricing_plan(
    app: web.Application, product_name: str, service_key: str, service_version: str
) -> PricingPlanGet:
    settings: ResourceUsageTrackerSettings = get_plugin_settings(app)
    url = URL(
        f"{settings.api_base_url}/services/{urllib.parse.quote_plus(service_key)}/{service_version}/pricing-plan",
        encoded=True,
    ).with_query(
        {
            "product_name": product_name,
        }
    )
    with handle_client_exceptions(app) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            body: dict = await response.json()
            return parse_obj_as(PricingPlanGet, body)


async def get_pricing_plan_unit(
    app: web.Application,
    product_name: str,
    pricing_plan_id: PricingPlanId,
    pricing_unit_id: PricingUnitId,
) -> PricingUnitGet:
    settings: ResourceUsageTrackerSettings = get_plugin_settings(app)
    url = (
        URL(settings.api_base_url)
        / "pricing-plans"
        / str(pricing_plan_id)
        / "pricing-units"
        / str(pricing_unit_id)
    ).with_query(
        {
            "product_name": product_name,
        }
    )
    with handle_client_exceptions(app) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            body: dict = await response.json()
            return parse_obj_as(PricingUnitGet, body)


async def sum_total_available_credits_in_the_wallet(
    app: web.Application,
    product_name: str,
    wallet_id: WalletID,
) -> WalletTotalCredits:
    settings: ResourceUsageTrackerSettings = get_plugin_settings(app)
    url = (
        URL(settings.api_base_url) / "credit-transactions" / "credits:sum"
    ).with_query(
        {
            "product_name": product_name,
            "wallet_id": wallet_id,
        }
    )
    with handle_client_exceptions(app) as session:
        async with session.post(url) as response:
            response.raise_for_status()
            body: dict = await response.json()
            return WalletTotalCredits.construct(**body)


async def add_credits_to_wallet(
    app: web.Application,
    product_name: str,
    wallet_id: WalletID,
    wallet_name: str,
    user_id: UserID,
    user_email: str,
    osparc_credits: Decimal,
    payment_transaction_id: str,
    created_at: datetime,
) -> dict:
    settings: ResourceUsageTrackerSettings = get_plugin_settings(app)
    url = URL(settings.api_base_url) / "credit-transactions"
    body = {
        "product_name": product_name,
        "wallet_id": wallet_id,
        "wallet_name": wallet_name,
        "user_id": user_id,
        "user_email": user_email,
        "osparc_credits": osparc_credits,
        "payment_transaction_id": payment_transaction_id,
        "created_at": created_at,
    }
    with handle_client_exceptions(app) as session:
        async with session.post(url, json=body) as response:
            response.raise_for_status()
            output: dict = await response.json()
            return output


async def is_resource_usage_tracking_service_responsive(app: web.Application) -> bool:
    """Returns true if resource usage tracker is ready"""
    try:
        session: ClientSession = get_client_session(app)
        settings: ResourceUsageTrackerSettings = get_plugin_settings(app)

        await session.get(
            settings.base_url,
            ssl=False,
            raise_for_status=True,
            timeout=ClientTimeout(total=2, connect=1),
        )
    except (ClientConnectionError, ClientResponseError, InvalidURL, ValueError):
        return False
    return True
