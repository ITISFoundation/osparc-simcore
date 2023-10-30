""" Misc that does not fit on other modules

Functions/classes that are too small to create a new module or helpers within this plugin's context are placed here

"""

import asyncio
import logging

import aiohttp
from aiohttp import ClientTimeout, web
from models_library.projects import ProjectID
from models_library.users import UserID
from models_library.wallets import ZERO_CREDITS, WalletID, WalletInfo
from pydantic import parse_obj_as

from ..application_settings import get_settings
from ..products.api import Product
from ..projects import projects_api
from ..users import preferences_api as user_preferences_api
from ..users.exceptions import UserDefaultWalletNotFoundError
from ..wallets import api as wallets_api
from ..wallets.errors import WalletNotEnoughCreditsError
from ._abc import AbstractProjectRunPolicy
from .settings import DirectorV2Settings, get_client_session, get_plugin_settings

log = logging.getLogger(__name__)


SERVICE_HEALTH_CHECK_TIMEOUT = ClientTimeout(total=2, connect=1)


async def is_healthy(app: web.Application) -> bool:
    try:
        session = get_client_session(app)
        settings: DirectorV2Settings = get_plugin_settings(app)
        health_check_url = settings.base_url.parent
        await session.get(
            url=health_check_url,
            ssl=False,
            raise_for_status=True,
            timeout=SERVICE_HEALTH_CHECK_TIMEOUT,
        )
        return True
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        # SEE https://docs.aiohttp.org/en/stable/client_reference.html#hierarchy-of-exceptions
        log.warning("Director is NOT healthy: %s", err)
        return False


class DefaultProjectRunPolicy(AbstractProjectRunPolicy):
    # pylint: disable=unused-argument

    async def get_runnable_projects_ids(
        self,
        request: web.Request,
        project_uuid: ProjectID,
    ) -> list[ProjectID]:
        return [
            project_uuid,
        ]

    async def get_or_create_runnable_projects(
        self,
        request: web.Request,
        project_uuid: ProjectID,
    ) -> tuple[list[ProjectID], list[int]]:
        """
        Returns ids and refid of projects that can run
        If project_uuid is a std-project, then it returns itself
        If project_uuid is a meta-project, then it returns iterations
        """
        return (
            [
                project_uuid,
            ],
            [],
        )


async def get_wallet_info(
    app: web.Application,
    *,
    product: Product,
    user_id: UserID,
    project_id: ProjectID,
    product_name: str,
) -> WalletInfo | None:
    app_settings = get_settings(app)
    if not (
        product.is_payment_enabled and app_settings.WEBSERVER_CREDIT_COMPUTATION_ENABLED
    ):
        return None
    project_wallet = await projects_api.get_project_wallet(app, project_id=project_id)
    if project_wallet is None:
        user_default_wallet_preference = await user_preferences_api.get_frontend_user_preference(
            app,
            user_id=user_id,
            product_name=product_name,
            preference_class=user_preferences_api.PreferredWalletIdFrontendUserPreference,
        )
        if user_default_wallet_preference is None:
            raise UserDefaultWalletNotFoundError(uid=user_id)
        project_wallet_id = parse_obj_as(WalletID, user_default_wallet_preference.value)
        await projects_api.connect_wallet_to_project(
            app,
            product_name=product_name,
            project_id=project_id,
            user_id=user_id,
            wallet_id=project_wallet_id,
        )
    else:
        project_wallet_id = project_wallet.wallet_id

    # Check whether user has access to the wallet
    wallet = await wallets_api.get_wallet_with_available_credits_by_user_and_wallet(
        app,
        user_id=user_id,
        wallet_id=project_wallet_id,
        product_name=product_name,
    )
    if wallet.available_credits <= ZERO_CREDITS:
        raise WalletNotEnoughCreditsError(
            reason=f"Wallet {wallet.wallet_id} credit balance {wallet.available_credits}"
        )
    return WalletInfo(wallet_id=project_wallet_id, wallet_name=wallet.name)
