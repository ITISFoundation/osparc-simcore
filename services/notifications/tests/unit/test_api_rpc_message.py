# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
from typing import Any

import pytest
from faker import Faker
from models_library.celery import OwnerMetadata
from models_library.notifications import Channel
from models_library.notifications.errors import (
    NotificationsTemplateContextValidationError,
    NotificationsTemplateNotFoundError,
)
from models_library.notifications.rpc import (
    EmailAddressing,
    EmailContact,
    EmailContent,
    EmailMessage,
    SendMessageResponse,
    TemplateRef,
)
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    send_message,
    send_message_from_template,
)
from simcore_service_notifications.services import _message as _message_module

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]


@pytest.fixture
def single_recipient_email_message(faker: Faker) -> EmailMessage:
    return EmailMessage(
        addressing=EmailAddressing(
            from_=EmailContact(name="Sender", email=faker.email()),
            to=[EmailContact(name="Recipient", email=faker.email())],
        ),
        content=EmailContent(
            subject="Test Subject",
            body_text="Test body text",
            body_html="<p>Test body html</p>",
        ),
    )


@pytest.fixture
def multi_recipient_email_message(faker: Faker) -> EmailMessage:
    return EmailMessage(
        addressing=EmailAddressing(
            from_=EmailContact(name="Sender", email=faker.email()),
            to=[
                EmailContact(name="First", email=faker.email()),
                EmailContact(name="Second", email=faker.email()),
            ],
        ),
        content=EmailContent(
            subject="Test Subject",
            body_text="Test body text",
            body_html="<p>Test body html</p>",
        ),
    )


@pytest.fixture
def email_addressing_single_recipient(faker: Faker) -> EmailAddressing:
    return EmailAddressing(
        **{
            "from": {"name": "Sender", "email": faker.email()},
            "to": [{"name": "Recipient", "email": faker.email()}],
        }
    )


@pytest.fixture
def email_addressing_multiple_recipients(faker: Faker) -> EmailAddressing:
    return EmailAddressing(
        **{
            "from": {"name": "Sender", "email": faker.email()},
            "to": [
                {"name": "First Recipient", "email": faker.email()},
                {"name": "Second Recipient", "email": faker.email()},
            ],
        }
    )


async def test_send_message_single_recipient(
    rpc_client: RabbitMQRPCClient,
    single_recipient_email_message: EmailMessage,
):
    response = await send_message(
        rpc_client,
        message=single_recipient_email_message,
    )
    assert isinstance(response, SendMessageResponse)
    assert response.task_or_group_uuid
    assert response.task_name == "send_email_message"


async def test_send_message_with_owner_metadata(
    rpc_client: RabbitMQRPCClient,
    single_recipient_email_message: EmailMessage,
    mocker: MockerFixture,
):
    owner_metadata = OwnerMetadata.model_validate(
        {
            "owner": "webserver",
            "user_id": 42,
            "product_name": "osparc",
        }
    )

    spy = mocker.patch(
        f"{_message_module.__name__}.submit_send_message_task",
        wraps=_message_module.submit_send_message_task,
    )

    response = await send_message(
        rpc_client,
        message=single_recipient_email_message,
        owner_metadata=owner_metadata,
    )
    assert isinstance(response, SendMessageResponse)
    assert response.task_or_group_uuid
    assert response.task_name == "send_email_message"

    spy.assert_awaited_once()
    call_kwargs = spy.call_args.kwargs
    assert call_kwargs["owner_metadata"] == owner_metadata
    assert call_kwargs["owner_metadata"].owner == "webserver"
    assert call_kwargs["owner_metadata"].model_dump()["user_id"] == 42
    assert call_kwargs["owner_metadata"].model_dump()["product_name"] == "osparc"


async def test_send_message_multiple_recipients(
    rpc_client: RabbitMQRPCClient,
    multi_recipient_email_message: EmailMessage,
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
    email_addressing_single_recipient: EmailAddressing,
):
    ref = TemplateRef(channel=Channel.email, template_name="empty")
    context = {
        "subject": "Test Email",
        "body": "This is a test email.",
        "product": fake_product_data,
    }

    response = await send_message_from_template(
        rpc_client,
        addressing=email_addressing_single_recipient,
        template_ref=ref,
        context=context,
    )
    assert isinstance(response, SendMessageResponse)
    assert response.task_or_group_uuid
    assert response.task_name == "send_email_message"


async def test_send_message_from_template_with_multiple_recipients(
    fake_product_data: dict[str, Any],
    rpc_client: RabbitMQRPCClient,
    email_addressing_multiple_recipients: EmailAddressing,
):
    ref = TemplateRef(channel=Channel.email, template_name="empty")
    context = {
        "subject": "Multi-recipient Test",
        "body": "Sent to multiple recipients.",
        "product": fake_product_data,
    }

    response = await send_message_from_template(
        rpc_client,
        addressing=email_addressing_multiple_recipients,
        template_ref=ref,
        context=context,
    )
    assert isinstance(response, SendMessageResponse)
    assert response.task_or_group_uuid
    assert response.task_name == "send_email_message"


async def test_send_message_from_template_not_found(
    rpc_client: RabbitMQRPCClient,
    email_addressing_single_recipient: EmailAddressing,
):
    ref = TemplateRef(channel=Channel.email, template_name="non_existent_template")
    context = {}

    with pytest.raises(NotificationsTemplateNotFoundError):
        await send_message_from_template(
            rpc_client,
            addressing=email_addressing_single_recipient,
            template_ref=ref,
            context=context,
        )


async def test_send_message_from_template_invalid_context(
    fake_product_data: dict[str, Any],
    rpc_client: RabbitMQRPCClient,
    email_addressing_single_recipient: EmailAddressing,
):
    ref = TemplateRef(channel=Channel.email, template_name="account_approved")
    # Missing required fields 'user' and 'link'
    context = {
        "invalid_key": "invalid_value",
        "product": fake_product_data,
    }

    with pytest.raises(NotificationsTemplateContextValidationError):
        await send_message_from_template(
            rpc_client,
            addressing=email_addressing_single_recipient,
            template_ref=ref,
            context=context,
        )
