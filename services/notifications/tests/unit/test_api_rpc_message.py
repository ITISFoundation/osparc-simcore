# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
from typing import Any

import pytest
from faker import Faker
from models_library.notifications import ChannelType, EmailMessage, TemplateRef
from models_library.notifications.errors import (
    NotificationsTemplateContextValidationError,
    NotificationsTemplateNotFoundError,
)
from models_library.notifications.rpc import SendMessageResponse
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    send_message,
    send_message_from_template,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]


@pytest.fixture
def single_recipient_email_message(faker: Faker) -> dict:
    return EmailMessage(
        **{
            "from": {"name": "Sender", "email": faker.email()},
            "to": [{"name": "Recipient", "email": faker.email()}],
            "content": {
                "subject": "Test Subject",
                "body_text": "Test body text",
                "body_html": "<p>Test body html</p>",
            },
        }
    ).model_dump(by_alias=True)


@pytest.fixture
def multi_recipient_email_message(faker: Faker) -> dict:
    return EmailMessage(
        **{
            "from": {"name": "Sender", "email": faker.email()},
            "to": [
                {"name": "First", "email": faker.email()},
                {"name": "Second", "email": faker.email()},
            ],
            "content": {
                "subject": "Test Subject",
                "body_text": "Test body text",
            },
        }
    ).model_dump(by_alias=True)


@pytest.fixture
def email_envelope_single_recipient(faker: Faker) -> dict[str, Any]:
    return {
        "from": {"name": "Sender", "email": faker.email()},
        "to": [{"name": "Recipient", "email": faker.email()}],
    }


@pytest.fixture
def email_envelope_multiple_recipients(faker: Faker) -> dict[str, Any]:
    return {
        "from": {"name": "Sender", "email": faker.email()},
        "to": [
            {"name": "First Recipient", "email": faker.email()},
            {"name": "Second Recipient", "email": faker.email()},
        ],
    }


async def test_send_message_single_recipient(
    rpc_client: RabbitMQRPCClient,
    single_recipient_email_message: dict,
):
    response = await send_message(
        rpc_client,
        message=single_recipient_email_message,
    )
    assert isinstance(response, SendMessageResponse)
    assert response.task_or_group_uuid
    assert response.task_name == "send_email_message"


async def test_send_message_multiple_recipients(
    rpc_client: RabbitMQRPCClient,
    multi_recipient_email_message: dict,
):
    response = await send_message(
        rpc_client,
        message=multi_recipient_email_message,
    )
    assert isinstance(response, SendMessageResponse)
    assert response.task_or_group_uuid
    assert response.task_name == "send_email_message"


async def test_send_message_from_template_with_empty_template(
    fake_product_data: dict[str, Any],
    rpc_client: RabbitMQRPCClient,
    email_envelope_single_recipient: dict[str, Any],
):
    ref = TemplateRef(channel=ChannelType.email, template_name="empty")
    context = {
        "subject": "Test Email",
        "body": "This is a test email.",
        "product": fake_product_data,
    }

    response = await send_message_from_template(
        rpc_client,
        envelope=email_envelope_single_recipient,
        template_ref=ref,
        context=context,
    )
    assert isinstance(response, SendMessageResponse)
    assert response.task_or_group_uuid
    assert response.task_name == "send_email_message"


async def test_send_message_from_template_with_multiple_recipients(
    fake_product_data: dict[str, Any],
    rpc_client: RabbitMQRPCClient,
    email_envelope_multiple_recipients: dict[str, Any],
):
    ref = TemplateRef(channel=ChannelType.email, template_name="empty")
    context = {
        "subject": "Multi-recipient Test",
        "body": "Sent to multiple recipients.",
        "product": fake_product_data,
    }

    response = await send_message_from_template(
        rpc_client,
        envelope=email_envelope_multiple_recipients,
        template_ref=ref,
        context=context,
    )
    assert isinstance(response, SendMessageResponse)
    assert response.task_or_group_uuid
    assert response.task_name == "send_email_message"


async def test_send_message_from_template_not_found(
    rpc_client: RabbitMQRPCClient,
    email_envelope_single_recipient: dict[str, Any],
):
    ref = TemplateRef(channel=ChannelType.email, template_name="non_existent_template")
    context = {}

    with pytest.raises(NotificationsTemplateNotFoundError):
        await send_message_from_template(
            rpc_client,
            envelope=email_envelope_single_recipient,
            template_ref=ref,
            context=context,
        )


async def test_send_message_from_template_invalid_context(
    fake_product_data: dict[str, Any],
    rpc_client: RabbitMQRPCClient,
    email_envelope_single_recipient: dict[str, Any],
):
    ref = TemplateRef(channel=ChannelType.email, template_name="account_approved")
    # Missing required fields 'user' and 'link'
    context = {
        "invalid_key": "invalid_value",
        "product": fake_product_data,
    }

    with pytest.raises(NotificationsTemplateContextValidationError):
        await send_message_from_template(
            rpc_client,
            envelope=email_envelope_single_recipient,
            template_ref=ref,
            context=context,
        )
