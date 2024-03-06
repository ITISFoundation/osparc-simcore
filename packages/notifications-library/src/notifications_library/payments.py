import logging
from dataclasses import dataclass

from models_library.api_schemas_webserver.wallets import (
    PaymentMethodTransaction,
    PaymentTransaction,
)
from models_library.users import UserID

from ._templates import get_email_templates

_logger = logging.getLogger(__name__)


_ON_PAYED_EVENT_EMAIL_TEMPLATES = {
    "base.html",
} | set(get_email_templates(event_name="on_payed"))


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
