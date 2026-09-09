import logging
from dataclasses import dataclass
from typing import Any

from common_library.gettext_support import SupportedLocale
from models_library.celery import (
    GroupUUID,
    OwnerMetadata,
    TaskName,
    TaskUUID,
)
from models_library.notifications import Channel
from models_library.notifications.errors import (
    NotificationsTooManyRecipientsError,
    NotificationsUnsupportedChannelError,
)
from models_library.notifications.rpc import (
    Addressing,
    EmailMessage,
    Message,
    SmsMessage,
)
from models_library.products import ProductName
from servicelib.celery.async_jobs.notifications import (
    submit_send_message_task,
    submit_send_messages_task,
)
from servicelib.celery.task_manager import TaskManager

from .._meta import APP_NAME
from ..core.settings import ApplicationSettings
from ..models.product import Product
from ..models.template import TemplateRef
from ..repositories.product import ProductRepository
from ._template import TemplateService
from .channel_handlers import for_channel

_logger = logging.getLogger(__name__)

_OWNER_METADATA = OwnerMetadata(owner=APP_NAME)


def _prepare_celery_messages(
    message: Message,
    *,
    product: Product,
    settings: ApplicationSettings,
) -> list[dict[str, Any]]:
    """Dispatches to channel handler to fan out into per-recipient celery payloads.

    Raises:
        NotificationsUnsupportedChannelError: If the channel is not supported.
    """
    handler = for_channel(message.channel)
    return handler.prepare_messages(
        message,
        product=product,
        settings=settings,
    )


def _get_task_description(message: Message) -> str | None:
    if isinstance(message, EmailMessage):
        return message.content.subject
    if isinstance(message, SmsMessage):
        return message.content.body
    return None


def _get_max_recipients(channel: Channel, settings: ApplicationSettings) -> int | None:
    return settings.NOTIFICATIONS_EMAIL_MAX_RECIPIENTS_PER_MESSAGE if channel == Channel.email else None


def _build_message(channel: Channel, addressing: Addressing, content: dict[str, Any]) -> Message:
    """Builds the channel-specific message, revalidating addressing against that channel's shape.

    Raises:
        NotificationsUnsupportedChannelError: If the channel is not supported.
    """
    payload = {"addressing": addressing.model_dump(), "content": content}
    match channel:
        case Channel.email:
            return EmailMessage.model_validate(payload)
        case Channel.sms:
            return SmsMessage.model_validate(payload)
        case _:
            raise NotificationsUnsupportedChannelError(channel=channel)


@dataclass(frozen=True)
class MessageService:
    template_service: TemplateService
    product_repository: ProductRepository
    task_manager: TaskManager
    settings: ApplicationSettings

    async def send_message(
        self,
        *,
        product_name: ProductName,
        message: Message,
        owner_metadata: OwnerMetadata | None = None,
    ) -> tuple[TaskUUID | GroupUUID, TaskName]:
        resolved_owner = owner_metadata or _OWNER_METADATA

        product = await self.product_repository.get_product(product_name)
        messages = _prepare_celery_messages(
            message,
            product=product,
            settings=self.settings,
        )

        num_recipients = len(messages)
        description = _get_task_description(message)

        if num_recipients == 1:
            task_uuid, task_name = await submit_send_message_task(
                self.task_manager,
                owner_metadata=resolved_owner,
                product_name=product_name,
                message=messages[0],
                description=description,
            )
            return task_uuid, task_name

        max_recipients = _get_max_recipients(message.channel, self.settings)
        if max_recipients and num_recipients > max_recipients:
            raise NotificationsTooManyRecipientsError(
                num_recipients=num_recipients,
                max_recipients=max_recipients,
            )

        group_uuid, _, task_name = await submit_send_messages_task(
            self.task_manager,
            owner_metadata=resolved_owner,
            product_name=product_name,
            messages=messages,
            description=description,
        )
        return group_uuid, task_name

    async def send_message_from_template(
        self,
        *,
        product_name: ProductName,
        addressing: Addressing,
        ref: TemplateRef,
        context: dict[str, Any],
        locale: SupportedLocale,
        owner_metadata: OwnerMetadata | None = None,
    ) -> tuple[TaskUUID | GroupUUID, TaskName]:
        preview = await self.template_service.preview_template(
            product_name=product_name, ref=ref, context=context, locale=locale
        )

        message = _build_message(
            ref.channel,
            addressing,
            preview.message_content.model_dump(),
        )
        return await self.send_message(
            product_name=product_name,
            message=message,
            owner_metadata=owner_metadata,
        )
