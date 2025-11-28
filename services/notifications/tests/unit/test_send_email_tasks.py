from typing import Any
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from models_library.api_schemas_notifications import NotificationRequest
from models_library.api_schemas_notifications.channels import EmailAddress, EmailChannel
from models_library.api_schemas_notifications.events import (
    AccountApprovedEvent,
    AccountRejectedEvent,
    AccountRequestedEvent,
    ProductData,
    ProductUIData,
    UserData,
)
from pydantic import HttpUrl
from servicelib.celery.models import ExecutionMetadata, OwnerMetadata, TaskState
from servicelib.celery.task_manager import TaskManager
from simcore_service_notifications.modules.celery.worker.tasks import (
    send_email_notification,
)
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]

_TENACITY_RETRY_PARAMS = {
    "reraise": True,
    "retry": retry_if_exception_type(AssertionError),
    "stop": stop_after_delay(30),
    "wait": wait_fixed(0.1),
}


@pytest.mark.usefixtures(
    "mock_celery_worker",
)
async def test_account_requested(
    task_manager: TaskManager,
    fake_ipinfo: dict[str, Any],
    smtp_mock_or_none: AsyncMock | None,
    faker: Faker,
):
    owner_metadata = OwnerMetadata(
        owner="test_service",
    )

    user_email = faker.email()
    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=send_email_notification.__name__,
        ),
        owner_metadata=owner_metadata,
        notification=NotificationRequest(
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
                host=faker.hostname(),
                ipinfo=fake_ipinfo,
            ),
            channel=EmailChannel(
                from_=EmailAddress(addr_spec=faker.email()),
                to=EmailAddress(
                    addr_spec=user_email,
                ),
            ),
        ).model_dump(mode="json"),
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_task_status(owner_metadata, task_uuid)
            assert status.task_state == TaskState.SUCCESS

    # if mocked, check email was sent
    if smtp_mock_or_none:
        smtp_mock_or_none.send_message.assert_called_once()


@pytest.mark.usefixtures(
    "mock_celery_worker",
)
async def test_account_approved(
    task_manager: TaskManager,
    smtp_mock_or_none: AsyncMock | None,
    faker: Faker,
):
    owner_metadata = OwnerMetadata(
        owner="test_service",
    )

    user_email = faker.email()
    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=send_email_notification.__name__,
        ),
        owner_metadata=owner_metadata,
        notification=NotificationRequest(
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
                        strong_color=faker.color_name(),
                    ),
                ),
                link=HttpUrl(faker.url()),
            ),
            channel=EmailChannel(
                from_=EmailAddress(addr_spec=faker.email()),
                to=EmailAddress(
                    addr_spec=user_email,
                ),
            ),
        ).model_dump(mode="json"),
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_task_status(owner_metadata, task_uuid)
            assert status.task_state == TaskState.SUCCESS

    # if mocked, check email was sent
    if smtp_mock_or_none:
        smtp_mock_or_none.send_message.assert_called_once()


@pytest.mark.usefixtures(
    "mock_celery_worker",
)
async def test_account_rejected(
    task_manager: TaskManager,
    smtp_mock_or_none: AsyncMock | None,
    faker: Faker,
):
    owner_metadata = OwnerMetadata(
        owner="test_service",
    )

    user_email = faker.email()
    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=send_email_notification.__name__,
        ),
        owner_metadata=owner_metadata,
        notification=NotificationRequest(
            event=AccountRejectedEvent(
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
                reason=faker.sentence(),
            ),
            channel=EmailChannel(
                from_=EmailAddress(addr_spec=faker.email()),
                to=EmailAddress(
                    addr_spec=user_email,
                ),
            ),
        ).model_dump(mode="json"),
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_task_status(owner_metadata, task_uuid)
            assert status.task_state == TaskState.SUCCESS

    # if mocked, check email was sent
    if smtp_mock_or_none:
        smtp_mock_or_none.send_message.assert_called_once()
