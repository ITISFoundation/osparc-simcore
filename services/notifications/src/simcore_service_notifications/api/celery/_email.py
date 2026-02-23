# pylint: disable=unused-argument

import logging
from email.headerregistry import Address

from celery import (  # type: ignore[import-untyped]
    Task,
)
from models_library.notifications.celery import EmailContact, EmailContent, EmailMessage
from notifications_library._email import (
    compose_email,
    create_email_session,
)
from servicelib.celery.models import TaskKey
from settings_library.email import SMTPSettings

_logger = logging.getLogger(__name__)

# Rate limit is 12 emails/minute = 1 email every 5 seconds
_SECONDS_BETWEEN_EMAILS = 5


def _to_address(address: EmailContact) -> Address:
    return Address(display_name=address.name or "", addr_spec=address.email)


async def _send_single_email_async(msg: EmailMessage) -> None:
    _logger.info("🚨 Sending email to %s", msg.to.email)
    async with create_email_session(settings=SMTPSettings.create_from_envs()) as smtp:
        await smtp.send_message(
            compose_email(
                from_=_to_address(msg.from_),
                to=_to_address(msg.to),
                subject=msg.content.subject,
                content_text=msg.content.body_text,
                content_html=msg.content.body_html,
                reply_to=_to_address(msg.reply_to) if msg.reply_to else None,
            )
        )


async def send_email_message(
    task: Task,
    task_key: TaskKey,
    message: EmailMessage,
) -> None:
    assert task  # nosec
    assert task_key  # nosec

    await _send_single_email_async(
        EmailMessage(
            from_=EmailContact(**message.from_.model_dump()),
            to=EmailContact(**message.to.model_dump()),
            reply_to=EmailContact(**message.reply_to.model_dump()) if message.reply_to else None,
            content=EmailContent(**message.content.model_dump()),
        )
    )
