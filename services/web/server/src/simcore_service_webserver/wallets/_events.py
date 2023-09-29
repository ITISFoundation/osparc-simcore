import functools

from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.aiohttp.observer import register_observer, setup_observer_registry

from ._api import create_wallet, list_wallets_for_user


async def _auto_add_default_wallet(
    app: web.Application, user_id: UserID, product_name: ProductName
):
    # TODO: check ANY OWNED wallets!
    if not await list_wallets_for_user(app, user_id=user_id, product_name=product_name):
        await create_wallet(
            app,
            user_id=user_id,
            wallet_name="Credits",
            description=None,
            thumbnail=None,
            product_name=product_name,
        )


async def _on_user_registration(
    app: web.Application, user_id: UserID, product_name: ProductName
):
    await _auto_add_default_wallet(app, user_id=user_id, product_name=product_name)


def setup_wallets_events(app: web.Application):
    # ensures registry in place
    setup_observer_registry(app)

    # registers SIGNAL_ON_USER_REGISTERED
    register_observer(
        app,
        functools.partial(_on_user_registration, app=app),
        event="SIGNAL_ON_USER_REGISTERED",
    )
