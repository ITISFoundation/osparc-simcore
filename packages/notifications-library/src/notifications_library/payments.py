import logging
from dataclasses import dataclass

from models_library.api_schemas_webserver.wallets import (
    PaymentMethodTransaction,
    PaymentTransaction,
)
from models_library.users import UserID

_logger = logging.getLogger(__name__)


_PRODUCT_NOTIFICATIONS_TEMPLATES = {
    "base.html",
    "notify_payments.email.html",
    "notify_payments.email.txt",
    "notify_payments.email.subject.txt",
}


@dataclass
class PaymentData:
    price_dollars: str
    osparc_credits: str
    invoice_url: str


async def notify_payment_completed(
    user_id: UserID,
    payment: PaymentTransaction,
):
    assert user_id  # nosec
    assert payment  # nosec
    raise NotImplementedError


async def notify_payment_method_acked(
    user_id: UserID,
    payment_method: PaymentMethodTransaction,
):
    assert user_id  # nosec
    assert payment_method  # nosec
    raise NotImplementedError
