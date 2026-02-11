# pylint: disable=unused-argument

import asyncio
import logging
from email.headerregistry import Address
from typing import Annotated

from celery import Task, group, shared_task  # type: ignore[import-untyped]
from models_library.api_schemas_notifications.message import EmailNotificationMessage
from notifications_library._email import (
    compose_email,
    create_email_session,
)
from pydantic import BaseModel, ConfigDict, Field
from servicelib.celery.models import TaskKey
from settings_library.email import SMTPSettings

from ...models.content import EmailNotificationContent
from ...models.message import EmailAddress

_logger = logging.getLogger(__name__)


class SingleEmailNotificationMessage(BaseModel):
    from_: Annotated[EmailAddress, Field(alias="from")]
    to: EmailAddress
    reply_to: EmailAddress | None = None

    # Content fields
    content: EmailNotificationContent

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
    )


def _to_address(address: EmailAddress) -> Address:
    return Address(display_name=address.name, addr_spec=address.email)


async def _send_single_email_async(msg: SingleEmailNotificationMessage) -> None:
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


@shared_task(name="send_single_email", pydantic=True, queue="notifications", rate_limit="12/m")
def send_single_email(msg: SingleEmailNotificationMessage) -> None:
    asyncio.run(_send_single_email_async(msg))


def send_email(
    task: Task,
    task_key: TaskKey,
    message: EmailNotificationMessage,
) -> None:
    assert task  # nosec
    assert task_key  # nosec

    single_msgs = [
        SingleEmailNotificationMessage(
            from_=EmailAddress(**message.from_.model_dump()),
            to=EmailAddress(**to.model_dump()),
            reply_to=EmailAddress(**message.reply_to.model_dump()) if message.reply_to else None,
            content=EmailNotificationContent(**message.content.model_dump()),
        )
        for to in message.to
    ]

    group([send_single_email.s(single_msg.model_dump()) for single_msg in single_msgs]).apply_async()  # type: ignore
