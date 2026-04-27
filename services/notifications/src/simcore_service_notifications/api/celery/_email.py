# pylint: disable=unused-argument

import logging
from email.headerregistry import Address
from typing import Any

from celery import (  # type: ignore[import-untyped]
    Task,
)
from models_library.notifications.celery import EmailContact, EmailContent, EmailMessage
from notifications_library._email import (
    add_attachments,
    compose_email,
    create_email_session,
)
from servicelib.logging_utils import log_context
from settings_library.email import SMTPSettings

_logger = logging.getLogger(__name__)


def _to_address(address: EmailContact) -> Address:
    return Address(display_name=address.name or "", addr_spec=address.email)


async def send_email_message(
    task: Task,
    message: EmailMessage,
    **_kwargs: Any,
) -> None:
    assert task  # nosec
    assert task.request.id  # nosec

    msg = EmailMessage(
        from_=EmailContact(**message.from_.model_dump()),
        to=EmailContact(**message.to.model_dump()),
        bcc=EmailContact(**message.bcc.model_dump()) if message.bcc else None,
        reply_to=EmailContact(**message.reply_to.model_dump()) if message.reply_to else None,
        content=EmailContent(**message.content.model_dump()),
        attachments=message.attachments,
    )

    with log_context(_logger, logging.INFO, "Send email to %s", msg.to.email):
        settings = SMTPSettings.create_from_envs()

        async with create_email_session(settings=settings) as smtp:
            email_msg = compose_email(
                from_=_to_address(msg.from_),
                to=_to_address(msg.to),
                subject=msg.content.subject,
                content_text=msg.content.body_text,
                content_html=msg.content.body_html,
                reply_to=_to_address(msg.reply_to) if msg.reply_to else None,
                bcc=[_to_address(msg.bcc)] if msg.bcc else None,
                extra_headers=settings.SMTP_EXTRA_HEADERS,
            )
            if msg.attachments:
                add_attachments(
                    email_msg,
                    [(a.content, a.filename) for a in msg.attachments],
                )
            await smtp.send_message(email_msg)
