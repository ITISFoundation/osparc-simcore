# pylint: disable=unused-argument
from fastapi import FastAPI
from models_library.notifications import ChannelType
from models_library.notifications.rpc import SendMessageFromTemplateRequest, TemplateRef
from models_library.notifications.rpc.channels import EmailContact, EmailEnvelope
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    send_message_from_template,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]


async def test_send_message_from_templates(
    mock_fastapi_app: FastAPI,
    notifications_rpc_client: RabbitMQRPCClient,
    fake_product_data: dict[str, str],
):
    assert mock_fastapi_app

    ref = TemplateRef(channel=ChannelType.email, template_name="empty")
    template_context = {
        "subject": "Test Email",
        "body": "This is a test email.",
    } | {"product": fake_product_data}

    await send_message_from_template(
        notifications_rpc_client,
        request=SendMessageFromTemplateRequest(
            ref=ref,
            template_context=template_context,
            envelope=EmailEnvelope(
                from_=EmailContact(name="Test Sender", email="sender@example.com"),
                to=EmailContact(name="Test Recipient", email="recipient@example.com"),
            ),
        ),
    )
