# pylint: disable=unused-argument

import logging
from email.headerregistry import Address
from email.message import EmailMessage

from celery import Task  # type: ignore[import-untyped]
from jinja2 import StrictUndefined
from models_library.api_schemas_notifications import NotificationRequest
from models_library.api_schemas_notifications.channels import EmailChannel
from notifications_library._email import (
    add_attachments,
    compose_email,
    create_email_session,
)
from notifications_library._email_render import render_email_parts
from notifications_library._render import (
    create_render_environment_from_notifications_library,
)
from servicelib.celery.models import TaskKey
from settings_library.email import SMTPSettings

_logger = logging.getLogger(__name__)


def _create_email_message(notification: NotificationRequest) -> EmailMessage:
    parts = render_email_parts(
        env=create_render_environment_from_notifications_library(undefined=StrictUndefined),
        event_name=f"on_{notification.event.type}",
        **notification.event.model_dump(),
    )

    return compose_email(
        Address(**notification.channel.from_.model_dump()),
        Address(**notification.channel.to.model_dump()),
        subject=parts.subject,
        content_text=parts.text_content,
        content_html=parts.html_content,
        reply_to=(Address(**notification.channel.reply_to.model_dump()) if notification.channel.reply_to else None),
    )


async def _send_email(msg: EmailMessage) -> None:
    async with create_email_session(settings=SMTPSettings.create_from_envs()) as smtp:
        await smtp.send_message(msg)


async def send_email_notification(
    task: Task,
    task_key: TaskKey,
    notification: NotificationRequest,
) -> None:
    assert task  # nosec
    assert task_key  # nosec

    assert isinstance(notification.channel, EmailChannel)  # nosec

    msg = _create_email_message(notification)

    if notification.channel.attachments:
        add_attachments(msg, [(a.content, a.filename) for a in notification.channel.attachments])

    await _send_email(msg)
