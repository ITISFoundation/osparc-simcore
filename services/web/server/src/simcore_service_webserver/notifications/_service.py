from dataclasses import asdict
from typing import Any, Final

from aiohttp import web
from models_library.celery import GroupUUID, TaskName, TaskUUID
from models_library.groups import GroupID
from models_library.notifications import (
    Channel,
)
from models_library.notifications.errors import (
    NotificationsNoActiveRecipientsError,
    NotificationsUnsupportedChannelError,
)
from models_library.notifications.rpc import Addressing as RpcAddressing
from models_library.notifications.rpc import Message as RpcMessage
from models_library.notifications.rpc import TemplateRef as RpcTemplateRef
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    preview_template as remote_preview_template,
)
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    search_templates as remote_search_templates,
)
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    send_message as remote_send_message,
)
from servicelib.rabbitmq.rpc_interfaces.notifications import (
    send_message_from_template as remote_send_message_from_template,
)

from ..models import WebServerOwnerMetadata
from ..products import products_service
from ..rabbitmq import get_rabbitmq_rpc_client
from ..users import users_service
from ._helpers import get_product_data
from ._models import (
    Contact,
    EmailAddressing,
    EmailContact,
    EmailContent,
    EmailMessage,
    Template,
    TemplatePreview,
    TemplateRef,
)

_RPC_ADDRESSING_ADAPTER: Final[TypeAdapter[RpcAddressing]] = TypeAdapter(RpcAddressing)
_RPC_MESSAGE_ADAPTER: Final[TypeAdapter[RpcMessage]] = TypeAdapter(RpcMessage)
_RPC_TEMPLATE_REF_ADAPTER: Final[TypeAdapter[RpcTemplateRef]] = TypeAdapter(RpcTemplateRef)


def _get_user_display_name(user: dict) -> str:
    first_name = user.get("first_name") or ""
    last_name = user.get("last_name") or ""
    return f"{first_name} {last_name}".strip()


async def _collect_active_recipients(app: web.Application, group_ids: list[GroupID]) -> list[EmailContact]:
    # Collect all unique user IDs from all groups
    all_user_ids: set[UserID] = set()
    for group_id in group_ids:
        user_ids = await users_service.get_users_in_group(app, gid=group_id)
        all_user_ids.update(user_ids)

    active_users = await users_service.get_active_users_email_data(app, user_ids=list(all_user_ids))

    # Deduplicate by email address while preserving order
    recipients_dict: dict[str, EmailContact] = {}
    for user in active_users:
        email_addr = EmailContact(
            name=_get_user_display_name(user),
            email=user["email"],
        )
        recipients_dict[user["email"]] = email_addr

    return list(recipients_dict.values())


async def _create_email_addressing(
    app: web.Application,
    *,
    product_name: ProductName,
    group_ids: list[GroupID] | None,
    external_contacts: list[Contact] | None,
    reply_to: Contact | None = None,
) -> EmailAddressing:
    """Build email addressing (from/to) for all recipients.

    Raises:
        NotificationsNoActiveRecipientsError: If no active recipients found.
    """
    product = products_service.get_product(app, product_name)

    from_contact = EmailContact(
        name=f"{product.display_name} Support",
        email=product.support_email,
    )

    to_contacts: list[EmailContact] = []

    if group_ids:
        to_contacts = await _collect_active_recipients(app, group_ids=group_ids)

    if external_contacts:
        to_contacts.extend(external_contacts)

    if not to_contacts:
        raise NotificationsNoActiveRecipientsError

    return EmailAddressing(
        from_=from_contact,
        to=to_contacts,
        reply_to=reply_to,
    )


async def _create_email_message(
    app: web.Application,
    *,
    product_name: ProductName,
    group_ids: list[GroupID] | None,
    external_contacts: list[Contact] | None,
    content: dict[str, Any],
) -> EmailMessage:
    """Build a single email message dict with all recipients.

    Raises:
        NotificationsNoActiveRecipientsError: If no active recipients found.
    """
    addressing = await _create_email_addressing(
        app,
        product_name=product_name,
        group_ids=group_ids,
        external_contacts=external_contacts,
    )

    return EmailMessage(
        channel=Channel.email,
        addressing=addressing,
        content=EmailContent(**content),
    )


async def preview_template(
    app: web.Application,
    *,
    product_name: ProductName,
    ref: TemplateRef,
    context: dict[str, Any],
) -> TemplatePreview:
    product_data = get_product_data(app, product_name=product_name)

    enriched_context = {**context, "product": asdict(product_data)}

    rpc_response = await remote_preview_template(
        get_rabbitmq_rpc_client(app),
        ref=_RPC_TEMPLATE_REF_ADAPTER.validate_python(ref.model_dump()),
        context=enriched_context,
    )
    return TemplatePreview(**rpc_response.model_dump())


async def search_templates(
    app: web.Application,
    *,
    channel: str | None = None,
    template_name: str | None = None,
) -> list[Template]:
    rpc_response = await remote_search_templates(
        get_rabbitmq_rpc_client(app),
        channel=channel,
        template_name=template_name,
    )
    return [Template(**t.model_dump()) for t in rpc_response]


async def send_message(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    channel: Channel,
    group_ids: list[GroupID] | None,
    external_contacts: list[Contact] | None,
    content: dict[str, Any],  # NOTE: validated internally
) -> tuple[TaskUUID | GroupUUID, TaskName]:
    match channel:
        case Channel.email:
            message = await _create_email_message(
                app,
                product_name=product_name,
                group_ids=group_ids,
                external_contacts=external_contacts,
                content=content,
            )
        case _:
            raise NotificationsUnsupportedChannelError(channel=channel)

    response = await remote_send_message(
        get_rabbitmq_rpc_client(app),
        message=_RPC_MESSAGE_ADAPTER.validate_python(message.model_dump()),
        owner_metadata=WebServerOwnerMetadata(
            user_id=user_id,
            product_name=product_name,
        ),
    )

    return response.task_or_group_uuid, response.task_name


async def send_message_from_template(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    channel: Channel,
    group_ids: list[GroupID] | None,
    external_contacts: list[Contact] | None,
    reply_to: Contact | None = None,
    template_name: str,
    context: dict[str, Any],
) -> tuple[TaskUUID | GroupUUID, TaskName]:
    match channel:
        case Channel.email:
            addressing = await _create_email_addressing(
                app,
                product_name=product_name,
                group_ids=group_ids,
                external_contacts=external_contacts,
                reply_to=reply_to,
            )
        case _:
            raise NotificationsUnsupportedChannelError(channel=channel)

    product_data = get_product_data(app, product_name=product_name)
    enriched_context = {**context, "product": asdict(product_data)}

    owner_metadata = (
        WebServerOwnerMetadata(
            user_id=user_id,
            product_name=product_name,
        )
        if user_id is not None
        else None
    )

    response = await remote_send_message_from_template(
        get_rabbitmq_rpc_client(app),
        addressing=_RPC_ADDRESSING_ADAPTER.validate_python(addressing.model_dump()),
        template_ref=_RPC_TEMPLATE_REF_ADAPTER.validate_python(
            TemplateRef(channel=channel, template_name=template_name).model_dump()
        ),
        context=enriched_context,
        owner_metadata=owner_metadata,
    )

    return response.task_or_group_uuid, response.task_name
