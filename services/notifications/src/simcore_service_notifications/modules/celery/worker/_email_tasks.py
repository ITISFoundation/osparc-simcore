# pylint: disable=unused-argument

import logging
from email.headerregistry import Address

from celery import Task  # type: ignore[import-untyped]
from jinja2 import StrictUndefined
from models_library.api_schemas_notifications import NotificationRequest
from models_library.api_schemas_notifications.channels import EmailChannel
from notifications_library._email import compose_email, create_email_session
from notifications_library._email_render import render_email_parts
from notifications_library._render import (
    create_render_environment_from_notifications_library,
)
from servicelib.celery.models import TaskKey
from settings_library.email import SMTPSettings

_logger = logging.getLogger(__name__)

EMAIL_CHANNEL_NAME = "email"


async def send_email_notification(
    task: Task,
    task_key: TaskKey,
    notification: NotificationRequest,
) -> None:
    _ = task
    _ = task_key

    #
    # NOTE: task can be used to provide progress
    #

    assert isinstance(notification.channel, EmailChannel)  # nosec

    _logger.info("Sending email notification to %s", notification.channel.to_addr)

    parts = render_email_parts(
        env=create_render_environment_from_notifications_library(
            undefined=StrictUndefined
        ),
        event_name=f"on_{notification.event.type}",
        **notification.event.model_dump(),
    )

    msg = compose_email(
        Address(**notification.channel.from_addr.model_dump()),
        Address(**notification.channel.to_addr.model_dump()),
        subject=parts.subject,
        content_text=parts.text_content,
        content_html=parts.html_content,
    )

    # if event_attachments:
    #     add_attachments(msg, event_attachments)

    async with create_email_session(settings=SMTPSettings.create_from_envs()) as smtp:
        await smtp.send_message(msg)
