import logging
import mimetypes
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from email.headerregistry import Address
from email.message import EmailMessage
from typing import Final

import httpx
from aiosmtplib import SMTP
from attr import dataclass
from jinja2 import DictLoader, Environment, select_autoescape
from models_library.api_schemas_webserver.wallets import PaymentMethodTransaction
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import EmailStr
from servicelib.logging_errors import create_troubleshootting_log_kwargs
from settings_library.email import EmailProtocol, SMTPSettings
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

from ..db.payment_users_repo import PaymentsUsersRepo
from ..models.db import PaymentsTransactionsDB
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
<title>{% block title %}{% endblock %}</title>
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
</style>
</head>
<body>
    {% block content %}
    {% endblock %}
</body>
</html>
"""


_NOTIFY_PAYMENTS_HTML = """
{% extends 'base.html' %}

{% block title %}Payment Confirmation{% endblock %}

{% block content %}
<p>Dear {{ user.first_name }},</p>
<p>We are delighted to confirm the successful processing of your payment of <strong>{{ payment.price_dollars }}</strong> <strong><em>USD</em></strong> for the purchase of <strong>{{ payment.osparc_credits }}</strong> <strong><em>credits</em></strong>.
The credits have been added to your {{ product.display_name }} account, and you are all set to utilize them.</p>
<p>For more details you can view or download your <a href="{{ payment.invoice_url }}">receipt</a>.</p>
<p>Please don't hesitate to contact us at {{ product.support_email }} if you need further help.</p>
<p>Best Regards,</p>
<p>The <i>{{ product.display_name }}</i> Team</p>
{% endblock %}
"""

_NOTIFY_PAYMENTS_TXT = """
Dear {{ user.first_name }},

We are delighted to confirm the successful processing of your payment of {{ payment.price_dollars }} USD for the purchase of {{ payment.osparc_credits }} credits. The credits have been added to your {{ product.display_name }} account, and you are all set to utilize them.

For more details you can view or download your receipt: {{ payment.invoice_url }}.

Please don't hesitate to contact us at {{ product.support_email }} if you need further help.

