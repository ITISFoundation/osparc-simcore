import logging
from decimal import Decimal

from models_library.notifications import Channel
from models_library.notifications.rpc import (
    EmailAddressing,
    EmailContact,
    TemplateRef,
)
from models_library.products import ProductName
from models_library.services_types import ServiceRunID
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    send_message_from_template,
)

_logger = logging.getLogger(__name__)

_CREDIT_REIMBURSEMENT_TEMPLATE = "credit_reimbursement"


async def notify_user_of_credit_reimbursement(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_email: str,
    service_run_id: ServiceRunID,
    reimbursed_credits: Decimal,
) -> None:
    addressing = EmailAddressing(
        **{
            "from": EmailContact(
                name=f"{product_name} support",
                email=f"support@{product_name}.io",
            ),
        },
        to=[EmailContact(name=user_email, email=user_email)],
    )

    context: dict = {
        "service_run_id": service_run_id,
        "reimbursed_credits": f"{reimbursed_credits}",
        "product": {
            "display_name": product_name,
            "support_email": f"support@{product_name}.io",
        },
    }

    await send_message_from_template(
        rabbitmq_rpc_client,
        addressing=addressing,
        template_ref=TemplateRef(
            channel=Channel.email,
            template_name=_CREDIT_REIMBURSEMENT_TEMPLATE,
        ),
        context=context,
    )

    _logger.info(
        "Sent credit reimbursement notification to %s for service_run_id %s",
        user_email,
        service_run_id,
    )
