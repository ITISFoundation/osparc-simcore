import logging

from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    GetWalletAutoRecharge,
    ReplaceWalletAutoRecharge,
)
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID

from ._api import check_wallet_permissions
from ._autorecharge_db import (
    PaymentsAutorechargeDB,
    get_wallet_autorecharge,
    replace_wallet_autorecharge,
)

_logger = logging.getLogger(__name__)


#
# payment-autorecharge
#


def from_db(got: PaymentsAutorechargeDB) -> GetWalletAutoRecharge:
    return GetWalletAutoRecharge(
        enabled=got.enabled,
        payment_method_id=got.primary_payment_method_id,
        min_balance_in_usd=got.min_balance_in_usd,
        inc_payment_amount_in_usd=got.inc_payment_amount_in_usd,
        inc_payment_countdown=(
            "UNLIMITED"
            if got.inc_payment_countdown is None
            else got.inc_payment_countdown
        ),
    )


def to_db(
    wallet_id: WalletID, new: ReplaceWalletAutoRecharge
) -> PaymentsAutorechargeDB:
    # There is a validator in  ReplaceWalletAutoRecharge to ensure these
    assert new.enabled
    assert new.payment_method_id  # nosec
    assert new.min_balance_in_usd  # nosec
    assert new.inc_payment_amount_in_usd  # nosec

    return PaymentsAutorechargeDB(
        wallet_id=wallet_id,
        enabled=new.enabled,
        primary_payment_method_id=new.payment_method_id,
        min_balance_in_usd=new.min_balance_in_usd,
        inc_payment_amount_in_usd=new.inc_payment_amount_in_usd,
        inc_payment_countdown=(
            None
            if new.inc_payment_countdown == "UNLIMITED"
            else new.inc_payment_countdown
        ),
    )


async def get_wallet_payment_autorecharge(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    wallet_id: WalletID,
) -> GetWalletAutoRecharge:
    await check_wallet_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )

    ar_db: PaymentsAutorechargeDB | None = await get_wallet_autorecharge(
        app, wallet_id=wallet_id
    )
    if not ar_db:
        # default
        return GetWalletAutoRecharge(
            enabled=False,
            payment_method_id=None,
            min_balance_in_usd=None,
            inc_payment_amount_in_usd=None,
            inc_payment_countdown="UNLIMITED",
        )
    return from_db(ar_db)


async def replace_wallet_payment_autorecharge(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    wallet_id: WalletID,
    new: ReplaceWalletAutoRecharge,
):
    await check_wallet_permissions(
        app, user_id=user_id, wallet_id=wallet_id, product_name=product_name
    )

    ar_db: PaymentsAutorechargeDB = await replace_wallet_autorecharge(
        app, user_id=user_id, wallet_id=wallet_id, auto_recharge=to_db(new)
    )

    return from_db(ar_db)
