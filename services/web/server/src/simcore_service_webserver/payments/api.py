import logging

from aiohttp import web
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import PositiveFloat

from ._client import get_payments_service_api

_logger = logging.getLogger(__name__)


async def create_payment_to_wallet(
    app: web.Application,
    product_name: str,
    user_id: UserID,
    wallet_id: WalletID,
    prize: PositiveFloat,
    credit: PositiveFloat,
):
    # is user wallet?
    #
    raise NotImplementedError


async def get_user_payments_page(
    app: web.Application,
    product_name: str,
    user_id: UserID,
    *,
    limit: int,
    offset: int,
) -> tuple[list, int]:
    assert limit > 1  # nosec
    assert offset >= 0  # nosec

    payments_service = get_payments_service_api(app)
    await payments_service.is_healthy()

    raise NotImplementedError


assert get_payments_service_api  # nosec

__all__: tuple[str, ...] = (
    "get_payments_service_api",
    "create_payment_to_wallet",
    "get_user_payments_page",
)
