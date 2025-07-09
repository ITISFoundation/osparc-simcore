import pytest
from faker import Faker
from models_library.rpc.notifications.account import AccountRequestedEvent
from models_library.rpc.notifications.schemas import Notification
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications.messages import (
    send_notification,
)
from simcore_service_notifications.clients.celery import EmailChannel

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]


@pytest.mark.usefixtures(
    "mock_celery_app",
    "mock_celery_worker",
    "fastapi_app",
)
async def test_account_requested(
    notifications_rabbitmq_rpc_client: RabbitMQRPCClient,
    faker: Faker,
):
    email = faker.email()

    await send_notification(
        notifications_rabbitmq_rpc_client,
        notification=Notification(
            event=AccountRequestedEvent(
                first_name=faker.first_name(),
                last_name=faker.last_name(),
                email=email,
            ),
            channel=EmailChannel(to=email),
        ),
    )

    # TODO: wait for the email to be sent and check
