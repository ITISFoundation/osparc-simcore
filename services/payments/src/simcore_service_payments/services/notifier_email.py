import logging

from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from models_library.api_schemas_webserver.wallets import PaymentMethodTransaction
from models_library.notifications import Channel
from models_library.notifications.rpc import (
    EmailAddressing,
    EmailContact,
    TemplateRef,
)
from models_library.users import UserID
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    send_message_from_template,
)

from ..db.payment_users_repo import PaymentsUsersRepo
from ..models.db import PaymentsTransactionsDB
from .notifier_abc import NotificationProvider

_logger = logging.getLogger(__name__)

_PAID_TEMPLATE_NAME = "paid"


class EmailProvider(NotificationProvider):
    def __init__(
        self,
        rabbitmq_rpc_client: RabbitMQRPCClient,
        users_repo: PaymentsUsersRepo,
    ):
        self._rabbitmq_rpc_client = rabbitmq_rpc_client
        self._users_repo = users_repo

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

            addressing = EmailAddressing(
                from_=EmailContact(
                    name=f"{data.display_name} support",
                    email=data.support_email,
                ),
                to=[
                    EmailContact(
                        name=f"{data.first_name} {data.last_name}",
                        email=data.email,
                    )
                ],
            )

            context: dict = {
                "user": {
                    "first_name": data.first_name,
                    "last_name": data.last_name,
                    "email": data.email,
                },
                "payment": {
                    "price_dollars": f"{payment.price_dollars:.2f}",
                    "osparc_credits": f"{payment.osparc_credits:.2f}",
                    "invoice_url": f"{payment.invoice_url}",
                },
                "product": {
                    "display_name": data.display_name,
                    "support_email": data.support_email,
                },
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
