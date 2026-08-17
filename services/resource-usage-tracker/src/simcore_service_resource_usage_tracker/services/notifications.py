import logging
from decimal import Decimal

from common_library.gettext_support import DEFAULT_LOCALE
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from models_library.notifications import Channel
from models_library.notifications.rpc import (
    EmailAddressing,
    EmailContact,
    TemplateRef,
)
from models_library.products import ProductName
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    send_message_from_template,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from .modules.db import users_db

_logger = logging.getLogger(__name__)

_CREDIT_REIMBURSEMENT_TEMPLATE = "credit_reimbursement"


async def notify_user_of_credit_reimbursement(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    db_engine: AsyncEngine,
    *,
    product_name: ProductName,
    user_id: UserID,
    user_email: str,
    service_run_id: ServiceRunID,
    reimbursed_credits: Decimal,
) -> None:
    try:
        addressing = EmailAddressing(
            to=[EmailContact(name=user_email, email=user_email)],
        )

        context: dict = {
            "service_run_id": service_run_id,
            "reimbursed_credits": f"{reimbursed_credits}",
        }

        language = await users_db.get_user_language(db_engine, user_id=user_id)

        await send_message_from_template(
            rabbitmq_rpc_client,
            product_name=product_name,
            addressing=addressing,
            template_ref=TemplateRef(
                channel=Channel.email,
                template_name=_CREDIT_REIMBURSEMENT_TEMPLATE,
            ),
            context=context,
            locale=language or DEFAULT_LOCALE,
        )
    except Exception as exc:  # pylint: disable=broad-except
        _logger.exception(
            **create_troubleshooting_log_kwargs(
                "Failed to send credit reimbursement notification",
                error=exc,
                error_context={
                    "user_email": user_email,
                    "service_run_id": service_run_id,
                    "template_name": _CREDIT_REIMBURSEMENT_TEMPLATE,
                    "product_name": product_name,
                },
                tip="Check that the notifications service is running and the email template exists.",
            )
        )
        return

    _logger.info(
        "Sent credit reimbursement notification to %s for service_run_id %s",
        user_email,
        service_run_id,
    )
