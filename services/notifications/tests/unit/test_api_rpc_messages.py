# pylint: disable=unused-argument
from typing import Any

from fastapi import FastAPI
from jinja2 import Environment
from models_library.notifications import ChannelType
from models_library.notifications.rpc import SendMessageFromTemplateRequest, TemplateRef
from models_library.notifications.rpc.channels import EmailContact, EmailEnvelope
from pytest_mock import MockerFixture
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
    mock_jinja_env_in_dependencies: Environment,
    notifications_rpc_client: RabbitMQRPCClient,
    fake_product_data: dict[str, str],
    mocker: MockerFixture,
):
    assert mock_fastapi_app

    # Mock the submit_send_message_task function
    mock_submit = mocker.patch(
        "simcore_service_notifications.api.rpc._messages.submit_send_message_task",
        return_value=("fake-task-uuid", "send_email_message"),
    )

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

    # Assert that submit_send_message_task was called
    mock_submit.assert_called_once()

    # Get the call arguments
    call_kwargs = mock_submit.call_args.kwargs
    assert call_kwargs is not None

    # Verify owner_metadata is passed
    assert "owner_metadata" in call_kwargs
    assert "channel" in call_kwargs
    assert call_kwargs["channel"] == ChannelType.email

    # Verify message structure
    message: dict[str, Any] = call_kwargs["message"]
    assert "envelope" in message
    assert "content" in message

    # Verify envelope
    envelope = message["envelope"]
    assert envelope["from_"]["email"] == "sender@example.com"
    assert envelope["from_"]["name"] == "Test Sender"
    assert envelope["to"]["email"] == "recipient@example.com"
    assert envelope["to"]["name"] == "Test Recipient"

    # Verify content was rendered from template
    content = message["content"]
    assert content["subject"] == "Test Email"
    assert content["body_html"] == "<p>This is a test email.</p>"
    assert content["body_text"] == "This is a test email."
