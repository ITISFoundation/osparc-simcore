import functools

from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.aiohttp.observer import register_observer, setup_observer_registry

from ..users import preferences_api
from ._api import any_wallet_owned_by_user, create_wallet


async def _auto_add_default_wallet(
    app: web.Application, user_id: UserID, product_name: ProductName
):
    if not await any_wallet_owned_by_user(
        app, user_id=user_id, product_name=product_name
    ):
        wallet = await create_wallet(
            app,
            user_id=user_id,
            wallet_name="Credits",
            description="Purchased credits end up in here",
            thumbnail=None,
            product_name=product_name,
        )

        preference_id = (
            preferences_api.PreferredWalletIdFrontendUserPreference().preference_identifier
        )
        await preferences_api.set_frontend_user_preference(
            app,
            user_id=user_id,
            product_name=product_name,
            frontend_preference_identifier=preference_id,
            value=wallet.wallet_id,
        )


async def _on_user_confirmation(
    app: web.Application, user_id: UserID, product_name: ProductName
):
    await _auto_add_default_wallet(app, user_id=user_id, product_name=product_name)


def setup_wallets_events(app: web.Application):
    # ensures registry in place
    setup_observer_registry(app)

    # registers SIGNAL_ON_USER_CONFIRMATION
    # NOTE: should follow up on https://github.com/ITISFoundation/osparc-simcore/issues/4822
    register_observer(
        app,
        functools.partial(_on_user_confirmation, app=app),
        event="SIGNAL_ON_USER_CONFIRMATION",
    )
