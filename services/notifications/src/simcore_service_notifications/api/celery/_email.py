# pylint: disable=unused-argument

import asyncio
import logging
from email.headerregistry import Address

from celery import (  # type: ignore[import-untyped]
    Task,
    group,
    shared_task,
)
from models_library.notifications.celery import EmailContact as SingleEmailContact
from models_library.notifications.celery import EmailContent, EmailMessage, SingleEmailMessage
from notifications_library._email import (
    compose_email,
    create_email_session,
)
from servicelib.celery.models import TaskKey
from settings_library.email import SMTPSettings

_logger = logging.getLogger(__name__)

# Rate limit is 12 emails/minute = 1 email every 5 seconds
_SECONDS_BETWEEN_EMAILS = 5


def _to_address(address: SingleEmailContact) -> Address:
    return Address(display_name=address.name or "", addr_spec=address.email)


async def _send_single_email_async(msg: SingleEmailMessage) -> None:
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


@shared_task(name="send_single_email_message", pydantic=True, queue="notifications", rate_limit="12/m")
def send_single_email_message(msg: SingleEmailMessage) -> None:
    asyncio.run(_send_single_email_async(msg))


def send_email_message(
    task: Task,
    task_key: TaskKey,
    message: EmailMessage,
) -> None:
    assert task  # nosec
    assert task_key  # nosec

    single_msgs = [
        SingleEmailMessage(
            from_=SingleEmailContact(**message.from_.model_dump()),
            to=SingleEmailContact(**to.model_dump()),
            reply_to=SingleEmailContact(**message.reply_to.model_dump()) if message.reply_to else None,
            content=EmailContent(**message.content.model_dump()),
        )
        for to in message.to
    ]

    group_res = group(
        [
            send_single_email_message.s(single_msg.model_dump()).set(countdown=i * _SECONDS_BETWEEN_EMAILS)  # pyright: ignore[reportCallIssue]
            for i, single_msg in enumerate(single_msgs)
        ]
    ).apply_async()

    return group_res.id
