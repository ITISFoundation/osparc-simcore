import logging
import re
from pathlib import PurePosixPath
from typing import Any, Final
from urllib.parse import urlparse

import httpx
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from fastapi import status
from models_library.api_schemas_webserver.wallets import PaymentMethodTransaction
from models_library.notifications import Channel
from models_library.notifications.rpc import (
    EmailAddressing,
    EmailAttachment,
    EmailContact,
    TemplateRef,
)
from models_library.users import UserID
from pydantic import EmailStr
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    send_message_from_template,
)
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from ..db.payment_users_repo import PaymentsUsersRepo
from ..models.db import PaymentsTransactionsDB
from .notifier_abc import NotificationProvider

_logger = logging.getLogger(__name__)

_PAID_TEMPLATE_NAME = "paid"
_DEFAULT_INVOICE_FILENAME: Final[str] = "invoice.pdf"


def _retry_if_invoice_pdf_error(exception: BaseException) -> bool:
    if isinstance(exception, (httpx.ConnectError, httpx.ReadTimeout)):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in (
            status.HTTP_429_TOO_MANY_REQUESTS,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_502_BAD_GATEWAY,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            status.HTTP_504_GATEWAY_TIMEOUT,
        )
    return False


_INVOICE_PDF_TIMEOUT_SECONDS: Final[float] = 10.0
_INVOICE_PDF_RETRY_ATTEMPTS: Final[int] = 5
_INVOICE_PDF_RETRY_WAIT_MIN_SECONDS: Final[int] = 4
_INVOICE_PDF_RETRY_WAIT_MAX_SECONDS: Final[int] = 10

# Worst case for repeated read timeouts is about 70 seconds total:
# 5 attempts * 10 seconds timeout + waits of 4 + 4 + 4 + 8 seconds.
_INVOICE_PDF_TIMEOUT: Final = httpx.Timeout(_INVOICE_PDF_TIMEOUT_SECONDS)


@retry(
    retry=retry_if_exception(_retry_if_invoice_pdf_error),
    wait=wait_exponential(
        multiplier=1,
        min=_INVOICE_PDF_RETRY_WAIT_MIN_SECONDS,
        max=_INVOICE_PDF_RETRY_WAIT_MAX_SECONDS,
    ),
    stop=stop_after_attempt(_INVOICE_PDF_RETRY_ATTEMPTS),
    reraise=True,
)
async def _get_invoice_pdf(invoice_pdf: str) -> httpx.Response:
    async with httpx.AsyncClient(follow_redirects=True, timeout=_INVOICE_PDF_TIMEOUT) as client:
        _response = await client.get(invoice_pdf)
        _response.raise_for_status()
    return _response


_INVOICE_FILE_NAME_PATTERN: Final = re.compile(r'filename="(?P<filename>[^"]+)"')


def _extract_file_name(response: httpx.Response, url: str) -> str:
    content_disposition = response.headers.get("content-disposition", "")
    match = _INVOICE_FILE_NAME_PATTERN.search(content_disposition)
    if match:
        return match.group("filename")

    url_filename = PurePosixPath(urlparse(url).path).name
    if url_filename.lower().endswith(".pdf"):
        return url_filename
    return _DEFAULT_INVOICE_FILENAME


async def _download_invoice_pdf(url: str) -> tuple[bytes, str] | None:
    """Download invoice PDF and resolve its filename. Returns None on failure."""
    try:
        response = await _get_invoice_pdf(url)
    except httpx.HTTPError:
        _logger.warning("Failed to download invoice PDF from %s", url, exc_info=True)
        return None
    return response.content, _extract_file_name(response, url)


