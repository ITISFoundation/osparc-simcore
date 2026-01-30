# pylint: disable=unused-argument

import logging
from email.headerregistry import Address
from email.message import EmailMessage as _EmailMessage

from celery import Task  # type: ignore[import-untyped]
from models_library.api_schemas_notifications.message import EmailNotificationMessage
from models_library.notifications import ChannelType
from notifications_library._email import (
    add_attachments,
    compose_email,
    create_email_session,
)
from servicelib.celery.models import TaskKey
from settings_library.email import SMTPSettings

_logger = logging.getLogger(__name__)


def _create_email_message(message: EmailNotificationMessage) -> _EmailMessage:
    return compose_email(
        from_=Address(**message.from_.model_dump()),
        to=[Address(**addr.model_dump()) for addr in message.to],
        subject=message.content.subject,
        content_text=message.content.body_text,
        content_html=message.content.body_html,
        reply_to=Address(**message.reply_to.model_dump()) if message.reply_to else None,
        bcc=[Address(**addr.model_dump()) for addr in message.bcc] if message.bcc else None,
    )


async def _send_email(msg: _EmailMessage) -> None:
    async with create_email_session(settings=SMTPSettings.create_from_envs()) as smtp:
        await smtp.send_message(msg)


async def send_email(
    task: Task,
    task_key: TaskKey,
    message: EmailNotificationMessage,
) -> None:
    assert task  # nosec
    assert task_key  # nosec

    assert message.channel == ChannelType.email  # nosec

    msg = _create_email_message(message)

    if message.attachments:
        add_attachments(msg, [(a.content, a.filename) for a in message.attachments])

    await _send_email(msg)
