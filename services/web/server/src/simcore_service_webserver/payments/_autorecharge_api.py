import logging

from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    GetWalletAutoRecharge,
    ReplaceWalletAutoRecharge,
)
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID

from ._autorecharge_db import (
    PaymentsAutorechargeDB,
    get_wallet_autorecharge,
    replace_wallet_autorecharge,
)
from ._methods_db import list_successful_payment_methods
from ._onetime_api import (
    raise_for_wallet_read_n_write_permissions,
    raise_for_wallet_read_permissions,
)
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


def _from_db_to_api_model(db_model: PaymentsAutorechargeDB) -> GetWalletAutoRecharge:
    return GetWalletAutoRecharge(
        enabled=db_model.enabled,
        payment_method_id=db_model.primary_payment_method_id,
        min_balance_in_usd=db_model.min_balance_in_usd,
        top_up_amount_in_usd=db_model.top_up_amount_in_usd,
        top_up_countdown=db_model.top_up_countdown,
    )


def _from_api_to_db_model(
    wallet_id: WalletID, api_model: ReplaceWalletAutoRecharge
) -> PaymentsAutorechargeDB:
    return PaymentsAutorechargeDB(
        wallet_id=wallet_id,
        enabled=api_model.enabled,
        primary_payment_method_id=api_model.payment_method_id,
        min_balance_in_usd=api_model.min_balance_in_usd,
        top_up_amount_in_usd=api_model.top_up_amount_in_usd,
        top_up_countdown=api_model.top_up_countdown,
    )


#
# payment-autorecharge api
#

_NEWEST = 0


async def get_wallet_payment_autorecharge(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    wallet_id: WalletID,
) -> GetWalletAutoRecharge:
    await raise_for_wallet_read_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )

    got: PaymentsAutorechargeDB | None = await get_wallet_autorecharge(
        app, wallet_id=wallet_id
    )
    if not got:
        settings = get_plugin_settings(app)
        payment_method_id = None
        wallet_payment_methods = await list_successful_payment_methods(
            app,
            user_id=user_id,
            wallet_id=wallet_id,
        )
        if wallet_payment_methods:
            payment_method_id = wallet_payment_methods[_NEWEST].payment_method_id

        return GetWalletAutoRecharge(
            enabled=False,
            payment_method_id=payment_method_id,
            min_balance_in_usd=settings.PAYMENTS_AUTORECHARGE_DEFAULT_MIN_BALANCE,
            top_up_amount_in_usd=settings.PAYMENTS_AUTORECHARGE_DEFAULT_TOP_UP_AMOUNT,
            top_up_countdown=None,
        )

    return _from_db_to_api_model(got)


async def replace_wallet_payment_autorecharge(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    wallet_id: WalletID,
    new: ReplaceWalletAutoRecharge,
) -> GetWalletAutoRecharge:
    await raise_for_wallet_read_n_write_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )

    got: PaymentsAutorechargeDB = await replace_wallet_autorecharge(
        app,
        user_id=user_id,
        wallet_id=wallet_id,
        new=_from_api_to_db_model(wallet_id, new),
    )

    return _from_db_to_api_model(got)