def _build_product_context(
    *,
    product_name: str,
    display_name: str,
    support_email: str,
    vendor: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the product template context from the product's vendor JSON.

    Mirrors the shape produced by ``services/web/server`` so the shared email
    templates render identically when emails are sent from the payments service.
    """
    vendor = vendor or {}
    ui = vendor.get("ui") or {}
    vendor_name = vendor.get("name")
    return {
        "product_name": product_name,
        "display_name": display_name,
        "vendor_display_inline": f"{vendor_name}" if vendor_name is not None else "IT'IS Foundation",
        "support_email": support_email,
        "homepage_url": vendor.get("url"),
        "ui": {
            "logo_url": ui.get("logo_url"),
            "strong_color": ui.get("strong_color"),
        },
        "footer": {
            "social_links": [{"name": name, "url": url} for name, url in vendor.get("footer_social_links", []) or []],
            "share_links": [
                {"name": name, "label": label, "url": url}
                for name, label, url in vendor.get("footer_share_links", []) or []
            ],
            "company_name": vendor.get("company_name", "") or "",
            "company_address": vendor.get("company_address", "") or "",
            "company_links": [{"name": name, "url": url} for name, url in vendor.get("company_links", []) or []],
        },
    }


class EmailProvider(NotificationProvider):
    def __init__(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient,
        users_repo: PaymentsUsersRepo,
        bcc_email: EmailStr | None = None,
    ):
        self._rabbitmq_rpc_client = rabbitmq_rpc_client
        self._users_repo = users_repo
        self._bcc_email = bcc_email

    async def notify_payment_completed(
        self,
        user_id: UserID,
        payment: PaymentsTransactionsDB,
    ) -> None:
        if payment.state != "SUCCESS":
            _logger.debug(
                "No email sent when %s did a non-SUCCESS %s",
                f"{user_id=}",
                f"{payment=}",
            )
            return

        data = await self._users_repo.get_notification_data(user_id, payment.payment_id)

        attachments: list[EmailAttachment] = []
        if payment.invoice_pdf_url:
            downloaded = await _download_invoice_pdf(str(payment.invoice_pdf_url))
            if downloaded is not None:
                pdf_content, pdf_filename = downloaded
                attachments.append(
                    EmailAttachment(
                        content=pdf_content,
                        filename=pdf_filename,
                    )
                )

        full_name = " ".join(part for part in (data.first_name, data.last_name) if part) or (data.user_name or "")

        addressing = EmailAddressing(
            from_=EmailContact(
                name=f"{data.display_name} support",
                email=data.support_email,
            ),
            to=[
                EmailContact(
                    name=full_name,
                    email=data.email,
                )
            ],
            bcc=EmailContact(name="", email=self._bcc_email) if self._bcc_email else None,
            attachments=attachments or None,
        )

        context: dict[str, Any] = {
            "user": {
                "first_name": data.first_name,
                "last_name": data.last_name,
                "user_name": data.user_name,
                "email": data.email,
            },
            "payment": {
                "price_dollars": f"{payment.price_dollars:.2f}",
                "osparc_credits": f"{payment.osparc_credits:.2f}",
                "invoice_url": f"{payment.invoice_url}" if payment.invoice_url else "",
            },
            "product": _build_product_context(
                product_name=data.product_name,
                display_name=data.display_name,
                support_email=data.support_email,
                vendor=data.vendor,
            ),
        }

        try:
            await send_message_from_template(
                self._rabbitmq_rpc_client,
                addressing=addressing,
                template_ref=TemplateRef(
                    channel=Channel.email,
                    template_name=_PAID_TEMPLATE_NAME,
                ),
                context=context,
            )
        except Exception as exc:  # pylint: disable=broad-except
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    "Failed to send payment completed email notification",
                    error=exc,
                    error_context={
                        "user_id": user_id,
                        "payment_id": payment.payment_id,
                        "template_name": _PAID_TEMPLATE_NAME,
                    },
                    tip="Check that the notifications service is running and the email template exists.",
                )
            )

    async def notify_payment_method_acked(
        self,
        user_id: UserID,
        payment_method: PaymentMethodTransaction,
    ) -> None:
        assert user_id  # nosec
        assert payment_method  # nosec
        _logger.debug("No email sent when payment method is acked")
