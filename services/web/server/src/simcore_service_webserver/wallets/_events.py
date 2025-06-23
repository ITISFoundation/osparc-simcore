import functools

from aiohttp import web
from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import PositiveInt
from servicelib.aiohttp.observer import register_observer, setup_observer_registry

from ..products import products_service
from ..resource_usage.service import add_credits_to_wallet
from ..users import preferences_api
from ..users.api import get_user_display_and_id_names
from ._api import any_wallet_owned_by_user, create_wallet

_WALLET_NAME_TEMPLATE = "{} Credits"
_WALLET_DESCRIPTION_TEMPLATE = "Credits purchased by {} end up in here"


async def _auto_add_default_wallet(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    extra_credits_in_usd: PositiveInt | None = None,
):
    if not await any_wallet_owned_by_user(
        app, user_id=user_id, product_name=product_name
    ):
        user = await get_user_display_and_id_names(app, user_id=user_id)
        product = products_service.get_product(app, product_name)

        wallet = await create_wallet(
            app,
            user_id=user_id,
            wallet_name=_WALLET_NAME_TEMPLATE.format(user.full_name),
            description=_WALLET_DESCRIPTION_TEMPLATE.format(user.full_name),
            thumbnail=None,
            product_name=product_name,
        )

        if extra_credits_in_usd and product.is_payment_enabled:
            assert product.credits_per_usd  # nosec
            await add_credits_to_wallet(
                app,
                product_name=product_name,
                wallet_id=wallet.wallet_id,
                wallet_name=wallet.name,
                user_id=user_id,
                user_email=user.email,
                osparc_credits=extra_credits_in_usd * product.credits_per_usd,
                payment_id=IDStr("INVITATION"),
                created_at=wallet.created,
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
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    extra_credits_in_usd: PositiveInt,
):
    await _auto_add_default_wallet(
        app,
        user_id=user_id,
        product_name=product_name,
        extra_credits_in_usd=extra_credits_in_usd,
    )


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
