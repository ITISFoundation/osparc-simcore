import logging
import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from email.headerregistry import Address
from email.message import EmailMessage
from pathlib import Path
from typing import Final, cast

import aiosmtplib
from attr import dataclass
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodTransaction,
    PaymentTransaction,
)
from models_library.products import ProductName
from models_library.users import UserID
from settings_library.email import EmailProtocol, SMTPSettings

from ..db.payment_users_repo import PaymentsUsersRepo
from .notifier_abc import NotificationProvider

_logger = logging.getLogger(__name__)

_BASE_HTML: Final[
    str
] = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Payment Confirmation</title>
<style>
    body {
        font-family: Arial, sans-serif;
        margin: 0;
        padding: 20px;
        color: #333;
    }
    .container {
        background-color: #f9f9f9;
        padding: 20px;
        border-radius: 5px;
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
    }
    a {
        color: #007bff;
        text-decoration: none;
    }
    .button {
        display: inline-block;
        padding: 10px 20px;
        font-size: 18px;
        cursor: pointer;
        text-align: center;
        text-decoration: none;
        outline: none;
        color: #fff;
        background-color: #007bff;
        border: none;
        border-radius: 5px;
        box-shadow: 0 9px #999;
    }
    .button:hover {background-color: #0056b3}
    .button:active {
        background-color: #0056b3;
        box-shadow: 0 5px #666;
        transform: translateY(4px);
    }
</style>
</head>
<body>
    <div class="container">
        {0}
    </div>
</body>
</html>
"""


def _guess_file_type(file_path: Path) -> tuple[str, str]:
    assert file_path.is_file()
    mimetype, _encoding = mimetypes.guess_type(file_path)
    if mimetype:
        maintype, subtype = mimetype.split("/", maxsplit=1)
    else:
        maintype, subtype = "application", "octet-stream"
    return maintype, subtype


def _add_attachments(msg: EmailMessage, file_paths: list[Path]):
    for attachment_path in file_paths:
        maintype, subtype = _guess_file_type(attachment_path)
        msg.add_attachment(
            attachment_path.read_bytes(),
            filename=attachment_path.name,
            maintype=maintype,
            subtype=subtype,
        )


@asynccontextmanager
async def _create_email_session(
    settings: SMTPSettings,
) -> AsyncIterator[aiosmtplib.SMTP]:
    async with aiosmtplib.SMTP(
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        # FROM https://aiosmtplib.readthedocs.io/en/stable/usage.html#starttls-connections
        # By default, if the server advertises STARTTLS support, aiosmtplib will upgrade the connection automatically.
        # Setting use_tls=True for STARTTLS servers will typically result in a connection error
        # To opt out of STARTTLS on connect, pass start_tls=False.
        # NOTE: for that reason TLS and STARTLS are mutally exclusive
        use_tls=settings.SMTP_PROTOCOL == EmailProtocol.TLS,
        start_tls=settings.SMTP_PROTOCOL == EmailProtocol.STARTTLS,
    ) as smtp:
        if settings.has_credentials:
            assert settings.SMTP_USERNAME
            assert settings.SMTP_PASSWORD
            await smtp.login(
                settings.SMTP_USERNAME,
                settings.SMTP_PASSWORD.get_secret_value(),
            )

        yield cast(aiosmtplib.SMTP, smtp)


@dataclass
class _ProductInfo:
    product_name: ProductName
    display_name: str
    vendor_display_inline: str
    support_email: str


async def _compose_subject_and_content(
    msg: EmailMessage, user, payment: PaymentTransaction, product: _ProductInfo
) -> EmailMessage:
    # TODO: templates come here. Keep it async

    msg[
        "Subject"
    ] = f"Your Payment {payment.price_dollars:2.f} USD for {payment.osparc_credits:2.f} Credits Was Successful"

    msg.set_content(
        f"""\
        Dear {user.first_name},

        We are delighted to confirm the successful processing of your payment of <strong>{payment.price_dollars:2.f}</strong> for the purchase of {payment.osparc_credits:2.f} credits. The credits have been added to your {product.display_name} account, and you are all set to utilize them.

        To view or download your detailed receipt, please click the following link: {payment.invoice_url}

        If you have any questions or need further assistance, please do not hesitate to reach out to our customer support team at {product.support_email}

        Best Regards,

        {product.display_name} support team
        {product.vendor_display_inline}
        """
    )

    msg.add_alternative(
        _BASE_HTML.format(
            f"""\
        <p>Dear {user.first_name},</p>
        <p>We are delighted to confirm the successful processing of your payment of <strong>{payment.price_dollars:2.f}</strong> for the purchase of {payment.osparc_credits:2.f} credits. The credits have been added to your {product.display_name} account, and you are all set to utilize them.</p>
        <p>To view or download your detailed receipt, please click the button below:</p>
        <p><a href="{payment.invoice_url}" class="button">View Receipt</a></p>
        <p>Should you have any questions or require further assistance, please do not hesitate to reach out to our <a href="mailto:{product.support_email}">customer support team</a>.</p>
        <p>Best Regards,</p>
        <p>{product.display_name} support team<br>{product.vendor_display_inline}</p>
        """
        )
    )
    return msg


async def _create_user_email(
    user, payment: PaymentTransaction, product: _ProductInfo
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = Address(
        display_name=f"{product.display_name} support",
        addr_spec=product.support_email,
    )
    msg["To"] = Address(
        display_name=f"{user.first_name} {user.last_name}",
        addr_spec=user.email,
    )
    await _compose_subject_and_content(msg, user, payment, product)
    return msg


class EmailProvider(NotificationProvider):
    # interfaces with the notification system
    def __init__(self, settings: SMTPSettings, users_repo: PaymentsUsersRepo):
        self._users_repo = users_repo
        self._settings = settings

    async def on_app_startup(self):
        # TODO: get templates from db upon start and not everytime
        raise NotImplementedError

    async def _create_message(
        self, user_id: UserID, payment: PaymentTransaction
    ) -> EmailMessage:

        # retrieve info
        user = await self._users_repo.get_email_info(user_id)
        product = _ProductInfo(
            product_name="osparc",
            display_name="o²S²PARC",
            vendor_display_inline="IT'IS Foundation. Zeughausstrasse 43, 8004 Zurich, Switzerland ",
            support_email="support@osparc.io",
        )

        # TODO: product? via wallet_id?
        # TODO: ger support email and display name

        # compose email
        msg: EmailMessage = await _create_user_email(
            user, payment=payment, product=product
        )

        return msg

    async def notify_payment_completed(
        self,
        user_id: UserID,
        payment: PaymentTransaction,
    ):
        msg = await self._create_message(user_id, payment)

        async with _create_email_session(self._settings) as smtp:
            await smtp.send_message(msg)

    async def notify_payment_method_acked(
        self,
        user_id: UserID,
        payment_method: PaymentMethodTransaction,
    ):
        assert user_id  # nosec
        assert payment_method  # nosec
        _logger.debug("Nothing to send here")
