from typing import Any

import pytest
from faker import Faker
from models_library.rpc.notifications import Notification
from models_library.rpc.notifications.channels import EmailAddress, EmailChannel
from models_library.rpc.notifications.events import (
    AccountApprovedEvent,
    AccountRequestedEvent,
    ProductData,
    ProductUIData,
    UserData,
)
from pydantic import HttpUrl
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    send_notification,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]


@pytest.mark.usefixtures(
    "mock_celery_worker",
    "mock_fastapi_app",
)
async def test_account_requested(
    notifications_rabbitmq_rpc_client: RabbitMQRPCClient,
    fake_ipinfo: dict[str, Any],
    faker: Faker,
):
    user_email = faker.email()

    await send_notification(
        notifications_rabbitmq_rpc_client,
        notification=Notification(
            event=AccountRequestedEvent(
                user=UserData(
                    username=faker.user_name(),
                    first_name=faker.first_name(),
                    last_name=faker.last_name(),
                    email=user_email,
                ),
                product=ProductData(
                    product_name=faker.company(),
                    display_name=faker.company(),
                    vendor_display_inline=faker.company_suffix(),
                    support_email=faker.email(),
                    homepage_url=faker.url(),
                    ui=ProductUIData(
                        project_alias=faker.word(),
                        logo_url=faker.image_url(),
                        strong_color=faker.color_name(),
                    ),
                ),
                host=HttpUrl(faker.url()),
                ipinfo=fake_ipinfo,
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


@pytest.mark.usefixtures(
    "mock_celery_worker",
    "mock_fastapi_app",
)
async def test_account_approved(
    notifications_rabbitmq_rpc_client: RabbitMQRPCClient,
    faker: Faker,
):
    user_email = faker.email()

    await send_notification(
        notifications_rabbitmq_rpc_client,
        notification=Notification(
            event=AccountApprovedEvent(
                user=UserData(
                    username=faker.user_name(),
                    first_name=faker.first_name(),
                    last_name=faker.last_name(),
                    email=user_email,
                ),
                product=ProductData(
                    product_name=faker.company(),
                    display_name=faker.company(),
                    vendor_display_inline=faker.company_suffix(),
                    support_email=faker.email(),
                    homepage_url=faker.url(),
                    ui=ProductUIData(
                        project_alias=faker.word(),
                        logo_url=faker.image_url(),
                        strong_color=faker.color(),
                    ),
                ),
                link=HttpUrl(faker.url()),
            ),
            channel=EmailChannel(
                from_addr=EmailAddress(
                    display_name=faker.name(), addr_spec=faker.email()
                ),
                to_addr=EmailAddress(
                    display_name=faker.name(),
                    addr_spec=user_email,
                ),
            ),
        ),
    )

    # TODO: wait for the email to be sent and check
