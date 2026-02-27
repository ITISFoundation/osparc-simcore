# pylint: disable=unused-argument

import logging
from email.headerregistry import Address

from celery import (  # type: ignore[import-untyped]
    Task,
)
from models_library.notifications.celery import EmailContact, EmailMessage
from notifications_library._email import (
    compose_email,
    create_email_session,
)
from servicelib.celery.models import TaskKey
from servicelib.logging_utils import log_context
from settings_library.email import SMTPSettings

_logger = logging.getLogger(__name__)


def _to_address(address: EmailContact) -> Address:
    return Address(display_name=address.name or "", addr_spec=address.email)


async def send_email_message(
    task: Task,
    task_key: TaskKey,
    message: EmailMessage,
) -> None:
    assert task  # nosec
    assert task_key  # nosec

    with log_context(_logger, logging.INFO, "Send email to %s", message.envelope.to.email):
        settings = SMTPSettings.create_from_envs()

        async with create_email_session(settings=settings) as smtp:
            await smtp.send_message(
                compose_email(
                    from_=_to_address(message.envelope.from_),
                    to=_to_address(message.envelope.to),
                    subject=message.content.subject,
                    content_text=message.content.body_text,
                    content_html=message.content.body_html,
                    reply_to=_to_address(message.envelope.reply_to) if message.envelope.reply_to else None,
                    extra_headers=settings.SMTP_EXTRA_HEADERS,
                )
            )
