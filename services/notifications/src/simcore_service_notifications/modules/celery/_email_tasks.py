# pylint: disable=unused-argument

import logging

from celery import Task
from models_library.rpc.notifications.schemas import EmailChannel, Notification
from servicelib.celery.models import TaskID

_logger = logging.getLogger(__name__)

EMAIL_CHANNEL_NAME = "email"


async def send_email_notification(
    task: Task,
    task_id: TaskID,
    notification: Notification,
) -> None:
    assert isinstance(notification.channel, EmailChannel)  # nosec

    _logger.info("Sending email notification to %s", notification.channel.to)

    # event_extra_data = event_extra_data | (asdict(sharer_data) if sharer_data else {})

    # parts = render_email_parts(
    #     env=create_render_environment_from_notifications_library(
    #         undefined=StrictUndefined
    #     ),
    #     event_name=event_name,
    #     user=user_data,
    #     product=product_data,
    #     # extras
    #     **event_extra_data,
    # )

    # from_ = get_support_address(product_data)
    # to = get_user_address(user_data)

    # assert from_.addr_spec == product_data.support_email
    # assert to.addr_spec == user_email

    # msg = compose_email(
    #     from_,
    #     to,
    #     subject=parts.subject,
    #     content_text=parts.text_content,
    #     content_html=parts.html_content,
    # )
    # if event_attachments:
    #     add_attachments(msg, event_attachments)

    # async with create_email_session(settings=SMTPSettings.create_from_envs()) as smtp:
    #     await smtp.send_message(msg)
