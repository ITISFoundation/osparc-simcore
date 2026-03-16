# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.notifications import ChannelType, TemplateRef
from models_library.notifications.celery import EmailContact, EmailContent, EmailMessage
from models_library.notifications.errors import (
    NotificationsTemplateContextValidationError,
    NotificationsTemplateNotFoundError,
)
from models_library.notifications.rpc import (
    EmailContact as RpcEmailContact,
)
from models_library.notifications.rpc import (
    EmailEnvelope,
    SendMessageResponse,
)
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
            "from": EmailContact(name="Sender", email=faker.email()),
            "to": EmailContact(name="Recipient", email=faker.email()),
            "content": EmailContent(
                subject="Test Subject",
                body_text="Test body text",
                body_html="<p>Test body html</p>",
            ),
        }
    ).model_dump(by_alias=True)


@pytest.fixture
def multi_recipient_email_message(faker: Faker) -> dict:
    return {
        **EmailMessage(
            **{
                "from": EmailContact(name="Sender", email=faker.email()),
                "to": EmailContact(name="First", email=faker.email()),
                "content": EmailContent(
                    subject="Test Subject",
                    body_text="Test body text",
                ),
            }
        ).model_dump(by_alias=True),
        "to": [
            EmailContact(name="First", email=faker.email()).model_dump(),
            EmailContact(name="Second", email=faker.email()).model_dump(),
        ],
    }


@pytest.fixture
def email_envelope_single_recipient(faker: Faker) -> EmailEnvelope:
    return EmailEnvelope(
        **{
            "from": RpcEmailContact(name="Sender", email=faker.email()),
            "to": [RpcEmailContact(name="Recipient", email=faker.email())],
        }
    )


@pytest.fixture
def email_envelope_multiple_recipients(faker: Faker) -> EmailEnvelope:
    return EmailEnvelope(
        **{
            "from": RpcEmailContact(name="Sender", email=faker.email()),
            "to": [
                RpcEmailContact(name="First Recipient", email=faker.email()),
                RpcEmailContact(name="Second Recipient", email=faker.email()),
            ],
            "reply_to": RpcEmailContact(name="Reply To", email=faker.email()),
        }
    )


async def test_send_message_single_recipient(
    mock_fastapi_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    single_recipient_email_message: dict,
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    response = await send_message(
        rpc_client,
        message=single_recipient_email_message,
    )
    assert isinstance(response, SendMessageResponse)
    assert response.task_or_group_uuid
    assert response.task_name == "send_email_message"


async def test_send_message_multiple_recipients(
    mock_fastapi_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    multi_recipient_email_message: dict,
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    response = await send_message(
        rpc_client,
        message=multi_recipient_email_message,
    )
    assert isinstance(response, SendMessageResponse)
    assert response.task_or_group_uuid
    assert response.task_name == "send_email_message"


async def test_send_message_from_template_with_empty_template(
    mock_fastapi_app: FastAPI,
    fake_product_data: dict[str, Any],
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    email_envelope_single_recipient: EmailEnvelope,
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    ref = TemplateRef(channel=ChannelType.email, template_name="empty")
    context = {
        "subject": "Test Email",
        "body": "This is a test email.",
        "product": fake_product_data,
    }

    response = await send_message_from_template(
        rpc_client,
        template_ref=ref,
        context=context,
        envelope=email_envelope_single_recipient,
    )
    assert isinstance(response, SendMessageResponse)
    assert response.task_or_group_uuid
    assert response.task_name == "send_email_message"


async def test_send_message_from_template_with_multiple_recipients(
    mock_fastapi_app: FastAPI,
    fake_product_data: dict[str, Any],
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    email_envelope_multiple_recipients: EmailEnvelope,
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    ref = TemplateRef(channel=ChannelType.email, template_name="empty")
    context = {
        "subject": "Multi-recipient Test",
        "body": "Sent to multiple recipients.",
        "product": fake_product_data,
    }

    response = await send_message_from_template(
        rpc_client,
        template_ref=ref,
        context=context,
        envelope=email_envelope_multiple_recipients,
    )
    assert isinstance(response, SendMessageResponse)
    assert response.task_or_group_uuid
    assert response.task_name == "send_email_message"


async def test_send_message_from_template_not_found(
    mock_fastapi_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    email_envelope_single_recipient: EmailEnvelope,
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    ref = TemplateRef(channel=ChannelType.email, template_name="non_existent_template")
    context = {}

    with pytest.raises(NotificationsTemplateNotFoundError):
        await send_message_from_template(
            rpc_client,
            template_ref=ref,
            context=context,
            envelope=email_envelope_single_recipient,
        )


async def test_send_message_from_template_invalid_context(
    mock_fastapi_app: FastAPI,
    fake_product_data: dict[str, Any],
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    email_envelope_single_recipient: EmailEnvelope,
):
    assert mock_fastapi_app

    rpc_client = await rabbitmq_rpc_client("notifications-test-client")

    ref = TemplateRef(channel=ChannelType.email, template_name="account_approved")
    # Missing required fields 'user' and 'link'
    context = {
        "invalid_key": "invalid_value",
        "product": fake_product_data,
    }

    with pytest.raises(NotificationsTemplateContextValidationError):
        await send_message_from_template(
            rpc_client,
            template_ref=ref,
            context=context,
            envelope=email_envelope_single_recipient,
        )
