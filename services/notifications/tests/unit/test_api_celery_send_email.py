from unittest.mock import AsyncMock

import pytest
from faker import Faker
from models_library.celery.notifications import EmailContact, EmailContent, EmailMessage
from servicelib.celery.models import ExecutionMetadata, OwnerMetadata, TaskState
from servicelib.celery.task_manager import TaskManager
from simcore_service_notifications.api.celery.tasks import (
    send_email,
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
async def test_send_mail(
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
            name=send_email.__name__,
        ),
        owner_metadata=owner_metadata,
        message=EmailMessage(
            from_=EmailContact(email=faker.email()),
            to=[EmailContact(email=user_email)],
            content=EmailContent(
                subject="Test Email",
                body_text="This is a test email sent from the notifications service.",
                body_html="<p>This is a test email sent from the notifications service.</p>",
            ),
        ).model_dump(),
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_task_status(owner_metadata, task_uuid)
            assert status.task_state == TaskState.SUCCESS

    # if mocked, check email was sent
    if smtp_mock_or_none:
        smtp_mock_or_none.send_message.assert_called_once()
