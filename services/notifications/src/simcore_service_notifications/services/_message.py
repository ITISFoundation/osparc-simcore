import logging
from dataclasses import dataclass
from typing import Any

from models_library.celery import (
    GroupUUID,
    OwnerMetadata,
    TaskName,
    TaskUUID,
)
from models_library.notifications import Channel
from models_library.notifications.errors import (
    NotificationsTooManyRecipientsError,
)
from models_library.notifications.rpc import (
    Addressing,
    EmailContact,
    EmailMessage,
    FromIdentity,
    Message,
)
from models_library.products import ProductName
from servicelib.celery.async_jobs.notifications import (
    submit_send_message_task,
    submit_send_messages_task,
)
from servicelib.celery.task_manager import TaskManager

from .._meta import APP_NAME
from ..core.settings import ApplicationSettings
from ..models.product import ProductData
from ..models.template import TemplateRef
from ..repositories.product import ProductRepository
from ._template import TemplateService
from .channel_handlers import for_channel

_logger = logging.getLogger(__name__)

_OWNER_METADATA = OwnerMetadata(owner=APP_NAME)


def _resolve_from_contact(product_data: ProductData, from_identity: FromIdentity) -> EmailContact:
    """Resolve a from_identity into a concrete EmailContact using product data."""
    match from_identity:
        case FromIdentity.SUPPORT:
            return EmailContact(
                name=f"{product_data.display_name} support",
                email=product_data.support_email,
            )
        case FromIdentity.NO_REPLY:
            return EmailContact(
                name=product_data.display_name,
                email=product_data.support_email,
            )


def _prepare_celery_messages(message: Message, *, resolved_from: EmailContact | None = None) -> list[dict[str, Any]]:
    """Dispatches to channel handler to fan out into per-recipient celery payloads.

    Raises:
        NotificationsUnsupportedChannelError: If the channel is not supported.
    """
    handler = for_channel(message.channel)
    return handler.prepare_messages(message, resolved_from=resolved_from)


def _get_task_description(message: Message) -> str | None:
    if message.channel == Channel.email:
        if isinstance(message, EmailMessage):
            return message.content.subject
        return None
    return None


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
        resolved_from: EmailContact | None = None,
        owner_metadata: OwnerMetadata | None = None,
    ) -> tuple[TaskUUID | GroupUUID, TaskName]:
        resolved_owner = owner_metadata or _OWNER_METADATA

        if resolved_from is None:
            product_data = await self.product_repository.get_product_data(product_name)
            resolved_from = _resolve_from_contact(product_data, message.addressing.from_identity)

        messages = _prepare_celery_messages(message, resolved_from=resolved_from)

        num_recipients = len(messages)
        description = _get_task_description(message)

        if num_recipients == 1:
            task_uuid, task_name = await submit_send_message_task(
                self.task_manager,
                owner_metadata=resolved_owner,
                message=messages[0],
                description=description,
            )
            return task_uuid, task_name

        max_recipients = self.settings.NOTIFICATIONS_EMAIL_MAX_RECIPIENTS_PER_MESSAGE
        if num_recipients > max_recipients:
            raise NotificationsTooManyRecipientsError(
                num_recipients=num_recipients,
                max_recipients=max_recipients,
            )

        group_uuid, _, task_name = await submit_send_messages_task(
            self.task_manager,
            owner_metadata=resolved_owner,
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
        owner_metadata: OwnerMetadata | None = None,
    ) -> tuple[TaskUUID | GroupUUID, TaskName]:
        preview = await self.template_service.preview_template(product_name=product_name, ref=ref, context=context)

        product_data = await self.product_repository.get_product_data(product_name)
        resolved_from = _resolve_from_contact(product_data, addressing.from_identity)

        message = EmailMessage(
            addressing=addressing,
            content=preview.message_content.model_dump(),
        )
        return await self.send_message(
            product_name=product_name,
            message=message,
            resolved_from=resolved_from,
            owner_metadata=owner_metadata,
        )
