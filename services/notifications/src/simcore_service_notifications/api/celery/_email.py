# pylint: disable=unused-argument

import logging
from email.headerregistry import Address
from email.message import EmailMessage

from celery import Task  # type: ignore[import-untyped]
from notifications_library._email import (
    add_attachments,
    compose_email,
    create_email_session,
)
from servicelib.celery.models import TaskKey
from settings_library.email import SMTPSettings

from simcore_service_notifications.models.channel import ChannelType

from ...channels.email.email_message import EmailNotificationMessage

_logger = logging.getLogger(__name__)


def _create_email_message(message: EmailNotificationMessage) -> EmailMessage:
    return compose_email(
        Address(),
        Address(),
        subject=message.content.subject,
        content_text=message.content.body_text,
        content_html=message.content.body_html,
        reply_to=None,
    )


async def _send_email(msg: EmailMessage) -> None:
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
