# pylint: disable=unused-argument
from collections.abc import Awaitable, Callable

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.notifications.celery import EmailContact, EmailContent, EmailMessage
from models_library.notifications.rpc import SendMessageResponse
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications import send_message

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
