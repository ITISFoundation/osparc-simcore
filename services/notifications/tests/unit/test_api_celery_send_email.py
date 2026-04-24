from email.message import EmailMessage as StdEmailMessage
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from models_library.celery import TaskExecutionMetadata, TaskState, TaskStatus
from models_library.notifications.celery import (
    EmailAttachment,
    EmailContact,
    EmailContent,
    EmailMessage,
)
from servicelib.celery.task_manager import TaskManager
from simcore_service_notifications.api.celery.tasks import (
    send_email_message,
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
    user_email = faker.email()
    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(
            name=send_email_message.__name__,
        ),
        owner="test_service",
        message=EmailMessage(
            from_=EmailContact(email=faker.email()),
            to=EmailContact(email=user_email),
            content=EmailContent(
                subject="Test Email",
                body_text="This is a test email sent from the notifications service.",
                body_html="<p>This is a test email sent from the notifications service.</p>",
            ),
        ).model_dump(),
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_status(task_uuid)
            assert isinstance(status, TaskStatus)  # nosec
            assert status.task_state == TaskState.SUCCESS

    # if mocked, check email was sent
    if smtp_mock_or_none:
        smtp_mock_or_none.send_message.assert_called_once()


@pytest.mark.usefixtures(
    "mock_celery_worker",
)
async def test_send_mail_with_bcc_and_attachment(
    task_manager: TaskManager,
    smtp_mock_or_none: AsyncMock | None,
    faker: Faker,
):
    bcc_contact = EmailContact(name=faker.name(), email=faker.email())
    attachment_content = faker.binary(length=128)
    attachment_filename = "invoice.pdf"

    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(name=send_email_message.__name__),
        owner="test_service",
        message=EmailMessage(
            from_=EmailContact(email=faker.email()),
            to=EmailContact(email=faker.email()),
            bcc=bcc_contact,
            content=EmailContent(
                subject="Test with BCC and attachment",
                body_text="Plain text body",
                body_html="<p>HTML body</p>",
            ),
            attachments=[
                EmailAttachment(content=attachment_content, filename=attachment_filename),
            ],
        ).model_dump(),
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_status(task_uuid)
            assert isinstance(status, TaskStatus)  # nosec
            assert status.task_state == TaskState.SUCCESS

    if smtp_mock_or_none:
        smtp_mock_or_none.send_message.assert_called_once()
        sent_msg: StdEmailMessage = smtp_mock_or_none.send_message.call_args[0][0]

        # bcc is reflected
        assert bcc_contact.email in sent_msg["Bcc"]

        # attachment is present
        attachments = list(sent_msg.iter_attachments())
        assert len(attachments) == 1
        assert attachments[0].get_filename() == attachment_filename
        assert attachments[0].get_content() == attachment_content
