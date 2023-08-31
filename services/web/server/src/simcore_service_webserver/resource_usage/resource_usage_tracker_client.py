""" Requests to catalog service API

"""
import logging

from aiohttp import ClientSession, ClientTimeout, web
from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientResponseError,
    InvalidURL,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import NonNegativeInt
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
    url = (URL(settings.api_base_url) / "usage" / "services").with_query(
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
    user_id: UserID,
    product_name: str,
    wallet_id: WalletID,
    access_all_wallet_usage: bool,
    offset: int,
    limit: NonNegativeInt,
) -> dict:
    settings: ResourceUsageTrackerSettings = get_plugin_settings(app)
    url = (URL(settings.api_base_url) / "usage" / "services").with_query(
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
