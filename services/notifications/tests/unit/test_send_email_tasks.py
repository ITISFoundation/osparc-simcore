import pytest
from faker import Faker
from models_library.rpc.notifications import Notification
from models_library.rpc.notifications.channels import EmailAddress, EmailChannel
from models_library.rpc.notifications.events._account_events import (
    AccountRequestedEvent,
)
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications.messages import (
    send_notification,
)

pytest_simcore_core_services_selection = [
    "postgres",
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
    user_email = faker.email()

    await send_notification(
        notifications_rabbitmq_rpc_client,
        notification=Notification(
            event=AccountRequestedEvent(
                first_name=faker.first_name(),
                last_name=faker.last_name(),
                email=user_email,
            ),
            channel=EmailChannel(
                from_addr=EmailAddress(addr_spec=faker.email()),
                to_addr=EmailAddress(
                    addr_spec=user_email,
                ),
            ),
        ),
    )

    # TODO: wait for the email to be sent and check
