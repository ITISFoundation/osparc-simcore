import logging
from urllib.parse import urlparse

import httpx
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
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

from ..db.payment_users_repo import PaymentsUsersRepo
from ..models.db import PaymentsTransactionsDB
from .notifier_abc import NotificationProvider

_logger = logging.getLogger(__name__)

_PAID_TEMPLATE_NAME = "paid"


async def _download_invoice_pdf(url: str) -> bytes | None:
    """Download invoice PDF content from the given URL. Returns None on failure."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()
            return response.content
    except httpx.HTTPError:
        _logger.warning("Failed to download invoice PDF from %s", url, exc_info=True)
        return None


def _extract_pdf_filename(url: str) -> str:
    path = urlparse(url).path
    filename = path.rsplit("/", maxsplit=1)[-1] if "/" in path else ""
    if filename and filename.lower().endswith(".pdf"):
        return filename
    return "invoice.pdf"


def _build_product_context(
    *,
    product_name: str,
    display_name: str,
    support_email: str,
    vendor: dict | None,
) -> dict:
    """Build the product template context from the product's vendor JSON.

    Mirrors the shape produced by ``services/web/server`` so the shared email
    templates render identically when emails are sent from the payments service.
    """
    vendor = vendor or {}
    ui = vendor.get("ui") or {}
    return {
        "product_name": product_name,
        "display_name": display_name,
        "support_email": support_email,
        "homepage_url": vendor.get("url"),
        "ui": {
            "logo_url": ui.get("logo_url"),
            "strong_color": ui.get("strong_color"),
        },
        "footer": {
            "social_links": [
                {"name": name, "url": url}
                for name, url in vendor.get("footer_social_links", []) or []
            ],
            "share_links": [
                {"name": name, "label": label, "url": url}
                for name, label, url in vendor.get("footer_share_links", []) or []
            ],
            "company_name": vendor.get("company_name", "") or "",
            "company_address": vendor.get("company_address", "") or "",
            "company_links": [
                {"name": name, "url": url}
                for name, url in vendor.get("company_links", []) or []
            ],
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

        try:
            data = await self._users_repo.get_notification_data(user_id, payment.payment_id)

            attachments: list[EmailAttachment] = []
            if payment.invoice_pdf_url:
                pdf_content = await _download_invoice_pdf(str(payment.invoice_pdf_url))
                if pdf_content:
                    attachments.append(
                        EmailAttachment(
                            content=pdf_content,
                            filename=_extract_pdf_filename(str(payment.invoice_pdf_url)),
                        )
                    )

            full_name = " ".join(
                part for part in (data.first_name, data.last_name) if part
            ) or (data.user_name or "")

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

            context: dict = {
                "user": {
                    "first_name": data.first_name,
                    "last_name": data.last_name,
                    "user_name": data.user_name,
                    "email": data.email,
                },
                "payment": {
                    "price_dollars": f"{payment.price_dollars:.2f}",
                    "osparc_credits": f"{payment.osparc_credits:.2f}",
                    "invoice_url": f"{payment.invoice_url}",
                },
                "product": _build_product_context(
                    product_name=data.product_name,
                    display_name=data.display_name,
                    support_email=data.support_email,
                    vendor=data.vendor,
                ),
            }

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
