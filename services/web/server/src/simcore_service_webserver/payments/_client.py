""" client for the RPC API in the payments service

"""

import asyncio
import logging
from decimal import Decimal
from uuid import uuid4

from aiohttp import web
from models_library.api_schemas_webserver.wallets import WalletPaymentCreated
from models_library.users import UserID
from models_library.wallets import WalletID
from yarl import URL

from .settings import PaymentsSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


async def create_fake_payment(
    app: web.Application,
    *,
    price_dollars: Decimal,
    osparc_credits: Decimal,
    product_name: str,
    user_id: UserID,
    name: str,
    email: str,
):
    assert osparc_credits > 0  # nosec
    assert name  # nosec
    assert email  # nosec
    assert product_name  # nosec
    assert price_dollars > 0  # nosec

    body = {
        "price_dollars": price_dollars,
        "osparc_credits": osparc_credits,
        "user_id": user_id,
        "name": name,
        "email": email,
    }

    # Fake response of payment service --------
    _logger.info("Sending -> payments-service %s", body)
    await asyncio.sleep(1)
    transaction_id = f"{uuid4()}"
    # -------------

    settings: PaymentsSettings = get_plugin_settings(app)
    base_url = URL(settings.PAYMENTS_FAKE_GATEWAY_URL)
    submission_link = base_url.with_path("/pay").with_query(id=transaction_id)
    return submission_link, transaction_id


async def init_payment(
    app: web.Application,
    *,
    amount_dollars: Decimal,
    target_credits: Decimal,
    product_name: str,
    wallet_id: WalletID,
    wallet_name: str,
    user_id: UserID,
    user_name: str,
    user_email: str,
    comment: str | None = None,
) -> WalletPaymentCreated:
    raise NotImplementedError
    # result = await rpc_client.request(
    #         PAYMENTS_RPC_NAMESPACE,
    #         parse_obj_as(RPCMethodName, "init_payment"),
    #         **init_payment_kwargs,
    #     )

    # assert isinstance(result, WalletPaymentCreated)