Best Regards,
The {{ product.display_name }} Team
"""


_NOTIFY_PAYMENTS_SUBJECT = "Your Payment {{ payment.price_dollars }} USD for {{ payment.osparc_credits }} Credits Was Successful"


_PRODUCT_NOTIFICATIONS_TEMPLATES = {
    "base.html": _BASE_HTML,
    "notify_payments.html": _NOTIFY_PAYMENTS_HTML,
    "notify_payments.txt": _NOTIFY_PAYMENTS_TXT,
    "notify_payments-subject.txt": _NOTIFY_PAYMENTS_SUBJECT,
}


@dataclass
class _UserData:
    first_name: str
    last_name: str
    email: str


@dataclass
class _ProductData:
    product_name: ProductName
    display_name: str
    vendor_display_inline: str
    support_email: str
    bcc_email: EmailStr | None = None


@dataclass
class _PaymentData:
    price_dollars: str
    osparc_credits: str
    invoice_url: str
    invoice_pdf_url: str


def retry_if_status_code(response):
    return response.status_code in (
        429,
        500,
        502,
        503,
        504,
    )  # Retry for these common transient errors


exception_retry_condition = retry_if_exception_type(
    (httpx.ConnectError, httpx.ReadTimeout)
)
result_retry_condition = retry_if_result(retry_if_status_code)


@retry(
    retry=exception_retry_condition | result_retry_condition,
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def _get_invoice_pdf(invoice_pdf: str) -> httpx.Response:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        _response = await client.get(invoice_pdf)
        _response.raise_for_status()
    return _response


_INVOICE_FILE_NAME_PATTERN: Final = re.compile(r'filename="(?P<filename>[^"]+)"')


def _extract_file_name(response: httpx.Response) -> str:
    match = _INVOICE_FILE_NAME_PATTERN.search(response.headers["content-disposition"])
    if not match:
        error_msg = f"Cannot file pdf invoice {response.request.url}"
        raise RuntimeError(error_msg)

    file_name: str = match.group("filename")
    return file_name


def _guess_file_type(filename: str) -> tuple[str, str]:
    mimetype, _encoding = mimetypes.guess_type(filename)
    if mimetype:
        maintype, subtype = mimetype.split("/", maxsplit=1)
    else:
        maintype, subtype = "application", "octet-stream"
    return maintype, subtype


async def _create_user_email(
    env: Environment,
    user: _UserData,
    payment: _PaymentData,
    product: _ProductData,
) -> EmailMessage:
    # data to interpolate template
    data = {
        "user": user,
        "product": product,
        "payment": payment,
    }

    email_msg = EmailMessage()

    email_msg["From"] = Address(
        display_name=f"{product.display_name} support",
        addr_spec=product.support_email,
    )
    email_msg["To"] = Address(
        display_name=f"{user.first_name} {user.last_name}",
        addr_spec=user.email,
    )
    email_msg["Subject"] = env.get_template("notify_payments-subject.txt").render(data)

    if product.bcc_email:
        email_msg["Bcc"] = product.bcc_email

    # Body
    text_template = env.get_template("notify_payments.txt")
    email_msg.set_content(text_template.render(data))

    html_template = env.get_template("notify_payments.html")
    email_msg.add_alternative(html_template.render(data), subtype="html")

    if payment.invoice_pdf_url:
        try:
            # Invoice attachment (It is important that attachment is added after body)
            pdf_response = await _get_invoice_pdf(payment.invoice_pdf_url)

            # file
            file_name = _extract_file_name(pdf_response)
            main_type, sub_type = _guess_file_type(file_name)

            pdf_data = pdf_response.content

            email_msg.add_attachment(
                pdf_data,
                filename=file_name,
                maintype=main_type,
                subtype=sub_type,
            )

        except Exception as exc:  # pylint: disable=broad-exception-caught
            _logger.exception(
                **create_troubleshootting_log_kwargs(
                    "Cannot attach invoice to payment. Email sent w/o attached pdf invoice",
                    error=exc,
                    error_context={
                        "user": user,
                        "payment": payment,
                        "product": product,
                    },
                    tip=f"Check downloading: `wget -v {payment.invoice_pdf_url}`",
                )
            )

    return email_msg


@asynccontextmanager
async def _create_email_session(
    settings: SMTPSettings,
) -> AsyncIterator[SMTP]:
    async with SMTP(
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
            assert settings.SMTP_USERNAME  # nosec
            assert settings.SMTP_PASSWORD  # nosec
            await smtp.login(
                settings.SMTP_USERNAME,
                settings.SMTP_PASSWORD.get_secret_value(),
            )

        yield smtp


class EmailProvider(NotificationProvider):
    def __init__(
        self,
        settings: SMTPSettings,
        users_repo: PaymentsUsersRepo,
        bcc_email: EmailStr | None = None,
    ):
        self._users_repo = users_repo
        self._settings = settings
        self._bcc_email = bcc_email
        self._jinja_env = Environment(
            loader=DictLoader(_PRODUCT_NOTIFICATIONS_TEMPLATES),
            autoescape=select_autoescape(["html", "xml"]),
        )

    async def _create_successful_payments_message(
        self,
        user_id: UserID,
        payment: PaymentsTransactionsDB,
    ) -> EmailMessage:
        data = await self._users_repo.get_notification_data(user_id, payment.payment_id)
        data_vendor = data.vendor or {}

        # email for successful payment
        msg: EmailMessage = await _create_user_email(
            self._jinja_env,
            user=_UserData(
                first_name=data.first_name,
                last_name=data.last_name,
                email=data.email,
            ),
            payment=_PaymentData(
                price_dollars=f"{payment.price_dollars:.2f}",
                osparc_credits=f"{payment.osparc_credits:.2f}",
                invoice_url=f"{payment.invoice_url}",
                invoice_pdf_url=f"{payment.invoice_pdf_url}",
            ),
            product=_ProductData(
                product_name=data.product_name,
                display_name=data.display_name,
                vendor_display_inline=f"{data_vendor.get('name', '')}. {data_vendor.get('address', '')}",
                support_email=data.support_email,
                bcc_email=self._bcc_email,
            ),
        )

        return msg

    async def notify_payment_completed(
        self,
        user_id: UserID,
        payment: PaymentsTransactionsDB,
    ):
        # NOTE: we only have an email for successful payments
        if payment.state == "SUCCESS":
            msg = await self._create_successful_payments_message(user_id, payment)

            async with _create_email_session(self._settings) as smtp:
                await smtp.send_message(msg)
        else:
            _logger.debug(
                "No email sent when %s did a non-SUCCESS %s",
                f"{user_id=}",
                f"{payment=}",
            )

    async def notify_payment_method_acked(
        self,
        user_id: UserID,
        payment_method: PaymentMethodTransaction,
    ):
        assert user_id  # nosec
        assert payment_method  # nosec
        _logger.debug("No email sent when payment method is acked")
